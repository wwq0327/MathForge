"""大题 Pydantic 模型。"""
from __future__ import annotations

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
        use_enum_values=True,
    )

    title: str | None = Field(default=None, max_length=200)
    content: str | None = None
    source: str | None = None
    source_abbr: str | None = Field(default=None, max_length=32)
    year: int | None = Field(default=None, ge=1900, le=2100)
    stage: Stage | None = None
    grade: Grade | None = None
    section: Section | None = None
    topic_l1: str | None = None
    topic_l2: str | None = None
    images: str | None = None


class PassageCreate(PassageBase):
    id: str = Field(..., pattern=PASSAGE_ID_PATTERN, description="{年份}-{来源缩写}-{序号}")


class PassageOut(PassageBase):
    id: str
    created_at: str | None = None
    updated_at: str | None = None
