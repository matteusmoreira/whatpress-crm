from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ...evolution_api import EvolutionAPI
else:
    try:
        from ...evolution_api import EvolutionAPI
    except ImportError:
        from evolution_api import EvolutionAPI
from ..auth import StaticHeadersAuth
from ..errors import AuthError, ConnectionError, ProviderRequestError
from ..http import HttpClient, HttpClientConfig
from .base import (
    ConnectionRef,
    ProviderCapabilities,
    ProviderContext,
    ProviderWebhookEvent,
    SendMessageRequest,
    WhatsAppProvider,
)


class UazapiWhatsAppProvider(WhatsAppProvider):
    """Provider para UAZAPI v2.
    
    Documentação: uazapiGO - WhatsApp API (v2.0)
    
    Autenticação:
    - Endpoints regulares: header 'token' com token da instância
    - Endpoints administrativos: header 'admintoken'
    """
    
    def __init__(self, *, default_base_url: Optional[str] = None, default_admin_token: Optional[str] = None):
        self._default_base_url = (default_base_url or "").strip()
        self._default_admin_token = (default_admin_token or "").strip()

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(provider_id="uazapi", supported_versions=("v2",))

    async def create_instance(
        self,
        ctx: ProviderContext,
        *,
        connection: ConnectionRef,
        webhook_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """Cria uma nova instância UAZAPI.
        
        Documentação v2: POST /instance/init
        Requer: admintoken no header
        Payload: {name, adminField01, adminField02}
        
        Retorna o token da instância que será usado para todas operações.
        """
        client, cfg = self._build_admin_client(connection)
        
        # Payload conforme documentação UAZAPI v2
        payload: dict[str, Any] = {
            "name": connection.instance_name,
        }
        
        # Campos administrativos opcionais
        admin_field_01 = cfg.get("adminField01") or cfg.get("admin_field_01") or ""
        admin_field_02 = cfg.get("adminField02") or cfg.get("admin_field_02") or ""
        if admin_field_01:
            payload["adminField01"] = admin_field_01
        if admin_field_02:
            payload["adminField02"] = admin_field_02
        
        try:
            # Endpoint v2: POST /instance/init
            result = await client.request("POST", "/instance/init", json=payload)
            return result
        except ProviderRequestError:
            raise
        except Exception as e:
            raise ProviderRequestError(
                "Falha ao criar instância.",
                provider="uazapi",
                transient=True,
                details={"error": str(e)},
            )

    async def list_instances(
        self,
        ctx: ProviderContext,
        *,
        connection: ConnectionRef,
    ) -> dict[str, Any]:
        """Lista todas as instâncias UAZAPI.
        
        Documentação v2: GET /instance/all
        Requer: admintoken no header
        
        Retorna lista com todas as instâncias incluindo:
        - ID e nome de cada instância
        - Status atual (disconnected, connecting, connected)
        - Data de criação
        - Última desconexão e motivo
        - Informações de perfil (se conectado)
        """
        client, cfg = self._build_admin_client(connection)
        
        try:
            # Endpoint v2: GET /instance/all
            result = await client.request("GET", "/instance/all", json=None)
            return result
        except ProviderRequestError:
            raise
        except Exception as e:
            raise ProviderRequestError(
                "Falha ao listar instâncias.",
                provider="uazapi",
                transient=True,
                details={"error": str(e)},
            )

    async def delete_instance(self, ctx: ProviderContext, *, connection: ConnectionRef) -> dict[str, Any]:
        """Deleta uma instância UAZAPI.
        
        Documentação v2: DELETE /instance
        Requer: token da instância no header
        """
        client, cfg = self._build_client(connection)
        
        try:
            # Endpoint v2: DELETE /instance (sem path param)
            return await client.request("DELETE", "/instance", json=None)
        except ProviderRequestError:
            raise
        except Exception as e:
            raise ProviderRequestError(
                "Falha ao deletar instância.",
                provider="uazapi",
                transient=True,
                details={"error": str(e)},
            )

    async def connect(self, ctx: ProviderContext, *, connection: ConnectionRef) -> dict[str, Any]:
        """Inicia o processo de conexão da instância ao WhatsApp.
        
        Documentação v2: POST /instance/connect
        Requer: token da instância no header
        
        Se passar o campo 'phone': gera código de pareamento
        Se não passar 'phone': gera QR code
        
        Retorna QRCode em base64 ou código de pareamento
        """
        client, cfg = self._build_client(connection)
        
        # Se houver telefone configurado, usar código de pareamento
        phone = connection.phone_number or cfg.get("phone") or cfg.get("phone_number") or ""
        payload: dict[str, Any] = {}
        if phone:
            phone_clean = _format_phone(phone)
            if phone_clean:
                payload["phone"] = phone_clean
        
        try:
            # Endpoint v2: POST /instance/connect
            result = await client.request("POST", "/instance/connect", json=payload if payload else None)
            
            if isinstance(result, dict):
                # Extrair QRCode da resposta
                qrcode = _extract_qrcode_value(result)
                if qrcode:
                    result["base64"] = qrcode
                
                # Extrair código de pareamento se presente
                if "pairingCode" not in result:
                    code = result.get("code") or result.get("paircode")
                    if isinstance(code, str) and code.strip():
                        result["pairingCode"] = code.strip()
            
            return result
        except ProviderRequestError:
            raise
        except Exception as e:
            raise ConnectionError(
                "Falha ao conectar instância.",
                provider="uazapi",
                transient=True,
                details={"error": str(e)},
            )

    async def get_connection_state(self, ctx: ProviderContext, *, connection: ConnectionRef) -> dict[str, Any]:
        """Obtém estado de conexão da instância.
        
        Documentação v2: GET /instance/status
        
        Retorna:
        - Estado da conexão (disconnected, connecting, connected)
        - QR code atualizado (se em processo de conexão)
        - Código de pareamento (se disponível)
        - Informações da última desconexão
        """
        client, cfg = self._build_client(connection)
        
        try:
            # Endpoint v2: GET /instance/status
            result = await client.request("GET", "/instance/status", json=None)
            
            if isinstance(result, dict):
                # Extrair QRCode da resposta
                qrcode = _extract_qrcode_value(result)
                if qrcode:
                    result["base64"] = qrcode
                
                # Extrair código de pareamento se presente
                if "pairingCode" not in result:
                    code = result.get("code") or result.get("paircode")
                    if isinstance(code, str) and code.strip():
                        result["pairingCode"] = code.strip()
            
            return result
        except ProviderRequestError:
            raise
        except Exception as e:
            raise ConnectionError(
                "Falha ao obter estado da conexão.",
                provider="uazapi",
                transient=True,
                details={"error": str(e)},
            )

    async def disconnect(self, ctx: ProviderContext, *, connection: ConnectionRef) -> dict[str, Any]:
        """Desconecta a instância do WhatsApp.
        
        Documentação v2: POST /instance/disconnect
        
        Encerra a conexão ativa e requer novo QR code para reconectar.
        """
        client, cfg = self._build_client(connection)
        
        try:
            return await client.request("POST", "/instance/disconnect", json=None)
        except ProviderRequestError:
            raise
        except Exception as e:
            raise ConnectionError(
                "Falha ao desconectar instância.",
                provider="uazapi",
                transient=True,
                details={"error": str(e)},
            )

    async def ensure_webhook(self, ctx: ProviderContext, *, connection: ConnectionRef, webhook_url: str) -> dict[str, Any]:
        """Configura webhook para a instância.
        
        Documentação v2: POST /webhook
        
        Modo simples: envia apenas url e events (sem action ou id)
        O sistema gerencia automaticamente um único webhook por instância.
        """
        client, cfg = self._build_client(connection)
        
        # Payload v2 - modo simples recomendado
        payload = {
            "enabled": True,
            "url": webhook_url,
            "events": [
                "connection",
                "messages",
                "messages_update",
                "presence",
                "groups",
            ],
            "addUrlEvents": True,
            "addUrlTypesMessages": True,
            # Importante: evita loops em automações
            "excludeMessages": ["wasSentByApi"],
        }
        
        try:
            # Endpoint v2: POST /webhook
            return await client.request("POST", "/webhook", json=payload)
        except ProviderRequestError:
            raise
        except Exception as e:
            raise ProviderRequestError(
                "Falha ao configurar webhook.",
                provider="uazapi",
                transient=True,
                details={"error": str(e)},
            )

    async def send_message(self, ctx: ProviderContext, *, connection: ConnectionRef, req: SendMessageRequest) -> dict[str, Any]:
        """Envia mensagem via UAZAPI v2.
        
        Documentação v2:
        - Texto: POST /send/text
        - Mídia: POST /send/media
        - Sticker: POST /send/media com type=sticker
        """
        client, cfg = self._build_client(connection)

        phone_norm = _format_phone(req.phone)
        if not phone_norm:
            raise ProviderRequestError("Número de telefone inválido.", provider="uazapi", transient=False)
        
        kind = (req.kind or "").strip().lower()
        content_str = str(req.content or "").strip()
        
        # Detectar base64
        base64_payload: Optional[str] = None
        if content_str.startswith("data:") and ";base64," in content_str:
            try:
                base64_payload = content_str.split(";base64,", 1)[1].strip()
            except Exception:
                base64_payload = None

        try:
            # Texto ou mensagem sem tipo específico
            if kind in {"text", "message", ""}:
                # Endpoint v2: POST /send/text
                text_payload = {
                    "number": phone_norm,
                    "text": req.content,
                }
                return await client.request("POST", "/send/text", json=text_payload)

            # Sticker
            if kind == "sticker":
                # Endpoint v2: POST /send/media com type=sticker
                sticker_payload = {
                    "number": phone_norm,
                    "type": "sticker",
                    "file": base64_payload or req.content,
                }
                return await client.request("POST", "/send/media", json=sticker_payload)

            # Tipos de mídia
            media_type = _map_kind_to_media_type(kind)
            if media_type:
                # Endpoint v2: POST /send/media
                media_payload: dict[str, Any] = {
                    "number": phone_norm,
                    "type": media_type,
                    "file": base64_payload or req.content,
                }
                
                # Caption/legenda
                if req.caption:
                    media_payload["text"] = req.caption
                
                # Nome do documento
                if req.filename:
                    media_payload["docName"] = req.filename
                
                return await client.request("POST", "/send/media", json=media_payload)

            # Fallback para texto
            fallback_payload = {
                "number": phone_norm,
                "text": req.content,
            }
            return await client.request("POST", "/send/text", json=fallback_payload)

        except ProviderRequestError:
            raise
        except Exception as e:
            raise ProviderRequestError(
                "Falha ao enviar mensagem.",
                provider="uazapi",
                transient=True,
                details={"error": str(e), "kind": req.kind},
            )

    async def send_presence(self, ctx: ProviderContext, *, connection: ConnectionRef, phone: str, presence: str = "composing") -> dict[str, Any]:
        """Envia atualização de presença (digitando/gravando).
        
        Documentação v2: POST /message/presence
        
        Tipos de presença:
        - composing: digitando
        - recording: gravando áudio
        - paused: cancelar presença
        
        A presença é gerenciada em background com tick a cada 10 segundos.
        Limite máximo: 5 minutos.
        """
        client, cfg = self._build_client(connection)
        
        phone_norm = _format_phone(phone)
        if not phone_norm:
            raise ProviderRequestError("Número de telefone inválido.", provider="uazapi", transient=False)
        
        # Payload v2
        payload = {
            "number": phone_norm,
            "presence": str(presence or "composing"),
        }
        
        try:
            # Endpoint v2: POST /message/presence
            return await client.request("POST", "/message/presence", json=payload)
        except ProviderRequestError:
            raise
        except Exception as e:
            raise ProviderRequestError(
                "Falha ao enviar presença.",
                provider="uazapi",
                transient=True,
                details={"error": str(e), "presence": presence},
            )

    def parse_webhook(self, ctx: ProviderContext, payload: dict[str, Any]) -> ProviderWebhookEvent:
        """Processa eventos de webhook da UAZAPI v2."""
        if not isinstance(payload, dict):
            data = {"raw": payload}
            return ProviderWebhookEvent(event="unknown", instance=None, data=data)

        jid_pattern = re.compile(r"(\d{7,20})@(s\.whatsapp\.net|g\.us)", re.IGNORECASE)

        def walk(v: Any, depth: int = 0):
            if depth > 6:
                return
            yield v
            if isinstance(v, dict):
                for vv in v.values():
                    yield from walk(vv, depth + 1)
            elif isinstance(v, list):
                for vv in v:
                    yield from walk(vv, depth + 1)

        def find_sender(obj: Any) -> Optional[str]:
            if not isinstance(obj, (dict, list)):
                if isinstance(obj, str):
                    s = obj.strip()
                    if s:
                        m = jid_pattern.search(s)
                        if m:
                            return m.group(0)
                        if s.isdigit() and 7 <= len(s) <= 20:
                            return s
                return None

            preferred_keys = (
                "remoteJid",
                "remote_jid",
                "jid",
                "chatId",
                "chat_id",
                "from",
                "sender",
                "phone",
                "phoneNumber",
                "number",
                "participant",
                "id",
            )

            for v in walk(obj):
                if isinstance(v, dict):
                    for k in preferred_keys:
                        cand = v.get(k)
                        if isinstance(cand, str) and cand.strip():
                            s = cand.strip()
                            m = jid_pattern.search(s)
                            if m:
                                return m.group(0)
                            if s.isdigit() and 7 <= len(s) <= 20:
                                return s

            for v in walk(obj):
                if isinstance(v, str):
                    s = v.strip()
                    if not s:
                        continue
                    m = jid_pattern.search(s)
                    if m:
                        return m.group(0)
            return None

        parser = EvolutionAPI(base_url="http://unused", api_key="unused")
        parsed: Optional[dict[str, Any]] = None

        try:
            candidate = parser.parse_webhook_message(payload)
            if isinstance(candidate, dict) and candidate.get("event"):
                parsed = candidate
        except Exception:
            parsed = None

        if parsed is None:
            # UAZAPI v2 usa 'EventType' (maiúsculo) em vez de 'event'
            raw_event = str(
                payload.get("event") 
                or payload.get("EventType")  # UAZAPI v2 format
                or payload.get("type") 
                or "unknown"
            )
            normalized_event = raw_event.strip().lower().replace("-", ".").replace("_", ".")
            instance = (
                payload.get("instance")
                or payload.get("instanceName")
                or payload.get("instance_id")
                or payload.get("instance_uuid")
            )
            
            # Evento de mensagem
            if normalized_event in {"messages.upsert", "messages"}:
                # UAZAPI v2 coloca dados na raiz do payload, não dentro de 'data'
                data = payload.get("data") or {}
                if not isinstance(data, dict):
                    data = {}
                
                # Para UAZAPI v2, verificar se 'chat' está na raiz do payload
                # IMPORTANTE: UAZAPI v2 NÃO tem objeto 'message'! 
                # Os dados da mensagem estão em:
                # - chat.wa_lastMessageTextVote = texto da mensagem
                # - chat.wa_lastMessageSender = quem enviou
                # - chat.wa_chatid = número do contato
                v2_chat = payload.get("chat")
                if payload.get("EventType") == "messages" and isinstance(v2_chat, dict):
                    # Formato UAZAPI v2 - dados no objeto chat
                    import re
                    
                    # Extrair dados do formato v2
                    remote_jid_raw = (
                        v2_chat.get("wa_chatid")
                        or v2_chat.get("wa_chatlid")
                        or ""
                    )
                    remote_jid = remote_jid_raw.split("@")[0] if "@" in remote_jid_raw else remote_jid_raw
                    
                    # Extrair número de telefone limpo
                    phone_raw = v2_chat.get("phone") or ""
                    if phone_raw:
                        phone_clean = re.sub(r'[^\d]', '', phone_raw)
                        if not remote_jid:
                            remote_jid = phone_clean
                    
                    # Conteúdo da mensagem está em wa_lastMessageTextVote
                    content = v2_chat.get("wa_lastMessageTextVote") or ""
                    
                    # Determinar se é from_me comparando wa_lastMessageSender com owner
                    last_sender = v2_chat.get("wa_lastMessageSender") or ""
                    owner = payload.get("owner") or v2_chat.get("owner") or ""
                    
                    # Se o sender contém o owner, é uma mensagem enviada por nós
                    from_me = False
                    if owner and last_sender:
                        from_me = owner in last_sender or last_sender.startswith(owner)
                    
                    push_name = v2_chat.get("name") or ""
                    
                    # Gerar ID único para a mensagem baseado no timestamp
                    timestamp = v2_chat.get("wa_lastMsgTimestamp")
                    if timestamp and timestamp > 1000000000000:
                        timestamp = timestamp // 1000  # Converter de ms para s
                    
                    message_id = f"uazapi_{v2_chat.get('id', '')}_{timestamp or ''}"
                    
                    msg_type = (v2_chat.get("wa_lastMessageType") or "text").lower()
                    if msg_type == "conversation":
                        msg_type = "text"
                    
                    return ProviderWebhookEvent(
                        event="message",
                        instance=instance if isinstance(instance, str) else None,
                        data={
                            "event": "messages",
                            "instance": instance,
                            "remote_jid_raw": remote_jid_raw,
                            "remote_jid": remote_jid,
                            "from_me": from_me,
                            "message_id": message_id,
                            "push_name": push_name,
                            "content": content,
                            "timestamp": timestamp,
                            "type": msg_type,
                            "v2_format": True,  # Flag para indicar formato v2
                        },
                    )

                msg_obj: dict[str, Any] = data
                messages = data.get("messages")
                if isinstance(messages, list) and messages:
                    first = messages[0]
                    if isinstance(first, dict):
                        msg_obj = first
                if isinstance(data.get("message"), dict):
                    msg_obj = {**msg_obj, **(data.get("message") or {})}

                key_obj: dict[str, Any] = {}
                key_candidate = msg_obj.get("key")
                if isinstance(key_candidate, dict):
                    key_obj = key_candidate

                data_key_obj: dict[str, Any] = {}
                data_key_candidate = data.get("key")
                if isinstance(data_key_candidate, dict):
                    data_key_obj = data_key_candidate

                sender = (
                    msg_obj.get("sender")
                    or msg_obj.get("phone")
                    or msg_obj.get("remoteJid")
                    or msg_obj.get("remote_jid")
                    or key_obj.get("remoteJid")
                    or key_obj.get("remote_jid")
                    or data.get("sender")
                    or data.get("phone")
                    or data.get("remoteJid")
                    or data.get("remote_jid")
                    or data_key_obj.get("remoteJid")
                    or data_key_obj.get("remote_jid")
                )

                remote_jid_raw: Optional[str] = None
                remote_jid: Optional[str] = None
                sender_str = sender.strip() if isinstance(sender, str) else ""
                if not sender_str:
                    sender_str = find_sender(payload) or find_sender(data) or ""
                if sender_str:
                    s = sender_str.strip()
                    if "@" in s:
                        remote_jid_raw = s
                        remote_jid = s.split("@", 1)[0]
                    else:
                        remote_jid = s
                        if s.isdigit():
                            remote_jid_raw = f"{s}@s.whatsapp.net"
                        else:
                            remote_jid_raw = s

                def _extract_text(value: Any, depth: int = 0) -> str:
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
                        return ""
                    if isinstance(value, list):
                        for item in value:
                            found = _extract_text(item, depth + 1)
                            if found:
                                return found
                        return ""
                    return ""

                text = (
                    _extract_text(msg_obj.get("message"))
                    or _extract_text(msg_obj)
                    or _extract_text(data)
                    or ""
                )

                msg_type = str(
                    msg_obj.get("type")
                    or msg_obj.get("messageType")
                    or msg_obj.get("message_type")
                    or data.get("type")
                    or data.get("messageType")
                    or "text"
                ).strip() or "text"

                ts = (
                    msg_obj.get("timestamp")
                    or msg_obj.get("messageTimestamp")
                    or payload.get("timestamp")
                    or payload.get("date_time")
                )

                push_name = (
                    msg_obj.get("pushname")
                    or msg_obj.get("push_name")
                    or msg_obj.get("pushName")
                    or msg_obj.get("senderName")
                    or data.get("pushname")
                    or data.get("push_name")
                    or data.get("pushName")
                    or data.get("senderName")
                )

                from_me = (
                    msg_obj.get("fromMe")
                    if isinstance(msg_obj.get("fromMe"), bool)
                    else (key_obj.get("fromMe") if isinstance(key_obj.get("fromMe"), bool) else False)
                )

                parsed_fallback = {
                    "event": "message",
                    "instance": instance,
                    "message_id": msg_obj.get("id") or key_obj.get("id") or data.get("id") or data.get("messageid"),
                    "from_me": from_me,
                    "remote_jid": remote_jid or sender,
                    "remote_jid_raw": remote_jid_raw or sender,
                    "content": text,
                    "type": msg_type,
                    "media_kind": msg_type if msg_type != "text" else None,
                    "media_url": (
                        msg_obj.get("audio_url")
                        or msg_obj.get("media_url")
                        or msg_obj.get("fileURL")
                        or data.get("audio_url")
                        or data.get("media_url")
                        or data.get("fileURL")
                    ),
                    "timestamp": ts,
                    "push_name": push_name,
                }
                return ProviderWebhookEvent(
                    event="message",
                    instance=instance if isinstance(instance, str) else None,
                    data=parsed_fallback,
                )
            
            # Evento de presença
            if normalized_event in {"presence.update", "presence"}:
                data = payload.get("data") or {}
                if not isinstance(data, dict):
                    data = {}

                presence_data: dict[str, Any] = {}
                presences = data.get("presences") or payload.get("presences")
                if isinstance(presences, list) and presences:
                    first = presences[0]
                    if isinstance(first, dict):
                        presence_data = first
                if not presence_data:
                    presence_data = data

                remote = (
                    presence_data.get("id")
                    or presence_data.get("remoteJid")
                    or presence_data.get("remote_jid")
                    or presence_data.get("sender")
                    or presence_data.get("phone")
                    or data.get("id")
                    or payload.get("remoteJid")
                    or payload.get("remote_jid")
                )
                remote_str = str(remote or "").strip()
                if "@" in remote_str:
                    remote_str = remote_str.split("@", 1)[0]

                presence_value = (
                    presence_data.get("presence")
                    or presence_data.get("status")
                    or data.get("presence")
                    or payload.get("presence")
                )
                presence_str = str(presence_value or "").strip() or None

                parsed_presence = {
                    "event": "presence",
                    "instance": instance,
                    "remote_jid": remote_str or None,
                    "presence": presence_str,
                    "participant": presence_data.get("participant"),
                }
                return ProviderWebhookEvent(
                    event="presence",
                    instance=instance if isinstance(instance, str) else None,
                    data=parsed_presence,
                )
            
            # Evento de conexão
            if normalized_event in {"connection", "connection.update"}:
                data = payload.get("data") or {}
                if not isinstance(data, dict):
                    data = {}
                
                status = data.get("status") or data.get("state") or payload.get("status")
                
                parsed_connection = {
                    "event": "connection",
                    "instance": instance,
                    "status": status,
                    "data": data,
                }
                return ProviderWebhookEvent(
                    event="connection",
                    instance=instance if isinstance(instance, str) else None,
                    data=parsed_connection,
                )
            
            # Evento genérico
            data = dict(payload)
            return ProviderWebhookEvent(
                event=raw_event,
                instance=instance if isinstance(instance, str) else None,
                data=data,
            )

        event = str(parsed.get("event") or "unknown")
        
        # Normalizar evento para compatibilidade com server.py
        # UAZAPI envia "messages" mas server.py espera "message"
        normalized_event = event.strip().lower()
        if normalized_event in {"messages", "messages.upsert", "messages_upsert"}:
            event = "message"
        elif normalized_event in {"messages.update", "messages_update"}:
            event = "message_update"
        
        instance = (
            parsed.get("instance")
            or parsed.get("instanceName")
            or parsed.get("instance_id")
            or parsed.get("instance_uuid")
            or payload.get("instance")
            or payload.get("instanceName")
            or payload.get("instance_id")
            or payload.get("instance_uuid")
        )
        
        # Se o evento é de mensagem mas não tem remote_jid, tentar extrair do payload original
        data = dict(parsed)
        if event == "message" and not data.get("remote_jid"):
            # Extrair dados do payload UAZAPI
            payload_data = payload.get("data") or {}
            if isinstance(payload_data, dict):
                key_obj = payload_data.get("key") or {}
                if isinstance(key_obj, dict):
                    remote_jid_raw = key_obj.get("remoteJid") or key_obj.get("remote_jid") or ""
                    if remote_jid_raw:
                        data["remote_jid_raw"] = remote_jid_raw
                        data["remote_jid"] = remote_jid_raw.split("@")[0] if "@" in remote_jid_raw else remote_jid_raw
                    
                    if "fromMe" in key_obj:
                        data["from_me"] = key_obj["fromMe"]
                    
                    if key_obj.get("id"):
                        data["message_id"] = key_obj["id"]
                
                # Extrair pushName
                push_name = payload_data.get("pushName") or payload_data.get("pushname") or payload_data.get("push_name")
                if push_name:
                    data["push_name"] = push_name
                
                # Extrair conteúdo da mensagem
                message_obj = payload_data.get("message") or {}
                if isinstance(message_obj, dict):
                    content = (
                        message_obj.get("conversation")
                        or message_obj.get("text")
                        or message_obj.get("caption")
                        or message_obj.get("body")
                    )
                    if content:
                        data["content"] = content
                
                # Extrair timestamp
                ts = payload_data.get("messageTimestamp") or payload_data.get("timestamp")
                if ts:
                    data["timestamp"] = ts
                
                # Extrair tipo de mensagem
                msg_type = payload_data.get("messageType") or payload_data.get("type") or "text"
                data["type"] = msg_type
        
        return ProviderWebhookEvent(
            event=event,
            instance=instance if isinstance(instance, str) else None,
            data=data,
        )

    def _build_client(self, connection: ConnectionRef) -> tuple[HttpClient, dict[str, Any]]:
        """Constrói cliente HTTP para operações de instância.
        
        UAZAPI v2 usa header 'token' para autenticação de instância.
        """
        cfg = connection.config or {}
        base_url = self._resolve_base_url(cfg)
        
        # Token da instância
        token = str(
            cfg.get("token")
            or cfg.get("instance_token")
            or cfg.get("apikey")
            or cfg.get("api_key")
            or ""
        ).strip()
        
        if not token:
            raise AuthError("Uazapi não configurada (token).", transient=False)
        if not base_url:
            raise ProviderRequestError(
                "Uazapi não configurada (base_url ou subdomain).",
                provider="uazapi",
                transient=False,
            )
        
        # UAZAPI v2 usa apenas header 'token'
        client = HttpClient(
            config=HttpClientConfig(base_url=base_url),
            auth=StaticHeadersAuth(headers={"token": token}),
            provider="uazapi",
        )
        return client, cfg

    def _build_admin_client(self, connection: ConnectionRef) -> tuple[HttpClient, dict[str, Any]]:
        """Constrói cliente HTTP para operações admin (criar/listar instâncias).
        
        UAZAPI v2 usa header 'admintoken' para operações administrativas.
        """
        cfg = connection.config or {}
        base_url = self._resolve_base_url(cfg)
        
        # Admin token
        admin_token = str(
            cfg.get("admintoken")
            or cfg.get("admin_token")
            or cfg.get("globalApikey")
            or cfg.get("global_apikey")
            or ""
        ).strip()
        
        if not admin_token:
            admin_token = self._default_admin_token
        if not admin_token:
            raise AuthError(
                "Uazapi não configurada (admintoken).",
                transient=False,
            )
        if not base_url:
            raise ProviderRequestError(
                "Uazapi não configurada (base_url ou subdomain).",
                provider="uazapi",
                transient=False,
            )
        
        # UAZAPI v2 usa header 'admintoken' para autenticação admin
        client = HttpClient(
            config=HttpClientConfig(base_url=base_url),
            auth=StaticHeadersAuth(headers={"admintoken": admin_token}),
            provider="uazapi",
        )
        return client, cfg

    def _resolve_base_url(self, cfg: dict[str, Any]) -> str:
        """Resolve a URL base da API."""
        base_url_raw = str(
            cfg.get("base_url") or cfg.get("url") or cfg.get("baseUrl") or ""
        ).strip()
        subdomain = str(cfg.get("subdomain") or "").strip()
        
        if not base_url_raw and subdomain:
            base_url_raw = f"https://{subdomain}.uazapi.com"
        
        base_url = _normalize_base_url(base_url_raw)
        
        if not base_url:
            base_url = _normalize_base_url(self._default_base_url)
        
        return base_url


def _format_phone(phone: str) -> str:
    """Formata número de telefone para padrão brasileiro."""
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if len(digits) == 10:
        return f"55{digits}"
    if len(digits) == 11 and not digits.startswith("55"):
        return f"55{digits}"
    return digits


def _map_kind_to_media_type(kind: str) -> Optional[str]:
    """Mapeia tipo de mídia para valores aceitos pela API v2.
    
    Tipos suportados: image, video, audio, document, ptt, ptv, sticker, myaudio
    """
    k = (kind or "").strip().lower()
    if k in {"image", "photo", "picture"}:
        return "image"
    if k in {"video"}:
        return "video"
    if k in {"audio", "voice"}:
        return "audio"
    if k in {"ptt", "voice_message"}:
        return "ptt"
    if k in {"document", "file", "pdf"}:
        return "document"
    if k in {"sticker"}:
        return "sticker"
    return None


def _extract_qrcode_value(obj: Any) -> Optional[str]:
    """Extrai valor do QR code de várias estruturas de resposta."""
    def pick_from_dict(d: dict[str, Any]) -> Optional[str]:
        base64 = d.get("base64")
        if isinstance(base64, str) and base64.strip():
            return base64.strip()
        for k in ("qrcode", "qr", "qrCode", "qr_code"):
            v = d.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
            if isinstance(v, dict):
                nested = v.get("base64") or v.get("qrcode") or v.get("qr") or v.get("qrCode") or v.get("qr_code")
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()
        return None

    if not isinstance(obj, dict):
        return None
    direct = pick_from_dict(obj)
    if direct:
        return direct
    for k in ("instance", "data", "response"):
        nested = obj.get(k)
        if isinstance(nested, dict):
            val = pick_from_dict(nested)
            if val:
                return val
    return None


def _normalize_base_url(base_url: str) -> str:
    """Normaliza URL base removendo sufixos de versão e paths."""
    raw = str(base_url or "").strip()
    if not raw:
        return ""
    
    b = raw.rstrip("/")
    
    # Remover paths de API se incluídos acidentalmente
    lowered = b.lower()
    for marker in ("/instance", "/message", "/send", "/webhook", "/group", "/chat"):
        if lowered.endswith(marker):
            b = b[: -len(marker)]
            break
    
    return b.rstrip("/")
