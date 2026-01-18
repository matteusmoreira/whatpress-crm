"""Modelos relacionados a flows e base de conhecimento."""
from pydantic import BaseModel
from typing import List, Optional


# ==================== FLOWS ====================

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


# ==================== KNOWLEDGE BASE ====================

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
