"""Modelos relacionados a conexões e webhooks."""
from pydantic import BaseModel
from typing import List, Optional


# ==================== CONNECTIONS ====================

class ConnectionCreate(BaseModel):
    tenant_id: str
    provider: str
    instance_name: str
    phone_number: Optional[str] = ""
    config: Optional[dict] = None


class ConnectionStatusUpdate(BaseModel):
    status: str


# ==================== WEBHOOKS ====================

class WebhookCreate(BaseModel):
    name: str
    url: str
    secret: Optional[str] = None
    events: List[str] = []
    headers: Optional[dict] = None
    is_active: bool = True
