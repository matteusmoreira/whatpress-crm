"""
Utils package for Altar CRM backend.

This package contains utility functions extracted from server.py for better organization.
"""

# Database helpers
from .db_helpers import (
    is_transient_db_error,
    is_missing_table_or_schema_error,
    is_supabase_not_configured_error,
    db_call_with_retry,
    queue_db_write,
    get_write_queue,
    cache_contact_row,
    get_contacts_cache_by_tenant,
    get_contact_cache_by_id,
    get_contact_cache_by_tenant_phone,
    get_tenant_user_names_cache,
    # Backwards compatibility
    _is_transient_db_error,
    _is_missing_table_or_schema_error,
    _is_supabase_not_configured_error,
    _db_call_with_retry,
    _queue_db_write,
    _cache_contact_row,
)

# Auth helpers
from .auth_helpers import (
    JWT_SECRET,
    create_token,
    verify_token,
    verify_password_and_maybe_upgrade,
    hash_password,
    looks_like_bcrypt_hash,
    normalize_email,
    security,
    # Backwards compatibility
    _looks_like_bcrypt_hash,
    _verify_password_and_maybe_upgrade,
    _normalize_email,
)

# Phone utilities
from .phone_utils import (
    normalize_phone_number,
    normalize_phone,
    format_phone_for_display,
    extract_phone_from_jid,
    phone_to_jid,
)

__all__ = [
    # DB helpers
    "is_transient_db_error",
    "is_missing_table_or_schema_error",
    "is_supabase_not_configured_error",
    "db_call_with_retry",
    "queue_db_write",
    "get_write_queue",
    "cache_contact_row",
    # Auth helpers
    "JWT_SECRET",
    "create_token",
    "verify_token",
    "verify_password_and_maybe_upgrade",
    "hash_password",
    "looks_like_bcrypt_hash",
    "normalize_email",
    "security",
    # Phone utils
    "normalize_phone_number",
    "normalize_phone",
    "format_phone_for_display",
    "extract_phone_from_jid",
    "phone_to_jid",
]
