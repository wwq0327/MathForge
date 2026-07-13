"""question_service 单元测试。"""
from __future__ import annotations

import pytest

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


@pytest.fixture
def seeded_db(tmp_path, monkeypatch):
    """灌入覆盖 7 维度的示例题到临时 db。"""
    import json

    from app.config import Settings
    from app.database import init_schema
    from app.services import question_service

    db = tmp_path / "vault.db"
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    seed_kt = [
        {"id": "kt-num", "name": "数与代数"},
        {"id": "kt-fig", "name": "图形与几何"},
    ]
    (prompts / "knowledge_tree_seed.json").write_text(
        json.dumps(seed_kt, ensure_ascii=False), encoding="utf-8"
    )

    test_settings = Settings(database_path=str(db), prompts_dir=str(prompts))
    monkeypatch.setattr("app.database.settings", test_settings)
    monkeypatch.setattr(question_service, "settings", test_settings)

    init_schema(db_path=db)
    with question_service.get_connection() as conn:
        conn.executemany(
            "INSERT INTO knowledge_tree (id, name) VALUES (?, ?)",
            [("kt-num", "数与代数"), ("kt-fig", "图形与几何")],
        )
        conn.executemany(
            """
            INSERT INTO questions (
                id, stage, grade, question_type, section, source, source_abbr,
                year, review_status, topic_l1, difficulty, stem, answer, solution,
                citation_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("M2024-NCZK-1", "初中", "七年级", "选择题", "数与代数", "测试A", "NCZK",
                 2024, "已入库", "kt-num", "易", "题干1", "答案1", "解析1", 5),
                ("M2024-NCZK-2", "初中", "七年级", "填空题", "数与代数", "测试A", "NCZK",
                 2024, "草稿", "kt-num", "中", "题干2", "答案2", "解析2", 0),
                ("M2024-BJMS-1", "初中", "八年级", "计算题", "图形与几何", "测试B", "BJMS",
                 2024, "已入库", "kt-fig", "难", "题干3", "答案3", "解析3", 12),
                ("M2025-NCZK-3", "初中", "九年级", "证明题", "函数", "测试C", "NCZK",
                 2025, "待审核", "kt-num", "中", "题干4", "答案4", "解析4", 3),
            ],
        )
    return test_settings


def test_list_questions_empty_db(tmp_path, monkeypatch):
    from app.config import Settings
    from app.database import init_schema
    from app.services import question_service

    db = tmp_path / "vault.db"
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    test_settings = Settings(database_path=str(db), prompts_dir=str(prompts))
    monkeypatch.setattr("app.database.settings", test_settings)
    monkeypatch.setattr(question_service, "settings", test_settings)
    init_schema(db_path=db)

    rows, total = question_service.list_questions(question_service.QuestionListQuery())
    assert rows == []
    assert total == 0


def test_list_questions_returns_all_when_no_filter(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery()
    rows, total = question_service.list_questions(q)
    assert total == 4
    assert len(rows) == 4


def test_list_questions_filter_by_grade(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(grades=["七年级"])
    rows, total = question_service.list_questions(q)
    assert total == 2
    assert {r.id for r in rows} == {"M2024-NCZK-1", "M2024-NCZK-2"}


def test_list_questions_multi_value_in(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(grades=["七年级", "八年级"])
    rows, total = question_service.list_questions(q)
    assert total == 3
    assert {r.id for r in rows} == {"M2024-NCZK-1", "M2024-NCZK-2", "M2024-BJMS-1"}


def test_list_questions_filter_by_year(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(years=[2024])
    rows, total = question_service.list_questions(q)
    assert total == 3


def test_list_questions_filter_by_difficulty(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(difficulties=["易"])
    rows, total = question_service.list_questions(q)
    assert total == 1
    assert rows[0].id == "M2024-NCZK-1"


def test_list_questions_filter_by_source_abbr(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(source_abbrs=["BJMS"])
    rows, total = question_service.list_questions(q)
    assert total == 1
    assert rows[0].id == "M2024-BJMS-1"


def test_list_questions_filter_by_topic_l1(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(topic_l1s=["kt-fig"])
    rows, total = question_service.list_questions(q)
    assert total == 1
    assert rows[0].id == "M2024-BJMS-1"


def test_list_questions_filter_by_review_status(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(review_statuses=["已入库"])
    rows, total = question_service.list_questions(q)
    assert total == 2


def test_list_questions_combined_filters(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(
        grades=["七年级"], review_statuses=["已入库"]
    )
    rows, total = question_service.list_questions(q)
    assert total == 1
    assert rows[0].id == "M2024-NCZK-1"


def test_list_questions_sort_year_desc(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(sort="year_desc")
    rows, _ = question_service.list_questions(q)
    years = [r.year for r in rows]
    assert years == sorted(years, reverse=True)


def test_list_questions_sort_id_asc(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(sort="id_asc")
    rows, _ = question_service.list_questions(q)
    ids = [r.id for r in rows]
    assert ids == sorted(ids)


def test_list_questions_sort_citation_desc(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(sort="citation_desc")
    rows, _ = question_service.list_questions(q)
    citations = [r.citation_count for r in rows]
    assert citations == sorted(citations, reverse=True)


def test_list_questions_pagination(seeded_db):
    from app.services import question_service

    q1 = question_service.QuestionListQuery(page=1, page_size=2)
    rows1, total1 = question_service.list_questions(q1)
    assert total1 == 4
    assert len(rows1) == 2

    q2 = question_service.QuestionListQuery(page=2, page_size=2)
    rows2, _ = question_service.list_questions(q2)
    assert len(rows2) == 2

    ids1 = {r.id for r in rows1}
    ids2 = {r.id for r in rows2}
    assert ids1.isdisjoint(ids2)


def test_list_questions_pagination_out_of_range(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(page=99, page_size=2)
    rows, total = question_service.list_questions(q)
    assert rows == []
    assert total == 4


def test_list_questions_safety_sql_injection_attempt(seeded_db):
    """SQL 注入：非法 topic_l1 已在 parse_list_query 丢弃；list 不应崩。"""
    from app.services import question_service

    q = question_service.QuestionListQuery(topic_l1s=["'; DROP TABLE questions; --"])
    rows, total = question_service.list_questions(q)
    assert total == 0
    with question_service.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 4


def test_get_question_detail_found(seeded_db):
    from app.services import question_service

    q = question_service.get_question_detail("M2024-NCZK-1")
    assert q.id == "M2024-NCZK-1"
    assert q.stem == "题干1"
    assert q.grade == "七年级"


def test_get_question_detail_not_found_raises(seeded_db):
    from app.services import question_service

    with pytest.raises(question_service.QuestionNotFoundError):
        question_service.get_question_detail("M2099-NOPE-1")


def test_get_question_detail_invalid_id_raises(seeded_db):
    from app.services import question_service

    with pytest.raises(question_service.QuestionNotFoundError):
        question_service.get_question_detail("not-a-valid-id")


def test_list_topic_l1_choices(seeded_db):
    from app.services import question_service

    choices = question_service.list_topic_l1_choices()
    assert ("kt-num", "数与代数") in choices
    assert ("kt-fig", "图形与几何") in choices
    assert len(choices) == 2


def test_list_topic_l1_choices_empty_db(tmp_path, monkeypatch):
    from app.config import Settings
    from app.database import init_schema
    from app.services import question_service

    db = tmp_path / "vault.db"
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    test_settings = Settings(database_path=str(db), prompts_dir=str(prompts))
    monkeypatch.setattr("app.database.settings", test_settings)
    monkeypatch.setattr(question_service, "settings", test_settings)
    init_schema(db_path=db)
    assert question_service.list_topic_l1_choices() == []
