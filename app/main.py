"""MathForge FastAPI 入口。

P0 范围：
- 应用实例创建
- 模板与静态文件挂载
- 基础首页 + 健康检查
- 数据库健康检查

后续阶段在此注册更多路由：questions / papers / ingest / stats。
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import settings
from .database import get_connection


PROJECT_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"


app = FastAPI(
    title="MathForge",
    description="AI 驱动的本地数学题库管理系统",
    version="0.1.0",
    debug=settings.app_debug,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """首页：P0 占位，显示项目名与阶段信息。"""
    return templates.TemplateResponse(
        "base.html",
        {
            "request": request,
            "project": "MathForge",
            "stage": "P0 — 项目骨架",
            "version": app.version,
        },
    )


@app.get("/health")
async def health() -> dict:
    """健康检查：同时验证数据库可读。"""
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        db_ok = True
    except Exception as exc:  # noqa: BLE001
        return {"status": "degraded", "database": False, "error": str(exc)}
    return {"status": "ok", "database": db_ok, "version": app.version}


@app.get("/api/stats/summary")
async def stats_summary() -> dict:
    """统计摘要：表行数。P3 阶段替换为完整仪表盘数据。"""
    with get_connection() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        summary = {}
        for (name,) in tables:
            summary[name] = conn.execute(
                f"SELECT COUNT(*) FROM {name}"
            ).fetchone()[0]
    return summary
