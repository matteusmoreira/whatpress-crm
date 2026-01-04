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

# Configure CORS immediately - Fix for Railway deployment
# allow_origins=["*"] fails with allow_credentials=True in some browsers/proxies
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",  # Allow all origins via regex to support credentials
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Healthcheck endpoint (required for Railway)
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "whatpress-crm"}

@app.get("/")
async def root():
    return {"message": "WhatsApp CRM API", "status": "running"}

@app.get("/debug-routes")
async def debug_routes():
    """List all registered routes to verify paths"""
    routes = []
    for route in app.routes:
        routes.append({
            "path": route.path,
            "name": route.name,
            "methods": list(route.methods) if hasattr(route, "methods") else None
        })
    return {"routes": routes}

@app.post("/test-login")
async def test_login(data: dict):
    """Direct login test endpoint outside router"""
    return {"message": "Direct login endpoint works", "received": data}

# DIRECT ROUTE FOR LOGIN (FIX FOR 405)
@app.post("/api/auth/login", response_model=LoginResponse)
async def direct_login(request: LoginRequest):
    """Direct Login path to avoid Router/Prefix issues"""
    print(f"Login attempt for: {request.email}")
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

# Create a router with the /api prefix, ensuring trailing slash handling
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

class AutoMessageCreate(BaseModel):
    type: str  # 'welcome', 'away', 'keyword'
    name: str
    message: str
    trigger_keyword: Optional[str] = None
    is_active: bool = True
    schedule_start: Optional[str] = None  # HH:MM format
    schedule_end: Optional[str] = None
    schedule_days: Optional[List[int]] = None  # 0-6, 0=Sunday
    delay_seconds: int = 0

class ChatbotFlowCreate(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_type: str  # 'keyword', 'new_conversation', 'menu_option'
    trigger_value: Optional[str] = None
    is_active: bool = True
    priority: int = 0

class ChatbotStepCreate(BaseModel):
    step_order: int
    step_type: str  # 'message', 'menu', 'wait_input', 'transfer', 'condition'
    message: Optional[str] = None
    menu_options: Optional[List[dict]] = None
    next_step_id: Optional[str] = None
    transfer_to: Optional[str] = None
    wait_timeout_seconds: int = 300

class WebhookCreate(BaseModel):
    name: str
    url: str
    secret: Optional[str] = None
    events: List[str] = []
    headers: Optional[dict] = None
    is_active: bool = True

class MessageTemplateCreate(BaseModel):
    name: str
    category: str = "general"
    content: str
    variables: Optional[List[dict]] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    is_active: bool = True

class KBCategoryCreate(BaseModel):
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    display_order: int = 0
    is_active: bool = True

class KBArticleCreate(BaseModel):
    category_id: Optional[str] = None
    title: str
    slug: Optional[str] = None
    content: str
    excerpt: Optional[str] = None
    keywords: List[str] = []
    is_published: bool = False
    is_featured: bool = False

class KBFaqCreate(BaseModel):
    category_id: Optional[str] = None
    question: str
    answer: str
    keywords: List[str] = []
    display_order: int = 0
    is_active: bool = True

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

# MOVED: Login logic moved to main app route below to fix 405 error
# @api_router.post("/auth/login", response_model=LoginResponse)
# async def login(request: LoginRequest):
#     """Login with email and password"""
#     ...

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

# ==================== MESSAGE REACTIONS ====================

@api_router.get("/messages/{message_id}/reactions")
async def get_message_reactions(message_id: str, payload: dict = Depends(verify_token)):
    """Get reactions for a message"""
    try:
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

@api_router.post("/messages/{message_id}/reactions")
async def add_message_reaction(message_id: str, emoji: str, payload: dict = Depends(verify_token)):
    """Add a reaction to a message"""
    try:
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

@api_router.delete("/messages/{message_id}/reactions/{reaction_id}")
async def remove_message_reaction(message_id: str, reaction_id: str, payload: dict = Depends(verify_token)):
    """Remove a reaction from a message"""
    try:
        supabase.table('message_reactions').delete().eq('id', reaction_id).execute()
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
        
        elif parsed['event'] == 'presence':
            # Handle typing indicator - broadcast via Supabase Realtime
            phone = parsed.get('remote_jid')
            presence = parsed.get('presence')  # 'composing', 'paused', etc.
            
            if phone and presence:
                # Find the connection and conversation
                conn = supabase.table('connections').select('tenant_id').eq('instance_name', instance_name).execute()
                if conn.data:
                    tenant_id = conn.data[0]['tenant_id']
                    conv = supabase.table('conversations').select('id').eq('tenant_id', tenant_id).eq('contact_phone', phone).execute()
                    
                    if conv.data:
                        # Insert a typing event that will be picked up by realtime subscription
                        # This is a lightweight way to broadcast typing status
                        typing_data = {
                            'conversation_id': conv.data[0]['id'],
                            'phone': phone,
                            'is_typing': presence == 'composing',
                            'timestamp': datetime.utcnow().isoformat()
                        }
                        # Use Supabase realtime broadcast via a temporary record
                        try:
                            supabase.table('typing_events').upsert(typing_data, on_conflict='conversation_id').execute()
                        except:
                            pass  # Table might not exist yet, ignore
    
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

# ==================== AUTO MESSAGES ====================

@api_router.get("/auto-messages")
async def get_auto_messages(tenant_id: str, payload: dict = Depends(verify_token)):
    """Get all auto messages for tenant"""
    try:
        result = supabase.table('auto_messages').select('*').eq('tenant_id', tenant_id).order('created_at').execute()
        return [{
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
        } for m in result.data] if result.data else []
    except Exception as e:
        logger.error(f"Error getting auto messages: {e}")
        return []

@api_router.post("/auto-messages")
async def create_auto_message(tenant_id: str, data: AutoMessageCreate, payload: dict = Depends(verify_token)):
    """Create a new auto message"""
    try:
        msg_data = {
            'tenant_id': tenant_id,
            'type': data.type,
            'name': data.name,
            'message': data.message,
            'trigger_keyword': data.trigger_keyword,
            'is_active': data.is_active,
            'schedule_start': data.schedule_start,
            'schedule_end': data.schedule_end,
            'schedule_days': data.schedule_days,
            'delay_seconds': data.delay_seconds
        }
        result = supabase.table('auto_messages').insert(msg_data).execute()
        
        if result.data:
            m = result.data[0]
            return {
                'id': m['id'],
                'type': m['type'],
                'name': m['name'],
                'message': m['message'],
                'triggerKeyword': m.get('trigger_keyword'),
                'isActive': m['is_active'],
                'createdAt': m['created_at']
            }
        
        raise HTTPException(status_code=400, detail="Erro ao criar mensagem automática")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.put("/auto-messages/{message_id}")
async def update_auto_message(message_id: str, data: AutoMessageCreate, payload: dict = Depends(verify_token)):
    """Update an auto message"""
    try:
        update_data = {
            'name': data.name,
            'message': data.message,
            'trigger_keyword': data.trigger_keyword,
            'is_active': data.is_active,
            'schedule_start': data.schedule_start,
            'schedule_end': data.schedule_end,
            'schedule_days': data.schedule_days,
            'delay_seconds': data.delay_seconds,
            'updated_at': datetime.utcnow().isoformat()
        }
        result = supabase.table('auto_messages').update(update_data).eq('id', message_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Mensagem não encontrada")
        
        return {"success": True, "id": message_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.delete("/auto-messages/{message_id}")
async def delete_auto_message(message_id: str, payload: dict = Depends(verify_token)):
    """Delete an auto message"""
    try:
        supabase.table('auto_messages').delete().eq('id', message_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.patch("/auto-messages/{message_id}/toggle")
async def toggle_auto_message(message_id: str, payload: dict = Depends(verify_token)):
    """Toggle auto message active status"""
    try:
        # Get current status
        msg = supabase.table('auto_messages').select('is_active').eq('id', message_id).execute()
        if not msg.data:
            raise HTTPException(status_code=404, detail="Mensagem não encontrada")
        
        new_status = not msg.data[0]['is_active']
        supabase.table('auto_messages').update({'is_active': new_status}).eq('id', message_id).execute()
        
        return {"success": True, "isActive": new_status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== CHATBOT FLOWS ====================

@api_router.get("/chatbot/flows")
async def get_chatbot_flows(tenant_id: str, payload: dict = Depends(verify_token)):
    """Get all chatbot flows for tenant"""
    try:
        result = supabase.table('chatbot_flows').select('*').eq('tenant_id', tenant_id).order('priority', desc=True).execute()
        flows = []
        for f in result.data or []:
            # Get steps count
            steps = supabase.table('chatbot_steps').select('id', count='exact').eq('flow_id', f['id']).execute()
            flows.append({
                'id': f['id'],
                'name': f['name'],
                'description': f.get('description'),
                'triggerType': f['trigger_type'],
                'triggerValue': f.get('trigger_value'),
                'isActive': f['is_active'],
                'priority': f['priority'],
                'stepsCount': steps.count or 0,
                'createdAt': f['created_at']
            })
        return flows
    except Exception as e:
        logger.error(f"Error getting chatbot flows: {e}")
        return []

@api_router.post("/chatbot/flows")
async def create_chatbot_flow(tenant_id: str, data: ChatbotFlowCreate, payload: dict = Depends(verify_token)):
    """Create a new chatbot flow"""
    try:
        flow_data = {
            'tenant_id': tenant_id,
            'name': data.name,
            'description': data.description,
            'trigger_type': data.trigger_type,
            'trigger_value': data.trigger_value,
            'is_active': data.is_active,
            'priority': data.priority
        }
        result = supabase.table('chatbot_flows').insert(flow_data).execute()
        
        if result.data:
            f = result.data[0]
            return {
                'id': f['id'],
                'name': f['name'],
                'triggerType': f['trigger_type'],
                'isActive': f['is_active']
            }
        raise HTTPException(status_code=400, detail="Erro ao criar fluxo")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.get("/chatbot/flows/{flow_id}")
async def get_chatbot_flow(flow_id: str, payload: dict = Depends(verify_token)):
    """Get a chatbot flow with its steps"""
    try:
        flow = supabase.table('chatbot_flows').select('*').eq('id', flow_id).execute()
        if not flow.data:
            raise HTTPException(status_code=404, detail="Fluxo não encontrado")
        
        f = flow.data[0]
        steps = supabase.table('chatbot_steps').select('*').eq('flow_id', flow_id).order('step_order').execute()
        
        return {
            'id': f['id'],
            'name': f['name'],
            'description': f.get('description'),
            'triggerType': f['trigger_type'],
            'triggerValue': f.get('trigger_value'),
            'isActive': f['is_active'],
            'priority': f['priority'],
            'steps': [{
                'id': s['id'],
                'stepOrder': s['step_order'],
                'stepType': s['step_type'],
                'message': s.get('message'),
                'menuOptions': s.get('menu_options'),
                'nextStepId': s.get('next_step_id'),
                'transferTo': s.get('transfer_to'),
                'waitTimeoutSeconds': s.get('wait_timeout_seconds', 300)
            } for s in steps.data] if steps.data else []
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.put("/chatbot/flows/{flow_id}")
async def update_chatbot_flow(flow_id: str, data: ChatbotFlowCreate, payload: dict = Depends(verify_token)):
    """Update a chatbot flow"""
    try:
        update_data = {
            'name': data.name,
            'description': data.description,
            'trigger_type': data.trigger_type,
            'trigger_value': data.trigger_value,
            'is_active': data.is_active,
            'priority': data.priority,
            'updated_at': datetime.utcnow().isoformat()
        }
        result = supabase.table('chatbot_flows').update(update_data).eq('id', flow_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Fluxo não encontrado")
        
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.delete("/chatbot/flows/{flow_id}")
async def delete_chatbot_flow(flow_id: str, payload: dict = Depends(verify_token)):
    """Delete a chatbot flow"""
    try:
        # Steps are deleted by CASCADE
        supabase.table('chatbot_flows').delete().eq('id', flow_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.patch("/chatbot/flows/{flow_id}/toggle")
async def toggle_chatbot_flow(flow_id: str, payload: dict = Depends(verify_token)):
    """Toggle chatbot flow active status"""
    try:
        flow = supabase.table('chatbot_flows').select('is_active').eq('id', flow_id).execute()
        if not flow.data:
            raise HTTPException(status_code=404, detail="Fluxo não encontrado")
        
        new_status = not flow.data[0]['is_active']
        supabase.table('chatbot_flows').update({'is_active': new_status}).eq('id', flow_id).execute()
        
        return {"success": True, "isActive": new_status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Chatbot Steps
@api_router.post("/chatbot/flows/{flow_id}/steps")
async def add_chatbot_step(flow_id: str, data: ChatbotStepCreate, payload: dict = Depends(verify_token)):
    """Add a step to a chatbot flow"""
    try:
        step_data = {
            'flow_id': flow_id,
            'step_order': data.step_order,
            'step_type': data.step_type,
            'message': data.message,
            'menu_options': data.menu_options,
            'next_step_id': data.next_step_id,
            'transfer_to': data.transfer_to,
            'wait_timeout_seconds': data.wait_timeout_seconds
        }
        result = supabase.table('chatbot_steps').insert(step_data).execute()
        
        if result.data:
            s = result.data[0]
            return {
                'id': s['id'],
                'stepOrder': s['step_order'],
                'stepType': s['step_type']
            }
        raise HTTPException(status_code=400, detail="Erro ao criar passo")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.put("/chatbot/steps/{step_id}")
async def update_chatbot_step(step_id: str, data: ChatbotStepCreate, payload: dict = Depends(verify_token)):
    """Update a chatbot step"""
    try:
        update_data = {
            'step_order': data.step_order,
            'step_type': data.step_type,
            'message': data.message,
            'menu_options': data.menu_options,
            'next_step_id': data.next_step_id,
            'transfer_to': data.transfer_to,
            'wait_timeout_seconds': data.wait_timeout_seconds
        }
        result = supabase.table('chatbot_steps').update(update_data).eq('id', step_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Passo não encontrado")
        
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.delete("/chatbot/steps/{step_id}")
async def delete_chatbot_step(step_id: str, payload: dict = Depends(verify_token)):
    """Delete a chatbot step"""
    try:
        supabase.table('chatbot_steps').delete().eq('id', step_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== WEBHOOKS ====================

@api_router.get("/webhooks")
async def get_webhooks(tenant_id: str, payload: dict = Depends(verify_token)):
    """Get all webhooks for tenant"""
    try:
        result = supabase.table('custom_webhooks').select('*').eq('tenant_id', tenant_id).order('created_at').execute()
        return [{
            'id': w['id'],
            'name': w['name'],
            'url': w['url'],
            'events': w.get('events', []),
            'isActive': w['is_active'],
            'lastTriggeredAt': w.get('last_triggered_at'),
            'lastStatus': w.get('last_status'),
            'failureCount': w.get('failure_count', 0),
            'createdAt': w['created_at']
        } for w in result.data] if result.data else []
    except Exception as e:
        logger.error(f"Error getting webhooks: {e}")
        return []

@api_router.post("/webhooks")
async def create_webhook(tenant_id: str, data: WebhookCreate, payload: dict = Depends(verify_token)):
    """Create a new webhook"""
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

@api_router.put("/webhooks/{webhook_id}")
async def update_webhook(webhook_id: str, data: WebhookCreate, payload: dict = Depends(verify_token)):
    """Update a webhook"""
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

@api_router.delete("/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str, payload: dict = Depends(verify_token)):
    """Delete a webhook"""
    try:
        supabase.table('custom_webhooks').delete().eq('id', webhook_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.patch("/webhooks/{webhook_id}/toggle")
async def toggle_webhook(webhook_id: str, payload: dict = Depends(verify_token)):
    """Toggle webhook active status"""
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

# ==================== MESSAGE TEMPLATES ====================

@api_router.get("/templates")
async def get_templates(tenant_id: str, category: str = None, payload: dict = Depends(verify_token)):
    """Get all message templates for tenant"""
    try:
        query = supabase.table('message_templates').select('*').eq('tenant_id', tenant_id)
        if category:
            query = query.eq('category', category)
        result = query.order('usage_count', desc=True).execute()
        
        return [{
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
        } for t in result.data] if result.data else []
    except Exception as e:
        logger.error(f"Error getting templates: {e}")
        return []

@api_router.post("/templates")
async def create_template(tenant_id: str, data: MessageTemplateCreate, payload: dict = Depends(verify_token)):
    """Create a new message template"""
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

@api_router.put("/templates/{template_id}")
async def update_template(template_id: str, data: MessageTemplateCreate, payload: dict = Depends(verify_token)):
    """Update a message template"""
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

@api_router.delete("/templates/{template_id}")
async def delete_template(template_id: str, payload: dict = Depends(verify_token)):
    """Delete a message template"""
    try:
        supabase.table('message_templates').delete().eq('id', template_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/templates/{template_id}/use")
async def use_template(template_id: str, payload: dict = Depends(verify_token)):
    """Increment template usage count and return content"""
    try:
        # Get template
        t = supabase.table('message_templates').select('*').eq('id', template_id).execute()
        if not t.data:
            raise HTTPException(status_code=404, detail="Template não encontrado")
        
        # Increment usage
        supabase.table('message_templates').update({
            'usage_count': (t.data[0].get('usage_count', 0) or 0) + 1
        }).eq('id', template_id).execute()
        
        return {
            'content': t.data[0]['content'],
            'variables': t.data[0].get('variables', []),
            'mediaUrl': t.data[0].get('media_url'),
            'mediaType': t.data[0].get('media_type')
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.get("/labels")
async def get_labels(tenant_id: str, payload: dict = Depends(verify_token)):
    """Get labels for tenant with usage count"""
    try:
        # Get labels from database
        result = supabase.table('labels').select('*').eq('tenant_id', tenant_id).order('created_at').execute()
        
        if result.data:
            labels = []
            for label in result.data:
                # Count conversations using this label
                count_result = supabase.table('conversations').select('id', count='exact').contains('labels', [label['id']]).execute()
                labels.append({
                    'id': label['id'],
                    'name': label['name'],
                    'color': label['color'],
                    'usageCount': count_result.count or 0,
                    'createdAt': label['created_at']
                })
            return labels
        
        # Return default labels if none exist
        return await LabelsService.get_labels(tenant_id)
    except Exception as e:
        logger.error(f"Error getting labels: {e}")
        return await LabelsService.get_labels(tenant_id)

@api_router.post("/labels")
async def create_label(tenant_id: str, data: LabelCreate, payload: dict = Depends(verify_token)):
    """Create a new label"""
    try:
        # Validate color format
        if not data.color.startswith('#') or len(data.color) != 7:
            raise HTTPException(status_code=400, detail="Cor inválida. Use formato hex: #RRGGBB")
        
        label_data = {
            'tenant_id': tenant_id,
            'name': data.name,
            'color': data.color
        }
        result = supabase.table('labels').insert(label_data).execute()
        
        if result.data:
            label = result.data[0]
            return {
                'id': label['id'],
                'name': label['name'],
                'color': label['color'],
                'usageCount': 0,
                'createdAt': label['created_at']
            }
        
        raise HTTPException(status_code=400, detail="Erro ao criar label")
    except HTTPException:
        raise
    except Exception as e:
        if 'unique' in str(e).lower():
            raise HTTPException(status_code=400, detail="Label com este nome já existe")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.put("/labels/{label_id}")
async def update_label(label_id: str, data: LabelCreate, payload: dict = Depends(verify_token)):
    """Update an existing label"""
    try:
        if not data.color.startswith('#') or len(data.color) != 7:
            raise HTTPException(status_code=400, detail="Cor inválida. Use formato hex: #RRGGBB")
        
        result = supabase.table('labels').update({
            'name': data.name,
            'color': data.color
        }).eq('id', label_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Label não encontrada")
        
        label = result.data[0]
        return {
            'id': label['id'],
            'name': label['name'],
            'color': label['color']
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.delete("/labels/{label_id}")
async def delete_label(label_id: str, payload: dict = Depends(verify_token)):
    """Delete a label and remove from all conversations"""
    try:
        # Remove label from all conversations that use it
        conversations = supabase.table('conversations').select('id, labels').contains('labels', [label_id]).execute()
        
        for conv in conversations.data or []:
            updated_labels = [l for l in (conv['labels'] or []) if l != label_id]
            supabase.table('conversations').update({'labels': updated_labels}).eq('id', conv['id']).execute()
        
        # Delete the label
        supabase.table('labels').delete().eq('id', label_id).execute()
        
        return {"success": True, "message": "Label removida com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== KNOWLEDGE BASE ====================

def slugify(text: str) -> str:
    """Convert text to URL-friendly slug"""
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text

# KB Categories
@api_router.get("/kb/categories")
async def get_kb_categories(tenant_id: str, payload: dict = Depends(verify_token)):
    """Get all KB categories"""
    try:
        result = supabase.table('kb_categories').select('*').eq('tenant_id', tenant_id).eq('is_active', True).order('display_order').execute()
        return [{
            'id': c['id'],
            'name': c['name'],
            'slug': c['slug'],
            'description': c.get('description'),
            'icon': c.get('icon'),
            'color': c.get('color'),
            'displayOrder': c['display_order']
        } for c in result.data] if result.data else []
    except Exception as e:
        logger.error(f"Error getting KB categories: {e}")
        return []

@api_router.post("/kb/categories")
async def create_kb_category(tenant_id: str, data: KBCategoryCreate, payload: dict = Depends(verify_token)):
    """Create a KB category"""
    try:
        cat_data = {
            'tenant_id': tenant_id,
            'name': data.name,
            'slug': data.slug or slugify(data.name),
            'description': data.description,
            'icon': data.icon,
            'color': data.color,
            'display_order': data.display_order,
            'is_active': data.is_active
        }
        result = supabase.table('kb_categories').insert(cat_data).execute()
        if result.data:
            return {'id': result.data[0]['id'], 'name': data.name}
        raise HTTPException(status_code=400, detail="Erro ao criar categoria")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.delete("/kb/categories/{category_id}")
async def delete_kb_category(category_id: str, payload: dict = Depends(verify_token)):
    """Delete a KB category"""
    try:
        supabase.table('kb_categories').delete().eq('id', category_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# KB Articles
@api_router.get("/kb/articles")
async def get_kb_articles(tenant_id: str, category_id: str = None, published_only: bool = True, payload: dict = Depends(verify_token)):
    """Get KB articles"""
    try:
        query = supabase.table('kb_articles').select('*, kb_categories(name, slug)').eq('tenant_id', tenant_id)
        if category_id:
            query = query.eq('category_id', category_id)
        if published_only:
            query = query.eq('is_published', True)
        result = query.order('created_at', desc=True).execute()
        
        return [{
            'id': a['id'],
            'title': a['title'],
            'slug': a['slug'],
            'excerpt': a.get('excerpt'),
            'content': a['content'],
            'category': a.get('kb_categories'),
            'keywords': a.get('keywords', []),
            'views': a.get('views', 0),
            'helpfulYes': a.get('helpful_yes', 0),
            'helpfulNo': a.get('helpful_no', 0),
            'isPublished': a['is_published'],
            'isFeatured': a.get('is_featured', False),
            'createdAt': a['created_at']
        } for a in result.data] if result.data else []
    except Exception as e:
        logger.error(f"Error getting KB articles: {e}")
        return []

@api_router.post("/kb/articles")
async def create_kb_article(tenant_id: str, data: KBArticleCreate, payload: dict = Depends(verify_token)):
    """Create a KB article"""
    try:
        article_data = {
            'tenant_id': tenant_id,
            'category_id': data.category_id,
            'title': data.title,
            'slug': data.slug or slugify(data.title),
            'content': data.content,
            'excerpt': data.excerpt or data.content[:200],
            'keywords': data.keywords,
            'is_published': data.is_published,
            'is_featured': data.is_featured,
            'author_id': payload.get('user_id'),
            'published_at': datetime.utcnow().isoformat() if data.is_published else None
        }
        result = supabase.table('kb_articles').insert(article_data).execute()
        if result.data:
            return {'id': result.data[0]['id'], 'title': data.title}
        raise HTTPException(status_code=400, detail="Erro ao criar artigo")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.put("/kb/articles/{article_id}")
async def update_kb_article(article_id: str, data: KBArticleCreate, payload: dict = Depends(verify_token)):
    """Update a KB article"""
    try:
        update_data = {
            'category_id': data.category_id,
            'title': data.title,
            'slug': data.slug or slugify(data.title),
            'content': data.content,
            'excerpt': data.excerpt or data.content[:200],
            'keywords': data.keywords,
            'is_published': data.is_published,
            'is_featured': data.is_featured,
            'updated_at': datetime.utcnow().isoformat()
        }
        if data.is_published:
            # Check if first publish
            existing = supabase.table('kb_articles').select('published_at').eq('id', article_id).execute()
            if existing.data and not existing.data[0].get('published_at'):
                update_data['published_at'] = datetime.utcnow().isoformat()
        
        supabase.table('kb_articles').update(update_data).eq('id', article_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.delete("/kb/articles/{article_id}")
async def delete_kb_article(article_id: str, payload: dict = Depends(verify_token)):
    """Delete a KB article"""
    try:
        supabase.table('kb_articles').delete().eq('id', article_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/kb/articles/{article_id}/view")
async def increment_article_view(article_id: str):
    """Increment article view count"""
    try:
        article = supabase.table('kb_articles').select('views').eq('id', article_id).execute()
        if article.data:
            supabase.table('kb_articles').update({
                'views': (article.data[0].get('views', 0) or 0) + 1
            }).eq('id', article_id).execute()
        return {"success": True}
    except Exception as e:
        return {"success": False}

@api_router.post("/kb/articles/{article_id}/feedback")
async def article_feedback(article_id: str, helpful: bool, payload: dict = Depends(verify_token)):
    """Submit article feedback"""
    try:
        article = supabase.table('kb_articles').select('helpful_yes, helpful_no').eq('id', article_id).execute()
        if article.data:
            field = 'helpful_yes' if helpful else 'helpful_no'
            supabase.table('kb_articles').update({
                field: (article.data[0].get(field, 0) or 0) + 1
            }).eq('id', article_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# KB FAQs
@api_router.get("/kb/faqs")
async def get_kb_faqs(tenant_id: str, category_id: str = None, payload: dict = Depends(verify_token)):
    """Get FAQs"""
    try:
        query = supabase.table('kb_faqs').select('*, kb_categories(name)').eq('tenant_id', tenant_id).eq('is_active', True)
        if category_id:
            query = query.eq('category_id', category_id)
        result = query.order('display_order').execute()
        
        return [{
            'id': f['id'],
            'question': f['question'],
            'answer': f['answer'],
            'category': f.get('kb_categories'),
            'keywords': f.get('keywords', []),
            'usageCount': f.get('usage_count', 0)
        } for f in result.data] if result.data else []
    except Exception as e:
        logger.error(f"Error getting FAQs: {e}")
        return []

@api_router.post("/kb/faqs")
async def create_kb_faq(tenant_id: str, data: KBFaqCreate, payload: dict = Depends(verify_token)):
    """Create a FAQ"""
    try:
        faq_data = {
            'tenant_id': tenant_id,
            'category_id': data.category_id,
            'question': data.question,
            'answer': data.answer,
            'keywords': data.keywords,
            'display_order': data.display_order,
            'is_active': data.is_active
        }
        result = supabase.table('kb_faqs').insert(faq_data).execute()
        if result.data:
            return {'id': result.data[0]['id']}
        raise HTTPException(status_code=400, detail="Erro ao criar FAQ")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.delete("/kb/faqs/{faq_id}")
async def delete_kb_faq(faq_id: str, payload: dict = Depends(verify_token)):
    """Delete a FAQ"""
    try:
        supabase.table('kb_faqs').delete().eq('id', faq_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# KB Search
@api_router.get("/kb/search")
async def search_kb(tenant_id: str, q: str, payload: dict = Depends(verify_token)):
    """Search KB articles and FAQs"""
    try:
        query_lower = q.lower()
        
        # Search articles
        articles = supabase.table('kb_articles').select('id, title, excerpt, slug').eq('tenant_id', tenant_id).eq('is_published', True).ilike('title', f'%{query_lower}%').limit(5).execute()
        
        # Search FAQs
        faqs = supabase.table('kb_faqs').select('id, question, answer').eq('tenant_id', tenant_id).eq('is_active', True).ilike('question', f'%{query_lower}%').limit(5).execute()
        
        # Log search
        supabase.table('kb_search_logs').insert({
            'tenant_id': tenant_id,
            'query': q,
            'results_count': len(articles.data or []) + len(faqs.data or []),
            'user_id': payload.get('user_id')
        }).execute()
        
        return {
            'articles': [{'id': a['id'], 'title': a['title'], 'excerpt': a.get('excerpt'), 'slug': a['slug']} for a in articles.data] if articles.data else [],
            'faqs': [{'id': f['id'], 'question': f['question'], 'answer': f['answer'][:200]} for f in faqs.data] if faqs.data else []
        }
    except Exception as e:
        logger.error(f"Error searching KB: {e}")
        return {'articles': [], 'faqs': []}

@api_router.get("/agents")
async def get_agents(tenant_id: str, payload: dict = Depends(verify_token)):
    """Get agents for tenant with status"""
    agents = await AgentService.get_agents(tenant_id)
    return [{
        'id': a['id'],
        'name': a['name'],
        'email': a['email'],
        'role': a['role'],
        'avatar': a['avatar'],
        'status': a.get('status', 'offline'),
        'lastSeen': a.get('last_seen')
    } for a in agents]

@api_router.get("/agents/{agent_id}/stats")
async def get_agent_stats(agent_id: str, tenant_id: str, payload: dict = Depends(verify_token)):
    """Get agent statistics"""
    stats = await AgentService.get_agent_stats(tenant_id, agent_id)
    return stats

@api_router.post("/agents/heartbeat")
async def agent_heartbeat(payload: dict = Depends(verify_token)):
    """Update agent online status (call periodically from frontend)"""
    user_id = payload['user_id']
    try:
        supabase.table('users').update({
            'status': 'online',
            'last_seen': datetime.utcnow().isoformat()
        }).eq('id', user_id).execute()
        return {"success": True, "status": "online"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/agents/offline")
async def agent_offline(payload: dict = Depends(verify_token)):
    """Set agent as offline"""
    user_id = payload['user_id']
    try:
        supabase.table('users').update({
            'status': 'offline',
            'last_seen': datetime.utcnow().isoformat()
        }).eq('id', user_id).execute()
        return {"success": True, "status": "offline"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.get("/conversations/{conversation_id}/assignment-history")
async def get_assignment_history(conversation_id: str, payload: dict = Depends(verify_token)):
    """Get assignment history for a conversation"""
    try:
        result = supabase.table('assignment_history').select(
            '*, assigned_to:users!assigned_to(id, name, avatar), assigned_by:users!assigned_by(id, name, avatar)'
        ).eq('conversation_id', conversation_id).order('assigned_at', desc=True).limit(10).execute()
        
        return [{
            'id': h['id'],
            'action': h['action'],
            'assignedTo': h.get('assigned_to'),
            'assignedBy': h.get('assigned_by'),
            'assignedAt': h['assigned_at'],
            'notes': h.get('notes')
        } for h in result.data] if result.data else []
    except:
        return []

@api_router.post("/conversations/{conversation_id}/assign-with-history")
async def assign_with_history(conversation_id: str, data: AssignAgent, payload: dict = Depends(verify_token)):
    """Assign conversation to agent and log history"""
    try:
        # Update conversation
        await AgentService.assign_conversation(conversation_id, data.agent_id)
        
        # Log to history
        history_data = {
            'conversation_id': conversation_id,
            'assigned_to': data.agent_id,
            'assigned_by': payload['user_id'],
            'action': 'assigned'
        }
        supabase.table('assignment_history').insert(history_data).execute()
        
        return {"success": True, "assignedTo": data.agent_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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
    
    # Get today's message count
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    today_messages = supabase.table('messages').select('id', count='exact').gte('timestamp', today).execute()
    
    # Get active agents count
    active_agents = supabase.table('users').select('id', count='exact').eq('tenant_id', tenant_id).eq('status', 'online').execute()
    
    return {
        'conversations': {
            'total': conversations.count or 0,
            'open': open_count.count or 0,
            'pending': pending_count.count or 0,
            'resolved': resolved_count.count or 0
        },
        'messages': {
            'thisMonth': tenant.data[0]['messages_this_month'] if tenant.data else 0,
            'today': today_messages.count or 0,
            'avgPerDay': (tenant.data[0]['messages_this_month'] // 30) if tenant.data else 0
        },
        'agents': {
            'online': active_agents.count or 0
        }
    }

@api_router.get("/analytics/messages-by-day")
async def get_messages_by_day(tenant_id: str, days: int = 7, payload: dict = Depends(verify_token)):
    """Get message count per day for the last N days"""
    try:
        from datetime import timedelta
        
        data = []
        for i in range(days - 1, -1, -1):
            day = datetime.utcnow() - timedelta(days=i)
            start = day.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            end = day.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()
            
            # Get inbound messages
            inbound = supabase.table('messages').select('id', count='exact').gte('timestamp', start).lte('timestamp', end).eq('direction', 'inbound').execute()
            
            # Get outbound messages
            outbound = supabase.table('messages').select('id', count='exact').gte('timestamp', start).lte('timestamp', end).eq('direction', 'outbound').execute()
            
            data.append({
                'date': day.strftime('%Y-%m-%d'),
                'day': day.strftime('%a'),
                'inbound': inbound.count or 0,
                'outbound': outbound.count or 0,
                'total': (inbound.count or 0) + (outbound.count or 0)
            })
        
        return data
    except Exception as e:
        logger.error(f"Error getting messages by day: {e}")
        return []

@api_router.get("/analytics/agent-performance")
async def get_agent_performance(tenant_id: str, payload: dict = Depends(verify_token)):
    """Get performance metrics for each agent"""
    try:
        agents = supabase.table('users').select('id, name, avatar, status').eq('tenant_id', tenant_id).in_('role', ['admin', 'agent']).execute()
        
        performance = []
        for agent in agents.data or []:
            # Get assigned conversations
            assigned = supabase.table('conversations').select('id', count='exact').eq('assigned_to', agent['id']).execute()
            
            # Get resolved conversations
            resolved = supabase.table('conversations').select('id', count='exact').eq('assigned_to', agent['id']).eq('status', 'resolved').execute()
            
            # Get messages sent by this agent (outbound)
            messages_sent = supabase.table('messages').select('id', count='exact').eq('direction', 'outbound').execute()
            
            performance.append({
                'id': agent['id'],
                'name': agent['name'],
                'avatar': agent['avatar'],
                'status': agent.get('status', 'offline'),
                'assignedConversations': assigned.count or 0,
                'resolvedConversations': resolved.count or 0,
                'resolutionRate': round((resolved.count or 0) / max(assigned.count or 1, 1) * 100, 1)
            })
        
        return performance
    except Exception as e:
        logger.error(f"Error getting agent performance: {e}")
        return []

@api_router.get("/analytics/conversations-by-status")
async def get_conversations_by_status(tenant_id: str, payload: dict = Depends(verify_token)):
    """Get conversation distribution by status"""
    try:
        statuses = ['open', 'pending', 'resolved']
        data = []
        
        for status in statuses:
            count = supabase.table('conversations').select('id', count='exact').eq('tenant_id', tenant_id).eq('status', status).execute()
            data.append({
                'status': status,
                'count': count.count or 0,
                'label': {'open': 'Abertas', 'pending': 'Pendentes', 'resolved': 'Resolvidas'}.get(status, status)
            })
        
        return data
    except Exception as e:
        logger.error(f"Error getting conversations by status: {e}")
        return []

# ==================== REPORTS EXPORT ====================

@api_router.get("/reports/conversations/csv")
async def export_conversations_csv(
    tenant_id: str, 
    status: str = None,
    date_from: str = None,
    date_to: str = None,
    payload: dict = Depends(verify_token)
):
    """Export conversations as CSV"""
    import csv
    import io
    from fastapi.responses import StreamingResponse
    
    try:
        query = supabase.table('conversations').select(
            'id, contact_name, contact_phone, status, created_at, last_message_at, unread_count, assigned_to'
        ).eq('tenant_id', tenant_id)
        
        if status:
            query = query.eq('status', status)
        if date_from:
            query = query.gte('created_at', date_from)
        if date_to:
            query = query.lte('created_at', date_to)
        
        result = query.order('last_message_at', desc=True).execute()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'ID', 'Nome do Contato', 'Telefone', 'Status', 
            'Data Criação', 'Última Mensagem', 'Não Lidas', 'Agente Atribuído'
        ])
        
        # Data
        for conv in result.data or []:
            writer.writerow([
                conv['id'],
                conv['contact_name'],
                conv['contact_phone'],
                conv['status'],
                conv['created_at'],
                conv['last_message_at'],
                conv['unread_count'],
                conv.get('assigned_to', '-')
            ])
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=conversas_{datetime.utcnow().strftime('%Y%m%d')}.csv"}
        )
    except Exception as e:
        logger.error(f"Error exporting conversations: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.get("/reports/messages/csv")
async def export_messages_csv(
    conversation_id: str,
    payload: dict = Depends(verify_token)
):
    """Export messages from a conversation as CSV"""
    import csv
    import io
    from fastapi.responses import StreamingResponse
    
    try:
        # Get conversation info
        conv = supabase.table('conversations').select('contact_name, contact_phone').eq('id', conversation_id).execute()
        contact_name = conv.data[0]['contact_name'] if conv.data else 'Contato'
        
        # Get messages
        result = supabase.table('messages').select(
            'id, content, type, direction, status, timestamp'
        ).eq('conversation_id', conversation_id).order('timestamp').execute()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['Data/Hora', 'Direção', 'Tipo', 'Conteúdo', 'Status'])
        
        # Data
        for msg in result.data or []:
            writer.writerow([
                msg['timestamp'],
                'Enviada' if msg['direction'] == 'outbound' else 'Recebida',
                msg['type'],
                msg['content'][:500] if msg['content'] else '',
                msg['status']
            ])
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=mensagens_{contact_name}_{datetime.utcnow().strftime('%Y%m%d')}.csv"}
        )
    except Exception as e:
        logger.error(f"Error exporting messages: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.get("/reports/agents/csv")
async def export_agents_report_csv(
    tenant_id: str,
    payload: dict = Depends(verify_token)
):
    """Export agent performance report as CSV"""
    import csv
    import io
    from fastapi.responses import StreamingResponse
    
    try:
        agents = supabase.table('users').select('id, name, email, role, status').eq('tenant_id', tenant_id).in_('role', ['admin', 'agent']).execute()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'Nome', 'Email', 'Papel', 'Status', 
            'Conversas Atribuídas', 'Conversas Resolvidas', 'Taxa de Resolução'
        ])
        
        # Data
        for agent in agents.data or []:
            assigned = supabase.table('conversations').select('id', count='exact').eq('assigned_to', agent['id']).execute()
            resolved = supabase.table('conversations').select('id', count='exact').eq('assigned_to', agent['id']).eq('status', 'resolved').execute()
            
            rate = round((resolved.count or 0) / max(assigned.count or 1, 1) * 100, 1)
            
            writer.writerow([
                agent['name'],
                agent['email'],
                agent['role'],
                agent.get('status', 'offline'),
                assigned.count or 0,
                resolved.count or 0,
                f"{rate}%"
            ])
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=agentes_{datetime.utcnow().strftime('%Y%m%d')}.csv"}
        )
    except Exception as e:
        logger.error(f"Error exporting agents report: {e}")
        raise HTTPException(status_code=400, detail=str(e))

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

# ==================== FILE UPLOAD ====================

class FileUploadResponse(BaseModel):
    id: str
    url: str
    name: str
    type: str
    size: int

@api_router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    conversation_id: str = Form(...),
    payload: dict = Depends(verify_token)
):
    """Upload a file and return its URL"""
    try:
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        # Validate file size (10MB max)
        max_size = 10 * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(status_code=400, detail="Arquivo muito grande. Máximo: 10MB")
        
        # Generate unique filename
        file_ext = file.filename.split('.')[-1] if '.' in file.filename else 'bin'
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        
        # Determine file type
        content_type = file.content_type or 'application/octet-stream'
        if content_type.startswith('image/'):
            file_type = 'image'
            folder = 'images'
        elif content_type.startswith('video/'):
            file_type = 'video'
            folder = 'videos'
        elif content_type.startswith('audio/'):
            file_type = 'audio'
            folder = 'audios'
        else:
            file_type = 'document'
            folder = 'documents'
        
        # Upload to Supabase Storage
        storage_path = f"{folder}/{unique_filename}"
        
        try:
            # Try to upload to Supabase Storage
            result = supabase.storage.from_('uploads').upload(
                storage_path,
                content,
                file_options={"content-type": content_type}
            )
            
            # Get public URL
            public_url = supabase.storage.from_('uploads').get_public_url(storage_path)
            
        except Exception as storage_error:
            logger.warning(f"Supabase storage error: {storage_error}")
            # Fallback: encode as base64 and store in database or return as data URL
            encoded = base64.b64encode(content).decode('utf-8')
            public_url = f"data:{content_type};base64,{encoded}"
        
        return {
            "id": str(uuid.uuid4()),
            "url": public_url,
            "name": file.filename,
            "type": file_type,
            "size": file_size
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao fazer upload: {str(e)}")

@api_router.post("/messages/media")
async def send_media_message(
    conversation_id: str = Form(...),
    content: str = Form(default=""),
    media_type: str = Form(...),
    media_url: str = Form(...),
    media_name: str = Form(default="file"),
    background_tasks: BackgroundTasks = None,
    payload: dict = Depends(verify_token)
):
    """Send a media message (image, video, audio, document)"""
    # Get conversation details
    conv = supabase.table('conversations').select('*, connections(*)').eq('id', conversation_id).execute()
    if not conv.data:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    conversation = conv.data[0]
    connection = conversation.get('connections')
    
    # Create message content
    message_content = content if content else f"📎 {media_name}"
    
    # Save message to database
    data = {
        'conversation_id': conversation_id,
        'content': message_content,
        'type': media_type,
        'direction': 'outbound',
        'status': 'sent',
        'media_url': media_url
    }
    
    result = supabase.table('messages').insert(data).execute()
    
    # Update conversation
    supabase.table('conversations').update({
        'last_message_at': datetime.utcnow().isoformat(),
        'last_message_preview': message_content[:50]
    }).eq('id', conversation_id).execute()
    
    # Update tenant message count
    if conversation.get('tenant_id'):
        tenant = supabase.table('tenants').select('messages_this_month').eq('id', conversation['tenant_id']).execute()
        if tenant.data:
            new_count = tenant.data[0]['messages_this_month'] + 1
            supabase.table('tenants').update({'messages_this_month': new_count}).eq('id', conversation['tenant_id']).execute()
    
    # Send via WhatsApp if Evolution API connection
    if connection and connection.get('provider') == 'evolution' and connection.get('status') == 'connected':
        if background_tasks:
            background_tasks.add_task(
                send_whatsapp_media,
                connection['instance_name'],
                conversation['contact_phone'],
                media_type,
                media_url,
                content,
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

async def send_whatsapp_media(instance_name: str, phone: str, media_type: str, media_url: str, caption: str, message_id: str):
    """Background task to send WhatsApp media"""
    try:
        await evolution_api.send_media(
            instance_name, 
            phone, 
            media_type,
            media_url=media_url,
            caption=caption
        )
        supabase.table('messages').update({'status': 'delivered'}).eq('id', message_id).execute()
    except Exception as e:
        logger.error(f"Failed to send WhatsApp media: {e}")
        supabase.table('messages').update({'status': 'failed'}).eq('id', message_id).execute()

# Include the router in the main app
app.include_router(api_router)



@app.on_event("startup")
async def startup_event():
    logger.info("WhatsApp CRM API v2.0 started successfully")
