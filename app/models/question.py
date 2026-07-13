"""题目 Pydantic 模型。"""
from __future__ import annotations

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

    stage: Stage | None = None
    grade: Grade | None = None
    question_type: QuestionType | None = None
    section: Section | None = None
    source: str | None = None
    source_abbr: str | None = Field(default=None, max_length=32)
    year: int | None = Field(default=None, ge=1900, le=2100)
    is_exam_question: bool = False
    review_status: ReviewStatus = ReviewStatus.DRAFT
    topic_l1: str | None = None
    topic_l2: str | None = None
    angle: str | None = None
    core_literacy: str | None = None
    difficulty: Difficulty | None = None
    bloom_level: BloomLevel | None = None
    stem: str | None = None
    answer: str | None = None
    solution: str | None = None
    images: str | None = None
    passage_id: str | None = None
    paper_id: str | None = None
    question_number: int | None = Field(default=None, ge=1, le=200)
    score: float | None = Field(default=None, ge=0, le=100)


class QuestionCreate(QuestionBase):
    id: str = Field(..., pattern=QUESTION_ID_PATTERN, description="M{年份}-{来源缩写}-{序号}")


class QuestionOut(QuestionBase):
    id: str
    citation_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None
