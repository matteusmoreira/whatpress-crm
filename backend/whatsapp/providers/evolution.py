from __future__ import annotations

from typing import Any, Optional

from ...evolution_api import EvolutionAPI
from ..errors import AuthError, ConnectionError, ProviderRequestError
from ..observability import Observability
from .base import (
    ConnectionRef,
    ProviderCapabilities,
    ProviderContext,
    ProviderWebhookEvent,
    SendMessageRequest,
    WhatsAppProvider,
)


class EvolutionWhatsAppProvider(WhatsAppProvider):
    def __init__(self, *, default_base_url: Optional[str] = None, default_api_key: Optional[str] = None):
        self._default_base_url = (default_base_url or "").strip()
        self._default_api_key = (default_api_key or "").strip()

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(provider_id="evolution", supported_versions=("v2",))

    async def create_instance(
        self,
        ctx: ProviderContext,
        *,
        connection: ConnectionRef,
        webhook_url: Optional[str] = None,
    ) -> dict[str, Any]:
        client = self._build_client(connection, ctx.obs)
        try:
            return await client.create_instance(connection.instance_name, webhook_url=webhook_url)
        except Exception as e:
            raise ProviderRequestError(
                "Falha ao criar instância.",
                provider="evolution",
                transient=True,
                details={"error": str(e)},
            )

    async def delete_instance(self, ctx: ProviderContext, *, connection: ConnectionRef) -> dict[str, Any]:
        client = self._build_client(connection, ctx.obs)
        try:
            return await client.delete_instance(connection.instance_name)
        except Exception as e:
            raise ProviderRequestError(
                "Falha ao deletar instância.",
                provider="evolution",
                transient=True,
                details={"error": str(e)},
            )

    async def connect(self, ctx: ProviderContext, *, connection: ConnectionRef) -> dict[str, Any]:
        client = self._build_client(connection, ctx.obs)
        try:
            return await client.connect_instance(connection.instance_name)
        except Exception as e:
            raise ConnectionError("Falha ao conectar instância.", provider="evolution", transient=True, details={"error": str(e)})

    async def get_connection_state(self, ctx: ProviderContext, *, connection: ConnectionRef) -> dict[str, Any]:
        client = self._build_client(connection, ctx.obs)
        try:
            return await client.get_connection_state(connection.instance_name)
        except Exception as e:
            raise ConnectionError(
                "Falha ao obter estado da conexão.",
                provider="evolution",
                transient=True,
                details={"error": str(e)},
            )

    async def ensure_webhook(self, ctx: ProviderContext, *, connection: ConnectionRef, webhook_url: str) -> dict[str, Any]:
        client = self._build_client(connection, ctx.obs)
        try:
            return await client.set_webhook(connection.instance_name, webhook_url)
        except Exception as e:
            raise ProviderRequestError(
                "Falha ao configurar webhook.",
                provider="evolution",
                transient=True,
                details={"error": str(e)},
            )

    async def send_message(self, ctx: ProviderContext, *, connection: ConnectionRef, req: SendMessageRequest) -> dict[str, Any]:
        client = self._build_client(connection, ctx.obs)
        try:
            kind = (req.kind or "").strip().lower()
            content_str = str(req.content or "").strip()
            base64_payload = None
            if content_str.startswith("data:") and ";base64," in content_str:
                try:
                    base64_payload = content_str.split(";base64,", 1)[1].strip()
                except Exception:
                    base64_payload = None
            if kind in {"text", "message"}:
                return await client.send_text(req.instance_name, req.phone, req.content)
            if kind in {"image", "video"}:
                if base64_payload:
                    return await client.send_media(req.instance_name, req.phone, kind, media_base64=base64_payload, caption=req.caption)
                return await client.send_media(req.instance_name, req.phone, kind, media_url=req.content, caption=req.caption)
            if kind in {"audio", "voice"}:
                if base64_payload:
                    return await client.send_media(
                        req.instance_name,
                        req.phone,
                        "audio",
                        media_base64=base64_payload,
                        caption=req.caption or "",
                        filename=req.filename,
                    )
                return await client.send_audio(req.instance_name, req.phone, req.content)
            if kind in {"document", "file"}:
                if base64_payload:
                    return await client.send_media(
                        req.instance_name,
                        req.phone,
                        "document",
                        media_base64=base64_payload,
                        caption=req.caption,
                        filename=req.filename,
                    )
                return await client.send_media(
                    req.instance_name,
                    req.phone,
                    "document",
                    media_url=req.content,
                    caption=req.caption,
                    filename=req.filename,
                )
            if kind in {"sticker"}:
                return await client.send_sticker(req.instance_name, req.phone, base64_payload or req.content)
            return await client.send_text(req.instance_name, req.phone, req.content)
        except Exception as e:
            raise ProviderRequestError(
                "Falha ao enviar mensagem.",
                provider="evolution",
                transient=True,
                details={"error": str(e), "kind": req.kind},
            )

    def parse_webhook(self, ctx: ProviderContext, payload: dict[str, Any]) -> ProviderWebhookEvent:
        parser = EvolutionAPI(base_url="http://unused", api_key="unused")
        parsed = parser.parse_webhook_message(payload)
        if not isinstance(parsed, dict):
            parsed = {"event": "unknown", "data": {"raw": parsed}}
        event = str(parsed.get("event") or "unknown")
        instance = parsed.get("instance")
        data = dict(parsed)
        return ProviderWebhookEvent(event=event, instance=instance if isinstance(instance, str) else None, data=data)

    def _build_client(self, connection: ConnectionRef, obs: Observability) -> EvolutionAPI:
        cfg = connection.config or {}
        base_url = (str(cfg.get("base_url") or "").strip() or self._default_base_url).strip()
        api_key = (str(cfg.get("api_key") or cfg.get("apikey") or "").strip() or self._default_api_key).strip()
        if not api_key:
            raise AuthError("Evolution API não configurada (api_key).", transient=False)
        if not base_url:
            raise ProviderRequestError("Evolution API não configurada (base_url).", provider="evolution", transient=False)
        return EvolutionAPI(base_url=base_url, api_key=api_key)
