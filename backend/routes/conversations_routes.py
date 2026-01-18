"""
Conversations routes extracted from server.py.

This module contains all conversation management endpoints:
- GET /conversations - List conversations
- PATCH /conversations/{id}/status - Update status
- POST /conversations/initiate - Start new conversation
- POST /conversations/{id}/read - Mark as read
- POST /conversations/{id}/assign - Assign to agent
- POST /conversations/{id}/unassign - Unassign
- POST /conversations/{id}/transfer - Transfer
- POST/DELETE /conversations/{id}/labels/{id} - Manage labels
- DELETE /conversations/{id} - Delete
- DELETE /conversations/purge - Purge all
"""

import re
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

try:
    from ..supabase_client import supabase
    from ..models import (
        ConversationStatusUpdate,
        InitiateConversation,
        ConversationTransferCreate,
        AssignAgent,
    )
    from ..utils.auth_helpers import verify_token
    from ..utils.db_helpers import (
        db_call_with_retry,
        is_transient_db_error,
        is_supabase_not_configured_error,
        is_missing_table_or_schema_error,
    )
except ImportError:
    from supabase_client import supabase
    from models import (
        ConversationStatusUpdate,
        InitiateConversation,
        ConversationTransferCreate,
        AssignAgent,
    )
    from utils.auth_helpers import verify_token
    from utils.db_helpers import (
        db_call_with_retry,
        is_transient_db_error,
        is_supabase_not_configured_error,
        is_missing_table_or_schema_error,
    )

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["Conversations"])


def _get_user_tenant_id(payload: dict) -> Optional[str]:
    """Get tenant ID from user payload."""
    if payload.get('role') == 'superadmin':
        return None
    return payload.get('tenant_id')


def _require_conversation_access(conversation_id: str, payload: dict) -> dict:
    """Verify user has access to conversation and return it."""
    result = supabase.table('conversations').select('*').eq('id', conversation_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    conv = result.data[0]
    user_tenant_id = _get_user_tenant_id(payload)
    
    if user_tenant_id and conv.get('tenant_id') != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    # Agents can only access their assigned conversations
    if payload.get('role') == 'agent':
        user_id = payload.get('user_id')
        if conv.get('assigned_to') and conv.get('assigned_to') != user_id:
            raise HTTPException(status_code=403, detail="Acesso negado")
    
    return conv


def _format_conversation(c: dict) -> dict:
    """Format conversation for API response."""
    avatar = c.get('contact_avatar')
    if isinstance(avatar, str) and 'api.dicebear.com' in avatar:
        avatar = None
    return {
        'id': c['id'],
        'tenantId': c['tenant_id'],
        'connectionId': c['connection_id'],
        'contactPhone': c['contact_phone'],
        'contactName': c['contact_name'],
        'contactAvatar': avatar,
        'status': c['status'],
        'assignedTo': c.get('assigned_to'),
        'transferStatus': c.get('transfer_status'),
        'transferTo': c.get('transfer_to'),
        'transferReason': c.get('transfer_reason'),
        'transferInitiatedBy': c.get('transfer_initiated_by'),
        'transferInitiatedAt': c.get('transfer_initiated_at'),
        'transferCompletedAt': c.get('transfer_completed_at'),
        'lastMessageAt': c.get('last_message_at'),
        'unreadCount': c.get('unread_count', 0),
        'lastMessagePreview': c.get('last_message_preview'),
        'labels': c.get('labels', []),
        'createdAt': c.get('created_at')
    }


@router.get("")
async def list_conversations(
    tenant_id: Optional[str] = Query(None),
    status: Optional[str] = None,
    connection_id: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    payload: dict = Depends(verify_token)
):
    """List conversations for a tenant."""
    try:
        user_tenant_id = _get_user_tenant_id(payload)
        effective_tenant_id = user_tenant_id or tenant_id
        if not effective_tenant_id:
            raise HTTPException(status_code=403, detail="Tenant não identificado")

        query = supabase.table('conversations').select('*').eq('tenant_id', effective_tenant_id)
        
        # Agents see only their assigned conversations
        if payload.get('role') == 'agent':
            user_id = payload.get('user_id')
            if user_id:
                query = query.or_(f"assigned_to.is.null,assigned_to.eq.{user_id}")

        if status and status != 'all':
            query = query.eq('status', status)
        if connection_id and connection_id != 'all':
            query = query.eq('connection_id', connection_id)

        limit = max(1, min(limit, 1000))
        offset = max(0, offset)

        try:
            result = db_call_with_retry(
                "conversations.list",
                lambda: query.order('last_message_at', desc=True).range(offset, offset + limit - 1).execute()
            )
        except Exception as e:
            if is_missing_table_or_schema_error(e, "conversations"):
                return []
            raise

        return [_format_conversation(c) for c in (result.data or [])]

    except HTTPException:
        raise
    except Exception as e:
        if is_supabase_not_configured_error(e) or is_missing_table_or_schema_error(e, "conversations"):
            return []
        if is_transient_db_error(e):
            raise HTTPException(status_code=503, detail="Banco de dados indisponível.")
        logger.error(f"Error listing conversations: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao listar conversas: {str(e)}")


@router.patch("/{conversation_id}/status")
async def update_conversation_status(
    conversation_id: str,
    status_update: ConversationStatusUpdate,
    payload: dict = Depends(verify_token)
):
    """Update conversation status."""
    _require_conversation_access(conversation_id, payload)
    result = supabase.table('conversations').update({'status': status_update.status}).eq('id', conversation_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    return _format_conversation(result.data[0])


@router.post("/initiate")
async def initiate_conversation(data: InitiateConversation, payload: dict = Depends(verify_token)):
    """Initiate a conversation with a contact."""
    tenant_id = _get_user_tenant_id(payload)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant não identificado")

    raw_phone = (data.phone or '').strip()
    if not raw_phone:
        raise HTTPException(status_code=400, detail="Telefone obrigatório")

    normalized_phone = re.sub(r'\D', '', raw_phone)
    if not normalized_phone:
        raise HTTPException(status_code=400, detail="Telefone obrigatório")

    # Check if conversation already exists
    result = supabase.table('conversations').select('*').eq('tenant_id', tenant_id).eq('contact_phone', normalized_phone).execute()
    if result.data:
        return _format_conversation(result.data[0])

    # Find a connection
    conn_result = supabase.table('connections').select('*').eq('tenant_id', tenant_id).eq('status', 'connected').limit(1).execute()
    if not conn_result.data:
        conn_result = supabase.table('connections').select('*').eq('tenant_id', tenant_id).limit(1).execute()
    if not conn_result.data:
        raise HTTPException(status_code=400, detail="Nenhuma conexão disponível para iniciar conversa")
    
    connection = conn_result.data[0]

    # Try to get contact name
    contact_name = normalized_phone
    if data.contact_id:
        try:
            contact_result = supabase.table('contacts').select('name, full_name').eq('id', data.contact_id).eq('tenant_id', tenant_id).limit(1).execute()
            if contact_result.data:
                contact_name = contact_result.data[0].get('name') or contact_result.data[0].get('full_name') or normalized_phone
        except Exception:
            pass

    conv_data = {
        'tenant_id': tenant_id,
        'connection_id': connection['id'],
        'contact_phone': normalized_phone,
        'contact_name': contact_name,
        'contact_avatar': None,
        'status': 'open',
        'unread_count': 0,
        'last_message_at': datetime.utcnow().isoformat(),
        'last_message_preview': ''
    }
    
    result = supabase.table('conversations').insert(conv_data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erro ao criar conversa")
    
    return _format_conversation(result.data[0])


@router.post("/{conversation_id}/read")
async def mark_conversation_read(conversation_id: str, payload: dict = Depends(verify_token)):
    """Mark conversation as read."""
    _require_conversation_access(conversation_id, payload)
    result = supabase.table('conversations').update({'unread_count': 0}).eq('id', conversation_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    return {"success": True}


@router.post("/{conversation_id}/assign")
async def assign_conversation(conversation_id: str, data: AssignAgent, payload: dict = Depends(verify_token)):
    """Assign conversation to agent."""
    _require_conversation_access(conversation_id, payload)
    
    supabase.table('conversations').update({'assigned_to': data.agent_id}).eq('id', conversation_id).execute()
    
    try:
        supabase.table('assignment_history').insert({
            'conversation_id': conversation_id,
            'assigned_to': data.agent_id,
            'assigned_by': payload.get('user_id'),
            'action': 'assigned'
        }).execute()
    except Exception:
        pass
    
    return {"success": True, "assignedTo": data.agent_id}


@router.post("/{conversation_id}/unassign")
async def unassign_conversation(conversation_id: str, payload: dict = Depends(verify_token)):
    """Unassign conversation."""
    _require_conversation_access(conversation_id, payload)
    
    supabase.table('conversations').update({'assigned_to': None}).eq('id', conversation_id).execute()
    
    return {"success": True}


@router.post("/{conversation_id}/transfer")
async def transfer_conversation(
    conversation_id: str,
    data: ConversationTransferCreate,
    payload: dict = Depends(verify_token)
):
    """Transfer conversation to another agent."""
    conv = _require_conversation_access(conversation_id, payload)

    to_user = supabase.table('users').select('id, name, tenant_id').eq('id', data.to_agent_id).execute()
    if not to_user.data:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    to_agent = to_user.data[0]
    
    if conv.get('tenant_id') and to_agent.get('tenant_id') != conv.get('tenant_id'):
        raise HTTPException(status_code=400, detail="Agente não pertence ao mesmo tenant")

    now = datetime.utcnow().isoformat()
    reason = (data.reason or '').strip() or None

    update_data = {
        'assigned_to': data.to_agent_id,
        'transfer_status': 'in_transfer',
        'transfer_to': data.to_agent_id,
        'transfer_reason': reason,
        'transfer_initiated_by': payload.get('user_id'),
        'transfer_initiated_at': now,
        'transfer_completed_at': None
    }

    updated = supabase.table('conversations').update(update_data).eq('id', conversation_id).execute()
    if not updated.data:
        raise HTTPException(status_code=400, detail="Erro ao transferir conversa")

    # Record transfer history
    try:
        supabase.table('assignment_history').insert({
            'conversation_id': conversation_id,
            'assigned_to': data.to_agent_id,
            'assigned_by': payload.get('user_id'),
            'action': 'transferred',
            'notes': reason
        }).execute()
    except Exception:
        pass

    return {"success": True}


@router.post("/{conversation_id}/transfer/accept")
async def accept_conversation_transfer(conversation_id: str, payload: dict = Depends(verify_token)):
    """Accept a conversation transfer."""
    user_id = payload.get('user_id')
    conv = _require_conversation_access(conversation_id, payload)
    
    if conv.get('transfer_to') and conv.get('transfer_to') != user_id:
        raise HTTPException(status_code=403, detail="Apenas o agente de destino pode aceitar")

    now = datetime.utcnow().isoformat()
    supabase.table('conversations').update({
        'transfer_status': 'completed',
        'transfer_completed_at': now
    }).eq('id', conversation_id).execute()

    return {"success": True}


@router.post("/{conversation_id}/labels/{label_id}")
async def add_label(conversation_id: str, label_id: str, payload: dict = Depends(verify_token)):
    """Add label to conversation."""
    conv = _require_conversation_access(conversation_id, payload)
    
    labels = conv.get('labels') or []
    if label_id not in labels:
        labels.append(label_id)
        supabase.table('conversations').update({'labels': labels}).eq('id', conversation_id).execute()
    
    return {"success": True}


@router.delete("/{conversation_id}/labels/{label_id}")
async def remove_label(conversation_id: str, label_id: str, payload: dict = Depends(verify_token)):
    """Remove label from conversation."""
    conv = _require_conversation_access(conversation_id, payload)
    
    labels = conv.get('labels') or []
    if label_id in labels:
        labels.remove(label_id)
        supabase.table('conversations').update({'labels': labels}).eq('id', conversation_id).execute()
    
    return {"success": True}


@router.delete("/purge")
async def purge_conversations(tenant_id: Optional[str] = None, payload: dict = Depends(verify_token)):
    """Purge all conversations for a tenant."""
    user_tenant_id = _get_user_tenant_id(payload)
    effective_tenant_id = tenant_id if payload.get('role') == 'superadmin' else user_tenant_id
    
    if not effective_tenant_id:
        raise HTTPException(status_code=403, detail="Tenant não identificado")

    count_result = supabase.table('conversations').select('id', count='exact').eq('tenant_id', effective_tenant_id).execute()
    total = count_result.count or 0

    if total <= 0:
        return {"success": True, "deletedConversations": 0}

    # Delete related data first
    conv_ids_result = supabase.table('conversations').select('id').eq('tenant_id', effective_tenant_id).execute()
    conversation_ids = [row.get('id') for row in (conv_ids_result.data or []) if row.get('id')]

    for i in range(0, len(conversation_ids), 200):
        chunk = conversation_ids[i:i + 200]
        try:
            supabase.table('messages').delete().in_('conversation_id', chunk).execute()
        except Exception:
            pass
        try:
            supabase.table('assignment_history').delete().in_('conversation_id', chunk).execute()
        except Exception:
            pass

    supabase.table('conversations').delete().eq('tenant_id', effective_tenant_id).execute()

    return {"success": True, "deletedConversations": total}


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str, payload: dict = Depends(verify_token)):
    """Delete a conversation and its messages."""
    _require_conversation_access(conversation_id, payload)

    supabase.table('messages').delete().eq('conversation_id', conversation_id).execute()
    supabase.table('conversations').delete().eq('id', conversation_id).execute()
    
    return {"success": True}


@router.delete("/{conversation_id}/messages")
async def clear_conversation_messages(conversation_id: str, payload: dict = Depends(verify_token)):
    """Clear all messages from a conversation."""
    _require_conversation_access(conversation_id, payload)

    supabase.table('messages').delete().eq('conversation_id', conversation_id).execute()
    supabase.table('conversations').update({
        'last_message_at': None,
        'last_message_preview': '',
        'unread_count': 0
    }).eq('id', conversation_id).execute()
    
    return {"success": True}
