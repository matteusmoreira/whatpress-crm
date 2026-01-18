"""
Authentication routes extracted from server.py.

This module contains all authentication-related endpoints:
- POST /auth/login - User login
- POST /auth/logout - User logout
- POST /auth/register - Tenant registration
- GET /auth/me - Get current user
- PATCH /auth/me - Update current user profile
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response

try:
    from ..supabase_client import supabase
    from ..models import LoginRequest, LoginResponse, TenantRegister, UserProfileUpdate
    from ..utils.auth_helpers import (
        JWT_SECRET,
        create_token,
        verify_token,
        verify_password_and_maybe_upgrade,
        normalize_email,
        hash_password,
        security,
    )
    from ..utils.db_helpers import (
        is_transient_db_error,
        is_missing_table_or_schema_error,
        is_supabase_not_configured_error,
    )
except ImportError:
    from supabase_client import supabase
    from models import LoginRequest, LoginResponse, TenantRegister, UserProfileUpdate
    from utils.auth_helpers import (
        JWT_SECRET,
        create_token,
        verify_token,
        verify_password_and_maybe_upgrade,
        normalize_email,
        hash_password,
        security,
    )
    from utils.db_helpers import (
        is_transient_db_error,
        is_missing_table_or_schema_error,
        is_supabase_not_configured_error,
    )

logger = logging.getLogger(__name__)

# Create router with /auth prefix
router = APIRouter(prefix="/auth", tags=["Authentication"])


def _get_maintenance_settings() -> dict:
    """Get maintenance settings - imported lazily to avoid circular imports."""
    # This will be passed from server.py or reimplemented here
    return {}


def set_maintenance_settings_getter(getter):
    """Set the maintenance settings getter function."""
    global _get_maintenance_settings
    _get_maintenance_settings = getter


# ==================== LOGIN ====================
@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, response: Response, http_request: Request):
    """Login with email and password."""
    email = normalize_email(request.email)
    password = str(request.password or "").strip()
    logger.info(f"Login attempt for: {email}")

    def _query_user():
        return (
            supabase.table("users")
            .select("*")
            .eq("email", email)
            .execute()
        )

    try:
        result = await asyncio.to_thread(_query_user)
    except Exception as e:
        logger.exception("Login failed (database error)")
        if is_supabase_not_configured_error(e):
            raise HTTPException(status_code=500, detail="Supabase não configurado no backend.")
        if is_missing_table_or_schema_error(e, "users"):
            raise HTTPException(status_code=503, detail="Banco de dados sem tabela de usuários.")
        if is_transient_db_error(e):
            raise HTTPException(status_code=503, detail="Banco de dados indisponível.")
        raise HTTPException(status_code=503, detail="Serviço de autenticação indisponível.")

    data = getattr(result, "data", None)
    if not data:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    user = data[0]
    ok, upgraded_hash = verify_password_and_maybe_upgrade(password, user.get("password_hash"))
    if not ok:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    if upgraded_hash:
        def _upgrade_password_hash():
            try:
                supabase.table("users").update({"password_hash": upgraded_hash}).eq("id", user["id"]).execute()
            except Exception:
                return
        await asyncio.to_thread(_upgrade_password_hash)

    token = create_token(user["id"], user["email"], user["role"], user.get("tenant_id"))

    proto = (http_request.headers.get("x-forwarded-proto") or http_request.url.scheme or "http").strip().lower()
    is_secure = proto == "https"
    cookie_samesite = "none" if is_secure else "lax"
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=is_secure,
        samesite=cookie_samesite,
        max_age=86400 * 7,
        path="/",
    )

    user_response = {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "tenantId": user.get("tenant_id"),
        "avatar": user.get("avatar"),
        "jobTitle": user.get("job_title"),
        "department": user.get("department"),
        "signatureEnabled": user.get("signature_enabled", True),
        "signatureIncludeTitle": user.get("signature_include_title", False),
        "signatureIncludeDepartment": user.get("signature_include_department", False),
        "createdAt": user.get("created_at"),
    }

    maintenance = None
    try:
        if str(user.get("role") or "").strip().lower() != "superadmin":
            settings = _get_maintenance_settings()
            if settings.get("enabled"):
                maintenance = settings
    except Exception:
        maintenance = None

    return {"user": user_response, "token": token, "maintenance": maintenance}


# ==================== LOGOUT ====================
@router.post("/logout")
async def logout(response: Response):
    """Logout and clear session cookie."""
    response.delete_cookie(key="access_token", path="/")
    return {"success": True}


# ==================== REGISTER ====================
@router.post("/register")
async def register_tenant(data: TenantRegister):
    """Register a new tenant with admin user."""
    # Check if slug already exists
    existing = supabase.table('tenants').select('id').eq('slug', data.tenant_slug).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Slug já está em uso")
    
    # Check if email already exists
    existing_email = supabase.table('users').select('id').eq('email', data.admin_email).execute()
    if existing_email.data:
        raise HTTPException(status_code=400, detail="Email já está em uso")
    
    # Create tenant
    tenant_data = {
        'name': data.tenant_name,
        'slug': data.tenant_slug,
        'status': 'active',
        'plan': data.plan,
        'messages_this_month': 0,
        'connections_count': 0
    }
    tenant_result = supabase.table('tenants').insert(tenant_data).execute()
    tenant = tenant_result.data[0]
    
    # Create admin user
    user_data = {
        'email': data.admin_email,
        'password_hash': hash_password(str(data.admin_password or "")),
        'name': data.admin_name,
        'role': 'admin',
        'tenant_id': tenant['id'],
        'avatar': f"https://api.dicebear.com/7.x/avataaars/svg?seed={data.admin_email}"
    }
    user_result = supabase.table('users').insert(user_data).execute()
    user = user_result.data[0]
    
    # Generate token
    token = create_token(user['id'], user['email'], user['role'], user.get('tenant_id'))
    
    return {
        "tenant": {
            'id': tenant['id'],
            'name': tenant['name'],
            'slug': tenant['slug'],
            'plan': tenant['plan']
        },
        "user": {
            'id': user['id'],
            'email': user['email'],
            'name': user['name'],
            'role': user['role'],
            'tenantId': user['tenant_id'],
            'avatar': user['avatar']
        },
        "token": token
    }


# ==================== GET CURRENT USER ====================
@router.get("/me")
async def get_current_user(payload: dict = Depends(verify_token)):
    """Get current authenticated user."""
    try:
        result = supabase.table('users').select('*').eq('id', payload['user_id']).execute()
    except Exception as e:
        if is_supabase_not_configured_error(e):
            raise HTTPException(status_code=500, detail="Supabase não configurado no backend.")
        if is_missing_table_or_schema_error(e, "users"):
            raise HTTPException(status_code=503, detail="Banco de dados sem tabela de usuários.")
        if is_transient_db_error(e):
            raise HTTPException(status_code=503, detail="Banco de dados indisponível.")
        raise HTTPException(status_code=500, detail="Erro ao carregar usuário.")
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    user = result.data[0]
    return {
        'id': user['id'],
        'email': user['email'],
        'name': user['name'],
        'role': user['role'],
        'tenantId': user['tenant_id'],
        'avatar': user['avatar'],
        'phone': user.get('phone'),
        'bio': user.get('bio'),
        'jobTitle': user.get('job_title'),
        'department': user.get('department'),
        'signatureEnabled': user.get('signature_enabled', True),
        'signatureIncludeTitle': user.get('signature_include_title', False),
        'signatureIncludeDepartment': user.get('signature_include_department', False),
        'createdAt': user.get('created_at'),
    }


# ==================== UPDATE CURRENT USER ====================
@router.patch("/me")
async def update_current_user_profile(data: UserProfileUpdate, payload: dict = Depends(verify_token)):
    """Update current user profile."""
    user_id = payload['user_id']
    update_data: Dict[str, Any] = {}
    
    if data.name is not None:
        update_data['name'] = (data.name or '').strip()
    if data.email is not None:
        email = (str(data.email) or '').strip().lower()
        if not email:
            raise HTTPException(status_code=400, detail="Email é obrigatório")
        existing = supabase.table('users').select('id').eq('email', email).neq('id', user_id).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail="Email já está em uso")
        update_data['email'] = email
    if data.phone is not None:
        phone = (data.phone or '').strip()
        update_data['phone'] = phone or None
    if data.avatar is not None:
        avatar = (data.avatar or '').strip()
        update_data['avatar'] = avatar or None
    if data.bio is not None:
        bio = (data.bio or '').strip()
        update_data['bio'] = bio or None
    if data.job_title is not None:
        update_data['job_title'] = (data.job_title or '').strip()
    if data.department is not None:
        update_data['department'] = (data.department or '').strip()
    if data.signature_enabled is not None:
        update_data['signature_enabled'] = data.signature_enabled
    if data.signature_include_title is not None:
        update_data['signature_include_title'] = data.signature_include_title
    if data.signature_include_department is not None:
        update_data['signature_include_department'] = data.signature_include_department

    def _format_user_response(u: dict) -> dict:
        return {
            'id': u['id'],
            'email': u['email'],
            'name': u['name'],
            'role': u['role'],
            'tenantId': u['tenant_id'],
            'avatar': u['avatar'],
            'phone': u.get('phone'),
            'bio': u.get('bio'),
            'jobTitle': u.get('job_title'),
            'department': u.get('department'),
            'signatureEnabled': u.get('signature_enabled', True),
            'signatureIncludeTitle': u.get('signature_include_title', False),
            'signatureIncludeDepartment': u.get('signature_include_department', False),
            'createdAt': u.get('created_at'),
        }

    if not update_data:
        result = supabase.table('users').select('*').eq('id', user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        return _format_user_response(result.data[0])

    try:
        result = supabase.table('users').update(update_data).eq('id', user_id).execute()
    except Exception as e:
        msg = str(e) or ""
        lowered = msg.lower()
        if "column" in lowered or "does not exist" in lowered:
            raise HTTPException(
                status_code=400,
                detail="Banco de dados sem colunas de perfil. Aplique a migração 009_contacts_transfer_signature_audit.sql.",
            )
        raise HTTPException(status_code=400, detail="Erro ao salvar perfil.")
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    return _format_user_response(result.data[0])
