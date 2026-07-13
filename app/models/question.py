"""题目 Pydantic 模型。

P0 范围：定义字段与类型约束，供后续录入/编辑/导出校验使用。
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class QuestionBase(BaseModel):
    stage: Optional[str] = None
    grade: Optional[str] = None
    question_type: Optional[str] = None
    section: Optional[str] = None
    source: Optional[str] = None
    source_abbr: Optional[str] = None
    year: Optional[int] = None
    is_exam_question: bool = False
    review_status: str = Field(default="草稿")
    topic_l1: Optional[str] = None
    topic_l2: Optional[str] = None
    angle: Optional[str] = None
    core_literacy: Optional[str] = None
    difficulty: Optional[str] = None
    bloom_level: Optional[str] = None
    stem: Optional[str] = None
    answer: Optional[str] = None
    solution: Optional[str] = None
    images: Optional[str] = None
    passage_id: Optional[str] = None
    paper_id: Optional[str] = None
    question_number: Optional[int] = None
    score: Optional[float] = None


class QuestionCreate(QuestionBase):
    id: str = Field(..., description="M{年份}-{来源缩写}-{序号}")


class QuestionOut(QuestionBase):
    id: str
    citation_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
