"""
Auto Messages routes extracted from server.py.

This module contains all auto message endpoints:
- GET /auto-messages - List auto messages
- POST /auto-messages - Create auto message
- PUT /auto-messages/{id} - Update
- DELETE /auto-messages/{id} - Delete
- PATCH /auto-messages/{id}/toggle - Toggle active status
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

try:
    from ..supabase_client import supabase
    from ..models import AutoMessageCreate
    from ..utils.auth_helpers import verify_token
except ImportError:
    from supabase_client import supabase
    from models import AutoMessageCreate
    from utils.auth_helpers import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auto-messages", tags=["Auto Messages"])


def _is_missing_table_error(exc: Exception, table_name: str) -> bool:
    """Check if exception indicates missing table."""
    s = str(exc or "").lower()
    return table_name.lower() in s and ("does not exist" in s or "not found" in s or "pgrst" in s)


def _auto_messages_missing_table_http():
    """Return HTTP exception for missing auto_messages table."""
    return HTTPException(
        status_code=503,
        detail="Tabela auto_messages não existe. Execute a migração."
    )


def _format_auto_message(m: dict) -> dict:
    """Format auto message for API response."""
    return {
        'id': m['id'],
        'type': m['type'],
        'name': m['name'],
        'message': m['message'],
        'triggerKeyword': m.get('trigger_keyword'),
        'isActive': m['is_active'],
        'scheduleStart': m.get('schedule_start'),
        'scheduleEnd': m.get('schedule_end'),
        'scheduleDays': m.get('schedule_days'),
        'delaySeconds': m.get('delay_seconds', 0),
        'createdAt': m['created_at']
    }


@router.get("")
async def get_auto_messages(tenant_id: str, payload: dict = Depends(verify_token)):
    """Get all auto messages for tenant."""
    try:
        result = supabase.table('auto_messages').select('*').eq('tenant_id', tenant_id).order('created_at').execute()
        return [_format_auto_message(m) for m in (result.data or [])]
    except Exception as e:
        if _is_missing_table_error(e, "auto_messages"):
            raise _auto_messages_missing_table_http()
        logger.error(f"Error getting auto messages: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("")
async def create_auto_message(tenant_id: str, data: AutoMessageCreate, payload: dict = Depends(verify_token)):
    """Create a new auto message."""
    try:
        msg_data = {
            'tenant_id': tenant_id,
            'type': data.type,
            'name': data.name,
            'message': data.message,
            'trigger_keyword': data.trigger_keyword,
            'is_active': data.is_active if data.is_active is not None else True,
            'schedule_start': data.schedule_start,
            'schedule_end': data.schedule_end,
            'schedule_days': data.schedule_days or [],
            'delay_seconds': data.delay_seconds or 0
        }
        result = supabase.table('auto_messages').insert(msg_data).execute()
        
        if not result.data:
            raise HTTPException(status_code=400, detail="Erro ao criar mensagem automática")
        
        return _format_auto_message(result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_table_error(e, "auto_messages"):
            raise _auto_messages_missing_table_http()
        logger.error(f"Error creating auto message: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{message_id}")
async def update_auto_message(message_id: str, data: AutoMessageCreate, payload: dict = Depends(verify_token)):
    """Update an existing auto message."""
    try:
        update_data: Dict[str, Any] = {
            'type': data.type,
            'name': data.name,
            'message': data.message,
            'trigger_keyword': data.trigger_keyword,
            'schedule_start': data.schedule_start,
            'schedule_end': data.schedule_end,
            'schedule_days': data.schedule_days,
            'delay_seconds': data.delay_seconds
        }
        if data.is_active is not None:
            update_data['is_active'] = data.is_active
        
        result = supabase.table('auto_messages').update(update_data).eq('id', message_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Mensagem não encontrada")
        
        return {"success": True, "id": message_id}
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_table_error(e, "auto_messages"):
            raise _auto_messages_missing_table_http()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{message_id}")
async def delete_auto_message(message_id: str, payload: dict = Depends(verify_token)):
    """Delete an auto message."""
    try:
        supabase.table('auto_messages').delete().eq('id', message_id).execute()
        return {"success": True}
    except Exception as e:
        if _is_missing_table_error(e, "auto_messages"):
            raise _auto_messages_missing_table_http()
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{message_id}/toggle")
async def toggle_auto_message(message_id: str, payload: dict = Depends(verify_token)):
    """Toggle auto message active status."""
    try:
        msg = supabase.table('auto_messages').select('is_active').eq('id', message_id).execute()
        if not msg.data:
            raise HTTPException(status_code=404, detail="Mensagem não encontrada")
        
        new_status = not msg.data[0]['is_active']
        supabase.table('auto_messages').update({'is_active': new_status}).eq('id', message_id).execute()
        
        return {"success": True, "isActive": new_status}
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_table_error(e, "auto_messages"):
            raise _auto_messages_missing_table_http()
        raise HTTPException(status_code=400, detail=str(e))
