from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks, Request, Query, Response, Body
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
logger = logging.getLogger(__name__)
import concurrent.futures
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple
import uuid
from datetime import datetime, timedelta
import httpx

if TYPE_CHECKING:
    from .supabase_client import (
        SUPABASE_ANON_KEY,
        SUPABASE_KEY_ROLE,
        SUPABASE_SERVICE_ROLE_KEY,
        SUPABASE_URL,
        supabase,
    )
    from .evolution_api import EvolutionAPI, evolution_api
    from .features import (
        AgentService,
        DEFAULT_LABELS,
        DEFAULT_QUICK_REPLIES,
        LabelsService,
        QuickRepliesService,
    )
    from .media_detection import detect_media_kind
    from .whatsapp import get_whatsapp_container
    from .whatsapp.errors import ProviderNotFoundError, WhatsAppError
    from .whatsapp.observability import LogContext
    from .whatsapp.providers.base import ConnectionRef, ProviderContext, SendMessageRequest
else:
    try:
        from .supabase_client import (
            supabase,
            SUPABASE_URL,
            SUPABASE_ANON_KEY,
            SUPABASE_SERVICE_ROLE_KEY,
            SUPABASE_KEY_ROLE,
        )
        from .evolution_api import evolution_api, EvolutionAPI
        from .media_detection import detect_media_kind
        from .features import QuickRepliesService, LabelsService, AgentService, DEFAULT_QUICK_REPLIES, DEFAULT_LABELS
        from .whatsapp import get_whatsapp_container
        from .whatsapp.errors import WhatsAppError, ProviderNotFoundError
        from .whatsapp.observability import LogContext
        from .whatsapp.providers.base import ConnectionRef, ProviderContext, SendMessageRequest
    except Exception:
        from supabase_client import (
            supabase,
            SUPABASE_URL,
            SUPABASE_ANON_KEY,
            SUPABASE_SERVICE_ROLE_KEY,
            SUPABASE_KEY_ROLE,
        )
        from evolution_api import evolution_api, EvolutionAPI
        from media_detection import detect_media_kind
        from features import QuickRepliesService, LabelsService, AgentService, DEFAULT_QUICK_REPLIES, DEFAULT_LABELS
        from whatsapp import get_whatsapp_container
        from whatsapp.errors import WhatsAppError, ProviderNotFoundError
        from whatsapp.observability import LogContext
        from whatsapp.providers.base import ConnectionRef, ProviderContext, SendMessageRequest
import jwt
import json
import base64
import asyncio
import re
import time
import hashlib
import tempfile
from collections import deque
from dataclasses import dataclass
from typing import Callable
import hmac

if TYPE_CHECKING:
    class CryptContext:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            ...

        def hash(self, secret: str) -> str:
            ...

        def verify(self, secret: str, hash: str) -> bool:
            ...

        def needs_update(self, hash: str) -> bool:
            ...
else:
    from passlib.context import CryptContext

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Create the main app
app = FastAPI(title="WhatsApp CRM API")

_DEBUG_ENDPOINTS_ENABLED = (
    (os.getenv("DEBUG_ENDPOINTS") or "").strip().lower() in {"1", "true", "yes", "y"}
)

# Configure CORS immediately - Fix for Railway deployment
# allow_origins=["*"] fails with allow_credentials=True in some browsers/proxies
def resolve_cors_allow_origins() -> List[str]:
    required = [
        "https://whatpress-crm.vercel.app",
        "https://crm.altartech.com.br",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    raw = (os.getenv("CORS_ALLOW_ORIGINS") or "").strip()
    if raw:
        if raw.startswith("["):
            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    origins: List[str] = []
                    for o in data:
                        if isinstance(o, str) and o.strip():
                            origins.append(o.strip().rstrip("/"))
                    if origins:
                        merged = []
                        for origin in origins + required:
                            if origin and origin not in merged:
                                merged.append(origin)
                        return merged
            except Exception:
                pass
        parsed = []
        for o in re.split(r"[,\s;]+", raw):
            origin = (o or "").strip().strip("'\"`").rstrip("/")
            if origin:
                parsed.append(origin)
        if parsed:
            merged = []
            for origin in parsed + required:
                if origin and origin not in merged:
                    merged.append(origin)
            return merged
    return required


CORS_ALLOW_ORIGINS = resolve_cors_allow_origins()
CORS_ALLOW_ORIGIN_REGEX = os.getenv(
    "CORS_ALLOW_ORIGIN_REGEX",
    r"^https://((.*\.)?whatpress-crm(-.*)?\.vercel\.app|crm\.altartech\.com\.br)$",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_origin_regex=CORS_ALLOW_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Healthcheck endpoint (required for Railway)
@app.get("/health")
async def health_check():
    async def _check_db():
        def _ping():
            return supabase.table("users").select("id").limit(1).execute()
        try:
            await asyncio.to_thread(_ping)
            return {"ok": True}
        except Exception as e:
            if _is_supabase_not_configured_error(e):
                return {"ok": False, "error": "supabase_not_configured"}
            if _is_missing_table_or_schema_error(e, "users"):
                return {"ok": False, "error": "missing_users_table"}
            if _is_transient_db_error(e):
                return {"ok": False, "error": "db_unavailable"}
            return {"ok": False, "error": "db_error"}

    timeout_s = float(
        (os.getenv("HEALTHCHECK_DB_TIMEOUT_SECONDS") or "2").strip() or "2"
    )
    try:
        db = await asyncio.wait_for(_check_db(), timeout=timeout_s)
    except asyncio.TimeoutError:
        db = {"ok": False, "error": "db_timeout"}
    config = {
        "supabase_url_configured": bool(SUPABASE_URL),
        "supabase_service_role_key_configured": bool(SUPABASE_SERVICE_ROLE_KEY),
        "supabase_anon_key_configured": bool(SUPABASE_ANON_KEY),
        "supabase_key_role": SUPABASE_KEY_ROLE or None,
    }
    return {
        "status": "healthy",
        "service": "whatpress-crm",
        "database": db,
        "config": config,
    }

@app.get("/")
async def root():
    return {"message": "WhatsApp CRM API", "status": "running"}

@app.get("/debug-routes")
async def debug_routes():
    if not _DEBUG_ENDPOINTS_ENABLED:
        raise HTTPException(status_code=404, detail="Not Found")
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
        schedule_start TIME,
        schedule_end TIME,
        schedule_days INTEGER[],
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

    CREATE TABLE IF NOT EXISTS audit_logs (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
        actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
        action VARCHAR(120) NOT NULL,
        entity_type VARCHAR(80),
        entity_id UUID,
        metadata JSONB DEFAULT '{}'::jsonb,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant ON audit_logs(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs(actor_user_id);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);

    ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
    CREATE POLICY IF NOT EXISTS "Service role has full access audit_logs" ON audit_logs FOR ALL USING (true);

    CREATE TABLE IF NOT EXISTS contact_history (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        contact_id UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
        changed_by UUID REFERENCES users(id) ON DELETE SET NULL,
        action VARCHAR(50) NOT NULL,
        before JSONB,
        after JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_contact_history_contact ON contact_history(contact_id);
    CREATE INDEX IF NOT EXISTS idx_contact_history_tenant ON contact_history(tenant_id);

    ALTER TABLE contact_history ENABLE ROW LEVEL SECURITY;
    CREATE POLICY IF NOT EXISTS "Service role has full access contact_history" ON contact_history FOR ALL USING (true);

    DO $$
    BEGIN
      IF to_regclass('public.messages') IS NOT NULL THEN
        CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_conversation_external_id_unique
          ON messages(conversation_id, external_id)
          WHERE external_id IS NOT NULL;
      END IF;
    END $$;

    DO $$
    BEGIN
      IF to_regclass('public.messages') IS NOT NULL THEN
        ALTER TABLE messages ADD COLUMN IF NOT EXISTS external_id VARCHAR(255);
        ALTER TABLE messages ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
        ALTER TABLE messages ALTER COLUMN media_url TYPE TEXT;

        UPDATE messages
        SET type = 'text'
        WHERE type IS NULL OR type NOT IN ('text', 'image', 'audio', 'video', 'document', 'sticker', 'system');

        ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_type_check;
        ALTER TABLE messages
          ADD CONSTRAINT messages_type_check
          CHECK (type IN ('text', 'image', 'audio', 'video', 'document', 'sticker', 'system'));
      END IF;
    END $$;

    CREATE TABLE IF NOT EXISTS bulk_message_templates (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        name VARCHAR(255) NOT NULL,
        body TEXT NOT NULL,
        is_active BOOLEAN DEFAULT true,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_bulk_message_templates_tenant ON bulk_message_templates(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_bulk_message_templates_active ON bulk_message_templates(is_active);

    ALTER TABLE bulk_message_templates ENABLE ROW LEVEL SECURITY;
    CREATE POLICY IF NOT EXISTS "Service role has full access bulk_message_templates" ON bulk_message_templates FOR ALL USING (true);

    CREATE TABLE IF NOT EXISTS bulk_campaigns (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        created_by UUID REFERENCES users(id) ON DELETE SET NULL,
        name VARCHAR(255) NOT NULL,
        template_body TEXT NOT NULL,
        connection_id UUID REFERENCES connections(id) ON DELETE SET NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'scheduled', 'running', 'paused', 'completed', 'cancelled', 'failed')),
        selection_mode VARCHAR(30) NOT NULL DEFAULT 'explicit' CHECK (selection_mode IN ('explicit', 'kanban_column', 'filters')),
        selection_payload JSONB DEFAULT '{}'::jsonb,
        delay_seconds INTEGER DEFAULT 0,
        start_at TIMESTAMP WITH TIME ZONE,
        recurrence VARCHAR(10) NOT NULL DEFAULT 'none' CHECK (recurrence IN ('none', 'daily', 'weekly', 'monthly')),
        timezone VARCHAR(80),
        next_run_at TIMESTAMP WITH TIME ZONE,
        last_run_at TIMESTAMP WITH TIME ZONE,
        max_messages_per_period INTEGER,
        period_unit VARCHAR(10) CHECK (period_unit IN ('minute', 'hour', 'day', 'week', 'month')),
        paused_at TIMESTAMP WITH TIME ZONE,
        cancelled_at TIMESTAMP WITH TIME ZONE,
        completed_at TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    DO $$
    BEGIN
      IF to_regclass('public.bulk_campaigns') IS NOT NULL THEN
        ALTER TABLE bulk_campaigns
          ADD COLUMN IF NOT EXISTS connection_id UUID REFERENCES connections(id) ON DELETE SET NULL;
      END IF;
    END $$;

    CREATE INDEX IF NOT EXISTS idx_bulk_campaigns_tenant ON bulk_campaigns(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_bulk_campaigns_next_run ON bulk_campaigns(next_run_at);
    CREATE INDEX IF NOT EXISTS idx_bulk_campaigns_status ON bulk_campaigns(status);
    CREATE INDEX IF NOT EXISTS idx_bulk_campaigns_connection ON bulk_campaigns(connection_id);

    ALTER TABLE bulk_campaigns ENABLE ROW LEVEL SECURITY;
    CREATE POLICY IF NOT EXISTS "Service role has full access bulk_campaigns" ON bulk_campaigns FOR ALL USING (true);

    CREATE TABLE IF NOT EXISTS bulk_campaign_recipients (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        campaign_id UUID NOT NULL REFERENCES bulk_campaigns(id) ON DELETE CASCADE,
        run_id UUID,
        contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
        contact_phone VARCHAR(50) NOT NULL,
        contact_name VARCHAR(255),
        status VARCHAR(20) NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'sending', 'sent', 'failed', 'skipped')),
        scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
        locked_at TIMESTAMP WITH TIME ZONE,
        locked_by VARCHAR(120),
        attempts INTEGER DEFAULT 0,
        message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
        sent_at TIMESTAMP WITH TIME ZONE,
        error TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_bulk_recipients_tenant ON bulk_campaign_recipients(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_bulk_recipients_campaign ON bulk_campaign_recipients(campaign_id);
    CREATE INDEX IF NOT EXISTS idx_bulk_recipients_due ON bulk_campaign_recipients(status, scheduled_at);
    CREATE INDEX IF NOT EXISTS idx_bulk_recipients_message ON bulk_campaign_recipients(message_id);

    ALTER TABLE bulk_campaign_recipients ENABLE ROW LEVEL SECURITY;
    CREATE POLICY IF NOT EXISTS "Service role has full access bulk_campaign_recipients" ON bulk_campaign_recipients FOR ALL USING (true);

    CREATE TABLE IF NOT EXISTS bulk_campaign_runs (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        campaign_id UUID NOT NULL REFERENCES bulk_campaigns(id) ON DELETE CASCADE,
        scheduled_for TIMESTAMP WITH TIME ZONE,
        started_at TIMESTAMP WITH TIME ZONE,
        finished_at TIMESTAMP WITH TIME ZONE,
        status VARCHAR(20) NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_bulk_runs_tenant ON bulk_campaign_runs(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_bulk_runs_campaign ON bulk_campaign_runs(campaign_id);
    CREATE INDEX IF NOT EXISTS idx_bulk_runs_created_at ON bulk_campaign_runs(created_at DESC);

    ALTER TABLE bulk_campaign_runs ENABLE ROW LEVEL SECURITY;
    CREATE POLICY IF NOT EXISTS "Service role has full access bulk_campaign_runs" ON bulk_campaign_runs FOR ALL USING (true);

    DO $$
    BEGIN
      IF to_regclass('public.bulk_campaign_recipients') IS NOT NULL THEN
        ALTER TABLE bulk_campaign_recipients
          ADD CONSTRAINT IF NOT EXISTS fk_bulk_recipients_run
          FOREIGN KEY (run_id) REFERENCES bulk_campaign_runs(id) ON DELETE SET NULL;
      END IF;
    END $$;
    """
    timeout_seconds = float((os.getenv("STARTUP_SCHEMA_TIMEOUT_SECONDS") or "10").strip() or "10")
    try:
        await asyncio.wait_for(
            asyncio.to_thread(lambda: supabase.rpc("exec_sql", {"sql": sql}).execute()),
            timeout=timeout_seconds,
        )
    except Exception as e:
        logger.warning(f"Auto messages schema not ensured (exec_sql unavailable?): {e}")
    _ensure_offline_flush_task_started()
    _ensure_bulk_worker_task_started()

# ==================== MODELS (defined early for login endpoint) ====================

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    user: dict
    token: str
    maintenance: Optional[dict] = None

class MaintenanceAttachment(BaseModel):
    url: str
    name: Optional[str] = None
    type: Optional[str] = None
    size: Optional[int] = None

class MaintenanceSettings(BaseModel):
    enabled: bool = False
    messageHtml: str = ""
    attachments: List[MaintenanceAttachment] = []
    updatedAt: Optional[str] = None

class MaintenanceSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    messageHtml: Optional[str] = None
    attachments: Optional[List[MaintenanceAttachment]] = None

# JWT Secret (needed for login)
JWT_SECRET = (
    os.getenv("JWT_SECRET")
    or os.getenv("APP_JWT_SECRET")
    or "whatsapp-crm-secret-key-2025"
).strip()

_PASSWORD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _looks_like_bcrypt_hash(value: str) -> bool:
    s = (value or "").strip()
    return s.startswith("$2a$") or s.startswith("$2b$") or s.startswith("$2y$")

def _verify_password_and_maybe_upgrade(plain_password: str, stored_hash: Any) -> Tuple[bool, Optional[str]]:
    plain = str(plain_password or "")
    stored = str(stored_hash or "")
    if not stored or not plain:
        return False, None

    if _looks_like_bcrypt_hash(stored):
        try:
            ok = bool(_PASSWORD_CONTEXT.verify(plain, stored))
        except Exception:
            return False, None
        if ok and _PASSWORD_CONTEXT.needs_update(stored):
            try:
                return True, _PASSWORD_CONTEXT.hash(plain)
            except Exception:
                return True, None
        return ok, None

    if hmac.compare_digest(stored, plain):
        try:
            return True, _PASSWORD_CONTEXT.hash(plain)
        except Exception:
            return True, None

    return False, None

def _normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()

def create_token(user_id: str, email: str, role: str, tenant_id: Optional[str] = None):
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "exp": datetime.utcnow().timestamp() + 86400 * 7  # 7 days
    }
    if tenant_id:
        payload["tenant_id"] = tenant_id
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

    return "https://altarcrm.up.railway.app"

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
    if not _DEBUG_ENDPOINTS_ENABLED:
        raise HTTPException(status_code=404, detail="Not Found")
    return {"message": "Direct login endpoint works", "received": data}

# OPTIONS handler for CORS preflight
@app.options("/api/auth/login")
async def login_options():
    return {"message": "OK"}

# DIRECT ROUTE FOR LOGIN (FIX FOR 405)
@app.post("/api/auth/login", response_model=LoginResponse)
async def direct_login(request: LoginRequest, response: Response, http_request: Request):
    """Direct Login path to avoid Router/Prefix issues"""
    email = _normalize_email(request.email)
    password = str(request.password or "").strip()
    logger.info(f"Login attempt for: {email}")

    def _query_user():
        return (
            supabase.table("users")
            .select("*")
            .eq("email", email)
            .execute()
        )

    try:
        result = await asyncio.to_thread(_query_user)
    except Exception as e:
        logger.exception("Login failed (database error)")
        if _is_supabase_not_configured_error(e):
            raise HTTPException(status_code=500, detail="Supabase não configurado no backend.")
        if _is_missing_table_or_schema_error(e, "users"):
            raise HTTPException(status_code=503, detail="Banco de dados sem tabela de usuários.")
        if _is_transient_db_error(e):
            raise HTTPException(status_code=503, detail="Banco de dados indisponível.")
        raise HTTPException(status_code=503, detail="Serviço de autenticação indisponível.")

    data = getattr(result, "data", None)
    if not data:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    user = data[0]
    ok, upgraded_hash = _verify_password_and_maybe_upgrade(password, user.get("password_hash"))
    if not ok:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    if upgraded_hash:
        def _upgrade_password_hash():
            try:
                supabase.table("users").update({"password_hash": upgraded_hash}).eq("id", user["id"]).execute()
            except Exception:
                return
        await asyncio.to_thread(_upgrade_password_hash)

    token = create_token(user["id"], user["email"], user["role"], user.get("tenant_id"))

    proto = (http_request.headers.get("x-forwarded-proto") or http_request.url.scheme or "http").strip().lower()
    is_secure = proto == "https"
    cookie_samesite = "none" if is_secure else "lax"
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=is_secure,
        samesite=cookie_samesite,
        max_age=86400 * 7,
        path="/",
    )

    user_response = {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "tenantId": user.get("tenant_id"),
        "avatar": user.get("avatar"),
        "jobTitle": user.get("job_title"),
        "department": user.get("department"),
        "signatureEnabled": user.get("signature_enabled", True),
        "signatureIncludeTitle": user.get("signature_include_title", False),
        "signatureIncludeDepartment": user.get("signature_include_department", False),
        "createdAt": user.get("created_at"),
    }

    maintenance = None
    try:
        if str(user.get("role") or "").strip().lower() != "superadmin":
            settings = _get_maintenance_settings()
            if settings.get("enabled"):
                maintenance = settings
    except Exception:
        maintenance = None

    return {"user": user_response, "token": token, "maintenance": maintenance}


@app.post("/api/auth/logout")
async def auth_logout(response: Response):
    response.delete_cookie(key="access_token", path="/")
    return {"success": True}

# Create a router with the /api prefix, ensuring trailing slash handling
api_router = APIRouter(prefix="/api")

# Security
security = HTTPBearer(auto_error=False)
# JWT_SECRET already defined above

# Configure logging
logging.basicConfig(level=logging.INFO)

def _get_whatsapp_container():
    return get_whatsapp_container()

def _get_whatsapp_provider(provider_id: str):
    return _get_whatsapp_container().registry.get(provider_id)

def _make_provider_ctx(*, tenant_id: str, provider: str, instance_name: str, correlation_id: str = None):
    container = _get_whatsapp_container()
    log_ctx = LogContext(
        tenant_id=str(tenant_id or ""),
        provider=str(provider or ""),
        instance_name=str(instance_name or ""),
        correlation_id=str(correlation_id) if correlation_id else None,
    )
    return container, ProviderContext(obs=container.obs, log_ctx=log_ctx)


def _parse_provider_webhook(provider: str, instance_name: str, payload: dict) -> dict:
    provider_id = str(provider or "").strip().lower()
    if not provider_id:
        return evolution_api.parse_webhook_message(payload)
    try:
        container, ctx = _make_provider_ctx(
            tenant_id="",
            provider=provider_id,
            instance_name=instance_name,
            correlation_id="webhook",
        )
        provider_obj = container.registry.get(provider_id)
        event = provider_obj.parse_webhook(ctx, payload)
        data = event.data
        if isinstance(data, dict):
            return data
        return {"event": event.event, "instance": event.instance, "data": data}
    except Exception:
        if provider_id == "evolution":
            return evolution_api.parse_webhook_message(payload)
        return {"event": str(payload.get("event") or "unknown"), "instance": instance_name, "data": payload}

def _resolve_provider_webhook_url(request: Request, provider: str, instance_name: str) -> str:
    base = resolve_public_base_url(request)
    return f"{base}/api/webhooks/{provider}/{instance_name}"

def _is_connected_state(provider: str, state: dict) -> bool:
    pid = str(provider or "").strip().lower()
    if pid == "evolution":
        instance_state = (state.get("instance", {}) or {}).get("state", "")
        return str(instance_state or "").strip().lower() in {"open", "connected"}
    if pid == "uazapi":
        status = (
            state.get("status")
            or state.get("connectionStatus")
            or (state.get("instance", {}) or {}).get("status")
            or (state.get("instance", {}) or {}).get("state")
        )
        return str(status or "").strip().lower() in {"connected", "open"}
    return False

def _extract_uazapi_instance_token(obj: Any) -> Optional[str]:
    token_keys = {
        "apikey",
        "api_key",
        "token",
        "instance_token",
        "instancetoken",
        "instance-token",
        "api_token",
        "apitoken",
    }

    def walk(value: Any, depth: int) -> Optional[str]:
        if depth > 6:
            return None
        if isinstance(value, dict):
            for k, v in value.items():
                k_norm = str(k or "").strip().lower()
                if "admin" not in k_norm and k_norm in token_keys:
                    if isinstance(v, str) and v.strip():
                        return v.strip()
                found = walk(v, depth + 1)
                if found:
                    return found
            return None
        if isinstance(value, list):
            for item in value:
                found = walk(item, depth + 1)
                if found:
                    return found
            return None
        return None

    return walk(obj, 0)


def _extract_qrcode_value(obj: Any) -> Optional[str]:
    if not isinstance(obj, dict):
        return None
    base64 = obj.get("base64")
    if isinstance(base64, str) and base64.strip():
        return base64.strip()

    qrcode = obj.get("qrcode") or obj.get("qr") or obj.get("qrCode") or obj.get("qr_code")
    if isinstance(qrcode, str) and qrcode.strip():
        return qrcode.strip()
    if isinstance(qrcode, dict):
        nested = qrcode.get("base64") or qrcode.get("qrcode") or qrcode.get("qr") or qrcode.get("qrCode") or qrcode.get("qr_code")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()

    for k in ("instance", "data", "response"):
        nested_obj = obj.get(k)
        if isinstance(nested_obj, dict):
            val = _extract_qrcode_value(nested_obj)
            if val:
                return val
    return None

def _whatsapp_http_error(e: Exception) -> HTTPException:
    if isinstance(e, ProviderNotFoundError):
        return HTTPException(status_code=400, detail=str(e))
    if isinstance(e, WhatsAppError):
        status = 502 if e.transient else 400
        detail = str(e)
        details = e.details if isinstance(e.details, dict) else {}
        provider = str(details.get("provider") or "").strip()
        provider_status = details.get("status_code")
        body = details.get("body")
        method = str(details.get("method") or "").strip().upper()
        url = str(details.get("url") or "").strip()
        if provider and body:
            body_str = str(body)
            if len(body_str) > 1200:
                body_str = body_str[:1200]
            if provider_status is not None:
                detail = f"{detail} ({provider} {provider_status}): {body_str}"
            else:
                detail = f"{detail} ({provider}): {body_str}"
        if provider and url:
            suffix = f"{method} {url}" if method else url
            if len(suffix) > 380:
                suffix = suffix[:380]
            detail = f"{detail} [{suffix}]"
        return HTTPException(status_code=status, detail=detail)
    return HTTPException(status_code=400, detail=str(e))

_DB_WRITE_QUEUE_MAX = int(os.getenv("DB_WRITE_QUEUE_MAX", "2000") or "2000")
_DB_WRITE_QUEUE: "deque[dict]" = deque(maxlen=max(100, _DB_WRITE_QUEUE_MAX))
_CONTACTS_CACHE_BY_TENANT: Dict[str, dict] = {}
_CONTACT_CACHE_BY_ID: Dict[str, dict] = {}
_CONTACT_CACHE_BY_TENANT_PHONE: Dict[str, dict] = {}
_TENANT_USER_NAMES_CACHE: Dict[str, Set[str]] = {}
_OFFLINE_FLUSH_TASK_STARTED = False
_BULK_WORKER_TASK_STARTED = False
_BULK_WORKER_ID = hashlib.sha1(f"{os.getpid()}:{time.time()}".encode("utf-8")).hexdigest()[:12]

def _is_transient_db_error(exc: Exception) -> bool:
    s = str(exc or "").lower()
    transient_markers = [
        "timeout",
        "timed out",
        "temporarily unavailable",
        "connection refused",
        "connection reset",
        "connection error",
        "network",
        "dns",
        "name or service not known",
        "failed to establish a new connection",
        "server disconnected",
        "502",
        "503",
        "504",
        "bad gateway",
        "gateway timeout",
        "service unavailable",
    ]
    return any(m in s for m in transient_markers)

def _is_missing_table_or_schema_error(exc: Exception, table_name: str) -> bool:
    s = str(exc or "").lower()
    t = (table_name or "").lower()
    if not t:
        return False
    markers = [
        "does not exist",
        "undefined table",
        "could not find the table",
        "relation",
        "pgrst",
        "not found",
    ]
    return t in s and any(m in s for m in markers)

def _is_supabase_not_configured_error(exc: Exception) -> bool:
    s = str(exc or "").lower()
    return "supabase não configurado" in s or "supabase nao configurado" in s

def _db_call_with_retry(op_name: str, fn: Callable[[], Any], max_attempts: int = 4) -> Any:
    try:
        asyncio.get_running_loop()
        in_event_loop = True
    except RuntimeError:
        in_event_loop = False

    if in_event_loop:
        max_attempts = 1

    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if attempt >= max_attempts or not _is_transient_db_error(e):
                raise
            sleep_s = min(2.0, 0.15 * (2 ** (attempt - 1)))
            logger.warning(f"{op_name} falhou (tentativa {attempt}/{max_attempts}): {e}")
            time.sleep(sleep_s)
    raise last_exc or Exception(f"{op_name} falhou")

def _queue_db_write(operation: dict) -> None:
    try:
        _DB_WRITE_QUEUE.append({
            **(operation or {}),
            "queued_at": datetime.utcnow().isoformat()
        })
    except Exception:
        return

async def _flush_db_write_queue_once() -> int:
    processed = 0
    while _DB_WRITE_QUEUE:
        op = _DB_WRITE_QUEUE[0]
        try:
            kind = op.get("kind")
            table = op.get("table")
            if kind == "insert":
                _db_call_with_retry(f"flush.insert.{table}", lambda: supabase.table(table).insert(op.get("data") or {}).execute())
            elif kind == "update":
                q = supabase.table(table).update(op.get("data") or {})
                for filt in (op.get("filters") or []):
                    if isinstance(filt, dict) and filt.get("op") == "eq":
                        q = q.eq(filt.get("field"), filt.get("value"))
                _db_call_with_retry(f"flush.update.{table}", lambda: q.execute())
            elif kind == "webhook_event":
                instance_name = op.get("instance_name")
                payload = op.get("payload")
                if instance_name and isinstance(payload, dict):
                    await _process_evolution_webhook(instance_name, payload, from_queue=True)
            _DB_WRITE_QUEUE.popleft()
            processed += 1
        except Exception as e:
            if _is_transient_db_error(e):
                break
            _DB_WRITE_QUEUE.popleft()
            processed += 1
    return processed

async def _flush_db_write_queue_loop() -> None:
    while True:
        try:
            await _flush_db_write_queue_once()
        except Exception:
            pass
        await asyncio.sleep(2.5)

async def _bulk_campaign_worker_loop() -> None:
    enabled = (os.getenv("BULK_WORKER_ENABLED") or "").strip().lower()
    if enabled in {"0", "false", "no", "off"}:
        while True:
            await asyncio.sleep(60)

    poll_s = float(os.getenv("BULK_WORKER_POLL_INTERVAL_SECONDS", "1.0") or "1.0")
    poll_s = max(0.25, min(10.0, poll_s))

    while True:
        try:
            await _bulk_campaign_worker_tick()
        except Exception as e:
            logger.error(f"Bulk worker tick error: {e}")
        await asyncio.sleep(poll_s)

async def _bulk_campaign_worker_tick() -> None:
    now = datetime.utcnow().isoformat()

    try:
        due = (
            supabase.table("bulk_campaigns")
            .select("id, tenant_id, status, next_run_at")
            .in_("status", ["scheduled"])
            .lte("next_run_at", now)
            .order("next_run_at", desc=False)
            .limit(25)
            .execute()
        )
    except Exception:
        due = None

    for c in (getattr(due, "data", None) or []):
        cid = c.get("id")
        if not cid:
            continue
        try:
            await _bulk_begin_campaign_run(cid)
        except Exception as e:
            logger.warning(f"Bulk begin run failed for {cid}: {e}")

    batch = int(os.getenv("BULK_WORKER_SEND_BATCH", "10") or "10")
    batch = max(1, min(50, batch))

    try:
        ready = (
            supabase.table("bulk_campaign_recipients")
            .select("id, campaign_id, tenant_id, contact_id, contact_phone, contact_name, scheduled_at, attempts")
            .eq("status", "scheduled")
            .lte("scheduled_at", now)
            .order("scheduled_at", desc=False)
            .limit(batch)
            .execute()
        )
    except Exception:
        ready = None

    for r in (getattr(ready, "data", None) or []):
        rid = r.get("id")
        if not rid:
            continue
        try:
            locked = (
                supabase.table("bulk_campaign_recipients")
                .update({"status": "sending", "locked_at": now, "locked_by": _BULK_WORKER_ID, "attempts": int(r.get("attempts") or 0) + 1, "updated_at": now})
                .eq("id", rid)
                .eq("status", "scheduled")
                .execute()
            )
            if not (getattr(locked, "data", None) or []):
                continue
        except Exception:
            continue
        try:
            await _bulk_send_recipient_message(rid)
        except Exception as e:
            try:
                supabase.table("bulk_campaign_recipients").update({"status": "failed", "error": str(e)[:800], "updated_at": now}).eq("id", rid).execute()
            except Exception:
                pass

def _bulk_parse_dt(value: Any) -> Optional[datetime]:
    s = str(value or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None

def _bulk_normalize_phone(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    return digits or raw

def _bulk_get_contact_row(tenant_id: str, contact_id: Optional[str], phone: Optional[str]) -> Optional[dict]:
    try:
        if contact_id:
            r = supabase.table("contacts").select("*").eq("id", contact_id).limit(1).execute()
            if r.data and (r.data[0].get("tenant_id") == tenant_id):
                return r.data[0]
    except Exception:
        pass
    p = _bulk_normalize_phone(phone)
    if not p:
        return None
    try:
        r = supabase.table("contacts").select("*").eq("tenant_id", tenant_id).eq("phone", p).limit(1).execute()
        if r.data:
            return r.data[0]
    except Exception:
        return None
    return None

def _bulk_get_or_create_conversation(tenant_id: str, phone: str, contact_name: Optional[str], contact_id: Optional[str], connection_id: Optional[str] = None) -> dict:
    normalized_phone = _bulk_normalize_phone(phone)
    if not normalized_phone:
        raise Exception("Telefone inválido")
    existing_q = (
        supabase.table("conversations")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("contact_phone", normalized_phone)
    )
    if connection_id:
        existing_q = existing_q.eq("connection_id", connection_id)
    existing = existing_q.limit(1).execute()
    if existing.data:
        return existing.data[0]

    if connection_id:
        conn_result = (
            supabase.table("connections")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("id", connection_id)
            .limit(1)
            .execute()
        )
    else:
        conn_result = (
            supabase.table("connections")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("provider", "evolution")
            .eq("status", "connected")
            .limit(1)
            .execute()
        )
        if not conn_result.data:
            conn_result = supabase.table("connections").select("*").eq("tenant_id", tenant_id).limit(1).execute()
    if not conn_result.data:
        raise Exception("Nenhuma conexão disponível para iniciar conversa")
    connection = conn_result.data[0]
    if connection_id:
        conn_status = str(connection.get("status") or "").strip().lower()
        if conn_status not in {"connected", "open"}:
            raise Exception("Conexão selecionada está desconectada")

    resolved_name = (contact_name or "").strip()
    if not resolved_name:
        resolved_name = normalized_phone

    now = datetime.utcnow().isoformat()
    conv_data = {
        "tenant_id": tenant_id,
        "connection_id": connection.get("id"),
        "contact_phone": normalized_phone,
        "contact_name": resolved_name,
        "contact_avatar": None,
        "status": "open",
        "unread_count": 0,
        "last_message_at": now,
        "last_message_preview": "",
    }
    created = supabase.table("conversations").insert(conv_data).execute()
    if not created.data:
        raise Exception("Erro ao criar conversa")
    return created.data[0]

async def _bulk_begin_campaign_run(campaign_id: str) -> None:
    now_dt = datetime.utcnow()
    now = now_dt.isoformat()

    locked = (
        supabase.table("bulk_campaigns")
        .update({"status": "running", "last_run_at": now, "updated_at": now})
        .eq("id", campaign_id)
        .eq("status", "scheduled")
        .execute()
    )
    if not (getattr(locked, "data", None) or []):
        return

    camp_r = supabase.table("bulk_campaigns").select("*").eq("id", campaign_id).limit(1).execute()
    if not camp_r.data:
        return
    campaign = camp_r.data[0]
    tenant_id = str(campaign.get("tenant_id") or "").strip()
    if not tenant_id:
        return

    start_dt = _bulk_parse_dt(campaign.get("start_at")) or now_dt
    scheduled_for = campaign.get("next_run_at") or start_dt.isoformat()

    run_r = (
        supabase.table("bulk_campaign_runs")
        .insert({
            "tenant_id": tenant_id,
            "campaign_id": campaign_id,
            "scheduled_for": scheduled_for,
            "started_at": now,
            "status": "running",
        })
        .execute()
    )
    if not run_r.data:
        return
    run_id = run_r.data[0].get("id")

    selection_mode = str(campaign.get("selection_mode") or "explicit").strip().lower()
    selection_payload = campaign.get("selection_payload") or {}
    if not isinstance(selection_payload, dict):
        selection_payload = {}

    contacts: List[dict] = []
    if selection_mode == "explicit":
        raw_ids = selection_payload.get("contact_ids") or selection_payload.get("contactIds") or selection_payload.get("contacts")
        ids: List[str] = []
        if isinstance(raw_ids, list):
            for item in raw_ids:
                if isinstance(item, str) and item.strip():
                    ids.append(item.strip())
                elif isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("id").strip():
                    ids.append(item.get("id").strip())
        ids = list(dict.fromkeys(ids))
        if ids:
            try:
                c_r = (
                    supabase.table("contacts")
                    .select("*")
                    .eq("tenant_id", tenant_id)
                    .in_("id", ids)
                    .limit(min(5000, max(50, len(ids))))
                    .execute()
                )
                contacts = [row for row in (c_r.data or []) if isinstance(row, dict)]
            except Exception:
                contacts = []

    if not contacts:
        try:
            supabase.table("bulk_campaign_runs").update({"status": "completed", "finished_at": now}).eq("id", run_id).execute()
        except Exception:
            pass
        try:
            supabase.table("bulk_campaigns").update({"status": "completed", "completed_at": now, "next_run_at": None, "updated_at": now}).eq("id", campaign_id).execute()
        except Exception:
            pass
        return

    schedule = _bulk_build_schedule(
        start_dt,
        len(contacts),
        delay_seconds=int(campaign.get("delay_seconds") or 0),
        max_messages_per_period=campaign.get("max_messages_per_period"),
        period_unit=campaign.get("period_unit"),
    )

    rows: List[dict] = []
    for idx, contact in enumerate(contacts):
        when = schedule[idx] if idx < len(schedule) else start_dt
        phone = _bulk_normalize_phone(contact.get("phone"))
        if not phone:
            continue
        rows.append({
            "tenant_id": tenant_id,
            "campaign_id": campaign_id,
            "run_id": run_id,
            "contact_id": contact.get("id"),
            "contact_phone": phone,
            "contact_name": (contact.get("name") or contact.get("full_name") or "").strip() or None,
            "status": "scheduled",
            "scheduled_at": when.isoformat(),
            "created_at": now,
            "updated_at": now,
        })

    if not rows:
        try:
            supabase.table("bulk_campaign_runs").update({"status": "completed", "finished_at": now}).eq("id", run_id).execute()
        except Exception:
            pass
        try:
            supabase.table("bulk_campaigns").update({"status": "completed", "completed_at": now, "next_run_at": None, "updated_at": now}).eq("id", campaign_id).execute()
        except Exception:
            pass
        return

    for i in range(0, len(rows), 200):
        supabase.table("bulk_campaign_recipients").insert(rows[i:i + 200]).execute()

    next_dt = _bulk_compute_next_run_at(campaign.get("recurrence"), start_dt)
    try:
        supabase.table("bulk_campaigns").update({
            "next_run_at": (next_dt.isoformat() if next_dt else None),
            "updated_at": now,
        }).eq("id", campaign_id).execute()
    except Exception:
        pass

async def _bulk_maybe_finalize_run(run_id: Optional[str], campaign_id: Optional[str]) -> None:
    rid = str(run_id or "").strip()
    cid = str(campaign_id or "").strip()
    if not rid or not cid:
        return
    try:
        remaining = (
            supabase.table("bulk_campaign_recipients")
            .select("id", count="exact")
            .eq("run_id", rid)
            .in_("status", ["scheduled", "sending"])
            .limit(1)
            .execute()
        )
        if int(getattr(remaining, "count", 0) or 0) > 0:
            return
    except Exception:
        return

    now = datetime.utcnow().isoformat()
    try:
        supabase.table("bulk_campaign_runs").update({"status": "completed", "finished_at": now}).eq("id", rid).execute()
    except Exception:
        pass

    try:
        camp_r = supabase.table("bulk_campaigns").select("status, next_run_at").eq("id", cid).limit(1).execute()
        if not camp_r.data:
            return
        current = camp_r.data[0] or {}
        status = str(current.get("status") or "").strip().lower()
        next_run_at = current.get("next_run_at")
        if status in {"cancelled", "paused"}:
            return
        if next_run_at:
            supabase.table("bulk_campaigns").update({"status": "scheduled", "updated_at": now}).eq("id", cid).execute()
        else:
            supabase.table("bulk_campaigns").update({"status": "completed", "completed_at": now, "updated_at": now}).eq("id", cid).execute()
    except Exception:
        return

async def _bulk_send_recipient_message(recipient_id: str) -> None:
    now = datetime.utcnow().isoformat()
    rec_r = supabase.table("bulk_campaign_recipients").select("*").eq("id", recipient_id).limit(1).execute()
    if not rec_r.data:
        return
    recipient = rec_r.data[0] or {}
    if str(recipient.get("status") or "").strip().lower() != "sending":
        return

    campaign_id = recipient.get("campaign_id")
    camp_r = supabase.table("bulk_campaigns").select("*").eq("id", campaign_id).limit(1).execute()
    if not camp_r.data:
        supabase.table("bulk_campaign_recipients").update({"status": "failed", "error": "Campanha não encontrada", "updated_at": now}).eq("id", recipient_id).execute()
        return
    campaign = camp_r.data[0] or {}

    camp_status = str(campaign.get("status") or "").strip().lower()
    if camp_status in {"paused", "cancelled"}:
        supabase.table("bulk_campaign_recipients").update({"status": "skipped", "error": f"Campanha {camp_status}", "updated_at": now}).eq("id", recipient_id).execute()
        await _bulk_maybe_finalize_run(recipient.get("run_id"), campaign_id)
        return

    tenant_id = str(recipient.get("tenant_id") or campaign.get("tenant_id") or "").strip()
    if not tenant_id:
        supabase.table("bulk_campaign_recipients").update({"status": "failed", "error": "Tenant inválido", "updated_at": now}).eq("id", recipient_id).execute()
        return

    contact_phone = recipient.get("contact_phone")
    contact_row = _bulk_get_contact_row(tenant_id, recipient.get("contact_id"), contact_phone)
    ctx = _bulk_template_ctx_from_contact(contact_row or {"name": recipient.get("contact_name"), "phone": contact_phone})
    body = _render_template_text(str(campaign.get("template_body") or ""), ctx).strip()
    if not body:
        supabase.table("bulk_campaign_recipients").update({"status": "failed", "error": "Mensagem vazia após template", "updated_at": now}).eq("id", recipient_id).execute()
        await _bulk_maybe_finalize_run(recipient.get("run_id"), campaign_id)
        return

    try:
        _enforce_messages_limit(tenant_id)
    except Exception as e:
        supabase.table("bulk_campaign_recipients").update({"status": "failed", "error": str(e)[:800], "updated_at": now}).eq("id", recipient_id).execute()
        await _bulk_maybe_finalize_run(recipient.get("run_id"), campaign_id)
        return

    contact_name = (recipient.get("contact_name") or (contact_row.get("name") if isinstance(contact_row, dict) else None) or (contact_row.get("full_name") if isinstance(contact_row, dict) else None))
    campaign_connection_id = str(campaign.get("connection_id") or campaign.get("connectionId") or "").strip() or None
    try:
        conv = _bulk_get_or_create_conversation(
            tenant_id,
            str(contact_phone or ""),
            contact_name,
            recipient.get("contact_id"),
            connection_id=campaign_connection_id,
        )
    except Exception as e:
        supabase.table("bulk_campaign_recipients").update({"status": "failed", "error": str(e)[:800], "updated_at": now}).eq("id", recipient_id).execute()
        await _bulk_maybe_finalize_run(recipient.get("run_id"), campaign_id)
        return

    conv_r = supabase.table("conversations").select("*, connections(*)").eq("id", conv.get("id")).limit(1).execute()
    if not conv_r.data:
        supabase.table("bulk_campaign_recipients").update({"status": "failed", "error": "Conversa não encontrada", "updated_at": now}).eq("id", recipient_id).execute()
        await _bulk_maybe_finalize_run(recipient.get("run_id"), campaign_id)
        return
    conversation = conv_r.data[0] or {}
    connection = conversation.get("connections") or {}
    is_connected = str(connection.get("status") or "").lower() in ["connected", "open"]
    instance_name = connection.get("instance_name")
    phone = conversation.get("contact_phone")

    provider_id = str(connection.get("provider") or "").strip().lower()
    if not (provider_id and is_connected and instance_name and phone):
        supabase.table("bulk_campaign_recipients").update({"status": "failed", "error": "Conexão indisponível", "updated_at": now}).eq("id", recipient_id).execute()
        await _bulk_maybe_finalize_run(recipient.get("run_id"), campaign_id)
        return

    data = {
        "conversation_id": conversation.get("id"),
        "content": body,
        "type": "text",
        "direction": "outbound",
        "status": "sent",
    }
    inserted = supabase.table("messages").insert(data).execute()
    if not inserted.data:
        supabase.table("bulk_campaign_recipients").update({"status": "failed", "error": "Falha ao salvar mensagem", "updated_at": now}).eq("id", recipient_id).execute()
        await _bulk_maybe_finalize_run(recipient.get("run_id"), campaign_id)
        return
    message_id = inserted.data[0].get("id")

    try:
        supabase.table("conversations").update({
            "last_message_at": datetime.utcnow().isoformat(),
            "last_message_preview": body[:50],
        }).eq("id", conversation.get("id")).execute()
    except Exception:
        pass

    try:
        if tenant_id:
            tenant = supabase.table("tenants").select("messages_this_month").eq("id", tenant_id).limit(1).execute()
            if tenant.data:
                new_count = int(tenant.data[0].get("messages_this_month") or 0) + 1
                supabase.table("tenants").update({"messages_this_month": new_count}).eq("id", tenant_id).execute()
    except Exception:
        pass

    conn_ref = ConnectionRef(
        tenant_id=str(tenant_id or ""),
        provider=provider_id,
        instance_name=str(instance_name or ""),
        phone_number=str(connection.get("phone_number") or "") or None,
        config=connection.get("config") if isinstance(connection.get("config"), dict) else {},
    )
    await send_provider_message(conn_ref, str(phone), body, "text", str(message_id))

    msg_status = None
    try:
        st_r = supabase.table("messages").select("status").eq("id", message_id).limit(1).execute()
        if st_r.data:
            msg_status = st_r.data[0].get("status")
    except Exception:
        msg_status = None

    if str(msg_status or "").strip().lower() in {"delivered", "sent"}:
        supabase.table("bulk_campaign_recipients").update({
            "status": "sent",
            "message_id": message_id,
            "sent_at": now,
            "updated_at": now,
        }).eq("id", recipient_id).execute()
    else:
        supabase.table("bulk_campaign_recipients").update({
            "status": "failed",
            "message_id": message_id,
            "error": "Falha no envio",
            "updated_at": now,
        }).eq("id", recipient_id).execute()

    await _bulk_maybe_finalize_run(recipient.get("run_id"), campaign_id)

def _ensure_offline_flush_task_started() -> None:
    global _OFFLINE_FLUSH_TASK_STARTED
    if _OFFLINE_FLUSH_TASK_STARTED:
        return
    try:
        asyncio.create_task(_flush_db_write_queue_loop())
        _OFFLINE_FLUSH_TASK_STARTED = True
    except Exception:
        _OFFLINE_FLUSH_TASK_STARTED = True

def _ensure_bulk_worker_task_started() -> None:
    global _BULK_WORKER_TASK_STARTED
    if _BULK_WORKER_TASK_STARTED:
        return
    try:
        asyncio.create_task(_bulk_campaign_worker_loop())
        _BULK_WORKER_TASK_STARTED = True
    except Exception:
        _BULK_WORKER_TASK_STARTED = True

def _cache_contact_row(contact_row: dict) -> None:
    if not isinstance(contact_row, dict):
        return
    cid = contact_row.get("id")
    tenant_id = contact_row.get("tenant_id") or contact_row.get("tenantId")
    phone = contact_row.get("phone")
    if cid:
        _CONTACT_CACHE_BY_ID[str(cid)] = contact_row
    if tenant_id and phone:
        _CONTACT_CACHE_BY_TENANT_PHONE[f"{tenant_id}:{phone}"] = contact_row

def _normalize_person_name(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().casefold()

def _get_tenant_user_names(tenant_id: Optional[str]) -> Set[str]:
    tid = str(tenant_id or "").strip()
    if not tid:
        return set()
    cached = _TENANT_USER_NAMES_CACHE.get(tid)
    if isinstance(cached, set):
        return cached
    try:
        result = _db_call_with_retry(
            "users.list_names",
            lambda: supabase.table("users").select("name").eq("tenant_id", tid).limit(250).execute(),
        )
        names: Set[str] = set()
        for row in (getattr(result, "data", None) or []):
            if isinstance(row, dict):
                n = _normalize_person_name(row.get("name"))
                if n:
                    names.add(n)
        _TENANT_USER_NAMES_CACHE[tid] = names
        return names
    except Exception:
        _TENANT_USER_NAMES_CACHE[tid] = set()
        return set()

def _looks_like_system_user_name(value: Any, tenant_id: Optional[str]) -> bool:
    n = _normalize_person_name(value)
    if not n:
        return False
    return n in _get_tenant_user_names(tenant_id)

def _postgrest_error_code(exc: Exception) -> Optional[str]:
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code.strip():
        return code.strip()
    args = getattr(exc, "args", None)
    if isinstance(args, tuple) and args:
        for arg in args:
            if isinstance(arg, dict) and isinstance(arg.get("code"), str) and arg.get("code").strip():
                return arg.get("code").strip()
    s = str(exc)
    if "PGRST" in s:
        m = re.search(r"\b(PGRST\d+)\b", s)
        if m:
            return m.group(1)
    return None


def _is_missing_table_error(exc: Exception, table: str) -> bool:
    if _postgrest_error_code(exc) != "PGRST205":
        return False
    s = str(exc)
    t = str(table or "").strip()
    if not t:
        return False
    return t in s or f"public.{t}" in s


def _auto_messages_missing_table_http() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail=(
            "Configuração do Supabase incompleta: a tabela public.auto_messages não existe. "
            "Execute a migration 004_auto_messages.sql no SQL Editor do Supabase e tente novamente."
        ),
    )


def _bulk_campaigns_missing_table_http(table: str) -> HTTPException:
    t = str(table or "bulk_campaigns").strip() or "bulk_campaigns"
    return HTTPException(
        status_code=503,
        detail=(
            f"Configuração do Supabase incompleta: a tabela public.{t} não existe. "
            "Crie as tabelas de Disparos (bulk_campaigns, bulk_campaign_recipients, bulk_campaign_runs) "
            "no SQL Editor do Supabase e tente novamente."
        ),
    )

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
    config: Optional[dict] = None

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
    provider: Optional[str] = "evolution"
    instance_name: str
    phone: str
    message: str
    type: str = "text"
    media_url: Optional[str] = None
    config: Optional[dict] = None

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
    avatar: Optional[str] = None
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

class BulkCampaignCreate(BaseModel):
    name: str
    template_body: str
    connection_id: Optional[str] = None
    selection_mode: str = "explicit"
    selection_payload: dict = {}
    delay_seconds: int = 0
    start_at: Optional[str] = None
    recurrence: str = "none"
    max_messages_per_period: Optional[int] = None
    period_unit: Optional[str] = None

class BulkCampaignUpdate(BaseModel):
    name: Optional[str] = None
    template_body: Optional[str] = None
    connection_id: Optional[str] = None
    selection_mode: Optional[str] = None
    selection_payload: Optional[dict] = None
    delay_seconds: Optional[int] = None
    start_at: Optional[str] = None
    recurrence: Optional[str] = None
    max_messages_per_period: Optional[int] = None
    period_unit: Optional[str] = None
    status: Optional[str] = None

class BulkCampaignRecipientsSet(BaseModel):
    contact_ids: List[str] = Field(default_factory=list)

class BulkCampaignSchedule(BaseModel):
    start_at: Optional[str] = None
    recurrence: Optional[str] = None
    delay_seconds: Optional[int] = None
    max_messages_per_period: Optional[int] = None
    period_unit: Optional[str] = None

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

# ==================== FLOWS MODELS ====================

class FlowCreate(BaseModel):
    name: str
    description: Optional[str] = None
    nodes: List[dict] = []
    edges: List[dict] = []
    variables: Optional[dict] = None
    status: str = "draft"

class FlowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    nodes: Optional[List[dict]] = None
    edges: Optional[List[dict]] = None
    variables: Optional[dict] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None

class FlowDuplicate(BaseModel):
    name: str
    description: Optional[str] = None


# ==================== AUTH ====================
# Note: create_token is defined at the top of the file

def verify_token(http_request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials if credentials else None
    if not token:
        token = http_request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Token não fornecido")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

def get_user_tenant_id(payload: dict) -> str:
    """Get tenant ID from user"""
    if payload['role'] == 'superadmin':
        return None
    token_tenant_id = payload.get("tenant_id")
    if token_tenant_id:
        return token_tenant_id
    try:
        user = _db_call_with_retry(
            "auth.get_user_tenant_id",
            lambda: supabase.table('users').select('tenant_id').eq('id', payload['user_id']).execute(),
        )
    except Exception as e:
        if _is_missing_table_or_schema_error(e, "users"):
            raise HTTPException(status_code=503, detail="Banco de dados sem tabela de usuários.")
        raise HTTPException(status_code=503, detail="Banco de dados indisponível.")
    if user.data:
        return user.data[0]['tenant_id']
    return None

def _sanitize_html_basic(value: Any) -> str:
    s = str(value or "")
    s = re.sub(r"(?is)<script\\b[^>]*>.*?</script>", "", s)
    s = re.sub(r"(?is)\\son\\w+\\s*=\\s*\"[^\"]*\"", "", s)
    s = re.sub(r"(?is)\\son\\w+\\s*=\\s*'[^']*'", "", s)
    return s.strip()

_SCHEMA_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=int((os.getenv("SCHEMA_EXECUTOR_WORKERS") or "2").strip() or "2")
)
_SYSTEM_SETTINGS_SCHEMA_ENSURED = False

def _ensure_system_settings_schema() -> None:
    global _SYSTEM_SETTINGS_SCHEMA_ENSURED
    if _SYSTEM_SETTINGS_SCHEMA_ENSURED:
        return
    sql = """
    CREATE TABLE IF NOT EXISTS system_settings (
        key TEXT PRIMARY KEY,
        value_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    ALTER TABLE system_settings ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS "Service role full access system_settings" ON system_settings;
    CREATE POLICY "Service role full access system_settings" ON system_settings FOR ALL USING (true) WITH CHECK (true);
    """
    try:
        timeout_s = float(
            (
                os.getenv("SYSTEM_SETTINGS_SCHEMA_TIMEOUT_SECONDS")
                or os.getenv("STARTUP_SCHEMA_TIMEOUT_SECONDS")
                or "3"
            ).strip()
            or "3"
        )
        future = _SCHEMA_EXECUTOR.submit(
            lambda: supabase.rpc("exec_sql", {"sql": sql}).execute()
        )
        future.result(timeout=timeout_s)
        _SYSTEM_SETTINGS_SCHEMA_ENSURED = True
    except Exception:
        return

_SYSTEM_SETTINGS_STORAGE_BUCKET = (os.getenv("SYSTEM_SETTINGS_STORAGE_BUCKET") or "uploads").strip() or "uploads"
_SYSTEM_SETTINGS_STORAGE_PREFIX = (os.getenv("SYSTEM_SETTINGS_STORAGE_PREFIX") or "system_settings").strip().strip("/") or "system_settings"
_SYSTEM_SETTINGS_IN_MEMORY: Dict[str, Any] = {}

def _system_settings_storage_path(key: str) -> str:
    k = (key or "").strip()
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", k) or "settings"
    return f"{_SYSTEM_SETTINGS_STORAGE_PREFIX}/{safe}.json"

def _get_system_setting_json(key: str, default: Any) -> Any:
    _ensure_system_settings_schema()
    try:
        res = supabase.table("system_settings").select("value_json").eq("key", key).execute()
    except Exception:
        res = None
    if getattr(res, "data", None):
        row = res.data[0]
        val = row.get("value_json")
        if val is None:
            return default
        return val
    try:
        path = _system_settings_storage_path(key)
        content = supabase.storage.from_(_SYSTEM_SETTINGS_STORAGE_BUCKET).download(path)
        if isinstance(content, (bytes, bytearray)):
            raw = content.decode("utf-8", errors="replace")
        else:
            raw = str(content or "")
        parsed = json.loads(raw)
        return default if parsed is None else parsed
    except Exception:
        pass
    if key in _SYSTEM_SETTINGS_IN_MEMORY:
        return _SYSTEM_SETTINGS_IN_MEMORY.get(key)
    return default

def _set_system_setting_json(key: str, value_json: Any) -> None:
    _ensure_system_settings_schema()
    now = datetime.utcnow().isoformat()
    payload = {"key": key, "value_json": value_json, "updated_at": now}
    try:
        supabase.table("system_settings").upsert(payload).execute()
        return
    except Exception:
        pass
    path = _system_settings_storage_path(key)
    body = json.dumps(value_json if value_json is not None else {}, ensure_ascii=False).encode("utf-8")
    upload_error: Optional[Exception] = None
    try:
        supabase.storage.from_(_SYSTEM_SETTINGS_STORAGE_BUCKET).upload(
            path,
            body,
            file_options={"content-type": "application/json"},
        )
        return
    except Exception as e:
        upload_error = e
    try:
        supabase.storage.from_(_SYSTEM_SETTINGS_STORAGE_BUCKET).update(
            path,
            body,
            file_options={"content-type": "application/json"},
        )
        return
    except Exception as e:
        logger.error(f"system_settings_write_failed: upload={upload_error} update={e}")
        _SYSTEM_SETTINGS_IN_MEMORY[key] = value_json if value_json is not None else {}
        return

def _normalize_maintenance_settings(value: Any) -> dict:
    base = {"enabled": False, "messageHtml": "", "attachments": [], "updatedAt": None}
    if not isinstance(value, dict):
        return base
    enabled = bool(value.get("enabled"))
    msg = _sanitize_html_basic(value.get("messageHtml"))
    attachments = value.get("attachments")
    if not isinstance(attachments, list):
        attachments = []
    safe_attachments = []
    for a in attachments:
        if not isinstance(a, dict):
            continue
        url = str(a.get("url") or "").strip()
        if not url:
            continue
        safe_attachments.append(
            {
                "url": url,
                "name": (str(a.get("name") or "").strip() or None),
                "type": (str(a.get("type") or "").strip() or None),
                "size": (int(a.get("size")) if isinstance(a.get("size"), int) else None),
            }
        )
    updated_at = value.get("updatedAt")
    if isinstance(updated_at, str) and updated_at.strip():
        updated_at = updated_at.strip()
    else:
        updated_at = None
    return {"enabled": enabled, "messageHtml": msg, "attachments": safe_attachments, "updatedAt": updated_at}

def _get_maintenance_settings() -> dict:
    value = _get_system_setting_json("maintenance", {})
    return _normalize_maintenance_settings(value)

def _update_maintenance_settings(patch: MaintenanceSettingsUpdate) -> dict:
    current = _get_maintenance_settings()
    next_value = {
        "enabled": current.get("enabled", False),
        "messageHtml": current.get("messageHtml", ""),
        "attachments": current.get("attachments", []),
        "updatedAt": datetime.utcnow().isoformat(),
    }
    if patch.enabled is not None:
        next_value["enabled"] = bool(patch.enabled)
    if patch.messageHtml is not None:
        next_value["messageHtml"] = _sanitize_html_basic(patch.messageHtml)
    if patch.attachments is not None:
        next_value["attachments"] = _normalize_maintenance_settings({"attachments": patch.attachments}).get("attachments", [])
    _set_system_setting_json("maintenance", next_value)
    return _normalize_maintenance_settings(next_value)

@api_router.get("/maintenance")
async def get_maintenance(payload: dict = Depends(verify_token)):
    if str(payload.get("role") or "").strip().lower() != "superadmin":
        raise HTTPException(status_code=403, detail="Acesso negado")
    try:
        return _get_maintenance_settings()
    except Exception:
        return {"enabled": False, "messageHtml": "", "attachments": [], "updatedAt": None}

@api_router.patch("/maintenance")
async def update_maintenance(patch: MaintenanceSettingsUpdate, payload: dict = Depends(verify_token)):
    if str(payload.get("role") or "").strip().lower() != "superadmin":
        raise HTTPException(status_code=403, detail="Acesso negado")
    try:
        return _update_maintenance_settings(patch)
    except Exception as e:
        logger.error(f"update_maintenance error: {type(e).__name__}: {e}")
        if _is_supabase_not_configured_error(e):
            raise HTTPException(status_code=503, detail="Supabase não configurado")
        if _is_transient_db_error(e):
            raise HTTPException(status_code=503, detail="Banco de dados indisponível")
        raise HTTPException(status_code=500, detail="Erro ao salvar manutenção")

@api_router.post("/maintenance/upload")
async def upload_maintenance_attachment(
    file: UploadFile = File(...),
    payload: dict = Depends(verify_token),
):
    if str(payload.get("role") or "").strip().lower() != "superadmin":
        raise HTTPException(status_code=403, detail="Acesso negado")
    try:
        content = await file.read()
        file_size = len(content)

        max_size = 10 * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(status_code=400, detail="Arquivo muito grande. Máximo: 10MB")

        file_ext = file.filename.split('.')[-1] if '.' in file.filename else 'bin'
        unique_filename = f"{uuid.uuid4()}.{file_ext}"

        detected = detect_media_kind(
            declared_mime_type=file.content_type,
            filename=file.filename,
            head_bytes=content[:96] if isinstance(content, (bytes, bytearray)) else b"",
        )
        kind = detected.kind if detected.kind in {'image', 'video', 'audio', 'document', 'sticker'} else 'document'
        content_type = detected.mime_type or (file.content_type or 'application/octet-stream')

        if kind == 'image':
            folder = 'images'
        elif kind == 'video':
            folder = 'videos'
        elif kind == 'audio':
            folder = 'audios'
        elif kind == 'sticker':
            folder = 'stickers'
        else:
            folder = 'documents'

        storage_path = f"{folder}/{unique_filename}"
        try:
            supabase.storage.from_('uploads').upload(
                storage_path,
                content,
                file_options={"content-type": content_type}
            )
            public_url = supabase.storage.from_('uploads').get_public_url(storage_path)
        except Exception as storage_error:
            logger.warning(f"Supabase storage error: {storage_error}")
            encoded = base64.b64encode(content).decode('utf-8')
            public_url = f"data:{content_type};base64,{encoded}"

        return {
            "url": public_url,
            "name": file.filename,
            "type": content_type,
            "size": file_size
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Maintenance upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao fazer upload: {str(e)}")

def _get_tenant_plan_limits(tenant_id: str) -> dict:
    default_limits = {"max_instances": 1, "max_messages_month": 500}
    if not tenant_id:
        return default_limits
    try:
        tenant_res = supabase.table("tenants").select("id, plan, plan_id, messages_this_month, connections_count").eq("id", tenant_id).execute()
    except Exception:
        return default_limits
    if not getattr(tenant_res, "data", None):
        return default_limits
    tenant = tenant_res.data[0] or {}
    plan_id = tenant.get("plan_id")
    plan_slug = tenant.get("plan")
    plan_row = None
    try:
        if plan_id:
            plan_res = supabase.table("plans").select("max_instances, max_messages_month").eq("id", plan_id).execute()
            if getattr(plan_res, "data", None):
                plan_row = plan_res.data[0]
        elif plan_slug:
            plan_res = supabase.table("plans").select("max_instances, max_messages_month").eq("slug", plan_slug).execute()
            if getattr(plan_res, "data", None):
                plan_row = plan_res.data[0]
    except Exception:
        plan_row = None
    max_instances = default_limits["max_instances"]
    max_messages_month = default_limits["max_messages_month"]
    if isinstance(plan_row, dict):
        if isinstance(plan_row.get("max_instances"), int):
            max_instances = plan_row["max_instances"]
        if isinstance(plan_row.get("max_messages_month"), int):
            max_messages_month = plan_row["max_messages_month"]
    usage_messages = tenant.get("messages_this_month")
    usage_conns = tenant.get("connections_count")
    return {
        "max_instances": max_instances,
        "max_messages_month": max_messages_month,
        "messages_this_month": int(usage_messages) if isinstance(usage_messages, int) else 0,
        "connections_count": int(usage_conns) if isinstance(usage_conns, int) else 0,
    }

def _enforce_messages_limit(tenant_id: Optional[str]) -> None:
    if not tenant_id:
        return
    snap = _get_tenant_plan_limits(tenant_id)
    limit = snap.get("max_messages_month")
    used = snap.get("messages_this_month", 0)
    if isinstance(limit, int) and limit > 0 and used >= limit:
        raise HTTPException(status_code=403, detail="Limite de mensagens do plano atingido")

def _enforce_connections_limit(tenant_id: Optional[str]) -> None:
    if not tenant_id:
        return
    snap = _get_tenant_plan_limits(tenant_id)
    limit = snap.get("max_instances")
    used = snap.get("connections_count", 0)
    if isinstance(limit, int) and limit > 0 and used >= limit:
        raise HTTPException(status_code=403, detail="Limite de conexões do plano atingido")


def _require_conversation_access(conversation_id: str, payload: dict) -> dict:
    conv = supabase.table('conversations').select('id, tenant_id, assigned_to').eq('id', conversation_id).execute()
    if not conv.data:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")

    row = conv.data[0]
    user_tenant_id = get_user_tenant_id(payload)
    if user_tenant_id and row.get('tenant_id') != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    role = payload.get('role')
    if role == 'agent':
        assigned_to = row.get('assigned_to')
        user_id = payload.get('user_id')
        if assigned_to and assigned_to != user_id:
            raise HTTPException(status_code=403, detail="Acesso negado")

    return row

def safe_insert_audit_log(
    tenant_id: Optional[str],
    actor_user_id: Optional[str],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    metadata: Optional[dict] = None
):
    try:
        _db_call_with_retry(
            "audit_logs.insert",
            lambda: supabase.table('audit_logs').insert({
                'tenant_id': tenant_id,
                'actor_user_id': actor_user_id,
                'action': action,
                'entity_type': entity_type,
                'entity_id': entity_id,
                'metadata': metadata or {}
            }).execute()
        )
    except Exception:
        return

def safe_insert_contact_history(
    tenant_id: Optional[str],
    contact_id: Optional[str],
    changed_by: Optional[str],
    action: str,
    before: Optional[dict],
    after: Optional[dict]
) -> None:
    if not tenant_id or not contact_id:
        return
    try:
        _db_call_with_retry(
            "contact_history.insert",
            lambda: supabase.table('contact_history').insert({
                'tenant_id': tenant_id,
                'contact_id': contact_id,
                'changed_by': changed_by,
                'action': action,
                'before': before,
                'after': after
            }).execute()
        )
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
        'password_hash': _PASSWORD_CONTEXT.hash(str(data.admin_password or "")),
        'name': data.admin_name,
        'role': 'admin',
        'tenant_id': tenant['id'],
        'avatar': f"https://api.dicebear.com/7.x/avataaars/svg?seed={data.admin_email}"
    }
    user_result = supabase.table('users').insert(user_data).execute()
    user = user_result.data[0]
    
    # Generate token
    token = create_token(user['id'], user['email'], user['role'], user.get('tenant_id'))
    
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
    try:
        result = supabase.table('users').select('*').eq('id', payload['user_id']).execute()
    except Exception as e:
        if _is_supabase_not_configured_error(e):
            raise HTTPException(status_code=500, detail="Supabase não configurado no backend.")
        if _is_missing_table_or_schema_error(e, "users"):
            raise HTTPException(status_code=503, detail="Banco de dados sem tabela de usuários.")
        if _is_transient_db_error(e):
            raise HTTPException(status_code=503, detail="Banco de dados indisponível.")
        raise HTTPException(status_code=500, detail="Erro ao carregar usuário.")
    
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
    if data.avatar is not None:
        avatar = (data.avatar or '').strip()
        update_data['avatar'] = avatar or None
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
        user_tenant_id = get_user_tenant_id(payload)
        if not user_tenant_id or str(user_tenant_id) != str(tenant_id):
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
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Acesso negado")
        user_tenant_id = get_user_tenant_id(payload)
        if not user_tenant_id or str(user_tenant_id) != str(tenant_id):
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
    user_tenant_id = get_user_tenant_id(payload)
    if payload.get('role') != 'superadmin':
        if not user_tenant_id:
            raise HTTPException(status_code=403, detail="Tenant não identificado")
        if tenant_id != user_tenant_id:
            raise HTTPException(status_code=403, detail="Acesso negado")
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
    if payload.get('role') not in ['admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Acesso negado")
    user_tenant_id = get_user_tenant_id(payload)
    if payload.get('role') != 'superadmin':
        if not user_tenant_id:
            raise HTTPException(status_code=403, detail="Tenant não identificado")
        if connection.tenant_id != user_tenant_id:
            raise HTTPException(status_code=403, detail="Acesso negado")
    _enforce_connections_limit(connection.tenant_id)
    cfg = connection.config if isinstance(connection.config, dict) else {}
    data = {
        'tenant_id': connection.tenant_id,
        'provider': connection.provider,
        'instance_name': connection.instance_name,
        'phone_number': connection.phone_number or '',
        'status': 'disconnected',
        'webhook_url': '',
        'config': cfg,
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
    if payload.get('role') not in ['admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Acesso negado")
    conn = supabase.table('connections').select('*').eq('id', connection_id).execute()
    if not conn.data:
        raise HTTPException(status_code=404, detail="Conexão não encontrada")
    
    connection = conn.data[0]
    user_tenant_id = get_user_tenant_id(payload)
    if payload.get('role') != 'superadmin' and user_tenant_id and connection.get('tenant_id') != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    provider_id = str(connection.get("provider") or "").strip().lower()
    instance_name = str(connection.get("instance_name") or "").strip()
    if not instance_name or len(instance_name) > 80:
        raise HTTPException(status_code=400, detail="instanceName inválido.")
    for ch in instance_name:
        if not (ch.isalnum() or ch in {"_", "-", "."}):
            raise HTTPException(status_code=400, detail="instanceName inválido.")
    conn_ref = ConnectionRef(
        tenant_id=str(connection.get("tenant_id") or ""),
        provider=provider_id,
        instance_name=instance_name,
        phone_number=str(connection.get("phone_number") or "") or None,
        config=connection.get("config") if isinstance(connection.get("config"), dict) else {},
    )

    container, ctx = _make_provider_ctx(
        tenant_id=conn_ref.tenant_id,
        provider=provider_id,
        instance_name=instance_name,
        correlation_id=f"conn_test:{connection_id}",
    )
    provider = _get_whatsapp_provider(provider_id)

    cfg = conn_ref.config or {}
    token_present = bool(
        str(
            cfg.get("token")
            or cfg.get("instance_token")
            or cfg.get("apikey")
            or cfg.get("api_key")
            or cfg.get("apiKey")
            or ""
        ).strip()
    )
    uazapi_mode = ""
    if provider_id == "uazapi":
        uazapi_mode = str(cfg.get("uazapi_mode") or cfg.get("uazapiMode") or cfg.get("mode") or "").strip().lower()
    allow_create = provider_id == "uazapi" and (
        uazapi_mode == "create"
        or bool(
            str(
                cfg.get("admintoken")
                or cfg.get("admin_token")
                or cfg.get("globalApikey")
                or cfg.get("global_apikey")
                or ""
            ).strip()
        )
    )

    async def _create_and_get_qr() -> dict[str, Any]:
        webhook_url = _resolve_provider_webhook_url(request, provider_id, instance_name)
        create_result = await provider.create_instance(ctx, connection=conn_ref, webhook_url=webhook_url)
        local_conn_ref = conn_ref
        if provider_id == "uazapi":
            token = _extract_uazapi_instance_token(create_result)
            if token:
                merged_cfg = dict(local_conn_ref.config or {})
                merged_cfg["token"] = token
                supabase.table("connections").update({"config": merged_cfg}).eq("id", connection_id).execute()
                local_conn_ref = ConnectionRef(
                    tenant_id=local_conn_ref.tenant_id,
                    provider=local_conn_ref.provider,
                    instance_name=local_conn_ref.instance_name,
                    phone_number=local_conn_ref.phone_number,
                    config=merged_cfg,
                )

        qrcode = _extract_qrcode_value(create_result)
        pairing_code = create_result.get("pairingCode")
        if not qrcode:
            qr_result = await container.connections.connect_with_retries(
                provider, connection=local_conn_ref, correlation_id=f"connect_after_create:{connection_id}"
            )
            qrcode = _extract_qrcode_value(qr_result)
            pairing_code = qr_result.get("pairingCode")

        if not qrcode:
            raise HTTPException(status_code=502, detail="Instância criada, mas não foi possível obter o QR Code.")

        supabase.table("connections").update({"status": "connecting"}).eq("id", connection_id).execute()
        return {
            "success": True,
            "message": "Instância criada! Escaneie o QR Code para conectar",
            "qrcode": qrcode,
            "pairingCode": pairing_code,
        }

    state: Optional[dict[str, Any]] = None
    if provider_id != "uazapi" or token_present:
        try:
            state = await provider.get_connection_state(ctx, connection=conn_ref)
        except Exception as e:
            logger.warning(f"Could not get connection state for {instance_name}: {e}")

    if isinstance(state, dict) and _is_connected_state(provider_id, state):
        webhook_url = _resolve_provider_webhook_url(request, provider_id, instance_name)
        try:
            await provider.ensure_webhook(ctx, connection=conn_ref, webhook_url=webhook_url)
        except Exception as e:
            logger.warning(f"Could not set webhook for {instance_name}: {e}")
        supabase.table("connections").update({"status": "connected", "webhook_url": webhook_url}).eq("id", connection_id).execute()
        return {"success": True, "message": "Conexão estabelecida com sucesso!"}

    if not token_present and provider_id == "uazapi" and not allow_create:
        raise HTTPException(status_code=400, detail="Uazapi não configurada (token).")

    try:
        if token_present:
            qr_result = await container.connections.connect_with_retries(
                provider, connection=conn_ref, correlation_id=f"connect:{connection_id}"
            )
            qrcode = _extract_qrcode_value(qr_result)
            if qrcode:
                return {
                    "success": True,
                    "message": "Escaneie o QR Code para conectar",
                    "qrcode": qrcode,
                    "pairingCode": qr_result.get("pairingCode"),
                }
        if allow_create:
            return await _create_and_get_qr()
        raise HTTPException(status_code=502, detail="Não foi possível obter o QR Code.")
    except Exception as e:
        if allow_create and not token_present:
            try:
                return await _create_and_get_qr()
            except Exception as e2:
                raise _whatsapp_http_error(e2)
        raise _whatsapp_http_error(e)

@api_router.get("/connections/{connection_id}/qrcode")
async def get_qrcode(connection_id: str, payload: dict = Depends(verify_token)):
    """Get QR code for a provider connection"""
    if payload.get('role') not in ['admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Acesso negado")
    conn = supabase.table('connections').select('*').eq('id', connection_id).execute()
    if not conn.data:
        raise HTTPException(status_code=404, detail="Conexão não encontrada")
    
    connection = conn.data[0]
    user_tenant_id = get_user_tenant_id(payload)
    if payload.get('role') != 'superadmin' and user_tenant_id and connection.get('tenant_id') != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    provider_id = str(connection.get("provider") or "").strip().lower()
    instance_name = str(connection.get("instance_name") or "").strip()
    conn_ref = ConnectionRef(
        tenant_id=str(connection.get("tenant_id") or ""),
        provider=provider_id,
        instance_name=instance_name,
        phone_number=str(connection.get("phone_number") or "") or None,
        config=connection.get("config") if isinstance(connection.get("config"), dict) else {},
    )
    container, ctx = _make_provider_ctx(
        tenant_id=conn_ref.tenant_id,
        provider=provider_id,
        instance_name=instance_name,
        correlation_id=f"qrcode:{connection_id}",
    )

    try:
        provider = _get_whatsapp_provider(provider_id)
        qr_result = await container.connections.connect_with_retries(provider, connection=conn_ref, correlation_id=f"connect:{connection_id}")
        qrcode = _extract_qrcode_value(qr_result)
        return {"qrcode": qrcode, "pairingCode": qr_result.get("pairingCode"), "code": qr_result.get("code")}
    except Exception as e:
        raise _whatsapp_http_error(e)

@api_router.post("/connections/{connection_id}/sync")
async def sync_connection_status(connection_id: str, request: Request, payload: dict = Depends(verify_token)):
    """Sincronizar status da conexão com o provedor"""
    if payload.get('role') not in ['admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Acesso negado")
    conn = supabase.table('connections').select('*').eq('id', connection_id).execute()
    if not conn.data:
        raise HTTPException(status_code=404, detail="Conexão não encontrada")
    
    connection = conn.data[0]
    user_tenant_id = get_user_tenant_id(payload)
    if payload.get('role') != 'superadmin' and user_tenant_id and connection.get('tenant_id') != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    provider_id = str(connection.get("provider") or "").strip().lower()
    instance_name = str(connection.get("instance_name") or "").strip()
    conn_ref = ConnectionRef(
        tenant_id=str(connection.get("tenant_id") or ""),
        provider=provider_id,
        instance_name=instance_name,
        phone_number=str(connection.get("phone_number") or "") or None,
        config=connection.get("config") if isinstance(connection.get("config"), dict) else {},
    )
    _container, ctx = _make_provider_ctx(
        tenant_id=conn_ref.tenant_id,
        provider=provider_id,
        instance_name=instance_name,
        correlation_id=f"sync:{connection_id}",
    )

    try:
        provider = _get_whatsapp_provider(provider_id)
        state = await provider.get_connection_state(ctx, connection=conn_ref)
        is_connected = _is_connected_state(provider_id, state)
        new_status = 'connected' if is_connected else 'disconnected'
        
        # Atualizar banco de dados
        update_data = {'status': new_status}
        if is_connected:
            update_data['webhook_url'] = _resolve_provider_webhook_url(request, provider_id, instance_name)
            try:
                await provider.ensure_webhook(ctx, connection=conn_ref, webhook_url=update_data['webhook_url'])
            except Exception as e:
                logger.warning(f"Could not set webhook for {instance_name}: {e}")
            
            # Tentar obter o número do telefone se conectado
            if provider_id == "evolution":
                try:
                    instances = await evolution_api.fetch_instances()
                    for inst in instances:
                        if inst.get('name') == instance_name:
                            owner_jid = inst.get('owner', inst.get('ownerJid', ''))
                            if owner_jid:
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
            'instanceState': (state.get('instance', {}) or {}).get('state', '') if isinstance(state, dict) else '',
            'phoneNumber': c.get('phone_number'),
            'message': f"Status atualizado para: {new_status}"
        }
        
    except Exception as e:
        logger.error(f"Error syncing connection status: {e}")
        raise _whatsapp_http_error(e)

@api_router.patch("/connections/{connection_id}/status")
async def update_connection_status(connection_id: str, status_update: ConnectionStatusUpdate, payload: dict = Depends(verify_token)):
    """Update connection status"""
    if payload.get('role') not in ['admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Acesso negado")
    conn = supabase.table('connections').select('id, tenant_id').eq('id', connection_id).execute()
    if not conn.data:
        raise HTTPException(status_code=404, detail="Conexão não encontrada")
    user_tenant_id = get_user_tenant_id(payload)
    if payload.get('role') != 'superadmin' and user_tenant_id and conn.data[0].get('tenant_id') != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
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
    """Delete a connection and its provider instance (when supported)"""
    if payload.get('role') not in ['admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Acesso negado")
    conn = supabase.table('connections').select('*').eq('id', connection_id).execute()
    
    if not conn.data:
        raise HTTPException(status_code=404, detail="Conexão não encontrada")
    
    connection = conn.data[0]
    user_tenant_id = get_user_tenant_id(payload)
    if payload.get('role') != 'superadmin' and user_tenant_id and connection.get('tenant_id') != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    tenant_id = connection['tenant_id']
    
    provider_id = str(connection.get("provider") or "").strip().lower()
    instance_name = str(connection.get("instance_name") or "").strip()
    if provider_id and instance_name:
        conn_ref = ConnectionRef(
            tenant_id=str(connection.get("tenant_id") or ""),
            provider=provider_id,
            instance_name=instance_name,
            phone_number=str(connection.get("phone_number") or "") or None,
            config=connection.get("config") if isinstance(connection.get("config"), dict) else {},
        )
        _container, ctx = _make_provider_ctx(
            tenant_id=conn_ref.tenant_id,
            provider=provider_id,
            instance_name=instance_name,
            correlation_id=f"conn_delete:{connection_id}",
        )
        try:
            provider = _get_whatsapp_provider(provider_id)
            await provider.delete_instance(ctx, connection=conn_ref)
            logger.info(f"Provider instance deleted: provider={provider_id} instance={instance_name}")
        except Exception as e:
            logger.warning(f"Could not delete provider instance: provider={provider_id} instance={instance_name} err={e}")
    
    # Atualizar contador do tenant
    tenant = supabase.table('tenants').select('connections_count').eq('id', tenant_id).execute()
    if tenant.data and tenant.data[0]['connections_count'] > 0:
        new_count = tenant.data[0]['connections_count'] - 1
        supabase.table('tenants').update({'connections_count': new_count}).eq('id', tenant_id).execute()
    
    # Deletar conexão do banco
    supabase.table('connections').delete().eq('id', connection_id).execute()
    return {"success": True}

# ==================== FLOWS ROUTES ====================

@api_router.get("/flows")
async def list_flows(
    tenant_id: Optional[str] = Query(None),
    status: Optional[str] = None,
    is_active: Optional[bool] = None,
    payload: dict = Depends(verify_token)
):
    """List all flows for a tenant"""
    user_tenant_id = get_user_tenant_id(payload)
    effective_tenant_id = user_tenant_id
    
    if not effective_tenant_id and payload.get('role') == 'superadmin':
        effective_tenant_id = tenant_id
    
    if not effective_tenant_id:
        raise HTTPException(status_code=403, detail="Tenant não identificado")
    
    query = supabase.table('flows').select('*').eq('tenant_id', effective_tenant_id)
    
    if status:
        query = query.eq('status', status)
    if is_active is not None:
        query = query.eq('is_active', is_active)
    
    query = query.order('updated_at', desc=True)
    result = query.execute()
    
    flows = []
    for f in result.data:
        flows.append({
            'id': f['id'],
            'tenantId': f['tenant_id'],
            'name': f['name'],
            'description': f.get('description'),
            'nodes': f.get('nodes', []),
            'edges': f.get('edges', []),
            'variables': f.get('variables', {}),
            'status': f['status'],
            'isActive': f['is_active'],
            'createdBy': f.get('created_by'),
            'createdAt': f['created_at'],
            'updatedAt': f['updated_at']
        })
    
    return flows

@api_router.get("/flows/{flow_id}")
async def get_flow(flow_id: str, payload: dict = Depends(verify_token)):
    """Get a specific flow by ID"""
    result = supabase.table('flows').select('*').eq('id', flow_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Fluxo não encontrado")
    
    f = result.data[0]
    user_tenant_id = get_user_tenant_id(payload)
    
    if payload.get('role') != 'superadmin' and user_tenant_id and f['tenant_id'] != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    return {
        'id': f['id'],
        'tenantId': f['tenant_id'],
        'name': f['name'],
        'description': f.get('description'),
        'nodes': f.get('nodes', []),
        'edges': f.get('edges', []),
        'variables': f.get('variables', {}),
        'status': f['status'],
        'isActive': f['is_active'],
        'createdBy': f.get('created_by'),
        'createdAt': f['created_at'],
        'updatedAt': f['updated_at']
    }

@api_router.post("/flows")
async def create_flow(flow: FlowCreate, payload: dict = Depends(verify_token)):
    """Create a new flow"""
    user_tenant_id = get_user_tenant_id(payload)
    
    if not user_tenant_id:
        raise HTTPException(status_code=403, detail="Tenant não identificado")
    
    data = {
        'tenant_id': user_tenant_id,
        'name': flow.name,
        'description': flow.description,
        'nodes': flow.nodes or [],
        'edges': flow.edges or [],
        'variables': flow.variables or {},
        'status': flow.status or 'draft',
        'is_active': False,
        'created_by': payload.get('user_id')
    }
    
    result = supabase.table('flows').insert(data).execute()
    
    if not result.data:
        raise HTTPException(status_code=400, detail="Erro ao criar fluxo")
    
    f = result.data[0]
    return {
        'id': f['id'],
        'tenantId': f['tenant_id'],
        'name': f['name'],
        'description': f.get('description'),
        'nodes': f.get('nodes', []),
        'edges': f.get('edges', []),
        'variables': f.get('variables', {}),
        'status': f['status'],
        'isActive': f['is_active'],
        'createdBy': f.get('created_by'),
        'createdAt': f['created_at'],
        'updatedAt': f['updated_at']
    }

@api_router.put("/flows/{flow_id}")
async def update_flow(flow_id: str, flow: FlowUpdate, payload: dict = Depends(verify_token)):
    """Update an existing flow"""
    # Verificar se o fluxo existe e se o usuário tem acesso
    existing = supabase.table('flows').select('id, tenant_id').eq('id', flow_id).execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Fluxo não encontrado")
    
    user_tenant_id = get_user_tenant_id(payload)
    if payload.get('role') != 'superadmin' and user_tenant_id and existing.data[0]['tenant_id'] != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    data = {}
    if flow.name is not None:
        data['name'] = flow.name
    if flow.description is not None:
        data['description'] = flow.description
    if flow.nodes is not None:
        data['nodes'] = flow.nodes
    if flow.edges is not None:
        data['edges'] = flow.edges
    if flow.variables is not None:
        data['variables'] = flow.variables
    if flow.status is not None:
        data['status'] = flow.status
    if flow.is_active is not None:
        data['is_active'] = flow.is_active
    
    if not data:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")
    
    result = supabase.table('flows').update(data).eq('id', flow_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Fluxo não encontrado")
    
    f = result.data[0]
    return {
        'id': f['id'],
        'tenantId': f['tenant_id'],
        'name': f['name'],
        'description': f.get('description'),
        'nodes': f.get('nodes', []),
        'edges': f.get('edges', []),
        'variables': f.get('variables', {}),
        'status': f['status'],
        'isActive': f['is_active'],
        'createdBy': f.get('created_by'),
        'createdAt': f['created_at'],
        'updatedAt': f['updated_at']
    }

@api_router.delete("/flows/{flow_id}")
async def delete_flow(flow_id: str, payload: dict = Depends(verify_token)):
    """Delete a flow"""
    # Verificar se o fluxo existe e se o usuário tem acesso
    existing = supabase.table('flows').select('id, tenant_id').eq('id', flow_id).execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Fluxo não encontrado")
    
    user_tenant_id = get_user_tenant_id(payload)
    if payload.get('role') != 'superadmin' and user_tenant_id and existing.data[0]['tenant_id'] != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    supabase.table('flows').delete().eq('id', flow_id).execute()
    return {"success": True, "message": "Fluxo deletado com sucesso"}

@api_router.post("/flows/{flow_id}/duplicate")
async def duplicate_flow(flow_id: str, duplicate: FlowDuplicate, payload: dict = Depends(verify_token)):
    """Duplicate an existing flow"""
    # Buscar o fluxo original
    result = supabase.table('flows').select('*').eq('id', flow_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Fluxo não encontrado")
    
    original = result.data[0]
    user_tenant_id = get_user_tenant_id(payload)
    
    if payload.get('role') != 'superadmin' and user_tenant_id and original['tenant_id'] != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    # Criar cópia
    data = {
        'tenant_id': original['tenant_id'],
        'name': duplicate.name,
        'description': duplicate.description or original.get('description'),
        'nodes': original.get('nodes', []),
        'edges': original.get('edges', []),
        'variables': original.get('variables', {}),
        'status': 'draft',
        'is_active': False,
        'created_by': payload.get('user_id')
    }
    
    new_flow = supabase.table('flows').insert(data).execute()
    
    if not new_flow.data:
        raise HTTPException(status_code=400, detail="Erro ao duplicar fluxo")
    
    f = new_flow.data[0]
    return {
        'id': f['id'],
        'tenantId': f['tenant_id'],
        'name': f['name'],
        'description': f.get('description'),
        'nodes': f.get('nodes', []),
        'edges': f.get('edges', []),
        'variables': f.get('variables', {}),
        'status': f['status'],
        'isActive': f['is_active'],
        'createdBy': f.get('created_by'),
        'createdAt': f['created_at'],
        'updatedAt': f['updated_at']
    }

@api_router.patch("/flows/{flow_id}/toggle")
async def toggle_flow(flow_id: str, payload: dict = Depends(verify_token)):
    """Toggle flow active status"""
    # Verificar se o fluxo existe
    existing = supabase.table('flows').select('id, tenant_id, is_active').eq('id', flow_id).execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Fluxo não encontrado")
    
    flow_data = existing.data[0]
    user_tenant_id = get_user_tenant_id(payload)
    
    if payload.get('role') != 'superadmin' and user_tenant_id and flow_data['tenant_id'] != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    # Inverter estado
    new_state = not flow_data['is_active']
    result = supabase.table('flows').update({'is_active': new_state}).eq('id', flow_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Fluxo não encontrado")
    
    f = result.data[0]
    return {
        'id': f['id'],
        'isActive': f['is_active'],
        'message': f"Fluxo {'ativado' if f['is_active'] else 'desativado'} com sucesso"
    }

# ==================== CONVERSATIONS ROUTES ====================


@api_router.get("/conversations")
async def list_conversations(
    tenant_id: Optional[str] = Query(None),
    status: Optional[str] = None,
    connection_id: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    refresh_avatars: bool = False,
    payload: dict = Depends(verify_token)
):
    """List conversations for a tenant"""
    def needs_avatar_refresh(conv_row: dict) -> bool:
        avatar = conv_row.get('contact_avatar')
        if not avatar:
            return True
        if isinstance(avatar, str) and 'api.dicebear.com' in avatar:
            return True
        return False

    try:
        user_tenant_id = get_user_tenant_id(payload)
        effective_tenant_id = user_tenant_id
        if not effective_tenant_id and payload.get('role') == 'superadmin':
            effective_tenant_id = tenant_id
        if not effective_tenant_id:
            raise HTTPException(status_code=403, detail="Tenant não identificado")

        query = supabase.table('conversations').select('*').eq('tenant_id', effective_tenant_id)
        if payload.get('role') == 'agent':
            user_id = payload.get('user_id')
            if user_id:
                query = query.or_(f"assigned_to.is.null,assigned_to.eq.{user_id}")

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

        try:
            result = _db_call_with_retry(
                "conversations.list",
                lambda: query.order('last_message_at', desc=True).range(offset, offset + limit - 1).execute()
            )
        except Exception as e:
            if _is_missing_table_or_schema_error(e, "conversations"):
                return []
            raise

        connection_by_id: Dict[str, Dict[str, Any]] = {}
        try:
            connections = _db_call_with_retry(
                "connections.list_for_conversations",
                lambda: supabase.table('connections').select('id, instance_name, provider').eq('tenant_id', effective_tenant_id).execute()
            )
            connection_by_id = {c['id']: c for c in (connections.data or []) if isinstance(c, dict) and c.get('id')}
        except Exception:
            connection_by_id = {}

        to_refresh = [c for c in (result.data or []) if needs_avatar_refresh(c)] if refresh_avatars else []
        refreshed: Dict[str, Optional[str]] = {}

        async def refresh_avatar(conv_row: dict) -> Optional[str]:
            conn = connection_by_id.get(conv_row.get('connection_id'))
            avatar = conv_row.get('contact_avatar')

            if not conn or conn.get('provider') != 'evolution' or not conn.get('instance_name'):
                if isinstance(avatar, str) and 'api.dicebear.com' in avatar:
                    try:
                        supabase.table('conversations').update({'contact_avatar': None}).eq('id', conv_row['id']).execute()
                    except Exception:
                        pass
                return None

            try:
                data = await evolution_api.get_profile_picture(conn['instance_name'], conv_row.get('contact_phone') or '')
                url = extract_profile_picture_url(data)
            except Exception:
                url = None

            if url:
                try:
                    supabase.table('conversations').update({'contact_avatar': url}).eq('id', conv_row['id']).execute()
                except Exception:
                    pass
                return url

            if isinstance(avatar, str) and 'api.dicebear.com' in avatar:
                try:
                    supabase.table('conversations').update({'contact_avatar': None}).eq('id', conv_row['id']).execute()
                except Exception:
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

    except HTTPException:
        raise
    except Exception as e:
        if _is_supabase_not_configured_error(e):
            return []
        if _is_missing_table_or_schema_error(e, "conversations"):
            return []
        if _is_transient_db_error(e):
            raise HTTPException(status_code=503, detail="Banco de dados indisponível.")
        logger.error(f"Error listing conversations: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao listar conversas: {str(e)}")

@api_router.patch("/conversations/{conversation_id}/status")
async def update_conversation_status(conversation_id: str, status_update: ConversationStatusUpdate, payload: dict = Depends(verify_token)):
    """Update conversation status"""
    _require_conversation_access(conversation_id, payload)
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
    _require_conversation_access(conversation_id, payload)
    result = supabase.table('conversations').update({'unread_count': 0}).eq('id', conversation_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    return {"success": True}

@api_router.post("/conversations/{conversation_id}/assign")
async def assign_conversation(conversation_id: str, data: AssignAgent, payload: dict = Depends(verify_token)):
    """Assign conversation to agent"""
    _require_conversation_access(conversation_id, payload)
    result = await AgentService.assign_conversation(conversation_id, data.agent_id)
    return {"success": True, "assignedTo": data.agent_id}

@api_router.post("/conversations/{conversation_id}/unassign")
async def unassign_conversation(conversation_id: str, payload: dict = Depends(verify_token)):
    """Unassign conversation"""
    _require_conversation_access(conversation_id, payload)
    await AgentService.unassign_conversation(conversation_id)
    return {"success": True}

@api_router.post("/conversations/{conversation_id}/transfer")
async def transfer_conversation(conversation_id: str, data: ConversationTransferCreate, payload: dict = Depends(verify_token)):
    user_tenant_id = get_user_tenant_id(payload)

    _require_conversation_access(conversation_id, payload)
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

    _require_conversation_access(conversation_id, payload)
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
        _require_conversation_access(conversation_id, payload)
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
        _require_conversation_access(conversation_id, payload)
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
    _require_conversation_access(conversation_id, payload)

    supabase.table('messages').delete().eq('conversation_id', conversation_id).execute()
    supabase.table('conversations').delete().eq('id', conversation_id).execute()
    return {"success": True}


@api_router.delete("/conversations/{conversation_id}/messages")
async def clear_conversation_messages(conversation_id: str, payload: dict = Depends(verify_token)):
    _require_conversation_access(conversation_id, payload)

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
    tenant_id: Optional[str] = Query(None),
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    payload: dict = Depends(verify_token)
):
    """List all contacts for the tenant"""
    try:
        user_tenant_id = get_user_tenant_id(payload)
        effective_tenant_id = user_tenant_id
        if not effective_tenant_id and payload.get('role') == 'superadmin':
            effective_tenant_id = tenant_id
        if not effective_tenant_id:
            raise HTTPException(status_code=403, detail="Tenant não identificado")

        if limit < 1:
            limit = 1
        if limit > 200:
            limit = 200
        if offset < 0:
            offset = 0

        query = supabase.table('contacts').select('*').eq('tenant_id', effective_tenant_id)

        if search:
            search_term = f"%{search}%"
            query = query.or_(f"name.ilike.{search_term},phone.ilike.{search_term},email.ilike.{search_term}")

        try:
            result = _db_call_with_retry(
                "contacts.list",
                lambda: query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()
            )
        except Exception as e:
            if _is_transient_db_error(e):
                cached = _CONTACTS_CACHE_BY_TENANT.get(str(effective_tenant_id))
                if isinstance(cached, dict) and isinstance(cached.get("data"), list):
                    return {
                        'contacts': cached.get("data") or [],
                        'total': cached.get("total") or len(cached.get("data") or []),
                        'limit': limit,
                        'offset': offset,
                        'cached': True
                    }
            if _is_supabase_not_configured_error(e):
                return {
                    'contacts': [],
                    'total': 0,
                    'limit': limit,
                    'offset': offset,
                    'notConfigured': True
                }
            if _is_missing_table_or_schema_error(e, "contacts"):
                cached = _CONTACTS_CACHE_BY_TENANT.get(str(effective_tenant_id))
                if (
                    isinstance(cached, dict)
                    and isinstance(cached.get("data"), list)
                    and str(cached.get("search") or "") == (search or "")
                    and int(cached.get("limit") or limit) == int(limit)
                    and int(cached.get("offset") or offset) == int(offset)
                ):
                    return {
                        'contacts': cached.get("data") or [],
                        'total': cached.get("total") or len(cached.get("data") or []),
                        'limit': limit,
                        'offset': offset,
                        'cached': True,
                        'fallback': True
                    }
                try:
                    conv_q = (
                        supabase.table("conversations")
                        .select("id, contact_phone, contact_name, contact_avatar, last_message_at")
                        .eq("tenant_id", effective_tenant_id)
                        .order("last_message_at", desc=True)
                        .range(0, 999)
                    )
                    conv_result = _db_call_with_retry("contacts.fallback.conversations", lambda: conv_q.execute())
                except Exception as conv_err:
                    logger.error(f"Fallback contacts from conversations failed: {conv_err}")
                    return {
                        'contacts': [],
                        'total': 0,
                        'limit': limit,
                        'offset': offset,
                        'fallback': True
                    }

                seen = set()
                derived = []
                needle = (search or "").strip().lower()
                for row in (conv_result.data or []):
                    phone = (row.get("contact_phone") or "").strip()
                    if not phone or phone in seen:
                        continue
                    name = (row.get("contact_name") or "").strip() or phone
                    if needle:
                        hay = f"{name} {phone}".lower()
                        if needle not in hay:
                            continue
                    seen.add(phone)
                    derived.append({
                        'id': f"conv-{row.get('id')}",
                        'tenantId': effective_tenant_id,
                        'name': name,
                        'phone': phone,
                        'email': None,
                        'tags': [],
                        'customFields': {},
                        'status': 'pending',
                        'firstContactAt': None,
                        'source': 'conversation',
                        'createdAt': row.get("last_message_at"),
                        'updatedAt': row.get("last_message_at"),
                    })

                total_derived = len(derived)
                paged = derived[offset: offset + limit]
                _CONTACTS_CACHE_BY_TENANT[str(effective_tenant_id)] = {
                    "data": paged,
                    "total": total_derived,
                    "cached_at": datetime.utcnow().isoformat(),
                    "search": search or "",
                    "limit": limit,
                    "offset": offset,
                }
                return {
                    'contacts': paged,
                    'total': total_derived,
                    'limit': limit,
                    'offset': offset,
                    'fallback': True
                }
            raise

        contacts = []
        for c in (result.data or []):
            _cache_contact_row(c)
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

        if not contacts:
            try:
                cached = _CONTACTS_CACHE_BY_TENANT.get(str(effective_tenant_id))
                if (
                    isinstance(cached, dict)
                    and isinstance(cached.get("data"), list)
                    and str(cached.get("search") or "") == (search or "")
                    and int(cached.get("limit") or limit) == int(limit)
                    and int(cached.get("offset") or offset) == int(offset)
                ):
                    return {
                        'contacts': cached.get("data") or [],
                        'total': cached.get("total") or len(cached.get("data") or []),
                        'limit': limit,
                        'offset': offset,
                        'cached': True,
                        'fallback': True
                    }
                conv_q = (
                    supabase.table("conversations")
                    .select("id, contact_phone, contact_name, contact_avatar, last_message_at")
                    .eq("tenant_id", effective_tenant_id)
                    .order("last_message_at", desc=True)
                    .range(0, 999)
                )
                conv_result = _db_call_with_retry(
                    "contacts.fallback.conversations.empty",
                    lambda: conv_q.execute(),
                )
                seen = set()
                derived = []
                needle = (search or "").strip().lower()
                for row in (conv_result.data or []):
                    phone = (row.get("contact_phone") or "").strip()
                    if not phone or phone in seen:
                        continue
                    name = (row.get("contact_name") or "").strip() or phone
                    if needle:
                        hay = f"{name} {phone}".lower()
                        if needle not in hay:
                            continue
                    seen.add(phone)
                    derived.append({
                        'id': f"conv-{row.get('id')}",
                        'tenantId': effective_tenant_id,
                        'name': name,
                        'phone': phone,
                        'email': None,
                        'tags': [],
                        'customFields': {},
                        'status': 'pending',
                        'firstContactAt': None,
                        'source': 'conversation',
                        'createdAt': row.get("last_message_at"),
                        'updatedAt': row.get("last_message_at"),
                    })
                total_derived = len(derived)
                paged = derived[offset: offset + limit]
                _CONTACTS_CACHE_BY_TENANT[str(effective_tenant_id)] = {
                    "data": paged,
                    "total": total_derived,
                    "cached_at": datetime.utcnow().isoformat(),
                    "search": search or "",
                    "limit": limit,
                    "offset": offset,
                }
                return {
                    'contacts': paged,
                    'total': total_derived,
                    'limit': limit,
                    'offset': offset,
                    'fallback': True
                }
            except Exception:
                pass

        total = len(result.data or [])
        try:
            count_result = _db_call_with_retry(
                "contacts.count",
                lambda: supabase.table('contacts').select('id', count='exact').eq('tenant_id', effective_tenant_id).execute()
            )
            if hasattr(count_result, 'count') and count_result.count:
                total = count_result.count
        except Exception as e:
            if _is_missing_table_or_schema_error(e, "contacts"):
                total = len(contacts)
            else:
                raise

        _CONTACTS_CACHE_BY_TENANT[str(effective_tenant_id)] = {
            "data": contacts,
            "total": total,
            "cached_at": datetime.utcnow().isoformat(),
            "search": search or "",
            "limit": limit,
            "offset": offset,
        }

        safe_insert_audit_log(
            tenant_id=effective_tenant_id,
            actor_user_id=payload.get('user_id'),
            action='contact.listed',
            entity_type='contact',
            entity_id=None,
            metadata={'search': search or '', 'limit': limit, 'offset': offset}
        )

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
async def create_contact(
    data: ContactCreate,
    tenant_id: Optional[str] = Query(None),
    payload: dict = Depends(verify_token),
):
    """Create a new contact"""
    try:
        user_tenant_id = get_user_tenant_id(payload)
        effective_tenant_id = user_tenant_id
        if not effective_tenant_id and payload.get('role') == 'superadmin':
            effective_tenant_id = tenant_id
        if not effective_tenant_id:
            raise HTTPException(status_code=403, detail="Tenant não identificado")

        name = (data.name or '').strip()
        raw_phone = (data.phone or '').strip()

        if not name:
            raise HTTPException(status_code=400, detail="Nome é obrigatório")
        if len(name) < 2 or len(name) > 100:
            raise HTTPException(status_code=400, detail="Nome deve ter entre 2 e 100 caracteres")
        if not raw_phone:
            raise HTTPException(status_code=400, detail="Telefone é obrigatório")

        phone = normalize_phone_number(raw_phone)
        if not phone:
            raise HTTPException(status_code=400, detail="Telefone é inválido")

        # Check if contact with same phone already exists
        existing = _db_call_with_retry(
            "contacts.exists",
            lambda: supabase.table('contacts').select('id').eq('tenant_id', effective_tenant_id).eq('phone', phone).limit(1).execute()
        )
        if (not existing.data) and raw_phone != phone:
            existing = _db_call_with_retry(
                "contacts.exists_raw",
                lambda: supabase.table('contacts').select('id').eq('tenant_id', effective_tenant_id).eq('phone', raw_phone).limit(1).execute()
            )
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
                'tenant_id': effective_tenant_id,
                'name': name,
                'phone': phone,
                'email': (data.email or '').strip() or None,
                'tags': data.tags or [],
                'custom_fields': data.custom_fields or {},
                'source': data.source or 'manual',
                'status': final_status,
                'first_contact_at': datetime.utcnow().isoformat()
            }
            insert_result = _db_call_with_retry(
                "contacts.insert",
                lambda: supabase.table('contacts').insert(insert_data).execute()
            )
        except Exception:
            insert_result = None

        if not insert_result or not insert_result.data:
            try:
                insert_data_alt = {
                    'tenant_id': effective_tenant_id,
                    'full_name': name,
                    'phone': phone,
                    'social_links': {},
                    'notes_html': '',
                    'status': final_status,
                    'first_contact_at': datetime.utcnow().isoformat()
                }
                insert_result = _db_call_with_retry(
                    "contacts.insert_alt",
                    lambda: supabase.table('contacts').insert(insert_data_alt).execute()
                )
            except Exception as e:
                if _is_transient_db_error(e):
                    _queue_db_write({"kind": "insert", "table": "contacts", "data": insert_data})
                    return {"success": True, "queued": True}
                raise HTTPException(status_code=400, detail=f"Erro ao criar contato: {str(e)}")

        if not insert_result or not insert_result.data:
            raise HTTPException(status_code=400, detail="Erro ao criar contato")

        c = insert_result.data[0]
        _cache_contact_row(c)
        name_value = c.get('name') or c.get('full_name') or name
        
        safe_insert_audit_log(
            tenant_id=effective_tenant_id,
            actor_user_id=payload.get('user_id'),
            action='contact.created',
            entity_type='contact',
            entity_id=c.get('id'),
            metadata={'phone': phone}
        )
        safe_insert_contact_history(
            tenant_id=effective_tenant_id,
            contact_id=c.get('id'),
            changed_by=payload.get('user_id'),
            action='created',
            before=None,
            after={'name': name_value, 'phone': phone}
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
            existing = _db_call_with_retry(
                "contacts.get_by_phone",
                lambda: supabase.table('contacts').select('*').eq('tenant_id', tenant_id).eq('phone', normalized_phone).limit(1).execute()
            )
            if (not existing.data) and raw_phone and raw_phone != normalized_phone:
                existing = _db_call_with_retry(
                    "contacts.get_by_phone_raw",
                    lambda: supabase.table('contacts').select('*').eq('tenant_id', tenant_id).eq('phone', raw_phone).limit(1).execute()
                )
            if existing.data:
                c = existing.data[0]
                _cache_contact_row(c)
                full_name = c.get('full_name') or c.get('name') or normalized_phone
                # Return with actual schema columns
                safe_insert_audit_log(
                    tenant_id=tenant_id,
                    actor_user_id=payload.get('user_id'),
                    action='contact.read_by_phone',
                    entity_type='contact',
                    entity_id=c.get('id'),
                    metadata={'phone': normalized_phone}
                )
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
            if _is_transient_db_error(table_error):
                cached = _CONTACT_CACHE_BY_TENANT_PHONE.get(f"{tenant_id}:{normalized_phone}") or _CONTACT_CACHE_BY_TENANT_PHONE.get(f"{tenant_id}:{raw_phone}")
                if isinstance(cached, dict):
                    full_name = cached.get('full_name') or cached.get('name') or normalized_phone
                    return {
                        'id': cached.get('id'),
                        'tenantId': tenant_id,
                        'phone': cached.get('phone') or normalized_phone,
                        'fullName': full_name,
                        'email': cached.get('email'),
                        'tags': cached.get('tags') or [],
                        'customFields': cached.get('custom_fields') or cached.get('customFields') or {},
                        'socialLinks': cached.get('social_links') or cached.get('socialLinks') or {},
                        'notesHtml': cached.get('notes_html') or cached.get('notesHtml') or '',
                        'status': cached.get('status'),
                        'firstContactAt': cached.get('first_contact_at') or cached.get('firstContactAt'),
                        'source': cached.get('source'),
                        'createdAt': cached.get('created_at') or cached.get('createdAt'),
                        'updatedAt': cached.get('updated_at') or cached.get('updatedAt'),
                        'cached': True
                    }

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

        try:
            result = _db_call_with_retry(
                "contacts.get",
                lambda: supabase.table('contacts').select('*').eq('id', contact_id).execute()
            )
        except Exception as e:
            if _is_transient_db_error(e):
                cached = _CONTACT_CACHE_BY_ID.get(str(contact_id))
                if isinstance(cached, dict):
                    return {
                        'id': cached.get('id') or contact_id,
                        'tenantId': cached.get('tenant_id'),
                        'name': cached.get('name') or cached.get('full_name'),
                        'phone': cached.get('phone'),
                        'email': cached.get('email'),
                        'tags': cached.get('tags') or [],
                        'customFields': cached.get('custom_fields') or {},
                        'socialLinks': cached.get('social_links') or {},
                        'notesHtml': cached.get('notes_html') or '',
                        'status': cached.get('status'),
                        'firstContactAt': cached.get('first_contact_at'),
                        'source': cached.get('source'),
                        'createdAt': cached.get('created_at'),
                        'updatedAt': cached.get('updated_at'),
                        'conversationCount': 0,
                        'cached': True
                    }
            raise
        if not result.data:
            raise HTTPException(status_code=404, detail="Contato não encontrado")

        c = result.data[0]
        _cache_contact_row(c)
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

        safe_insert_audit_log(
            tenant_id=c.get('tenant_id'),
            actor_user_id=payload.get('user_id'),
            action='contact.read',
            entity_type='contact',
            entity_id=contact_id,
            metadata={}
        )

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
            
            # If conversation doesn't exist, check if there's a real contact with this UUID
            if not conv.data:
                try:
                    existing_contact = supabase.table('contacts').select('*').eq('id', conversation_id).limit(1).execute()
                    if existing_contact.data:
                        # Found a real contact with this ID - use it directly instead of conv- processing
                        contact_id = conversation_id
                        # Fall through to the normal contact update logic below (outside this if block)
                    else:
                        raise HTTPException(status_code=404, detail="Contato ou conversa não encontrado")
                except HTTPException:
                    raise
                except Exception:
                    raise HTTPException(status_code=404, detail="Contato ou conversa não encontrado")
            else:
                # Conversation exists - process as synthetic contact
                conversation = conv.data[0]
                if user_tenant_id and conversation.get('tenant_id') != user_tenant_id:
                    raise HTTPException(status_code=403, detail="Acesso negado")

                tenant_value = conversation.get('tenant_id')
                phone_value = (conversation.get('contact_phone') or '').strip()
                normalized_phone = normalize_phone_number(phone_value) or phone_value
                desired_name: Optional[str] = None
                
                # Update conversation contact name
                if data.full_name is not None:
                    desired_name = (data.full_name or '').strip()
                    if not desired_name:
                        raise HTTPException(status_code=400, detail="Nome é obrigatório")
                    if len(desired_name) < 2 or len(desired_name) > 100:
                        raise HTTPException(status_code=400, detail="Nome deve ter entre 2 e 100 caracteres")
                    try:
                        if tenant_value and phone_value:
                            supabase.table('conversations').update({
                                'contact_name': desired_name
                            }).eq('tenant_id', tenant_value).eq('contact_phone', phone_value).execute()
                        else:
                            supabase.table('conversations').update({
                                'contact_name': desired_name
                            }).eq('id', conversation_id).execute()
                    except Exception:
                        supabase.table('conversations').update({
                            'contact_name': desired_name
                        }).eq('id', conversation_id).execute()

                    safe_insert_audit_log(
                        tenant_id=conversation.get('tenant_id'),
                        actor_user_id=payload.get('user_id'),
                        action='contact.updated',
                        entity_type='conversation',
                        entity_id=conversation_id,
                        metadata={'fields': ['contact_name']}
                    )

                created_or_updated_contact = None
                should_upsert_contact = any([
                    data.email is not None,
                    data.tags is not None,
                    data.custom_fields is not None,
                    data.social_links is not None,
                    data.notes_html is not None,
                    data.status is not None,
                ])

            if should_upsert_contact and tenant_value and normalized_phone:
                try:
                    existing_contact = None
                    try:
                        existing = _db_call_with_retry(
                            "contacts.upsert_by_conv.get",
                            lambda: supabase.table('contacts').select('*').eq('tenant_id', tenant_value).eq('phone', normalized_phone).limit(1).execute()
                        )
                        if (not existing.data) and phone_value and phone_value != normalized_phone:
                            existing = _db_call_with_retry(
                                "contacts.upsert_by_conv.get_raw",
                                lambda: supabase.table('contacts').select('*').eq('tenant_id', tenant_value).eq('phone', phone_value).limit(1).execute()
                            )
                        if existing.data:
                            existing_contact = existing.data[0]
                    except Exception:
                        existing_contact = None

                    if existing_contact and existing_contact.get('id'):
                        update_data: Dict[str, Any] = {}
                        if desired_name is not None:
                            update_data['name'] = desired_name
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
                            updated = _db_call_with_retry(
                                "contacts.upsert_by_conv.update",
                                lambda: supabase.table('contacts').update(update_data).eq('id', existing_contact.get('id')).execute()
                            )
                            if updated.data:
                                created_or_updated_contact = updated.data[0]
                    else:
                        name_value = (
                            (desired_name or '').strip()
                            or (conversation.get('contact_name') or '').strip()
                            or normalized_phone
                        )

                        raw_status = str(data.status or 'pending').strip().lower()
                        normalized_status = {
                            'pendente': 'pending',
                            'pending': 'pending',
                            'nao verificado': 'unverified',
                            'não verificado': 'unverified',
                            'unverified': 'unverified',
                            'verificado': 'verified',
                            'verified': 'verified'
                        }.get(raw_status) or 'pending'

                        insert_data = {
                            'tenant_id': tenant_value,
                            'name': name_value,
                            'phone': normalized_phone,
                            'email': (data.email or '').strip() or None,
                            'tags': data.tags or [],
                            'custom_fields': data.custom_fields or {},
                            'social_links': data.social_links or {},
                            'notes_html': data.notes_html or '',
                            'source': 'conversation',
                            'status': normalized_status,
                            'first_contact_at': conversation.get('created_at') or datetime.utcnow().isoformat(),
                            'updated_at': datetime.utcnow().isoformat(),
                        }

                        insert_result = None
                        try:
                            insert_result = _db_call_with_retry(
                                "contacts.upsert_by_conv.insert",
                                lambda: supabase.table('contacts').insert(insert_data).execute()
                            )
                        except Exception:
                            insert_result = None

                        if not insert_result or not insert_result.data:
                            insert_data_alt = dict(insert_data)
                            insert_data_alt['full_name'] = insert_data_alt.pop('name', None)
                            try:
                                insert_result = _db_call_with_retry(
                                    "contacts.upsert_by_conv.insert_alt",
                                    lambda: supabase.table('contacts').insert(insert_data_alt).execute()
                                )
                            except Exception:
                                insert_result = None

                        if insert_result and insert_result.data:
                            created_or_updated_contact = insert_result.data[0]
                except HTTPException:
                    raise
                except Exception:
                    created_or_updated_contact = None

            if created_or_updated_contact:
                _cache_contact_row(created_or_updated_contact)
                full_name_value = created_or_updated_contact.get('full_name') or created_or_updated_contact.get('name') or normalized_phone
                return {
                    'id': created_or_updated_contact.get('id'),
                    'tenantId': created_or_updated_contact.get('tenant_id'),
                    'phone': created_or_updated_contact.get('phone'),
                    'fullName': full_name_value,
                    'email': created_or_updated_contact.get('email'),
                    'tags': created_or_updated_contact.get('tags') or [],
                    'customFields': created_or_updated_contact.get('custom_fields') or {},
                    'socialLinks': created_or_updated_contact.get('social_links') or {},
                    'notesHtml': created_or_updated_contact.get('notes_html') or '',
                    'status': created_or_updated_contact.get('status'),
                    'firstContactAt': created_or_updated_contact.get('first_contact_at'),
                    'source': created_or_updated_contact.get('source'),
                    'createdAt': created_or_updated_contact.get('created_at'),
                    'updatedAt': created_or_updated_contact.get('updated_at')
                }

            return {
                'id': contact_id,
                'tenantId': conversation.get('tenant_id'),
                'phone': conversation.get('contact_phone'),
                'fullName': desired_name or conversation.get('contact_name'),
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
                if len(desired_name) < 2 or len(desired_name) > 100:
                    raise HTTPException(status_code=400, detail="Nome deve ter entre 2 e 100 caracteres")

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
                before_snapshot = dict(contact or {})
                updated = _db_call_with_retry(
                    "contacts.update",
                    lambda: supabase.table('contacts').update(update_data).eq('id', contact_id).execute()
                )
                if updated.data:
                    after = updated.data[0]
            except Exception:
                after = None

            if after is None:
                update_data_alt = build_update_payload('full_name')
                try:
                    before_snapshot = dict(contact or {})
                    updated_alt = _db_call_with_retry(
                        "contacts.update_alt",
                        lambda: supabase.table('contacts').update(update_data_alt).eq('id', contact_id).execute()
                    )
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
            _cache_contact_row(after)

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
            safe_insert_contact_history(
                tenant_id=contact.get('tenant_id'),
                contact_id=contact_id,
                changed_by=payload.get('user_id'),
                action='updated',
                before=locals().get("before_snapshot"),
                after=after
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

@api_router.delete("/contacts/purge")
async def purge_contacts(tenant_id: Optional[str] = Query(None), payload: dict = Depends(verify_token)):
    """Delete all contacts for a tenant"""
    requested_tenant_id = (tenant_id or '').strip() or None
    user_tenant_id = get_user_tenant_id(payload)

    effective_tenant_id = None
    if payload.get('role') == 'superadmin' and requested_tenant_id:
        effective_tenant_id = requested_tenant_id
    else:
        effective_tenant_id = user_tenant_id

    if not effective_tenant_id:
        raise HTTPException(status_code=403, detail="Tenant não identificado")

    count_result = supabase.table('contacts').select('id', count='exact').eq('tenant_id', effective_tenant_id).execute()
    total = count_result.count or 0

    if total <= 0:
        return {"success": True, "deletedContacts": 0}

    try:
        supabase.table('contacts').delete().eq('tenant_id', effective_tenant_id).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao excluir contatos: {str(e)}")

    safe_insert_audit_log(
        tenant_id=effective_tenant_id,
        actor_user_id=payload.get('user_id'),
        action='contacts.purge',
        entity_type='contact',
        entity_id=None,
        metadata={'deleted': total}
    )

    return {"success": True, "deletedContacts": total}


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

    before_snapshot = None
    try:
        row = supabase.table('contacts').select('*').eq('id', contact_id).limit(1).execute()
        if row.data:
            before_snapshot = row.data[0]
    except Exception:
        before_snapshot = None

    supabase.table('contacts').delete().eq('id', contact_id).execute()

    safe_insert_audit_log(
        tenant_id=user_tenant_id,
        actor_user_id=payload.get('user_id'),
        action='contact.deleted',
        entity_type='contact',
        entity_id=contact_id,
        metadata={}
    )
    safe_insert_contact_history(
        tenant_id=user_tenant_id,
        contact_id=contact_id,
        changed_by=payload.get('user_id'),
        action='deleted',
        before=before_snapshot,
        after=None
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
    _require_conversation_access(conversation_id, payload)

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
            if msg_type == 'sticker':
                return '[Figurinha]'
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
    msg = supabase.table('messages').select('id, conversation_id').eq('id', message_id).execute()
    if not msg.data:
        raise HTTPException(status_code=404, detail="Mensagem não encontrada")
    conversation_id = msg.data[0]['conversation_id']
    _require_conversation_access(conversation_id, payload)

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
                prefix = build_user_signature_prefix(user_row.data[0])
                if prefix and not content.startswith(prefix) and not content.lstrip().startswith(f"*{(user_row.data[0].get('name') or '').strip()}*"):
                    content = prefix + content
        except Exception:
            pass

    _enforce_messages_limit(conversation.get('tenant_id'))

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

def _extract_sent_message_id(obj: Any) -> Optional[str]:
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
    try:
        row = supabase.table("messages").select("metadata").eq("id", message_id).limit(1).execute()
        if row.data and isinstance(row.data[0].get("metadata"), dict):
            return row.data[0].get("metadata") or {}
    except Exception:
        return {}
    return {}

async def send_provider_message(connection: ConnectionRef, phone: str, content: str, msg_type: str, message_id: str, *, caption: str = None, filename: str = None):
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

async def send_whatsapp_message(instance_name: str, phone: str, content: str, msg_type: str, message_id: str):
    conn_ref = ConnectionRef(tenant_id="", provider="evolution", instance_name=instance_name, config={})
    await send_provider_message(conn_ref, phone, content, msg_type, message_id)

# ==================== WHATSAPP DIRECT ROUTES ====================

@api_router.post("/whatsapp/send")
async def send_whatsapp_direct(data: SendWhatsAppMessage, payload: dict = Depends(verify_token)):
    try:
        provider_id = str(data.provider or "evolution").strip().lower()
        instance_name = str(data.instance_name or "").strip()
        conn_ref = ConnectionRef(
            tenant_id=str(get_user_tenant_id(payload) or ""),
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

@api_router.post("/whatsapp/typing")
async def send_typing_indicator(
    instance_name: str,
    phone: str,
    provider: str = Query("evolution"),
    presence: str = Query("composing"),
    config: Optional[dict[str, Any]] = Body(None),
    payload: dict = Depends(verify_token),
):
    """Send typing indicator"""
    try:
        provider_id = str(provider or "evolution").strip().lower()
        instance_name_norm = str(instance_name or "").strip()
        conn_ref = ConnectionRef(
            tenant_id=str(get_user_tenant_id(payload) or ""),
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

# ==================== MESSAGE REACTIONS ====================

@api_router.get("/messages/{message_id}/reactions")
async def get_message_reactions(message_id: str, payload: dict = Depends(verify_token)):
    """Get reactions for a message"""
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

@api_router.post("/messages/{message_id}/reactions")
async def add_message_reaction(message_id: str, emoji: str, payload: dict = Depends(verify_token)):
    """Add a reaction to a message"""
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

@api_router.delete("/messages/{message_id}/reactions/{reaction_id}")
async def remove_message_reaction(message_id: str, reaction_id: str, payload: dict = Depends(verify_token)):
    """Remove a reaction from a message"""
    try:
        msg = supabase.table('messages').select('conversation_id').eq('id', message_id).execute()
        if not msg.data:
            raise HTTPException(status_code=404, detail="Mensagem não encontrada")
        _require_conversation_access(msg.data[0].get('conversation_id'), payload)
        supabase.table('message_reactions').delete().eq('id', reaction_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

def _safe_parse_json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return default
        try:
            return json.loads(s)
        except Exception:
            return default
    return default


def _extract_keyword_trigger_from_flow_nodes(nodes: Any) -> Optional[str]:
    parsed_nodes = _safe_parse_json_value(nodes, [])
    if not isinstance(parsed_nodes, list):
        return None
    for node in parsed_nodes:
        if not isinstance(node, dict):
            continue
        if node.get("type") != "start":
            continue
        data = node.get("data") or {}
        if not isinstance(data, dict):
            continue
        cfg = (data.get("config") or {}) if isinstance(data.get("config") or {}, dict) else {}
        trigger = str(cfg.get("trigger") or "").strip().lower()
        if trigger != "keyword":
            continue
        keyword = str(cfg.get("keyword") or "").strip()
        if keyword:
            return keyword
    return None


def _build_edges_from_map(edges: Any) -> Dict[str, List[dict]]:
    parsed_edges = _safe_parse_json_value(edges, [])
    if not isinstance(parsed_edges, list):
        return {}
    edges_from: Dict[str, List[dict]] = {}
    for edge in parsed_edges:
        if not isinstance(edge, dict):
            continue
        src = edge.get("source")
        if not isinstance(src, str) or not src:
            continue
        edges_from.setdefault(src, []).append(edge)
    return edges_from


def _get_start_node_id(nodes: Any) -> Optional[str]:
    parsed_nodes = _safe_parse_json_value(nodes, [])
    if not isinstance(parsed_nodes, list):
        return None
    for node in parsed_nodes:
        if isinstance(node, dict) and node.get("type") == "start" and isinstance(node.get("id"), str):
            return node["id"]
    return None


def _render_template_text(template: str, ctx: Dict[str, Any]) -> str:
    s = str(template or "")
    if not s:
        return ""

    def repl(match: "re.Match[str]") -> str:
        key = (match.group(1) or "").strip()
        if not key:
            return ""
        val = ctx.get(key)
        if val is None:
            return ""
        return str(val)
    return re.sub(r"\{([^{}]+)\}", repl, s)

def _bulk_template_ctx_from_contact(contact_row: Any) -> Dict[str, Any]:
    if not isinstance(contact_row, dict):
        return {}
    name = (contact_row.get("name") or contact_row.get("full_name") or "").strip()
    phone = (contact_row.get("phone") or "").strip()
    email = (contact_row.get("email") or "").strip()
    tags = contact_row.get("tags") or []
    custom_fields = contact_row.get("custom_fields") or contact_row.get("customFields") or {}
    if not isinstance(custom_fields, dict):
        custom_fields = {}

    ctx: Dict[str, Any] = {
        "nome": name,
        "name": name,
        "contato_nome": name,
        "contact_name": name,
        "telefone": phone,
        "phone": phone,
        "email": email,
        "tags": tags,
    }
    for k, v in custom_fields.items():
        if not isinstance(k, str) or not k.strip():
            continue
        if k in ctx:
            continue
        ctx[k] = v
    return ctx

def _bulk_period_seconds(period_unit: Any) -> Optional[int]:
    unit = str(period_unit or "").strip().lower()
    if unit == "minute":
        return 60
    if unit == "hour":
        return 60 * 60
    if unit == "day":
        return 60 * 60 * 24
    if unit == "week":
        return 60 * 60 * 24 * 7
    if unit == "month":
        return 60 * 60 * 24 * 30
    return None

def _bulk_build_schedule(
    start_at: datetime,
    count: int,
    *,
    delay_seconds: int,
    max_messages_per_period: Optional[int],
    period_unit: Optional[str],
) -> List[datetime]:
    n = int(count or 0)
    if n <= 0:
        return []
    delay = int(delay_seconds or 0)
    if delay < 0:
        delay = 0

    per = int(max_messages_per_period or 0) if max_messages_per_period is not None else 0
    period_s = _bulk_period_seconds(period_unit) if per > 0 else None

    out: List[datetime] = []
    for i in range(n):
        when = start_at + timedelta(seconds=delay * i)
        if period_s and per > 0:
            window_idx = i // per
            when = when + timedelta(seconds=window_idx * period_s)
        out.append(when)
    return out

def _bulk_add_months(dt: datetime, months: int) -> datetime:
    m = int(months or 0)
    if m == 0:
        return dt
    year = dt.year
    month = dt.month + m
    while month > 12:
        month -= 12
        year += 1
    while month < 1:
        month += 12
        year -= 1

    last_day = 28
    for d in (31, 30, 29, 28):
        try:
            datetime(year, month, d)
            last_day = d
            break
        except Exception:
            continue

    day = min(dt.day, last_day)
    return dt.replace(year=year, month=month, day=day)

def _bulk_compute_next_run_at(recurrence: Any, from_dt: datetime) -> Optional[datetime]:
    r = str(recurrence or "none").strip().lower()
    if r == "daily":
        return from_dt + timedelta(days=1)
    if r == "weekly":
        return from_dt + timedelta(days=7)
    if r == "monthly":
        return _bulk_add_months(from_dt, 1)
    return None


def _wait_seconds(duration: Any, unit: Any) -> int:
    try:
        d = float(duration)
    except Exception:
        d = 0
    if d <= 0:
        return 0
    u = str(unit or "seconds").strip().lower()
    mult = 1
    if u in {"minute", "minutes"}:
        mult = 60
    elif u in {"hour", "hours"}:
        mult = 60 * 60
    elif u in {"day", "days"}:
        mult = 60 * 60 * 24
    return int(d * mult)


def _eval_condition(condition: Any, ctx: Dict[str, Any]) -> bool:
    if not isinstance(condition, dict):
        return False
    var_name = str(condition.get("variable") or "").strip()
    operator = str(condition.get("operator") or "equals").strip().lower()
    expected_raw = condition.get("value")
    actual = ctx.get(var_name) if var_name else None
    expected = expected_raw
    if operator in {"greater", "less"}:
        try:
            a = float(actual)
            b = float(expected)
        except Exception:
            return False
        return a > b if operator == "greater" else a < b
    actual_s = str(actual or "")
    expected_s = str(expected or "")
    if operator == "contains":
        return expected_s.lower() in actual_s.lower()
    return actual_s.strip().lower() == expected_s.strip().lower()


async def _execute_flow_for_conversation(
    flow_row: dict,
    *,
    tenant_id: str,
    conversation: dict,
    connection: dict,
    phone: str,
    incoming_text: str,
):
    nodes = _safe_parse_json_value(flow_row.get("nodes"), [])
    if not isinstance(nodes, list) or not nodes:
        return
    edges_from = _build_edges_from_map(flow_row.get("edges"))
    nodes_by_id: Dict[str, dict] = {
        n.get("id"): n for n in nodes
        if isinstance(n, dict) and isinstance(n.get("id"), str)
    }
    start_id = _get_start_node_id(nodes)
    if not start_id or start_id not in nodes_by_id:
        return

    ctx: Dict[str, Any] = {}
    vars_from_flow = _safe_parse_json_value(flow_row.get("variables"), {})
    if isinstance(vars_from_flow, dict):
        ctx.update(vars_from_flow)
    ctx.setdefault("telefone", phone)
    ctx.setdefault("phone", phone)
    ctx.setdefault("mensagem", incoming_text)
    ctx.setdefault("message", incoming_text)
    contact_name = (conversation.get("contact_name") or "").strip()
    if contact_name:
        ctx.setdefault("contato_nome", contact_name)
        ctx.setdefault("contact_name", contact_name)

    execution_id = None
    try:
        exec_row = supabase.table("flow_executions").insert({
            "flow_id": flow_row.get("id"),
            "tenant_id": tenant_id,
            "conversation_id": conversation.get("id"),
            "status": "running",
            "current_node_id": start_id,
            "context": ctx,
        }).execute()
        if exec_row.data and isinstance(exec_row.data[0], dict):
            execution_id = exec_row.data[0].get("id")
    except Exception:
        execution_id = None

    async def log_node(node_id: str, node_type: str, status: str, *, error_message: Optional[str] = None):
        if not execution_id:
            return
        try:
            supabase.table("flow_logs").insert({
                "execution_id": execution_id,
                "node_id": node_id,
                "node_type": node_type,
                "status": status,
                "error_message": error_message,
            }).execute()
        except Exception:
            pass

    connection_cache: Dict[str, Optional[dict]] = {}

    def _get_node_connection(cfg: dict) -> Optional[dict]:
        node_connection_id = str(cfg.get("connectionId") or cfg.get("connection_id") or "").strip()
        if node_connection_id:
            cached = connection_cache.get(node_connection_id)
            if cached is not None:
                return cached
            try:
                r = (
                    supabase.table("connections")
                    .select("*")
                    .eq("tenant_id", tenant_id)
                    .eq("id", node_connection_id)
                    .limit(1)
                    .execute()
                )
                conn = r.data[0] if r.data and isinstance(r.data[0], dict) else None
                connection_cache[node_connection_id] = conn
                return conn
            except Exception:
                connection_cache[node_connection_id] = None
                return None
        return connection if isinstance(connection, dict) else None

    def next_from(node_id: str, *, handle: Optional[str] = None) -> Optional[str]:
        outs = edges_from.get(node_id) or []
        if handle:
            for e in outs:
                if str(e.get("sourceHandle") or "").strip() == handle:
                    tgt = e.get("target")
                    if isinstance(tgt, str) and tgt:
                        return tgt
        for e in outs:
            tgt = e.get("target")
            if isinstance(tgt, str) and tgt:
                return tgt
        return None

    current_id: Optional[str] = next_from(start_id)
    steps = 0
    while current_id and steps < 200:
        steps += 1
        node = nodes_by_id.get(current_id)
        if not isinstance(node, dict):
            break
        node_type = str(node.get("type") or "").strip()
        data = node.get("data") or {}
        cfg = (data.get("config") or {}) if isinstance(data, dict) else {}
        if not isinstance(cfg, dict):
            cfg = {}

        try:
            if node_type == "textMessage":
                raw = str(cfg.get("message") or "")
                content = _render_template_text(raw, ctx).strip()
                if content:
                    now = datetime.utcnow().isoformat()
                    msg_row = supabase.table("messages").insert({
                        "conversation_id": conversation["id"],
                        "content": content,
                        "type": "text",
                        "direction": "outbound",
                        "status": "sent",
                    }).execute()
                    if msg_row.data and isinstance(msg_row.data[0], dict):
                        msg_id = msg_row.data[0]["id"]
                        try:
                            supabase.table("conversations").update({
                                "last_message_at": now,
                                "last_message_preview": content[:50],
                            }).eq("id", conversation["id"]).execute()
                        except Exception:
                            pass
                        try:
                            tenant_row = supabase.table("tenants").select("messages_this_month").eq("id", tenant_id).execute()
                            if tenant_row.data:
                                supabase.table("tenants").update({
                                    "messages_this_month": tenant_row.data[0]["messages_this_month"] + 1
                                }).eq("id", tenant_id).execute()
                        except Exception:
                            pass
                        node_conn = _get_node_connection(cfg)
                        if not node_conn:
                            supabase.table("messages").update({"status": "failed"}).eq("id", msg_id).execute()
                            raise Exception("Conexão do nó não encontrada")
                        provider_id = str(node_conn.get("provider") or "").strip().lower()
                        connection_status = str(node_conn.get("status") or "").strip().lower()
                        is_connected = connection_status in ["connected", "open"]
                        instance_name = str(node_conn.get("instance_name") or "").strip()
                        if not (provider_id and is_connected and instance_name):
                            supabase.table("messages").update({"status": "failed"}).eq("id", msg_id).execute()
                            raise Exception("Conexão do nó indisponível")
                        conn_ref = ConnectionRef(
                            tenant_id=str(node_conn.get("tenant_id") or tenant_id or ""),
                            provider=provider_id,
                            instance_name=instance_name,
                            phone_number=str(node_conn.get("phone_number") or "") or None,
                            config=node_conn.get("config") if isinstance(node_conn.get("config"), dict) else {},
                        )
                        asyncio.create_task(send_provider_message(conn_ref, phone, content, "text", msg_id))
                await log_node(current_id, node_type, "success")
                current_id = next_from(current_id)
                continue

            if node_type == "mediaMessage":
                media_type = str(cfg.get("mediaType") or "").strip().lower() or "image"
                media_url = str(cfg.get("mediaUrl") or "").strip()
                caption_raw = str(cfg.get("caption") or "")
                caption = _render_template_text(caption_raw, ctx).strip()
                if media_url:
                    now = datetime.utcnow().isoformat()
                    msg_row = supabase.table("messages").insert({
                        "conversation_id": conversation["id"],
                        "content": caption or f"[{media_type}]",
                        "type": media_type,
                        "direction": "outbound",
                        "status": "sent",
                        "media_url": media_url,
                    }).execute()
                    if msg_row.data and isinstance(msg_row.data[0], dict):
                        msg_id = msg_row.data[0]["id"]
                        preview = caption[:50] if caption else f"[{media_type.capitalize()}]"
                        try:
                            supabase.table("conversations").update({
                                "last_message_at": now,
                                "last_message_preview": preview,
                            }).eq("id", conversation["id"]).execute()
                        except Exception:
                            pass
                        try:
                            tenant_row = supabase.table("tenants").select("messages_this_month").eq("id", tenant_id).execute()
                            if tenant_row.data:
                                supabase.table("tenants").update({
                                    "messages_this_month": tenant_row.data[0]["messages_this_month"] + 1
                                }).eq("id", tenant_id).execute()
                        except Exception:
                            pass
                        node_conn = _get_node_connection(cfg)
                        if not node_conn:
                            supabase.table("messages").update({"status": "failed"}).eq("id", msg_id).execute()
                            raise Exception("Conexão do nó não encontrada")
                        provider_id = str(node_conn.get("provider") or "").strip().lower()
                        connection_status = str(node_conn.get("status") or "").strip().lower()
                        is_connected = connection_status in ["connected", "open"]
                        instance_name = str(node_conn.get("instance_name") or "").strip()
                        if not (provider_id and is_connected and instance_name):
                            supabase.table("messages").update({"status": "failed"}).eq("id", msg_id).execute()
                            raise Exception("Conexão do nó indisponível")
                        conn_ref = ConnectionRef(
                            tenant_id=str(node_conn.get("tenant_id") or tenant_id or ""),
                            provider=provider_id,
                            instance_name=instance_name,
                            phone_number=str(node_conn.get("phone_number") or "") or None,
                            config=node_conn.get("config") if isinstance(node_conn.get("config"), dict) else {},
                        )
                        asyncio.create_task(send_provider_message(
                            conn_ref,
                            phone,
                            str(media_url or ""),
                            str(media_type or "document"),
                            msg_id,
                            caption=caption,
                            filename="flow_media",
                        ))
                await log_node(current_id, node_type, "success")
                current_id = next_from(current_id)
                continue

            if node_type == "wait":
                seconds = _wait_seconds(cfg.get("duration"), cfg.get("unit"))
                await log_node(current_id, node_type, "success")
                if seconds > 0:
                    await asyncio.sleep(seconds)
                current_id = next_from(current_id)
                continue

            if node_type == "variable":
                action = str(cfg.get("action") or "set").strip().lower()
                var_name = str(cfg.get("variableName") or "").strip()
                if action == "set" and var_name:
                    value_raw = str(cfg.get("value") or "")
                    ctx[var_name] = _render_template_text(value_raw, ctx)
                await log_node(current_id, node_type, "success")
                current_id = next_from(current_id)
                continue

            if node_type == "conditional":
                condition = cfg.get("condition")
                ok = _eval_condition(condition, ctx)
                await log_node(current_id, node_type, "success")
                current_id = next_from(current_id, handle=("true" if ok else "false"))
                continue

            await log_node(current_id, node_type or "unknown", "skipped")
            current_id = next_from(current_id)
        except Exception as e:
            await log_node(current_id, node_type or "unknown", "error", error_message=str(e))
            break

    if execution_id:
        try:
            supabase.table("flow_executions").update({
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
                "context": ctx,
                "current_node_id": current_id,
            }).eq("id", execution_id).execute()
        except Exception:
            pass


# ==================== WEBHOOKS ====================

@api_router.post("/webhooks/{provider}/{instance_name}")
async def provider_webhook(provider: str, instance_name: str, payload: dict):
    provider_id = str(provider or "").strip().lower()
    if provider_id == "evolution":
        return await _process_evolution_webhook(instance_name, payload, from_queue=False)
    if provider_id == "uazapi":
        return await _process_uazapi_webhook(instance_name, payload, from_queue=False)
    logger.warning(
        f"Webhook for unsupported provider '{provider_id}' - currently only 'evolution' and 'uazapi' are implemented."
    )
    return {"success": True, "ignored": "unsupported_provider"}

@api_router.post("/webhooks/evolution/{instance_name}")
async def evolution_webhook(instance_name: str, payload: dict):
    return await _process_evolution_webhook(instance_name, payload, from_queue=False)


async def _process_generic_webhook(provider: str, instance_name: str, payload: dict, *, from_queue: bool) -> dict:
    provider_id = str(provider or "").strip().lower()
    logger.info(f"Webhook received for provider={provider_id} instance={instance_name}: {payload.get('event')}")
    logger.info(f"Full webhook payload: {json.dumps(payload, indent=2, default=str)[:2000]}")

    try:
        parsed = _parse_provider_webhook(provider_id, instance_name, payload)

        if parsed.get('event') == 'message':
            logger.info(f"DEBUG - Parsed pushName: '{parsed.get('push_name')}' | Phone: {parsed.get('remote_jid')}")

        if parsed['event'] == 'message':
            is_from_me = parsed.get('from_me', False)
            push_name_raw = (parsed.get('push_name') or '').strip()
            contact_push_name = push_name_raw if (push_name_raw and not is_from_me) else None

            raw_jid = parsed.get('remote_jid_raw') or payload.get('data', {}).get('key', {}).get('remoteJid', '')
            if '@g.us' in raw_jid:
                logger.info(f"Ignoring group message from {raw_jid}")
                return {"success": True, "ignored": "group_message"}
            if '@broadcast' in raw_jid:
                logger.info(f"Ignoring broadcast message from {raw_jid}")
                return {"success": True, "ignored": "broadcast_message"}

            try:
                conn = _db_call_with_retry(
                    "connections.get_by_instance",
                    lambda: supabase.table('connections').select('*, tenants(*)').eq('instance_name', instance_name).execute()
                )
            except Exception as e:
                if _is_transient_db_error(e):
                    if (provider_id == "evolution") and (not from_queue):
                        _queue_db_write({"kind": "webhook_event", "instance_name": instance_name, "payload": payload})
                        return {"success": True, "queued": True}
                    raise
                raise

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

                if (provider_id == "evolution") and is_placeholder_text(parsed.get('content') or ''):
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

                direction = 'outbound' if is_from_me else 'inbound'

                is_new_conversation = False
                try:
                    conv = _db_call_with_retry(
                        "conversations.get_by_phone",
                        lambda: supabase.table('conversations').select('*').eq('tenant_id', tenant_id).eq('connection_id', connection['id']).eq('contact_phone', phone).execute()
                    )
                    if (not conv.data) and raw_phone and str(raw_phone).strip() and str(raw_phone).strip() != phone:
                        conv = _db_call_with_retry(
                            "conversations.get_by_phone_raw",
                            lambda: supabase.table('conversations').select('*').eq('tenant_id', tenant_id).eq('connection_id', connection['id']).eq('contact_phone', str(raw_phone).strip()).execute()
                        )
                except Exception as e:
                    if _is_transient_db_error(e):
                        if (provider_id == "evolution") and (not from_queue):
                            _queue_db_write({"kind": "webhook_event", "instance_name": instance_name, "payload": payload})
                            return {"success": True, "queued": True}
                        raise
                    raise

                if conv.data:
                    conversation = conv.data[0]
                    preview = '' if is_placeholder_text(parsed.get('content') or '') else (parsed.get('content') or '')[:50]

                    update_data = {
                        'last_message_at': datetime.utcnow().isoformat(),
                        'last_message_preview': preview
                    }
                    if not is_from_me:
                        update_data['unread_count'] = conversation['unread_count'] + 1
                        if contact_push_name:
                            existing_name = (conversation.get('contact_name') or '').strip()
                            if (not existing_name) or existing_name == phone or _looks_like_system_user_name(existing_name, tenant_id):
                                update_data['contact_name'] = contact_push_name

                    try:
                        _db_call_with_retry(
                            "conversations.update_last_message",
                            lambda: supabase.table('conversations').update(update_data).eq('id', conversation['id']).execute()
                        )
                    except Exception as e:
                        if _is_transient_db_error(e):
                            _queue_db_write({
                                "kind": "update",
                                "table": "conversations",
                                "data": update_data,
                                "filters": [{"op": "eq", "field": "id", "value": conversation['id']}],
                            })
                        else:
                            raise
                else:
                    avatar_url = None
                    if provider_id == "evolution":
                        try:
                            data = await evolution_api.get_profile_picture(instance_name, phone)
                            avatar_url = extract_profile_picture_url(data)
                        except Exception:
                            avatar_url = None

                    contact_name_to_use = contact_push_name or phone
                    logger.info(f"DEBUG - Creating conversation with contact_name: '{contact_name_to_use}' | push_name from parsed: '{parsed.get('push_name')}' | phone: {phone}")

                    conv_data = {
                        'tenant_id': tenant_id,
                        'connection_id': connection['id'],
                        'contact_phone': phone,
                        'contact_name': contact_name_to_use,
                        'contact_avatar': avatar_url,
                        'status': 'open',
                        'unread_count': 0 if is_from_me else 1,
                        'last_message_preview': '' if is_placeholder_text(parsed.get('content') or '') else (parsed.get('content') or '')[:50]
                    }
                    try:
                        conv_result = _db_call_with_retry(
                            "conversations.insert",
                            lambda: supabase.table('conversations').insert(conv_data).execute()
                        )
                        conversation = conv_result.data[0]
                        is_new_conversation = True
                    except Exception as e:
                        if _is_transient_db_error(e):
                            if (provider_id == "evolution") and (not from_queue):
                                _queue_db_write({"kind": "webhook_event", "instance_name": instance_name, "payload": payload})
                                return {"success": True, "queued": True}
                            raise
                        raise

                if phone:
                    try:
                        cached_contact = _CONTACT_CACHE_BY_TENANT_PHONE.get(f"{tenant_id}:{phone}")
                        existing_contact_rows: List[dict] = []
                        if isinstance(cached_contact, dict) and cached_contact.get('id') and cached_contact.get('phone'):
                            existing_contact_rows = [cached_contact]
                        else:
                            existing_contact = _db_call_with_retry(
                                "contacts.auto.exists",
                                lambda: supabase.table('contacts').select('id, phone, name, full_name, first_contact_at, status, custom_fields').eq('tenant_id', tenant_id).eq('phone', phone).limit(1).execute()
                            )
                            existing_contact_rows = existing_contact.data or []
                            if (not existing_contact_rows) and raw_phone and str(raw_phone).strip() and str(raw_phone).strip() != phone:
                                existing_contact = _db_call_with_retry(
                                    "contacts.auto.exists_raw",
                                    lambda: supabase.table('contacts').select('id, phone, name, full_name, first_contact_at, status, custom_fields').eq('tenant_id', tenant_id).eq('phone', str(raw_phone).strip()).limit(1).execute()
                                )
                                existing_contact_rows = existing_contact.data or []

                        if existing_contact_rows:
                            row = existing_contact_rows[0]
                            if contact_push_name and row.get('id'):
                                current_name = (row.get('name') or row.get('full_name') or '').strip()
                                if (not current_name) or current_name == phone or _looks_like_system_user_name(current_name, tenant_id):
                                    name_payload = {'updated_at': datetime.utcnow().isoformat(), 'name': contact_push_name}
                                    try:
                                        _db_call_with_retry(
                                            "contacts.auto.set_name",
                                            lambda: supabase.table('contacts').update(name_payload).eq('id', row.get('id')).execute()
                                        )
                                        _cache_contact_row({**row, **name_payload})
                                    except Exception:
                                        alt_payload = {'updated_at': datetime.utcnow().isoformat(), 'full_name': contact_push_name}
                                        try:
                                            _db_call_with_retry(
                                                "contacts.auto.set_full_name",
                                                lambda: supabase.table('contacts').update(alt_payload).eq('id', row.get('id')).execute()
                                            )
                                            _cache_contact_row({**row, **alt_payload})
                                        except Exception:
                                            pass
                            if not row.get('first_contact_at'):
                                touch_data = {'first_contact_at': first_contact_at_iso, 'updated_at': datetime.utcnow().isoformat()}
                                try:
                                    _db_call_with_retry(
                                        "contacts.auto.touch_first_contact",
                                        lambda: supabase.table('contacts').update(touch_data).eq('id', row.get('id')).execute()
                                    )
                                except Exception as e:
                                    if _is_transient_db_error(e):
                                        _queue_db_write({
                                            "kind": "update",
                                            "table": "contacts",
                                            "data": touch_data,
                                            "filters": [{"op": "eq", "field": "id", "value": row.get('id')}],
                                        })
                                    else:
                                        raise
                            try:
                                current_cf = row.get('custom_fields') or {}
                                if isinstance(current_cf, dict) and current_cf.get('lifecycleStatus') != 'Novo contato':
                                    current_cf = {**current_cf, 'lifecycleStatus': 'Novo contato'}
                                    lifecycle_data = {'custom_fields': current_cf, 'updated_at': datetime.utcnow().isoformat()}
                                    try:
                                        _db_call_with_retry(
                                            "contacts.auto.ensure_lifecycle",
                                            lambda: supabase.table('contacts').update(lifecycle_data).eq('id', row.get('id')).execute()
                                        )
                                    except Exception as e:
                                        if _is_transient_db_error(e):
                                            _queue_db_write({
                                                "kind": "update",
                                                "table": "contacts",
                                                "data": lifecycle_data,
                                                "filters": [{"op": "eq", "field": "id", "value": row.get('id')}],
                                            })
                                        else:
                                            raise
                            except Exception:
                                pass
                        else:
                            push_name = (contact_push_name or '').strip() or None

                            logger.info(f"DEBUG - Auto-creating contact | push_name: '{push_name}' | phone: {phone} | tenant: {tenant_id}")

                            try:
                                insert_data = {
                                    'tenant_id': tenant_id,
                                    'name': push_name,
                                    'phone': phone,
                                    'source': 'whatsapp',
                                    'status': 'pending',
                                    'first_contact_at': first_contact_at_iso,
                                    'custom_fields': {'lifecycleStatus': 'Novo contato'}
                                }
                                _db_call_with_retry(
                                    "contacts.auto.insert",
                                    lambda: supabase.table('contacts').insert(insert_data).execute()
                                )
                                _cache_contact_row({**insert_data})
                            except Exception:
                                insert_data_alt = {
                                    'tenant_id': tenant_id,
                                    'full_name': push_name,
                                    'phone': phone,
                                    'source': 'whatsapp',
                                    'status': 'pending',
                                    'first_contact_at': first_contact_at_iso,
                                    'custom_fields': {'lifecycleStatus': 'Novo contato'}
                                }
                                try:
                                    _db_call_with_retry(
                                        "contacts.auto.insert_alt",
                                        lambda: supabase.table('contacts').insert(insert_data_alt).execute()
                                    )
                                    _cache_contact_row({**insert_data_alt})
                                except Exception as e:
                                    if _is_transient_db_error(e):
                                        _queue_db_write({"kind": "insert", "table": "contacts", "data": insert_data_alt})
                                    else:
                                        raise
                            safe_insert_audit_log(
                                tenant_id=tenant_id,
                                actor_user_id=None,
                                action='contact.auto_created',
                                entity_type='contact',
                                entity_id=None,
                                metadata={'phone': phone, 'source': 'whatsapp'}
                            )
                    except Exception as e:
                        logger.warning(f"Auto-create contact failed for {tenant_id} phone={phone}: {e}")
                        if _is_transient_db_error(e):
                            pass

                parsed_type_raw = parsed.get('type') or 'text'
                parsed_kind_raw = parsed.get('media_kind')
                parsed_type = str(parsed_type_raw or '').strip().lower() or 'text'
                parsed_kind = str(parsed_kind_raw or '').strip().lower() if parsed_kind_raw is not None else ''
                allowed_message_types = {'text', 'image', 'video', 'audio', 'document', 'sticker', 'system'}
                message_type_to_store = parsed_kind if parsed_kind in allowed_message_types else parsed_type
                if message_type_to_store not in allowed_message_types:
                    message_type_to_store = 'text'

                media_url_final = parsed.get('media_url')
                detected_mime_type = parsed.get('mime_type')

                def infer_media_kind_from_payload(obj: Any) -> Tuple[Optional[str], Optional[str]]:
                    stack: List[Any] = [obj]
                    key_map = {
                        'imageMessage': 'image',
                        'videoMessage': 'video',
                        'audioMessage': 'audio',
                        'stickerMessage': 'sticker',
                        'documentMessage': 'document',
                    }
                    indicators = {
                        'url',
                        'directPath',
                        'mediaKey',
                        'fileEncSha256',
                        'fileSha256',
                        'thumbnailDirectPath',
                        'jpegThumbnail',
                        'fileLength',
                        'seconds',
                        'ptt',
                    }
                    while stack:
                        cur = stack.pop()
                        if isinstance(cur, dict):
                            for k, hinted in key_map.items():
                                if k in cur and isinstance(cur.get(k), dict):
                                    node = cur.get(k) or {}
                                    mime = node.get('mimetype') or node.get('mimeType') or cur.get('mimetype') or cur.get('mimeType')
                                    detected = detect_media_kind(declared_mime_type=mime, hinted_kind=hinted)
                                    if detected.kind != 'unknown':
                                        return detected.kind, detected.mime_type
                            mime = cur.get('mimetype') or cur.get('mimeType')
                            if mime and any(ind in cur for ind in indicators):
                                detected = detect_media_kind(declared_mime_type=mime)
                                if detected.kind != 'unknown':
                                    return detected.kind, detected.mime_type
                            for v in cur.values():
                                if isinstance(v, (dict, list)):
                                    stack.append(v)
                        elif isinstance(cur, list):
                            for v in cur:
                                if isinstance(v, (dict, list)):
                                    stack.append(v)
                    return None, None

                if message_type_to_store == 'text':
                    inferred_kind, inferred_mime = infer_media_kind_from_payload(payload)
                    if inferred_kind in allowed_message_types and inferred_kind != 'text':
                        message_type_to_store = inferred_kind
                        if inferred_mime and not detected_mime_type:
                            detected_mime_type = inferred_mime
                        parsed_content = str(parsed.get('content') or '').strip()
                        if (not parsed_content) or parsed_content.isdigit() or parsed_content.lower() in {'[mensagem]', '[message]'}:
                            parsed['content'] = (
                                '[Imagem]' if inferred_kind == 'image'
                                else '[Vídeo]' if inferred_kind == 'video'
                                else '[Áudio]' if inferred_kind == 'audio'
                                else '[Documento]' if inferred_kind == 'document'
                                else '[Figurinha]' if inferred_kind == 'sticker'
                                else parsed.get('content')
                            )

                if provider_id == "evolution" and message_type_to_store in ['image', 'video', 'audio', 'document', 'sticker'] and parsed.get('message_id'):
                    try:
                        base64_result = await evolution_api.get_base64_from_media_message(
                            instance_name=instance_name,
                            message_id=parsed.get('message_id'),
                            remote_jid=parsed.get('remote_jid_raw') or f"{phone}@s.whatsapp.net",
                            from_me=is_from_me
                        )

                        if base64_result:
                            base64_data = base64_result.get('base64') or (base64_result.get('data', {}) or {}).get('base64')
                            mimetype = base64_result.get('mimetype') or (base64_result.get('data', {}) or {}).get('mimetype') or detected_mime_type or 'application/octet-stream'

                            if base64_data:
                                import uuid as uuid_mod
                                mime_parts = mimetype.split('/')
                                file_ext = mime_parts[-1].split(';')[0] if len(mime_parts) > 1 else 'bin'
                                if file_ext in ['ogg; codecs=opus', 'ogg;codecs=opus']:
                                    file_ext = 'ogg'
                                unique_filename = f"{uuid_mod.uuid4()}.{file_ext}"

                                if 'image' in mimetype or message_type_to_store in ['image', 'sticker']:
                                    folder = 'images'
                                elif 'video' in mimetype or message_type_to_store == 'video':
                                    folder = 'videos'
                                elif 'audio' in mimetype or message_type_to_store == 'audio':
                                    folder = 'audios'
                                else:
                                    folder = 'documents'

                                storage_path = f"media-messages/{folder}/{unique_filename}"

                                file_content = base64.b64decode(base64_data)
                                supabase.storage.from_('uploads').upload(
                                    storage_path,
                                    file_content,
                                    file_options={"content-type": mimetype}
                                )

                                media_url_final = supabase.storage.from_('uploads').get_public_url(storage_path)
                                detected_mime_type = mimetype
                                logger.info(f"Media saved to storage: {storage_path} for message {parsed.get('message_id')}")
                    except Exception as e:
                        logger.warning(f"Failed to process media for message {parsed.get('message_id')}: {e}")

                msg_data = {
                    'conversation_id': conversation['id'],
                    'content': '' if is_placeholder_text(parsed.get('content') or '') else (parsed.get('content') or ''),
                    'type': message_type_to_store,
                    'direction': direction,
                    'status': 'read' if is_from_me else 'delivered',
                    'media_url': media_url_final,
                    'external_id': parsed.get('message_id'),
                    'metadata': {
                        'remote_jid': parsed.get('remote_jid_raw') or f"{phone}@s.whatsapp.net",
                        'instance_name': instance_name,
                        'from_me': is_from_me,
                        'message_id': parsed.get('message_id'),
                        'media_kind': parsed.get('media_kind') or message_type_to_store,
                        'mime_type': detected_mime_type
                    }
                }
                try:
                    _db_call_with_retry("messages.insert", lambda: supabase.table('messages').insert(msg_data).execute())
                except Exception as e:
                    if _is_transient_db_error(e):
                        _queue_db_write({"kind": "insert", "table": "messages", "data": msg_data})
                    else:
                        raise

                tenant = _db_call_with_retry(
                    "tenants.get_message_count",
                    lambda: supabase.table('tenants').select('messages_this_month').eq('id', tenant_id).execute()
                )
                if tenant.data:
                    try:
                        _db_call_with_retry(
                            "tenants.bump_message_count",
                            lambda: supabase.table('tenants').update({
                                'messages_this_month': tenant.data[0]['messages_this_month'] + 1
                            }).eq('id', tenant_id).execute()
                        )
                    except Exception as e:
                        if _is_transient_db_error(e):
                            _queue_db_write({
                                "kind": "update",
                                "table": "tenants",
                                "data": {'messages_this_month': tenant.data[0]['messages_this_month'] + 1},
                                "filters": [{"op": "eq", "field": "id", "value": tenant_id}]
                            })
                        else:
                            raise

                incoming_text = (parsed.get('content') or '').strip()
                should_process_inbound_text = (not is_from_me) and (not is_placeholder_text(incoming_text)) and bool(incoming_text.strip())

                auto_messages_result = None
                if should_process_inbound_text:
                    try:
                        auto_messages_result = supabase.table('auto_messages').select('*').eq('tenant_id', tenant_id).eq('is_active', True).execute()
                    except Exception as e:
                        if _is_missing_table_error(e, "auto_messages"):
                            logger.warning(f"Missing table auto_messages in Supabase (tenant={tenant_id}): {e}")
                        else:
                            logger.error(f"Error loading auto messages for tenant {tenant_id}: {e}")
                        auto_messages_result = None

                if auto_messages_result and auto_messages_result.data and should_process_inbound_text:
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

                    def normalize_schedule_days(value: Any) -> List[int]:
                        if value is None:
                            return []
                        if isinstance(value, (list, tuple)):
                            out: List[int] = []
                            for item in value:
                                try:
                                    out.append(int(item))
                                except Exception:
                                    continue
                            return out
                        if isinstance(value, str):
                            s = value.strip()
                            if not s:
                                return []
                            if s.startswith("{") and s.endswith("}"):
                                inner = s[1:-1].strip()
                                if not inner:
                                    return []
                                out: List[int] = []
                                for part in inner.split(","):
                                    part = part.strip()
                                    if not part:
                                        continue
                                    try:
                                        out.append(int(part))
                                    except Exception:
                                        continue
                                return out
                            if s.startswith("[") and s.endswith("]"):
                                try:
                                    parsed_days = json.loads(s)
                                except Exception:
                                    parsed_days = None
                                return normalize_schedule_days(parsed_days)
                            out: List[int] = []
                            for part in re.split(r"[,\s]+", s):
                                part = part.strip()
                                if not part:
                                    continue
                                try:
                                    out.append(int(part))
                                except Exception:
                                    continue
                            return out
                        return []

                    def minutes_to_hm(value: int) -> Tuple[int, int]:
                        h = value // 60
                        m = value % 60
                        return h, m

                    def away_window_bounds_utc(auto_msg: Dict[str, Any]) -> Tuple[datetime, datetime]:
                        start_min = parse_time_to_minutes(auto_msg.get("schedule_start"))
                        end_min = parse_time_to_minutes(auto_msg.get("schedule_end"))
                        if start_min is None or end_min is None:
                            day_start_local = datetime(local_now.year, local_now.month, local_now.day)
                            day_end_local = day_start_local + timedelta(days=1)
                            return day_start_local - local_offset, day_end_local - local_offset

                        spans_midnight = start_min > end_min
                        start_date = local_now.date()
                        if spans_midnight and now_minutes <= end_min:
                            start_date = (local_now - timedelta(days=1)).date()

                        sh, sm = minutes_to_hm(start_min)
                        eh, em = minutes_to_hm(end_min)
                        start_local = datetime(start_date.year, start_date.month, start_date.day, sh, sm)
                        end_date = start_date + timedelta(days=1) if spans_midnight else start_date
                        end_local = datetime(end_date.year, end_date.month, end_date.day, eh, em)
                        return start_local - local_offset, end_local - local_offset
                    connection_provider = (connection.get('provider') if isinstance(connection, dict) else None)
                    connection_status = (connection.get('status') if isinstance(connection, dict) else None)
                    is_evolution = str(connection_provider or '').lower() == 'evolution'
                    is_connected = str(connection_status or '').lower() in ['connected', 'open']

                    async def send_auto_message(auto_msg, delay_seconds: int):
                        try:
                            msg_type_inner = str(auto_msg.get('type') or '').lower()
                            log_query = supabase.table('auto_message_logs').select('id').eq('auto_message_id', auto_msg['id']).eq('conversation_id', conversation['id'])

                            if msg_type_inner == 'away':
                                window_start_utc, window_end_utc = away_window_bounds_utc(auto_msg)
                                log_query = log_query.gte('sent_at', window_start_utc.isoformat()).lt('sent_at', window_end_utc.isoformat())

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

                            if is_connected:
                                provider_conn = str(connection_provider or '').strip().lower() or 'evolution'
                                if delay_seconds and delay_seconds > 0:
                                    await asyncio.sleep(delay_seconds)
                                conn_ref = ConnectionRef(
                                    tenant_id=str(tenant_id or ""),
                                    provider=provider_conn,
                                    instance_name=str(connection.get("instance_name") or instance_name or ""),
                                    phone_number=str(connection.get("phone_number") or "") or None,
                                    config=connection.get("config") if isinstance(connection.get("config"), dict) else {},
                                )
                                await send_provider_message(
                                    conn_ref,
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
                            start_min = parse_time_to_minutes(auto_msg.get('schedule_start'))
                            end_min = parse_time_to_minutes(auto_msg.get('schedule_end'))
                            spans_midnight = (
                                start_min is not None
                                and end_min is not None
                                and start_min > end_min
                            )
                            effective_day_index = day_index
                            if spans_midnight and end_min is not None and now_minutes <= end_min:
                                effective_day_index = (day_index - 1) % 7

                            days = normalize_schedule_days(auto_msg.get('schedule_days'))
                            if days and effective_day_index not in days:
                                continue
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

                if should_process_inbound_text:
                    try:
                        flows_result = supabase.table("flows").select("id, tenant_id, nodes, edges, variables, is_active, status").eq("tenant_id", tenant_id).eq("is_active", True).execute()
                    except Exception:
                        flows_result = None

                    if flows_result and flows_result.data:
                        for flow_row in flows_result.data:
                            if not isinstance(flow_row, dict):
                                continue
                            keyword = _extract_keyword_trigger_from_flow_nodes(flow_row.get("nodes"))
                            if not keyword:
                                continue
                            if keyword.lower() not in incoming_text.lower():
                                continue
                            asyncio.create_task(_execute_flow_for_conversation(
                                flow_row,
                                tenant_id=tenant_id,
                                conversation=conversation,
                                connection=connection,
                                phone=phone,
                                incoming_text=incoming_text,
                            ))

        elif parsed['event'] == 'connection' and provider_id == "evolution":
            logger.info(f"Processing connection event for {instance_name}: state={parsed.get('state')}, raw_data={parsed.get('raw_data')}")

            connection_state = parsed.get('state', '').lower()
            is_connected = connection_state in ['open', 'connected']

            status = 'connected' if is_connected else 'disconnected'

            update_data = {'status': status}
            if is_connected:
                update_data['webhook_url'] = f"https://altarcrm.up.railway.app/api/webhooks/evolution/{instance_name}"

            result = supabase.table('connections').update(update_data).eq('instance_name', instance_name).execute()
            logger.info(f"Connection status updated for {instance_name}: {status}, result: {result.data}")

        elif parsed['event'] == 'presence':
            phone_raw = parsed.get('remote_jid')
            presence = parsed.get('presence')

            if phone_raw and presence:
                phone = normalize_phone_number(phone_raw) or (str(phone_raw or '').strip())
                conn = supabase.table('connections').select('tenant_id, id').eq('instance_name', instance_name).execute()
                if conn.data:
                    tenant_id = conn.data[0]['tenant_id']
                    connection_id = conn.data[0].get('id')
                    query = supabase.table('conversations').select('id').eq('tenant_id', tenant_id).eq('contact_phone', phone)
                    if connection_id:
                        query = query.eq('connection_id', connection_id)
                    conv = query.execute()
                    if (not conv.data) and str(phone_raw or '').strip() and str(phone_raw).strip() != phone:
                        query2 = supabase.table('conversations').select('id').eq('tenant_id', tenant_id).eq('contact_phone', str(phone_raw).strip())
                        if connection_id:
                            query2 = query2.eq('connection_id', connection_id)
                        conv = query2.execute()

                    if conv.data:
                        typing_data = {
                            'conversation_id': conv.data[0]['id'],
                            'phone': phone,
                            'is_typing': presence == 'composing',
                            'timestamp': datetime.utcnow().isoformat()
                        }
                        try:
                            supabase.table('typing_events').upsert(typing_data, on_conflict='conversation_id').execute()
                        except Exception:
                            pass

    except Exception as e:
        logger.error(f"Webhook processing error: {e}")

    return {"success": True}


async def _process_evolution_webhook(instance_name: str, payload: dict, *, from_queue: bool) -> dict:
    return await _process_generic_webhook("evolution", instance_name, payload, from_queue=from_queue)


async def _process_uazapi_webhook(instance_name: str, payload: dict, *, from_queue: bool) -> dict:
    return await _process_generic_webhook("uazapi", instance_name, payload, from_queue=from_queue)

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
        if _is_missing_table_error(e, "auto_messages"):
            raise _auto_messages_missing_table_http()
        logger.error(f"Error getting auto messages: {e}")
        raise HTTPException(status_code=400, detail=str(e))

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
        if _is_missing_table_error(e, "auto_messages"):
            raise _auto_messages_missing_table_http()
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
        if _is_missing_table_error(e, "auto_messages"):
            raise _auto_messages_missing_table_http()
        raise HTTPException(status_code=400, detail=str(e))

@api_router.delete("/auto-messages/{message_id}")
async def delete_auto_message(message_id: str, payload: dict = Depends(verify_token)):
    """Delete an auto message"""
    try:
        supabase.table('auto_messages').delete().eq('id', message_id).execute()
        return {"success": True}
    except Exception as e:
        if _is_missing_table_error(e, "auto_messages"):
            raise _auto_messages_missing_table_http()
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
        if _is_missing_table_error(e, "auto_messages"):
            raise _auto_messages_missing_table_http()
        raise HTTPException(status_code=400, detail=str(e))

@api_router.get("/bulk-campaigns")
async def list_bulk_campaigns(tenant_id: str, payload: dict = Depends(verify_token)):
    try:
        result = (
            supabase.table("bulk_campaigns")
            .select("*")
            .eq("tenant_id", tenant_id)
            .order("created_at", desc=True)
            .limit(200)
            .execute()
        )
        return result.data or []
    except Exception as e:
        if _is_missing_table_error(e, "bulk_campaigns"):
            raise _bulk_campaigns_missing_table_http("bulk_campaigns")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/bulk-campaigns")
async def create_bulk_campaign(tenant_id: str, data: BulkCampaignCreate, payload: dict = Depends(verify_token)):
    try:
        now = datetime.utcnow().isoformat()
        row = {
            "tenant_id": tenant_id,
            "created_by": payload.get("user_id"),
            "name": data.name,
            "template_body": data.template_body,
            "connection_id": data.connection_id,
            "status": "draft",
            "selection_mode": data.selection_mode,
            "selection_payload": data.selection_payload or {},
            "delay_seconds": int(data.delay_seconds or 0),
            "start_at": data.start_at,
            "recurrence": data.recurrence or "none",
            "next_run_at": None,
            "max_messages_per_period": data.max_messages_per_period,
            "period_unit": data.period_unit,
            "created_at": now,
            "updated_at": now,
        }
        result = supabase.table("bulk_campaigns").insert(row).execute()
        if not result.data:
            raise HTTPException(status_code=400, detail="Erro ao criar campanha")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_table_error(e, "bulk_campaigns"):
            raise _bulk_campaigns_missing_table_http("bulk_campaigns")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.put("/bulk-campaigns/{campaign_id}")
async def update_bulk_campaign(campaign_id: str, data: BulkCampaignUpdate, payload: dict = Depends(verify_token)):
    try:
        now = datetime.utcnow().isoformat()
        update_data: Dict[str, Any] = {"updated_at": now}
        for k in (
            "name",
            "template_body",
            "connection_id",
            "selection_mode",
            "selection_payload",
            "delay_seconds",
            "start_at",
            "recurrence",
            "max_messages_per_period",
            "period_unit",
            "status",
        ):
            v = getattr(data, k)
            if v is not None:
                update_data[k] = v
        result = supabase.table("bulk_campaigns").update(update_data).eq("id", campaign_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Campanha não encontrada")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_table_error(e, "bulk_campaigns"):
            raise _bulk_campaigns_missing_table_http("bulk_campaigns")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.delete("/bulk-campaigns/{campaign_id}")
async def delete_bulk_campaign(campaign_id: str, payload: dict = Depends(verify_token)):
    try:
        supabase.table("bulk_campaigns").delete().eq("id", campaign_id).execute()
        return {"success": True}
    except Exception as e:
        if _is_missing_table_error(e, "bulk_campaigns"):
            raise _bulk_campaigns_missing_table_http("bulk_campaigns")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/bulk-campaigns/{campaign_id}/recipients")
async def set_bulk_campaign_recipients(campaign_id: str, tenant_id: str, data: BulkCampaignRecipientsSet, payload: dict = Depends(verify_token)):
    try:
        now = datetime.utcnow().isoformat()
        ids = [str(x).strip() for x in (data.contact_ids or []) if str(x).strip()]
        ids = list(dict.fromkeys(ids))
        result = (
            supabase.table("bulk_campaigns")
            .update({
                "selection_mode": "explicit",
                "selection_payload": {"contact_ids": ids},
                "updated_at": now,
            })
            .eq("id", campaign_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Campanha não encontrada")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_table_error(e, "bulk_campaigns"):
            raise _bulk_campaigns_missing_table_http("bulk_campaigns")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/bulk-campaigns/{campaign_id}/schedule")
async def schedule_bulk_campaign(campaign_id: str, tenant_id: str, data: BulkCampaignSchedule, payload: dict = Depends(verify_token)):
    try:
        now_dt = datetime.utcnow()
        now = now_dt.isoformat()
        start_dt = _bulk_parse_dt(data.start_at) or now_dt
        next_run_at = start_dt.isoformat()
        update_data: Dict[str, Any] = {
            "status": "scheduled",
            "start_at": start_dt.isoformat(),
            "next_run_at": next_run_at,
            "updated_at": now,
        }
        if data.recurrence is not None:
            update_data["recurrence"] = data.recurrence
        if data.delay_seconds is not None:
            update_data["delay_seconds"] = int(data.delay_seconds or 0)
        if data.max_messages_per_period is not None:
            update_data["max_messages_per_period"] = data.max_messages_per_period
        if data.period_unit is not None:
            update_data["period_unit"] = data.period_unit
        result = (
            supabase.table("bulk_campaigns")
            .update(update_data)
            .eq("id", campaign_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Campanha não encontrada")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_table_error(e, "bulk_campaigns"):
            raise _bulk_campaigns_missing_table_http("bulk_campaigns")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/bulk-campaigns/{campaign_id}/pause")
async def pause_bulk_campaign(campaign_id: str, tenant_id: str, payload: dict = Depends(verify_token)):
    try:
        now = datetime.utcnow().isoformat()
        result = (
            supabase.table("bulk_campaigns")
            .update({"status": "paused", "paused_at": now, "updated_at": now})
            .eq("id", campaign_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Campanha não encontrada")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_table_error(e, "bulk_campaigns"):
            raise _bulk_campaigns_missing_table_http("bulk_campaigns")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/bulk-campaigns/{campaign_id}/resume")
async def resume_bulk_campaign(campaign_id: str, tenant_id: str, payload: dict = Depends(verify_token)):
    try:
        now_dt = datetime.utcnow()
        now = now_dt.isoformat()
        result = (
            supabase.table("bulk_campaigns")
            .update({"status": "scheduled", "paused_at": None, "next_run_at": now, "updated_at": now})
            .eq("id", campaign_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Campanha não encontrada")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_table_error(e, "bulk_campaigns"):
            raise _bulk_campaigns_missing_table_http("bulk_campaigns")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/bulk-campaigns/{campaign_id}/cancel")
async def cancel_bulk_campaign(campaign_id: str, tenant_id: str, payload: dict = Depends(verify_token)):
    try:
        now = datetime.utcnow().isoformat()
        result = (
            supabase.table("bulk_campaigns")
            .update({"status": "cancelled", "cancelled_at": now, "updated_at": now})
            .eq("id", campaign_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Campanha não encontrada")
        try:
            supabase.table("bulk_campaign_recipients").update({"status": "skipped", "error": "Campanha cancelada", "updated_at": now}).eq("campaign_id", campaign_id).eq("status", "scheduled").execute()
        except Exception:
            pass
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_table_error(e, "bulk_campaigns"):
            raise _bulk_campaigns_missing_table_http("bulk_campaigns")
        if _is_missing_table_error(e, "bulk_campaign_recipients"):
            raise _bulk_campaigns_missing_table_http("bulk_campaign_recipients")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.get("/bulk-campaigns/{campaign_id}/stats")
async def bulk_campaign_stats(campaign_id: str, tenant_id: str, payload: dict = Depends(verify_token)):
    try:
        campaign_r = supabase.table("bulk_campaigns").select("*").eq("id", campaign_id).eq("tenant_id", tenant_id).limit(1).execute()
        if not campaign_r.data:
            raise HTTPException(status_code=404, detail="Campanha não encontrada")
        campaign = campaign_r.data[0]

        def count_status(where: Dict[str, Any]) -> int:
            q = supabase.table("bulk_campaign_recipients").select("id", count="exact")
            for k, v in where.items():
                q = q.eq(k, v)
            r = q.execute()
            return int(getattr(r, "count", 0) or 0)

        totals = {
            "scheduled": count_status({"campaign_id": campaign_id, "status": "scheduled"}),
            "sending": count_status({"campaign_id": campaign_id, "status": "sending"}),
            "sent": count_status({"campaign_id": campaign_id, "status": "sent"}),
            "failed": count_status({"campaign_id": campaign_id, "status": "failed"}),
            "skipped": count_status({"campaign_id": campaign_id, "status": "skipped"}),
        }

        if sum(int(v or 0) for v in totals.values()) == 0:
            selection_mode = str(campaign.get("selection_mode") or "").strip().lower()
            selection_payload = campaign.get("selection_payload") or {}
            if selection_mode == "explicit" and isinstance(selection_payload, dict):
                raw_ids = selection_payload.get("contact_ids") or selection_payload.get("contactIds") or selection_payload.get("contacts") or []
                planned_ids: List[str] = []
                if isinstance(raw_ids, list):
                    for item in raw_ids:
                        if isinstance(item, str) and item.strip():
                            planned_ids.append(item.strip())
                        elif isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("id").strip():
                            planned_ids.append(item.get("id").strip())
                planned_ids = list(dict.fromkeys(planned_ids))
                totals["scheduled"] = len(planned_ids)

        run = None
        try:
            run_r = supabase.table("bulk_campaign_runs").select("*").eq("campaign_id", campaign_id).order("created_at", desc=True).limit(1).execute()
            if run_r.data:
                run = run_r.data[0]
        except Exception:
            run = None

        return {"campaign": campaign, "totals": totals, "lastRun": run}
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_table_error(e, "bulk_campaigns"):
            raise _bulk_campaigns_missing_table_http("bulk_campaigns")
        if _is_missing_table_error(e, "bulk_campaign_recipients"):
            raise _bulk_campaigns_missing_table_http("bulk_campaign_recipients")
        if _is_missing_table_error(e, "bulk_campaign_runs"):
            raise _bulk_campaigns_missing_table_http("bulk_campaign_runs")
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
async def get_analytics_overview(tenant_id: Optional[str] = Query(None), payload: dict = Depends(verify_token)):
    """Get analytics overview for tenant"""
    try:
        user_tenant_id = get_user_tenant_id(payload)
        effective_tenant_id = user_tenant_id
        if not effective_tenant_id and payload.get('role') == 'superadmin':
            effective_tenant_id = tenant_id
        if not effective_tenant_id:
            raise HTTPException(status_code=403, detail="Tenant não identificado")

        try:
            conversations = _db_call_with_retry(
                "analytics.conversations.total",
                lambda: supabase.table('conversations').select('status', count='exact').eq('tenant_id', effective_tenant_id).execute()
            )
            open_count = _db_call_with_retry(
                "analytics.conversations.open",
                lambda: supabase.table('conversations').select('id', count='exact').eq('tenant_id', effective_tenant_id).eq('status', 'open').execute()
            )
            pending_count = _db_call_with_retry(
                "analytics.conversations.pending",
                lambda: supabase.table('conversations').select('id', count='exact').eq('tenant_id', effective_tenant_id).eq('status', 'pending').execute()
            )
            resolved_count = _db_call_with_retry(
                "analytics.conversations.resolved",
                lambda: supabase.table('conversations').select('id', count='exact').eq('tenant_id', effective_tenant_id).eq('status', 'resolved').execute()
            )
        except Exception as e:
            if _is_missing_table_or_schema_error(e, "conversations"):
                conversations = type("x", (), {"count": 0})()
                open_count = type("x", (), {"count": 0})()
                pending_count = type("x", (), {"count": 0})()
                resolved_count = type("x", (), {"count": 0})()
            else:
                raise

        this_month = 0
        try:
            tenant_row = _db_call_with_retry(
                "analytics.tenants.messages_this_month",
                lambda: supabase.table('tenants').select('messages_this_month').eq('id', effective_tenant_id).limit(1).execute()
            )
            if tenant_row.data and isinstance(tenant_row.data[0], dict):
                this_month = int(tenant_row.data[0].get('messages_this_month') or 0)
        except Exception:
            this_month = 0

        today_messages_count = 0
        try:
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            today_messages = _db_call_with_retry(
                "analytics.messages.today",
                lambda: supabase.table('messages').select('id', count='exact').gte('timestamp', today).execute()
            )
            today_messages_count = int(getattr(today_messages, "count", 0) or 0)
        except Exception:
            today_messages_count = 0

        online_agents = 0
        try:
            active_agents = _db_call_with_retry(
                "analytics.agents.online",
                lambda: supabase.table('users').select('id', count='exact').eq('tenant_id', effective_tenant_id).eq('status', 'online').execute()
            )
            online_agents = int(getattr(active_agents, "count", 0) or 0)
        except Exception:
            online_agents = 0

        return {
            'conversations': {
                'total': getattr(conversations, "count", 0) or 0,
                'open': getattr(open_count, "count", 0) or 0,
                'pending': getattr(pending_count, "count", 0) or 0,
                'resolved': getattr(resolved_count, "count", 0) or 0
            },
            'messages': {
                'thisMonth': this_month,
                'today': today_messages_count,
                'avgPerDay': (this_month // 30) if this_month else 0
            },
            'agents': {
                'online': online_agents
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        if _is_supabase_not_configured_error(e):
            return {
                'conversations': {'total': 0, 'open': 0, 'pending': 0, 'resolved': 0},
                'messages': {'thisMonth': 0, 'today': 0, 'avgPerDay': 0},
                'agents': {'online': 0},
                'notConfigured': True
            }
        if _is_transient_db_error(e):
            raise HTTPException(status_code=503, detail="Banco de dados indisponível.")
        logger.error(f"Error getting analytics overview: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao carregar analytics: {str(e)}")

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


def _summarize_for_log(value: Any, max_len: int = 160) -> str:
    s = str(value or "")
    if not s:
        return ""
    if s.lower().startswith("data:"):
        return f"data_url(len={len(s)})"
    if len(s) <= max_len:
        return s
    return s[:max_len] + "…"


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extract_image_dimensions(head: bytes) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    if not head:
        return None, None, None

    if head.startswith(b"\x89PNG\r\n\x1a\n") and len(head) >= 24:
        if head[12:16] == b"IHDR" and len(head) >= 24:
            w = int.from_bytes(head[16:20], "big", signed=False)
            h = int.from_bytes(head[20:24], "big", signed=False)
            if w > 0 and h > 0:
                return w, h, "png"
        return None, None, "png"

    if (head.startswith(b"GIF87a") or head.startswith(b"GIF89a")) and len(head) >= 10:
        w = int.from_bytes(head[6:8], "little", signed=False)
        h = int.from_bytes(head[8:10], "little", signed=False)
        if w > 0 and h > 0:
            return w, h, "gif"
        return None, None, "gif"

    if head.startswith(b"\xFF\xD8\xFF"):
        i = 2
        n = len(head)
        while i + 1 < n:
            if head[i] != 0xFF:
                i += 1
                continue
            while i < n and head[i] == 0xFF:
                i += 1
            if i >= n:
                break
            marker = head[i]
            i += 1
            if marker in {0xD8, 0xD9}:
                continue
            if marker == 0xDA:
                break
            if i + 1 >= n:
                break
            seg_len = int.from_bytes(head[i:i + 2], "big", signed=False)
            if seg_len < 2:
                break
            seg_start = i + 2
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                if seg_start + 7 <= n:
                    h = int.from_bytes(head[seg_start + 1:seg_start + 3], "big", signed=False)
                    w = int.from_bytes(head[seg_start + 3:seg_start + 5], "big", signed=False)
                    if w > 0 and h > 0:
                        return w, h, "jpeg"
                return None, None, "jpeg"
            i = seg_start + (seg_len - 2)
        return None, None, "jpeg"

    if len(head) >= 16 and head[0:4] == b"RIFF" and head[8:12] == b"WEBP":
        if len(head) >= 30 and head[12:16] == b"VP8X":
            w = 1 + int.from_bytes(head[24:27], "little", signed=False)
            h = 1 + int.from_bytes(head[27:30], "little", signed=False)
            if w > 0 and h > 0:
                return w, h, "webp"
        return None, None, "webp"

    return None, None, None


def _log_media_event(event: str, fields: Dict[str, Any]) -> None:
    safe_fields: Dict[str, Any] = {}
    for k, v in (fields or {}).items():
        if k in {"url", "media_url", "mediaUrl"}:
            safe_fields[k] = _summarize_for_log(v, max_len=200)
            safe_fields[f"{k}_len"] = len(str(v or ""))
        else:
            safe_fields[k] = v
    try:
        logger.info(json.dumps({"event": event, **safe_fields}, ensure_ascii=False))
    except Exception:
        logger.info(f"{event} {safe_fields}")


def _estimate_base64_decoded_size(b64: str) -> int:
    s = "".join((b64 or "").split())
    if not s:
        return 0
    pad = 0
    if s.endswith("=="):
        pad = 2
    elif s.endswith("="):
        pad = 1
    return max(0, (len(s) * 3) // 4 - pad)


def _decode_base64_head(b64: str, max_bytes: int = 2048) -> bytes:
    s = "".join((b64 or "").split())
    if not s or max_bytes <= 0:
        return b""
    needed_chars = ((max_bytes * 4 + 2) // 3 + 3) // 4 * 4
    prefix = s[:needed_chars]
    prefix = prefix + ("=" * ((-len(prefix)) % 4))
    try:
        decoded = base64.b64decode(prefix, validate=False)
        return (decoded or b"")[:max_bytes]
    except Exception:
        return b""


def _parse_data_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    u = str(url or "").strip()
    if not u.lower().startswith("data:"):
        return None, None
    if ";base64," not in u:
        return None, None
    try:
        header, b64 = u.split(",", 1)
    except Exception:
        return None, None
    mime = None
    try:
        if header.lower().startswith("data:"):
            mime = header[5:].split(";", 1)[0].strip().lower() or None
    except Exception:
        mime = None
    return mime, (b64 or "").strip() or None


def _derive_media_metadata_from_url(
    *,
    media_type: str,
    media_url: str,
    media_name: str,
    max_size_bytes: int = 10 * 1024 * 1024,
) -> Dict[str, Any]:
    mt = str(media_type or "").strip().lower()
    name = str(media_name or "").strip()
    url = str(media_url or "").strip()

    declared_mime = None
    head = b""
    size = None

    data_mime, data_b64 = _parse_data_url(url)
    if data_mime and data_b64:
        declared_mime = data_mime
        size = _estimate_base64_decoded_size(data_b64)
        if size > max_size_bytes:
            raise HTTPException(status_code=400, detail="Arquivo muito grande. Máximo: 10MB")
        head = _decode_base64_head(data_b64, max_bytes=2048)

    detected = detect_media_kind(
        declared_mime_type=declared_mime,
        filename=name or None,
        head_bytes=(head[:96] if head else b""),
        hinted_kind=(mt if mt in {"image", "video", "audio", "document", "sticker"} else None),
    )
    w, h, fmt = _extract_image_dimensions(head[:96] if head else b"")
    meta: Dict[str, Any] = {
        "media_kind": detected.kind,
        "mime_type": detected.mime_type,
        "file_name": name or None,
    }
    if size is not None:
        meta["file_size"] = size
    if w is not None:
        meta["width"] = w
    if h is not None:
        meta["height"] = h
    if fmt is not None:
        meta["format"] = fmt
    return meta

@api_router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    conversation_id: str = Form(...),
    payload: dict = Depends(verify_token)
):
    """Upload a file and return its URL"""
    try:
        _require_conversation_access(conversation_id, payload)
        upload_id = str(uuid.uuid4())
        # Read file content
        content = await file.read()
        file_size = len(content)
        head = content[:96] if isinstance(content, (bytes, bytearray)) else b""
        declared_ct = file.content_type
        filename = file.filename
        ext = ""
        try:
            ext = (Path(filename).suffix or "").lower()
        except Exception:
            ext = ""
        sha256 = _sha256_hex(content) if isinstance(content, (bytes, bytearray)) else ""
        w, h, fmt = _extract_image_dimensions(head)

        _log_media_event(
            "upload.attempt",
            {
                "upload_id": upload_id,
                "conversation_id": conversation_id,
                "tenant_id": payload.get("tenant_id"),
                "user_id": payload.get("user_id"),
                "filename": filename,
                "ext": ext,
                "declared_content_type": declared_ct,
                "size": file_size,
                "sha256": sha256,
                "width": w,
                "height": h,
                "format": fmt,
            },
        )
        
        # Validate file size (10MB max)
        max_size = 10 * 1024 * 1024
        if file_size > max_size:
            _log_media_event(
                "upload.rejected",
                {
                    "upload_id": upload_id,
                    "reason": "file_too_large",
                    "filename": filename,
                    "size": file_size,
                    "max_size": max_size,
                },
            )
            raise HTTPException(status_code=400, detail="Arquivo muito grande. Máximo: 10MB")
        
        # Generate unique filename
        file_ext = file.filename.split('.')[-1] if '.' in file.filename else 'bin'
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        
        detected = detect_media_kind(
            declared_mime_type=file.content_type,
            filename=file.filename,
            head_bytes=head,
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

            _log_media_event(
                "upload.storage.success",
                {
                    "upload_id": upload_id,
                    "bucket": "uploads",
                    "storage_path": storage_path,
                    "file_type": file_type,
                    "content_type": content_type,
                    "result_type": str(type(result)),
                    "url": public_url,
                },
            )
            
        except Exception as storage_error:
            _log_media_event(
                "upload.storage.failure",
                {
                    "upload_id": upload_id,
                    "bucket": "uploads",
                    "storage_path": storage_path,
                    "file_type": file_type,
                    "content_type": content_type,
                    "error": str(storage_error),
                    "error_type": str(type(storage_error)),
                },
            )
            # Fallback: encode as base64 and store in database or return as data URL
            encoded = base64.b64encode(content).decode('utf-8')
            public_url = f"data:{content_type};base64,{encoded}"

        _log_media_event(
            "upload.success",
            {
                "upload_id": upload_id,
                "filename": filename,
                "file_type": file_type,
                "content_type": content_type,
                "size": file_size,
                "sha256": sha256,
                "url": public_url,
            },
        )
        
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
        _log_media_event(
            "upload.error",
            {
                "conversation_id": conversation_id,
                "tenant_id": payload.get("tenant_id") if isinstance(payload, dict) else None,
                "user_id": payload.get("user_id") if isinstance(payload, dict) else None,
                "error": str(e),
                "error_type": str(type(e)),
            },
        )
        raise HTTPException(status_code=500, detail=f"Erro ao fazer upload: {str(e)}")


class MediaInspectRequest(BaseModel):
    url: str


@api_router.post("/media/inspect")
async def inspect_media(request: MediaInspectRequest, payload: dict = Depends(verify_token)):
    url = str(request.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url é obrigatório")

    start = time.time()
    _log_media_event(
        "media.inspect.attempt",
        {
            "url": url,
            "tenant_id": payload.get("tenant_id"),
            "user_id": payload.get("user_id"),
        },
    )

    def _infer_ext_from_url(u: str) -> str:
        try:
            path = u.split("?", 1)[0].split("#", 1)[0]
            return (Path(path).suffix or "").lower()
        except Exception:
            return ""

    ext = _infer_ext_from_url(url)
    declared_mime = None
    content_length = None
    head = b""
    sha256 = None
    warnings: List[str] = []

    if url.lower().startswith("data:") and ";base64," in url:
        try:
            header, b64 = url.split(",", 1)
            declared_mime = header[5:].split(";", 1)[0].strip() if header.startswith("data:") else None
            padded = b64.strip() + ("=" * ((4 - (len(b64.strip()) % 4)) % 4))
            raw = base64.b64decode(padded, validate=False)
            content_length = len(raw)
            head = raw[:96]
            sha256 = _sha256_hex(raw)
        except Exception as e:
            _log_media_event(
                "media.inspect.failure",
                {"url": url, "error": str(e), "error_type": str(type(e))},
            )
            raise HTTPException(status_code=400, detail="data URL inválida")
    else:
        if not (url.startswith("http://") or url.startswith("https://")):
            raise HTTPException(status_code=400, detail="Apenas http(s) URLs ou data URLs são suportadas")
        timeout = httpx.Timeout(10.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            try:
                head_resp = await client.head(url)
                declared_mime = (head_resp.headers.get("content-type") or "").split(";", 1)[0].strip() or None
                cl = (head_resp.headers.get("content-length") or "").strip()
                content_length = int(cl) if cl.isdigit() else None
            except Exception:
                declared_mime = None
                content_length = None
            try:
                resp = await client.get(url, headers={"Range": "bytes=0-2047"})
                resp.raise_for_status()
                head = (resp.content or b"")[:96]
            except Exception as e:
                _log_media_event(
                    "media.inspect.failure",
                    {"url": url, "error": str(e), "error_type": str(type(e))},
                )
                raise HTTPException(status_code=502, detail="Falha ao buscar cabeçalho da mídia")

    detected = detect_media_kind(declared_mime_type=declared_mime, filename=ext or None, head_bytes=head)
    w, h, fmt = _extract_image_dimensions(head)

    if ext and detected.mime_type and detected.mime_type.startswith("image/"):
        expected_from_ext = detect_media_kind(filename=f"file{ext}").mime_type
        if expected_from_ext and expected_from_ext != detected.mime_type:
            warnings.append("extensao_nao_confere_com_conteudo")

    if content_length is not None and content_length > 10 * 1024 * 1024:
        warnings.append("acima_do_limite_10mb")

    elapsed_ms = int((time.time() - start) * 1000)
    _log_media_event(
        "media.inspect.success",
        {
            "url": url,
            "ext": ext,
            "declared_mime": declared_mime,
            "detected_mime": detected.mime_type,
            "detected_kind": detected.kind,
            "confidence": detected.confidence,
            "size": content_length,
            "width": w,
            "height": h,
            "format": fmt,
            "sha256": sha256,
            "warnings": warnings,
            "duration_ms": elapsed_ms,
        },
    )

    return {
        "url": url,
        "ext": ext,
        "declaredMime": declared_mime,
        "detectedMime": detected.mime_type,
        "detectedKind": detected.kind,
        "confidence": detected.confidence,
        "size": content_length,
        "width": w,
        "height": h,
        "format": fmt,
        "sha256": sha256,
        "warnings": warnings,
        "durationMs": elapsed_ms,
    }


class MediaLoadLog(BaseModel):
    url: str
    kind: Optional[str] = None
    messageId: Optional[str] = None
    success: bool
    error: Optional[str] = None
    ts: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


@api_router.post("/media/log")
async def log_media_load(body: MediaLoadLog, payload: dict = Depends(verify_token)):
    _log_media_event(
        "media.load",
        {
            "success": bool(body.success),
            "kind": body.kind,
            "message_id": body.messageId,
            "url": body.url,
            "error": body.error,
            "ts": body.ts,
            "tenant_id": payload.get("tenant_id"),
            "user_id": payload.get("user_id"),
            "extra": body.extra or {},
        },
    )
    return {"ok": True}

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
    _require_conversation_access(conversation_id, payload)
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

    _enforce_messages_limit(conversation.get('tenant_id'))
    
    derived_meta: Dict[str, Any] = {}
    try:
        derived_meta = _derive_media_metadata_from_url(
            media_type=media_type,
            media_url=media_url,
            media_name=media_name,
            max_size_bytes=10 * 1024 * 1024,
        )
    except HTTPException:
        raise
    except Exception as e:
        _log_media_event(
            "message.media.metadata_error",
            {
                "conversation_id": conversation_id,
                "tenant_id": conversation.get("tenant_id"),
                "user_id": payload.get("user_id") if isinstance(payload, dict) else None,
                "media_type": media_type,
                "media_name": media_name,
                "media_url": media_url,
                "error": str(e),
                "error_type": str(type(e)),
            },
        )
        derived_meta = {
            "media_kind": str(media_type or "").strip().lower() or "document",
            "mime_type": "",
            "file_name": str(media_name or "").strip() or None,
        }

    _log_media_event(
        "message.media.attempt",
        {
            "conversation_id": conversation_id,
            "tenant_id": conversation.get("tenant_id"),
            "user_id": payload.get("user_id") if isinstance(payload, dict) else None,
            "media_type": media_type,
            "media_name": media_name,
            "media_url": media_url,
            "meta_kind": derived_meta.get("media_kind"),
            "meta_mime": derived_meta.get("mime_type"),
            "meta_size": derived_meta.get("file_size"),
            "meta_width": derived_meta.get("width"),
            "meta_height": derived_meta.get("height"),
        },
    )

    # Save message to database
    connection_provider = (connection.get('provider') if isinstance(connection, dict) else None)
    connection_status = (connection.get('status') if isinstance(connection, dict) else None)
    is_evolution = str(connection_provider or '').lower() == 'evolution'
    is_connected = str(connection_status or '').lower() in ['connected', 'open']
    instance_name = connection.get('instance_name') if isinstance(connection, dict) else None
    remote_jid_value = f"{conversation.get('contact_phone')}@s.whatsapp.net" if conversation.get('contact_phone') else None

    insert_meta = dict(derived_meta or {})
    if connection and is_evolution and is_connected and instance_name:
        insert_meta.update(
            {
                "remote_jid": remote_jid_value,
                "instance_name": instance_name,
                "from_me": True,
            }
        )

    data = {
        'conversation_id': conversation_id,
        'content': message_content,
        'type': media_type,
        'direction': 'outbound',
        'status': 'sent',
        'media_url': media_url,
        'metadata': insert_meta,
    }
    
    result = supabase.table('messages').insert(data).execute()
    _log_media_event(
        "message.media.inserted",
        {
            "conversation_id": conversation_id,
            "tenant_id": conversation.get("tenant_id"),
            "message_id": (result.data[0].get("id") if result and result.data else None),
            "media_type": media_type,
            "media_name": media_name,
            "media_url": media_url,
            "meta_kind": insert_meta.get("media_kind"),
            "meta_mime": insert_meta.get("mime_type"),
            "meta_size": insert_meta.get("file_size"),
        },
    )
    
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
        metadata={
            'conversation_id': conversation_id,
            'type': media_type,
            'media_name': media_name,
            'media_url': _summarize_for_log(media_url, max_len=200),
            'media_url_len': len(str(media_url or '')),
            'mime_type': insert_meta.get('mime_type'),
            'media_kind': insert_meta.get('media_kind'),
            'file_size': insert_meta.get('file_size'),
        }
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
            if background_tasks:
                background_tasks.add_task(
                    send_provider_message,
                    conn_ref,
                    conversation["contact_phone"],
                    str(media_url or ""),
                    media_type,
                    result.data[0]["id"],
                    caption=message_content,
                    filename=media_name,
                )
            else:
                await send_provider_message(
                    conn_ref,
                    conversation["contact_phone"],
                    str(media_url or ""),
                    media_type,
                    result.data[0]["id"],
                    caption=message_content,
                    filename=media_name,
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

async def send_whatsapp_media(instance_name: str, phone: str, media_type: str, media_url: str, caption: str, *rest):
    """Background task to send WhatsApp media"""
    filename = None
    message_id = None
    if len(rest) == 1:
        message_id = rest[0]
    elif len(rest) == 2:
        filename, message_id = rest
    else:
        raise TypeError("send_whatsapp_media recebeu argumentos inválidos")

    conn_ref = ConnectionRef(tenant_id="", provider="evolution", instance_name=instance_name, config={})
    await send_provider_message(
        conn_ref,
        phone,
        str(media_url or ""),
        str(media_type or "document"),
        str(message_id),
        caption=caption or "",
        filename=filename,
    )

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
        def _looks_like_uuid(value: Any) -> bool:
            s = str(value or "").strip().lower()
            if not s:
                return False
            return bool(re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", s))

        def _normalize_remote_jid(value: Any) -> str:
            s = str(value or "").strip()
            if not s:
                return ""
            s = s.replace(" ", "")
            if "@" in s:
                return s
            digits = "".join(ch for ch in s if ch.isdigit())
            if digits:
                return f"{digits}@s.whatsapp.net"
            return s

        def _extract_base64_and_mime(obj: Any) -> Tuple[Optional[str], Optional[str]]:
            def _walk(node: Any, depth: int = 0) -> Tuple[Optional[str], Optional[str]]:
                if depth > 5:
                    return None, None
                if isinstance(node, dict):
                    b64 = node.get("base64") or node.get("base64Data") or node.get("data_base64")
                    mime = (
                        node.get("mimetype")
                        or node.get("mimeType")
                        or node.get("contentType")
                        or node.get("type")
                    )
                    if isinstance(b64, str) and b64.strip():
                        return b64.strip(), (str(mime).strip() if mime else None)
                    for key in ("data", "result", "response", "message", "payload"):
                        if key in node:
                            found_b64, found_mime = _walk(node.get(key), depth + 1)
                            if found_b64:
                                return found_b64, found_mime
                    for v in node.values():
                        found_b64, found_mime = _walk(v, depth + 1)
                        if found_b64:
                            return found_b64, found_mime
                if isinstance(node, list):
                    for v in node:
                        found_b64, found_mime = _walk(v, depth + 1)
                        if found_b64:
                            return found_b64, found_mime
                return None, None

            return _walk(obj, 0)

        if not (message_id or "").strip():
            raise HTTPException(status_code=400, detail="message_id é obrigatório")
        if not (remote_jid or "").strip():
            raise HTTPException(status_code=400, detail="remote_jid é obrigatório")
        if not (instance_name or "").strip():
            raise HTTPException(status_code=400, detail="instance_name é obrigatório")

        evo_message_id = message_id
        resolved_message = None
        try:
            resolved_message = (
                supabase.table('messages')
                .select('id, conversation_id, external_id')
                .eq('id', message_id)
                .limit(1)
                .execute()
            )
        except Exception:
            resolved_message = None

        row = None
        if resolved_message and getattr(resolved_message, "data", None):
            row = resolved_message.data[0]
        else:
            try:
                resolved_message = (
                    supabase.table('messages')
                    .select('id, conversation_id, external_id')
                    .eq('external_id', message_id)
                    .limit(1)
                    .execute()
                )
            except Exception:
                resolved_message = None
            if resolved_message and getattr(resolved_message, "data", None):
                row = resolved_message.data[0]

        if row:
            user_tenant_id = get_user_tenant_id(payload)
            if user_tenant_id:
                conv = supabase.table('conversations').select('tenant_id').eq('id', row.get('conversation_id')).limit(1).execute()
                if not conv.data:
                    raise HTTPException(status_code=404, detail="Conversa não encontrada")
                if conv.data[0].get('tenant_id') != user_tenant_id:
                    raise HTTPException(status_code=403, detail="Acesso negado")

            external_id = (row.get('external_id') or '').strip() if isinstance(row.get('external_id'), str) else (row.get('external_id') or '')
            if external_id:
                evo_message_id = str(external_id).strip()

        # Try to extract media URL and provider message id from stored message data.
        media_url = None
        mimetype_hint = None
        msg_type = 'unknown'
        extracted_provider_id = None
        internal_message_uuid = row.get('id') if isinstance(row, dict) else None

        def _is_plausible_provider_id(value: Any) -> bool:
            s = str(value or "").strip()
            if not s:
                return False
            lowered = s.lower()
            if lowered.startswith("http://") or lowered.startswith("https://"):
                return False
            if lowered.startswith("data:"):
                return False
            if "@" in s:
                return False
            if any(ch.isspace() for ch in s):
                return False
            if len(s) < 8 or len(s) > 160:
                return False
            return True

        def _find_provider_id(node: Any, depth: int = 0) -> Optional[str]:
            if depth > 5:
                return None
            if isinstance(node, dict):
                for k in ("external_id", "externalId", "message_id", "messageId", "id", "stanzaId"):
                    if k in node and _is_plausible_provider_id(node.get(k)):
                        return str(node.get(k)).strip()
                key_node = node.get("key")
                if isinstance(key_node, dict):
                    if _is_plausible_provider_id(key_node.get("id")):
                        return str(key_node.get("id")).strip()
                for v in node.values():
                    found = _find_provider_id(v, depth + 1)
                    if found:
                        return found
            if isinstance(node, list):
                for v in node:
                    found = _find_provider_id(v, depth + 1)
                    if found:
                        return found
            return None
            
        try:
            lookup_id = internal_message_uuid or message_id
            msg_full = (
                supabase.table('messages')
                .select('content, type, metadata, media_url, external_id')
                .eq('id', lookup_id)
                .limit(1)
                .execute()
            )
            if (not msg_full.data) and (not internal_message_uuid):
                msg_full = (
                    supabase.table('messages')
                    .select('content, type, metadata, media_url, external_id')
                    .eq('external_id', message_id)
                    .limit(1)
                    .execute()
                )
            if msg_full.data:
                msg_data = msg_full.data[0]
                content = msg_data.get('content')
                metadata = msg_data.get('metadata') or {}
                msg_type = msg_data.get('type') or 'unknown'
                stored_media_url = msg_data.get('media_url')
                extracted_provider_id = _find_provider_id(msg_data) or _find_provider_id(metadata) or _find_provider_id(content)

                if stored_media_url and isinstance(stored_media_url, str):
                    stored_url = stored_media_url.strip()
                    if stored_url.startswith('http://') or stored_url.startswith('https://'):
                        media_url = stored_url
                        mimetype_hint = metadata.get('mime_type') or metadata.get('mimetype') or metadata.get('mimeType')
                        logger.info(f"Found media_url in database for message {lookup_id}: {media_url[:60]}...")

                if not media_url and isinstance(content, dict):
                    media_url = (
                        content.get('url') or content.get('mediaUrl') or
                        content.get('media_url') or content.get('imageUrl') or
                        content.get('videoUrl') or content.get('audioUrl') or
                        content.get('documentUrl')
                    )
                    mimetype_hint = content.get('mimetype') or content.get('mimeType')
                    if media_url:
                        logger.info(f"Found media URL in content dict for message {lookup_id}")

                if not media_url and isinstance(metadata, dict):
                    media_url = (
                        metadata.get('url') or metadata.get('mediaUrl') or
                        metadata.get('media_url') or metadata.get('directPath')
                    )
                    if not mimetype_hint:
                        mimetype_hint = metadata.get('mimetype') or metadata.get('mimeType')
                    if media_url:
                        logger.info(f"Found media URL in metadata for message {lookup_id}")

                if not media_url and isinstance(content, str):
                    content_str = content.strip()
                    if content_str.startswith('http://') or content_str.startswith('https://'):
                        media_url = content_str
                        logger.info(f"Found media URL in content string for message {lookup_id}")
        except Exception as e:
            logger.warning(f"Error fetching message data for fallback: {e}")

        if extracted_provider_id and _is_plausible_provider_id(extracted_provider_id):
            if not (evo_message_id and str(evo_message_id).strip()) or (internal_message_uuid and str(evo_message_id) == str(internal_message_uuid)):
                evo_message_id = extracted_provider_id
            
        if media_url and isinstance(media_url, str) and (media_url.startswith('http://') or media_url.startswith('https://')):
            logger.info(f"Using fallback media URL for message {message_id}: {media_url[:60]}...")
            return {
                "success": True,
                "mediaUrl": media_url,
                "mimetype": mimetype_hint or 'application/octet-stream',
                "kind": msg_type,
                "confidence": 0.5,
                "fallback": True
            }

        if internal_message_uuid and str(evo_message_id) == str(internal_message_uuid) and not extracted_provider_id:
            raise HTTPException(status_code=404, detail="Mídia indisponível para esta mensagem")

        # Call Evolution API to get base64 media
        normalized_remote_jid = _normalize_remote_jid(remote_jid)
        result = await evolution_api.get_base64_from_media_message(
            instance_name=instance_name,
            message_id=evo_message_id,
            remote_jid=normalized_remote_jid,
            from_me=from_me
        )
        
        if not result or not isinstance(result, (dict, list)):
            raise HTTPException(status_code=404, detail="Mídia não encontrada")
        
        # Result should contain base64 and mimetype
        base64_data, mimetype = _extract_base64_and_mime(result)
        if not mimetype:
            mimetype = 'application/octet-stream'
        
        if not base64_data:
            raise HTTPException(status_code=404, detail="Dados da mídia não disponíveis")

        if isinstance(base64_data, str) and base64_data.startswith("data:") and "," in base64_data:
            header, b64 = base64_data.split(",", 1)
            base64_data = b64
            if (not mimetype) or mimetype == 'application/octet-stream':
                try:
                    header_mime = header[5:].split(";", 1)[0].strip()
                    if header_mime:
                        mimetype = header_mime
                except Exception:
                    pass
        
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
        s = str(e or "")
        logger.error(f"Media proxy error: {s}")
        lowered = s.lower()
        if "evolution api não configurada" in lowered:
            raise HTTPException(status_code=500, detail="Evolution API não configurada no backend.")
        if "401" in lowered or "403" in lowered:
            raise HTTPException(status_code=502, detail="Falha ao autenticar na Evolution API.")
        if "404" in lowered or "not found" in lowered or "não encontrado" in lowered or "nao encontrado" in lowered:
            raise HTTPException(status_code=404, detail="Mídia não encontrada na Evolution API.")
        if "400" in lowered or "bad request" in lowered or "invalid" in lowered:
            raise HTTPException(status_code=400, detail="Requisição inválida para obter mídia.")
        if "timeout" in lowered or "timed out" in lowered or "502" in lowered or "503" in lowered or "504" in lowered:
            raise HTTPException(status_code=503, detail="Evolution API indisponível.")
        raise HTTPException(status_code=502, detail="Erro ao obter mídia.")

# Mount uploads directory for static file serving
uploads_dir = (os.getenv("UPLOADS_DIR") or "").strip()
uploads_path = Path(uploads_dir) if uploads_dir else (ROOT_DIR / "uploads")
try:
    uploads_path.mkdir(parents=True, exist_ok=True)
except Exception:
    uploads_path = Path(tempfile.gettempdir()) / "uploads"
    uploads_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")

# Include the router in the main app
app.include_router(api_router)



@app.on_event("startup")
async def startup_event():
    timeout_s = float((os.getenv("STARTUP_SCHEMA_TIMEOUT_SECONDS") or "10").strip() or "10")
    try:
        await asyncio.wait_for(asyncio.to_thread(_ensure_system_settings_schema), timeout=timeout_s)
    except Exception:
        pass
    sql = """
    ALTER TABLE users ADD COLUMN IF NOT EXISTS job_title VARCHAR(120);
    ALTER TABLE users ADD COLUMN IF NOT EXISTS department VARCHAR(120);
    ALTER TABLE users ADD COLUMN IF NOT EXISTS signature_enabled BOOLEAN DEFAULT true;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS signature_include_title BOOLEAN DEFAULT false;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS signature_include_department BOOLEAN DEFAULT false;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    ALTER TABLE messages ALTER COLUMN media_url TYPE TEXT;
    """
    try:
        await asyncio.wait_for(
            asyncio.to_thread(lambda: supabase.rpc("exec_sql", {"sql": sql}).execute()),
            timeout=timeout_s,
        )
    except Exception:
        pass
    logger.info("WhatsApp CRM API v2.0 started successfully")
