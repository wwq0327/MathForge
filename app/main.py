"""MathForge FastAPI 入口。"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import PROJECT_ROOT, STATIC_DIR, TEMPLATES_DIR, settings
from .database import get_connection
from .logging_config import configure as configure_logging
from .logging_config import get_logger


configure_logging(log_dir=settings.db_path.parent, level="DEBUG" if settings.app_debug else "INFO")
log = get_logger("main")


app = FastAPI(
    title="MathForge",
    description="AI 驱动的本地数学题库管理系统",
    version="0.1.0",
    debug=settings.app_debug,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR), html=False), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/", response_class=HTMLResponse, tags=["system"])
async def index(request: Request) -> HTMLResponse:
    """首页：当前阶段概览。"""
    return templates.TemplateResponse(
        "base.html",
        {
            "request": request,
            "project": "MathForge",
            "stage": "P0 — 项目骨架",
            "version": app.version,
        },
    )


@app.get("/health", tags=["system"])
async def health() -> JSONResponse:
    """健康检查：DB 不可读时返回 503，不向客户端泄露错误细节。"""
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception as exc:  # noqa: BLE001
        log.exception("health check failed")
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": False, "error": "database unavailable"},
            headers={"X-Error-Reason": "db-unavailable" if str(exc) else ""},
        )
    return JSONResponse(
        status_code=200,
        content={"status": "ok", "database": True, "version": app.version},
    )


@app.get("/api/stats/summary", tags=["system"])
async def stats_summary() -> dict:
    """统计摘要：表行数。P3 阶段替换为完整仪表盘数据。"""
    from .database import ALLOWED_TABLES

    summary: dict[str, int] = {}
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        for (name,) in rows:
            if name not in ALLOWED_TABLES:
                continue
            summary[name] = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    return summary
