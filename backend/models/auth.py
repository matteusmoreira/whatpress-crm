"""Modelos relacionados a autenticação e manutenção."""
from pydantic import BaseModel
from typing import List, Optional


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
