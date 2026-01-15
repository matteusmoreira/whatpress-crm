from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import httpx

from .auth import AuthStrategy, StaticHeadersAuth
from .errors import ProviderRequestError


@dataclass(frozen=True)
class HttpClientConfig:
    base_url: str
    timeout_s: float = 30.0
    headers: Optional[dict[str, str]] = None


class HttpClient:
    def __init__(self, *, config: HttpClientConfig, auth: Optional[AuthStrategy] = None, provider: str):
        self._config = config
        self._auth = auth or StaticHeadersAuth(headers={})
        self._provider = provider

    async def request(self, method: str, path: str, *, json: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        base = (self._config.base_url or "").rstrip("/")
        if not base:
            raise ProviderRequestError("Base URL não configurada.", provider=self._provider, transient=False)
        url = f"{base}{path}"
        base_headers = dict(self._config.headers or {})
        auth_headers = await self._auth.get_headers()
        headers = {**base_headers, **auth_headers}

        try:
            async with httpx.AsyncClient(timeout=self._config.timeout_s) as client:
                resp = await client.request(method, url, headers=headers, json=json)
        except httpx.HTTPError as e:
            raise ProviderRequestError(
                "Falha de comunicação com provedor.",
                provider=self._provider,
                transient=True,
                details={"error": str(e)},
            )

        if resp.status_code >= 400:
            raise ProviderRequestError(
                "Erro retornado pelo provedor.",
                provider=self._provider,
                status_code=resp.status_code,
                transient=resp.status_code >= 500,
                details={
                    "body": _safe_text(resp),
                    "method": str(method or "").upper(),
                    "url": url,
                    "path": path,
                },
            )

        try:
            return resp.json()
        except Exception:
            return {"raw_text": _safe_text(resp)}


def _safe_text(resp: httpx.Response, limit: int = 4000) -> str:
    try:
        return (resp.text or "")[:limit]
    except Exception:
        return ""
