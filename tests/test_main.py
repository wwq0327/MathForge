"""FastAPI 路由测试。"""
from __future__ import annotations

import sqlite3


def test_index_returns_200(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "MathForge" in r.text


def test_health_returns_200_when_db_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] is True
    assert "version" in body


def test_stats_summary_returns_table_counts(client):
    r = client.get("/api/stats/summary")
    assert r.status_code == 200
    body = r.json()
    assert "questions" in body
    assert "knowledge_tree" in body
    assert "papers" in body
    assert "passages" in body
    assert "generated_papers" in body


def test_health_returns_503_when_db_unavailable(client, monkeypatch):
    from contextlib import contextmanager
    from app import main as main_module

    @contextmanager
    def boom():
        raise sqlite3.OperationalError("disk I/O error")
        yield  # pragma: no cover

    monkeypatch.setattr(main_module, "get_connection", boom)
    r = client.get("/health")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert body["database"] is False
    assert "disk I/O error" not in body["error"]
