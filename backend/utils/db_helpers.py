"""
Database helper utilities extracted from server.py.

These functions handle database operations with retry logic, error detection,
and caching mechanisms.
"""

import logging
import os
import time
import hashlib
from collections import deque
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Set

logger = logging.getLogger(__name__)


# ==================== DATABASE WRITE QUEUE ====================
_DB_WRITE_QUEUE_MAX = int(os.getenv("DB_WRITE_QUEUE_MAX", "2000") or "2000")
_DB_WRITE_QUEUE: "deque[dict]" = deque(maxlen=max(100, _DB_WRITE_QUEUE_MAX))


# ==================== CACHES ====================
_CONTACTS_CACHE_BY_TENANT: Dict[str, dict] = {}
_CONTACT_CACHE_BY_ID: Dict[str, dict] = {}
_CONTACT_CACHE_BY_TENANT_PHONE: Dict[str, dict] = {}
_TENANT_USER_NAMES_CACHE: Dict[str, Set[str]] = {}


# ==================== ERROR DETECTION ====================
def is_transient_db_error(exc: Exception) -> bool:
    """Check if an exception is a transient database error that may be retried."""
    s = str(exc or "").lower()
    transient_markers = [
        "timeout",
        "timed out",
        "temporarily unavailable",
        "connection refused",
        "connection reset",
        "connection error",
        "network",
        "dns",
        "name or service not known",
        "failed to establish a new connection",
        "server disconnected",
        "502",
        "503",
        "504",
        "bad gateway",
        "gateway timeout",
        "service unavailable",
    ]
    return any(m in s for m in transient_markers)


def is_missing_table_or_schema_error(exc: Exception, table_name: str) -> bool:
    """Check if an exception indicates a missing table or schema."""
    s = str(exc or "").lower()
    t = (table_name or "").lower()
    if not t:
        return False
    markers = [
        "does not exist",
        "undefined table",
        "could not find the table",
        "relation",
        "pgrst",
        "not found",
    ]
    return t in s and any(m in s for m in markers)


def is_supabase_not_configured_error(exc: Exception) -> bool:
    """Check if an exception indicates Supabase is not configured."""
    s = str(exc or "").lower()
    return "supabase não configurado" in s or "supabase nao configurado" in s


# ==================== RETRY LOGIC ====================
def db_call_with_retry(op_name: str, fn: Callable[[], Any], max_attempts: int = 4) -> Any:
    """
    Execute a database call with retry logic for transient errors.
    
    Args:
        op_name: Name of the operation (for logging)
        fn: Function to execute
        max_attempts: Maximum number of retry attempts
        
    Returns:
        Result of the function call
        
    Raises:
        Exception: If all attempts fail or a non-transient error occurs
    """
    import asyncio
    
    try:
        asyncio.get_running_loop()
        in_event_loop = True
    except RuntimeError:
        in_event_loop = False

    if in_event_loop:
        max_attempts = 1

    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if attempt >= max_attempts or not is_transient_db_error(e):
                raise
            sleep_s = min(2.0, 0.15 * (2 ** (attempt - 1)))
            logger.warning(f"{op_name} falhou (tentativa {attempt}/{max_attempts}): {e}")
            time.sleep(sleep_s)
    raise last_exc or Exception(f"{op_name} falhou")


# ==================== WRITE QUEUE ====================
def queue_db_write(operation: dict) -> None:
    """Queue a database write operation for later processing."""
    try:
        _DB_WRITE_QUEUE.append({
            **(operation or {}),
            "queued_at": datetime.utcnow().isoformat()
        })
    except Exception:
        return


def get_write_queue() -> "deque[dict]":
    """Get the database write queue."""
    return _DB_WRITE_QUEUE


# ==================== CACHE HELPERS ====================
def get_contacts_cache_by_tenant() -> Dict[str, dict]:
    """Get the contacts cache dictionary."""
    return _CONTACTS_CACHE_BY_TENANT


def get_contact_cache_by_id() -> Dict[str, dict]:
    """Get the contact by ID cache dictionary."""
    return _CONTACT_CACHE_BY_ID


def get_contact_cache_by_tenant_phone() -> Dict[str, dict]:
    """Get the contact by tenant+phone cache dictionary."""
    return _CONTACT_CACHE_BY_TENANT_PHONE


def get_tenant_user_names_cache() -> Dict[str, Set[str]]:
    """Get the tenant user names cache dictionary."""
    return _TENANT_USER_NAMES_CACHE


def cache_contact_row(contact_row: dict) -> None:
    """Cache a contact row in all relevant caches."""
    if not contact_row:
        return
    contact_id = contact_row.get("id")
    tenant_id = contact_row.get("tenant_id")
    phone = contact_row.get("phone")
    
    if contact_id:
        _CONTACT_CACHE_BY_ID[str(contact_id)] = contact_row
    if tenant_id and phone:
        cache_key = f"{tenant_id}:{phone}"
        _CONTACT_CACHE_BY_TENANT_PHONE[cache_key] = contact_row


# Backwards compatibility aliases (prefixed with underscore)
_is_transient_db_error = is_transient_db_error
_is_missing_table_or_schema_error = is_missing_table_or_schema_error
_is_supabase_not_configured_error = is_supabase_not_configured_error
_db_call_with_retry = db_call_with_retry
_queue_db_write = queue_db_write
_cache_contact_row = cache_contact_row
