"""题目路由：列表 + 详情。

- GET /questions：URL 同步筛选 + 分页 + 排序，HTMX 局部刷新
- GET /questions/{id}：详情页（404 走全局异常处理）
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import TEMPLATES_DIR
from app.services import question_service

router = APIRouter(tags=["questions"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _build_params(request: Request) -> dict[str, list[str]]:
    """组装 query_params 为 dict[str, list[str]]。"""
    qp = request.query_params
    keys = {
        "grade", "question_type", "section", "difficulty", "year",
        "source_abbr", "review_status", "topic_l1", "sort", "page",
    }
    return {k: qp.getlist(k) for k in keys if qp.getlist(k)}


@router.get(
    "/questions",
    response_class=HTMLResponse,
    summary="题目列表（HTMX 局部刷新友好）",
)
async def list_questions_view(request: Request) -> HTMLResponse:
    params = _build_params(request)
    q = question_service.parse_list_query(params)
    rows, total = question_service.list_questions(q)
    topic_choices = question_service.list_topic_l1_choices()
    is_htmx = request.headers.get("HX-Request") == "true"

    ctx = {
        "request": request,
        "rows": rows,
        "total": total,
        "query": q,
        "params": params,
        "topic_choices": topic_choices,
        "page_total": (total + q.page_size - 1) // q.page_size if total else 0,
    }
    if is_htmx:
        return templates.TemplateResponse("questions/_table.html", ctx)
    return templates.TemplateResponse("questions/list.html", ctx)


@router.get(
    "/questions/{question_id}",
    response_class=HTMLResponse,
    summary="题目详情",
)
async def detail_question_view(request: Request, question_id: str) -> HTMLResponse:
    try:
        q = question_service.get_question_detail(question_id)
    except question_service.QuestionNotFoundError as err:
        raise HTTPException(status_code=404, detail="题目不存在") from err
    return templates.TemplateResponse(
        "questions/detail.html", {"request": request, "q": q}
    )
