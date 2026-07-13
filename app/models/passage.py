"""大题 Pydantic 模型。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class PassageBase(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    source: Optional[str] = None
    source_abbr: Optional[str] = None
    year: Optional[int] = None
    stage: Optional[str] = None
    grade: Optional[str] = None
    section: Optional[str] = None
    topic_l1: Optional[str] = None
    topic_l2: Optional[str] = None
    images: Optional[str] = None


class PassageCreate(PassageBase):
    id: str = Field(..., description="{年份}-{来源缩写}-{序号}")


class PassageOut(PassageBase):
    id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
