from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from .errors import AuthError, ConfigError, ProviderRequestError


class AuthStrategy:
    async def get_headers(self) -> dict[str, str]:
        raise NotImplementedError


@dataclass(frozen=True)
class StaticHeadersAuth(AuthStrategy):
    headers: dict[str, str]

    async def get_headers(self) -> dict[str, str]:
        return dict(self.headers)


@dataclass(frozen=True)
class ApiKeyHeaderAuth(AuthStrategy):
    header_name: str
    api_key: str

    async def get_headers(self) -> dict[str, str]:
        if not self.api_key:
            raise AuthError("Credencial de API key ausente.", transient=False)
        return {self.header_name: self.api_key}


@dataclass(frozen=True)
class BearerTokenAuth(AuthStrategy):
    token: str

    async def get_headers(self) -> dict[str, str]:
        if not self.token:
            raise AuthError("Token ausente.", transient=False)
        return {"Authorization": f"Bearer {self.token}"}


class OAuth2ClientCredentialsAuth(AuthStrategy):
    def __init__(
        self,
        *,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: Optional[str] = None,
        audience: Optional[str] = None,
        timeout_s: float = 20.0,
    ):
        if not token_url:
            raise ConfigError("OAuth2 token_url não configurado.")
        if not client_id or not client_secret:
            raise ConfigError("OAuth2 client_id/client_secret não configurados.")
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self._audience = audience
        self._timeout_s = timeout_s

        self._access_token: Optional[str] = None
        self._expires_at_epoch: float = 0.0

    async def get_headers(self) -> dict[str, str]:
        token = await self._get_access_token()
        return {"Authorization": f"Bearer {token}"}

    async def _get_access_token(self) -> str:
        now = time.time()
        if self._access_token and now < (self._expires_at_epoch - 30):
            return self._access_token

        data: dict[str, Any] = {"grant_type": "client_credentials"}
        if self._scope:
            data["scope"] = self._scope
        if self._audience:
            data["audience"] = self._audience

        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                resp = await client.post(
                    self._token_url,
                    data=data,
                    auth=(self._client_id, self._client_secret),
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
        except httpx.HTTPError as e:
            raise AuthError("Falha ao obter token OAuth2.", transient=True, details={"error": str(e)})

        if resp.status_code >= 400:
            raise ProviderRequestError(
                "Erro ao obter token OAuth2.",
                provider="oauth2",
                status_code=resp.status_code,
                transient=resp.status_code >= 500,
                details={"body": _safe_text(resp)},
            )

        payload = resp.json() if resp.content else {}
        token = str(payload.get("access_token") or "").strip()
        expires_in = payload.get("expires_in")
        if not token:
            raise AuthError("Resposta OAuth2 sem access_token.", transient=False, details={"payload": payload})

        ttl = 3600
        if isinstance(expires_in, (int, float)) and expires_in > 0:
            ttl = int(expires_in)

        self._access_token = token
        self._expires_at_epoch = time.time() + ttl
        return token


def _safe_text(resp: httpx.Response, limit: int = 2000) -> str:
    try:
        return (resp.text or "")[:limit]
    except Exception:
        return ""

