from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class LogContext:
    tenant_id: Optional[str] = None
    provider: Optional[str] = None
    instance_name: Optional[str] = None
    correlation_id: Optional[str] = None


class Observability:
    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def info(self, event: str, *, ctx: Optional[LogContext] = None, **fields: Any) -> None:
        self._logger.info(self._format(event, ctx=ctx, fields=fields))

    def warning(self, event: str, *, ctx: Optional[LogContext] = None, **fields: Any) -> None:
        self._logger.warning(self._format(event, ctx=ctx, fields=fields))

    def error(self, event: str, *, ctx: Optional[LogContext] = None, **fields: Any) -> None:
        self._logger.error(self._format(event, ctx=ctx, fields=fields))

    def exception(self, event: str, *, ctx: Optional[LogContext] = None, **fields: Any) -> None:
        self._logger.exception(self._format(event, ctx=ctx, fields=fields))

    def _format(self, event: str, *, ctx: Optional[LogContext], fields: Mapping[str, Any]) -> str:
        parts: list[str] = [event]
        if ctx:
            if ctx.tenant_id:
                parts.append(f"tenant={ctx.tenant_id}")
            if ctx.provider:
                parts.append(f"provider={ctx.provider}")
            if ctx.instance_name:
                parts.append(f"instance={ctx.instance_name}")
            if ctx.correlation_id:
                parts.append(f"corr={ctx.correlation_id}")
        for k, v in fields.items():
            if v is None:
                continue
            parts.append(f"{k}={v}")
        return " ".join(parts)

