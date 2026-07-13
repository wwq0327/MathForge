"""试卷 Pydantic 模型。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class PaperBase(BaseModel):
    title: str
    year: Optional[int] = None
    source: Optional[str] = None
    source_abbr: Optional[str] = None
    stage: Optional[str] = None
    source_path: Optional[str] = None
    status: str = "待录入"
    total_questions: int = 0
    total_score: float = 0.0


class PaperCreate(PaperBase):
    id: str = Field(..., description="{年份}-{来源缩写}")


class PaperOut(PaperBase):
    id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
