"""
Webhooks routes extracted from server.py.

This module contains all custom webhook endpoints:
- GET /webhooks - List webhooks
- POST /webhooks - Create webhook
- PUT /webhooks/{id} - Update
- DELETE /webhooks/{id} - Delete
- PATCH /webhooks/{id}/toggle - Toggle active status
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

try:
    from ..supabase_client import supabase
    from ..models import WebhookCreate
    from ..utils.auth_helpers import verify_token
except ImportError:
    from supabase_client import supabase
    from models import WebhookCreate
    from utils.auth_helpers import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


def _format_webhook(w: dict) -> dict:
    """Format webhook for API response."""
    return {
        'id': w['id'],
        'name': w['name'],
        'url': w['url'],
        'events': w.get('events', []),
        'isActive': w['is_active'],
        'lastTriggeredAt': w.get('last_triggered_at'),
        'lastStatus': w.get('last_status'),
        'failureCount': w.get('failure_count', 0),
        'createdAt': w['created_at']
    }


@router.get("")
async def get_webhooks(tenant_id: str, payload: dict = Depends(verify_token)):
    """Get all webhooks for tenant."""
    try:
        result = supabase.table('custom_webhooks').select('*').eq('tenant_id', tenant_id).order('created_at').execute()
        return [_format_webhook(w) for w in (result.data or [])]
    except Exception as e:
        logger.error(f"Error getting webhooks: {e}")
        return []


@router.post("")
async def create_webhook(tenant_id: str, data: WebhookCreate, payload: dict = Depends(verify_token)):
    """Create a new webhook."""
    try:
        webhook_data = {
            'tenant_id': tenant_id,
            'name': data.name,
            'url': data.url,
            'secret': data.secret,
            'events': data.events,
            'headers': data.headers or {},
            'is_active': data.is_active
        }
        result = supabase.table('custom_webhooks').insert(webhook_data).execute()
        
        if result.data:
            return {'id': result.data[0]['id'], 'name': data.name}
        raise HTTPException(status_code=400, detail="Erro ao criar webhook")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{webhook_id}")
async def update_webhook(webhook_id: str, data: WebhookCreate, payload: dict = Depends(verify_token)):
    """Update a webhook."""
    try:
        update_data = {
            'name': data.name,
            'url': data.url,
            'secret': data.secret,
            'events': data.events,
            'headers': data.headers or {},
            'is_active': data.is_active,
            'updated_at': datetime.utcnow().isoformat()
        }
        supabase.table('custom_webhooks').update(update_data).eq('id', webhook_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{webhook_id}")
async def delete_webhook(webhook_id: str, payload: dict = Depends(verify_token)):
    """Delete a webhook."""
    try:
        supabase.table('custom_webhooks').delete().eq('id', webhook_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{webhook_id}/toggle")
async def toggle_webhook(webhook_id: str, payload: dict = Depends(verify_token)):
    """Toggle webhook active status."""
    try:
        wh = supabase.table('custom_webhooks').select('is_active').eq('id', webhook_id).execute()
        if not wh.data:
            raise HTTPException(status_code=404, detail="Webhook não encontrado")
        
        new_status = not wh.data[0]['is_active']
        supabase.table('custom_webhooks').update({'is_active': new_status}).eq('id', webhook_id).execute()
        
        return {"success": True, "isActive": new_status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
