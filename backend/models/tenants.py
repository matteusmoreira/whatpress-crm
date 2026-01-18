"""Modelos relacionados a tenants, planos e usuários."""
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional


# ==================== TENANTS ====================

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


class TenantRegister(BaseModel):
    tenant_name: str
    tenant_slug: str
    admin_name: str
    admin_email: str
    admin_password: str
    plan: str = "free"


# ==================== PLANS ====================

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


# ==================== USERS ====================

class UserCreate(BaseModel):
    email: str
    password: str
    name: str
    role: str = "agent"
    tenant_id: Optional[str] = None
    avatar: Optional[str] = None


class UserUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    tenant_id: Optional[str] = None
    avatar: Optional[str] = None


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
