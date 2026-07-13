# P2 组卷与导出 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement task by task.

**Goal:** 实现手动组卷（勾选 → cart → 生成） + 4 种答案模式 + 导出 HTML/LaTeX

**Architecture:** 新加 `cart_items` 表 + session cookie 中间件做临时购物车；`paper_service.py` 封装所有业务逻辑；`routers/papers.py` 拆分为 API 路由（cart 操作）和页面路由（组卷/预览/导出）；导出模板复用已存在的 KaTeX 和 Jinja2

**Tech Stack:** FastAPI + SQLite + Jinja2 + HTMX + Tailwind + KaTeX

## Global Constraints

- 新增表必须写入 `app/database.py` 的 `SCHEMA_SQL`
- 所有 SQL 列名/表名不拼字符串，用白名单常量
- 所有业务枚举用 `app/models/enums.py` 中定义的值
- 写入 `generated_papers` 和递增 `citation_count` 在同一事务中
- Cart session cookie: `mf_cart`，`max_age=3600`，`httponly=True`
- 导出 LaTeX 不调用 xelatex，直接返回 `.tex` 文件下载
- 对现有 `base.html` 的改动仅限导航栏加"组卷"入口
- 测试文件放 `tests/`，遵循 `test_xxx.py` 命名

---

### Task 1: cart_items 表 + session 中间件

**Files:**
- Modify: `app/database.py` — `SCHEMA_SQL` 加 cart_items 表
- Create: `app/services/cart_middleware.py` — session cookie 中间件
- Modify: `app/main.py` — 注册中间件

**Interfaces:**
- Produces: `CartSessionMiddleware` ASGI 中间件；`cart_items` SQLite 表

- [ ] **Step 1: cart_items 表定义**

在 `app/database.py` 的 `SCHEMA_SQL` 末尾（`generated_papers` 表之后）插入：

```sql
CREATE TABLE IF NOT EXISTS cart_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    sort_order  INTEGER DEFAULT 0,
    added_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cart_session ON cart_items(session_id);
```

同时把 `"cart_items"` 加入 `ALLOWED_TABLES` frozenset。

- [ ] **Step 2: 确认表创建可重复执行**

验证：
```bash
python -c "
from app.database import init_schema
init_schema()
print('OK')
"
```
预期输出：`OK`（IF NOT EXISTS 保障幂等）

- [ ] **Step 3: 写 CartSessionMiddleware**

创建 `app/services/cart_middleware.py`：

```python
from __future__ import annotations

import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

CART_COOKIE = "mf_cart"
CART_MAX_AGE = 3600


class CartSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        session_id = request.cookies.get(CART_COOKIE)
        if not session_id:
            session_id = str(uuid.uuid4())
            request.state.session_id = session_id
            response: Response = await call_next(request)
            response.set_cookie(
                key=CART_COOKIE,
                value=session_id,
                max_age=CART_MAX_AGE,
                path="/",
                httponly=True,
            )
            return response
        request.state.session_id = session_id
        return await call_next(request)
```

- [ ] **Step 4: 注册中间件**

在 `app/main.py` 中，`app` 创建之后，`app.mount("/static"...)` 之前加入：

```python
from app.services.cart_middleware import CartSessionMiddleware
app.add_middleware(CartSessionMiddleware)
```

- [ ] **Step 5: 测中间件**

运行 `python run.py`，访问 `/questions`，检查响应头含 `Set-Cookie: mf_cart=...`。

- [ ] **Step 6: 提交**

```bash
git add app/database.py app/services/cart_middleware.py app/main.py
git commit -m "feat(db,mid): cart_items 表 + session cookie 中间件"
```

---

### Task 2: Paper Service — cart CRUD + generate + export

**Files:**
- Create: `app/services/paper_service.py`
- Modify: `app/database.py` — `ALLOWED_TABLES` 加 "cart_items"

**Interfaces:**
- Consumes: `request.state.session_id` (from middleware)
- Produces: `add_to_cart(session_id, question_id)`, `remove_from_cart(session_id, question_id)`, `list_cart(session_id) -> list[dict]`, `update_order(session_id, question_ids)`, `clear_cart(session_id)`, `generate_paper(session_id, title, answer_mode, format) -> int`, `get_paper(paper_id) -> dict`, `get_paper_questions(paper_id) -> list[QuestionOut]`, `latex_escape(text: str) -> str`

- [ ] **Step 1: 建 paper_service.py**

创建 `app/services/paper_service.py`，包含以下函数：

**cart 操作**（全部接收 `session_id: str`）：

```python
def add_to_cart(session_id: str, question_id: str) -> int:
    """添加题目到 cart，返回当前 cart 总数。重复添加幂等。"""
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM cart_items WHERE session_id=? AND question_id=?",
            (session_id, question_id),
        ).fetchone()
        if existing is None:
            max_order = conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) FROM cart_items WHERE session_id=?",
                (session_id,),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO cart_items (session_id, question_id, sort_order) VALUES (?, ?, ?)",
                (session_id, question_id, max_order + 1),
            )
        return conn.execute(
            "SELECT COUNT(*) FROM cart_items WHERE session_id=?", (session_id,)
        ).fetchone()[0]


def remove_from_cart(session_id: str, question_id: str) -> int:
    """从 cart 移除题目，返回当前 cart 总数。"""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM cart_items WHERE session_id=? AND question_id=?",
            (session_id, question_id),
        )
        return conn.execute(
            "SELECT COUNT(*) FROM cart_items WHERE session_id=?", (session_id,)
        ).fetchone()[0]


def list_cart(session_id: str) -> list[dict]:
    """返回 cart 内的题目（按 sort_order 排序），每项含 question_id。"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, question_id, sort_order FROM cart_items "
            "WHERE session_id=? ORDER BY sort_order, id",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_cart_order(session_id: str, question_ids: list[str]) -> None:
    """按传入顺序更新 sort_order。"""
    with get_connection() as conn:
        for idx, qid in enumerate(question_ids):
            conn.execute(
                "UPDATE cart_items SET sort_order=? WHERE session_id=? AND question_id=?",
                (idx, session_id, qid),
            )


def clear_cart(session_id: str) -> None:
    """清空当前 session 的 cart。"""
    with get_connection() as conn:
        conn.execute("DELETE FROM cart_items WHERE session_id=?", (session_id,))


def cart_count(session_id: str) -> int:
    """返回 cart 中的题目数量。"""
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM cart_items WHERE session_id=?", (session_id,)
        ).fetchone()[0]
```

- [ ] **Step 2: generate_paper 函数**

```python
def generate_paper(
    session_id: str,
    title: str,
    answer_mode: int = 0,
    format: str = "html",
) -> int:
    """从 cart 生成试卷，写入 generated_papers，递增 citation_count，清空 cart。"""
    items = list_cart(session_id)
    if not items:
        raise ValueError("cart 为空，无法生成试卷")
    question_ids = [item["question_id"] for item in items]
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO generated_papers (title, answer_mode, format, question_ids) "
            "VALUES (?, ?, ?, ?)",
            (title, answer_mode, format, json.dumps(question_ids)),
        )
        paper_id = cur.lastrowid
        placeholders = ",".join("?" * len(question_ids))
        conn.execute(
            f"UPDATE questions SET citation_count = citation_count + 1 "
            f"WHERE id IN ({placeholders})",
            question_ids,
        )
        conn.execute(
            "DELETE FROM cart_items WHERE session_id=?", (session_id,)
        )
    return paper_id
```

需要 import `json`。

- [ ] **Step 3: get_paper / get_paper_questions 函数**

```python
def get_paper(paper_id: int) -> dict | None:
    """返回 generated_papers 记录，不存在返回 None。"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM generated_papers WHERE id=?", (paper_id,)
        ).fetchone()
    return dict(row) if row else None


def get_paper_questions(paper_id: int) -> list[dict]:
    """返回试卷关联的题目列表。"""
    paper = get_paper(paper_id)
    if not paper:
        return []
    qids = json.loads(paper["question_ids"])
    if not qids:
        return []
    placeholders = ",".join("?" * len(qids))
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM questions WHERE id IN ({placeholders})",
            qids,
        ).fetchall()
    qmap = {r["id"]: dict(r) for r in rows}
    return [qmap[qid] for qid in qids if qid in qmap]
```

- [ ] **Step 4: latex_escape filter**

```python
_LATEX_SPECIAL = str.maketrans({
    "#": r"\#",
    "$": r"\$",
    "%": r"\%",
    "&": r"\&",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "\\": r"\textbackslash{}",
})


def latex_escape(text: str) -> str:
    """转义 LaTeX 特殊字符。"""
    return text.translate(_LATEX_SPECIAL) if text else text
```

- [ ] **Step 5: 测试 paper_service 主逻辑**

```bash
python -c "
from app.services.paper_service import *
import uuid
sid = str(uuid.uuid4())
# 加一个不存在的 ID 应报错（外键约束）
# 加一个存在的 ID（先查 demo 数据中的真实 ID）
"
```

但需要先有数据。在后续 Task 中统一测试。这里只确认导入和语法无错：

```bash
python -c "from app.services.paper_service import add_to_cart, remove_from_cart, list_cart, generate_paper, latex_escape; print('import ok')"
```

预期输出：`import ok`

- [ ] **Step 6: 提交**

```bash
git add app/services/paper_service.py
git commit -m "feat(service): 组卷业务逻辑 — cart CRUD + generate + export 辅助"
```

---

### Task 3: LaTeX escape Jinja2 filter

**Files:**
- Modify: None — 直接用 `app/services/paper_service.py` 中已定义的 `latex_escape`

**说明：**
LaTeX 导出模板 `.tex.j2` 中通过 `environments` 或 `add_to_environs` 注册 filter 使用。FastAPI 的 Jinja2Templates 在路由中注册。

改为在 `app/main.py` 或 `app/routers/papers.py` 中注册：

```python
from app.services.paper_service import latex_escape

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["latex_escape"] = latex_escape
```

但 `app/main.py` 已有 `templates` 实例。export 模板在 `routers/papers.py` 中使用。为确保 filter 可用，在 `routers/papers.py` 中从 `app.main` 导入 `templates`。

实际上更好的做法：在 `app/main.py` 中注册 filter。

- [ ] **Step 1: 注册 latex_escape filter**

在 `app/main.py` 中，`templates = Jinja2Templates(...)` 之后加入：

```python
from app.services.paper_service import latex_escape
templates.env.filters["latex_escape"] = latex_escape
```

- [ ] **Step 2: 验证 filter**

```bash
python -c "
from app.services.paper_service import latex_escape
assert latex_escape('100%') == r'100\%'
assert latex_escape('# &') == r'\# \&'
print('latex_escape OK')
"
```

- [ ] **Step 3: 提交**

```bash
git add app/main.py
git commit -m "feat(export): 注册 latex_escape Jinja2 filter"
```

---

### Task 4: Papers Router

**Files:**
- Create: `app/routers/papers.py`

**Interfaces:**
- Produces: `router` 变量，包含所有 /papers 和 /api/cart 路由
- Consumes: `request.state.session_id`

- [ ] **Step 1: 写 papers.py 路由文件**

```python
"""组卷路由：cart API + 生成/预览/导出页面。"""
from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import TEMPLATES_DIR
from app.services import paper_service

router = APIRouter(tags=["papers"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _session_id(request: Request) -> str:
    return request.state.session_id


# ── Cart API ──


@router.post("/api/cart/toggle")
async def cart_toggle(request: Request, question_id: str) -> HTMLResponse:
    sid = _session_id(request)
    cart = paper_service.list_cart(sid)
    qids = {item["question_id"] for item in cart}
    if question_id in qids:
        paper_service.remove_from_cart(sid, question_id)
    else:
        paper_service.add_to_cart(sid, question_id)
    count = paper_service.cart_count(sid)
    return templates.TemplateResponse(
        "papers/_cart_bar.html",
        {"request": request, "count": count},
    )


@router.get("/api/cart/summary")
async def cart_summary(request: Request) -> HTMLResponse:
    sid = _session_id(request)
    count = paper_service.cart_count(sid)
    return templates.TemplateResponse(
        "papers/_cart_bar.html",
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
        "papers/_cart_bar.html",
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
        "papers/new.html",
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
    title = form.get("title", "未命名试卷")
    try:
        answer_mode = int(form.get("answer_mode", 0))
    except (ValueError, TypeError):
        answer_mode = 0
    fmt = form.get("format", "html")
    if fmt not in ("html", "latex"):
        fmt = "html"
    try:
        paper_id = paper_service.generate_paper(sid, title, answer_mode, fmt)
    except ValueError:
        return RedirectResponse(url="/papers/new", status_code=303)
    return RedirectResponse(url=f"/papers/{paper_id}", status_code=303)


# ── 查看/导出页面 ──


@router.get("/papers/{paper_id}")
async def papers_result(request: Request, paper_id: int) -> HTMLResponse:
    paper = paper_service.get_paper(paper_id)
    if paper is None:
        return JSONResponse(status_code=404, content={"detail": "试卷不存在", "code": "not_found"})
    return templates.TemplateResponse(
        "papers/result.html",
        {"request": request, "paper": paper},
    )


@router.get("/papers/{paper_id}/preview")
async def papers_preview(request: Request, paper_id: int) -> HTMLResponse:
    paper = paper_service.get_paper(paper_id)
    if paper is None:
        return JSONResponse(status_code=404, content={"detail": "试卷不存在", "code": "not_found"})
    questions = paper_service.get_paper_questions(paper_id)
    answer_mode = paper["answer_mode"]
    return templates.TemplateResponse(
        "export/print.html",
        {
            "request": request,
            "paper": paper,
            "questions": questions,
            "answer_mode": answer_mode,
        },
    )


@router.get("/papers/{paper_id}/export/html")
async def papers_export_html(request: Request, paper_id: int):
    paper = paper_service.get_paper(paper_id)
    if paper is None:
        return JSONResponse(status_code=404, content={"detail": "试卷不存在", "code": "not_found"})
    questions = paper_service.get_paper_questions(paper_id)
    answer_mode = paper["answer_mode"]
    rendered = templates.TemplateResponse(
        "export/print.html",
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
async def papers_export_latex(request: Request, paper_id: int):
    paper = paper_service.get_paper(paper_id)
    if paper is None:
        return JSONResponse(status_code=404, content={"detail": "试卷不存在", "code": "not_found"})
    questions = paper_service.get_paper_questions(paper_id)
    answer_mode = paper["answer_mode"]
    rendered = templates.TemplateResponse(
        "export/paper.tex.j2",
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
```

- [ ] **Step 2: 注册 router 到 main.py**

在 `app/main.py` 中：

```python
from .routers import papers as papers_router
app.include_router(papers_router.router)
```

现有的 `questions_router` 注册后面加入即可。

- [ ] **Step 3: 验证导入**

```bash
python -c "from app.routers.papers import router; print('import ok')"
```

预期输出：`import ok`

- [ ] **Step 4: 提交**

```bash
git add app/routers/papers.py app/main.py
git commit -m "feat(router): 组卷路由 — cart API + 生成/预览/导出"
```

---

### Task 5: 模板 — cart 浮条 + new.html + result.html

**Files:**
- Create: `app/templates/papers/_cart_bar.html`
- Create: `app/templates/papers/new.html`
- Create: `app/templates/papers/result.html`

- [ ] **Step 1: _cart_bar.html**

```html
<div id="cart-bar"
     class="fixed bottom-0 left-0 right-0 bg-white border-t border-slate-200 shadow-lg px-6 py-3 flex items-center justify-between z-50 transition-all duration-200"
     hx-swap-oob="true">
  <span class="text-sm text-slate-600">
    已选 <strong class="text-indigo-600">{{ count }}</strong> 题
  </span>
  <div class="flex items-center gap-2">
    <button hx-post="/api/cart/clear"
            hx-target="#cart-bar"
            hx-swap="outerHTML"
            class="text-xs text-slate-400 hover:text-red-500 transition-colors">
      清空
    </button>
    <a href="/papers/new"
       class="inline-block px-4 py-1.5 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700 transition-colors {% if count == 0 %}opacity-50 pointer-events-none{% endif %}">
      生成试卷
    </a>
  </div>
</div>
```

- [ ] **Step 2: questions/_table.html 加 checkbox 列**

在现有的 `_table.html` 中，表头和数据行各加一列：

表头 `<th>` 加 `<th class="w-10">#</th>`

数据行 `<td>` 加：
```html
<td class="w-10">
  <input type="checkbox"
         class="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cart-checkbox"
         data-question-id="{{ row.id }}"
         {% if row.id in cart_qids %}checked{% endif %}
         hx-post="/api/cart/toggle?question_id={{ row.id }}"
         hx-target="#cart-bar"
         hx-swap="outerHTML">
</td>
```

注意：列表视图需要获取当前 cart 的 question_id 集合。要么：
- A) 修改 `list_questions_view` 也传 `cart_qids`
- B) 用 HTMX 额外请求

选 A，因为最简单。在 router 中获取并传入 ctx。

修改 `app/routers/questions.py`：

文件顶部加：
```python
from app.services.paper_service import list_cart

def _session_id(request: Request) -> str:
    return request.state.session_id
```

在 `list_questions_view` 中，`ctx` 字典加：
```python
cart_items = list_cart(_session_id(request))
cart_qids = {item["question_id"] for item in cart_items}
ctx["cart_qids"] = cart_qids
```

HTMX 刷新 `_table.html` 时同样需要 `cart_qids`，所以**不管是否 HTMX 都计算**。

- [ ] **Step 3: _table.html 增加 cart_qids 判断**

模板 `_table.html` 中，循环 `rows` 时 `{% if row.id in cart_qids %}` 控制 checkbox 初始选中状态。

因为 HTMX 刷新时同时返回 table 和 cart_bar 的 swap，所以 `_table.html` 刷新也要传 `cart_qids`。

修改 `_table.html` 模板：

```html
{% for row in rows %}
<tr class="border-b border-slate-100 hover:bg-slate-50 transition-colors">
  <td class="px-4 py-3">
    <input type="checkbox"
           class="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cart-checkbox"
           data-question-id="{{ row.id }}"
           {% if row.id in cart_qids %}checked{% endif %}
           hx-post="/api/cart/toggle?question_id={{ row.id }}"
           hx-target="#cart-bar"
           hx-swap="outerHTML">
  </td>
  <!-- 现有列保持不变 -->
```

`_table.html` 自身需要一个 `{% block cart_qids %}` 或直接作为变量传入。修改 router 中 `_table.html` 的渲染也要传 `cart_qids`。

- [ ] **Step 4: new.html**

```html
{% extends "base.html" %}
{% block content %}
<div class="max-w-4xl mx-auto">
  <h2 class="text-lg font-semibold mb-4">生成试卷</h2>

  {% if not cart_questions %}
  <div class="bg-white rounded-lg border border-slate-200 p-8 text-center">
    <p class="text-slate-500 mb-4">购物车为空，请先在题库浏览页选择题目。</p>
    <a href="/questions" class="text-indigo-600 hover:text-indigo-800">→ 去选题</a>
  </div>
  {% else %}
  <form method="post" action="/papers">
    <div class="bg-white rounded-lg border border-slate-200 p-6 mb-6">
      <label class="block mb-2 text-sm font-medium">试卷标题</label>
      <input type="text" name="title"
             class="w-full px-3 py-2 border border-slate-300 rounded text-sm"
             placeholder="例如：2026 九上期中测试" required>
    </div>

    <div class="bg-white rounded-lg border border-slate-200 p-6 mb-6">
      <h3 class="text-sm font-medium mb-3">已选题目（{{ cart_questions|length }} 题）</h3>
      <ol class="space-y-2">
        {% for q in cart_questions %}
        <li class="flex items-center gap-3 text-sm text-slate-700">
          <span class="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-xs font-medium">{{ loop.index }}</span>
          <span class="flex-1 truncate">{{ q.stem|striptags|truncate(80) }}</span>
          <span class="text-xs text-slate-400">{{ q.question_type }}</span>
        </li>
        {% endfor %}
      </ol>
    </div>

    <div class="bg-white rounded-lg border border-slate-200 p-6 mb-6">
      <h3 class="text-sm font-medium mb-3">答案模式</h3>
      <div class="space-y-2">
        <label class="flex items-center gap-2 text-sm">
          <input type="radio" name="answer_mode" value="0" checked>
          0 — 完整显示（题干 + 解答 + 答案）
        </label>
        <label class="flex items-center gap-2 text-sm">
          <input type="radio" name="answer_mode" value="1">
          1 — 留白篇幅（解答区空白占位，答案隐藏）
        </label>
        <label class="flex items-center gap-2 text-sm">
          <input type="radio" name="answer_mode" value="2">
          2 — 固定空白（题后分页占位，答案隐藏）
        </label>
        <label class="flex items-center gap-2 text-sm">
          <input type="radio" name="answer_mode" value="3">
          3 — 完全隐藏（仅题干）
        </label>
      </div>
    </div>

    <div class="bg-white rounded-lg border border-slate-200 p-6 mb-6">
      <h3 class="text-sm font-medium mb-3">导出格式</h3>
      <div class="space-y-2">
        <label class="flex items-center gap-2 text-sm">
          <input type="radio" name="format" value="html" checked>
          HTML 打印版（浏览器直接查看/打印）
        </label>
        <label class="flex items-center gap-2 text-sm">
          <input type="radio" name="format" value="latex">
          LaTeX（.tex 文件，可自行编译为 PDF）
        </label>
      </div>
    </div>

    <button type="submit"
            class="px-6 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 transition-colors">
      生成试卷
    </button>
  </form>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 5: result.html**

```html
{% extends "base.html" %}
{% block content %}
<div class="max-w-4xl mx-auto">
  <div class="bg-white rounded-lg border border-slate-200 p-8 text-center">
    <h2 class="text-lg font-semibold mb-2">试卷已生成</h2>
    <p class="text-slate-500 mb-6">{{ paper.title }}</p>

    <div class="flex items-center justify-center gap-4 mb-6">
      <a href="/papers/{{ paper.id }}/preview"
         class="px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 transition-colors">
        预览
      </a>
      <a href="/papers/{{ paper.id }}/export/html"
         class="px-4 py-2 border border-indigo-600 text-indigo-600 rounded hover:bg-indigo-50 transition-colors">
        下载 HTML
      </a>
      <a href="/papers/{{ paper.id }}/export/latex"
         class="px-4 py-2 border border-indigo-600 text-indigo-600 rounded hover:bg-indigo-50 transition-colors">
        下载 LaTeX
      </a>
    </div>

    <p class="text-xs text-slate-400">
      {% if paper.answer_mode == 0 %}完整显示模式{% elif paper.answer_mode == 1 %}留白篇幅模式{% elif paper.answer_mode == 2 %}固定空白模式{% else %}完全隐藏模式{% endif %}
      ·
      {% if paper.format == "html" %}HTML{% else %}LaTeX{% endif %}
      ·
      {{ paper.created_at }}
    </p>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 6: 验证模板语法**

```bash
python -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('app/templates'))
env.get_template('papers/_cart_bar.html')
env.get_template('papers/new.html')
env.get_template('papers/result.html')
print('template syntax OK')
"
```

- [ ] **Step 7: 提交**

```bash
git add app/templates/papers/ app/routers/questions.py
git commit -m "feat(templates): cart 浮条 + 组卷表单 + 结果页 + 浏览页 checkbox"
```

---

### Task 6: 模板 — 导出模板

**Files:**
- Create: `app/templates/export/print.html`
- Create: `app/templates/export/paper.tex.j2`

- [ ] **Step 1: print.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ paper.title }}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"
          onload="renderMathInElement(document.body, {delimiters: [{left: '$$', right: '$$', display: true}, {left: '$', right: '$', display: false}]});"></script>
  <style>
    @media print {
      @page { margin: 2cm; }
      body { font-size: 12pt; line-height: 1.6; color: #000; }
      .no-print { display: none !important; }
      .page-break { page-break-after: always; }
      .solution-space { min-height: 12em; border: 1px dashed #ccc; margin: 1em 0; padding: 0.5em; }
    }
    body { font-family: 'Times New Roman', serif; padding: 2em; max-width: 210mm; margin: 0 auto; }
    .header { text-align: center; margin-bottom: 2em; border-bottom: 2px solid #333; padding-bottom: 1em; }
    .question { margin-bottom: 1.5em; }
    .question .stem { margin-bottom: 0.5em; }
    .question .answer { margin-top: 0.5em; padding: 0.5em; background: #f9f9f9; }
    .question .solution { margin-top: 0.5em; padding: 0.5em; background: #f0f0f0; }
  </style>
</head>
<body>
  <div class="header">
    <h1>{{ paper.title }}</h1>
  </div>

  {% for q in questions %}
  <div class="question">
    <div class="stem">{{ q.stem|safe }}</div>

    {% if answer_mode == 0 %}
      {% if q.answer %}<div class="answer"><strong>答案：</strong>{{ q.answer|safe }}</div>{% endif %}
      {% if q.solution %}<div class="solution"><strong>解析：</strong>{{ q.solution|safe }}</div>{% endif %}
    {% elif answer_mode == 1 %}
      <div class="solution-space"></div>
    {% elif answer_mode == 2 %}
      <div class="page-break"></div>
    {% endif %}
  </div>
  {% endfor %}

  <div class="no-print" style="margin-top: 2em; padding-top: 1em; border-top: 1px solid #ccc;">
    <p style="text-align: center;">
      <a href="#" onclick="window.print();return false;" style="color: #4f46e5;">打印</a>
      {% if paper.answer_mode == 0 %}
      · <a href="/papers/{{ paper.id }}/export/latex" style="color: #4f46e5;">下载 LaTeX</a>
      {% endif %}
    </p>
  </div>
</body>
</html>
```

- [ ] **Step 2: paper.tex.j2**

```latex
{% autoescape false %}
\documentclass[12pt,a4paper]{ctexart}
\usepackage{amsmath,amssymb,geometry,enumitem}
\geometry{left=2cm,right=2cm,top=2.5cm,bottom=2.5cm}

\title{{{ paper.title }}}
\date{}
\begin{document}
\maketitle

{% for q in questions %}
\section*{第 {{ loop.index }} 题}

{{ q.stem | latex_escape }}

{% if q.answer and answer_mode == 0 %}
\noindent\textbf{答案：}{{ q.answer | latex_escape }}
{% endif %}

{% if q.solution and answer_mode == 0 %}
\begin{solution}
{{ q.solution | latex_escape }}
\end{solution}
{% endif %}

{% if answer_mode == 1 %}
\vspace{5cm}
{% elif answer_mode == 2 %}
\newpage
{% endif %}

{% endfor %}
\end{document}
{% endautoescape %}
```

- [ ] **Step 3: 验证**

```bash
python -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('app/templates'))
env.get_template('export/print.html')
env.get_template('export/paper.tex.j2')
print('export template syntax OK')
"
```

- [ ] **Step 4: 提价**

```bash
git add app/templates/export/
git commit -m "feat(templates): HTML 打印版 + LaTeX 导出模板"
```

---

### Task 7: 导航 + 集成测试

**Files:**
- Modify: `app/templates/base.html` — 导航加"组卷"入口
- Modify: `app/main.py` — 确认 router 已注册
- Create: `tests/test_papers.py` — 完整测试

- [ ] **Step 1: base.html 导航栏加"组卷"**

在 `base.html` 的 `<nav>` 中加：

```html
<a href="/papers/new" class="hover:text-slate-900">组卷</a>
```

- [ ] **Step 2: 写测试文件**

创建 `tests/test_papers.py`：

```python
"""组卷模块测试。"""
from __future__ import annotations

import json
import uuid

import pytest
from app.services.paper_service import (
    add_to_cart,
    cart_count,
    clear_cart,
    generate_paper,
    get_paper,
    get_paper_questions,
    latex_escape,
    list_cart,
    remove_from_cart,
    update_cart_order,
)


@pytest.fixture
def session_id() -> str:
    """返回一个随机 session_id。"""
    return str(uuid.uuid4())


@pytest.fixture
def demo_question_ids() -> list[str]:
    """返回 demo 数据中的题目 ID。"""
    from app.database import get_connection
    with get_connection() as conn:
        rows = conn.execute("SELECT id FROM questions LIMIT 3").fetchall()
    return [r["id"] for r in rows]


class TestCartService:
    def test_add_to_cart(self, session_id, demo_question_ids):
        qid = demo_question_ids[0]
        count = add_to_cart(session_id, qid)
        assert count == 1
        items = list_cart(session_id)
        assert len(items) == 1
        assert items[0]["question_id"] == qid

    def test_add_duplicate_is_idempotent(self, session_id, demo_question_ids):
        qid = demo_question_ids[0]
        add_to_cart(session_id, qid)
        add_to_cart(session_id, qid)
        assert cart_count(session_id) == 1

    def test_add_multiple_questions(self, session_id, demo_question_ids):
        for qid in demo_question_ids:
            add_to_cart(session_id, qid)
        assert cart_count(session_id) == len(demo_question_ids)
        items = list_cart(session_id)
        assert len(items) == len(demo_question_ids)

    def test_remove_from_cart(self, session_id, demo_question_ids):
        qid = demo_question_ids[0]
        add_to_cart(session_id, qid)
        count = remove_from_cart(session_id, qid)
        assert count == 0
        assert cart_count(session_id) == 0

    def test_remove_nonexistent(self, session_id):
        count = remove_from_cart(session_id, "M0000-NONE-999")
        assert count == 0

    def test_clear_cart(self, session_id, demo_question_ids):
        for qid in demo_question_ids:
            add_to_cart(session_id, qid)
        clear_cart(session_id)
        assert cart_count(session_id) == 0

    def test_update_cart_order(self, session_id, demo_question_ids):
        for qid in demo_question_ids:
            add_to_cart(session_id, qid)
        reversed_ids = list(reversed(demo_question_ids))
        update_cart_order(session_id, reversed_ids)
        items = list_cart(session_id)
        assert [i["question_id"] for i in items] == reversed_ids

    def test_cart_empty_list(self, session_id):
        assert list_cart(session_id) == []

    def test_cart_count_zero(self, session_id):
        assert cart_count(session_id) == 0


class TestGeneratePaper:
    def test_generate_paper(self, session_id, demo_question_ids):
        for qid in demo_question_ids:
            add_to_cart(session_id, qid)
        pid = generate_paper(session_id, "测试试卷", answer_mode=0, format="html")
        assert pid > 0
        paper = get_paper(pid)
        assert paper is not None
        assert paper["title"] == "测试试卷"
        assert paper["answer_mode"] == 0
        assert paper["format"] == "html"

    def test_generate_empty_cart_raises(self, session_id):
        with pytest.raises(ValueError, match="空"):
            generate_paper(session_id, "空试卷")

    def test_generate_increments_citation_count(self, session_id, demo_question_ids):
        from app.database import get_connection
        qid = demo_question_ids[0]
        with get_connection() as conn:
            before = conn.execute("SELECT citation_count FROM questions WHERE id=?", (qid,)).fetchone()[0]
        add_to_cart(session_id, qid)
        generate_paper(session_id, "引用计数测试")
        with get_connection() as conn:
            after = conn.execute("SELECT citation_count FROM questions WHERE id=?", (qid,)).fetchone()[0]
        assert after == before + 1

    def test_generate_clears_cart(self, session_id, demo_question_ids):
        for qid in demo_question_ids:
            add_to_cart(session_id, qid)
        generate_paper(session_id, "清空测试")
        assert cart_count(session_id) == 0

    def test_get_paper_nonexistent(self):
        assert get_paper(99999) is None

    def test_get_paper_questions(self, session_id, demo_question_ids):
        for qid in demo_question_ids:
            add_to_cart(session_id, qid)
        pid = generate_paper(session_id, "题目列表测试")
        questions = get_paper_questions(pid)
        assert len(questions) == len(demo_question_ids)

    def test_get_paper_questions_nonexistent(self):
        assert get_paper_questions(99999) == []


class TestLatexEscape:
    def test_escape_percent(self):
        assert latex_escape("100%") == r"100\%"

    def test_escape_hash(self):
        assert latex_escape("#1") == r"\#1"

    def test_escape_underscore(self):
        assert latex_escape("a_b") == r"a\_b"

    def test_escape_dollar(self):
        assert latex_escape("$5") == r"\$5"

    def test_escape_braces(self):
        assert latex_escape("{test}") == r"\{test\}"

    def test_escape_backslash(self):
        assert latex_escape("a\\b") == r"a\textbackslash{}b"

    def test_escape_ampersand(self):
        assert latex_escape("a&b") == r"a\&b"

    def test_escape_none(self):
        assert latex_escape("正常文本") == "正常文本"

    def test_escape_empty(self):
        assert latex_escape("") == ""

    def test_escape_tilde(self):
        assert "~" in latex_escape("~")
        assert "textasciitilde" in latex_escape("~")
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/test_papers.py -v
```

全部通过后：

```bash
pytest --cov=app
```

确保覆盖率不降。

- [ ] **Step 4: ruff + mypy**

```bash
ruff check .
mypy app/
```

- [ ] **Step 5: 手工验证**

```bash
python run.py
```

- 浏览页勾选/取消 → 浮条更新
- 浮条"生成试卷" → `/papers/new` → 显示已选题
- 填写标题 → 选择答案模式/格式 → 生成
- 结果页 → 预览 / 下载 HTML / 下载 LaTeX

- [ ] **Step 6: 提交**

```bash
git add app/templates/base.html tests/test_papers.py
git commit -m "test(papers): 导航入口 + 完整组卷测试套件"
```

---

## Spec Coverage Check

| Spec Section | Task |
|---|---|
| 2.1 Cart Items 表 | Task 1 |
| 3. Cart 机制 / Session 管理 | Task 1 (middleware) |
| 4.2 API 路由 | Task 4 |
| 2.2 Answer Mode | Task 5 (new.html radio) |
| 2.3 Generated Papers | Task 2 (generate_paper) |
| 4.1 页面路由 | Task 4 |
| 5.1 HTML 打印版 | Task 6 (print.html) |
| 5.2 LaTeX 模板 | Task 6 (paper.tex.j2) |
| 6. 引用计数 | Task 2 (generate_paper 内) |
| 浏览页 checkbox | Task 5 |
| 导航入口 | Task 7 |
| 测试 | Task 7 |
