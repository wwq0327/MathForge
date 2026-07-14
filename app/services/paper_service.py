"""组卷业务逻辑 — cart CRUD + generate + export 辅助。

依赖：
- CartSessionMiddleware 提供的 request.state.session_id
- app.database.get_connection() 数据库访问
"""

from __future__ import annotations

import json

from app.database import get_connection

_LATEX_SPECIAL = str.maketrans({
    "#": r"\#",
    "$": r"\$",
    "%": r"\%",
    "&": r"\&",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "\\": r"\textbackslash{}",
})


def latex_escape(text: str) -> str:
    """转义 LaTeX 特殊字符。"""
    return text.translate(_LATEX_SPECIAL) if text else text


def add_to_cart(session_id: str, question_id: str) -> int | None:
    """添加题目到 cart，返回当前 cart 总数。题目不存在返回 None。重复添加幂等。"""
    with get_connection() as conn:
        if conn.execute(
            "SELECT 1 FROM questions WHERE id=?", (question_id,)
        ).fetchone() is None:
            return None
        existing = conn.execute(
            "SELECT id FROM cart_items WHERE session_id=? AND question_id=?",
            (session_id, question_id),
        ).fetchone()
        if existing is None:
            max_order = conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) FROM cart_items WHERE session_id=?",
                (session_id,),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO cart_items (session_id, question_id, sort_order) VALUES (?, ?, ?)",
                (session_id, question_id, max_order + 1),
            )
        return conn.execute(
            "SELECT COUNT(*) FROM cart_items WHERE session_id=?", (session_id,)
        ).fetchone()[0]


def remove_from_cart(session_id: str, question_id: str) -> int:
    """从 cart 移除题目，返回当前 cart 总数。"""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM cart_items WHERE session_id=? AND question_id=?",
            (session_id, question_id),
        )
        return conn.execute(
            "SELECT COUNT(*) FROM cart_items WHERE session_id=?", (session_id,)
        ).fetchone()[0]


def list_cart(session_id: str) -> list[dict]:
    """返回 cart 内的题目（按 sort_order 排序），每项含 question_id。"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, question_id, sort_order FROM cart_items "
            "WHERE session_id=? ORDER BY sort_order, id",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_cart_order(session_id: str, question_ids: list[str]) -> None:
    """按传入顺序更新 sort_order。"""
    with get_connection() as conn:
        for idx, qid in enumerate(question_ids):
            conn.execute(
                "UPDATE cart_items SET sort_order=? WHERE session_id=? AND question_id=?",
                (idx, session_id, qid),
            )


def clear_cart(session_id: str) -> None:
    """清空当前 session 的 cart。"""
    with get_connection() as conn:
        conn.execute("DELETE FROM cart_items WHERE session_id=?", (session_id,))


def cart_count(session_id: str) -> int:
    """返回 cart 中的题目数量。"""
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM cart_items WHERE session_id=?", (session_id,)
        ).fetchone()[0]


def generate_paper(
    session_id: str,
    title: str,
    answer_mode: int = 0,
    format: str = "html",
) -> int:
    """从 cart 生成试卷，写入 generated_papers，递增 citation_count，清空 cart。"""
    items = list_cart(session_id)
    if not items:
        raise ValueError("cart 为空，无法生成试卷")
    question_ids = [item["question_id"] for item in items]
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO generated_papers (title, answer_mode, format, question_ids) "
            "VALUES (?, ?, ?, ?)",
            (title, answer_mode, format, json.dumps(question_ids)),
        )
        _pid = cur.lastrowid
        assert _pid is not None
        paper_id = _pid
        placeholders = ",".join("?" * len(question_ids))
        conn.execute(
            f"UPDATE questions SET citation_count = citation_count + 1 "
            f"WHERE id IN ({placeholders})",
            question_ids,
        )
        conn.execute(
            "DELETE FROM cart_items WHERE session_id=?", (session_id,)
        )
    return paper_id


def get_paper(paper_id: int) -> dict | None:
    """返回 generated_papers 记录，不存在返回 None。"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM generated_papers WHERE id=?", (paper_id,)
        ).fetchone()
    return dict(row) if row else None


def get_paper_questions(paper_id: int) -> list[dict]:
    """返回试卷关联的题目列表（按 question_ids 顺序）。"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM generated_papers WHERE id=?", (paper_id,)
        ).fetchone()
        if not row:
            return []
        paper = dict(row)
        qids = json.loads(paper["question_ids"])
        if not qids:
            return []
        placeholders = ",".join("?" * len(qids))
        rows = conn.execute(
            f"SELECT * FROM questions WHERE id IN ({placeholders})",
            qids,
        ).fetchall()
    qmap = {r["id"]: dict(r) for r in rows}
    return [qmap[qid] for qid in qids if qid in qmap]


def list_cart_with_questions(session_id: str) -> list[dict]:
    """返回 cart 内的题目详情（id, stem, question_type, difficulty），保持 cart 顺序。"""
    items = list_cart(session_id)
    if not items:
        return []
    qids = [item["question_id"] for item in items]
    placeholders = ",".join("?" * len(qids))
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT id, stem, question_type, difficulty FROM questions "
            f"WHERE id IN ({placeholders})",
            qids,
        ).fetchall()
    qmap = {r["id"]: dict(r) for r in rows}
    return [
        {**dict(item), **qmap[item["question_id"]]}
        for item in items
        if item["question_id"] in qmap
    ]
