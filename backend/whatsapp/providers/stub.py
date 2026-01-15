from __future__ import annotations

from typing import Any

from ..errors import ConnectionError, ProviderRequestError
from .base import ConnectionRef, ProviderCapabilities, ProviderContext, ProviderWebhookEvent, SendMessageRequest, WhatsAppProvider


class StubWhatsAppProvider(WhatsAppProvider):
    def __init__(self, provider_id: str):
        self._provider_id = (provider_id or "").strip().lower()

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(provider_id=self._provider_id, supported_versions=())

    async def create_instance(self, ctx: ProviderContext, *, connection: ConnectionRef, webhook_url: str | None = None) -> dict[str, Any]:
        raise ProviderRequestError("Provedor ainda não implementado.", provider=self._provider_id, transient=False)

    async def delete_instance(self, ctx: ProviderContext, *, connection: ConnectionRef) -> dict[str, Any]:
        raise ProviderRequestError("Provedor ainda não implementado.", provider=self._provider_id, transient=False)

    async def connect(self, ctx: ProviderContext, *, connection: ConnectionRef) -> dict[str, Any]:
        raise ConnectionError("Provedor ainda não implementado.", provider=self._provider_id, transient=False)

    async def get_connection_state(self, ctx: ProviderContext, *, connection: ConnectionRef) -> dict[str, Any]:
        raise ProviderRequestError("Provedor ainda não implementado.", provider=self._provider_id, transient=False)

    async def ensure_webhook(self, ctx: ProviderContext, *, connection: ConnectionRef, webhook_url: str) -> dict[str, Any]:
        raise ProviderRequestError("Provedor ainda não implementado.", provider=self._provider_id, transient=False)

    async def send_message(self, ctx: ProviderContext, *, connection: ConnectionRef, req: SendMessageRequest) -> dict[str, Any]:
        raise ProviderRequestError("Provedor ainda não implementado.", provider=self._provider_id, transient=False)

    def parse_webhook(self, ctx: ProviderContext, payload: dict[str, Any]) -> ProviderWebhookEvent:
        return ProviderWebhookEvent(event="unknown", instance=None, data={"raw": payload})
