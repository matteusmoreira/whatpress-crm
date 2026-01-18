"""Provider UAZAPI v2 para WhatsApp.

Documentação: uazapiGO - WhatsApp API (v2.0)

Autenticação:
- Endpoints regulares: header 'token' com token da instância
- Endpoints administrativos: header 'admintoken'
"""
from __future__ import annotations

from typing import Any, Optional

from ..base import (
    ConnectionRef,
    ProviderCapabilities,
    ProviderContext,
    ProviderWebhookEvent,
    SendMessageRequest,
    WhatsAppProvider,
)
from ...errors import AuthError, ConnectionError, ProviderRequestError

from .client import build_client, build_admin_client
from .helpers import format_phone, map_kind_to_media_type, extract_qrcode
from .parsers import parse_webhook

# Re-export para compatibilidade com testes que fazem mock do Evolution parser
try:
    from ...evolution_api import EvolutionAPI
except ImportError:
    from evolution_api import EvolutionAPI


class UazapiWhatsAppProvider(WhatsAppProvider):
    """Provider para UAZAPI v2."""

    def __init__(
        self,
        *,
        default_base_url: Optional[str] = None,
        default_admin_token: Optional[str] = None,
    ):
        self._default_base_url = (default_base_url or "").strip()
        self._default_admin_token = (default_admin_token or "").strip()

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(provider_id="uazapi", supported_versions=("v2",))

    # ==================== Instance Management ====================

    async def create_instance(
        self,
        ctx: ProviderContext,
        *,
        connection: ConnectionRef,
        webhook_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """Cria uma nova instância UAZAPI. POST /instance/init"""
        client, cfg = self._build_admin_client(connection)

        payload: dict[str, Any] = {"name": connection.instance_name}
        for field in ("adminField01", "admin_field_01", "adminField02", "admin_field_02"):
            if cfg.get(field):
                key = "adminField01" if "01" in field else "adminField02"
                payload[key] = cfg[field]

        return await self._request(client, "POST", "/instance/init", payload)

    async def list_instances(
        self,
        ctx: ProviderContext,
        *,
        connection: ConnectionRef,
    ) -> dict[str, Any]:
        """Lista todas as instâncias UAZAPI. GET /instance/all"""
        client, _ = self._build_admin_client(connection)
        return await self._request(client, "GET", "/instance/all")

    async def delete_instance(
        self,
        ctx: ProviderContext,
        *,
        connection: ConnectionRef,
    ) -> dict[str, Any]:
        """Deleta uma instância UAZAPI. DELETE /instance"""
        client, _ = self._build_client(connection)
        return await self._request(client, "DELETE", "/instance")

    # ==================== Connection ====================

    async def connect(
        self,
        ctx: ProviderContext,
        *,
        connection: ConnectionRef,
    ) -> dict[str, Any]:
        """Inicia conexão ao WhatsApp. POST /instance/connect"""
        client, cfg = self._build_client(connection)

        payload: dict[str, Any] = {}
        phone = connection.phone_number or cfg.get("phone") or cfg.get("phone_number") or ""
        phone_clean = format_phone(phone)
        if phone_clean:
            payload["phone"] = phone_clean

        result = await self._request(client, "POST", "/instance/connect", payload or None)
        return self._enrich_qr_response(result)

    async def get_connection_state(
        self,
        ctx: ProviderContext,
        *,
        connection: ConnectionRef,
    ) -> dict[str, Any]:
        """Obtém estado de conexão. GET /instance/status"""
        client, _ = self._build_client(connection)
        result = await self._request(client, "GET", "/instance/status")
        return self._enrich_qr_response(result)

    async def disconnect(
        self,
        ctx: ProviderContext,
        *,
        connection: ConnectionRef,
    ) -> dict[str, Any]:
        """Desconecta do WhatsApp. POST /instance/disconnect"""
        client, _ = self._build_client(connection)
        return await self._request(client, "POST", "/instance/disconnect")

    # ==================== Webhook ====================

    async def ensure_webhook(
        self,
        ctx: ProviderContext,
        *,
        connection: ConnectionRef,
        webhook_url: str,
    ) -> dict[str, Any]:
        """Configura webhook. POST /webhook"""
        client, _ = self._build_client(connection)

        payload = {
            "enabled": True,
            "url": webhook_url,
            "events": ["connection", "messages", "messages_update", "presence", "groups"],
            "addUrlEvents": True,
            "addUrlTypesMessages": True,
            "excludeMessages": ["wasSentByApi"],
        }

        return await self._request(client, "POST", "/webhook", payload)

    # ==================== Messaging ====================

    async def send_message(
        self,
        ctx: ProviderContext,
        *,
        connection: ConnectionRef,
        req: SendMessageRequest,
    ) -> dict[str, Any]:
        """Envia mensagem. POST /send/text ou POST /send/media"""
        client, _ = self._build_client(connection)

        phone = format_phone(req.phone)
        if not phone:
            raise ProviderRequestError("Número de telefone inválido.", provider="uazapi", transient=False)

        kind = (req.kind or "").strip().lower()
        content = str(req.content or "").strip()

        # Detectar base64
        base64_payload = None
        if content.startswith("data:") and ";base64," in content:
            try:
                base64_payload = content.split(";base64,", 1)[1].strip()
            except Exception:
                pass

        # Texto
        if kind in {"text", "message", ""}:
            return await self._request(client, "POST", "/send/text", {"number": phone, "text": req.content})

        # Sticker
        if kind == "sticker":
            return await self._request(client, "POST", "/send/media", {
                "number": phone,
                "type": "sticker",
                "file": base64_payload or req.content,
            })

        # Mídia
        media_type = map_kind_to_media_type(kind)
        if media_type:
            payload: dict[str, Any] = {
                "number": phone,
                "type": media_type,
                "file": base64_payload or req.content,
            }
            if req.caption:
                payload["text"] = req.caption
            if req.filename:
                payload["docName"] = req.filename
            return await self._request(client, "POST", "/send/media", payload)

        # Fallback texto
        return await self._request(client, "POST", "/send/text", {"number": phone, "text": req.content})

    async def send_presence(
        self,
        ctx: ProviderContext,
        *,
        connection: ConnectionRef,
        phone: str,
        presence: str = "composing",
    ) -> dict[str, Any]:
        """Envia presença (digitando/gravando). POST /message/presence"""
        client, _ = self._build_client(connection)

        phone_clean = format_phone(phone)
        if not phone_clean:
            raise ProviderRequestError("Número de telefone inválido.", provider="uazapi", transient=False)

        return await self._request(client, "POST", "/message/presence", {
            "number": phone_clean,
            "presence": str(presence or "composing"),
        })

    # ==================== Webhook Parsing ====================

    def parse_webhook(
        self,
        ctx: ProviderContext,
        payload: dict[str, Any],
    ) -> ProviderWebhookEvent:
        """Processa eventos de webhook."""
        return parse_webhook(payload)

    # ==================== Private Helpers ====================

    def _build_client(self, connection: ConnectionRef):
        return build_client(connection, default_base_url=self._default_base_url)

    def _build_admin_client(self, connection: ConnectionRef):
        return build_admin_client(
            connection,
            default_base_url=self._default_base_url,
            default_admin_token=self._default_admin_token,
        )

    async def _request(
        self,
        client,
        method: str,
        path: str,
        json: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Executa request com tratamento de erro padronizado."""
        try:
            return await client.request(method, path, json=json)
        except ProviderRequestError:
            raise
        except Exception as e:
            raise ProviderRequestError(
                f"Falha na requisição {method} {path}.",
                provider="uazapi",
                transient=True,
                details={"error": str(e)},
            )

    def _enrich_qr_response(self, result: dict[str, Any]) -> dict[str, Any]:
        """Adiciona campos de QR code/pairing à resposta."""
        if not isinstance(result, dict):
            return result

        qrcode = extract_qrcode(result)
        if qrcode:
            result["base64"] = qrcode

        if "pairingCode" not in result:
            code = result.get("code") or result.get("paircode")
            if isinstance(code, str) and code.strip():
                result["pairingCode"] = code.strip()

        return result


# Exportar para compatibilidade
__all__ = ["UazapiWhatsAppProvider", "EvolutionAPI"]
