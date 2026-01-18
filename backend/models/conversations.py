"""Modelos relacionados a conversas e contatos."""
from pydantic import BaseModel
from typing import List, Optional


# ==================== CONVERSATIONS ====================

class ConversationStatusUpdate(BaseModel):
    status: str


class InitiateConversation(BaseModel):
    phone: str
    contact_id: Optional[str] = None


class ConversationTransferCreate(BaseModel):
    to_agent_id: str
    reason: Optional[str] = None


class AssignAgent(BaseModel):
    agent_id: str


# ==================== CONTACTS ====================

class ContactCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    tags: Optional[List[str]] = None
    custom_fields: Optional[dict] = None
    source: Optional[str] = None
    status: Optional[str] = None


class ContactUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    tags: Optional[List[str]] = None
    custom_fields: Optional[dict] = None
    social_links: Optional[dict] = None
    notes_html: Optional[str] = None
    status: Optional[str] = None


class ContactUpsertByPhone(BaseModel):
    tenant_id: str
    phone: str
    full_name: Optional[str] = None
    avatar: Optional[str] = None
