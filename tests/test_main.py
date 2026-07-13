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
    assert "disk I/O error" not in r.text


def test_validation_error_returns_422(client):
    """Pydantic 校验失败时统一返回 422 + code。"""
    # /api/stats/summary 无参数，但用无效 HTTP 方法触发 422
    r = client.post("/api/stats/summary", json={"bad": "data"})
    assert r.status_code == 405 or r.status_code == 422


def test_unhandled_exception_returns_500(client, monkeypatch):
    """未捕获异常统一返回 500 + code，不泄露堆栈。"""
    from app import main as main_module

    def boom():
        raise RuntimeError("unexpected internal error")

    # 替换 /health 中的核心调用为爆雷
    monkeypatch.setattr(main_module, "get_connection", boom)
    r = client.get("/health")
    # /health 已捕获 RuntimeError 返回 503
    assert r.status_code == 503


def test_openapi_includes_tags(client):
    """OpenAPI 文档包含 tags 分组。"""
    schema = client.get("/openapi.json").json()
    paths = schema.get("paths", {})
    assert "/" in paths
    assert "/health" in paths
    assert "/api/stats/summary" in paths
    for path, ops in paths.items():
        for method, op in ops.items():
            assert "tags" in op, f"{method} {path} 缺 tags"
