"""Modelos Pydantic do CRM.

Este módulo re-exporta todos os modelos para facilitar importações.
"""
from .auth import (
    LoginRequest,
    LoginResponse,
    MaintenanceAttachment,
    MaintenanceSettings,
    MaintenanceSettingsUpdate,
)
from .tenants import (
    TenantCreate,
    TenantUpdate,
    TenantRegister,
    PlanCreate,
    PlanUpdate,
    UserCreate,
    UserUpdate,
    UserProfileUpdate,
)
from .conversations import (
    ConversationStatusUpdate,
    InitiateConversation,
    ConversationTransferCreate,
    AssignAgent,
    ContactCreate,
    ContactUpdate,
    ContactUpsertByPhone,
)
from .messages import (
    MessageCreate,
    SendWhatsAppMessage,
    MessageTemplateCreate,
    QuickReplyCreate,
    LabelCreate,
)
from .campaigns import (
    AutoMessageCreate,
    BulkCampaignCreate,
    BulkCampaignUpdate,
    BulkCampaignRecipientsSet,
    BulkCampaignSchedule,
)
from .connections import (
    ConnectionCreate,
    ConnectionStatusUpdate,
    WebhookCreate,
)
from .flows import (
    FlowCreate,
    FlowUpdate,
    FlowDuplicate,
    KBCategoryCreate,
    KBArticleCreate,
    KBFaqCreate,
)

__all__ = [
    # Auth
    "LoginRequest",
    "LoginResponse",
    "MaintenanceAttachment",
    "MaintenanceSettings",
    "MaintenanceSettingsUpdate",
    # Tenants
    "TenantCreate",
    "TenantUpdate",
    "TenantRegister",
    "PlanCreate",
    "PlanUpdate",
    "UserCreate",
    "UserUpdate",
    "UserProfileUpdate",
    # Conversations
    "ConversationStatusUpdate",
    "InitiateConversation",
    "ConversationTransferCreate",
    "AssignAgent",
    "ContactCreate",
    "ContactUpdate",
    "ContactUpsertByPhone",
    # Messages
    "MessageCreate",
    "SendWhatsAppMessage",
    "MessageTemplateCreate",
    "QuickReplyCreate",
    "LabelCreate",
    # Campaigns
    "AutoMessageCreate",
    "BulkCampaignCreate",
    "BulkCampaignUpdate",
    "BulkCampaignRecipientsSet",
    "BulkCampaignSchedule",
    # Connections
    "ConnectionCreate",
    "ConnectionStatusUpdate",
    "WebhookCreate",
    # Flows
    "FlowCreate",
    "FlowUpdate",
    "FlowDuplicate",
    "KBCategoryCreate",
    "KBArticleCreate",
    "KBFaqCreate",
]
