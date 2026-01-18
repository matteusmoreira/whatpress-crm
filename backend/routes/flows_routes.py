"""
Flows routes extracted from server.py.

This module contains all automation flow endpoints:
- GET /flows - List flows
- GET /flows/{id} - Get flow
- POST /flows - Create flow
- PUT /flows/{id} - Update flow
- DELETE /flows/{id} - Delete flow
- POST /flows/{id}/duplicate - Duplicate flow
- PATCH /flows/{id}/toggle - Toggle flow active status
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

try:
    from ..supabase_client import supabase
    from ..models import FlowCreate, FlowUpdate, FlowDuplicate
    from ..utils.auth_helpers import verify_token
except ImportError:
    from supabase_client import supabase
    from models import FlowCreate, FlowUpdate, FlowDuplicate
    from utils.auth_helpers import verify_token

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/flows", tags=["Flows"])


# ==================== HELPER FUNCTIONS ====================

def _get_user_tenant_id(payload: dict) -> Optional[str]:
    """Get tenant ID from user payload."""
    if payload.get('role') == 'superadmin':
        return payload.get('tenant_id')
    return payload.get('tenant_id')


def _format_flow_response(f: dict) -> dict:
    """Format flow for API response."""
    return {
        'id': f['id'],
        'tenantId': f['tenant_id'],
        'name': f['name'],
        'description': f.get('description'),
        'nodes': f.get('nodes', []),
        'edges': f.get('edges', []),
        'variables': f.get('variables', {}),
        'status': f['status'],
        'isActive': f['is_active'],
        'createdBy': f.get('created_by'),
        'createdAt': f['created_at'],
        'updatedAt': f['updated_at']
    }


# ==================== ROUTES ====================

@router.get("")
async def list_flows(
    tenant_id: Optional[str] = Query(None),
    status: Optional[str] = None,
    is_active: Optional[bool] = None,
    payload: dict = Depends(verify_token)
):
    """List all flows for a tenant."""
    user_tenant_id = _get_user_tenant_id(payload)
    effective_tenant_id = user_tenant_id
    
    if not effective_tenant_id and payload.get('role') == 'superadmin':
        effective_tenant_id = tenant_id
    
    if not effective_tenant_id:
        raise HTTPException(status_code=403, detail="Tenant não identificado")
    
    query = supabase.table('flows').select('*').eq('tenant_id', effective_tenant_id)
    
    if status:
        query = query.eq('status', status)
    if is_active is not None:
        query = query.eq('is_active', is_active)
    
    query = query.order('updated_at', desc=True)
    result = query.execute()
    
    return [_format_flow_response(f) for f in result.data]


@router.get("/{flow_id}")
async def get_flow(flow_id: str, payload: dict = Depends(verify_token)):
    """Get a specific flow by ID."""
    result = supabase.table('flows').select('*').eq('id', flow_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Fluxo não encontrado")
    
    f = result.data[0]
    user_tenant_id = _get_user_tenant_id(payload)
    
    if payload.get('role') != 'superadmin' and user_tenant_id and f['tenant_id'] != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    return _format_flow_response(f)


@router.post("")
async def create_flow(flow: FlowCreate, payload: dict = Depends(verify_token)):
    """Create a new flow."""
    user_tenant_id = _get_user_tenant_id(payload)
    
    if not user_tenant_id:
        raise HTTPException(status_code=403, detail="Tenant não identificado")
    
    data = {
        'tenant_id': user_tenant_id,
        'name': flow.name,
        'description': flow.description,
        'nodes': flow.nodes or [],
        'edges': flow.edges or [],
        'variables': flow.variables or {},
        'status': flow.status or 'draft',
        'is_active': False,
        'created_by': payload.get('user_id')
    }
    
    result = supabase.table('flows').insert(data).execute()
    
    if not result.data:
        raise HTTPException(status_code=400, detail="Erro ao criar fluxo")
    
    return _format_flow_response(result.data[0])


@router.put("/{flow_id}")
async def update_flow(flow_id: str, flow: FlowUpdate, payload: dict = Depends(verify_token)):
    """Update an existing flow."""
    # Check if flow exists and user has access
    existing = supabase.table('flows').select('id, tenant_id').eq('id', flow_id).execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Fluxo não encontrado")
    
    user_tenant_id = _get_user_tenant_id(payload)
    if payload.get('role') != 'superadmin' and user_tenant_id and existing.data[0]['tenant_id'] != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    data: Dict[str, Any] = {}
    if flow.name is not None:
        data['name'] = flow.name
    if flow.description is not None:
        data['description'] = flow.description
    if flow.nodes is not None:
        data['nodes'] = flow.nodes
    if flow.edges is not None:
        data['edges'] = flow.edges
    if flow.variables is not None:
        data['variables'] = flow.variables
    if flow.status is not None:
        data['status'] = flow.status
    if flow.is_active is not None:
        data['is_active'] = flow.is_active
    
    if not data:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")
    
    result = supabase.table('flows').update(data).eq('id', flow_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Fluxo não encontrado")
    
    return _format_flow_response(result.data[0])


@router.delete("/{flow_id}")
async def delete_flow(flow_id: str, payload: dict = Depends(verify_token)):
    """Delete a flow."""
    # Check if flow exists and user has access
    existing = supabase.table('flows').select('id, tenant_id').eq('id', flow_id).execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Fluxo não encontrado")
    
    user_tenant_id = _get_user_tenant_id(payload)
    if payload.get('role') != 'superadmin' and user_tenant_id and existing.data[0]['tenant_id'] != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    supabase.table('flows').delete().eq('id', flow_id).execute()
    return {"success": True, "message": "Fluxo deletado com sucesso"}


@router.post("/{flow_id}/duplicate")
async def duplicate_flow(flow_id: str, duplicate: FlowDuplicate, payload: dict = Depends(verify_token)):
    """Duplicate an existing flow."""
    # Get original flow
    result = supabase.table('flows').select('*').eq('id', flow_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Fluxo não encontrado")
    
    original = result.data[0]
    user_tenant_id = _get_user_tenant_id(payload)
    
    if payload.get('role') != 'superadmin' and user_tenant_id and original['tenant_id'] != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    # Create copy
    data = {
        'tenant_id': original['tenant_id'],
        'name': duplicate.name,
        'description': duplicate.description or original.get('description'),
        'nodes': original.get('nodes', []),
        'edges': original.get('edges', []),
        'variables': original.get('variables', {}),
        'status': 'draft',
        'is_active': False,
        'created_by': payload.get('user_id')
    }
    
    new_flow = supabase.table('flows').insert(data).execute()
    
    if not new_flow.data:
        raise HTTPException(status_code=400, detail="Erro ao duplicar fluxo")
    
    return _format_flow_response(new_flow.data[0])


@router.patch("/{flow_id}/toggle")
async def toggle_flow(flow_id: str, payload: dict = Depends(verify_token)):
    """Toggle flow active status."""
    # Check if flow exists
    existing = supabase.table('flows').select('id, tenant_id, is_active').eq('id', flow_id).execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Fluxo não encontrado")
    
    flow_data = existing.data[0]
    user_tenant_id = _get_user_tenant_id(payload)
    
    if payload.get('role') != 'superadmin' and user_tenant_id and flow_data['tenant_id'] != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    # Toggle state
    new_state = not flow_data['is_active']
    result = supabase.table('flows').update({'is_active': new_state}).eq('id', flow_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Fluxo não encontrado")
    
    f = result.data[0]
    return {
        'id': f['id'],
        'isActive': f['is_active'],
        'message': f"Fluxo {'ativado' if f['is_active'] else 'desativado'} com sucesso"
    }
