"""Parsers de webhook para UAZAPI v2."""
from __future__ import annotations

import re
from typing import Any, Optional

from ..base import ProviderWebhookEvent

# Pattern para identificar JIDs do WhatsApp
JID_PATTERN = re.compile(r"(\d{7,20})@(s\.whatsapp\.net|g\.us)", re.IGNORECASE)


def parse_webhook(payload: dict[str, Any]) -> ProviderWebhookEvent:
    """Processa eventos de webhook da UAZAPI v2."""
    if not isinstance(payload, dict):
        return ProviderWebhookEvent(event="unknown", instance=None, data={"raw": payload})

    # Tentar formato UAZAPI v2 primeiro (EventType + chat)
    if payload.get("EventType") == "messages" and isinstance(payload.get("chat"), dict):
        return _parse_message_v2(payload)

    # Fallback para parser Evolution
    parsed = _try_evolution_parser(payload)
    if parsed:
        return _finalize_evolution_parsed(parsed, payload)

    # Parser manual por tipo de evento
    event_type = _get_event_type(payload)
    instance = _get_instance(payload)

    if event_type in {"messages.upsert", "messages"}:
        # Verificar se ainda é formato v2
        if payload.get("EventType") == "messages" and isinstance(payload.get("chat"), dict):
            return _parse_message_v2(payload)
        return _parse_message_fallback(payload, instance)

    if event_type in {"presence.update", "presence"}:
        return _parse_presence(payload, instance)

    if event_type in {"connection", "connection.update"}:
        return _parse_connection(payload, instance)

    # Evento genérico
    return ProviderWebhookEvent(
        event=payload.get("event") or payload.get("EventType") or "unknown",
        instance=instance if isinstance(instance, str) else None,
        data=dict(payload),
    )


def _parse_message_v2(payload: dict[str, Any]) -> ProviderWebhookEvent:
    """Parser para formato UAZAPI v2 com EventType=messages e chat."""
    chat = payload.get("chat", {})
    instance = payload.get("instanceName") or payload.get("instance")

    # Extrair remote_jid
    wa_chatid = chat.get("wa_chatid") or ""
    wa_chatlid = chat.get("wa_chatlid") or ""
    remote_jid_raw = wa_chatid if "@s.whatsapp.net" in wa_chatid else (wa_chatlid or wa_chatid)

    # Extrair phone limpo
    phone_raw = chat.get("phone") or ""
    phone_clean = re.sub(r'[^\d]', '', phone_raw) if phone_raw else ""

    # Resolver remote_jid (LID vs número real)
    if "@lid" in remote_jid_raw or not remote_jid_raw:
        remote_jid = phone_clean if phone_clean else (remote_jid_raw.split("@")[0] if "@" in remote_jid_raw else remote_jid_raw)
    else:
        remote_jid = remote_jid_raw.split("@")[0] if "@" in remote_jid_raw else remote_jid_raw

    # Conteúdo e metadata
    content = chat.get("wa_lastMessageTextVote") or ""
    push_name = chat.get("name") or ""

    # Determinar from_me
    last_sender = chat.get("wa_lastMessageSender") or ""
    owner = payload.get("owner") or chat.get("owner") or ""
    from_me = _is_from_me(last_sender, owner)

    # Timestamp e ID
    timestamp = chat.get("wa_lastMsgTimestamp")
    if timestamp and timestamp > 1000000000000:
        timestamp = timestamp // 1000

    message_id = f"uazapi_{chat.get('id', '')}_{timestamp or ''}"

    # Tipo de mensagem normalizado
    msg_type = (chat.get("wa_lastMessageType") or "text").lower()
    if msg_type in ("conversation", "extendedtextmessage", "extended_text_message"):
        msg_type = "text"

    return ProviderWebhookEvent(
        event="message",
        instance=instance if isinstance(instance, str) else None,
        data={
            "event": "message",
            "instance": instance,
            "remote_jid_raw": remote_jid_raw,
            "remote_jid": remote_jid,
            "from_me": from_me,
            "message_id": message_id,
            "push_name": push_name,
            "content": content,
            "timestamp": timestamp,
            "type": msg_type,
            "v2_format": True,
        },
    )


def _parse_message_fallback(payload: dict[str, Any], instance: Any) -> ProviderWebhookEvent:
    """Parser fallback para mensagens em formato Evolution-like."""
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        data = {}

    msg_obj = _extract_message_object(data)
    key_obj = msg_obj.get("key") if isinstance(msg_obj.get("key"), dict) else {}

    # Extrair sender/remote_jid
    sender = _find_sender_in_objects(msg_obj, data, key_obj)
    remote_jid_raw, remote_jid = _resolve_remote_jid(sender, payload, data)

    # Conteúdo
    text = _extract_text(msg_obj.get("message")) or _extract_text(msg_obj) or _extract_text(data) or ""

    # Tipo
    msg_type = str(msg_obj.get("type") or msg_obj.get("messageType") or data.get("type") or "text").strip() or "text"

    # Timestamp
    ts = msg_obj.get("timestamp") or msg_obj.get("messageTimestamp") or payload.get("timestamp")

    # Push name
    push_name = (
        msg_obj.get("pushname") or msg_obj.get("push_name") or msg_obj.get("pushName") or
        data.get("pushname") or data.get("push_name") or data.get("pushName")
    )

    # From me
    from_me = msg_obj.get("fromMe") if isinstance(msg_obj.get("fromMe"), bool) else (
        key_obj.get("fromMe") if isinstance(key_obj.get("fromMe"), bool) else False
    )

    return ProviderWebhookEvent(
        event="message",
        instance=instance if isinstance(instance, str) else None,
        data={
            "event": "message",
            "instance": instance,
            "message_id": msg_obj.get("id") or key_obj.get("id") or data.get("id"),
            "from_me": from_me,
            "remote_jid": remote_jid or sender,
            "remote_jid_raw": remote_jid_raw or sender,
            "content": text,
            "type": msg_type,
            "media_kind": msg_type if msg_type != "text" else None,
            "media_url": msg_obj.get("audio_url") or msg_obj.get("media_url") or data.get("media_url"),
            "timestamp": ts,
            "push_name": push_name,
        },
    )


def _parse_presence(payload: dict[str, Any], instance: Any) -> ProviderWebhookEvent:
    """Parser para eventos de presença."""
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        data = {}

    presence_data = {}
    presences = data.get("presences") or payload.get("presences")
    if isinstance(presences, list) and presences and isinstance(presences[0], dict):
        presence_data = presences[0]
    if not presence_data:
        presence_data = data

    remote = (
        presence_data.get("id") or presence_data.get("remoteJid") or
        presence_data.get("sender") or data.get("id") or payload.get("remoteJid")
    )
    remote_str = str(remote or "").strip()
    if "@" in remote_str:
        remote_str = remote_str.split("@", 1)[0]

    presence_value = presence_data.get("presence") or presence_data.get("status") or data.get("presence")

    return ProviderWebhookEvent(
        event="presence",
        instance=instance if isinstance(instance, str) else None,
        data={
            "event": "presence",
            "instance": instance,
            "remote_jid": remote_str or None,
            "presence": str(presence_value or "").strip() or None,
            "participant": presence_data.get("participant"),
        },
    )


def _parse_connection(payload: dict[str, Any], instance: Any) -> ProviderWebhookEvent:
    """Parser para eventos de conexão."""
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        data = {}

    status = data.get("status") or data.get("state") or payload.get("status")

    return ProviderWebhookEvent(
        event="connection",
        instance=instance if isinstance(instance, str) else None,
        data={"event": "connection", "instance": instance, "status": status, "data": data},
    )


# ============ Helpers ============

def _get_event_type(payload: dict[str, Any]) -> str:
    """Extrai e normaliza tipo de evento."""
    raw = str(payload.get("event") or payload.get("EventType") or payload.get("type") or "unknown")
    return raw.strip().lower().replace("-", ".").replace("_", ".")


def _get_instance(payload: dict[str, Any]) -> Any:
    """Extrai instância do payload."""
    return (
        payload.get("instance") or payload.get("instanceName") or
        payload.get("instance_id") or payload.get("instance_uuid")
    )


def _is_from_me(sender: str, owner: str) -> bool:
    """Determina se mensagem foi enviada pelo próprio usuário."""
    if not owner or not sender:
        return False
    owner_digits = re.sub(r'[^\d]', '', owner)
    sender_digits = re.sub(r'[^\d]', '', sender.split("@")[0])
    return (
        owner in sender or
        sender.startswith(owner) or
        (owner_digits and sender_digits and owner_digits == sender_digits)
    )


def _try_evolution_parser(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Tenta usar o parser Evolution como fallback."""
    try:
        from ...evolution_api import EvolutionAPI
        parser = EvolutionAPI(base_url="http://unused", api_key="unused")
        candidate = parser.parse_webhook_message(payload)
        if isinstance(candidate, dict) and candidate.get("event"):
            return candidate
    except Exception:
        pass
    return None


def _finalize_evolution_parsed(parsed: dict[str, Any], payload: dict[str, Any]) -> ProviderWebhookEvent:
    """Finaliza evento parseado pelo Evolution, normalizando campos."""
    event = str(parsed.get("event") or "unknown")
    normalized = event.strip().lower()

    if normalized in {"messages", "messages.upsert", "messages_upsert"}:
        event = "message"
    elif normalized in {"messages.update", "messages_update"}:
        event = "message_update"

    instance = parsed.get("instance") or parsed.get("instanceName") or _get_instance(payload)
    data = dict(parsed)

    # Enriquecer dados se necessário
    if event == "message" and not data.get("remote_jid"):
        _enrich_message_data(data, payload)

    return ProviderWebhookEvent(
        event=event,
        instance=instance if isinstance(instance, str) else None,
        data=data,
    )


def _enrich_message_data(data: dict[str, Any], payload: dict[str, Any]) -> None:
    """Enriquece dados de mensagem do payload original."""
    payload_data = payload.get("data") or {}
    if not isinstance(payload_data, dict):
        return

    key_obj = payload_data.get("key") or {}
    if isinstance(key_obj, dict):
        remote_jid_raw = key_obj.get("remoteJid") or ""
        if remote_jid_raw:
            data["remote_jid_raw"] = remote_jid_raw
            data["remote_jid"] = remote_jid_raw.split("@")[0] if "@" in remote_jid_raw else remote_jid_raw
        if "fromMe" in key_obj:
            data["from_me"] = key_obj["fromMe"]
        if key_obj.get("id"):
            data["message_id"] = key_obj["id"]

    push_name = payload_data.get("pushName") or payload_data.get("pushname")
    if push_name:
        data["push_name"] = push_name

    message_obj = payload_data.get("message") or {}
    if isinstance(message_obj, dict):
        content = message_obj.get("conversation") or message_obj.get("text") or message_obj.get("caption")
        if content:
            data["content"] = content

    ts = payload_data.get("messageTimestamp") or payload_data.get("timestamp")
    if ts:
        data["timestamp"] = ts

    data["type"] = payload_data.get("messageType") or payload_data.get("type") or "text"


def _extract_message_object(data: dict[str, Any]) -> dict[str, Any]:
    """Extrai objeto de mensagem de estruturas variadas."""
    msg_obj = data
    messages = data.get("messages")
    if isinstance(messages, list) and messages and isinstance(messages[0], dict):
        msg_obj = messages[0]
    if isinstance(data.get("message"), dict):
        msg_obj = {**msg_obj, **(data.get("message") or {})}
    return msg_obj


def _find_sender_in_objects(*objects: dict[str, Any]) -> Optional[str]:
    """Busca sender em múltiplos objetos."""
    keys = ("sender", "phone", "remoteJid", "remote_jid")
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        for k in keys:
            val = obj.get(k)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return None


def _resolve_remote_jid(sender: Optional[str], payload: dict[str, Any], data: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Resolve remote_jid a partir do sender."""
    sender_str = (sender or "").strip()
    if not sender_str:
        sender_str = _find_sender_deep(payload) or _find_sender_deep(data) or ""

    if not sender_str:
        return None, None

    if "@" in sender_str:
        return sender_str, sender_str.split("@", 1)[0]

    if sender_str.isdigit():
        return f"{sender_str}@s.whatsapp.net", sender_str

    return sender_str, sender_str


def _find_sender_deep(obj: Any, depth: int = 0) -> Optional[str]:
    """Busca recursiva por sender em estrutura aninhada."""
    if depth > 6:
        return None

    if isinstance(obj, str):
        s = obj.strip()
        m = JID_PATTERN.search(s)
        if m:
            return m.group(0)
        if s.isdigit() and 7 <= len(s) <= 20:
            return s
        return None

    if isinstance(obj, dict):
        preferred = ("remoteJid", "remote_jid", "jid", "chatId", "from", "sender", "phone", "number")
        for k in preferred:
            val = obj.get(k)
            if isinstance(val, str) and val.strip():
                s = val.strip()
                m = JID_PATTERN.search(s)
                if m:
                    return m.group(0)
                if s.isdigit() and 7 <= len(s) <= 20:
                    return s
        for v in obj.values():
            found = _find_sender_deep(v, depth + 1)
            if found:
                return found

    if isinstance(obj, list):
        for item in obj:
            found = _find_sender_deep(item, depth + 1)
            if found:
                return found

    return None


def _extract_text(value: Any, depth: int = 0) -> str:
    """Extrai texto de estruturas variadas."""
    if depth > 6:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for k in ("conversation", "text", "caption", "body", "message", "content"):
            v = value.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        for v in value.values():
            found = _extract_text(v, depth + 1)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _extract_text(item, depth + 1)
            if found:
                return found
    return ""
