"""统一 API 响应与错误结构。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """统一错误响应。"""
    detail: str = Field(..., description="人类可读错误描述")
    code: str = Field(..., description="机器可读错误码")


class HealthResponse(BaseModel):
    """健康检查响应。"""
    status: str = Field(..., description="ok | degraded")
    database: bool = Field(..., description="数据库是否可读")
    version: str = Field(..., description="服务版本")


class StatsSummaryResponse(BaseModel):
    """统计摘要：表名 → 行数。"""
    questions: int = 0
    papers: int = 0
    passages: int = 0
    knowledge_tree: int = 0
    generated_papers: int = 0
    cart_items: int = 0


def install_exception_handlers(app) -> None:
    """为 FastAPI app 安装统一异常处理器。"""
    from fastapi import Request, status
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "请求参数校验失败",
                "code": "validation_error",
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        from .logging_config import get_logger
        log = get_logger("unhandled")
        log.exception("unhandled error: %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "内部错误", "code": "internal_error"},
        )
