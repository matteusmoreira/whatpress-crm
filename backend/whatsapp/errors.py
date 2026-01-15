from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class WhatsAppError(Exception):
    message: str
    code: str = "whatsapp_error"
    transient: bool = False
    details: Optional[dict[str, Any]] = None

    def __str__(self) -> str:
        return self.message


class ConfigError(WhatsAppError):
    def __init__(self, message: str, *, details: Optional[dict[str, Any]] = None):
        super().__init__(message=message, code="config_error", transient=False, details=details)


class ProviderNotFoundError(WhatsAppError):
    def __init__(self, provider_id: str):
        super().__init__(
            message=f"Provedor WhatsApp não encontrado: {provider_id}",
            code="provider_not_found",
            transient=False,
            details={"provider": provider_id},
        )


class AuthError(WhatsAppError):
    def __init__(self, message: str, *, transient: bool = False, details: Optional[dict[str, Any]] = None):
        super().__init__(message=message, code="auth_error", transient=transient, details=details)


class ProviderRequestError(WhatsAppError):
    def __init__(
        self,
        message: str,
        *,
        provider: str,
        status_code: Optional[int] = None,
        transient: bool = False,
        details: Optional[dict[str, Any]] = None,
    ):
        merged_details: dict[str, Any] = {"provider": provider}
        if status_code is not None:
            merged_details["status_code"] = status_code
        if details:
            merged_details.update(details)
        super().__init__(message=message, code="provider_request_error", transient=transient, details=merged_details)


class ConnectionError(WhatsAppError):
    def __init__(self, message: str, *, provider: str, transient: bool = True, details: Optional[dict[str, Any]] = None):
        merged_details: dict[str, Any] = {"provider": provider}
        if details:
            merged_details.update(details)
        super().__init__(message=message, code="connection_error", transient=transient, details=merged_details)

