# P2 组卷与导出 设计文档

- **阶段**：P2
- **范围**：手动组卷 + 答案模式 + 导出 HTML/LaTeX
- **技术栈**：FastAPI + Jinja2 + HTMX + Tailwind + KaTeX（CDN）
- **预计工时**：2 天
- **设计日期**：2026-07-13

---

## 1. 目标与边界

### 1.1 包含
- 手动选题：浏览页勾选 + cart 机制（session cookie + `cart_items` 表）
- 生成试卷：从 cart 生成 `generated_papers` 记录
- 4 种答案模式（0-完整 / 1-留白 / 2-固定空白 / 3-完全隐藏）
- 导出 HTML 打印版（Jinja2 + KaTeX）
- 导出 LaTeX（`.tex` 文件下载，不编译 PDF）
- `citation_count` 批量递增

### 1.2 不包含
- AI 预组卷（P4 LLM 接入后）
- 题目顺序拖拽（先数字输入）
- LaTeX → PDF 编译（依赖系统环境，后续再议）
- 试卷存档/历史管理（P5 管理后台）

### 1.3 验收标准
- 浏览页每行可勾选/取消勾选，底部浮条实时更新已选数量
- `/papers/new` 可调整顺序、选择答案模式、选择导出格式
- 生成后 `citation_count` 正确递增
- HTML 打印预览按答案模式正确显示/隐藏解答
- LaTeX 导出生成合法 `.tex`（ctex + amsmath 包）
- 135+ 个测试全部通过

---

## 2. 数据层

### 2.1 Cart Items 表

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

- `session_id`：服务端生成 UUID，存 cookie `mf_cart`，`max_age=3600`
- 每次写入先按 `session_id` 查，不存在则自动创建新 session

### 2.2 Answer Mode

复用 `generated_papers.answer_mode` 字段（INTEGER），值域：

| 值 | 名称 | 显示 |
|----|------|------|
| 0  | 完整显示 | 题干 + 解答 + 答案 |
| 1  | 留白篇幅 | 保留解答区占位空白，答案隐藏 |
| 2  | 固定空白 | 题后分页占位，答案隐藏 |
| 3  | 完全隐藏 | 仅题干 |

### 2.3 Generated Papers

现有 `generated_papers` 表，写入时填充：

| 字段 | 来源 |
|------|------|
| title | 用户输入 |
| config | JSON: `{"grade": "...", "section": "...", ...}` |
| answer_mode | 0-3 |
| format | "html" / "latex" |
| question_ids | JSON 数组，保持排序 |
| output_path | 导出文件路径（可选） |
| citation_count | 首次读取时从 questions 表聚合 |

---

## 3. Cart 机制

### 3.1 Session 管理

- 中间件 `CartSessionMiddleware`：检查 `mf_cart` cookie
- 不存在则生成 UUID v4，设置 cookie（`path=/`, `max_age=3600`, `httponly=True`）
- 请求中通过 `request.state.session_id` 访问

### 3.2 HTMX 交互

| 触发 | 路由 | 效果 |
|------|------|------|
| 勾选 checkbox | `POST /api/cart/toggle?question_id=X` | 写入/删除 cart_items，返回浮条 fragment |
| 底部浮条点击 | `GET /api/cart/summary` | 返回已选数量 + "生成试卷"按钮 |
| 页面加载 | `GET /api/cart/summary` | 初始化浮条状态 + 选中状态 |

**浮条**：固定在底部的 `<div>`，包含：
- "已选 N 题"
- "生成试卷" 按钮 → `/papers/new`

---

## 4. 组卷路由

### 4.1 路由表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/papers/new` | 组卷页面：cart 题目列表 + 表单（标题、答案模式、格式） |
| POST | `/papers` | 生成试卷：写入 `generated_papers` → 递增 `citation_count` → 重定向到 `/papers/{id}` |
| GET | `/papers/{id}` | 试卷结果页（展示摘要 + 导出链接） |
| GET | `/papers/{id}/preview` | HTML 打印预览 |
| GET | `/papers/{id}/export/html` | HTML 文件下载 |
| GET | `/papers/{id}/export/latex` | LaTeX `.tex` 文件下载 |

### 4.2 API 路由

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/cart/toggle` | 添加/移除题目（带 `question_id`） |
| GET | `/api/cart/summary` | 返回浮条 HTMX fragment |
| PUT | `/api/cart/reorder` | 调整顺序（传入 id 列表） |
| POST | `/api/cart/clear` | 清空当前 session |

---

## 5. 导出模板

### 5.1 HTML 打印版

模板 `templates/export/print.html`：

- 纯打印样式（`@media print`），无导航/页眉
- `\` 分页占位（仅答案模式 2）
- KaTeX 渲染题干
- 答案模式控制：
  - `{% if answer_mode == 0 %}` 显示 `{{ q.answer }}` 和 `{{ q.solution }}`
  - `{% if answer_mode == 1 %}` 显示解答区占位框，无答案
  - `{% if answer_mode == 2 %}` 题后 `<div class="page-break">`
  - `{% if answer_mode == 3 %}` 跳过解答和答案

### 5.2 LaTeX 模板

模板 `templates/export/paper.tex.j2`：

```latex
\documentclass[12pt,a4paper]{ctexart}
\usepackage{amsmath,amssymb,geometry,enumitem}
\geometry{left=2cm,right=2cm,top=2.5cm,bottom=2.5cm}
\begin{document}
\title{试卷标题}
\date{}
\maketitle

{% for q in questions %}
\section*{第 {{ loop.index }} 题}

{{ q.stem|latex_escape }}

{% if answer_mode == 0 %}
\begin{solution}
{{ q.solution|latex_escape }}
\end{solution}
\vfill
{% elif answer_mode == 1 %}
\vspace{5cm}
{% elif answer_mode == 2 %}
\newpage
{% endif %}
{% endfor %}
\end{document}
```

- `latex_escape` filter：`#`, `$`, `%`, `&`, `_`, `{`, `}`, `~`, `\` 转义
- 不调用 xelatex，直接返回 `.tex` 文件下载（`Content-Disposition: attachment`）

---

## 6. 引用计数

生成试卷时批量递增：

```sql
UPDATE questions
SET citation_count = citation_count + 1
WHERE id IN (?, ?, ..., ?)
```

在写入 `generated_papers` 后的同个事务中执行。

---

## 7. 新文件清单

```
app/services/paper_service.py      — 组卷业务（cart CRUD + generate + export）
app/routers/papers.py              — 组卷路由
app/routers/__init__.py            — 已有，注册新 router
app/templates/papers/new.html      — 组卷表单页
app/templates/papers/result.html   — 生成成功页面
app/templates/papers/_cart_bar.html  — 底部浮条 HTMX fragment
app/templates/papers/_cart_row.html  — cart 题目行 HTMX fragment
app/templates/export/print.html    — HTML 打印模板
app/templates/export/paper.tex.j2  — LaTeX 模板
docs/superpowers/plans/2026-07-13-p2-composition.md  — 实施计划（后续生成）
```

---

## 8. 测试

| 模块 | 类型 | 用例 |
|------|------|------|
| `paper_service` | 单元 | cart 增删查、空 cart 拒绝、重复勾选幂等、citation_count 递增、latex 转义 |
| `routers/papers` | 集成 | 生成成功 302、无效 ID 404、预览 200、HTML 下载 200、LaTeX 下载 200 |
| `export` | 单元 | 4 种答案模式渲染、LaTeX 模板转义 |

预估新增 30-40 个测试。

---

## 9. 验证

- `ruff check .` — 无新 warning
- `mypy app/` — 无新 type error
- `pytest --cov=app` — 覆盖率不降
- 手工验证：浏览页勾选 → 浮条更新 → 生成 → 预览 → 下载
