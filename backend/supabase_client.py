from supabase import create_client, Client
import os
import logging
from typing import Optional, cast

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


SUPABASE_URL = _get_first_env("SUPABASE_URL", "REACT_APP_SUPABASE_URL") or ""
SUPABASE_SERVICE_ROLE_KEY = _get_first_env(
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_KEY",
)
SUPABASE_ANON_KEY = _get_first_env(
    "SUPABASE_ANON_KEY",
    "REACT_APP_SUPABASE_ANON_KEY",
)

_resolved_key = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY or ""


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
