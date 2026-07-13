"""题目 Pydantic 模型。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    QUESTION_ID_PATTERN,
    BloomLevel,
    Difficulty,
    Grade,
    QuestionType,
    ReviewStatus,
    Section,
    Stage,
)


class QuestionBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        use_enum_values=False,
    )

    stage: Optional[Stage] = None
    grade: Optional[Grade] = None
    question_type: Optional[QuestionType] = None
    section: Optional[Section] = None
    source: Optional[str] = None
    source_abbr: Optional[str] = Field(default=None, max_length=32)
    year: Optional[int] = Field(default=None, ge=1900, le=2100)
    is_exam_question: bool = False
    review_status: ReviewStatus = ReviewStatus.DRAFT
    topic_l1: Optional[str] = None
    topic_l2: Optional[str] = None
    angle: Optional[str] = None
    core_literacy: Optional[str] = None
    difficulty: Optional[Difficulty] = None
    bloom_level: Optional[BloomLevel] = None
    stem: Optional[str] = None
    answer: Optional[str] = None
    solution: Optional[str] = None
    images: Optional[str] = None
    passage_id: Optional[str] = None
    paper_id: Optional[str] = None
    question_number: Optional[int] = Field(default=None, ge=1, le=200)
    score: Optional[float] = Field(default=None, ge=0, le=100)


class QuestionCreate(QuestionBase):
    id: str = Field(..., pattern=QUESTION_ID_PATTERN, description="M{年份}-{来源缩写}-{序号}")


class QuestionOut(QuestionBase):
    id: str
    citation_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
