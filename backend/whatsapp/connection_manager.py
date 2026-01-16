from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Optional

from .errors import AuthError, ConnectionError, ProviderRequestError, WhatsAppError
from .observability import LogContext, Observability
from .providers.base import ConnectionRef, ProviderContext, WhatsAppProvider


@dataclass(frozen=True)
class ReconnectPolicy:
    max_attempts: int = 5
    initial_delay_s: float = 0.8
    max_delay_s: float = 10.0
    jitter_s: float = 0.2


class ConnectionManager:
    def __init__(self, *, obs: Observability, policy: Optional[ReconnectPolicy] = None):
        self._obs = obs
        self._policy = policy or ReconnectPolicy()

    async def connect_with_retries(
        self,
        provider: WhatsAppProvider,
        *,
        connection: ConnectionRef,
        correlation_id: Optional[str] = None,
    ) -> dict[str, Any]:
        log_ctx = LogContext(
            tenant_id=connection.tenant_id,
            provider=connection.provider,
            instance_name=connection.instance_name,
            correlation_id=correlation_id,
        )
        ctx = ProviderContext(obs=self._obs, log_ctx=log_ctx)

        delay = self._policy.initial_delay_s
        last_error: Optional[Exception] = None
        for attempt in range(1, self._policy.max_attempts + 1):
            try:
                self._obs.info("whatsapp.connect.attempt", ctx=log_ctx, attempt=attempt)
                return await provider.connect(ctx, connection=connection)
            except ConnectionError as e:
                last_error = e
                self._obs.warning(
                    "whatsapp.connect.transient_error",
                    ctx=log_ctx,
                    attempt=attempt,
                    code=e.code,
                    transient=e.transient,
                )
                if not e.transient or attempt >= self._policy.max_attempts:
                    raise
            except (ProviderRequestError, AuthError) as e:
                # Erros do provider/auth: repassar com mensagem original
                last_error = e
                self._obs.warning(
                    "whatsapp.connect.provider_error",
                    ctx=log_ctx,
                    attempt=attempt,
                    code=e.code,
                    transient=e.transient,
                    message=str(e),
                )
                if not e.transient or attempt >= self._policy.max_attempts:
                    # Repassar o erro original para preservar a mensagem
                    raise ConnectionError(
                        str(e.message),
                        provider=connection.provider,
                        transient=e.transient,
                        details=e.details,
                    )
            except Exception as e:
                last_error = e
                self._obs.warning("whatsapp.connect.unexpected_error", ctx=log_ctx, attempt=attempt, error=str(e))
                if attempt >= self._policy.max_attempts:
                    raise ConnectionError(
                        f"Falha ao conectar: {str(e)}",
                        provider=connection.provider,
                        transient=True,
                        details={"error": str(e), "type": type(e).__name__},
                    )

            await asyncio.sleep(_with_jitter(delay, self._policy.jitter_s))
            delay = min(delay * 2, self._policy.max_delay_s)

        raise ConnectionError(
            "Falha ao conectar após tentativas.",
            provider=connection.provider,
            transient=True,
            details={"error": str(last_error) if last_error else None},
        )


def _with_jitter(delay_s: float, jitter_s: float) -> float:
    if jitter_s <= 0:
        return delay_s
    return max(0.0, delay_s + (jitter_s * 0.5))

