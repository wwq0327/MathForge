"""试卷 Pydantic 模型。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import PAPER_ID_PATTERN, PaperStatus, Stage


class PaperBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        use_enum_values=False,
    )

    title: str = Field(..., min_length=1, max_length=200)
    year: Optional[int] = Field(default=None, ge=1900, le=2100)
    source: Optional[str] = None
    source_abbr: Optional[str] = Field(default=None, max_length=32)
    stage: Optional[Stage] = None
    source_path: Optional[str] = None
    status: PaperStatus = PaperStatus.PENDING
    total_questions: int = Field(default=0, ge=0, le=500)
    total_score: float = Field(default=0.0, ge=0, le=1000)


class PaperCreate(PaperBase):
    id: str = Field(..., pattern=PAPER_ID_PATTERN, description="{年份}-{来源缩写}")


class PaperOut(PaperBase):
    id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
