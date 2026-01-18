"""
Authentication helper utilities extracted from server.py.

These functions handle JWT token creation/verification, password hashing,
and user authentication logic.
"""

import os
import hmac
import logging
from datetime import datetime
from typing import Any, Optional, Tuple, TYPE_CHECKING

import jwt
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

if TYPE_CHECKING:
    class CryptContext:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            ...

        def hash(self, secret: str) -> str:
            ...

        def verify(self, secret: str, hash: str) -> bool:
            ...

        def needs_update(self, hash: str) -> bool:
            ...
else:
    from passlib.context import CryptContext

from .db_helpers import db_call_with_retry, is_missing_table_or_schema_error

logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================
JWT_SECRET = (
    os.getenv("JWT_SECRET")
    or os.getenv("APP_JWT_SECRET")
    or "whatsapp-crm-secret-key-2025"
).strip()

_PASSWORD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security bearer for FastAPI
security = HTTPBearer(auto_error=False)


# ==================== PASSWORD FUNCTIONS ====================
def looks_like_bcrypt_hash(value: str) -> bool:
    """Check if a string looks like a bcrypt hash."""
    s = (value or "").strip()
    return s.startswith("$2a$") or s.startswith("$2b$") or s.startswith("$2y$")


def verify_password_and_maybe_upgrade(plain_password: str, stored_hash: Any) -> Tuple[bool, Optional[str]]:
    """
    Verify a password and optionally upgrade the hash if needed.
    
    Args:
        plain_password: The plain text password to verify
        stored_hash: The stored password hash
        
    Returns:
        Tuple of (is_valid, upgraded_hash_if_needed)
    """
    plain = str(plain_password or "")
    stored = str(stored_hash or "")
    if not stored or not plain:
        return False, None

    if looks_like_bcrypt_hash(stored):
        try:
            ok = bool(_PASSWORD_CONTEXT.verify(plain, stored))
        except Exception:
            return False, None
        if ok and _PASSWORD_CONTEXT.needs_update(stored):
            try:
                return True, _PASSWORD_CONTEXT.hash(plain)
            except Exception:
                return True, None
        return ok, None

    # Plain text password comparison (migrate to bcrypt)
    if hmac.compare_digest(stored, plain):
        try:
            return True, _PASSWORD_CONTEXT.hash(plain)
        except Exception:
            return True, None

    return False, None


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return _PASSWORD_CONTEXT.hash(password)


# ==================== TOKEN FUNCTIONS ====================
def create_token(user_id: str, email: str, role: str, tenant_id: Optional[str] = None) -> str:
    """
    Create a JWT token for a user.
    
    Args:
        user_id: The user's ID
        email: The user's email
        role: The user's role
        tenant_id: Optional tenant ID
        
    Returns:
        JWT token string
    """
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "exp": datetime.utcnow().timestamp() + 86400 * 7  # 7 days
    }
    if tenant_id:
        payload["tenant_id"] = tenant_id
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_token(http_request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Verify a JWT token from the request.
    
    Args:
        http_request: The FastAPI Request object
        credentials: The HTTP bearer credentials
        
    Returns:
        The decoded token payload
        
    Raises:
        HTTPException: If token is missing, expired, or invalid
    """
    token = credentials.credentials if credentials else None
    if not token:
        token = http_request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Token não fornecido")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


def get_user_tenant_id(payload: dict, supabase) -> Optional[str]:
    """
    Get tenant ID from user payload or database.
    
    Args:
        payload: The decoded JWT payload
        supabase: The Supabase client
        
    Returns:
        The tenant ID or None for superadmin
        
    Raises:
        HTTPException: If database is unavailable
    """
    if payload['role'] == 'superadmin':
        return None
    token_tenant_id = payload.get("tenant_id")
    if token_tenant_id:
        return token_tenant_id
    try:
        user = db_call_with_retry(
            "auth.get_user_tenant_id",
            lambda: supabase.table('users').select('tenant_id').eq('id', payload['user_id']).execute(),
        )
    except Exception as e:
        if is_missing_table_or_schema_error(e, "users"):
            raise HTTPException(status_code=503, detail="Banco de dados sem tabela de usuários.")
        raise HTTPException(status_code=503, detail="Banco de dados indisponível.")
    if user.data:
        return user.data[0]['tenant_id']
    return None


# ==================== NORMALIZATION ====================
def normalize_email(value: Any) -> str:
    """Normalize an email address to lowercase."""
    return str(value or "").strip().lower()


# Backwards compatibility aliases (prefixed with underscore)
_looks_like_bcrypt_hash = looks_like_bcrypt_hash
_verify_password_and_maybe_upgrade = verify_password_and_maybe_upgrade
_normalize_email = normalize_email
