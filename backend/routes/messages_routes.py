"""
Messages routes extracted from server.py.

This module contains all message-related endpoints:
- GET /messages - List messages
- POST /messages - Send message
- DELETE /messages/{id} - Delete message
- POST /whatsapp/send - Send WhatsApp direct
- POST /whatsapp/typing - Send typing indicator
- GET /messages/{id}/reactions - Get reactions
- POST /messages/{id}/reactions - Add reaction
- DELETE /messages/{id}/reactions/{reaction_id} - Remove reaction
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query

try:
    from ..supabase_client import supabase
    from ..models import MessageCreate, SendWhatsAppMessage
    from ..utils.auth_helpers import verify_token
    from ..whatsapp.container import get_whatsapp_container
    from ..whatsapp.observability import LogContext
    from ..whatsapp.providers.base import ConnectionRef, ProviderContext, SendMessageRequest
except ImportError:
    from supabase_client import supabase
    from models import MessageCreate, SendWhatsAppMessage
    from utils.auth_helpers import verify_token
    from whatsapp.container import get_whatsapp_container
    from whatsapp.observability import LogContext
    from whatsapp.providers.base import ConnectionRef, ProviderContext, SendMessageRequest

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["Messages"])


# ==================== HELPER FUNCTIONS ====================

def _get_user_tenant_id(payload: dict) -> Optional[str]:
    """Get tenant ID from user payload."""
    return payload.get('tenant_id')


def _get_whatsapp_container_instance():
    return get_whatsapp_container()


def _get_whatsapp_provider(provider_id: str):
    return _get_whatsapp_container_instance().registry.get(provider_id)


def _make_provider_ctx(*, tenant_id: str, provider: str, instance_name: str, correlation_id: str = None):
    container = _get_whatsapp_container_instance()
    log_ctx = LogContext(
        tenant_id=str(tenant_id or ""),
        provider=str(provider or ""),
        instance_name=str(instance_name or ""),
        correlation_id=str(correlation_id) if correlation_id else None,
    )
    return container, ProviderContext(obs=container.obs, log_ctx=log_ctx)


def _whatsapp_http_error(e: Exception) -> HTTPException:
    """Convert WhatsApp provider exception to HTTP exception."""
    msg = str(e)
    if "401" in msg or "unauthorized" in msg.lower():
        return HTTPException(status_code=401, detail="Credenciais do provedor inválidas")
    if "404" in msg or "not found" in msg.lower():
        return HTTPException(status_code=404, detail="Instância não encontrada no provedor")
    if "timeout" in msg.lower():
        return HTTPException(status_code=504, detail="Timeout ao conectar com o provedor")
    return HTTPException(status_code=502, detail=f"Erro do provedor: {msg[:200]}")


def _require_conversation_access(conversation_id: str, payload: dict):
    """Check if user has access to conversation."""
    conv = supabase.table('conversations').select('tenant_id').eq('id', conversation_id).execute()
    if not conv.data:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    user_tenant_id = _get_user_tenant_id(payload)
    if payload.get('role') != 'superadmin' and user_tenant_id and conv.data[0]['tenant_id'] != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")


def _enforce_messages_limit(tenant_id: Optional[str]):
    """Check if tenant has reached messages limit."""
    if not tenant_id:
        return
    # TODO: Implement actual limit checking
    pass


def _normalize_message_content(content: Any, msg_type: str) -> str:
    """Normalize message content for display."""
    if content is None:
        return ''
    if isinstance(content, (int, float, bool)):
        return str(content)
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        cur: Any = content
        for _ in range(10):
            if not isinstance(cur, dict):
                break
            if isinstance(cur.get('message'), dict):
                cur = cur.get('message')
                continue
            ephemeral = cur.get('ephemeralMessage')
            if isinstance(ephemeral, dict) and isinstance(ephemeral.get('message'), dict):
                cur = ephemeral.get('message')
                continue
            view_once = cur.get('viewOnceMessage')
            if isinstance(view_once, dict) and isinstance(view_once.get('message'), dict):
                cur = view_once.get('message')
                continue
            view_once_v2 = cur.get('viewOnceMessageV2')
            if isinstance(view_once_v2, dict) and isinstance(view_once_v2.get('message'), dict):
                cur = view_once_v2.get('message')
                continue
            break

        if isinstance(cur, dict):
            if isinstance(cur.get('content'), str):
                return cur.get('content') or ''
            if isinstance(cur.get('text'), str):
                return cur.get('text') or ''
            if isinstance(cur.get('conversation'), str):
                return cur.get('conversation') or ''

            tm = cur.get('textMessage')
            if isinstance(tm, dict) and isinstance(tm.get('text'), str):
                return tm.get('text') or ''

            etm = cur.get('extendedTextMessage')
            if isinstance(etm, dict) and isinstance(etm.get('text'), str):
                return etm.get('text') or ''

            br = cur.get('buttonsResponseMessage')
            if isinstance(br, dict):
                v = br.get('selectedDisplayText') or br.get('selectedButtonId')
                if isinstance(v, str):
                    return v or ''

            lr = cur.get('listResponseMessage')
            if isinstance(lr, dict):
                title = lr.get('title')
                if isinstance(title, str) and title.strip():
                    return title

            img = cur.get('imageMessage')
            if isinstance(img, dict) and isinstance(img.get('caption'), str) and img.get('caption'):
                return img.get('caption') or ''
            vid = cur.get('videoMessage')
            if isinstance(vid, dict) and isinstance(vid.get('caption'), str) and vid.get('caption'):
                return vid.get('caption') or ''
            doc = cur.get('documentMessage')
            if isinstance(doc, dict):
                if isinstance(doc.get('fileName'), str) and doc.get('fileName'):
                    return doc.get('fileName') or ''

        if msg_type == 'audio':
            return '[Áudio]'
        if msg_type == 'image':
            return '[Imagem]'
        if msg_type == 'video':
            return '[Vídeo]'
        if msg_type == 'document':
            return '[Documento]'
        if msg_type == 'sticker':
            return '[Figurinha]'
        return '[Mensagem]'
    if isinstance(content, list):
        return '[Mensagem]'
    return str(content)


def _parse_bool(value: Any) -> bool:
    """Parse boolean from various types."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ['true', '1', 'yes', 'y', 'sim']:
            return True
    return False


def _build_user_signature_prefix(user_row: dict) -> str:
    """Build signature prefix from user data."""
    enabled = user_row.get('signature_enabled', True)
    if enabled is False:
        return ''

    name = (user_row.get('name') or '').strip()
    if not name:
        return ''

    extras: List[str] = []
    if user_row.get('signature_include_title') and (user_row.get('job_title') or '').strip():
        extras.append((user_row.get('job_title') or '').strip())
    if user_row.get('signature_include_department') and (user_row.get('department') or '').strip():
        extras.append((user_row.get('department') or '').strip())

    first_line = f"*{name}*"
    if extras:
        first_line += f" ({' / '.join(extras)})"
    return first_line + "\n"


def _extract_sent_message_id(obj: Any) -> Optional[str]:
    """Extract message ID from send result."""
    seen: Set[int] = set()

    def _walk(node: Any, depth: int = 0) -> Optional[str]:
        if node is None or depth > 6:
            return None
        try:
            node_id = id(node)
            if node_id in seen:
                return None
            seen.add(node_id)
        except Exception:
            pass

        if isinstance(node, dict):
            key = node.get("key")
            if isinstance(key, dict):
                v = key.get("id")
                if isinstance(v, str) and v.strip():
                    return v.strip()
            for k in ("message_id", "messageId", "stanzaId", "id"):
                v = node.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
            for k in ("data", "message", "result", "response"):
                if k in node:
                    found = _walk(node.get(k), depth + 1)
                    if found:
                        return found
            for v in node.values():
                found = _walk(v, depth + 1)
                if found:
                    return found
            return None

        if isinstance(node, list):
            for v in node:
                found = _walk(v, depth + 1)
                if found:
                    return found
            return None

        return None

    return _walk(obj, 0)


def _read_message_metadata(message_id: str) -> dict:
    """Read message metadata from database."""
    try:
        row = supabase.table("messages").select("metadata").eq("id", message_id).limit(1).execute()
        if row.data and isinstance(row.data[0].get("metadata"), dict):
            return row.data[0].get("metadata") or {}
    except Exception:
        return {}
    return {}


def _safe_insert_audit_log(
    tenant_id: Optional[str],
    actor_user_id: Optional[str],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    metadata: Optional[dict] = None
):
    """Insert audit log safely."""
    try:
        supabase.table('audit_logs').insert({
            'tenant_id': tenant_id,
            'actor_user_id': actor_user_id,
            'action': action,
            'entity_type': entity_type,
            'entity_id': entity_id,
            'metadata': metadata or {}
        }).execute()
    except Exception:
        pass


async def send_provider_message(
    connection: ConnectionRef, 
    phone: str, 
    content: str, 
    msg_type: str, 
    message_id: str, 
    *, 
    caption: str = None, 
    filename: str = None
):
    """Send message via provider."""
    try:
        _container, ctx = _make_provider_ctx(
            tenant_id=connection.tenant_id,
            provider=connection.provider,
            instance_name=connection.instance_name,
            correlation_id=f"send:{message_id}",
        )
        provider = _get_whatsapp_provider(connection.provider)
        req = SendMessageRequest(
            instance_name=connection.instance_name,
            phone=phone,
            kind=msg_type,
            content=content,
            caption=caption,
            filename=filename,
        )
        result = await provider.send_message(ctx, connection=connection, req=req)

        external_id = _extract_sent_message_id(result)
        if external_id:
            current_meta = _read_message_metadata(message_id)
            next_meta = {**current_meta, "message_id": external_id}
            supabase.table("messages").update({"status": "delivered", "external_id": external_id, "metadata": next_meta}).eq("id", message_id).execute()
        else:
            supabase.table("messages").update({"status": "delivered"}).eq("id", message_id).execute()
    except Exception as e:
        logger.error(f"Failed to send provider message: {e}")
        try:
            supabase.table("messages").update({"status": "failed"}).eq("id", message_id).execute()
        except Exception:
            pass


# ==================== ROUTES ====================

@router.get("/messages")
async def list_messages(
    conversation_id: str,
    after: Optional[str] = None,
    before: Optional[str] = None,
    limit: int = 500,
    tail: bool = False,
    payload: dict = Depends(verify_token)
):
    """List messages for a conversation."""
    _require_conversation_access(conversation_id, payload)

    query = supabase.table('messages').select('*').eq('conversation_id', conversation_id)
    descending = False
    if after:
        query = query.gt('timestamp', after)
    else:
        if before:
            query = query.lt('timestamp', before)
        if tail or before:
            descending = True
    
    result = query.order('timestamp', desc=descending).limit(limit).execute()
    rows = result.data or []
    if descending:
        rows = list(reversed(rows))
    
    messages = []
    for m in rows:
        raw_direction = m.get('direction') or 'inbound'
        metadata = m.get('metadata') or {}
        from_me = False
        if isinstance(metadata, dict):
            from_me = _parse_bool(metadata.get('from_me')) or _parse_bool(metadata.get('fromMe'))
        direction = 'outbound' if from_me else raw_direction

        msg_type = (m.get('type') or 'text').lower()
        if msg_type == 'system':
            origin = 'system'
            direction = 'outbound'
        elif direction == 'outbound':
            origin = 'agent'
        else:
            origin = 'customer'
        
        messages.append({
            'id': m['id'],
            'conversationId': m['conversation_id'],
            'content': _normalize_message_content(m.get('content'), m.get('type') or 'text'),
            'type': m['type'],
            'direction': direction,
            'status': m['status'],
            'mediaUrl': m['media_url'],
            'externalId': m.get('external_id'),
            'metadata': m.get('metadata'),
            'timestamp': m['timestamp'],
            'origin': origin
        })
    
    return messages


@router.delete("/messages/{message_id}")
async def delete_message(message_id: str, payload: dict = Depends(verify_token)):
    """Delete a message."""
    msg = supabase.table('messages').select('id, conversation_id').eq('id', message_id).execute()
    if not msg.data:
        raise HTTPException(status_code=404, detail="Mensagem não encontrada")
    
    conversation_id = msg.data[0]['conversation_id']
    _require_conversation_access(conversation_id, payload)

    supabase.table('messages').delete().eq('id', message_id).execute()

    # Update conversation preview
    latest = supabase.table('messages').select('content, timestamp, type').eq('conversation_id', conversation_id).order('timestamp', desc=True).limit(1).execute()
    if latest.data:
        lm = latest.data[0]
        content = _normalize_message_content(lm.get('content'), lm.get('type') or 'text')
        preview = (content or '').strip()[:50]
        supabase.table('conversations').update({
            'last_message_at': lm.get('timestamp'),
            'last_message_preview': preview
        }).eq('id', conversation_id).execute()
    else:
        supabase.table('conversations').update({
            'last_message_at': None,
            'last_message_preview': '',
            'unread_count': 0
        }).eq('id', conversation_id).execute()

    return {"success": True, "conversationId": conversation_id}


@router.post("/messages")
async def send_message(
    message: MessageCreate, 
    background_tasks: BackgroundTasks, 
    payload: dict = Depends(verify_token)
):
    """Send a new message."""
    _require_conversation_access(message.conversation_id, payload)
    
    # Get conversation details
    conv = supabase.table('conversations').select('*, connections(*)').eq('id', message.conversation_id).execute()
    if not conv.data:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    conversation = conv.data[0]
    connection = conversation.get('connections')
    
    content = (message.content or '').strip()
    if not content:
        raise HTTPException(status_code=400, detail="Mensagem vazia")

    preview_content = content
    if (message.type or 'text') != 'system':
        try:
            user_row = supabase.table('users').select('name, job_title, department, signature_enabled, signature_include_title, signature_include_department').eq('id', payload.get('user_id')).execute()
            if user_row.data:
                prefix = _build_user_signature_prefix(user_row.data[0])
                if prefix and not content.startswith(prefix) and not content.lstrip().startswith(f"*{(user_row.data[0].get('name') or '').strip()}*"):
                    content = prefix + content
        except Exception:
            pass

    _enforce_messages_limit(conversation.get('tenant_id'))

    # Save message to database
    data = {
        'conversation_id': message.conversation_id,
        'content': content,
        'type': message.type,
        'direction': 'outbound',
        'status': 'sent'
    }
    
    result = supabase.table('messages').insert(data).execute()
    
    # Update conversation
    supabase.table('conversations').update({
        'last_message_at': datetime.utcnow().isoformat(),
        'last_message_preview': preview_content[:50]
    }).eq('id', message.conversation_id).execute()
    
    # Update tenant message count
    if conversation.get('tenant_id'):
        tenant = supabase.table('tenants').select('messages_this_month').eq('id', conversation['tenant_id']).execute()
        if tenant.data:
            new_count = tenant.data[0]['messages_this_month'] + 1
            supabase.table('tenants').update({'messages_this_month': new_count}).eq('id', conversation['tenant_id']).execute()

    _safe_insert_audit_log(
        tenant_id=conversation.get('tenant_id'),
        actor_user_id=payload.get('user_id'),
        action='message.sent',
        entity_type='message',
        entity_id=(result.data[0]['id'] if result.data else None),
        metadata={'conversation_id': message.conversation_id, 'type': message.type}
    )
    
    status = 'sent'

    if connection and isinstance(connection, dict):
        provider_id = str(connection.get("provider") or "").strip().lower()
        connection_status = str(connection.get("status") or "").strip().lower()
        is_connected = connection_status in ["connected", "open"]
        instance_name = str(connection.get("instance_name") or "").strip()
        
        if provider_id and is_connected and instance_name:
            conn_ref = ConnectionRef(
                tenant_id=str(conversation.get("tenant_id") or ""),
                provider=provider_id,
                instance_name=instance_name,
                phone_number=str(connection.get("phone_number") or "") or None,
                config=connection.get("config") if isinstance(connection.get("config"), dict) else {},
            )
            background_tasks.add_task(
                send_provider_message,
                conn_ref,
                conversation["contact_phone"],
                content,
                message.type,
                result.data[0]["id"],
            )
        else:
            supabase.table("messages").update({"status": "failed"}).eq("id", result.data[0]["id"]).execute()
            status = "failed"
    else:
        supabase.table("messages").update({"status": "failed"}).eq("id", result.data[0]["id"]).execute()
        status = "failed"
    
    m = result.data[0]
    return {
        'id': m['id'],
        'conversationId': m['conversation_id'],
        'content': m['content'],
        'type': m['type'],
        'direction': m['direction'],
        'status': status,
        'mediaUrl': m['media_url'],
        'timestamp': m['timestamp']
    }


@router.post("/whatsapp/send")
async def send_whatsapp_direct(data: SendWhatsAppMessage, payload: dict = Depends(verify_token)):
    """Send WhatsApp message directly."""
    try:
        provider_id = str(data.provider or "evolution").strip().lower()
        instance_name = str(data.instance_name or "").strip()
        conn_ref = ConnectionRef(
            tenant_id=str(_get_user_tenant_id(payload) or ""),
            provider=provider_id,
            instance_name=instance_name,
            config=data.config if isinstance(data.config, dict) else {},
        )
        _container, ctx = _make_provider_ctx(
            tenant_id=conn_ref.tenant_id,
            provider=provider_id,
            instance_name=instance_name,
            correlation_id="whatsapp_direct",
        )
        provider = _get_whatsapp_provider(provider_id)

        kind = str(data.type or "text").strip().lower()
        content = str(data.message or "").strip()
        media_url = str(data.media_url or "").strip() or None

        req = SendMessageRequest(
            instance_name=instance_name,
            phone=data.phone,
            kind=kind,
            content=media_url or content,
            caption=(content if kind in {"image", "video", "document"} else None),
            filename=(content if kind in {"document", "file"} else None),
        )
        result = await provider.send_message(ctx, connection=conn_ref, req=req)
        return {"success": True, "result": result}
    except Exception as e:
        raise _whatsapp_http_error(e)


@router.post("/whatsapp/typing")
async def send_typing_indicator(
    instance_name: str,
    phone: str,
    provider: str = Query("evolution"),
    presence: str = Query("composing"),
    config: Optional[dict[str, Any]] = Body(None),
    payload: dict = Depends(verify_token),
):
    """Send typing indicator."""
    try:
        provider_id = str(provider or "evolution").strip().lower()
        instance_name_norm = str(instance_name or "").strip()
        conn_ref = ConnectionRef(
            tenant_id=str(_get_user_tenant_id(payload) or ""),
            provider=provider_id,
            instance_name=instance_name_norm,
            config=config if isinstance(config, dict) else {},
        )
        _container, ctx = _make_provider_ctx(
            tenant_id=conn_ref.tenant_id,
            provider=provider_id,
            instance_name=instance_name_norm,
            correlation_id="typing",
        )
        provider_impl = _get_whatsapp_provider(provider_id)
        result = await provider_impl.send_presence(ctx, connection=conn_ref, phone=phone, presence=presence)
        return {"success": True, "result": result}
    except Exception as e:
        raise _whatsapp_http_error(e)


# ==================== REACTIONS ====================

@router.get("/messages/{message_id}/reactions")
async def get_message_reactions(message_id: str, payload: dict = Depends(verify_token)):
    """Get reactions for a message."""
    try:
        msg = supabase.table('messages').select('conversation_id').eq('id', message_id).execute()
        if not msg.data:
            raise HTTPException(status_code=404, detail="Mensagem não encontrada")
        _require_conversation_access(msg.data[0].get('conversation_id'), payload)
        result = supabase.table('message_reactions').select('*, users(name, avatar)').eq('message_id', message_id).execute()
        return [{
            'id': r['id'],
            'emoji': r['emoji'],
            'userId': r['user_id'],
            'userName': r['users']['name'] if r.get('users') else None,
            'userAvatar': r['users']['avatar'] if r.get('users') else None
        } for r in result.data] if result.data else []
    except Exception as e:
        logger.error(f"Error getting reactions: {e}")
        return []


@router.post("/messages/{message_id}/reactions")
async def add_message_reaction(message_id: str, emoji: str, payload: dict = Depends(verify_token)):
    """Add a reaction to a message."""
    try:
        msg = supabase.table('messages').select('conversation_id').eq('id', message_id).execute()
        if not msg.data:
            raise HTTPException(status_code=404, detail="Mensagem não encontrada")
        _require_conversation_access(msg.data[0].get('conversation_id'), payload)
        user_id = payload.get('user_id')
        
        # Check if user already reacted with this emoji
        existing = supabase.table('message_reactions').select('id').eq('message_id', message_id).eq('user_id', user_id).eq('emoji', emoji).execute()
        
        if existing.data:
            # Remove the reaction (toggle)
            supabase.table('message_reactions').delete().eq('id', existing.data[0]['id']).execute()
            return {"success": True, "action": "removed"}
        else:
            # Add the reaction
            supabase.table('message_reactions').insert({
                'message_id': message_id,
                'user_id': user_id,
                'emoji': emoji
            }).execute()
            return {"success": True, "action": "added"}
    except Exception as e:
        logger.error(f"Error adding reaction: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/messages/{message_id}/reactions/{reaction_id}")
async def remove_message_reaction(message_id: str, reaction_id: str, payload: dict = Depends(verify_token)):
    """Remove a reaction from a message."""
    try:
        msg = supabase.table('messages').select('conversation_id').eq('id', message_id).execute()
        if not msg.data:
            raise HTTPException(status_code=404, detail="Mensagem não encontrada")
        _require_conversation_access(msg.data[0].get('conversation_id'), payload)
        supabase.table('message_reactions').delete().eq('id', reaction_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
