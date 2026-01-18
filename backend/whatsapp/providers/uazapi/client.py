"""Builders de cliente HTTP para UAZAPI v2."""
from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..base import ConnectionRef
    from ...http import HttpClient

from ..base import ConnectionRef
from ...auth import StaticHeadersAuth
from ...errors import AuthError, ProviderRequestError
from ...http import HttpClient, HttpClientConfig
from .helpers import normalize_base_url


def build_client(
    connection: ConnectionRef,
    *,
    default_base_url: str = "",
) -> tuple["HttpClient", dict[str, Any]]:
    """Constrói cliente HTTP para operações de instância.
    
    UAZAPI v2 usa header 'token' para autenticação de instância.
    """
    cfg = connection.config or {}
    base_url = _resolve_base_url(cfg, default_base_url)
    
    token = str(
        cfg.get("token") or cfg.get("instance_token") or cfg.get("apikey") or cfg.get("api_key") or ""
    ).strip()
    
    if not token:
        raise AuthError("Uazapi não configurada (token).", transient=False)
    if not base_url:
        raise ProviderRequestError(
            "Uazapi não configurada (base_url ou subdomain).",
            provider="uazapi",
            transient=False,
        )
    
    client = HttpClient(
        config=HttpClientConfig(base_url=base_url),
        auth=StaticHeadersAuth(headers={"token": token}),
        provider="uazapi",
    )
    return client, cfg


def build_admin_client(
    connection: ConnectionRef,
    *,
    default_base_url: str = "",
    default_admin_token: str = "",
) -> tuple["HttpClient", dict[str, Any]]:
    """Constrói cliente HTTP para operações admin.
    
    UAZAPI v2 usa header 'admintoken' para operações administrativas.
    """
    cfg = connection.config or {}
    base_url = _resolve_base_url(cfg, default_base_url)
    
    admin_token = str(
        cfg.get("admintoken") or cfg.get("admin_token") or cfg.get("globalApikey") or cfg.get("global_apikey") or ""
    ).strip()
    
    if not admin_token:
        admin_token = default_admin_token
    if not admin_token:
        raise AuthError("Uazapi não configurada (admintoken).", transient=False)
    if not base_url:
        raise ProviderRequestError(
            "Uazapi não configurada (base_url ou subdomain).",
            provider="uazapi",
            transient=False,
        )
    
    client = HttpClient(
        config=HttpClientConfig(base_url=base_url),
        auth=StaticHeadersAuth(headers={"admintoken": admin_token}),
        provider="uazapi",
    )
    return client, cfg


def _resolve_base_url(cfg: dict[str, Any], default_base_url: str) -> str:
    """Resolve a URL base da API."""
    base_url_raw = str(cfg.get("base_url") or cfg.get("url") or cfg.get("baseUrl") or "").strip()
    subdomain = str(cfg.get("subdomain") or "").strip()
    
    if not base_url_raw and subdomain:
        base_url_raw = f"https://{subdomain}.uazapi.com"
    
    base_url = normalize_base_url(base_url_raw)
    if not base_url:
        base_url = normalize_base_url(default_base_url)
    
    return base_url
