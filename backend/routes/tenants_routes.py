"""
Tenants and Plans routes extracted from server.py.

This module contains all tenant and plan management endpoints:
- GET/POST /tenants - List/Create tenants
- GET/PUT/DELETE /tenants/{id} - CRUD operations
- GET /tenants/stats - Tenant statistics
- GET/POST /plans - List/Create plans
- GET/PUT/DELETE /plans/{id} - CRUD operations
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

try:
    from ..supabase_client import supabase
    from ..models import TenantCreate, TenantUpdate, PlanCreate, PlanUpdate
    from ..utils.auth_helpers import verify_token
except ImportError:
    from supabase_client import supabase
    from models import TenantCreate, TenantUpdate, PlanCreate, PlanUpdate
    from utils.auth_helpers import verify_token


# Create router
router = APIRouter(tags=["Tenants & Plans"])


def _get_user_tenant_id(payload: dict) -> Optional[str]:
    """Get tenant ID from user payload."""
    if payload.get('role') == 'superadmin':
        return None
    return payload.get('tenant_id')


def _format_tenant(t: dict) -> dict:
    """Format tenant for API response."""
    return {
        'id': t['id'],
        'name': t['name'],
        'slug': t['slug'],
        'status': t['status'],
        'plan': t['plan'],
        'planId': t.get('plan_id'),
        'planData': t.get('plans'),
        'messagesThisMonth': t['messages_this_month'],
        'connectionsCount': t['connections_count'],
        'createdAt': t['created_at'],
        'updatedAt': t.get('updated_at')
    }


def _format_plan(p: dict) -> dict:
    """Format plan for API response."""
    return {
        'id': p['id'],
        'name': p['name'],
        'slug': p['slug'],
        'price': float(p['price']) if p.get('price') else 0,
        'maxInstances': p['max_instances'],
        'maxMessagesMonth': p['max_messages_month'],
        'maxUsers': p['max_users'],
        'features': p['features'],
        'isActive': p['is_active'],
        'createdAt': p['created_at']
    }


# ==================== TENANTS ====================

@router.get("/tenants")
async def list_tenants(payload: dict = Depends(verify_token)):
    """List all tenants (superadmin only)."""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    result = supabase.table('tenants').select('*').order('created_at', desc=True).execute()
    return [_format_tenant(t) for t in result.data]


@router.get("/tenants/stats")
async def get_tenants_stats(payload: dict = Depends(verify_token)):
    """Get tenants statistics."""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    tenants = supabase.table('tenants').select('*').execute()
    connections = supabase.table('connections').select('*').eq('status', 'connected').execute()
    
    total_tenants = len(tenants.data)
    active_tenants = len([t for t in tenants.data if t['status'] == 'active'])
    total_messages = sum(t['messages_this_month'] for t in tenants.data)
    total_connections = len(connections.data)
    
    return {
        'totalTenants': total_tenants,
        'activeTenants': active_tenants,
        'totalMessages': total_messages,
        'totalConnections': total_connections,
        'messagesPerDay': total_messages // 30 if total_messages else 0
    }


@router.post("/tenants")
async def create_tenant(tenant: TenantCreate, payload: dict = Depends(verify_token)):
    """Create a new tenant."""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    data = {
        'name': tenant.name,
        'slug': tenant.slug,
        'status': 'active',
        'plan': 'free',
        'messages_this_month': 0,
        'connections_count': 0
    }
    
    if tenant.plan_id:
        data['plan_id'] = tenant.plan_id
        plan = supabase.table('plans').select('slug').eq('id', tenant.plan_id).execute()
        if plan.data:
            data['plan'] = plan.data[0]['slug']
    
    result = supabase.table('tenants').insert(data).execute()
    
    if not result.data:
        raise HTTPException(status_code=400, detail="Erro ao criar tenant")
    
    return _format_tenant(result.data[0])


@router.get("/tenants/{tenant_id}")
async def get_tenant(tenant_id: str, payload: dict = Depends(verify_token)):
    """Get a single tenant by ID."""
    if payload['role'] != 'superadmin':
        user_tenant_id = _get_user_tenant_id(payload)
        if not user_tenant_id or str(user_tenant_id) != str(tenant_id):
            raise HTTPException(status_code=403, detail="Acesso negado")
    
    result = supabase.table('tenants').select('*, plans(*)').eq('id', tenant_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    
    return _format_tenant(result.data[0])


@router.put("/tenants/{tenant_id}")
async def update_tenant(tenant_id: str, tenant: TenantUpdate, payload: dict = Depends(verify_token)):
    """Update a tenant."""
    if payload['role'] != 'superadmin':
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Acesso negado")
        user_tenant_id = _get_user_tenant_id(payload)
        if not user_tenant_id or str(user_tenant_id) != str(tenant_id):
            raise HTTPException(status_code=403, detail="Acesso negado")
    
    data = {k: v for k, v in tenant.dict().items() if v is not None}
    data['updated_at'] = datetime.utcnow().isoformat()
    
    if 'plan_id' in data and data['plan_id']:
        plan = supabase.table('plans').select('slug').eq('id', data['plan_id']).execute()
        if plan.data:
            data['plan'] = plan.data[0]['slug']
    
    result = supabase.table('tenants').update(data).eq('id', tenant_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    
    return _format_tenant(result.data[0])


@router.delete("/tenants/{tenant_id}")
async def delete_tenant(tenant_id: str, payload: dict = Depends(verify_token)):
    """Delete a tenant."""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    supabase.table('tenants').delete().eq('id', tenant_id).execute()
    return {"success": True}


# ==================== PLANS ====================

@router.get("/plans")
async def list_plans(payload: dict = Depends(verify_token)):
    """List all plans."""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    result = supabase.table('plans').select('*').order('price', desc=False).execute()
    return [_format_plan(p) for p in result.data]


@router.get("/plans/{plan_id}")
async def get_plan(plan_id: str, payload: dict = Depends(verify_token)):
    """Get a single plan by ID."""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    result = supabase.table('plans').select('*').eq('id', plan_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    
    return _format_plan(result.data[0])


@router.post("/plans")
async def create_plan(plan: PlanCreate, payload: dict = Depends(verify_token)):
    """Create a new plan."""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    data = {
        'name': plan.name,
        'slug': plan.slug,
        'price': plan.price,
        'max_instances': plan.max_instances,
        'max_messages_month': plan.max_messages_month,
        'max_users': plan.max_users,
        'features': plan.features or {},
        'is_active': plan.is_active
    }
    
    result = supabase.table('plans').insert(data).execute()
    
    if not result.data:
        raise HTTPException(status_code=400, detail="Erro ao criar plano")
    
    return _format_plan(result.data[0])


@router.put("/plans/{plan_id}")
async def update_plan(plan_id: str, plan: PlanUpdate, payload: dict = Depends(verify_token)):
    """Update a plan."""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    data = {}
    if plan.name is not None:
        data['name'] = plan.name
    if plan.slug is not None:
        data['slug'] = plan.slug
    if plan.price is not None:
        data['price'] = plan.price
    if plan.max_instances is not None:
        data['max_instances'] = plan.max_instances
    if plan.max_messages_month is not None:
        data['max_messages_month'] = plan.max_messages_month
    if plan.max_users is not None:
        data['max_users'] = plan.max_users
    if plan.features is not None:
        data['features'] = plan.features
    if plan.is_active is not None:
        data['is_active'] = plan.is_active
    
    data['updated_at'] = datetime.utcnow().isoformat()
    
    result = supabase.table('plans').update(data).eq('id', plan_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    
    return _format_plan(result.data[0])


@router.delete("/plans/{plan_id}")
async def delete_plan(plan_id: str, payload: dict = Depends(verify_token)):
    """Delete a plan."""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    # Check if any tenant is using this plan
    tenants = supabase.table('tenants').select('id').eq('plan_id', plan_id).execute()
    if tenants.data:
        raise HTTPException(status_code=400, detail="Não é possível excluir plano em uso por tenants")
    
    supabase.table('plans').delete().eq('id', plan_id).execute()
    return {"success": True}
