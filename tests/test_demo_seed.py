"""示例题种子测试。"""
from __future__ import annotations

import pytest


@pytest.fixture
def empty_db(tmp_path, monkeypatch):
    from app.config import Settings
    from app.database import init_schema
    from app.services import demo_seed

    db = tmp_path / "vault.db"
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    test_settings = Settings(database_path=str(db), prompts_dir=str(prompts))
    monkeypatch.setattr("app.database.settings", test_settings)
    monkeypatch.setattr(demo_seed, "settings", test_settings)
    init_schema(db_path=db)

    from app.services import question_service
    with question_service.get_connection() as conn:
        conn.executemany(
            "INSERT INTO knowledge_tree (id, name) VALUES (?, ?)",
            [
                ("kt-num", "数与代数"),
                ("kt-fig", "图形与几何"),
                ("kt-func", "函数"),
                ("kt-stat", "统计与概率"),
            ],
        )
    return test_settings


def test_seed_demo_questions_returns_count(empty_db):
    from app.services import demo_seed

    n = demo_seed.seed_demo_questions()
    assert n > 0
    assert n >= 20


def test_seed_demo_questions_idempotent(empty_db):
    from app.services import demo_seed, question_service

    n1 = demo_seed.seed_demo_questions()
    n2 = demo_seed.seed_demo_questions()
    assert n1 > 0
    assert n2 == 0
    with question_service.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == n1


def test_seed_demo_questions_covers_dimensions(empty_db):
    from app.services import demo_seed, question_service

    demo_seed.seed_demo_questions()
    with question_service.get_connection() as conn:
        grades = {r[0] for r in conn.execute(
            "SELECT DISTINCT grade FROM questions WHERE grade IS NOT NULL"
        ).fetchall()}
        years = {r[0] for r in conn.execute(
            "SELECT DISTINCT year FROM questions WHERE year IS NOT NULL"
        ).fetchall()}
    assert "七年级" in grades
    assert "八年级" in grades
    assert "九年级" in grades
    assert len(years) >= 3
