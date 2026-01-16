from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol

from ..observability import LogContext, Observability


@dataclass(frozen=True)
class ProviderCapabilities:
    provider_id: str
    supported_versions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProviderContext:
    obs: Observability
    log_ctx: LogContext


@dataclass(frozen=True)
class ConnectionRef:
    tenant_id: str
    provider: str
    instance_name: str
    phone_number: Optional[str] = None
    config: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class SendMessageRequest:
    instance_name: str
    phone: str
    kind: str
    content: str
    caption: Optional[str] = None
    filename: Optional[str] = None


@dataclass(frozen=True)
class ProviderWebhookEvent:
    event: str
    instance: Optional[str]
    data: dict[str, Any]


class WhatsAppProvider(Protocol):
    def capabilities(self) -> ProviderCapabilities:
        raise NotImplementedError

    async def create_instance(self, ctx: ProviderContext, *, connection: ConnectionRef, webhook_url: Optional[str] = None) -> dict[str, Any]:
        raise NotImplementedError

    async def delete_instance(self, ctx: ProviderContext, *, connection: ConnectionRef) -> dict[str, Any]:
        raise NotImplementedError

    async def connect(self, ctx: ProviderContext, *, connection: ConnectionRef) -> dict[str, Any]:
        raise NotImplementedError

    async def get_connection_state(self, ctx: ProviderContext, *, connection: ConnectionRef) -> dict[str, Any]:
        raise NotImplementedError

    async def ensure_webhook(self, ctx: ProviderContext, *, connection: ConnectionRef, webhook_url: str) -> dict[str, Any]:
        raise NotImplementedError

    async def send_message(self, ctx: ProviderContext, *, connection: ConnectionRef, req: SendMessageRequest) -> dict[str, Any]:
        raise NotImplementedError

    async def send_presence(self, ctx: ProviderContext, *, connection: ConnectionRef, phone: str, presence: str = "composing") -> dict[str, Any]:
        raise NotImplementedError

    def parse_webhook(self, ctx: ProviderContext, payload: dict[str, Any]) -> ProviderWebhookEvent:
        raise NotImplementedError
