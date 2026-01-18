"""
Quick Replies routes extracted from server.py.

This module contains all quick reply endpoints:
- GET /quick-replies - List quick replies
- POST /quick-replies - Create quick reply
- PUT /quick-replies/{id} - Update
- DELETE /quick-replies/{id} - Delete
"""

import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

try:
    from ..supabase_client import supabase
    from ..models import QuickReplyCreate
    from ..utils.auth_helpers import verify_token
    from ..features import QuickRepliesService
except ImportError:
    from supabase_client import supabase
    from models import QuickReplyCreate
    from utils.auth_helpers import verify_token
    from features import QuickRepliesService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quick-replies", tags=["Quick Replies"])


@router.get("")
async def get_quick_replies(tenant_id: str, payload: dict = Depends(verify_token)):
    """Get quick replies for tenant."""
    replies = await QuickRepliesService.get_quick_replies(tenant_id)
    return replies


@router.post("")
async def create_quick_reply(tenant_id: str, data: QuickReplyCreate, payload: dict = Depends(verify_token)):
    """Create quick reply."""
    reply = await QuickRepliesService.create_quick_reply(tenant_id, data.title, data.content, data.category)
    return reply or {"id": str(uuid.uuid4()), **data.dict()}


@router.put("/{reply_id}")
async def update_quick_reply(reply_id: str, data: QuickReplyCreate, payload: dict = Depends(verify_token)):
    """Update an existing quick reply."""
    try:
        update_data = {
            'title': data.title,
            'content': data.content,
            'category': data.category
        }
        result = supabase.table('quick_replies').update(update_data).eq('id', reply_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Resposta rápida não encontrada")
        
        reply = result.data[0]
        return {
            'id': reply['id'],
            'title': reply['title'],
            'content': reply['content'],
            'category': reply['category']
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{reply_id}")
async def delete_quick_reply(reply_id: str, payload: dict = Depends(verify_token)):
    """Delete quick reply."""
    await QuickRepliesService.delete_quick_reply(reply_id)
    return {"success": True}
