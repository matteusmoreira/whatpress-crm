from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta
from supabase_client import supabase
from evolution_api import evolution_api, EvolutionAPI
from media_detection import detect_media_kind
from features import QuickRepliesService, LabelsService, AgentService, DEFAULT_QUICK_REPLIES, DEFAULT_LABELS
import jwt
import json
import base64
import asyncio
import re

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Create the main app
app = FastAPI(title="WhatsApp CRM API")

# Configure CORS immediately - Fix for Railway deployment
# allow_origins=["*"] fails with allow_credentials=True in some browsers/proxies
def resolve_cors_allow_origins() -> List[str]:
    raw = (os.getenv("CORS_ALLOW_ORIGINS") or "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "https://whatpress-crm.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


CORS_ALLOW_ORIGINS = resolve_cors_allow_origins()
CORS_ALLOW_ORIGIN_REGEX = os.getenv(
    "CORS_ALLOW_ORIGIN_REGEX", r"^https://(.*\.)?whatpress-crm(-.*)?\.vercel\.app$"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_origin_regex=CORS_ALLOW_ORIGIN_REGEX,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
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

@app.on_event("startup")
async def ensure_auto_messages_schema():
    sql = """
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

    CREATE TABLE IF NOT EXISTS auto_messages (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        type VARCHAR(50) NOT NULL CHECK (type IN ('welcome', 'away', 'keyword')),
        name VARCHAR(255) NOT NULL,
        message TEXT NOT NULL,
        trigger_keyword VARCHAR(255),
        is_active BOOLEAN DEFAULT true,
        schedule_start VARCHAR(10),
        schedule_end VARCHAR(10),
        schedule_days JSONB,
        delay_seconds INTEGER DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS auto_message_logs (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
        auto_message_id UUID NOT NULL REFERENCES auto_messages(id) ON DELETE CASCADE,
        conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        sent_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_auto_messages_tenant ON auto_messages(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_auto_messages_active ON auto_messages(is_active);
    CREATE INDEX IF NOT EXISTS idx_auto_message_logs_auto_message ON auto_message_logs(auto_message_id);
    CREATE INDEX IF NOT EXISTS idx_auto_message_logs_conversation ON auto_message_logs(conversation_id);

    ALTER TABLE auto_messages ENABLE ROW LEVEL SECURITY;
    ALTER TABLE auto_message_logs ENABLE ROW LEVEL SECURITY;

    CREATE POLICY IF NOT EXISTS "Service role has full access to auto_messages" ON auto_messages FOR ALL USING (true);
    CREATE POLICY IF NOT EXISTS "Service role has full access to auto_message_logs" ON auto_message_logs FOR ALL USING (true);

    CREATE TABLE IF NOT EXISTS contacts (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        name VARCHAR(255),
        full_name VARCHAR(255),
        phone VARCHAR(50) NOT NULL,
        email VARCHAR(255),
        tags JSONB DEFAULT '[]',
        custom_fields JSONB DEFAULT '{}',
        social_links JSONB DEFAULT '{}',
        notes_html TEXT DEFAULT '',
        source VARCHAR(50) DEFAULT 'manual',
        status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'unverified', 'verified')),
        first_contact_at TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    ALTER TABLE contacts ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'pending';
    ALTER TABLE contacts ADD COLUMN IF NOT EXISTS first_contact_at TIMESTAMP WITH TIME ZONE;
    ALTER TABLE contacts ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '[]';
    ALTER TABLE contacts ADD COLUMN IF NOT EXISTS custom_fields JSONB DEFAULT '{}';
    ALTER TABLE contacts ADD COLUMN IF NOT EXISTS social_links JSONB DEFAULT '{}';
    ALTER TABLE contacts ADD COLUMN IF NOT EXISTS notes_html TEXT DEFAULT '';
    ALTER TABLE contacts ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'manual';

    CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_tenant_phone_unique ON contacts(tenant_id, phone);
    CREATE INDEX IF NOT EXISTS idx_contacts_tenant ON contacts(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone);

    ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;
    CREATE POLICY IF NOT EXISTS "Service role has full access to contacts" ON contacts FOR ALL USING (true);
    """
    try:
        supabase.rpc('exec_sql', {'sql': sql}).execute()
    except Exception:
        return

# ==================== MODELS (defined early for login endpoint) ====================

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    user: dict
    token: str

# JWT Secret (needed for login)
JWT_SECRET = "whatsapp-crm-secret-key-2025"

def create_token(user_id: str, email: str, role: str):
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "exp": datetime.utcnow().timestamp() + 86400 * 7  # 7 days
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def resolve_public_base_url(request: Optional[Request] = None) -> str:
    configured = (
        os.getenv("PUBLIC_BASE_URL")
        or os.getenv("BACKEND_PUBLIC_URL")
        or os.getenv("WEBHOOK_BASE_URL")
        or os.getenv("APP_BASE_URL")
        or ""
    ).strip()
    if configured:
        return configured.rstrip("/")

    if request is not None:
        proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "http").strip()
        host = (
            request.headers.get("x-forwarded-host")
            or request.headers.get("host")
            or request.url.netloc
            or ""
        ).strip()
        if host:
            return f"{proto}://{host}".rstrip("/")

    return "https://whatpress-crm-production.up.railway.app"

def extract_profile_picture_url(data: Any) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    for key in [
        "profilePictureUrl",
        "profilePicUrl",
        "pictureUrl",
        "avatarUrl",
        "url",
        "profile_picture_url",
        "profile_pic_url",
    ]:
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    for container_key in ["data", "result", "response"]:
        container = data.get(container_key)
        if isinstance(container, dict):
            nested = extract_profile_picture_url(container)
            if nested:
                return nested
    return None

def normalize_phone_number(value: Any) -> str:
    s = str(value or '').strip()
    if not s:
        return ''
    digits = ''.join(ch for ch in s if ch.isdigit())
    if not digits:
        return ''
    if len(digits) > 10:
        digits = digits.lstrip('0')
    if digits.startswith('00'):
        digits = digits[2:]
        digits = digits.lstrip('0')
    if digits.startswith('55'):
        return digits
    if len(digits) == 11 and digits[0] in ('1', '7'):
        return digits
    if len(digits) == 10:
        return f"55{digits}"
    if len(digits) == 11:
        return f"55{digits}"
    return digits

@app.post("/test-login")
async def test_login(data: dict):
    """Direct login test endpoint outside router"""
    return {"message": "Direct login endpoint works", "received": data}

# OPTIONS handler for CORS preflight
@app.options("/api/auth/login")
async def login_options():
    return {"message": "OK"}

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
        'jobTitle': user.get('job_title'),
        'department': user.get('department'),
        'signatureEnabled': user.get('signature_enabled', True),
        'signatureIncludeTitle': user.get('signature_include_title', False),
        'signatureIncludeDepartment': user.get('signature_include_department', False),
        'createdAt': user['created_at']
    }
    
    return {"user": user_response, "token": token}

# Create a router with the /api prefix, ensuring trailing slash handling
api_router = APIRouter(prefix="/api")

# Security
security = HTTPBearer(auto_error=False)
# JWT_SECRET already defined above

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== MODELS ====================
# Note: LoginRequest and LoginResponse are defined at the top of the file

class TenantCreate(BaseModel):
    name: str
    slug: str
    plan_id: Optional[str] = None

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    status: Optional[str] = None
    plan: Optional[str] = None
    plan_id: Optional[str] = None

# ==================== PLANS MODELS ====================

class PlanCreate(BaseModel):
    name: str
    slug: str
    price: float = 0
    max_instances: int = 1
    max_messages_month: int = 1000
    max_users: int = 1
    features: Optional[dict] = {}
    is_active: bool = True

class PlanUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    price: Optional[float] = None
    max_instances: Optional[int] = None
    max_messages_month: Optional[int] = None
    max_users: Optional[int] = None
    features: Optional[dict] = None
    is_active: Optional[bool] = None

# ==================== USERS MODELS (SuperAdmin) ====================

class UserCreate(BaseModel):
    email: str
    password: str
    name: str
    role: str = "agent"  # superadmin, admin, agent
    tenant_id: Optional[str] = None
    avatar: Optional[str] = None

class UserUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    tenant_id: Optional[str] = None
    avatar: Optional[str] = None

class ConnectionCreate(BaseModel):
    tenant_id: str
    provider: str
    instance_name: str
    phone_number: Optional[str] = ""

class ConnectionStatusUpdate(BaseModel):
    status: str

class ConversationStatusUpdate(BaseModel):
    status: str

class InitiateConversation(BaseModel):
    phone: str
    contact_id: Optional[str] = None

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

class ConversationTransferCreate(BaseModel):
    to_agent_id: str
    reason: Optional[str] = None

class UserProfileUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    job_title: Optional[str] = Field(default=None, alias="jobTitle")
    department: Optional[str] = None
    signature_enabled: Optional[bool] = Field(default=None, alias="signatureEnabled")
    signature_include_title: Optional[bool] = Field(default=None, alias="signatureIncludeTitle")
    signature_include_department: Optional[bool] = Field(default=None, alias="signatureIncludeDepartment")

class ContactUpsertByPhone(BaseModel):
    tenant_id: str
    phone: str
    full_name: Optional[str] = None
    avatar: Optional[str] = None

class ContactUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    tags: Optional[List[str]] = None
    custom_fields: Optional[dict] = None
    social_links: Optional[dict] = None
    notes_html: Optional[str] = None
    status: Optional[str] = None

class ContactCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    tags: Optional[List[str]] = None
    custom_fields: Optional[dict] = None
    source: Optional[str] = None
    status: Optional[str] = None

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
# Note: create_token is defined at the top of the file

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

def safe_insert_audit_log(
    tenant_id: Optional[str],
    actor_user_id: Optional[str],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    metadata: Optional[dict] = None
):
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
        return

def build_user_signature_prefix(user_row: dict) -> str:
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
        'avatar': user['avatar'],
        'phone': user.get('phone'),
        'bio': user.get('bio'),
        'jobTitle': user.get('job_title'),
        'department': user.get('department'),
        'signatureEnabled': user.get('signature_enabled', True),
        'signatureIncludeTitle': user.get('signature_include_title', False),
        'signatureIncludeDepartment': user.get('signature_include_department', False),
        'createdAt': user.get('created_at'),
    }

@api_router.patch("/auth/me")
async def update_current_user_profile(data: UserProfileUpdate, payload: dict = Depends(verify_token)):
    user_id = payload['user_id']
    update_data: Dict[str, Any] = {}
    if data.name is not None:
        update_data['name'] = (data.name or '').strip()
    if data.email is not None:
        email = (str(data.email) or '').strip().lower()
        if not email:
            raise HTTPException(status_code=400, detail="Email é obrigatório")
        existing = supabase.table('users').select('id').eq('email', email).neq('id', user_id).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail="Email já está em uso")
        update_data['email'] = email
    if data.phone is not None:
        phone = (data.phone or '').strip()
        update_data['phone'] = phone or None
    if data.bio is not None:
        bio = (data.bio or '').strip()
        update_data['bio'] = bio or None
    if data.job_title is not None:
        update_data['job_title'] = (data.job_title or '').strip()
    if data.department is not None:
        update_data['department'] = (data.department or '').strip()
    if data.signature_enabled is not None:
        update_data['signature_enabled'] = data.signature_enabled
    if data.signature_include_title is not None:
        update_data['signature_include_title'] = data.signature_include_title
    if data.signature_include_department is not None:
        update_data['signature_include_department'] = data.signature_include_department

    if not update_data:
        result = supabase.table('users').select('*').eq('id', user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        u = result.data[0]
        return {
            'id': u['id'],
            'email': u['email'],
            'name': u['name'],
            'role': u['role'],
            'tenantId': u['tenant_id'],
            'avatar': u['avatar'],
            'phone': u.get('phone'),
            'bio': u.get('bio'),
            'jobTitle': u.get('job_title'),
            'department': u.get('department'),
            'signatureEnabled': u.get('signature_enabled', True),
            'signatureIncludeTitle': u.get('signature_include_title', False),
            'signatureIncludeDepartment': u.get('signature_include_department', False),
            'createdAt': u.get('created_at'),
        }

    try:
        result = supabase.table('users').update(update_data).eq('id', user_id).execute()
    except Exception as e:
        msg = str(e) or ""
        lowered = msg.lower()
        if "column" in lowered or "does not exist" in lowered:
            raise HTTPException(
                status_code=400,
                detail="Banco de dados sem colunas de perfil. Aplique a migração 009_contacts_transfer_signature_audit.sql.",
            )
        raise HTTPException(status_code=400, detail="Erro ao salvar perfil.")
    if not result.data:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    u = result.data[0]
    return {
        'id': u['id'],
        'email': u['email'],
        'name': u['name'],
        'role': u['role'],
        'tenantId': u['tenant_id'],
        'avatar': u['avatar'],
        'phone': u.get('phone'),
        'bio': u.get('bio'),
        'jobTitle': u.get('job_title'),
        'department': u.get('department'),
        'signatureEnabled': u.get('signature_enabled', True),
        'signatureIncludeTitle': u.get('signature_include_title', False),
        'signatureIncludeDepartment': u.get('signature_include_department', False),
        'createdAt': u.get('created_at'),
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
    
    # Add plan_id if provided
    if tenant.plan_id:
        data['plan_id'] = tenant.plan_id
        # Get plan slug for the legacy 'plan' field
        plan = supabase.table('plans').select('slug').eq('id', tenant.plan_id).execute()
        if plan.data:
            data['plan'] = plan.data[0]['slug']
    
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
        'planId': t.get('plan_id'),
        'messagesThisMonth': t['messages_this_month'],
        'connectionsCount': t['connections_count'],
        'createdAt': t['created_at'],
        'updatedAt': t['updated_at']
    }

@api_router.get("/tenants/{tenant_id}")
async def get_tenant(tenant_id: str, payload: dict = Depends(verify_token)):
    """Get a single tenant by ID"""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    result = supabase.table('tenants').select('*, plans(*)').eq('id', tenant_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    
    t = result.data[0]
    return {
        'id': t['id'],
        'name': t['name'],
        'slug': t['slug'],
        'status': t['status'],
        'plan': t['plan'],
        'planId': t.get('plan_id'),
        'planData': t.get('plans'),
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
    
    # If plan_id is provided, also update the legacy 'plan' field
    if 'plan_id' in data and data['plan_id']:
        plan = supabase.table('plans').select('slug').eq('id', data['plan_id']).execute()
        if plan.data:
            data['plan'] = plan.data[0]['slug']
    
    result = supabase.table('tenants').update(data).eq('id', tenant_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    
    t = result.data[0]
    return {
        'id': t['id'],
        'name': t['name'],
        'slug': t['slug'],
        'status': t['status'],
        'plan': t['plan'],
        'planId': t.get('plan_id'),
        'messagesThisMonth': t['messages_this_month'],
        'connectionsCount': t['connections_count'],
        'createdAt': t['created_at'],
        'updatedAt': t['updated_at']
    }

@api_router.delete("/tenants/{tenant_id}")
async def delete_tenant(tenant_id: str, payload: dict = Depends(verify_token)):
    """Delete a tenant"""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    supabase.table('tenants').delete().eq('id', tenant_id).execute()
    return {"success": True}

# ==================== PLANS ROUTES (SuperAdmin) ====================

@api_router.get("/plans")
async def list_plans(payload: dict = Depends(verify_token)):
    """List all plans"""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    result = supabase.table('plans').select('*').order('price', desc=False).execute()
    
    plans = []
    for p in result.data:
        plans.append({
            'id': p['id'],
            'name': p['name'],
            'slug': p['slug'],
            'price': float(p['price']) if p['price'] else 0,
            'maxInstances': p['max_instances'],
            'maxMessagesMonth': p['max_messages_month'],
            'maxUsers': p['max_users'],
            'features': p['features'],
            'isActive': p['is_active'],
            'createdAt': p['created_at']
        })
    
    return plans

@api_router.get("/plans/{plan_id}")
async def get_plan(plan_id: str, payload: dict = Depends(verify_token)):
    """Get a single plan by ID"""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    result = supabase.table('plans').select('*').eq('id', plan_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    
    p = result.data[0]
    return {
        'id': p['id'],
        'name': p['name'],
        'slug': p['slug'],
        'price': float(p['price']) if p['price'] else 0,
        'maxInstances': p['max_instances'],
        'maxMessagesMonth': p['max_messages_month'],
        'maxUsers': p['max_users'],
        'features': p['features'],
        'isActive': p['is_active'],
        'createdAt': p['created_at']
    }

@api_router.post("/plans")
async def create_plan(plan: PlanCreate, payload: dict = Depends(verify_token)):
    """Create a new plan"""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    data = {
        'name': plan.name,
        'slug': plan.slug,
        'price': plan.price,
        'max_instances': plan.max_instances,
        'max_messages_month': plan.max_messages_month,
        'max_users': plan.max_users,
        'features': plan.features or {},
        'is_active': plan.is_active
    }
    
    result = supabase.table('plans').insert(data).execute()
    
    if not result.data:
        raise HTTPException(status_code=400, detail="Erro ao criar plano")
    
    p = result.data[0]
    return {
        'id': p['id'],
        'name': p['name'],
        'slug': p['slug'],
        'price': float(p['price']) if p['price'] else 0,
        'maxInstances': p['max_instances'],
        'maxMessagesMonth': p['max_messages_month'],
        'maxUsers': p['max_users'],
        'features': p['features'],
        'isActive': p['is_active'],
        'createdAt': p['created_at']
    }

@api_router.put("/plans/{plan_id}")
async def update_plan(plan_id: str, plan: PlanUpdate, payload: dict = Depends(verify_token)):
    """Update a plan"""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    # Map frontend field names to database field names
    data = {}
    if plan.name is not None:
        data['name'] = plan.name
    if plan.slug is not None:
        data['slug'] = plan.slug
    if plan.price is not None:
        data['price'] = plan.price
    if plan.max_instances is not None:
        data['max_instances'] = plan.max_instances
    if plan.max_messages_month is not None:
        data['max_messages_month'] = plan.max_messages_month
    if plan.max_users is not None:
        data['max_users'] = plan.max_users
    if plan.features is not None:
        data['features'] = plan.features
    if plan.is_active is not None:
        data['is_active'] = plan.is_active
    
    data['updated_at'] = datetime.utcnow().isoformat()
    
    result = supabase.table('plans').update(data).eq('id', plan_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    
    p = result.data[0]
    return {
        'id': p['id'],
        'name': p['name'],
        'slug': p['slug'],
        'price': float(p['price']) if p['price'] else 0,
        'maxInstances': p['max_instances'],
        'maxMessagesMonth': p['max_messages_month'],
        'maxUsers': p['max_users'],
        'features': p['features'],
        'isActive': p['is_active'],
        'createdAt': p['created_at']
    }

@api_router.delete("/plans/{plan_id}")
async def delete_plan(plan_id: str, payload: dict = Depends(verify_token)):
    """Delete a plan"""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    # Check if any tenant is using this plan
    tenants = supabase.table('tenants').select('id').eq('plan_id', plan_id).execute()
    if tenants.data:
        raise HTTPException(status_code=400, detail="Não é possível excluir plano em uso por tenants")
    
    supabase.table('plans').delete().eq('id', plan_id).execute()
    return {"success": True}

# ==================== USERS ROUTES (SuperAdmin) ====================

@api_router.get("/users")
async def list_users(tenant_id: Optional[str] = None, role: Optional[str] = None, payload: dict = Depends(verify_token)):
    """List all users (SuperAdmin) or users from a tenant"""
    if payload['role'] != 'superadmin':
        # Non-superadmin can only list users from their own tenant
        user_tenant = get_user_tenant_id(payload)
        if not user_tenant:
            raise HTTPException(status_code=403, detail="Acesso negado")
        tenant_id = user_tenant
    
    query = supabase.table('users').select('*, tenants(name, slug)')
    
    if tenant_id:
        query = query.eq('tenant_id', tenant_id)
    if role:
        query = query.eq('role', role)
    
    result = query.order('created_at', desc=True).execute()
    
    users = []
    for u in result.data:
        users.append({
            'id': u['id'],
            'email': u['email'],
            'name': u['name'],
            'role': u['role'],
            'tenantId': u['tenant_id'],
            'tenantName': u.get('tenants', {}).get('name') if u.get('tenants') else None,
            'avatar': u['avatar'],
            'createdAt': u['created_at']
        })
    
    return users

@api_router.get("/users/{user_id}")
async def get_user(user_id: str, payload: dict = Depends(verify_token)):
    """Get a single user by ID"""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    result = supabase.table('users').select('*, tenants(name, slug)').eq('id', user_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    u = result.data[0]
    return {
        'id': u['id'],
        'email': u['email'],
        'name': u['name'],
        'role': u['role'],
        'tenantId': u['tenant_id'],
        'tenantName': u.get('tenants', {}).get('name') if u.get('tenants') else None,
        'avatar': u['avatar'],
        'createdAt': u['created_at']
    }

@api_router.post("/users")
async def create_user(user: UserCreate, payload: dict = Depends(verify_token)):
    """Create a new user (SuperAdmin only)"""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    # Check if email already exists
    existing = supabase.table('users').select('id').eq('email', user.email).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Email já está em uso")
    
    data = {
        'email': user.email,
        'password_hash': user.password,  # In production, hash this!
        'name': user.name,
        'role': user.role,
        'tenant_id': user.tenant_id,
        'avatar': user.avatar or f"https://api.dicebear.com/7.x/avataaars/svg?seed={user.email}"
    }
    
    result = supabase.table('users').insert(data).execute()
    
    if not result.data:
        raise HTTPException(status_code=400, detail="Erro ao criar usuário")
    
    u = result.data[0]
    return {
        'id': u['id'],
        'email': u['email'],
        'name': u['name'],
        'role': u['role'],
        'tenantId': u['tenant_id'],
        'avatar': u['avatar'],
        'createdAt': u['created_at']
    }

@api_router.put("/users/{user_id}")
async def update_user(user_id: str, user: UserUpdate, payload: dict = Depends(verify_token)):
    """Update a user (SuperAdmin only)"""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    data = {}
    if user.email is not None:
        # Check if new email already exists
        existing = supabase.table('users').select('id').eq('email', user.email).neq('id', user_id).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail="Email já está em uso")
        data['email'] = user.email
    if user.password is not None:
        data['password_hash'] = user.password  # In production, hash this!
    if user.name is not None:
        data['name'] = user.name
    if user.role is not None:
        data['role'] = user.role
    if user.tenant_id is not None:
        data['tenant_id'] = user.tenant_id if user.tenant_id != '' else None
    if user.avatar is not None:
        data['avatar'] = user.avatar
    
    result = supabase.table('users').update(data).eq('id', user_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    u = result.data[0]
    return {
        'id': u['id'],
        'email': u['email'],
        'name': u['name'],
        'role': u['role'],
        'tenantId': u['tenant_id'],
        'avatar': u['avatar'],
        'createdAt': u['created_at']
    }

@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, payload: dict = Depends(verify_token)):
    """Delete a user (SuperAdmin only)"""
    if payload['role'] != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    # Prevent deleting yourself
    if user_id == payload['user_id']:
        raise HTTPException(status_code=400, detail="Você não pode excluir seu próprio usuário")
    
    supabase.table('users').delete().eq('id', user_id).execute()
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
        'phone_number': connection.phone_number or '',
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
async def test_connection(connection_id: str, request: Request, payload: dict = Depends(verify_token)):
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
                webhook_url = f"{resolve_public_base_url(request)}/api/webhooks/evolution/{connection['instance_name']}"
                try:
                    await evolution_api.set_webhook(connection['instance_name'], webhook_url)
                except Exception as e:
                    logger.warning(f"Could not set webhook for {connection['instance_name']}: {e}")
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
                webhook_url = f"{resolve_public_base_url(request)}/api/webhooks/evolution/{connection['instance_name']}"
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

@api_router.post("/connections/{connection_id}/sync")
async def sync_connection_status(connection_id: str, request: Request, payload: dict = Depends(verify_token)):
    """Sincronizar status da conexão com a Evolution API"""
    conn = supabase.table('connections').select('*').eq('id', connection_id).execute()
    if not conn.data:
        raise HTTPException(status_code=404, detail="Conexão não encontrada")
    
    connection = conn.data[0]
    
    if connection['provider'] != 'evolution':
        raise HTTPException(status_code=400, detail="Sincronização disponível apenas para Evolution API")
    
    try:
        # Verificar estado atual na Evolution API
        state = await evolution_api.get_connection_state(connection['instance_name'])
        logger.info(f"Evolution API state for {connection['instance_name']}: {state}")
        
        # Determinar se está conectado
        instance_state = state.get('instance', {}).get('state', '')
        is_connected = instance_state.lower() in ['open', 'connected']
        
        new_status = 'connected' if is_connected else 'disconnected'
        
        # Atualizar banco de dados
        update_data = {'status': new_status}
        if is_connected:
            update_data['webhook_url'] = f"{resolve_public_base_url(request)}/api/webhooks/evolution/{connection['instance_name']}"
            try:
                await evolution_api.set_webhook(connection['instance_name'], update_data['webhook_url'])
            except Exception as e:
                logger.warning(f"Could not set webhook for {connection['instance_name']}: {e}")
            
            # Tentar obter o número do telefone se conectado
            try:
                instances = await evolution_api.fetch_instances()
                for inst in instances:
                    if inst.get('name') == connection['instance_name']:
                        owner_jid = inst.get('owner', inst.get('ownerJid', ''))
                        if owner_jid:
                            # Extrair número do JID (formato: 5521999998888@s.whatsapp.net)
                            phone_number = owner_jid.split('@')[0] if '@' in owner_jid else owner_jid
                            if phone_number:
                                update_data['phone_number'] = phone_number
                        break
            except Exception as e:
                logger.warning(f"Could not get phone number: {e}")
        
        result = supabase.table('connections').update(update_data).eq('id', connection_id).execute()
        
        c = result.data[0] if result.data else connection
        return {
            'id': c['id'],
            'status': new_status,
            'instanceState': instance_state,
            'phoneNumber': c.get('phone_number'),
            'message': f"Status atualizado para: {new_status}"
        }
        
    except Exception as e:
        logger.error(f"Error syncing connection status: {e}")
        raise HTTPException(status_code=400, detail=f"Erro ao sincronizar: {str(e)}")

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
    """Delete a connection and its instance from Evolution API"""
    conn = supabase.table('connections').select('*').eq('id', connection_id).execute()
    
    if not conn.data:
        raise HTTPException(status_code=404, detail="Conexão não encontrada")
    
    connection = conn.data[0]
    tenant_id = connection['tenant_id']
    
    # Deletar instância na Evolution API se for provider evolution
    if connection['provider'] == 'evolution' and connection.get('instance_name'):
        try:
            await evolution_api.delete_instance(connection['instance_name'])
            logger.info(f"Evolution instance {connection['instance_name']} deleted")
        except Exception as e:
            logger.warning(f"Could not delete Evolution instance: {e}")
            # Continua mesmo se falhar a exclusão na Evolution API
    
    # Atualizar contador do tenant
    tenant = supabase.table('tenants').select('connections_count').eq('id', tenant_id).execute()
    if tenant.data and tenant.data[0]['connections_count'] > 0:
        new_count = tenant.data[0]['connections_count'] - 1
        supabase.table('tenants').update({'connections_count': new_count}).eq('id', tenant_id).execute()
    
    # Deletar conexão do banco
    supabase.table('connections').delete().eq('id', connection_id).execute()
    return {"success": True}

# ==================== CONVERSATIONS ROUTES ====================

@api_router.get("/conversations")
async def list_conversations(
    tenant_id: str,
    status: Optional[str] = None,
    connection_id: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    refresh_avatars: bool = False,
    payload: dict = Depends(verify_token)
):
    """List conversations for a tenant"""
    query = supabase.table('conversations').select('*').eq('tenant_id', tenant_id)
    
    if status and status != 'all':
        query = query.eq('status', status)
    if connection_id and connection_id != 'all':
        query = query.eq('connection_id', connection_id)
    
    if limit < 1:
        limit = 1
    if limit > 1000:
        limit = 1000
    if offset < 0:
        offset = 0

    result = query.order('last_message_at', desc=True).range(offset, offset + limit - 1).execute()

    connection_by_id: Dict[str, Dict[str, Any]] = {}
    try:
        connections = supabase.table('connections').select('id, instance_name, provider').eq('tenant_id', tenant_id).execute()
        connection_by_id = {c['id']: c for c in (connections.data or []) if c.get('id')}
    except:
        connection_by_id = {}

    def needs_avatar_refresh(conv_row: dict) -> bool:
        avatar = conv_row.get('contact_avatar')
        if not avatar:
            return True
        if isinstance(avatar, str) and 'api.dicebear.com' in avatar:
            return True
        return False

    to_refresh = [c for c in (result.data or []) if needs_avatar_refresh(c)] if refresh_avatars else []
    refreshed: Dict[str, Optional[str]] = {}

    async def refresh_avatar(conv_row: dict) -> Optional[str]:
        conn = connection_by_id.get(conv_row.get('connection_id'))
        avatar = conv_row.get('contact_avatar')

        if not conn or conn.get('provider') != 'evolution' or not conn.get('instance_name'):
            if isinstance(avatar, str) and 'api.dicebear.com' in avatar:
                try:
                    supabase.table('conversations').update({'contact_avatar': None}).eq('id', conv_row['id']).execute()
                except:
                    pass
            return None

        try:
            data = await evolution_api.get_profile_picture(conn['instance_name'], conv_row.get('contact_phone') or '')
            url = extract_profile_picture_url(data)
        except:
            url = None

        if url:
            try:
                supabase.table('conversations').update({'contact_avatar': url}).eq('id', conv_row['id']).execute()
            except:
                pass
            return url

        if isinstance(avatar, str) and 'api.dicebear.com' in avatar:
            try:
                supabase.table('conversations').update({'contact_avatar': None}).eq('id', conv_row['id']).execute()
            except:
                pass

        return None

    if refresh_avatars and to_refresh:
        results = await asyncio.gather(*(refresh_avatar(c) for c in to_refresh), return_exceptions=True)
        for row, res in zip(to_refresh, results):
            if isinstance(res, str) and res.strip():
                refreshed[row['id']] = res.strip()
            else:
                refreshed[row['id']] = None

    conversations = []
    for c in (result.data or []):
        avatar = refreshed.get(c['id']) if c.get('id') in refreshed else c.get('contact_avatar')
        if isinstance(avatar, str) and 'api.dicebear.com' in avatar:
            avatar = None
        conversations.append({
            'id': c['id'],
            'tenantId': c['tenant_id'],
            'connectionId': c['connection_id'],
            'contactPhone': c['contact_phone'],
            'contactName': c['contact_name'],
            'contactAvatar': avatar,
            'status': c['status'],
            'assignedTo': c['assigned_to'],
            'transferStatus': c.get('transfer_status'),
            'transferTo': c.get('transfer_to'),
            'transferReason': c.get('transfer_reason'),
            'transferInitiatedBy': c.get('transfer_initiated_by'),
            'transferInitiatedAt': c.get('transfer_initiated_at'),
            'transferCompletedAt': c.get('transfer_completed_at'),
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

@api_router.post("/conversations/initiate")
async def initiate_conversation(data: InitiateConversation, payload: dict = Depends(verify_token)):
    """Initiate a conversation with a contact"""
    tenant_id = get_user_tenant_id(payload)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant não identificado")

    raw_phone = (data.phone or '').strip()
    if not raw_phone:
        raise HTTPException(status_code=400, detail="Telefone obrigatório")

    # Check if conversation already exists
    normalized_phone = re.sub(r'\D', '', raw_phone)
    if not normalized_phone:
        raise HTTPException(status_code=400, detail="Telefone obrigatório")

    result = supabase.table('conversations').select('*').eq('tenant_id', tenant_id).eq('contact_phone', normalized_phone).execute()
    if (not result.data) and raw_phone != normalized_phone:
        result = supabase.table('conversations').select('*').eq('tenant_id', tenant_id).eq('contact_phone', raw_phone).execute()
    
    if result.data:
        # Return existing conversation
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

    # Need to create a new conversation. 
    # Must find a valid connection (Evolution instance) to assign to this conversation.
    # We'll pick the first connected Evolution instance for this tenant.
    conn_result = supabase.table('connections').select('*').eq('tenant_id', tenant_id).eq('provider', 'evolution').eq('status', 'connected').execute()
    
    if not conn_result.data:
        # Fallback to any connection
        conn_result = supabase.table('connections').select('*').eq('tenant_id', tenant_id).limit(1).execute()
        
    if not conn_result.data:
        raise HTTPException(status_code=400, detail="Nenhuma conexão disponível para iniciar conversa")
        
    connection = conn_result.data[0]
    
    # Try to get profile picture and name
    avatar_url = None
    contact_name = normalized_phone
    
    # If contact_id provided, look up name (and ensure tenant isolation)
    if data.contact_id:
        try:
            contact_result = supabase.table('contacts').select('id, tenant_id, name, full_name').eq('id', data.contact_id).limit(1).execute()
            if contact_result.data:
                contact_row = contact_result.data[0]
                if contact_row.get('tenant_id') == tenant_id:
                    desired = (contact_row.get('name') or contact_row.get('full_name') or '').strip()
                    if desired:
                        contact_name = desired
        except Exception:
            pass

    # If no name resolved, try by phone (covers when the UI doesn't pass contact_id)
    if not (contact_name or '').strip() or contact_name == normalized_phone:
        try:
            contact_result = supabase.table('contacts').select('name, full_name, phone').eq('tenant_id', tenant_id).eq('phone', normalized_phone).limit(1).execute()
            if (not contact_result.data) and raw_phone != normalized_phone:
                contact_result = supabase.table('contacts').select('name, full_name, phone').eq('tenant_id', tenant_id).eq('phone', raw_phone).limit(1).execute()
            if contact_result.data:
                contact_row = contact_result.data[0]
                desired = (contact_row.get('name') or contact_row.get('full_name') or '').strip()
                if desired:
                    contact_name = desired
        except Exception:
            pass
            
    try:
        if connection['provider'] == 'evolution':
            profile_data = await evolution_api.get_profile_picture(connection['instance_name'], normalized_phone)
            avatar_url = extract_profile_picture_url(profile_data)
    except Exception:
        pass

    conv_data = {
        'tenant_id': tenant_id,
        'connection_id': connection['id'],
        'contact_phone': normalized_phone,
        'contact_name': (contact_name or '').strip() or normalized_phone,
        'contact_avatar': avatar_url,
        'status': 'open',
        'unread_count': 0,
        'last_message_at': datetime.utcnow().isoformat(),
        'last_message_preview': ''
    }
    
    result = supabase.table('conversations').insert(conv_data).execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Erro ao criar conversa")
        
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

@api_router.post("/conversations/{conversation_id}/transfer")
async def transfer_conversation(conversation_id: str, data: ConversationTransferCreate, payload: dict = Depends(verify_token)):
    user_tenant_id = get_user_tenant_id(payload)

    conv = supabase.table('conversations').select('*').eq('id', conversation_id).execute()
    if not conv.data:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    conversation = conv.data[0]
    if user_tenant_id and conversation.get('tenant_id') != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    to_user = supabase.table('users').select('id, name, tenant_id').eq('id', data.to_agent_id).execute()
    if not to_user.data:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    to_agent = to_user.data[0]
    if conversation.get('tenant_id') and to_agent.get('tenant_id') != conversation.get('tenant_id'):
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

    system_text = f"Transferência iniciada para {to_agent.get('name') or 'agente'}."
    if reason:
        system_text += f" Motivo: {reason}"

    try:
        msg_row = supabase.table('messages').insert({
            'conversation_id': conversation_id,
            'content': system_text,
            'type': 'system',
            'direction': 'outbound',
            'status': 'sent'
        }).execute()
        if msg_row.data:
            supabase.table('conversations').update({
                'last_message_at': now,
                'last_message_preview': system_text[:50]
            }).eq('id', conversation_id).execute()
    except Exception:
        pass

    safe_insert_audit_log(
        tenant_id=conversation.get('tenant_id'),
        actor_user_id=payload.get('user_id'),
        action='conversation.transferred',
        entity_type='conversation',
        entity_id=conversation_id,
        metadata={'to_agent_id': data.to_agent_id, 'reason': reason}
    )

    return {"success": True}

@api_router.post("/conversations/{conversation_id}/transfer/accept")
async def accept_conversation_transfer(conversation_id: str, payload: dict = Depends(verify_token)):
    user_id = payload.get('user_id')
    user_tenant_id = get_user_tenant_id(payload)

    conv = supabase.table('conversations').select('*').eq('id', conversation_id).execute()
    if not conv.data:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    conversation = conv.data[0]
    if user_tenant_id and conversation.get('tenant_id') != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    if conversation.get('transfer_to') and conversation.get('transfer_to') != user_id:
        raise HTTPException(status_code=403, detail="Apenas o agente de destino pode aceitar")

    now = datetime.utcnow().isoformat()
    supabase.table('conversations').update({
        'transfer_status': 'completed',
        'transfer_completed_at': now
    }).eq('id', conversation_id).execute()

    safe_insert_audit_log(
        tenant_id=conversation.get('tenant_id'),
        actor_user_id=user_id,
        action='conversation.transfer_accepted',
        entity_type='conversation',
        entity_id=conversation_id,
        metadata={}
    )

    return {"success": True}

@api_router.post("/conversations/{conversation_id}/labels/{label_id}")
async def add_label(conversation_id: str, label_id: str, payload: dict = Depends(verify_token)):
    """Add label to conversation"""
    try:
        result = await LabelsService.add_label_to_conversation(conversation_id, label_id)
        if not result:
            raise HTTPException(status_code=404, detail="Conversa não encontrada")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding label {label_id} to conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao adicionar label: {str(e)}")

@api_router.delete("/conversations/{conversation_id}/labels/{label_id}")
async def remove_label(conversation_id: str, label_id: str, payload: dict = Depends(verify_token)):
    """Remove label from conversation"""
    try:
        result = await LabelsService.remove_label_from_conversation(conversation_id, label_id)
        if not result:
            raise HTTPException(status_code=404, detail="Conversa não encontrada")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing label {label_id} from conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao remover label: {str(e)}")

@api_router.delete("/conversations/purge")
async def purge_conversations(tenant_id: Optional[str] = None, payload: dict = Depends(verify_token)):
    requested_tenant_id = (tenant_id or '').strip() or None
    user_tenant_id = get_user_tenant_id(payload)

    effective_tenant_id = None
    if payload.get('role') == 'superadmin' and requested_tenant_id:
        effective_tenant_id = requested_tenant_id
    else:
        effective_tenant_id = user_tenant_id

    if not effective_tenant_id:
        raise HTTPException(status_code=403, detail="Tenant não identificado")

    count_result = supabase.table('conversations').select('id', count='exact').eq('tenant_id', effective_tenant_id).execute()
    total = count_result.count or 0

    if total <= 0:
        return {"success": True, "deletedConversations": 0}

    conv_ids_result = supabase.table('conversations').select('id').eq('tenant_id', effective_tenant_id).execute()
    conversation_ids = [row.get('id') for row in (conv_ids_result.data or []) if row.get('id')]

    chunk_size = 200
    for i in range(0, len(conversation_ids), chunk_size):
        chunk = conversation_ids[i:i + chunk_size]
        try:
            supabase.table('assignment_history').delete().in_('conversation_id', chunk).execute()
        except Exception:
            pass
        try:
            supabase.table('auto_message_logs').delete().in_('conversation_id', chunk).execute()
        except Exception:
            pass
        try:
            supabase.table('typing_events').delete().in_('conversation_id', chunk).execute()
        except Exception:
            pass

    try:
        supabase.table('conversations').delete().eq('tenant_id', effective_tenant_id).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao excluir conversas: {str(e)}")

    safe_insert_audit_log(
        tenant_id=effective_tenant_id,
        actor_user_id=payload.get('user_id'),
        action='conversations.purge',
        entity_type='conversation',
        entity_id=None,
        metadata={'deleted': total}
    )

    return {"success": True, "deletedConversations": total}

@api_router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, payload: dict = Depends(verify_token)):
    user_tenant_id = get_user_tenant_id(payload)

    conv = supabase.table('conversations').select('id, tenant_id').eq('id', conversation_id).execute()
    if not conv.data:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    if user_tenant_id and conv.data[0].get('tenant_id') != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    supabase.table('messages').delete().eq('conversation_id', conversation_id).execute()
    supabase.table('conversations').delete().eq('id', conversation_id).execute()
    return {"success": True}

@api_router.delete("/conversations/{conversation_id}/messages")
async def clear_conversation_messages(conversation_id: str, payload: dict = Depends(verify_token)):
    user_tenant_id = get_user_tenant_id(payload)

    conv = supabase.table('conversations').select('id, tenant_id').eq('id', conversation_id).execute()
    if not conv.data:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    if user_tenant_id and conv.data[0].get('tenant_id') != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    supabase.table('messages').delete().eq('conversation_id', conversation_id).execute()
    supabase.table('conversations').update({
        'last_message_at': None,
        'last_message_preview': '',
        'unread_count': 0
    }).eq('id', conversation_id).execute()
    return {"success": True}

# ==================== CONTACTS ROUTES ====================

@api_router.get("/contacts")
async def list_contacts(
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    payload: dict = Depends(verify_token)
):
    """List all contacts for the tenant"""
    try:
        user_tenant_id = get_user_tenant_id(payload)
        if not user_tenant_id:
            raise HTTPException(status_code=403, detail="Tenant não identificado")

        if limit < 1:
            limit = 1
        if limit > 200:
            limit = 200
        if offset < 0:
            offset = 0

        query = supabase.table('contacts').select('*').eq('tenant_id', user_tenant_id)

        if search:
            search_term = f"%{search}%"
            query = query.or_(f"name.ilike.{search_term},phone.ilike.{search_term},email.ilike.{search_term}")

        result = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()

        contacts = []
        for c in (result.data or []):
            contacts.append({
                'id': c.get('id'),
                'tenantId': c.get('tenant_id'),
                'name': c.get('name') or c.get('full_name'),
                'phone': c.get('phone'),
                'email': c.get('email'),
                'tags': c.get('tags') or [],
                'customFields': c.get('custom_fields') or {},
                'status': c.get('status'),
                'firstContactAt': c.get('first_contact_at'),
                'source': c.get('source'),
                'createdAt': c.get('created_at'),
                'updatedAt': c.get('updated_at')
            })

        # Get total count
        count_result = supabase.table('contacts').select('id', count='exact').eq('tenant_id', user_tenant_id).execute()
        total = count_result.count if hasattr(count_result, 'count') and count_result.count else len(result.data or [])

        return {
            'contacts': contacts,
            'total': total,
            'limit': limit,
            'offset': offset
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing contacts: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao listar contatos: {str(e)}")

@api_router.post("/contacts")
async def create_contact(data: ContactCreate, payload: dict = Depends(verify_token)):
    """Create a new contact"""
    try:
        user_tenant_id = get_user_tenant_id(payload)
        if not user_tenant_id:
            raise HTTPException(status_code=403, detail="Tenant não identificado")

        name = (data.name or '').strip()
        raw_phone = (data.phone or '').strip()

        if not name:
            raise HTTPException(status_code=400, detail="Nome é obrigatório")
        if not raw_phone:
            raise HTTPException(status_code=400, detail="Telefone é obrigatório")

        phone = normalize_phone_number(raw_phone)
        if not phone:
            raise HTTPException(status_code=400, detail="Telefone é inválido")

        # Check if contact with same phone already exists
        existing = supabase.table('contacts').select('id').eq('tenant_id', user_tenant_id).eq('phone', phone).limit(1).execute()
        if (not existing.data) and raw_phone != phone:
            existing = supabase.table('contacts').select('id').eq('tenant_id', user_tenant_id).eq('phone', raw_phone).limit(1).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail="Já existe um contato com este telefone")

        insert_result = None
        try:
            raw_status = str(data.status or '').strip().lower()
            normalized_status = {
                'pendente': 'pending',
                'pending': 'pending',
                'nao verificado': 'unverified',
                'não verificado': 'unverified',
                'unverified': 'unverified',
                'verificado': 'verified',
                'verified': 'verified'
            }.get(raw_status, None)
            final_status = normalized_status or 'verified'

            insert_data = {
                'tenant_id': user_tenant_id,
                'name': name,
                'phone': phone,
                'email': (data.email or '').strip() or None,
                'tags': data.tags or [],
                'custom_fields': data.custom_fields or {},
                'source': data.source or 'manual',
                'status': final_status,
                'first_contact_at': datetime.utcnow().isoformat()
            }
            insert_result = supabase.table('contacts').insert(insert_data).execute()
        except Exception:
            insert_result = None

        if not insert_result or not insert_result.data:
            try:
                insert_data_alt = {
                    'tenant_id': user_tenant_id,
                    'full_name': name,
                    'phone': phone,
                    'social_links': {},
                    'notes_html': '',
                    'status': final_status,
                    'first_contact_at': datetime.utcnow().isoformat()
                }
                insert_result = supabase.table('contacts').insert(insert_data_alt).execute()
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Erro ao criar contato: {str(e)}")

        if not insert_result or not insert_result.data:
            raise HTTPException(status_code=400, detail="Erro ao criar contato")

        c = insert_result.data[0]
        name_value = c.get('name') or c.get('full_name') or name
        
        safe_insert_audit_log(
            tenant_id=user_tenant_id,
            actor_user_id=payload.get('user_id'),
            action='contact.created',
            entity_type='contact',
            entity_id=c.get('id'),
            metadata={'phone': phone}
        )

        return {
            'id': c.get('id'),
            'tenantId': c.get('tenant_id'),
            'name': name_value,
            'phone': c.get('phone'),
            'email': c.get('email'),
            'tags': c.get('tags') or [],
            'customFields': c.get('custom_fields') or {},
            'socialLinks': c.get('social_links') or {},
            'notesHtml': c.get('notes_html') or '',
            'status': c.get('status'),
            'firstContactAt': c.get('first_contact_at'),
            'source': c.get('source'),
            'createdAt': c.get('created_at'),
            'updatedAt': c.get('updated_at')
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating contact: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao criar contato: {str(e)}")

@api_router.get("/contacts/by-phone")
async def get_contact_by_phone(tenant_id: str, phone: str, payload: dict = Depends(verify_token)):
    """
    Get or create a contact by phone number.
    This endpoint is resilient to schema changes and will work even if:
    - The contacts table doesn't exist
    - The contacts table has a different schema
    Falls back to reading contact info from conversations table.
    """
    try:
        user_tenant_id = get_user_tenant_id(payload)
        if user_tenant_id and tenant_id != user_tenant_id:
            raise HTTPException(status_code=403, detail="Acesso negado")

        raw_phone = (phone or '').strip()
        normalized_phone = normalize_phone_number(raw_phone) or raw_phone
        if not normalized_phone:
            raise HTTPException(status_code=400, detail="Telefone inválido")

        logger.info(f"Looking for contact with phone: {normalized_phone} in tenant: {tenant_id}")

        # Try to find contact in the contacts table
        try:
            existing = supabase.table('contacts').select('*').eq('tenant_id', tenant_id).eq('phone', normalized_phone).limit(1).execute()
            if (not existing.data) and raw_phone and raw_phone != normalized_phone:
                existing = supabase.table('contacts').select('*').eq('tenant_id', tenant_id).eq('phone', raw_phone).limit(1).execute()
            if existing.data:
                c = existing.data[0]
                full_name = c.get('full_name') or c.get('name') or normalized_phone
                # Return with actual schema columns
                return {
                    'id': c.get('id'),
                    'tenantId': c.get('tenant_id'),
                    'phone': c.get('phone'),
                    'fullName': full_name,
                    'email': c.get('email'),
                    'tags': c.get('tags') or [],
                    'customFields': c.get('custom_fields') or {},
                    'socialLinks': c.get('social_links') or {},
                    'notesHtml': c.get('notes_html') or '',
                    'status': c.get('status'),
                    'firstContactAt': c.get('first_contact_at'),
                    'source': c.get('source'),
                    'createdAt': c.get('created_at'),
                    'updatedAt': c.get('updated_at')
                }
        except Exception as table_error:
            # Table might not exist or have different schema - continue to fallback
            logger.warning(f"Could not query contacts table: {table_error}")

        # Fallback: get contact info from conversations table
        try:
            conv = supabase.table('conversations').select('id, contact_name, contact_avatar, contact_phone').eq('tenant_id', tenant_id).eq('contact_phone', normalized_phone).order('last_message_at', desc=True).limit(1).execute()
        except Exception as conv_error:
            logger.warning(f"Could not query conversations table for contact fallback: {conv_error}")
            conv = None
        
        if conv and conv.data:
            c = conv.data[0]
            # Return contact-like object from conversation data
            return {
                'id': f"conv-{c.get('id')}",  # Synthetic ID
                'tenantId': tenant_id,
                'phone': normalized_phone,
                'fullName': c.get('contact_name') or normalized_phone,
                'email': None,
                'tags': [],
                'customFields': {},
                'status': 'pending',
                'firstContactAt': None,
                'source': 'conversation',
                'createdAt': None,
                'updatedAt': None,
                'isFromConversation': True  # Flag to indicate this is from conversations table
            }

        # No contact found anywhere - return empty contact
        return {
            'id': None,
            'tenantId': tenant_id,
            'phone': normalized_phone,
            'fullName': normalized_phone,
            'email': None,
            'tags': [],
            'customFields': {},
            'status': 'pending',
            'firstContactAt': None,
            'source': None,
            'createdAt': None,
            'updatedAt': None,
            'isNew': True  # Flag to indicate this is a new contact
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_contact_by_phone: {e}")
        return {
            'id': None,
            'tenantId': tenant_id,
            'phone': (phone or '').strip(),
            'fullName': (phone or '').strip(),
            'email': None,
            'tags': [],
            'customFields': {},
            'socialLinks': {},
            'notesHtml': '',
            'status': 'pending',
            'firstContactAt': None,
            'source': None,
            'createdAt': None,
            'updatedAt': None,
            'isNew': True
        }

@api_router.get("/contacts/{contact_id}")
async def get_contact(contact_id: str, payload: dict = Depends(verify_token)):
    """Get a single contact by ID"""
    try:
        user_tenant_id = get_user_tenant_id(payload)

        try:
            uuid.UUID(contact_id)
        except Exception:
            raise HTTPException(status_code=404, detail="Contato não encontrado")

        result = supabase.table('contacts').select('*').eq('id', contact_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Contato não encontrado")

        c = result.data[0]
        if user_tenant_id and c.get('tenant_id') != user_tenant_id:
            raise HTTPException(status_code=403, detail="Acesso negado")

        conv_count = 0
        try:
            phone_value = c.get('phone')
            normalized_phone = normalize_phone_number(phone_value) or phone_value
            conv_result = supabase.table('conversations').select('id', count='exact').eq('tenant_id', c.get('tenant_id')).eq('contact_phone', normalized_phone).execute()
            if (not conv_result.count) and phone_value and normalized_phone and phone_value != normalized_phone:
                conv_result = supabase.table('conversations').select('id', count='exact').eq('tenant_id', c.get('tenant_id')).eq('contact_phone', phone_value).execute()
            conv_count = conv_result.count if hasattr(conv_result, 'count') and conv_result.count else 0
        except Exception:
            pass

        return {
            'id': c.get('id'),
            'tenantId': c.get('tenant_id'),
            'name': c.get('name') or c.get('full_name'),
            'phone': c.get('phone'),
            'email': c.get('email'),
            'tags': c.get('tags') or [],
            'customFields': c.get('custom_fields') or {},
            'socialLinks': c.get('social_links') or {},
            'notesHtml': c.get('notes_html') or '',
            'status': c.get('status'),
            'firstContactAt': c.get('first_contact_at'),
            'source': c.get('source'),
            'createdAt': c.get('created_at'),
            'updatedAt': c.get('updated_at'),
            'conversationCount': conv_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting contact: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar contato: {str(e)}")

@api_router.patch("/contacts/{contact_id}")
async def update_contact(contact_id: str, data: ContactUpdate, payload: dict = Depends(verify_token)):
    """
    Update a contact by ID. 
    If the contact_id starts with 'conv-', it means we're working with a synthetic 
    contact from the conversations table.
    
    NOTE: The actual contacts table uses 'name' column (not 'full_name').
    The API accepts 'full_name' for backwards compatibility but maps to 'name'.
    """
    try:
        user_tenant_id = get_user_tenant_id(payload)
        
        # Check if this is a synthetic contact ID from conversations
        if contact_id.startswith('conv-'):
            conversation_id = contact_id.replace('conv-', '')
            conv = supabase.table('conversations').select('*').eq('id', conversation_id).execute()
            if not conv.data:
                raise HTTPException(status_code=404, detail="Conversa não encontrada")
            
            conversation = conv.data[0]
            if user_tenant_id and conversation.get('tenant_id') != user_tenant_id:
                raise HTTPException(status_code=403, detail="Acesso negado")
            
            # Update conversation contact name
            if data.full_name is not None:
                name = (data.full_name or '').strip()
                if not name:
                    raise HTTPException(status_code=400, detail="Nome é obrigatório")
                supabase.table('conversations').update({
                    'contact_name': name
                }).eq('id', conversation_id).execute()
            
            return {
                'id': contact_id,
                'tenantId': conversation.get('tenant_id'),
                'phone': conversation.get('contact_phone'),
                'fullName': data.full_name or conversation.get('contact_name'),
                'socialLinks': {},
                'notesHtml': '',
                'createdAt': conversation.get('created_at'),
                'updatedAt': datetime.utcnow().isoformat()
            }
        
        # Try to update in the contacts table
        try:
            try:
                uuid.UUID(contact_id)
            except Exception:
                raise HTTPException(status_code=404, detail="Contato não encontrado")

            existing = supabase.table('contacts').select('*').eq('id', contact_id).execute()
            if not existing.data:
                raise HTTPException(status_code=404, detail="Contato não encontrado")
            contact = existing.data[0]
            if user_tenant_id and contact.get('tenant_id') != user_tenant_id:
                raise HTTPException(status_code=403, detail="Acesso negado")

            desired_name = None
            if data.full_name is not None:
                desired_name = (data.full_name or '').strip()
                if not desired_name:
                    raise HTTPException(status_code=400, detail="Nome é obrigatório")

                try:
                    supabase.table('conversations').update({
                        'contact_name': desired_name
                    }).eq('tenant_id', contact.get('tenant_id')).eq('contact_phone', contact.get('phone')).execute()
                except Exception:
                    pass

            def build_update_payload(name_field: str) -> Dict[str, Any]:
                update_data: Dict[str, Any] = {}
                if desired_name is not None:
                    update_data[name_field] = desired_name
                if data.email is not None:
                    update_data['email'] = (data.email or '').strip() or None
                if data.tags is not None:
                    update_data['tags'] = data.tags or []
                if data.custom_fields is not None:
                    update_data['custom_fields'] = data.custom_fields or {}
                if data.social_links is not None:
                    update_data['social_links'] = data.social_links or {}
                if data.notes_html is not None:
                    update_data['notes_html'] = data.notes_html or ''
                if data.status is not None:
                    raw_status = str(data.status or '').strip().lower()
                    normalized_status = {
                        'pendente': 'pending',
                        'pending': 'pending',
                        'nao verificado': 'unverified',
                        'não verificado': 'unverified',
                        'unverified': 'unverified',
                        'verificado': 'verified',
                        'verified': 'verified'
                    }.get(raw_status)
                    if not normalized_status:
                        raise HTTPException(status_code=400, detail="Status inválido")
                    update_data['status'] = normalized_status
                if update_data:
                    update_data['updated_at'] = datetime.utcnow().isoformat()
                return update_data

            update_data = build_update_payload('name')
            if not update_data:
                return {"success": True}

            after = None
            try:
                updated = supabase.table('contacts').update(update_data).eq('id', contact_id).execute()
                if updated.data:
                    after = updated.data[0]
            except Exception:
                after = None

            if after is None:
                update_data_alt = build_update_payload('full_name')
                try:
                    updated_alt = supabase.table('contacts').update(update_data_alt).eq('id', contact_id).execute()
                    if updated_alt.data:
                        after = updated_alt.data[0]
                except Exception:
                    after = None

            if after is None:
                if desired_name is not None:
                    return {
                        'id': contact.get('id') or contact_id,
                        'tenantId': contact.get('tenant_id'),
                        'phone': contact.get('phone'),
                        'fullName': desired_name,
                        'email': contact.get('email'),
                        'tags': contact.get('tags') or [],
                        'customFields': contact.get('custom_fields') or {},
                        'socialLinks': contact.get('social_links') or {},
                        'notesHtml': contact.get('notes_html') or '',
                        'status': contact.get('status'),
                        'firstContactAt': contact.get('first_contact_at'),
                        'createdAt': contact.get('created_at'),
                        'updatedAt': datetime.utcnow().isoformat()
                    }
                raise HTTPException(status_code=400, detail="Erro ao atualizar contato")

            full_name_value = after.get('full_name') or after.get('name')

            if desired_name is not None:
                try:
                    supabase.table('conversations').update({
                        'contact_name': desired_name
                    }).eq('tenant_id', contact.get('tenant_id')).eq('contact_phone', contact.get('phone')).execute()
                except Exception:
                    pass

            safe_insert_audit_log(
                tenant_id=contact.get('tenant_id'),
                actor_user_id=payload.get('user_id'),
                action='contact.updated',
                entity_type='contact',
                entity_id=contact_id,
                metadata={'fields': list((update_data or {}).keys())}
            )

            return {
                'id': after.get('id'),
                'tenantId': after.get('tenant_id'),
                'phone': after.get('phone'),
                'fullName': full_name_value,
                'email': after.get('email'),
                'tags': after.get('tags') or [],
                'customFields': after.get('custom_fields') or {},
                'socialLinks': after.get('social_links') or {},
                'notesHtml': after.get('notes_html') or '',
                'status': after.get('status'),
                'firstContactAt': after.get('first_contact_at'),
                'createdAt': after.get('created_at'),
                'updatedAt': after.get('updated_at')
            }
        except HTTPException:
            raise
        except Exception as table_error:
            logger.error(f"Could not update contacts table: {table_error}")
            raise HTTPException(status_code=400, detail=f"Erro ao atualizar contato: {str(table_error)}")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating contact: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar contato: {str(e)}")

@api_router.delete("/contacts/{contact_id}")
async def delete_contact(contact_id: str, payload: dict = Depends(verify_token)):
    """Delete a contact by ID"""
    user_tenant_id = get_user_tenant_id(payload)
    if not user_tenant_id:
        raise HTTPException(status_code=403, detail="Tenant não identificado")

    if (contact_id or '').startswith('conv-'):
        raise HTTPException(status_code=400, detail="Não é possível excluir este contato")

    try:
        uuid.UUID(contact_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Contato não encontrado")

    existing = supabase.table('contacts').select('id, tenant_id').eq('id', contact_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Contato não encontrado")
    contact = existing.data[0]
    if contact.get('tenant_id') != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    supabase.table('contacts').delete().eq('id', contact_id).execute()

    safe_insert_audit_log(
        tenant_id=user_tenant_id,
        actor_user_id=payload.get('user_id'),
        action='contact.deleted',
        entity_type='contact',
        entity_id=contact_id,
        metadata={}
    )

    return {"success": True}

@api_router.get("/contacts/{contact_id}/history")
async def list_contact_history(contact_id: str, limit: int = 20, payload: dict = Depends(verify_token)):
    user_tenant_id = get_user_tenant_id(payload)

    contact = supabase.table('contacts').select('tenant_id').eq('id', contact_id).execute()
    if not contact.data:
        raise HTTPException(status_code=404, detail="Contato não encontrado")
    tenant_id = contact.data[0].get('tenant_id')
    if user_tenant_id and tenant_id != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    if limit < 1:
        limit = 1
    if limit > 200:
        limit = 200

    result = supabase.table('contact_history').select(
        'id, action, before, after, created_at, changed_by:users!changed_by(id, name, avatar)'
    ).eq('contact_id', contact_id).order('created_at', desc=True).limit(limit).execute()

    return [{
        'id': h['id'],
        'action': h['action'],
        'before': h.get('before'),
        'after': h.get('after'),
        'createdAt': h.get('created_at'),
        'changedBy': h.get('changed_by')
    } for h in (result.data or [])]

# ==================== MESSAGES ROUTES ====================

@api_router.get("/messages")
async def list_messages(
    conversation_id: str,
    after: Optional[str] = None,
    before: Optional[str] = None,
    limit: int = 500,
    tail: bool = False,
    payload: dict = Depends(verify_token)
):
    """List messages for a conversation"""

    def normalize_message_content(content: Any, msg_type: str) -> str:
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
                view_once_v2_ext = cur.get('viewOnceMessageV2Extension')
                if isinstance(view_once_v2_ext, dict) and isinstance(view_once_v2_ext.get('message'), dict):
                    cur = view_once_v2_ext.get('message')
                    continue
                document_with_caption = cur.get('documentWithCaptionMessage')
                if isinstance(document_with_caption, dict) and isinstance(document_with_caption.get('message'), dict):
                    cur = document_with_caption.get('message')
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
                    ssr = lr.get('singleSelectReply')
                    if isinstance(ssr, dict) and isinstance(ssr.get('selectedRowId'), str):
                        return ssr.get('selectedRowId') or ''

                tbr = cur.get('templateButtonReplyMessage')
                if isinstance(tbr, dict):
                    v = tbr.get('selectedDisplayText') or tbr.get('selectedId')
                    if isinstance(v, str):
                        return v or ''

                rx = cur.get('reactionMessage')
                if isinstance(rx, dict) and isinstance(rx.get('text'), str):
                    return rx.get('text') or ''

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
                    if isinstance(doc.get('title'), str) and doc.get('title'):
                        return doc.get('title') or ''

            if msg_type == 'audio':
                return '[Áudio]'
            if msg_type == 'image':
                return '[Imagem]'
            if msg_type == 'video':
                return '[Vídeo]'
            if msg_type == 'document':
                return '[Documento]'
            return '[Mensagem]'
        if isinstance(content, list):
            return '[Mensagem]'
        return str(content)

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
        def parse_bool(value: Any) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                v = value.strip().lower()
                if v in ['true', '1', 'yes', 'y', 'sim']:
                    return True
                if v in ['false', '0', 'no', 'n', 'nao', 'não', '']:
                    return False
            return False

        raw_direction = m.get('direction') or 'inbound'
        metadata = m.get('metadata') or {}
        from_me = False
        if isinstance(metadata, dict):
            from_me = parse_bool(metadata.get('from_me')) or parse_bool(metadata.get('fromMe'))
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
            'content': normalize_message_content(m.get('content'), m.get('type') or 'text'),
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

@api_router.delete("/messages/{message_id}")
async def delete_message(message_id: str, payload: dict = Depends(verify_token)):
    user_tenant_id = get_user_tenant_id(payload)

    msg = supabase.table('messages').select('id, conversation_id').eq('id', message_id).execute()
    if not msg.data:
        raise HTTPException(status_code=404, detail="Mensagem não encontrada")
    conversation_id = msg.data[0]['conversation_id']

    conv = supabase.table('conversations').select('id, tenant_id').eq('id', conversation_id).execute()
    if not conv.data:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    if user_tenant_id and conv.data[0].get('tenant_id') != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    supabase.table('messages').delete().eq('id', message_id).execute()

    def normalize_preview(content: Any, msg_type: str) -> str:
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
                view_once_v2_ext = cur.get('viewOnceMessageV2Extension')
                if isinstance(view_once_v2_ext, dict) and isinstance(view_once_v2_ext.get('message'), dict):
                    cur = view_once_v2_ext.get('message')
                    continue
                break

            if isinstance(cur, dict):
                c = cur.get('conversation')
                if isinstance(c, str) and c:
                    return c
                tm = cur.get('textMessage')
                if isinstance(tm, dict) and isinstance(tm.get('text'), str) and tm.get('text'):
                    return tm.get('text')
                etm = cur.get('extendedTextMessage')
                if isinstance(etm, dict) and isinstance(etm.get('text'), str) and etm.get('text'):
                    return etm.get('text')
                v = cur.get('conversation')
                if isinstance(v, str) and v:
                    return v

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

    latest = supabase.table('messages').select('content, timestamp, type').eq('conversation_id', conversation_id).order('timestamp', desc=True).limit(1).execute()
    if latest.data:
        lm = latest.data[0]
        content = normalize_preview(lm.get('content'), lm.get('type') or 'text')
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

@api_router.post("/messages")
async def send_message(message: MessageCreate, background_tasks: BackgroundTasks, payload: dict = Depends(verify_token)):
    """Send a new message"""
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
                prefix = build_user_signature_prefix(user_row.data[0])
                if prefix and not content.startswith(prefix) and not content.lstrip().startswith(f"*{(user_row.data[0].get('name') or '').strip()}*"):
                    content = prefix + content
        except Exception:
            pass

    # Save message to database first
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

    safe_insert_audit_log(
        tenant_id=conversation.get('tenant_id'),
        actor_user_id=payload.get('user_id'),
        action='message.sent',
        entity_type='message',
        entity_id=(result.data[0]['id'] if result.data else None),
        metadata={'conversation_id': message.conversation_id, 'type': message.type}
    )
    
    connection_provider = (connection.get('provider') if isinstance(connection, dict) else None)
    connection_status = (connection.get('status') if isinstance(connection, dict) else None)
    is_evolution = str(connection_provider or '').lower() == 'evolution'
    is_connected = str(connection_status or '').lower() in ['connected', 'open']

    status = 'sent'

    # Send via WhatsApp if Evolution API connection
    if connection and is_evolution and is_connected:
        background_tasks.add_task(
            send_whatsapp_message,
            connection['instance_name'],
            conversation['contact_phone'],
            content,
            message.type,
            result.data[0]['id']
        )
    else:
        supabase.table('messages').update({'status': 'failed'}).eq('id', result.data[0]['id']).execute()
        status = 'failed'
    
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
        elif msg_type == 'sticker':
            await evolution_api.send_sticker(instance_name, phone, content)
        
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
        
        # Process ALL messages (including fromMe - messages sent from the phone)
        if parsed['event'] == 'message':
            is_from_me = parsed.get('from_me', False)
            
            # Ignorar mensagens de grupos (grupos têm @g.us no JID)
            raw_jid = parsed.get('remote_jid_raw') or payload.get('data', {}).get('key', {}).get('remoteJid', '')
            if '@g.us' in raw_jid:
                logger.info(f"Ignoring group message from {raw_jid}")
                return {"success": True, "ignored": "group_message"}
            if '@broadcast' in raw_jid:
                logger.info(f"Ignoring broadcast message from {raw_jid}")
                return {"success": True, "ignored": "broadcast_message"}
            
            # Find connection by instance name
            conn = supabase.table('connections').select('*, tenants(*)').eq('instance_name', instance_name).execute()
            
            if conn.data:
                connection = conn.data[0]
                tenant_id = connection['tenant_id']
                raw_phone = parsed['remote_jid']
                phone = normalize_phone_number(raw_phone) or (raw_phone or '').strip()
                if not phone or phone in ['status', 'broadcast']:
                    logger.info(f"Ignoring message with invalid remote_jid: {phone} raw_jid={raw_jid}")
                    return {"success": True, "ignored": "invalid_remote_jid"}

                def is_placeholder_text(text: str) -> bool:
                    t = (text or '').strip().lower()
                    return t in ['[mensagem]', '[message]']

                first_contact_dt = datetime.utcnow()
                ts = parsed.get('timestamp')
                try:
                    ts_int = int(ts)
                    if ts_int > 10**12:
                        ts_int = ts_int // 1000
                    if ts_int > 0:
                        first_contact_dt = datetime.utcfromtimestamp(ts_int)
                except Exception:
                    first_contact_dt = datetime.utcnow()
                first_contact_at_iso = first_contact_dt.isoformat()

                if is_placeholder_text(parsed.get('content') or ''):
                    try:
                        fetched = await evolution_api.fetch_messages(instance_name, phone, count=25)
                        messages = []
                        if isinstance(fetched, list):
                            messages = fetched
                        elif isinstance(fetched, dict):
                            if isinstance(fetched.get('messages'), list):
                                messages = fetched.get('messages') or []
                            elif isinstance(fetched.get('data'), list):
                                messages = fetched.get('data') or []
                            elif isinstance(fetched.get('data'), dict) and isinstance(fetched.get('data', {}).get('messages'), list):
                                messages = fetched.get('data', {}).get('messages') or []
                            elif isinstance(fetched.get('response'), list):
                                messages = fetched.get('response') or []

                        target_id = parsed.get('message_id')
                        candidate = None
                        for m in messages:
                            if not isinstance(m, dict):
                                continue
                            key = m.get('key') or {}
                            m_id = key.get('id') if isinstance(key, dict) else None
                            if target_id and m_id == target_id:
                                candidate = m
                                break
                        if candidate is None and messages:
                            candidate = messages[0] if isinstance(messages[0], dict) else None

                        if candidate:
                            reparsed = evolution_api.parse_webhook_message({
                                'event': 'MESSAGES_UPSERT',
                                'instance': instance_name,
                                'data': {'messages': [candidate]}
                            })
                            if isinstance(reparsed, dict) and reparsed.get('event') == 'message':
                                if not is_placeholder_text(reparsed.get('content') or ''):
                                    parsed = {**parsed, **reparsed}
                    except Exception as e:
                        logger.warning(f"Fallback fetch_messages failed for {instance_name}: {e}")
                
                if is_placeholder_text(parsed.get('content') or ''):
                    data_obj = payload.get('data')
                    data_type = type(data_obj).__name__
                    data_keys = list(data_obj.keys())[:25] if isinstance(data_obj, dict) else None
                    logger.warning(
                        f"Placeholder message content for {instance_name}: "
                        f"msg_id={parsed.get('message_id')} data_type={data_type} data_keys={data_keys}"
                    )
                
                # Determine message direction based on fromMe flag
                direction = 'outbound' if is_from_me else 'inbound'
                
                # Find or create conversation
                is_new_conversation = False
                conv = supabase.table('conversations').select('*').eq('tenant_id', tenant_id).eq('connection_id', connection['id']).eq('contact_phone', phone).execute()
                if (not conv.data) and raw_phone and str(raw_phone).strip() and str(raw_phone).strip() != phone:
                    conv = supabase.table('conversations').select('*').eq('tenant_id', tenant_id).eq('connection_id', connection['id']).eq('contact_phone', str(raw_phone).strip()).execute()
                
                if conv.data:
                    conversation = conv.data[0]
                    preview = '' if is_placeholder_text(parsed.get('content') or '') else (parsed.get('content') or '')[:50]
                    
                    # Only increment unread_count for INBOUND messages (not from_me)
                    update_data = {
                        'last_message_at': datetime.utcnow().isoformat(),
                        'last_message_preview': preview
                    }
                    if not is_from_me:
                        update_data['unread_count'] = conversation['unread_count'] + 1
                    
                    supabase.table('conversations').update(update_data).eq('id', conversation['id']).execute()
                else:
                    # Create new conversation
                    avatar_url = None
                    try:
                        data = await evolution_api.get_profile_picture(instance_name, phone)
                        avatar_url = extract_profile_picture_url(data)
                    except Exception:
                        avatar_url = None
                    conv_data = {
                        'tenant_id': tenant_id,
                        'connection_id': connection['id'],
                        'contact_phone': phone,
                        'contact_name': parsed.get('push_name') or phone,
                        'contact_avatar': avatar_url,
                        'status': 'open',
                        'unread_count': 0 if is_from_me else 1,  # Don't count as unread if from_me
                        'last_message_preview': '' if is_placeholder_text(parsed.get('content') or '') else (parsed.get('content') or '')[:50]
                    }
                    conv_result = supabase.table('conversations').insert(conv_data).execute()
                    conversation = conv_result.data[0]
                    is_new_conversation = True

                if not is_from_me:
                    try:
                        existing_contact = supabase.table('contacts').select('id, first_contact_at, status').eq('tenant_id', tenant_id).eq('phone', phone).limit(1).execute()
                        if (not existing_contact.data) and raw_phone and str(raw_phone).strip() and str(raw_phone).strip() != phone:
                            existing_contact = supabase.table('contacts').select('id, first_contact_at, status').eq('tenant_id', tenant_id).eq('phone', str(raw_phone).strip()).limit(1).execute()

                        if existing_contact.data:
                            row = existing_contact.data[0]
                            if not row.get('first_contact_at'):
                                supabase.table('contacts').update({'first_contact_at': first_contact_at_iso, 'updated_at': datetime.utcnow().isoformat()}).eq('id', row.get('id')).execute()
                        else:
                            push_name = (parsed.get('push_name') or '').strip() or None
                            try:
                                supabase.table('contacts').insert({
                                    'tenant_id': tenant_id,
                                    'name': push_name,
                                    'phone': phone,
                                    'source': 'whatsapp',
                                    'status': 'pending',
                                    'first_contact_at': first_contact_at_iso
                                }).execute()
                            except Exception:
                                supabase.table('contacts').insert({
                                    'tenant_id': tenant_id,
                                    'full_name': push_name,
                                    'phone': phone,
                                    'source': 'whatsapp',
                                    'status': 'pending',
                                    'first_contact_at': first_contact_at_iso
                                }).execute()
                    except Exception as e:
                        logger.warning(f"Auto-create contact failed for {tenant_id} phone={phone}: {e}")
                
                # Save message with correct direction
                parsed_type_raw = parsed.get('type') or 'text'
                parsed_kind_raw = parsed.get('media_kind')
                parsed_type = str(parsed_type_raw or '').strip().lower() or 'text'
                parsed_kind = str(parsed_kind_raw or '').strip().lower() if parsed_kind_raw is not None else ''
                allowed_message_types = {'text', 'image', 'video', 'audio', 'document', 'sticker', 'system'}
                message_type_to_store = parsed_kind if parsed_kind in allowed_message_types else parsed_type
                if message_type_to_store not in allowed_message_types:
                    message_type_to_store = 'text'

                msg_data = {
                    'conversation_id': conversation['id'],
                    'content': '' if is_placeholder_text(parsed.get('content') or '') else (parsed.get('content') or ''),
                    'type': message_type_to_store,
                    'direction': direction,  # 'inbound' for received, 'outbound' for sent
                    'status': 'read' if is_from_me else 'delivered',
                    'media_url': parsed.get('media_url'),
                    'external_id': parsed.get('message_id'),
                    'metadata': {
                        'remote_jid': parsed.get('remote_jid_raw') or f"{phone}@s.whatsapp.net",
                        'instance_name': instance_name,
                        'from_me': is_from_me,
                        'media_kind': parsed.get('media_kind'),
                        'mime_type': parsed.get('mime_type')
                    }
                }
                supabase.table('messages').insert(msg_data).execute()
                
                # Update tenant message count
                tenant = supabase.table('tenants').select('messages_this_month').eq('id', tenant_id).execute()
                if tenant.data:
                    supabase.table('tenants').update({
                        'messages_this_month': tenant.data[0]['messages_this_month'] + 1
                    }).eq('id', tenant_id).execute()

                try:
                    auto_messages_result = supabase.table('auto_messages').select('*').eq('tenant_id', tenant_id).eq('is_active', True).execute()
                except Exception as e:
                    logger.error(f"Error loading auto messages for tenant {tenant_id}: {e}")
                    auto_messages_result = None

                if auto_messages_result and auto_messages_result.data:
                    incoming_text = (parsed.get('content') or '').strip()
                    if not is_placeholder_text(incoming_text):
                        now_utc = datetime.utcnow()
                        local_offset = timedelta(hours=-3)
                        local_now = now_utc + local_offset
                        day_index = (local_now.weekday() + 1) % 7

                        def parse_time_to_minutes(value):
                            s = str(value or '').strip()
                            if not s:
                                return None
                            if len(s) >= 5 and s[2] == ':':
                                s = s[:5]
                            parts = s.split(':')
                            if len(parts) < 2:
                                return None
                            try:
                                hour = int(parts[0])
                                minute = int(parts[1])
                                if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                                    return None
                                return hour * 60 + minute
                            except Exception:
                                return None

                        now_minutes = local_now.hour * 60 + local_now.minute
                        connection_provider = (connection.get('provider') if isinstance(connection, dict) else None)
                        connection_status = (connection.get('status') if isinstance(connection, dict) else None)
                        is_evolution = str(connection_provider or '').lower() == 'evolution'
                        is_connected = str(connection_status or '').lower() in ['connected', 'open']

                        async def send_auto_message(auto_msg, delay_seconds: int):
                            try:
                                msg_type_inner = str(auto_msg.get('type') or '').lower()
                                log_query = supabase.table('auto_message_logs').select('id').eq('auto_message_id', auto_msg['id']).eq('conversation_id', conversation['id'])

                                if msg_type_inner == 'away':
                                    day_start_local = datetime(local_now.year, local_now.month, local_now.day)
                                    day_start_utc = day_start_local - local_offset
                                    day_end_utc = day_start_utc + timedelta(days=1)
                                    log_query = log_query.gte('sent_at', day_start_utc.isoformat()).lt('sent_at', day_end_utc.isoformat())

                                log_exists = log_query.limit(1).execute()
                                if log_exists.data:
                                    return

                                supabase.table('auto_message_logs').insert({
                                    'auto_message_id': auto_msg['id'],
                                    'conversation_id': conversation['id']
                                }).execute()

                                content = (auto_msg.get('message') or '').strip()
                                if not content:
                                    return

                                msg_row = supabase.table('messages').insert({
                                    'conversation_id': conversation['id'],
                                    'content': content,
                                    'type': 'system',
                                    'direction': 'outbound',
                                    'status': 'sent'
                                }).execute()
                                if not msg_row.data:
                                    return
                                msg = msg_row.data[0]

                                supabase.table('conversations').update({
                                    'last_message_at': now_utc.isoformat(),
                                    'last_message_preview': content[:50]
                                }).eq('id', conversation['id']).execute()

                                if tenant_id:
                                    tenant_row = supabase.table('tenants').select('messages_this_month').eq('id', tenant_id).execute()
                                    if tenant_row.data:
                                        supabase.table('tenants').update({
                                            'messages_this_month': tenant_row.data[0]['messages_this_month'] + 1
                                        }).eq('id', tenant_id).execute()

                                if is_evolution and is_connected:
                                    if delay_seconds and delay_seconds > 0:
                                        await asyncio.sleep(delay_seconds)
                                    await send_whatsapp_message(
                                        connection['instance_name'],
                                        phone,
                                        content,
                                        'text',
                                        msg['id']
                                    )
                            except Exception as e:
                                logger.error(f"Error sending auto message: {e}")

                        for auto_msg in auto_messages_result.data:
                            msg_type = str(auto_msg.get('type') or '').lower()
                            delay_seconds = auto_msg.get('delay_seconds') or 0
                            try:
                                delay_seconds = int(delay_seconds)
                            except Exception:
                                delay_seconds = 0
                            if delay_seconds < 0:
                                delay_seconds = 0

                            if msg_type == 'welcome':
                                if not is_new_conversation:
                                    continue
                            elif msg_type == 'away':
                                days = auto_msg.get('schedule_days') or []
                                if days and day_index not in days:
                                    continue
                                start_min = parse_time_to_minutes(auto_msg.get('schedule_start'))
                                end_min = parse_time_to_minutes(auto_msg.get('schedule_end'))
                                active = False
                                if start_min is None or end_min is None:
                                    active = True
                                elif start_min <= end_min:
                                    active = start_min <= now_minutes <= end_min
                                else:
                                    active = now_minutes >= start_min or now_minutes <= end_min
                                if not active:
                                    continue
                            elif msg_type == 'keyword':
                                keyword = (auto_msg.get('trigger_keyword') or '').strip()
                                if not keyword:
                                    continue
                                if keyword.lower() not in incoming_text.lower():
                                    continue
                            else:
                                continue

                            asyncio.create_task(send_auto_message(auto_msg, delay_seconds))
        
        elif parsed['event'] == 'connection':
            # Update connection status
            logger.info(f"Processing connection event for {instance_name}: state={parsed.get('state')}, raw_data={parsed.get('raw_data')}")
            
            # Detectar estados de conexão válidos
            connection_state = parsed.get('state', '').lower()
            is_connected = connection_state in ['open', 'connected']
            
            status = 'connected' if is_connected else 'disconnected'
            
            # Atualizar também o número do telefone se disponível
            update_data = {'status': status}
            if is_connected:
                update_data['webhook_url'] = f"https://whatpress-crm-production.up.railway.app/api/webhooks/evolution/{instance_name}"
            
            result = supabase.table('connections').update(update_data).eq('instance_name', instance_name).execute()
            logger.info(f"Connection status updated for {instance_name}: {status}, result: {result.data}")
        
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

@api_router.put("/quick-replies/{reply_id}")
async def update_quick_reply(reply_id: str, data: QuickReplyCreate, payload: dict = Depends(verify_token)):
    """Update an existing quick reply"""
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
        
        # If no labels exist, create default labels in the database
        default_labels_data = [
            {'name': 'Urgente', 'color': '#EF4444'},
            {'name': 'VIP', 'color': '#F59E0B'},
            {'name': 'Novo Cliente', 'color': '#10B981'},
            {'name': 'Follow-up', 'color': '#3B82F6'},
            {'name': 'Reclamação', 'color': '#EF4444'},
            {'name': 'Venda', 'color': '#8B5CF6'},
            {'name': 'Suporte', 'color': '#06B6D4'},
            {'name': 'Dúvida', 'color': '#6366F1'}
        ]
        
        created_labels = []
        for label_data in default_labels_data:
            insert_result = supabase.table('labels').insert({
                'tenant_id': tenant_id,
                'name': label_data['name'],
                'color': label_data['color']
            }).execute()
            if insert_result.data:
                created_label = insert_result.data[0]
                created_labels.append({
                    'id': created_label['id'],
                    'name': created_label['name'],
                    'color': created_label['color'],
                    'usageCount': 0,
                    'createdAt': created_label['created_at']
                })
        
        return created_labels
    except Exception as e:
        logger.error(f"Error getting labels: {e}")
        # Return empty list on error instead of static defaults
        return []

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
        writer.writerow(['Data/Hora', 'Direção', 'Tipo', 'Origem', 'Conteúdo', 'Status'])
        
        # Data
        for msg in result.data or []:
            direction = msg['direction']
            msg_type = (msg.get('type') or 'text').lower()
            if direction == 'inbound':
                origin = 'Cliente'
            elif msg_type == 'system':
                origin = 'Sistema'
            else:
                origin = 'Agente'

            writer.writerow([
                msg['timestamp'],
                'Enviada' if direction == 'outbound' else 'Recebida',
                msg['type'],
                origin,
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
async def list_evolution_instances(tenant_id: str = None, payload: dict = Depends(verify_token)):
    """List Evolution API instances filtered by tenant"""
    try:
        instances = await evolution_api.fetch_instances()
        
        # If tenant_id is provided, filter instances to only show those belonging to the tenant
        if tenant_id:
            # Get connections for this tenant to find which instances belong to them
            connections = supabase.table('connections').select('instance_name').eq('tenant_id', tenant_id).eq('provider', 'evolution').execute()
            
            if connections.data:
                # Get list of instance names that belong to this tenant
                tenant_instance_names = {conn['instance_name'] for conn in connections.data if conn.get('instance_name')}
                
                # Filter instances to only include those that match tenant's connections
                instances = [i for i in instances if i.get('name') in tenant_instance_names]
            else:
                # No connections for this tenant, return empty list
                instances = []
        
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
async def create_evolution_instance(name: str, request: Request, payload: dict = Depends(verify_token)):
    """Create new Evolution API instance"""
    try:
        webhook_url = f"{resolve_public_base_url(request)}/api/webhooks/evolution/{name}"
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
        
        detected = detect_media_kind(
            declared_mime_type=file.content_type,
            filename=file.filename,
            head_bytes=content[:96] if isinstance(content, (bytes, bytearray)) else b"",
        )
        file_type = detected.kind if detected.kind in {'image', 'video', 'audio', 'document', 'sticker'} else 'document'
        content_type = detected.mime_type or (file.content_type or 'application/octet-stream')

        if file_type == 'image':
            folder = 'images'
        elif file_type == 'video':
            folder = 'videos'
        elif file_type == 'audio':
            folder = 'audios'
        elif file_type == 'sticker':
            folder = 'stickers'
        else:
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
    preview_content = message_content
    if (media_type or '').lower() != 'system':
        try:
            user_row = supabase.table('users').select('name, job_title, department, signature_enabled, signature_include_title, signature_include_department').eq('id', payload.get('user_id')).execute()
            if user_row.data:
                prefix = build_user_signature_prefix(user_row.data[0])
                if prefix and not message_content.startswith(prefix) and not message_content.lstrip().startswith(f"*{(user_row.data[0].get('name') or '').strip()}*"):
                    message_content = prefix + message_content
        except Exception:
            pass
    
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
        'last_message_preview': preview_content[:50]
    }).eq('id', conversation_id).execute()
    
    # Update tenant message count
    if conversation.get('tenant_id'):
        tenant = supabase.table('tenants').select('messages_this_month').eq('id', conversation['tenant_id']).execute()
        if tenant.data:
                new_count = tenant.data[0]['messages_this_month'] + 1
                supabase.table('tenants').update({'messages_this_month': new_count}).eq('id', conversation['tenant_id']).execute()

    safe_insert_audit_log(
        tenant_id=conversation.get('tenant_id'),
        actor_user_id=payload.get('user_id'),
        action='message.media_sent',
        entity_type='message',
        entity_id=(result.data[0]['id'] if result.data else None),
        metadata={'conversation_id': conversation_id, 'type': media_type, 'media_url': media_url}
    )
    
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
        if (media_type or '').lower() == 'sticker':
            await evolution_api.send_sticker(instance_name, phone, media_url)
        elif (media_type or '').lower() == 'audio':
            await evolution_api.send_audio(instance_name, phone, media_url)
        else:
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

# ==================== MEDIA PROXY ====================

@api_router.get("/media/proxy")
async def proxy_whatsapp_media(
    message_id: str,
    remote_jid: str,
    instance_name: str,
    from_me: bool = False,
    payload: dict = Depends(verify_token)
):
    """
    Proxy endpoint to fetch WhatsApp media as base64.
    This is needed because WhatsApp media URLs are temporary and require authentication.
    """
    try:
        # Call Evolution API to get base64 media
        result = await evolution_api.get_base64_from_media_message(
            instance_name=instance_name,
            message_id=message_id,
            remote_jid=remote_jid,
            from_me=from_me
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Mídia não encontrada")
        
        # Result should contain base64 and mimetype
        base64_data = result.get('base64') or result.get('data', {}).get('base64')
        mimetype = result.get('mimetype') or result.get('data', {}).get('mimetype') or 'application/octet-stream'
        
        if not base64_data:
            raise HTTPException(status_code=404, detail="Dados da mídia não disponíveis")
        
        head_bytes = b""
        try:
            if isinstance(base64_data, str) and base64_data:
                want_bytes = 96
                take_chars = ((want_bytes + 2) // 3) * 4
                chunk = base64_data[: max(0, take_chars)]
                chunk += "=" * ((4 - (len(chunk) % 4)) % 4)
                head_bytes = base64.b64decode(chunk, validate=False)[:want_bytes]
        except Exception:
            head_bytes = b""

        detected = detect_media_kind(
            declared_mime_type=mimetype,
            head_bytes=head_bytes,
        )

        # Return as data URL
        return {
            "success": True,
            "dataUrl": f"data:{mimetype};base64,{base64_data}",
            "mimetype": mimetype,
            "kind": detected.kind,
            "confidence": detected.confidence
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Media proxy error: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao obter mídia: {str(e)}")

# Include the router in the main app
app.include_router(api_router)



@app.on_event("startup")
async def startup_event():
    sql = """
    ALTER TABLE users ADD COLUMN IF NOT EXISTS job_title VARCHAR(120);
    ALTER TABLE users ADD COLUMN IF NOT EXISTS department VARCHAR(120);
    ALTER TABLE users ADD COLUMN IF NOT EXISTS signature_enabled BOOLEAN DEFAULT true;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS signature_include_title BOOLEAN DEFAULT false;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS signature_include_department BOOLEAN DEFAULT false;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    """
    try:
        supabase.rpc('exec_sql', {'sql': sql}).execute()
    except Exception:
        pass
    logger.info("WhatsApp CRM API v2.0 started successfully")
