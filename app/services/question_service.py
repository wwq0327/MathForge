"""题目服务：列表查询 / 详情查询 / SQL 白名单。

设计要点：
- parse_list_query 接受路由层组装的 dict[str, list[str]]，与 Starlette 解耦
- 所有枚举值走白名单，非法值丢弃；非字典 / 类型错误的入参永不入 SQL
- 列名 / 排序从模块级常量取，绝不走 f-string 拼列
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.database import get_connection
from app.models.enums import (
    QUESTION_ID_PATTERN,
    Difficulty,
    Grade,
    QuestionType,
    ReviewStatus,
    Section,
)
from app.models.question import QuestionOut


class QuestionNotFoundError(Exception):
    """题目 ID 不存在或 ID 不合法。"""


@dataclass(frozen=True)
class QuestionListQuery:
    grades: list[str] = field(default_factory=list)
    question_types: list[str] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)
    difficulties: list[str] = field(default_factory=list)
    years: list[int] = field(default_factory=list)
    source_abbrs: list[str] = field(default_factory=list)
    review_statuses: list[str] = field(default_factory=list)
    topic_l1s: list[str] = field(default_factory=list)
    sort: str = "year_desc"
    page: int = 1
    page_size: int = 20


# SQL 列白名单：URL 参数 -> (列名, 类型标记)。
# 列名由白名单常量提供，**绝不**走 f-string 拼列。
ALLOWED_FILTER_COLUMNS: dict[str, tuple[str, str]] = {
    "grade": ("grade", "text"),
    "question_type": ("question_type", "text"),
    "section": ("section", "text"),
    "difficulty": ("difficulty", "text"),
    "year": ("year", "int"),
    "source_abbr": ("source_abbr", "text"),
    "review_status": ("review_status", "text"),
    "topic_l1": ("topic_l1", "text"),
}

ALLOWED_SORTS: dict[str, str] = {
    "year_desc": "year DESC, id ASC",
    "id_asc": "id ASC",
    "citation_desc": "citation_count DESC, id ASC",
}

_TEXT_ENUM_SETS: dict[str, frozenset[str]] = {
    "grade": frozenset(e.value for e in Grade),
    "question_type": frozenset(e.value for e in QuestionType),
    "section": frozenset(e.value for e in Section),
    "difficulty": frozenset(e.value for e in Difficulty),
    "review_status": frozenset(e.value for e in ReviewStatus),
}

_SOURCE_ABBR_RE = re.compile(r"^[A-Z]+$")
_YEAR_MIN, _YEAR_MAX = 1900, 2100


def _clean_text(values: list[str], enum_key: str) -> list[str]:
    allowed = _TEXT_ENUM_SETS[enum_key]
    return [v for v in values if isinstance(v, str) and v in allowed]


def _clean_years(values: list[str]) -> list[int]:
    out: list[int] = []
    for v in values:
        if not isinstance(v, str):
            continue
        try:
            n = int(v)
        except ValueError:
            continue
        if _YEAR_MIN <= n <= _YEAR_MAX:
            out.append(n)
    return out


def _clean_source_abbrs(values: list[str]) -> list[str]:
    return [v for v in values if isinstance(v, str) and _SOURCE_ABBR_RE.match(v)]


def _clean_topic_l1s(
    values: list[str], allowed: set[str] | None
) -> list[str]:
    """topic_l1 清洗：非空字符串 + 可选白名单（None 表示跳过校验）。"""
    out: list[str] = []
    for v in values:
        if not isinstance(v, str) or not v:
            continue
        if allowed is not None and v not in allowed:
            continue
        out.append(v)
    return out


def _pick_positive_int(values: list[str], default: int) -> int:
    """从候选值中取第一个合法正整数；都非法则返回 default。"""
    for v in values:
        if not isinstance(v, str):
            continue
        try:
            n = int(v)
        except ValueError:
            continue
        if n >= 1:
            return n
    return default


def parse_list_query(
    params: Mapping[str, list[str]],
    allowed_topic_l1s: set[str] | None = None,
) -> QuestionListQuery:
    """解析并校验 query string，非法值丢弃，缺失项用默认。

    params 由路由层用 ``request.query_params.getlist(key)`` 显式组装为
    ``dict[str, list[str]]`` 后传入；service 不直接依赖 Starlette 类型。

    ``allowed_topic_l1s`` 来自 ``list_topic_l1_choices()``；不传或传 None
    时跳过 topic_l1 白名单校验（保留向后兼容，便于 service 层单测）。
    """
    sort = params.get("sort", ["year_desc"])[0] if params.get("sort") else "year_desc"
    if sort not in ALLOWED_SORTS:
        sort = "year_desc"

    page = _pick_positive_int(params.get("page", []), 1)

    return QuestionListQuery(
        grades=_clean_text(params.get("grade", []), "grade"),
        question_types=_clean_text(params.get("question_type", []), "question_type"),
        sections=_clean_text(params.get("section", []), "section"),
        difficulties=_clean_text(params.get("difficulty", []), "difficulty"),
        years=_clean_years(params.get("year", [])),
        source_abbrs=_clean_source_abbrs(params.get("source_abbr", [])),
        review_statuses=_clean_text(params.get("review_status", []), "review_status"),
        topic_l1s=_clean_topic_l1s(params.get("topic_l1", []), allowed_topic_l1s),
        sort=sort,
        page=page,
    )


def _build_where_clause(q: QuestionListQuery) -> tuple[str, list]:
    """构造 WHERE 子句（不包含 1=1）和对应参数。"""
    clauses: list[str] = []
    args: list = []

    text_filters: list[tuple[str, list[str]]] = [
        ("grade", q.grades),
        ("question_type", q.question_types),
        ("section", q.sections),
        ("difficulty", q.difficulties),
        ("source_abbr", q.source_abbrs),
        ("review_status", q.review_statuses),
        ("topic_l1", q.topic_l1s),
    ]
    for param_key, values in text_filters:
        if not values:
            continue
        col, _ = ALLOWED_FILTER_COLUMNS[param_key]
        placeholders = ",".join("?" * len(values))
        clauses.append(f"{col} IN ({placeholders})")
        args.extend(values)

    if q.years:
        placeholders = ",".join("?" * len(q.years))
        clauses.append(f"year IN ({placeholders})")
        args.extend(q.years)

    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where_sql, args


def list_questions(q: QuestionListQuery) -> tuple[list[QuestionOut], int]:
    """返回 (本页 rows, 总数)；page 越界返回 ([], total)。"""
    where_sql, where_args = _build_where_clause(q)
    order_sql = ALLOWED_SORTS.get(q.sort, ALLOWED_SORTS["year_desc"])
    offset = (q.page - 1) * q.page_size

    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM questions {where_sql}", where_args
        ).fetchone()[0]
        if total == 0 or offset >= total:
            return [], total
        rows = conn.execute(
            f"SELECT * FROM questions {where_sql} ORDER BY {order_sql} "
            f"LIMIT ? OFFSET ?",
            [*where_args, q.page_size, offset],
        ).fetchall()

    return [QuestionOut.model_validate(dict(r)) for r in rows], total


_QUESTION_ID_RE = re.compile(QUESTION_ID_PATTERN)


def get_question_detail(id: str) -> QuestionOut:
    """返回题目详情；不存在或 ID 不合法均抛 QuestionNotFoundError。"""
    if not isinstance(id, str) or not _QUESTION_ID_RE.match(id):
        raise QuestionNotFoundError(id)
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM questions WHERE id = ?", (id,)).fetchone()
    if row is None:
        raise QuestionNotFoundError(id)
    return QuestionOut.model_validate(dict(row))


def list_topic_l1_choices() -> list[tuple[str, str]]:
    """返回 (id, name) 列表，仅 parent_id IS NULL 的顶层节点。"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name FROM knowledge_tree "
            "WHERE parent_id IS NULL ORDER BY sort_order, name"
        ).fetchall()
    return [(r["id"], r["name"]) for r in rows]
