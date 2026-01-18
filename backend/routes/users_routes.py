"""
Users routes extracted from server.py.

This module contains all user management endpoints:
- GET /users - List users
- GET /users/{id} - Get user
- POST /users - Create user
- PUT /users/{id} - Update user
- DELETE /users/{id} - Delete user
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

try:
    from ..supabase_client import supabase
    from ..models import UserCreate, UserUpdate
    from ..utils.auth_helpers import verify_token, hash_password
except ImportError:
    from supabase_client import supabase
    from models import UserCreate, UserUpdate
    from utils.auth_helpers import verify_token, hash_password


# Create router
router = APIRouter(prefix="/users", tags=["Users"])


def _get_user_tenant_id(payload: dict) -> Optional[str]:
    """Get tenant ID from user payload."""
    if payload.get('role') == 'superadmin':
        return None
    return payload.get('tenant_id')


def _format_user(u: dict) -> dict:
    """Format user for API response."""
    tenant = u.get('tenants', {}) if u.get('tenants') else {}
    return {
        'id': u['id'],
        'email': u['email'],
        'name': u['name'],
        'role': u['role'],
        'tenantId': u['tenant_id'],
        'tenantName': tenant.get('name') if tenant else None,
        'avatar': u['avatar'],
        'createdAt': u['created_at']
    }


# ==================== USERS ====================

@router.get("")
async def list_users(
    tenant_id: Optional[str] = None,
    role: Optional[str] = None,
    payload: dict = Depends(verify_token)
):
    """List all users (SuperAdmin) or users from a tenant."""
    if payload['role'] != 'superadmin':
        user_tenant = _get_user_tenant_id(payload)
        if not user_tenant:
            raise HTTPException(status_code=403, detail="Acesso negado")
        tenant_id = user_tenant
    
    query = supabase.table('users').select('*, tenants(name, slug)')
    
    if tenant_id:
        query = query.eq('tenant_id', tenant_id)
    if role:
        query = query.eq('role', role)
    
    result = query.order('created_at', desc=True).execute()
    return [_format_user(u) for u in result.data]


@router.get("/{user_id}")
async def get_user(user_id: str, payload: dict = Depends(verify_token)):
    """Get a single user by ID."""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    result = supabase.table('users').select('*, tenants(name, slug)').eq('id', user_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    return _format_user(result.data[0])


@router.post("")
async def create_user(user: UserCreate, payload: dict = Depends(verify_token)):
    """Create a new user (SuperAdmin only)."""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    # Check if email already exists
    existing = supabase.table('users').select('id').eq('email', user.email).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Email já está em uso")
    
    data = {
        'email': user.email,
        'password_hash': hash_password(user.password) if user.password else user.password,
        'name': user.name,
        'role': user.role,
        'tenant_id': user.tenant_id,
        'avatar': user.avatar or f"https://api.dicebear.com/7.x/avataaars/svg?seed={user.email}"
    }
    
    result = supabase.table('users').insert(data).execute()
    
    if not result.data:
        raise HTTPException(status_code=400, detail="Erro ao criar usuário")
    
    return _format_user(result.data[0])


@router.put("/{user_id}")
async def update_user(user_id: str, user: UserUpdate, payload: dict = Depends(verify_token)):
    """Update a user (SuperAdmin only)."""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    data = {}
    if user.email is not None:
        existing = supabase.table('users').select('id').eq('email', user.email).neq('id', user_id).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail="Email já está em uso")
        data['email'] = user.email
    if user.password is not None:
        data['password_hash'] = hash_password(user.password)
    if user.name is not None:
        data['name'] = user.name
    if user.role is not None:
        data['role'] = user.role
    if user.tenant_id is not None:
        data['tenant_id'] = user.tenant_id if user.tenant_id != '' else None
    if user.avatar is not None:
        data['avatar'] = user.avatar
    
    result = supabase.table('users').update(data).eq('id', user_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    return _format_user(result.data[0])


@router.delete("/{user_id}")
async def delete_user(user_id: str, payload: dict = Depends(verify_token)):
    """Delete a user (SuperAdmin only)."""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    # Prevent deleting yourself
    if user_id == payload['user_id']:
        raise HTTPException(status_code=400, detail="Você não pode excluir seu próprio usuário")
    
    supabase.table('users').delete().eq('id', user_id).execute()
    return {"success": True}
