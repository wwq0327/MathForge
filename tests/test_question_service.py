"""question_service 单元测试。"""
from __future__ import annotations

from app.services.question_service import (
    ALLOWED_FILTER_COLUMNS,
    ALLOWED_SORTS,
    QuestionListQuery,
    parse_list_query,
)


def test_parse_empty_returns_defaults():
    q = parse_list_query({})
    assert q == QuestionListQuery()


def test_parse_single_value():
    q = parse_list_query({"grade": ["七年级"]})
    assert q.grades == ["七年级"]
    assert q.question_types == []


def test_parse_repeat_key_multi_value():
    q = parse_list_query({"grade": ["七年级", "八年级"]})
    assert q.grades == ["七年级", "八年级"]


def test_parse_illegal_grade_dropped():
    q = parse_list_query({"grade": ["六年级", "七年级"]})
    assert q.grades == ["七年级"]


def test_parse_year_validates_range():
    q = parse_list_query({"year": ["1850", "2024", "2200", "abc"]})
    assert q.years == [2024]


def test_parse_source_abbr_validates_pattern():
    q = parse_list_query({"source_abbr": ["NCZK", "abc", "NCZK'; DROP--"]})
    assert q.source_abbrs == ["NCZK"]


def test_parse_illegal_sort_falls_back():
    q = parse_list_query({"sort": ["foo"]})
    assert q.sort == "year_desc"


def test_parse_legal_sort_kept():
    q = parse_list_query({"sort": ["citation_desc"]})
    assert q.sort == "citation_desc"


def test_parse_page_falls_back_on_garbage():
    q = parse_list_query({"page": ["-1", "0", "abc", "3"]})
    assert q.page == 3


def test_parse_question_type_legal_values():
    q = parse_list_query({"question_type": ["选择题", "未知题", "填空题"]})
    assert q.question_types == ["选择题", "填空题"]


def test_parse_difficulty_legal_values():
    q = parse_list_query({"difficulty": ["易", "极难", "中"]})
    assert q.difficulties == ["易", "中"]


def test_parse_section_legal_values():
    q = parse_list_query({"section": ["数与代数", "虚构板块", "函数"]})
    assert q.sections == ["数与代数", "函数"]


def test_parse_review_status_legal_values():
    q = parse_list_query({"review_status": ["草稿", "垃圾状态", "已入库"]})
    assert q.review_statuses == ["草稿", "已入库"]


def test_whitelist_defined():
    assert "grade" in ALLOWED_FILTER_COLUMNS
    assert "year" in ALLOWED_FILTER_COLUMNS
    assert ALLOWED_SORTS["year_desc"] == "year DESC, id ASC"
    assert ALLOWED_SORTS["citation_desc"] == "citation_count DESC, id ASC"
