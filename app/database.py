"""MathForge 数据库层。

负责：
- SQLite 连接管理（行级连接 + context manager）
- 表结构定义（SCHEMA_SQL）
- 原子写入辅助（数据文件原子替换）

设计要点：
- 题目表 questions 的 id 形如 M{年份}-{来源缩写}-{序号}
- 关联表 papers / passages / knowledge_tree 通过外键关联
- 启用 WAL 模式以提升并发读性能
- 写入前自动备份（由调用方决定时机，db 模块只提供工具）
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .config import settings

ALLOWED_TABLES: frozenset[str] = frozenset(
    {
        "knowledge_tree",
        "papers",
        "passages",
        "questions",
        "generated_papers",
        "cart_items",
    }
)


SCHEMA_SQL = """
-- 知识点树（自引用，支持二级嵌套）
CREATE TABLE IF NOT EXISTS knowledge_tree (
    id            TEXT PRIMARY KEY,
    parent_id     TEXT REFERENCES knowledge_tree(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    code          TEXT,
    sort_order    INTEGER DEFAULT 0,
    description   TEXT,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_knowledge_parent ON knowledge_tree(parent_id);

-- 试卷
CREATE TABLE IF NOT EXISTS papers (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    year            INTEGER,
    source          TEXT,
    source_abbr     TEXT,
    stage           TEXT,
    source_path     TEXT,
    status          TEXT DEFAULT '待录入',
    total_questions INTEGER DEFAULT 0,
    total_score     REAL DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 大题（共享题干）
CREATE TABLE IF NOT EXISTS passages (
    id              TEXT PRIMARY KEY,
    title           TEXT,
    content         TEXT,
    source          TEXT,
    source_abbr     TEXT,
    year            INTEGER,
    stage           TEXT,
    grade           TEXT,
    section         TEXT,
    topic_l1        TEXT,
    topic_l2        TEXT,
    images          TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 题目
CREATE TABLE IF NOT EXISTS questions (
    id                TEXT PRIMARY KEY,
    stage             TEXT,
    grade             TEXT,
    question_type     TEXT,
    section           TEXT,
    source            TEXT,
    source_abbr       TEXT,
    year              INTEGER,
    is_exam_question  INTEGER DEFAULT 0,
    review_status     TEXT DEFAULT '草稿',
    topic_l1          TEXT,
    topic_l2          TEXT,
    angle             TEXT,
    core_literacy     TEXT,
    difficulty        TEXT,
    bloom_level       TEXT,
    stem              TEXT,
    answer            TEXT,
    solution          TEXT,
    images            TEXT,
    passage_id        TEXT REFERENCES passages(id) ON DELETE SET NULL,
    paper_id          TEXT REFERENCES papers(id) ON DELETE SET NULL,
    question_number   INTEGER,
    score             REAL,
    citation_count    INTEGER DEFAULT 0,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_q_paper ON questions(paper_id);
CREATE INDEX IF NOT EXISTS idx_q_passage ON questions(passage_id);
CREATE INDEX IF NOT EXISTS idx_q_topic_l1 ON questions(topic_l1);
CREATE INDEX IF NOT EXISTS idx_q_difficulty ON questions(difficulty);
CREATE INDEX IF NOT EXISTS idx_q_year ON questions(year);
CREATE INDEX IF NOT EXISTS idx_q_type ON questions(question_type);

-- 组卷记录
CREATE TABLE IF NOT EXISTS generated_papers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    config        TEXT,
    answer_mode   INTEGER DEFAULT 0,
    format        TEXT DEFAULT 'html',
    output_path   TEXT,
    question_ids  TEXT,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 购物车（匿名 session）
CREATE TABLE IF NOT EXISTS cart_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    sort_order  INTEGER DEFAULT 0,
    added_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cart_session ON cart_items(session_id);
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    """建立 SQLite 连接，启用外键约束与 WAL 模式。"""
    conn = sqlite3.connect(
        str(db_path),
        detect_types=sqlite3.PARSE_DECLTYPES,
        timeout=10.0,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """获取数据库连接（context manager）。"""
    db_path = settings.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema(db_path: Path | None = None) -> None:
    """初始化表结构。已存在则跳过（IF NOT EXISTS）。"""
    target = db_path or settings.db_path
    target.parent.mkdir(parents=True, exist_ok=True)
    with _connect(target) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()


def atomic_write_text(path: Path, content: str) -> None:
    """原子写入文本文件：先写临时文件 → fsync → 原子替换。

    适用于 YAML / JSON / Markdown 等文本导出文件。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def backup_database(target: Path | None = None) -> Path:
    r"""备份数据库到 .backups/ 目录，返回备份文件路径。

    优先用 SQLite 原生 ``Connection.backup()``（一致性好）；目标存在时不覆盖。
    """
    src = settings.db_path
    if not src.exists():
        raise FileNotFoundError(f"数据库不存在: {src}")

    if target is not None:
        target.parent.mkdir(parents=True, exist_ok=True)
        dst = target
    else:
        dst_dir = settings.backups_path
        dst_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        dst = dst_dir / f"vault-{stamp}.db"

    if dst.exists():
        raise FileExistsError(f"备份目标已存在: {dst}")

    with _connect(src) as src_conn:
        with sqlite3.connect(str(dst)) as dst_conn:
            src_conn.backup(dst_conn)
    return dst
