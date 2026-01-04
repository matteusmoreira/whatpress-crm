from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
from supabase_client import supabase
from evolution_api import evolution_api, EvolutionAPI
from features import QuickRepliesService, LabelsService, AgentService, DEFAULT_QUICK_REPLIES, DEFAULT_LABELS
import jwt
import json
import base64

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Create the main app
app = FastAPI(title="WhatsApp CRM API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Security
security = HTTPBearer(auto_error=False)
JWT_SECRET = "whatsapp-crm-secret-key-2025"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== MODELS ====================

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    user: dict
    token: str

class TenantCreate(BaseModel):
    name: str
    slug: str

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    plan: Optional[str] = None

class ConnectionCreate(BaseModel):
    tenant_id: str
    provider: str
    instance_name: str
    phone_number: str

class ConnectionStatusUpdate(BaseModel):
    status: str

class ConversationStatusUpdate(BaseModel):
    status: str

class MessageCreate(BaseModel):
    conversation_id: str
    content: str
    type: str = "text"

class SendWhatsAppMessage(BaseModel):
    instance_name: str
    phone: str
    message: str
    type: str = "text"
    media_url: Optional[str] = None

class QuickReplyCreate(BaseModel):
    title: str
    content: str
    category: str = "custom"

class LabelCreate(BaseModel):
    name: str
    color: str

class AssignAgent(BaseModel):
    agent_id: str

class TenantRegister(BaseModel):
    tenant_name: str
    tenant_slug: str
    admin_name: str
    admin_email: str
    admin_password: str
    plan: str = "free"

# ==================== AUTH ====================

def create_token(user_id: str, email: str, role: str):
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "exp": datetime.utcnow().timestamp() + 86400 * 7  # 7 days
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Token não fornecido")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

def get_user_tenant_id(payload: dict) -> str:
    """Get tenant ID from user"""
    if payload['role'] == 'superadmin':
        return None
    user = supabase.table('users').select('tenant_id').eq('id', payload['user_id']).execute()
    if user.data:
        return user.data[0]['tenant_id']
    return None

# ==================== AUTH ROUTES ====================

@api_router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login with email and password"""
    result = supabase.table('users').select('*').eq('email', request.email).eq('password_hash', request.password).execute()
    
    if not result.data:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    
    user = result.data[0]
    token = create_token(user['id'], user['email'], user['role'])
    
    user_response = {
        'id': user['id'],
        'email': user['email'],
        'name': user['name'],
        'role': user['role'],
        'tenantId': user['tenant_id'],
        'avatar': user['avatar'],
        'createdAt': user['created_at']
    }
    
    return {"user": user_response, "token": token}

@api_router.post("/auth/register")
async def register_tenant(data: TenantRegister):
    """Register a new tenant with admin user"""
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
        'password_hash': data.admin_password,  # In production, hash this!
        'name': data.admin_name,
        'role': 'admin',
        'tenant_id': tenant['id'],
        'avatar': f"https://api.dicebear.com/7.x/avataaars/svg?seed={data.admin_email}"
    }
    user_result = supabase.table('users').insert(user_data).execute()
    user = user_result.data[0]
    
    # Generate token
    token = create_token(user['id'], user['email'], user['role'])
    
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

@api_router.get("/auth/me")
async def get_current_user(payload: dict = Depends(verify_token)):
    """Get current authenticated user"""
    result = supabase.table('users').select('*').eq('id', payload['user_id']).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    user = result.data[0]
    return {
        'id': user['id'],
        'email': user['email'],
        'name': user['name'],
        'role': user['role'],
        'tenantId': user['tenant_id'],
        'avatar': user['avatar']
    }

# ==================== TENANTS ROUTES ====================

@api_router.get("/tenants")
async def list_tenants(payload: dict = Depends(verify_token)):
    """List all tenants (superadmin only)"""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    result = supabase.table('tenants').select('*').order('created_at', desc=True).execute()
    
    tenants = []
    for t in result.data:
        tenants.append({
            'id': t['id'],
            'name': t['name'],
            'slug': t['slug'],
            'status': t['status'],
            'plan': t['plan'],
            'messagesThisMonth': t['messages_this_month'],
            'connectionsCount': t['connections_count'],
            'createdAt': t['created_at'],
            'updatedAt': t['updated_at']
        })
    
    return tenants

@api_router.get("/tenants/stats")
async def get_tenants_stats(payload: dict = Depends(verify_token)):
    """Get tenants statistics"""
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

@api_router.post("/tenants")
async def create_tenant(tenant: TenantCreate, payload: dict = Depends(verify_token)):
    """Create a new tenant"""
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
    
    result = supabase.table('tenants').insert(data).execute()
    
    if not result.data:
        raise HTTPException(status_code=400, detail="Erro ao criar tenant")
    
    t = result.data[0]
    return {
        'id': t['id'],
        'name': t['name'],
        'slug': t['slug'],
        'status': t['status'],
        'plan': t['plan'],
        'messagesThisMonth': t['messages_this_month'],
        'connectionsCount': t['connections_count'],
        'createdAt': t['created_at'],
        'updatedAt': t['updated_at']
    }

@api_router.put("/tenants/{tenant_id}")
async def update_tenant(tenant_id: str, tenant: TenantUpdate, payload: dict = Depends(verify_token)):
    """Update a tenant"""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    data = {k: v for k, v in tenant.dict().items() if v is not None}
    data['updated_at'] = datetime.utcnow().isoformat()
    
    result = supabase.table('tenants').update(data).eq('id', tenant_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    
    return result.data[0]

@api_router.delete("/tenants/{tenant_id}")
async def delete_tenant(tenant_id: str, payload: dict = Depends(verify_token)):
    """Delete a tenant"""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    supabase.table('tenants').delete().eq('id', tenant_id).execute()
    return {"success": True}

# ==================== CONNECTIONS ROUTES ====================

@api_router.get("/connections")
async def list_connections(tenant_id: str, payload: dict = Depends(verify_token)):
    """List connections for a tenant"""
    result = supabase.table('connections').select('*').eq('tenant_id', tenant_id).execute()
    
    connections = []
    for c in result.data:
        connections.append({
            'id': c['id'],
            'tenantId': c['tenant_id'],
            'provider': c['provider'],
            'instanceName': c['instance_name'],
            'phoneNumber': c['phone_number'],
            'status': c['status'],
            'webhookUrl': c['webhook_url'],
            'config': c['config'],
            'createdAt': c['created_at']
        })
    
    return connections

@api_router.post("/connections")
async def create_connection(connection: ConnectionCreate, payload: dict = Depends(verify_token)):
    """Create a new connection"""
    data = {
        'tenant_id': connection.tenant_id,
        'provider': connection.provider,
        'instance_name': connection.instance_name,
        'phone_number': connection.phone_number,
        'status': 'disconnected',
        'webhook_url': '',
        'config': {}
    }
    
    result = supabase.table('connections').insert(data).execute()
    
    # Update tenant connections count
    tenant = supabase.table('tenants').select('connections_count').eq('id', connection.tenant_id).execute()
    if tenant.data:
        new_count = tenant.data[0]['connections_count'] + 1
        supabase.table('tenants').update({'connections_count': new_count}).eq('id', connection.tenant_id).execute()
    
    c = result.data[0]
    return {
        'id': c['id'],
        'tenantId': c['tenant_id'],
        'provider': c['provider'],
        'instanceName': c['instance_name'],
        'phoneNumber': c['phone_number'],
        'status': c['status'],
        'webhookUrl': c['webhook_url'],
        'config': c['config'],
        'createdAt': c['created_at']
    }

@api_router.post("/connections/{connection_id}/test")
async def test_connection(connection_id: str, payload: dict = Depends(verify_token)):
    """Test a connection"""
    conn = supabase.table('connections').select('*').eq('id', connection_id).execute()
    if not conn.data:
        raise HTTPException(status_code=404, detail="Conexão não encontrada")
    
    connection = conn.data[0]
    
    if connection['provider'] == 'evolution':
        try:
            # Check if instance exists in Evolution API
            state = await evolution_api.get_connection_state(connection['instance_name'])
            
            if state.get('instance', {}).get('state') == 'open':
                # Already connected
                webhook_url = f"https://easy-wapp.preview.emergentagent.com/api/webhooks/evolution/{connection['instance_name']}"
                supabase.table('connections').update({
                    'status': 'connected',
                    'webhook_url': webhook_url
                }).eq('id', connection_id).execute()
                
                return {"success": True, "message": "Conexão estabelecida com sucesso!"}
            else:
                # Need to connect - get QR code
                qr_result = await evolution_api.connect_instance(connection['instance_name'])
                return {
                    "success": True, 
                    "message": "Escaneie o QR Code para conectar",
                    "qrcode": qr_result.get('base64'),
                    "pairingCode": qr_result.get('pairingCode')
                }
        except Exception as e:
            # Instance might not exist, try to create it
            try:
                webhook_url = f"https://easy-wapp.preview.emergentagent.com/api/webhooks/evolution/{connection['instance_name']}"
                create_result = await evolution_api.create_instance(
                    connection['instance_name'],
                    webhook_url
                )
                return {
                    "success": True,
                    "message": "Instância criada! Escaneie o QR Code para conectar",
                    "qrcode": create_result.get('qrcode', {}).get('base64')
                }
            except Exception as create_error:
                raise HTTPException(status_code=400, detail=f"Erro ao conectar: {str(create_error)}")
    else:
        # Simulated test for other providers
        import random
        success = random.random() > 0.3
        
        if not success:
            raise HTTPException(status_code=400, detail="Falha ao conectar. Verifique as credenciais.")
        
        webhook_url = f"https://api.whatsappcrm.com/webhooks/{connection['instance_name']}"
        supabase.table('connections').update({'status': 'connected', 'webhook_url': webhook_url}).eq('id', connection_id).execute()
        
        return {"success": True, "message": "Conexão estabelecida com sucesso!"}

@api_router.get("/connections/{connection_id}/qrcode")
async def get_qrcode(connection_id: str, payload: dict = Depends(verify_token)):
    """Get QR code for Evolution API connection"""
    conn = supabase.table('connections').select('*').eq('id', connection_id).execute()
    if not conn.data:
        raise HTTPException(status_code=404, detail="Conexão não encontrada")
    
    connection = conn.data[0]
    
    if connection['provider'] != 'evolution':
        raise HTTPException(status_code=400, detail="QR Code disponível apenas para Evolution API")
    
    try:
        qr_result = await evolution_api.connect_instance(connection['instance_name'])
        return {
            "qrcode": qr_result.get('base64'),
            "pairingCode": qr_result.get('pairingCode'),
            "code": qr_result.get('code')
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.patch("/connections/{connection_id}/status")
async def update_connection_status(connection_id: str, status_update: ConnectionStatusUpdate, payload: dict = Depends(verify_token)):
    """Update connection status"""
    data = {'status': status_update.status}
    if status_update.status == 'disconnected':
        data['webhook_url'] = ''
    
    result = supabase.table('connections').update(data).eq('id', connection_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Conexão não encontrada")
    
    c = result.data[0]
    return {
        'id': c['id'],
        'tenantId': c['tenant_id'],
        'provider': c['provider'],
        'instanceName': c['instance_name'],
        'phoneNumber': c['phone_number'],
        'status': c['status'],
        'webhookUrl': c['webhook_url'],
        'config': c['config'],
        'createdAt': c['created_at']
    }

@api_router.delete("/connections/{connection_id}")
async def delete_connection(connection_id: str, payload: dict = Depends(verify_token)):
    """Delete a connection"""
    conn = supabase.table('connections').select('tenant_id').eq('id', connection_id).execute()
    
    if conn.data:
        tenant_id = conn.data[0]['tenant_id']
        tenant = supabase.table('tenants').select('connections_count').eq('id', tenant_id).execute()
        if tenant.data and tenant.data[0]['connections_count'] > 0:
            new_count = tenant.data[0]['connections_count'] - 1
            supabase.table('tenants').update({'connections_count': new_count}).eq('id', tenant_id).execute()
    
    supabase.table('connections').delete().eq('id', connection_id).execute()
    return {"success": True}

# ==================== CONVERSATIONS ROUTES ====================

@api_router.get("/conversations")
async def list_conversations(tenant_id: str, status: Optional[str] = None, connection_id: Optional[str] = None, payload: dict = Depends(verify_token)):
    """List conversations for a tenant"""
    query = supabase.table('conversations').select('*').eq('tenant_id', tenant_id)
    
    if status and status != 'all':
        query = query.eq('status', status)
    if connection_id and connection_id != 'all':
        query = query.eq('connection_id', connection_id)
    
    result = query.order('last_message_at', desc=True).execute()
    
    conversations = []
    for c in result.data:
        conversations.append({
            'id': c['id'],
            'tenantId': c['tenant_id'],
            'connectionId': c['connection_id'],
            'contactPhone': c['contact_phone'],
            'contactName': c['contact_name'],
            'contactAvatar': c['contact_avatar'],
            'status': c['status'],
            'assignedTo': c['assigned_to'],
            'lastMessageAt': c['last_message_at'],
            'unreadCount': c['unread_count'],
            'lastMessagePreview': c['last_message_preview'],
            'labels': c.get('labels', []),
            'createdAt': c['created_at']
        })
    
    return conversations

@api_router.patch("/conversations/{conversation_id}/status")
async def update_conversation_status(conversation_id: str, status_update: ConversationStatusUpdate, payload: dict = Depends(verify_token)):
    """Update conversation status"""
    result = supabase.table('conversations').update({'status': status_update.status}).eq('id', conversation_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    c = result.data[0]
    return {
        'id': c['id'],
        'tenantId': c['tenant_id'],
        'connectionId': c['connection_id'],
        'contactPhone': c['contact_phone'],
        'contactName': c['contact_name'],
        'status': c['status'],
        'unreadCount': c['unread_count']
    }

@api_router.post("/conversations/{conversation_id}/read")
async def mark_conversation_read(conversation_id: str, payload: dict = Depends(verify_token)):
    """Mark conversation as read"""
    result = supabase.table('conversations').update({'unread_count': 0}).eq('id', conversation_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    return {"success": True}

@api_router.post("/conversations/{conversation_id}/assign")
async def assign_conversation(conversation_id: str, data: AssignAgent, payload: dict = Depends(verify_token)):
    """Assign conversation to agent"""
    result = await AgentService.assign_conversation(conversation_id, data.agent_id)
    return {"success": True, "assignedTo": data.agent_id}

@api_router.post("/conversations/{conversation_id}/unassign")
async def unassign_conversation(conversation_id: str, payload: dict = Depends(verify_token)):
    """Unassign conversation"""
    await AgentService.unassign_conversation(conversation_id)
    return {"success": True}

@api_router.post("/conversations/{conversation_id}/labels/{label_id}")
async def add_label(conversation_id: str, label_id: str, payload: dict = Depends(verify_token)):
    """Add label to conversation"""
    await LabelsService.add_label_to_conversation(conversation_id, label_id)
    return {"success": True}

@api_router.delete("/conversations/{conversation_id}/labels/{label_id}")
async def remove_label(conversation_id: str, label_id: str, payload: dict = Depends(verify_token)):
    """Remove label from conversation"""
    await LabelsService.remove_label_from_conversation(conversation_id, label_id)
    return {"success": True}

# ==================== MESSAGES ROUTES ====================

@api_router.get("/messages")
async def list_messages(conversation_id: str, payload: dict = Depends(verify_token)):
    """List messages for a conversation"""
    result = supabase.table('messages').select('*').eq('conversation_id', conversation_id).order('timestamp', desc=False).execute()
    
    messages = []
    for m in result.data:
        messages.append({
            'id': m['id'],
            'conversationId': m['conversation_id'],
            'content': m['content'],
            'type': m['type'],
            'direction': m['direction'],
            'status': m['status'],
            'mediaUrl': m['media_url'],
            'timestamp': m['timestamp']
        })
    
    return messages

@api_router.post("/messages")
async def send_message(message: MessageCreate, background_tasks: BackgroundTasks, payload: dict = Depends(verify_token)):
    """Send a new message"""
    # Get conversation details
    conv = supabase.table('conversations').select('*, connections(*)').eq('id', message.conversation_id).execute()
    if not conv.data:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    conversation = conv.data[0]
    connection = conversation.get('connections')
    
    # Save message to database first
    data = {
        'conversation_id': message.conversation_id,
        'content': message.content,
        'type': message.type,
        'direction': 'outbound',
        'status': 'sent'
    }
    
    result = supabase.table('messages').insert(data).execute()
    
    # Update conversation
    supabase.table('conversations').update({
        'last_message_at': datetime.utcnow().isoformat(),
        'last_message_preview': message.content[:50]
    }).eq('id', message.conversation_id).execute()
    
    # Update tenant message count
    if conversation.get('tenant_id'):
        tenant = supabase.table('tenants').select('messages_this_month').eq('id', conversation['tenant_id']).execute()
        if tenant.data:
            new_count = tenant.data[0]['messages_this_month'] + 1
            supabase.table('tenants').update({'messages_this_month': new_count}).eq('id', conversation['tenant_id']).execute()
    
    # Send via WhatsApp if Evolution API connection
    if connection and connection.get('provider') == 'evolution' and connection.get('status') == 'connected':
        background_tasks.add_task(
            send_whatsapp_message,
            connection['instance_name'],
            conversation['contact_phone'],
            message.content,
            message.type,
            result.data[0]['id']
        )
    
    m = result.data[0]
    return {
        'id': m['id'],
        'conversationId': m['conversation_id'],
        'content': m['content'],
        'type': m['type'],
        'direction': m['direction'],
        'status': m['status'],
        'mediaUrl': m['media_url'],
        'timestamp': m['timestamp']
    }

async def send_whatsapp_message(instance_name: str, phone: str, content: str, msg_type: str, message_id: str):
    """Background task to send WhatsApp message"""
    try:
        if msg_type == 'text':
            await evolution_api.send_text(instance_name, phone, content)
        elif msg_type == 'image':
            await evolution_api.send_media(instance_name, phone, 'image', media_url=content)
        elif msg_type == 'audio':
            await evolution_api.send_audio(instance_name, phone, content)
        elif msg_type == 'document':
            await evolution_api.send_media(instance_name, phone, 'document', media_url=content)
        
        # Update message status to delivered
        supabase.table('messages').update({'status': 'delivered'}).eq('id', message_id).execute()
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {e}")
        supabase.table('messages').update({'status': 'failed'}).eq('id', message_id).execute()

# ==================== WHATSAPP DIRECT ROUTES ====================

@api_router.post("/whatsapp/send")
async def send_whatsapp_direct(data: SendWhatsAppMessage, payload: dict = Depends(verify_token)):
    """Send WhatsApp message directly via Evolution API"""
    try:
        if data.type == 'text':
            result = await evolution_api.send_text(data.instance_name, data.phone, data.message)
        elif data.type == 'image':
            result = await evolution_api.send_media(data.instance_name, data.phone, 'image', 
                                                     media_url=data.media_url, caption=data.message)
        elif data.type == 'audio':
            result = await evolution_api.send_audio(data.instance_name, data.phone, data.media_url or data.message)
        elif data.type == 'document':
            result = await evolution_api.send_media(data.instance_name, data.phone, 'document',
                                                     media_url=data.media_url, filename=data.message)
        else:
            result = await evolution_api.send_text(data.instance_name, data.phone, data.message)
        
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/whatsapp/typing")
async def send_typing_indicator(instance_name: str, phone: str, payload: dict = Depends(verify_token)):
    """Send typing indicator"""
    try:
        await evolution_api.send_presence(instance_name, phone, 'composing')
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== WEBHOOKS ====================

@api_router.post("/webhooks/evolution/{instance_name}")
async def evolution_webhook(instance_name: str, payload: dict):
    """Receive webhooks from Evolution API"""
    logger.info(f"Webhook received for {instance_name}: {payload.get('event')}")
    
    try:
        parsed = evolution_api.parse_webhook_message(payload)
        
        if parsed['event'] == 'message' and not parsed['from_me']:
            # Find connection by instance name
            conn = supabase.table('connections').select('*, tenants(*)').eq('instance_name', instance_name).execute()
            
            if conn.data:
                connection = conn.data[0]
                tenant_id = connection['tenant_id']
                phone = parsed['remote_jid']
                
                # Find or create conversation
                conv = supabase.table('conversations').select('*').eq('tenant_id', tenant_id).eq('contact_phone', phone).execute()
                
                if conv.data:
                    conversation = conv.data[0]
                    # Update conversation
                    supabase.table('conversations').update({
                        'last_message_at': datetime.utcnow().isoformat(),
                        'last_message_preview': (parsed['content'] or '')[:50],
                        'unread_count': conversation['unread_count'] + 1
                    }).eq('id', conversation['id']).execute()
                else:
                    # Create new conversation
                    conv_data = {
                        'tenant_id': tenant_id,
                        'connection_id': connection['id'],
                        'contact_phone': phone,
                        'contact_name': parsed.get('push_name') or phone,
                        'contact_avatar': f"https://api.dicebear.com/7.x/avataaars/svg?seed={phone}",
                        'status': 'open',
                        'unread_count': 1,
                        'last_message_preview': (parsed['content'] or '')[:50]
                    }
                    conv_result = supabase.table('conversations').insert(conv_data).execute()
                    conversation = conv_result.data[0]
                
                # Save message
                msg_data = {
                    'conversation_id': conversation['id'],
                    'content': parsed['content'] or '',
                    'type': parsed['type'],
                    'direction': 'inbound',
                    'status': 'delivered',
                    'media_url': parsed.get('media_url')
                }
                supabase.table('messages').insert(msg_data).execute()
                
                # Update tenant message count
                tenant = supabase.table('tenants').select('messages_this_month').eq('id', tenant_id).execute()
                if tenant.data:
                    supabase.table('tenants').update({
                        'messages_this_month': tenant.data[0]['messages_this_month'] + 1
                    }).eq('id', tenant_id).execute()
        
        elif parsed['event'] == 'connection':
            # Update connection status
            status = 'connected' if parsed['state'] == 'open' else 'disconnected'
            supabase.table('connections').update({'status': status}).eq('instance_name', instance_name).execute()
    
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
    
    return {"success": True}

# ==================== QUICK REPLIES & LABELS ====================

@api_router.get("/quick-replies")
async def get_quick_replies(tenant_id: str, payload: dict = Depends(verify_token)):
    """Get quick replies for tenant"""
    replies = await QuickRepliesService.get_quick_replies(tenant_id)
    return replies

@api_router.post("/quick-replies")
async def create_quick_reply(tenant_id: str, data: QuickReplyCreate, payload: dict = Depends(verify_token)):
    """Create quick reply"""
    reply = await QuickRepliesService.create_quick_reply(tenant_id, data.title, data.content, data.category)
    return reply or {"id": str(uuid.uuid4()), **data.dict()}

@api_router.delete("/quick-replies/{reply_id}")
async def delete_quick_reply(reply_id: str, payload: dict = Depends(verify_token)):
    """Delete quick reply"""
    await QuickRepliesService.delete_quick_reply(reply_id)
    return {"success": True}

@api_router.get("/labels")
async def get_labels(tenant_id: str, payload: dict = Depends(verify_token)):
    """Get labels for tenant"""
    labels = await LabelsService.get_labels(tenant_id)
    return labels

@api_router.post("/labels")
async def create_label(tenant_id: str, data: LabelCreate, payload: dict = Depends(verify_token)):
    """Create label"""
    label = await LabelsService.create_label(tenant_id, data.name, data.color)
    return label or {"id": str(uuid.uuid4()), **data.dict()}

# ==================== AGENTS ====================

@api_router.get("/agents")
async def get_agents(tenant_id: str, payload: dict = Depends(verify_token)):
    """Get agents for tenant"""
    agents = await AgentService.get_agents(tenant_id)
    return [{
        'id': a['id'],
        'name': a['name'],
        'email': a['email'],
        'role': a['role'],
        'avatar': a['avatar']
    } for a in agents]

@api_router.get("/agents/{agent_id}/stats")
async def get_agent_stats(agent_id: str, tenant_id: str, payload: dict = Depends(verify_token)):
    """Get agent statistics"""
    stats = await AgentService.get_agent_stats(tenant_id, agent_id)
    return stats

# ==================== ANALYTICS ====================

@api_router.get("/analytics/overview")
async def get_analytics_overview(tenant_id: str, payload: dict = Depends(verify_token)):
    """Get analytics overview for tenant"""
    # Get conversation stats
    conversations = supabase.table('conversations').select('status', count='exact').eq('tenant_id', tenant_id).execute()
    
    open_count = supabase.table('conversations').select('id', count='exact').eq('tenant_id', tenant_id).eq('status', 'open').execute()
    pending_count = supabase.table('conversations').select('id', count='exact').eq('tenant_id', tenant_id).eq('status', 'pending').execute()
    resolved_count = supabase.table('conversations').select('id', count='exact').eq('tenant_id', tenant_id).eq('status', 'resolved').execute()
    
    # Get message stats
    messages = supabase.table('messages').select('direction', count='exact').execute()
    
    tenant = supabase.table('tenants').select('messages_this_month').eq('id', tenant_id).execute()
    
    return {
        'conversations': {
            'total': conversations.count or 0,
            'open': open_count.count or 0,
            'pending': pending_count.count or 0,
            'resolved': resolved_count.count or 0
        },
        'messages': {
            'thisMonth': tenant.data[0]['messages_this_month'] if tenant.data else 0,
            'avgPerDay': (tenant.data[0]['messages_this_month'] // 30) if tenant.data else 0
        }
    }

# ==================== EVOLUTION API INSTANCES ====================

@api_router.get("/evolution/instances")
async def list_evolution_instances(payload: dict = Depends(verify_token)):
    """List all Evolution API instances"""
    try:
        instances = await evolution_api.fetch_instances()
        return [{
            'id': i['id'],
            'name': i['name'],
            'status': i['connectionStatus'],
            'ownerJid': i.get('ownerJid'),
            'profileName': i.get('profileName'),
            'profilePicUrl': i.get('profilePicUrl')
        } for i in instances]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/evolution/instances")
async def create_evolution_instance(name: str, payload: dict = Depends(verify_token)):
    """Create new Evolution API instance"""
    try:
        webhook_url = f"https://easy-wapp.preview.emergentagent.com/api/webhooks/evolution/{name}"
        result = await evolution_api.create_instance(name, webhook_url)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== HEALTH CHECK ====================

@api_router.get("/")
async def root():
    return {"message": "WhatsApp CRM API v2.0", "status": "healthy"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "database": "supabase", "whatsapp": "evolution-api"}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    logger.info("WhatsApp CRM API v2.0 started successfully")
