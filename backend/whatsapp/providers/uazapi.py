from __future__ import annotations

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
        """Cria uma nova instância UAZAPI.
        
        Documentação: POST /instance/create
        Requer: globalApikey no header apikey
        Payload: {instanceName, apikey (opcional), number (opcional)}
        """
        client, cfg = self._build_admin_client(connection)
        
        # Preparar payload conforme documentação UAZAPI
        instance_apikey = str(
            (connection.config or {}).get("token")
            or (connection.config or {}).get("apikey")
            or (connection.config or {}).get("instance_token")
            or ""
        ).strip()
        
        phone = connection.phone_number or ""
        phone_norm = _format_phone(phone) if phone else ""
        
        # Payload baseado na documentação oficial UAZAPI
        payload: dict[str, Any] = {
            "instanceName": connection.instance_name,
        }
        
        # apikey da instância (se fornecida, senão UAZAPI gera automaticamente)
        if instance_apikey:
            payload["apikey"] = instance_apikey
        
        # Número para conectar (retorna código de pareamento)
        if phone_norm:
            payload["number"] = phone_norm
        
        try:
            # Endpoint direto conforme documentação: POST /instance/create
            result = await client.request("POST", "/instance/create", json=payload)
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

    async def delete_instance(self, ctx: ProviderContext, *, connection: ConnectionRef) -> dict[str, Any]:
        """Deleta uma instância UAZAPI.
        
        Documentação: DELETE /instance/delete/{{instance}}
        Requer: apikey da instância no header
        Nota: Só é possível deletar instâncias não conectadas.
        """
        client, cfg = self._build_client(connection)
        path = f"/instance/delete/{connection.instance_name}"
        try:
            return await client.request("DELETE", path, json=None)
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
        """Obtém estado de conexão e QRCode da instância.
        
        Documentação: GET /instance/connectionState/{{instance}}
        Retorna: QRCode em base64, status da conexão, código de pareamento
        """
        client, cfg = self._build_client(connection)
        path = f"/instance/connectionState/{connection.instance_name}"
        
        try:
            result = await client.request("GET", path, json=None)
            
            if isinstance(result, dict):
                # Extrair QRCode da resposta
                qrcode = _extract_qrcode_value(result)
                if qrcode:
                    result["base64"] = qrcode
                
                # Extrair código de pareamento se presente
                if "pairingCode" not in result:
                    code = result.get("code")
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
        
        Documentação: GET /instance/connectionState/{{instance}}
        """
        client, cfg = self._build_client(connection)
        path = f"/instance/connectionState/{connection.instance_name}"
        
        try:
            return await client.request("GET", path, json=None)
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
        """Configura webhook para a instância.
        
        Documentação: POST /webhook/set/{{instance}}
        """
        client, cfg = self._build_client(connection)
        path = f"/webhook/set/{connection.instance_name}"
        
        payload = {
            "url": webhook_url,
            "enabled": True,
            "local_map": False,
            # Eventos principais
            "STATUS_INSTANCE": True,
            "MESSAGES_UPSERT": True,
            "SEND_MESSAGE": True,
            "GROUPS_UPSERT": True,
            "GROUPS_UPDATE": True,
            "GROUP_PARTICIPANTS_UPDATE": True,
            "MESSAGES_UPDATE": True,
            "QRCODE_UPDATED": True,
            "PRESENCE_UPDATE": True,
            "CONNECTION_UPDATE": True,
            "groups_ignore": True,
        }
        
        try:
            return await client.request("POST", path, json=payload)
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
        endpoints_raw = cfg.get("endpoints")
        endpoints_cfg: dict[str, Any] = endpoints_raw if isinstance(endpoints_raw, dict) else {}
        send_text_path = str(endpoints_cfg.get("send_text") or "/message/sendText").strip()
        send_media_path = str(endpoints_cfg.get("send_media") or "/message/sendMedia").strip()
        send_sticker_path = str(endpoints_cfg.get("send_sticker") or "/message/sendSticker").strip()

        phone_norm = _format_phone(req.phone)
        if not phone_norm:
            raise ProviderRequestError("Número de telefone inválido.", provider="uazapi", transient=False)
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
                text_payload = {
                    "number": phone_norm,
                    "phoneNumber": phone_norm,
                    "textMessage": {"text": req.content},
                    "message": req.content,
                    "options": {"delay": 200},
                }
                return await _request_with_uazapi_fallbacks(
                    client,
                    method="POST",
                    path=send_text_path,
                    json=text_payload,
                    instance_name=connection.instance_name,
                )

            if kind in {"sticker"}:
                sticker_payload = {
                    "number": phone_norm,
                    "options": {"delay": 200},
                    "stickerMessage": {"image": base64_payload or req.content},
                }
                return await _request_with_uazapi_fallbacks(
                    client,
                    method="POST",
                    path=send_sticker_path,
                    json=sticker_payload,
                    instance_name=connection.instance_name,
                )

            media_type = _map_kind_to_media_type(kind)
            if not media_type:
                fallback_payload = {
                    "number": phone_norm,
                    "phoneNumber": phone_norm,
                    "textMessage": {"text": req.content},
                    "message": req.content,
                    "options": {"delay": 200},
                }
                return await _request_with_uazapi_fallbacks(
                    client,
                    method="POST",
                    path=send_text_path,
                    json=fallback_payload,
                    instance_name=connection.instance_name,
                )

            media_payload: dict[str, Any] = {
                "number": phone_norm,
                "phoneNumber": phone_norm,
                "mediaMessage": {
                    "mediatype": media_type,
                    "caption": req.caption or "",
                    "media": base64_payload or req.content,
                },
                "options": {"delay": 200},
            }
            if req.filename:
                media_message = media_payload.get("mediaMessage")
                if isinstance(media_message, dict):
                    media_message["fileName"] = req.filename

            return await _request_with_uazapi_fallbacks(
                client,
                method="POST",
                path=send_media_path,
                json=media_payload,
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

    async def send_presence(self, ctx: ProviderContext, *, connection: ConnectionRef, phone: str, presence: str = "composing") -> dict[str, Any]:
        client, cfg = self._build_client(connection)
        endpoints_raw = cfg.get("endpoints")
        endpoints_cfg: dict[str, Any] = endpoints_raw if isinstance(endpoints_raw, dict) else {}
        path = str(endpoints_cfg.get("update_presence") or endpoints_cfg.get("send_presence") or "/chat/updatePresence").strip()
        phone_norm = _format_phone(phone)
        if not phone_norm:
            raise ProviderRequestError("Número de telefone inválido.", provider="uazapi", transient=False)
        payload = {"number": phone_norm, "presence": str(presence or "composing")}
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
                "Falha ao enviar presença.",
                provider="uazapi",
                transient=True,
                details={"error": str(e), "presence": presence},
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
            if normalized_event in {"presence.update", "presence_update", "presence"}:
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
        base_url = _normalize_uazapi_base_url(base_url_raw)
        token = str(cfg.get("token") or cfg.get("instance_token") or "").strip()
        apikey = str(cfg.get("apikey") or cfg.get("api_key") or cfg.get("apiKey") or "").strip()
        credential = token or apikey
        if not credential:
            raise AuthError("Uazapi não configurada (token/apikey).", transient=False)
        if not base_url:
            base_url = self._default_base_url.rstrip("/")
        base_url = _normalize_uazapi_base_url(base_url)
        if not base_url:
            raise ProviderRequestError(
                "Uazapi não configurada (base_url ou subdomain).",
                provider="uazapi",
                transient=False,
            )
        client = HttpClient(
            config=HttpClientConfig(base_url=base_url),
            auth=StaticHeadersAuth(headers={"apikey": credential, "token": credential}),
            provider="uazapi",
        )
        return client, cfg

    def _build_admin_client(self, connection: ConnectionRef) -> tuple[HttpClient, dict[str, Any]]:
        """Constrói cliente HTTP para operações admin (criar/listar instâncias).
        
        UAZAPI usa 'globalApikey' no header 'apikey' para operações admin.
        Documentação: header apikey com valor da globalApikey.
        """
        cfg = connection.config or {}
        base_url_raw = str(
            cfg.get("base_url") or cfg.get("url") or cfg.get("baseUrl") or ""
        ).strip()
        subdomain = str(cfg.get("subdomain") or "").strip()
        if not base_url_raw and subdomain:
            base_url_raw = f"https://{subdomain}.uazapi.com"
        base_url = _normalize_uazapi_base_url(base_url_raw)
        if not base_url:
            base_url = self._default_base_url.rstrip("/")
        base_url = _normalize_uazapi_base_url(base_url)
        
        # Buscar globalApikey (token admin)
        admin_token = str(
            cfg.get("globalApikey")
            or cfg.get("global_apikey")
            or cfg.get("admintoken")
            or cfg.get("admin_token")
            or ""
        ).strip()
        if not admin_token:
            admin_token = self._default_admin_token
        if not admin_token:
            raise AuthError(
                "Uazapi não configurada (globalApikey).",
                transient=False,
            )
        if not base_url:
            raise ProviderRequestError(
                "Uazapi não configurada (base_url ou subdomain).",
                provider="uazapi",
                transient=False,
            )
        # UAZAPI usa header 'apikey' para autenticação (não 'admintoken')
        client = HttpClient(
            config=HttpClientConfig(base_url=base_url),
            auth=StaticHeadersAuth(headers={"apikey": admin_token}),
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


def _extract_qrcode_value(obj: Any) -> Optional[str]:
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


def _normalize_path(path: str) -> str:
    p = str(path or "").strip()
    if not p:
        return "/"
    if not p.startswith("/"):
        return f"/{p}"
    return p


def _normalize_uazapi_base_url(base_url: str) -> str:
    raw = str(base_url or "").strip()
    if not raw:
        return ""
    b = raw.rstrip("/")
    lowered = b.lower()
    for marker in ("/admin", "/instance", "/message", "/chat", "/webhook"):
        idx = lowered.find(f"{marker}/")
        if idx != -1:
            b = b[:idx]
            lowered = b.lower()
            break
        if lowered.endswith(marker):
            b = b[: -len(marker)]
            lowered = b.lower()
            break
    for suffix in ("/api/v2", "/api/v1", "/v2", "/v1", "/api"):
        if lowered.endswith(suffix):
            b = b[: -len(suffix)]
            break
    return b.rstrip("/")


def _sanitize_uazapi_admin_path(path: str, *, op: str) -> str:
    p = str(path or "").strip()
    if not p:
        return "/admin/instances" if op == "create_instance" else "/admin/instances/delete"
    p_norm = _normalize_path(p)
    lowered = p_norm.lower()
    if "admin/instan" in lowered and "instances" not in lowered:
        if op == "create_instance":
            return "/admin/instances"
        return "/admin/instances/delete"
    if op == "delete_instance" and lowered.rstrip("/").endswith("/admin/instances"):
        return "/admin/instances/delete"
    return p_norm


def _candidate_paths(path: str, *, instance_name: Optional[str]) -> list[str]:
    p = _normalize_path(path)
    candidates: list[str] = [p]

    if not p.startswith("/api/") and p != "/api":
        candidates.append(f"/api{p}")

    if not p.startswith("/v1/") and not p.startswith("/api/v1/") and p not in {"/v1", "/api/v1"}:
        candidates.append(f"/v1{p}")
        candidates.append(f"/api/v1{p}")

    if not p.startswith("/v2/") and not p.startswith("/api/v2/") and p not in {"/v2", "/api/v2"}:
        candidates.append(f"/v2{p}")
        candidates.append(f"/api/v2{p}")

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

