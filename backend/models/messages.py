"""Modelos relacionados a mensagens e templates."""
from pydantic import BaseModel
from typing import List, Optional


# ==================== MESSAGES ====================

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


# ==================== TEMPLATES ====================

class MessageTemplateCreate(BaseModel):
    name: str
    category: str = "general"
    content: str
    variables: Optional[List[dict]] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    is_active: bool = True


# ==================== QUICK REPLIES & LABELS ====================

class QuickReplyCreate(BaseModel):
    title: str
    content: str
    category: str = "custom"


class LabelCreate(BaseModel):
    name: str
    color: str
