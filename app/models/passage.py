"""大题 Pydantic 模型。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    PASSAGE_ID_PATTERN,
    Grade,
    Section,
    Stage,
)


class PassageBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        use_enum_values=False,
    )

    title: Optional[str] = Field(default=None, max_length=200)
    content: Optional[str] = None
    source: Optional[str] = None
    source_abbr: Optional[str] = Field(default=None, max_length=32)
    year: Optional[int] = Field(default=None, ge=1900, le=2100)
    stage: Optional[Stage] = None
    grade: Optional[Grade] = None
    section: Optional[Section] = None
    topic_l1: Optional[str] = None
    topic_l2: Optional[str] = None
    images: Optional[str] = None


class PassageCreate(PassageBase):
    id: str = Field(..., pattern=PASSAGE_ID_PATTERN, description="{年份}-{来源缩写}-{序号}")


class PassageOut(PassageBase):
    id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
