"""
Routes package for Altar CRM backend.

This package contains FastAPI routers extracted from server.py for better organization.
Each router handles a specific domain of the API.
"""

from .auth_routes import router as auth_router
from .tenants_routes import router as tenants_router
from .users_routes import router as users_router
from .contacts_routes import router as contacts_router
from .campaigns_routes import router as campaigns_router
from .auto_messages_routes import router as auto_messages_router
from .quick_replies_routes import router as quick_replies_router
from .webhooks_routes import router as webhooks_router
from .templates_routes import router as templates_router
from .conversations_routes import router as conversations_router

__all__ = [
    "auth_router",
    "tenants_router",
    "users_router",
    "contacts_router",
    "campaigns_router",
    "auto_messages_router",
    "quick_replies_router",
    "webhooks_router",
    "templates_router",
    "conversations_router",
]
