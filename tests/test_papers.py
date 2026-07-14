"""组卷模块测试。"""
from __future__ import annotations

import uuid

import pytest

from app.services.paper_service import (
    add_to_cart,
    cart_count,
    clear_cart,
    generate_paper,
    get_paper,
    get_paper_questions,
    latex_escape,
    list_cart,
    remove_from_cart,
    update_cart_order,
)


@pytest.fixture
def session_id() -> str:
    """返回一个随机 session_id。"""
    return str(uuid.uuid4())


def _seed_questions(conn) -> None:
    """灌入 3 道测试题。"""
    conn.execute("INSERT INTO knowledge_tree (id, name) VALUES ('kt-num', '数与代数')")
    conn.executemany(
        """INSERT INTO questions (
            id, stage, grade, question_type, section, source, source_abbr,
            year, review_status, topic_l1, difficulty, stem, answer, solution,
            citation_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            ("M2024-NCZK-1", "初中", "七年级", "选择题", "数与代数", "测试A", "NCZK",
             2024, "已入库", "kt-num", "易", "题干1", "答案1", "解析1", 5),
            ("M2024-NCZK-2", "初中", "七年级", "填空题", "数与代数", "测试A", "NCZK",
             2024, "草稿", "kt-num", "中", "题干2", "答案2", "解析2", 0),
            ("M2024-BJMS-1", "初中", "八年级", "计算题", "图形与几何", "测试B", "BJMS",
             2024, "已入库", "kt-num", "难", "题干3", "答案3", "解析3", 12),
        ],
    )


@pytest.fixture
def demo_question_ids(tmp_path, monkeypatch) -> list[str]:
    """返回隔离临时数据库中的题目 ID。"""
    from app.config import Settings
    from app.database import get_connection, init_schema

    db = tmp_path / "vault.db"
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    test_settings = Settings(database_path=str(db), prompts_dir=str(prompts))
    monkeypatch.setattr("app.database.settings", test_settings)

    init_schema(db_path=db)
    with get_connection() as conn:
        _seed_questions(conn)
        rows = conn.execute("SELECT id FROM questions LIMIT 3").fetchall()
    return [r["id"] for r in rows]


class TestCartService:
    def test_add_to_cart(self, session_id, demo_question_ids):
        qid = demo_question_ids[0]
        count = add_to_cart(session_id, qid)
        assert count == 1
        items = list_cart(session_id)
        assert len(items) == 1
        assert items[0]["question_id"] == qid

    def test_add_duplicate_is_idempotent(self, session_id, demo_question_ids):
        qid = demo_question_ids[0]
        add_to_cart(session_id, qid)
        add_to_cart(session_id, qid)
        assert cart_count(session_id) == 1

    def test_add_multiple_questions(self, session_id, demo_question_ids):
        for qid in demo_question_ids:
            add_to_cart(session_id, qid)
        assert cart_count(session_id) == len(demo_question_ids)
        items = list_cart(session_id)
        assert len(items) == len(demo_question_ids)

    def test_add_nonexistent_returns_none(self, session_id):
        result = add_to_cart(session_id, "M9999-NOPE-999")
        assert result is None
        assert cart_count(session_id) == 0

    def test_remove_from_cart(self, session_id, demo_question_ids):
        qid = demo_question_ids[0]
        add_to_cart(session_id, qid)
        count = remove_from_cart(session_id, qid)
        assert count == 0
        assert cart_count(session_id) == 0

    def test_remove_nonexistent(self, session_id):
        count = remove_from_cart(session_id, "M0000-NONE-999")
        assert count == 0

    def test_clear_cart(self, session_id, demo_question_ids):
        for qid in demo_question_ids:
            add_to_cart(session_id, qid)
        clear_cart(session_id)
        assert cart_count(session_id) == 0

    def test_update_cart_order(self, session_id, demo_question_ids):
        for qid in demo_question_ids:
            add_to_cart(session_id, qid)
        reversed_ids = list(reversed(demo_question_ids))
        update_cart_order(session_id, reversed_ids)
        items = list_cart(session_id)
        assert [i["question_id"] for i in items] == reversed_ids

    def test_cart_empty_list(self, session_id):
        assert list_cart(session_id) == []

    def test_cart_count_zero(self, session_id):
        assert cart_count(session_id) == 0


class TestGeneratePaper:
    def test_generate_paper(self, session_id, demo_question_ids):
        for qid in demo_question_ids:
            add_to_cart(session_id, qid)
        pid = generate_paper(session_id, "测试试卷", answer_mode=0, format="html")
        assert pid > 0
        paper = get_paper(pid)
        assert paper is not None
        assert paper["title"] == "测试试卷"
        assert paper["answer_mode"] == 0
        assert paper["format"] == "html"

    def test_generate_empty_cart_raises(self, session_id):
        with pytest.raises(ValueError, match="空"):
            generate_paper(session_id, "空试卷")

    def test_generate_increments_citation_count(self, session_id, demo_question_ids):
        from app.database import get_connection
        qid = demo_question_ids[0]
        with get_connection() as conn:
            before = conn.execute("SELECT citation_count FROM questions WHERE id=?", (qid,)).fetchone()[0]
        add_to_cart(session_id, qid)
        generate_paper(session_id, "引用计数测试")
        with get_connection() as conn:
            after = conn.execute("SELECT citation_count FROM questions WHERE id=?", (qid,)).fetchone()[0]
        assert after == before + 1

    def test_generate_clears_cart(self, session_id, demo_question_ids):
        for qid in demo_question_ids:
            add_to_cart(session_id, qid)
        generate_paper(session_id, "清空测试")
        assert cart_count(session_id) == 0

    def test_get_paper_nonexistent(self):
        assert get_paper(99999) is None

    def test_get_paper_questions(self, session_id, demo_question_ids):
        for qid in demo_question_ids:
            add_to_cart(session_id, qid)
        pid = generate_paper(session_id, "题目列表测试")
        questions = get_paper_questions(pid)
        assert len(questions) == len(demo_question_ids)

    def test_get_paper_questions_nonexistent(self):
        assert get_paper_questions(99999) == []


class TestLatexEscape:
    def test_escape_percent(self):
        assert latex_escape("100%") == r"100\%"

    def test_escape_hash(self):
        assert latex_escape("#1") == r"\#1"

    def test_escape_underscore(self):
        assert latex_escape("a_b") == r"a\_b"

    def test_escape_dollar(self):
        assert latex_escape("$5") == r"\$5"

    def test_escape_braces(self):
        assert latex_escape("{test}") == r"\{test\}"

    def test_escape_backslash(self):
        assert latex_escape("a\\b") == r"a\textbackslash{}b"

    def test_escape_ampersand(self):
        assert latex_escape("a&b") == r"a\&b"

    def test_escape_none(self):
        assert latex_escape("正常文本") == "正常文本"

    def test_escape_empty(self):
        assert latex_escape("") == ""

    def test_escape_tilde(self):
        assert latex_escape("~") == r"\textasciitilde{}"

    def test_escape_title_with_special_chars(self):
        """C3 回归：含 & % $ # 的标题需要转义。"""
        result = latex_escape("My & Title 100% $test")
        assert r"\&" in result
        assert r"\%" in result
        assert r"\$" in result
        assert "100% $test" not in result
