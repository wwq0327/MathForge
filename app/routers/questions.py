"""题目路由：列表 + 详情。

- GET /questions：URL 同步筛选 + 分页 + 排序，HTMX 局部刷新
- GET /questions/{id}：详情页（404 返回 ``{detail, code}`` 形式 JSON）
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
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
    topic_choices = question_service.list_topic_l1_choices()
    allowed_topic_l1s = {tid for tid, _ in topic_choices}
    params = _build_params(request)
    q = question_service.parse_list_query(params, allowed_topic_l1s=allowed_topic_l1s)
    rows, total = question_service.list_questions(q)
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
async def detail_question_view(request: Request, question_id: str) -> Response:
    try:
        q = question_service.get_question_detail(question_id)
    except question_service.QuestionNotFoundError:
        return JSONResponse(
            status_code=404,
            content={"detail": "题目不存在", "code": "not_found"},
        )
    return templates.TemplateResponse(
        "questions/detail.html", {"request": request, "q": q}
    )
