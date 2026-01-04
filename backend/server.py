from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime
from supabase_client import supabase
import jwt

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

# ==================== AUTH ROUTES ====================

@api_router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login with email and password"""
    result = supabase.table('users').select('*').eq('email', request.email).eq('password_hash', request.password).execute()
    
    if not result.data:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    
    user = result.data[0]
    token = create_token(user['id'], user['email'], user['role'])
    
    # Remove password from response
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
    
    # Convert snake_case to camelCase
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
    """Test a connection (simulated)"""
    import random
    
    # Simulate connection test
    success = random.random() > 0.3
    
    if not success:
        raise HTTPException(status_code=400, detail="Falha ao conectar. Verifique as credenciais.")
    
    # Update status to connected
    conn = supabase.table('connections').select('*').eq('id', connection_id).execute()
    if conn.data:
        webhook_url = f"https://api.whatsappcrm.com/webhooks/{conn.data[0]['instance_name']}"
        supabase.table('connections').update({'status': 'connected', 'webhook_url': webhook_url}).eq('id', connection_id).execute()
    
    return {"success": True, "message": "Conexão estabelecida com sucesso!"}

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
    # Get connection to update tenant count
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
async def send_message(message: MessageCreate, payload: dict = Depends(verify_token)):
    """Send a new message"""
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
    conv = supabase.table('conversations').select('tenant_id').eq('id', message.conversation_id).execute()
    if conv.data:
        tenant = supabase.table('tenants').select('messages_this_month').eq('id', conv.data[0]['tenant_id']).execute()
        if tenant.data:
            new_count = tenant.data[0]['messages_this_month'] + 1
            supabase.table('tenants').update({'messages_this_month': new_count}).eq('id', conv.data[0]['tenant_id']).execute()
    
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

# ==================== HEALTH CHECK ====================

@api_router.get("/")
async def root():
    return {"message": "WhatsApp CRM API v1.0", "status": "healthy"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "database": "supabase"}

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
    logger.info("WhatsApp CRM API started successfully")
