from supabase import create_client, Client
import os
import logging
from typing import Optional, cast, Any, Dict
import base64
import json

logger = logging.getLogger(__name__)

_SUPABASE_NOT_CONFIGURED_ERROR = (
    "Supabase não configurado (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY)."
)
_SUPABASE_NOT_CONFIGURED_WARNING = (
    "Supabase não configurado: defina SUPABASE_URL e "
    "SUPABASE_SERVICE_ROLE_KEY."
)


def _get_first_env(*names: str) -> Optional[str]:
    for name in names:
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return None


def _decode_jwt_payload_unverified(token: str) -> Dict[str, Any]:
    try:
        parts = (token or "").split(".")
        if len(parts) < 2:
            return {}
        payload_b64 = parts[1]
        padding = "=" * (-len(payload_b64) % 4)
        raw = base64.urlsafe_b64decode(payload_b64 + padding)
        obj = json.loads(raw.decode("utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _is_service_role_key(key: Optional[str]) -> bool:
    if not key:
        return False
    payload = _decode_jwt_payload_unverified(key)
    role = str(payload.get("role") or "").strip().lower()
    return role == "service_role"


SUPABASE_URL = _get_first_env("SUPABASE_URL", "REACT_APP_SUPABASE_URL") or ""
_candidate_service_key = _get_first_env(
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_KEY",
)
SUPABASE_ANON_KEY = _get_first_env(
    "SUPABASE_ANON_KEY",
    "REACT_APP_SUPABASE_ANON_KEY",
)

SUPABASE_SERVICE_ROLE_KEY = (
    _candidate_service_key
    if _is_service_role_key(_candidate_service_key)
    else None
)
ALLOW_ANON_BACKEND = (
    (os.getenv("SUPABASE_ALLOW_ANON_BACKEND") or "").strip().lower()
    in {"1", "true", "yes", "y"}
)

_resolved_key = (
    SUPABASE_SERVICE_ROLE_KEY
    or (SUPABASE_ANON_KEY if ALLOW_ANON_BACKEND else "")
    or ""
)


class _SupabaseNotConfigured:
    def table(self, *_args, **_kwargs):
        raise RuntimeError(_SUPABASE_NOT_CONFIGURED_ERROR)

    def rpc(self, *_args, **_kwargs):
        raise RuntimeError(_SUPABASE_NOT_CONFIGURED_ERROR)

    @property
    def storage(self):
        raise RuntimeError(_SUPABASE_NOT_CONFIGURED_ERROR)


if SUPABASE_URL and _resolved_key:
    supabase: Client = create_client(SUPABASE_URL, _resolved_key)
else:
    logger.warning(_SUPABASE_NOT_CONFIGURED_WARNING)
    supabase = cast(Client, _SupabaseNotConfigured())
