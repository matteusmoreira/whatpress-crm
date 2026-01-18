"""Modelos relacionados a campanhas e auto-mensagens."""
from pydantic import BaseModel, Field
from typing import List, Optional


# ==================== AUTO MESSAGES ====================

class AutoMessageCreate(BaseModel):
    type: str  # 'welcome', 'away', 'keyword'
    name: str
    message: str
    trigger_keyword: Optional[str] = None
    is_active: bool = True
    schedule_start: Optional[str] = None
    schedule_end: Optional[str] = None
    schedule_days: Optional[List[int]] = None
    delay_seconds: int = 0


# ==================== BULK CAMPAIGNS ====================

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
