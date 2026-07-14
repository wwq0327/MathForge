"""组卷路由：cart API + 生成/预览/导出页面。"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)

from app.config import templates
from app.services import paper_service

router = APIRouter(tags=["papers"])


def _session_id(request: Request) -> str:
    return request.state.session_id


# ── Cart API ──


@router.post("/api/cart/toggle")
async def cart_toggle(request: Request, question_id: str) -> Response:
    sid = _session_id(request)
    cart = paper_service.list_cart(sid)
    qids = {item["question_id"] for item in cart}
    if question_id in qids:
        paper_service.remove_from_cart(sid, question_id)
    else:
        result = paper_service.add_to_cart(sid, question_id)
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"detail": "题目不存在", "code": "not_found"},
            )
    count = paper_service.cart_count(sid)
    return templates.TemplateResponse(
        request, "papers/_cart_bar.html",
        {"request": request, "count": count},
    )


@router.get("/api/cart/summary")
async def cart_summary(request: Request) -> HTMLResponse:
    sid = _session_id(request)
    count = paper_service.cart_count(sid)
    return templates.TemplateResponse(
        request, "papers/_cart_bar.html",
        {"request": request, "count": count},
    )


@router.put("/api/cart/reorder")
async def cart_reorder(request: Request) -> JSONResponse:
    sid = _session_id(request)
    body = await request.json()
    question_ids = body.get("question_ids", [])
    paper_service.update_cart_order(sid, question_ids)
    return JSONResponse({"status": "ok"})


@router.post("/api/cart/clear")
async def cart_clear(request: Request) -> HTMLResponse:
    sid = _session_id(request)
    paper_service.clear_cart(sid)
    return templates.TemplateResponse(
        request, "papers/_cart_bar.html",
        {"request": request, "count": 0},
    )


# ── 组卷页面 ──


@router.get("/papers/new")
async def papers_new(request: Request) -> HTMLResponse:
    sid = _session_id(request)
    items = paper_service.list_cart(sid)
    qids = [item["question_id"] for item in items]
    if qids:
        placeholders = ",".join("?" * len(qids))
        from app.database import get_connection
        with get_connection() as conn:
            rows = conn.execute(
                f"SELECT id, stem, question_type, difficulty FROM questions WHERE id IN ({placeholders})",
                qids,
            ).fetchall()
        questions = {r["id"]: dict(r) for r in rows}
    else:
        questions = {}
    cart_questions = [questions.get(item["question_id"]) for item in items if item["question_id"] in questions]
    return templates.TemplateResponse(
        request, "papers/new.html",
        {
            "request": request,
            "items": items,
            "cart_questions": cart_questions,
        },
    )


@router.post("/papers")
async def papers_generate(request: Request) -> RedirectResponse:
    sid = _session_id(request)
    form = await request.form()
    title_raw = form.get("title", "未命名试卷")
    title = title_raw if isinstance(title_raw, str) else "未命名试卷"
    answer_mode_raw = form.get("answer_mode", 0)
    try:
        answer_mode = int(answer_mode_raw) if isinstance(answer_mode_raw, str) else 0
    except (ValueError, TypeError):
        answer_mode = 0
    fmt_raw = form.get("format", "html")
    fmt = fmt_raw if isinstance(fmt_raw, str) else "html"
    if fmt not in ("html", "latex"):
        fmt = "html"
    try:
        paper_id = paper_service.generate_paper(sid, title, answer_mode, fmt)
    except ValueError:
        return RedirectResponse(url="/papers/new", status_code=303)
    return RedirectResponse(url=f"/papers/{paper_id}", status_code=303)


# ── 查看/导出页面 ──


@router.get("/papers/{paper_id}")
async def papers_result(request: Request, paper_id: int) -> Response:
    paper = paper_service.get_paper(paper_id)
    if paper is None:
        return JSONResponse(status_code=404, content={"detail": "试卷不存在", "code": "not_found"})
    return templates.TemplateResponse(
        request, "papers/result.html",
        {"request": request, "paper": paper},
    )


@router.get("/papers/{paper_id}/preview")
async def papers_preview(request: Request, paper_id: int) -> Response:
    paper = paper_service.get_paper(paper_id)
    if paper is None:
        return JSONResponse(status_code=404, content={"detail": "试卷不存在", "code": "not_found"})
    questions = paper_service.get_paper_questions(paper_id)
    answer_mode = paper["answer_mode"]
    return templates.TemplateResponse(
        request, "export/print.html",
        {
            "request": request,
            "paper": paper,
            "questions": questions,
            "answer_mode": answer_mode,
        },
    )


@router.get("/papers/{paper_id}/export/html")
async def papers_export_html(request: Request, paper_id: int) -> Response:
    paper = paper_service.get_paper(paper_id)
    if paper is None:
        return JSONResponse(status_code=404, content={"detail": "试卷不存在", "code": "not_found"})
    questions = paper_service.get_paper_questions(paper_id)
    answer_mode = paper["answer_mode"]
    rendered = templates.TemplateResponse(
        request, "export/print.html",
        {
            "request": request,
            "paper": paper,
            "questions": questions,
            "answer_mode": answer_mode,
        },
    )
    body = rendered.body.decode() if hasattr(rendered.body, "decode") else rendered.body
    return HTMLResponse(
        content=body,
        headers={"Content-Disposition": f'attachment; filename="paper-{paper_id}.html"'},
    )


@router.get("/papers/{paper_id}/export/latex")
async def papers_export_latex(request: Request, paper_id: int) -> Response:
    paper = paper_service.get_paper(paper_id)
    if paper is None:
        return JSONResponse(status_code=404, content={"detail": "试卷不存在", "code": "not_found"})
    questions = paper_service.get_paper_questions(paper_id)
    answer_mode = paper["answer_mode"]
    rendered = templates.TemplateResponse(
        request, "export/paper.tex.j2",
        {
            "request": request,
            "paper": paper,
            "questions": questions,
            "answer_mode": answer_mode,
        },
    )
    body = rendered.body.decode() if hasattr(rendered.body, "decode") else rendered.body
    return PlainTextResponse(
        content=body,
        media_type="application/x-tex",
        headers={"Content-Disposition": f'attachment; filename="paper-{paper_id}.tex"'},
    )
