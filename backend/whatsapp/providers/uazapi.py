from __future__ import annotations

from typing import Any, Optional

try:
    from ...evolution_api import EvolutionAPI
except ImportError:
    from evolution_api import EvolutionAPI
from ..auth import ApiKeyHeaderAuth
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
    def __init__(self, *, default_base_url: Optional[str] = None, default_admin_token: Optional[str] = None):
        self._default_base_url = (default_base_url or "").strip()
        self._default_admin_token = (default_admin_token or "").strip()

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(provider_id="uazapi", supported_versions=("v1",))

    async def create_instance(
        self,
        ctx: ProviderContext,
        *,
        connection: ConnectionRef,
        webhook_url: Optional[str] = None,
    ) -> dict[str, Any]:
        client, cfg = self._build_admin_client(connection)
        endpoints_cfg = cfg.get("endpoints") if isinstance(cfg.get("endpoints"), dict) else {}
        path = str(endpoints_cfg.get("create_instance") or "/admin/instances").strip()
        base_payload: dict[str, Any] = {
            "name": connection.instance_name,
            "instanceName": connection.instance_name,
            "instance_name": connection.instance_name,
        }
        payloads: list[dict[str, Any]] = []
        if webhook_url:
            payloads.append(
                {
                    **base_payload,
                    "webhookUrl": webhook_url,
                    "webhook_url": webhook_url,
                    "webhookURL": webhook_url,
                }
            )
        payloads.append(base_payload)
        try:
            last: Optional[Exception] = None
            for p in payloads:
                try:
                    return await _request_with_uazapi_fallbacks(
                        client,
                        method="POST",
                        path=path,
                        json=p,
                        instance_name=connection.instance_name,
                    )
                except ProviderRequestError as e:
                    last = e
                    details = e.details or {}
                    if details.get("status_code") not in {400, 404, 405}:
                        raise
            if last:
                raise last
            return await _request_with_uazapi_fallbacks(
                client,
                method="POST",
                path=path,
                json=base_payload,
                instance_name=connection.instance_name,
            )
        except ProviderRequestError:
            raise
        except Exception as e:
            raise ProviderRequestError(
                "Falha ao criar instância.",
                provider="uazapi",
                transient=True,
                details={"error": str(e)},
            )

    async def delete_instance(self, ctx: ProviderContext, *, connection: ConnectionRef) -> dict[str, Any]:
        client, cfg = self._build_admin_client(connection)
        endpoints_cfg = cfg.get("endpoints") if isinstance(cfg.get("endpoints"), dict) else {}
        path = str(endpoints_cfg.get("delete_instance") or "/admin/instances/delete").strip()
        payload: dict[str, Any] = {
            "name": connection.instance_name,
            "instanceName": connection.instance_name,
            "instance_name": connection.instance_name,
        }
        try:
            return await _request_with_uazapi_fallbacks(
                client,
                method="POST",
                path=path,
                json=payload,
                instance_name=connection.instance_name,
            )
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
        client, cfg = self._build_client(connection)
        endpoints_cfg = cfg.get("endpoints") if isinstance(cfg.get("endpoints"), dict) else {}
        path = str(endpoints_cfg.get("connect") or "/instance/connect").strip()
        phone = connection.phone_number or ""
        phone_norm = _format_phone(phone) if phone else ""
        payload: dict[str, Any] = {"qrcode": True, "qr": True, "base64": True}
        if phone_norm:
            payload["phone"] = phone_norm
            payload["phoneNumber"] = phone_norm
            payload["number"] = phone_norm
        try:
            try:
                return await _request_with_uazapi_fallbacks(
                    client,
                    method="POST",
                    path=path,
                    json=payload,
                    instance_name=connection.instance_name,
                )
            except ProviderRequestError as e:
                details = e.details or {}
                if details.get("status_code") not in {400, 405}:
                    raise
                return await _request_with_uazapi_fallbacks(
                    client,
                    method="GET",
                    path=path,
                    json=None,
                    instance_name=connection.instance_name,
                )
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
        client, cfg = self._build_client(connection)
        endpoints_cfg = cfg.get("endpoints") if isinstance(cfg.get("endpoints"), dict) else {}
        path = str(endpoints_cfg.get("get_status") or "/instance/getStatus").strip()
        try:
            return await _request_with_uazapi_fallbacks(
                client,
                method="GET",
                path=path,
                json=None,
                instance_name=connection.instance_name,
            )
        except ProviderRequestError:
            raise
        except Exception as e:
            raise ConnectionError(
                "Falha ao obter estado da conexão.",
                provider="uazapi",
                transient=True,
                details={"error": str(e)},
            )

    async def ensure_webhook(self, ctx: ProviderContext, *, connection: ConnectionRef, webhook_url: str) -> dict[str, Any]:
        client, cfg = self._build_client(connection)
        endpoints_cfg = cfg.get("endpoints") if isinstance(cfg.get("endpoints"), dict) else {}
        path = str(endpoints_cfg.get("ensure_webhook") or "/instance/webhook").strip()
        payload = {"url": webhook_url, "webhookUrl": webhook_url, "webhookURL": webhook_url}
        try:
            return await _request_with_uazapi_fallbacks(
                client,
                method="POST",
                path=path,
                json=payload,
                instance_name=connection.instance_name,
            )
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
        client, cfg = self._build_client(connection)
        endpoints_cfg = cfg.get("endpoints") if isinstance(cfg.get("endpoints"), dict) else {}
        send_text_path = str(endpoints_cfg.get("send_text") or "/message/sendText").strip()
        send_media_path = str(endpoints_cfg.get("send_media") or "/message/sendMedia").strip()

        phone_norm = _format_phone(req.phone)
        kind = (req.kind or "").strip().lower()
        content_str = str(req.content or "").strip()
        base64_payload: Optional[str] = None
        if content_str.startswith("data:") and ";base64," in content_str:
            try:
                base64_payload = content_str.split(";base64,", 1)[1].strip()
            except Exception:
                base64_payload = None

        try:
            if kind in {"text", "message", ""}:
                payload = {"phoneNumber": phone_norm, "message": req.content}
                return await _request_with_uazapi_fallbacks(
                    client,
                    method="POST",
                    path=send_text_path,
                    json=payload,
                    instance_name=connection.instance_name,
                )

            media_type = _map_kind_to_media_type(kind)
            if not media_type:
                payload = {"phoneNumber": phone_norm, "message": req.content}
                return await _request_with_uazapi_fallbacks(
                    client,
                    method="POST",
                    path=send_text_path,
                    json=payload,
                    instance_name=connection.instance_name,
                )

            payload: dict[str, Any] = {
                "phoneNumber": phone_norm,
                "mediaType": media_type,
                "caption": req.caption or "",
            }
            if base64_payload:
                payload["mediaBase64"] = base64_payload
                if req.filename:
                    payload["filename"] = req.filename
            else:
                payload["mediaUrl"] = req.content
                if req.filename:
                    payload["filename"] = req.filename

            return await _request_with_uazapi_fallbacks(
                client,
                method="POST",
                path=send_media_path,
                json=payload,
                instance_name=connection.instance_name,
            )
        except ProviderRequestError:
            raise
        except Exception as e:
            raise ProviderRequestError(
                "Falha ao enviar mensagem.",
                provider="uazapi",
                transient=True,
                details={"error": str(e), "kind": req.kind},
            )

    def parse_webhook(self, ctx: ProviderContext, payload: dict[str, Any]) -> ProviderWebhookEvent:
        if not isinstance(payload, dict):
            data = {"raw": payload}
            return ProviderWebhookEvent(event="unknown", instance=None, data=data)

        parser = EvolutionAPI(base_url="http://unused", api_key="unused")
        parsed: Optional[dict[str, Any]] = None

        try:
            candidate = parser.parse_webhook_message(payload)
            if isinstance(candidate, dict) and candidate.get("event"):
                parsed = candidate
        except Exception:
            parsed = None

        if parsed is None:
            raw_event = str(payload.get("event") or payload.get("type") or "unknown")
            normalized_event = raw_event.strip().lower().replace("-", ".")
            instance = (
                payload.get("instance")
                or payload.get("instanceName")
                or payload.get("instance_id")
                or payload.get("instance_uuid")
            )
            if normalized_event == "messages.upsert":
                data = payload.get("data") or {}
                if not isinstance(data, dict):
                    data = {}
                sender = (
                    data.get("sender")
                    or data.get("phone")
                    or data.get("remoteJid")
                    or data.get("remote_jid")
                )
                remote_jid_raw = None
                if isinstance(sender, str) and sender.strip():
                    s = sender.strip()
                    if "@s.whatsapp.net" in s or "@g.us" in s:
                        remote_jid_raw = s
                    else:
                        remote_jid_raw = f"{s}@s.whatsapp.net"
                text = (
                    data.get("message")
                    or data.get("text")
                    or ""
                )
                msg_type = str(data.get("type") or "").strip() or "text"
                ts = payload.get("timestamp") or payload.get("date_time")
                push_name = (
                    data.get("pushname")
                    or data.get("push_name")
                    or data.get("pushName")
                )
                parsed_fallback = {
                    "event": "message",
                    "instance": instance,
                    "message_id": data.get("id"),
                    "from_me": False,
                    "remote_jid": sender,
                    "remote_jid_raw": remote_jid_raw or sender,
                    "content": text,
                    "type": msg_type,
                    "media_kind": msg_type if msg_type != "text" else None,
                    "media_url": data.get("audio_url") or data.get("media_url"),
                    "timestamp": ts,
                    "push_name": push_name,
                }
                return ProviderWebhookEvent(
                    event="message",
                    instance=instance if isinstance(instance, str) else None,
                    data=parsed_fallback,
                )
            data = dict(payload)
            return ProviderWebhookEvent(
                event=raw_event,
                instance=instance if isinstance(instance, str) else None,
                data=data,
            )

        event = str(parsed.get("event") or "unknown")
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
        data = dict(parsed)
        return ProviderWebhookEvent(
            event=event,
            instance=instance if isinstance(instance, str) else None,
            data=data,
        )

    def _build_client(self, connection: ConnectionRef) -> tuple[HttpClient, dict[str, Any]]:
        cfg = connection.config or {}
        base_url_raw = str(
            cfg.get("base_url") or cfg.get("url") or cfg.get("baseUrl") or ""
        ).strip()
        subdomain = str(cfg.get("subdomain") or "").strip()
        if not base_url_raw and subdomain:
            base_url_raw = f"https://{subdomain}.uazapi.com"
        base_url = base_url_raw.rstrip("/")
        token = str(
            cfg.get("token") or cfg.get("instance_token") or ""
        ).strip()
        if not token:
            raise AuthError("Uazapi não configurada (token).", transient=False)
        if not base_url:
            base_url = self._default_base_url.rstrip("/")
        if not base_url:
            raise ProviderRequestError(
                "Uazapi não configurada (base_url ou subdomain).",
                provider="uazapi",
                transient=False,
            )
        client = HttpClient(
            config=HttpClientConfig(base_url=base_url),
            auth=ApiKeyHeaderAuth(header_name="token", api_key=token),
            provider="uazapi",
        )
        return client, cfg

    def _build_admin_client(self, connection: ConnectionRef) -> tuple[HttpClient, dict[str, Any]]:
        cfg = connection.config or {}
        base_url_raw = str(
            cfg.get("base_url") or cfg.get("url") or cfg.get("baseUrl") or ""
        ).strip()
        subdomain = str(cfg.get("subdomain") or "").strip()
        if not base_url_raw and subdomain:
            base_url_raw = f"https://{subdomain}.uazapi.com"
        base_url = base_url_raw.rstrip("/")
        if not base_url:
            base_url = self._default_base_url.rstrip("/")
        admin_token = str(
            cfg.get("admintoken") or cfg.get("admin_token") or ""
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
        client = HttpClient(
            config=HttpClientConfig(base_url=base_url),
            auth=ApiKeyHeaderAuth(
                header_name="admintoken",
                api_key=admin_token,
            ),
            provider="uazapi",
        )
        return client, cfg


def _format_phone(phone: str) -> str:
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if len(digits) == 10:
        return f"55{digits}"
    if len(digits) == 11 and not digits.startswith("55"):
        return f"55{digits}"
    return digits


def _map_kind_to_media_type(kind: str) -> Optional[str]:
    k = (kind or "").strip().lower()
    if k in {"image", "photo", "picture"}:
        return "image"
    if k in {"video"}:
        return "video"
    if k in {"audio", "voice"}:
        return "audio"
    if k in {"document", "file", "pdf"}:
        return "document"
    if k in {"sticker"}:
        return "sticker"
    return None


def _normalize_path(path: str) -> str:
    p = str(path or "").strip()
    if not p:
        return "/"
    if not p.startswith("/"):
        return f"/{p}"
    return p


def _candidate_paths(path: str, *, instance_name: Optional[str]) -> list[str]:
    p = _normalize_path(path)
    candidates: list[str] = [p]

    if not p.startswith("/api/") and p != "/api":
        candidates.append(f"/api{p}")

    if instance_name:
        inst = str(instance_name or "").strip()
        if inst:
            expanded: list[str] = []
            for base in candidates:
                expanded.append(base)
                if not base.rstrip("/").endswith(f"/{inst}"):
                    expanded.append(f"{base.rstrip('/')}/{inst}")
            candidates = expanded

    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        out.append(c)
    return out


async def _request_with_uazapi_fallbacks(
    client: HttpClient,
    *,
    method: str,
    path: str,
    json: Optional[dict[str, Any]],
    instance_name: Optional[str],
) -> dict[str, Any]:
    last: Optional[Exception] = None
    for candidate_path in _candidate_paths(path, instance_name=instance_name):
        try:
            return await client.request(method, candidate_path, json=json)
        except ProviderRequestError as e:
            last = e
            details = e.details or {}
            status = details.get("status_code")
            if status not in {400, 404, 405}:
                raise
    if last:
        raise last
    return await client.request(method, _normalize_path(path), json=json)

