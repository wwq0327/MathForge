"""MathForge FastAPI 入口。"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api_schemas import HealthResponse, StatsSummaryResponse, install_exception_handlers
from .config import STATIC_DIR, settings, templates
from .database import get_connection
from .logging_config import configure as configure_logging
from .logging_config import get_logger
from .services.cart_middleware import CartSessionMiddleware

configure_logging(log_dir=settings.db_path.parent, level="DEBUG" if settings.app_debug else "INFO")
log = get_logger("main")


app = FastAPI(
    title="MathForge",
    description="AI 驱动的本地数学题库管理系统",
    version="0.2.0",
    debug=settings.app_debug,
)


if settings.app_debug:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_middleware(CartSessionMiddleware)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """基础安全响应头。"""
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path in {"/docs", "/redoc"}:
        return response
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response

app.mount("/static", StaticFiles(directory=str(STATIC_DIR), html=False), name="static")
from app.services.paper_service import latex_escape

templates.env.filters["latex_escape"] = latex_escape
install_exception_handlers(app)

from .routers import papers as papers_router  # noqa: E402
from .routers import questions as questions_router  # noqa: E402

app.include_router(questions_router.router)
app.include_router(papers_router.router)


@app.get("/", response_class=HTMLResponse, tags=["system"], summary="首页")
async def index(request: Request) -> HTMLResponse:
    """首页：当前阶段概览。"""
    return templates.TemplateResponse(
        request,
        "base.html",
        {
            "project": "MathForge",
            "stage": "P0 — 项目骨架",
            "version": app.version,
        },
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["system"],
    summary="健康检查",
)
async def health() -> JSONResponse:
    """健康检查：DB 不可读时返回 503，不向客户端泄露错误细节。"""
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception:
        log.exception("health check failed")
        return JSONResponse(
            status_code=503,
            content=HealthResponse(
                status="degraded", database=False, version=app.version
            ).model_dump(),
        )
    return JSONResponse(
        status_code=200,
        content=HealthResponse(
            status="ok", database=True, version=app.version
        ).model_dump(),
    )


@app.get(
    "/api/stats/summary",
    response_model=StatsSummaryResponse,
    tags=["stats"],
    summary="统计摘要",
)
async def stats_summary() -> StatsSummaryResponse:
    """统计摘要：表行数。P3 阶段替换为完整仪表盘数据。"""
    from .database import ALLOWED_TABLES

    summary = StatsSummaryResponse()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        for (name,) in rows:
            if name not in ALLOWED_TABLES:
                continue
            count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            setattr(summary, name, count)
    return summary
