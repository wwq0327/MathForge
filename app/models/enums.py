"""MathForge 业务枚举与合法值域。

参考 PLAN.md 第 152-163 行 + 第 195 行 + 《义务教育数学课程标准（2022年版）》。
所有枚举继承 ``str`` 与 ``Enum``，序列化与数据库 TEXT 字段直接兼容。
"""
from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """字符串枚举基类。"""


class Stage(StrEnum):
    """学段。P0 仅支持初中。"""
    JUNIOR = "初中"
    SENIOR = "高中"


class Grade(StrEnum):
    """年级（初中）。"""
    SEVEN = "七年级"
    EIGHT = "八年级"
    NINE = "九年级"


class QuestionType(StrEnum):
    """题型。"""
    CHOICE = "选择题"
    FILL = "填空题"
    CALCULATION = "计算题"
    PROOF = "证明题"
    DRAWING = "作图题"
    APPLICATION = "应用题"
    INQUIRY = "探究题"
    COMPREHENSIVE = "综合题"


class Section(StrEnum):
    """六大板块。"""
    NUMBER = "数与代数"
    GEOMETRY = "图形与几何"
    FUNCTION = "函数"
    STATS = "统计与概率"
    COMPREHENSIVE = "综合与实践"
    PROJECT = "课题学习"


class Difficulty(StrEnum):
    """难度。"""
    EASY = "易"
    MEDIUM = "中"
    HARD = "难"


class ReviewStatus(StrEnum):
    """题目审核状态。"""
    DRAFT = "草稿"
    PENDING = "待审核"
    APPROVED = "已入库"


class PaperStatus(StrEnum):
    """试卷录入状态。"""
    PENDING = "待录入"
    IN_PROGRESS = "录入中"
    DONE = "已录入"


class BloomLevel(StrEnum):
    """布鲁姆认知层级。"""
    REMEMBER = "记忆"
    UNDERSTAND = "理解"
    APPLY = "应用"
    ANALYZE = "分析"
    EVALUATE = "评价"
    CREATE = "创造"


# ── ID 编码规则（PLAN.md 第 148-190 行）──
# 题目：M{4位年份}-{大写来源缩写}-{序号}
# 大题：{4位年份}-{大写来源缩写}-{序号}
# 试卷：{4位年份}-{大写来源缩写}
QUESTION_ID_PATTERN = r"^M\d{4}-[A-Z]+-\d+$"
PASSAGE_ID_PATTERN = r"^\d{4}-[A-Z]+-\d+$"
PAPER_ID_PATTERN = r"^\d{4}-[A-Z]+$"
