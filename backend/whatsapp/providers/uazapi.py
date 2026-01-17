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
            normalized_event = raw_event.strip().lower().replace("-", ".").replace("_", ".")
            instance = (
                payload.get("instance")
                or payload.get("instanceName")
                or payload.get("instance_id")
                or payload.get("instance_uuid")
            )
            
            # Evento de mensagem
            if normalized_event in {"messages.upsert", "messages"}:
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
                msg_type = str(data.get("type") or data.get("messageType") or "text").strip() or "text"
                ts = payload.get("timestamp") or payload.get("date_time")
                push_name = (
                    data.get("pushname")
                    or data.get("push_name")
                    or data.get("pushName")
                    or data.get("senderName")
                )
                parsed_fallback = {
                    "event": "message",
                    "instance": instance,
                    "message_id": data.get("id") or data.get("messageid"),
                    "from_me": data.get("fromMe", False),
                    "remote_jid": sender,
                    "remote_jid_raw": remote_jid_raw or sender,
                    "content": text,
                    "type": msg_type,
                    "media_kind": msg_type if msg_type != "text" else None,
                    "media_url": data.get("audio_url") or data.get("media_url") or data.get("fileURL"),
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
