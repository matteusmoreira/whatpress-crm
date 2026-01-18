"""
Templates routes extracted from server.py.

This module contains all message template endpoints:
- GET /templates - List templates
- POST /templates - Create template
- PUT /templates/{id} - Update
- DELETE /templates/{id} - Delete
- POST /templates/{id}/use - Increment usage count
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

try:
    from ..supabase_client import supabase
    from ..models import MessageTemplateCreate
    from ..utils.auth_helpers import verify_token
except ImportError:
    from supabase_client import supabase
    from models import MessageTemplateCreate
    from utils.auth_helpers import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/templates", tags=["Templates"])


def _format_template(t: dict) -> dict:
    """Format template for API response."""
    return {
        'id': t['id'],
        'name': t['name'],
        'category': t['category'],
        'content': t['content'],
        'variables': t.get('variables', []),
        'mediaUrl': t.get('media_url'),
        'mediaType': t.get('media_type'),
        'usageCount': t.get('usage_count', 0),
        'isActive': t['is_active'],
        'createdAt': t['created_at']
    }


@router.get("")
async def get_templates(
    tenant_id: str,
    category: Optional[str] = None,
    payload: dict = Depends(verify_token)
):
    """Get all message templates for tenant."""
    try:
        query = supabase.table('message_templates').select('*').eq('tenant_id', tenant_id)
        if category:
            query = query.eq('category', category)
        result = query.order('usage_count', desc=True).execute()
        
        return [_format_template(t) for t in (result.data or [])]
    except Exception as e:
        logger.error(f"Error getting templates: {e}")
        return []


@router.post("")
async def create_template(tenant_id: str, data: MessageTemplateCreate, payload: dict = Depends(verify_token)):
    """Create a new message template."""
    try:
        template_data = {
            'tenant_id': tenant_id,
            'name': data.name,
            'category': data.category,
            'content': data.content,
            'variables': data.variables or [],
            'media_url': data.media_url,
            'media_type': data.media_type,
            'is_active': data.is_active
        }
        result = supabase.table('message_templates').insert(template_data).execute()
        
        if result.data:
            return {'id': result.data[0]['id'], 'name': data.name}
        raise HTTPException(status_code=400, detail="Erro ao criar template")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{template_id}")
async def update_template(template_id: str, data: MessageTemplateCreate, payload: dict = Depends(verify_token)):
    """Update a message template."""
    try:
        update_data = {
            'name': data.name,
            'category': data.category,
            'content': data.content,
            'variables': data.variables or [],
            'media_url': data.media_url,
            'media_type': data.media_type,
            'is_active': data.is_active,
            'updated_at': datetime.utcnow().isoformat()
        }
        supabase.table('message_templates').update(update_data).eq('id', template_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{template_id}")
async def delete_template(template_id: str, payload: dict = Depends(verify_token)):
    """Delete a message template."""
    try:
        supabase.table('message_templates').delete().eq('id', template_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{template_id}/use")
async def use_template(template_id: str, payload: dict = Depends(verify_token)):
    """Increment template usage count and return content."""
    try:
        template = supabase.table('message_templates').select('*').eq('id', template_id).execute()
        if not template.data:
            raise HTTPException(status_code=404, detail="Template não encontrado")
        
        t = template.data[0]
        new_count = (t.get('usage_count') or 0) + 1
        supabase.table('message_templates').update({'usage_count': new_count}).eq('id', template_id).execute()
        
        return _format_template({**t, 'usage_count': new_count})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
