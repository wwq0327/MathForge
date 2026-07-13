"""app.database 模块测试。"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager

import pytest

from app.database import (
    ALLOWED_TABLES,
    atomic_write_text,
    backup_database,
    init_schema,
)


def test_init_schema_creates_all_tables(tmp_db_path):
    init_schema(db_path=tmp_db_path)
    with _conn_at(tmp_db_path) as conn:
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert {"questions", "papers", "passages",
            "knowledge_tree", "generated_papers"} <= names


def test_init_schema_is_idempotent(tmp_db_path):
    init_schema(db_path=tmp_db_path)
    init_schema(db_path=tmp_db_path)
    init_schema(db_path=tmp_db_path)
    with _conn_at(tmp_db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
    assert count >= 5


def test_wal_mode_enabled(tmp_db_path):
    init_schema(db_path=tmp_db_path)
    with _conn_at(tmp_db_path) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_foreign_keys_enabled(tmp_db_path):
    init_schema(db_path=tmp_db_path)
    with _conn_at(tmp_db_path) as conn:
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1


def test_allowed_tables_match_schema():
    expected = {
        "knowledge_tree",
        "papers",
        "passages",
        "questions",
        "generated_papers",
    }
    assert ALLOWED_TABLES == expected


def test_atomic_write_text_creates_file(tmp_path):
    target = tmp_path / "out.txt"
    atomic_write_text(target, "hello world\n")
    assert target.read_text(encoding="utf-8") == "hello world\n"


def test_atomic_write_text_overwrites_existing(tmp_path):
    target = tmp_path / "out.txt"
    target.write_text("old", encoding="utf-8")
    atomic_write_text(target, "new")
    assert target.read_text(encoding="utf-8") == "new"


def test_atomic_write_text_creates_parent_dirs(tmp_path):
    target = tmp_path / "a" / "b" / "c" / "out.txt"
    atomic_write_text(target, "deep")
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "deep"


def test_atomic_write_text_cleans_tmp_on_failure(tmp_path, monkeypatch):
    target = tmp_path / "out.txt"
    original_replace = __import__("os").replace

    def boom(src, dst):
        raise OSError("simulated disk error")

    monkeypatch.setattr("os.replace", boom)
    with pytest.raises(OSError, match="simulated disk error"):
        atomic_write_text(target, "x")
    leftover = list(tmp_path.glob(".out.txt.*.tmp"))
    assert leftover == []


def test_backup_database_creates_file(tmp_db_path, tmp_path, monkeypatch):
    from app.config import Settings
    from app import database as database_module

    test_settings = Settings(database_path=str(tmp_db_path))
    monkeypatch.setattr(database_module, "settings", test_settings)

    init_schema(db_path=tmp_db_path)
    with _conn_at(tmp_db_path) as conn:
        conn.execute(
            "INSERT INTO knowledge_tree (id, name) VALUES ('t1', '测试节点')"
        )
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    target = tmp_path / "backup.db"
    result = backup_database(target=target)
    assert result == target
    assert target.exists()

    with _conn_at(target) as conn:
        names = [r[0] for r in conn.execute(
            "SELECT name FROM knowledge_tree"
        ).fetchall()]
    assert "测试节点" in names


def test_backup_database_raises_if_source_missing(tmp_path, monkeypatch):
    from app.config import Settings

    fake_settings = Settings(database_path=str(tmp_path / "no.db"))
    monkeypatch.setattr("app.database.settings", fake_settings)
    with pytest.raises(FileNotFoundError):
        backup_database(target=tmp_path / "backup.db")


def test_backup_database_refuses_overwrite(tmp_db_path, tmp_path):
    init_schema(db_path=tmp_db_path)
    target = tmp_path / "backup.db"
    target.write_text("existing", encoding="utf-8")
    with pytest.raises(FileExistsError):
        backup_database(target=target)


# ── 内部辅助 ──

@contextmanager
def _conn_at(path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()
