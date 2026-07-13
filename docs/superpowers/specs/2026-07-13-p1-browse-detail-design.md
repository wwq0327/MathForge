# P1 题目浏览与详情 设计文档

- **阶段**：P1
- **范围**：仅 `questions` 表
- **技术栈**：FastAPI + Jinja2 + HTMX + Tailwind + KaTeX（CDN）
- **预计工时**：3 天
- **设计日期**：2026-07-13

---

## 1. 目标与边界

### 1.1 包含
- 题目列表页：URL 同步多条件筛选 + 分页 + 排序，HTMX 局部刷新表格区
- 题目详情页：独立路由，KaTeX 渲染题干/答案/解析 + 完整元数据
- 业务服务层（`question_service`）：纯函数 + SQL 白名单
- 路由层（`routers/questions.py`）：两个 GET 端点
- 测试：service 单元 + 路由集成 + 表单参数解析
- 示例题种子：独立 issue，P1 主线不阻塞

### 1.2 不包含
- passages / papers 浏览（P5 管理后台阶段）
- 题目编辑/录入（P4 录入引擎阶段）
- 关键词搜索 / 全文检索
- 收藏/购物车 / 组卷（P2 阶段）
- Alpine.js（仅在 P4 审查界面需要，本期不引入）
- Playwright 端到端测试

### 1.3 验收标准
- `/questions` 列表页 200，含筛选侧栏 + 表格
- 筛选/分页/排序触发 HTMX 局部刷新，URL 同步可分享
- `/questions/{id}` 详情页 200，KaTeX 正确渲染数学公式
- 非法 ID / 不存在题目 → 404 + 通用消息
- 测试通过，`mypy app/` / `ruff check .` 干净
- CI 绿灯

---

## 2. 架构与数据流

```
浏览器（HTMX）
    │
    │  GET /questions?grade=…&page=2
    │  HX-Request: true（局部刷新）或省略（完整页）
    ▼
FastAPI 路由（routers/questions.py）
    │
    ▼
question_service（services/question_service.py）
    │  - parse_list_query(params)
    │  - list_questions(q) -> (rows, total)
    │  - get_question_detail(id)
    ▼
SQLite（参数化查询 + 白名单列名/排序）
```

**层职责**：
- **路由**：解析 HTTP 层（query string、HTMX 头）、调用服务、选模板、错误码映射
- **服务**：业务逻辑、SQL 构造、枚举白名单校验、参数合法性
- **模板**：HTML 渲染、HTMX 属性绑定、KaTeX 调用
- **数据库**：`app.database.get_connection()` context manager，WAL + foreign_keys

---

## 3. 路由契约

### 3.1 `GET /questions`

**Query 参数**：

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `grade` | str，可重复 | 无 | 七/八/九年级，URL 写中文枚举值 |
| `question_type` | str，可重复 | 无 | 题型枚举值 |
| `section` | str，可重复 | 无 | 六大板块 |
| `difficulty` | str，可重复 | 无 | 易/中/难 |
| `year` | int，可重复 | 无 | 1900-2100 |
| `source_abbr` | str，可重复 | 无 | `^[A-Z]+$` |
| `review_status` | str，可重复 | 无 | 草稿/待审核/已入库 |
| `topic_l1` | str，可重复 | 无 | 知识树顶层节点 **id**（模板显示对应 name） |
| `sort` | str | `year_desc` | `year_desc` / `id_asc` / `citation_desc` |
| `page` | int ≥ 1 | 1 | 页码 |

**响应**：
- 非 HTMX 请求：HTML 完整页（base.html + list.html，含筛选侧栏 + `#q-table` 容器 + 初始表格片段）
- HTMX 请求（`HX-Request: true`）：HTML 片段（仅 `_table.html`，含表格 + 分页）

**HTTP 状态**：
- 200：所有合法 / 非法参数（非法值被丢弃，等同无过滤）
- 404：理论不触发（无路径参数）

### 3.2 `GET /questions/{id}`

**路径参数**：
- `id` —— `^M\d{4}-[A-Z]+-\d+$`（与 `QUESTION_ID_PATTERN` 一致）

**响应**：
- 200：HTML 完整页（base.html + detail.html）
- 404：通用消息（`{detail: "题目不存在", code: "not_found"}`），不论 ID 不匹配正则还是库内不存在
- 不泄露 ID 内容

---

## 4. 服务层契约

### 4.1 数据类

```python
@dataclass(frozen=True)
class QuestionListQuery:
    grades: list[str] = field(default_factory=list)
    question_types: list[str] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)
    difficulties: list[str] = field(default_factory=list)
    years: list[int] = field(default_factory=list)
    source_abbrs: list[str] = field(default_factory=list)
    review_statuses: list[str] = field(default_factory=list)
    topic_l1s: list[str] = field(default_factory=list)
    sort: str = "year_desc"
    page: int = 1
    page_size: int = 20  # 固定
```

### 4.2 公开函数

```python
def parse_list_query(params: Mapping[str, list[str]]) -> QuestionListQuery:
    """解析并校验 query string，非法值丢弃，缺失项用默认。

    params 由路由层用 ``request.query_params.getlist(key)`` 显式组装为
    ``dict[str, list[str]]`` 后传入；service 不直接依赖 Starlette 类型。
    """

def list_questions(q: QuestionListQuery) -> tuple[list[QuestionOut], int]:
    """返回 (本页 rows, 总数)；page 越界返回 ([], total)。"""

def get_question_detail(id: str) -> QuestionOut:
    """返回题目详情；不存在抛 QuestionNotFoundError。"""

def list_topic_l1_choices() -> list[tuple[str, str]]:
    """返回 (id, name) 列表，仅 parent_id IS NULL；供筛选下拉。"""
```

### 4.3 异常

```python
class QuestionNotFoundError(Exception):
    """题目 ID 不存在或 ID 不合法。"""
```

---

## 5. SQL 构造与安全

### 5.1 白名单

```python
ALLOWED_FILTER_COLUMNS: dict[str, tuple[str, str]] = {
    # URL 参数 -> (列名, 类型标记 for 参数校验)
    "grade": ("grade", "text"),
    "question_type": ("question_type", "text"),
    "section": ("section", "text"),
    "difficulty": ("difficulty", "text"),
    "year": ("year", "int"),
    "source_abbr": ("source_abbr", "text"),
    "review_status": ("review_status", "text"),
    "topic_l1": ("topic_l1", "text"),
}

ALLOWED_SORTS: dict[str, str] = {
    "year_desc": "year DESC, id ASC",
    "id_asc": "id ASC",
    "citation_desc": "citation_count DESC, id ASC",
}
```

### 5.2 枚举值白名单

- 文本参数：值必须在 `EnumCls.__members__` 对应的 `.value` 集合内；不在则丢弃
  - 复用 `app.models.enums.Grade` / `QuestionType` / `Section` / `Difficulty` / `ReviewStatus`
- `year`：`1900 ≤ int(v) ≤ 2100`，非整数丢弃
- `source_abbr`：匹配 `^[A-Z]+$`，否则丢弃
- `topic_l1`：经 `list_topic_l1_choices()` 校验；不在白名单则丢弃

### 5.3 SQL 模板

```sql
-- 列表
SELECT <全部列> FROM questions
 WHERE 1=1
   [AND <col> IN (?, ?, ?) ...]
   [AND <col> IN (?, ?, ?) ...]
 ORDER BY <白名单 sort>
 LIMIT ? OFFSET ?

-- 计数
SELECT COUNT(*) FROM questions
 WHERE 1=1
   [AND ...]
```

- 列名/排序从白名单取，**绝不走 f-string 拼列**
- 占位符数 = 各过滤值列表的元素数之和
- 列表 + 计数共享 WHERE 片段生成器（保证一致）
- 全程 `get_connection()` context manager，事务由 `get_connection` 提交

### 5.4 安全回归

- `?grade=' OR 1=1 --` → 丢弃（不在枚举集合）
- `?source_abbr=A'; DROP TABLE questions; --` → 丢弃（不匹配 `^[A-Z]+$`）
- `?year=99999` → 丢弃（越界）
- `?sort=id; DROP TABLE` → 回退默认 `year_desc`

---

## 6. 模板结构

### 6.1 文件树

```
app/templates/
├── base.html                 # 改造：加 htmx CDN + 3 个 block
└── questions/
    ├── list.html             # 完整页：侧栏 + #q-table 容器
    ├── _filters.html         # 筛选侧栏片段
    ├── _table.html           # 表格片段（HTMX 局部刷入）
    ├── _pagination.html      # 分页片段
    └── detail.html           # 详情完整页
```

### 6.2 base.html 改造（增量）

- `<head>` 加 `<script src="https://unpkg.com/htmx.org@1.9.10" defer></script>`
- 新增 `{% block extra_head %}{% endblock %}` / `{% block content %}{% endblock %}` / `{% block scripts %}{% endblock %}`
- 顶部 `<nav>` 加 `<a href="/questions">题库浏览</a>`
- 不破坏现有 P0 页面（首页仍是默认内容）

### 6.3 list.html 布局

```
┌────────────────┬────────────────────────────────────┐
│  _filters.html │  #q-table（hx-target）             │
│  - 年级 多选   │   ┌─ _table.html ──────────────┐  │
│  - 题型 多选   │   │ 题号  题型  难度  年份  ...  │  │
│  - 板块 多选   │   │ 行（点行跳详情）           │  │
│  - 难度 多选   │   │ ...                         │  │
│  - 年份 多选   │   └─ _pagination.html ───────┘  │
│  - 来源 多选   │                                    │
│  - 状态 多选   │                                    │
│  - 知识点 多选 │                                    │
│  - 排序 单选   │                                    │
│  - [清空]      │                                    │
└────────────────┴────────────────────────────────────┘
```

### 6.4 HTMX 绑定

- 侧栏 `<form id="filters">` 包裹所有 `<select multiple>` + 排序 `<select>`
- 排序：`hx-get="/questions" hx-include="#filters" hx-target="#q-table" hx-trigger="change" hx-push-url="true"`
- 分页按钮：`hx-get="/questions?{当前筛选+新页码}" hx-target="#q-table" hx-push-url="true"`
- "清空"链接：`<a href="/questions">`（无参）
- KaTeX 重渲染：监听 `htmx:afterSwap`，对 `#q-table` 调 `renderMathInElement`

### 6.5 _filters.html

- 7 个多选 + 1 个排序单选，选项从枚举 `.value` 动态生成（`{# for v in enum_values #}` Jinja 循环）
- 知识点 l1 选项从 `list_topic_l1_choices()` 取 `[(id, name), ...]`
- 模板显示 `name`（如"数与代数"），URL 带 `id`（如"kt-001"）
- 选中状态：`{% if value in current_filters %}selected{% endif %}`
- `<select multiple>` 配 `name="grade"` 等，HTMX 自动包含

### 6.6 _table.html

- 表头：题号、题型、难度、年份、来源、知识点、引用次数、操作
- 行：`<tr style="cursor:pointer" onclick="window.location='/questions/{{ q.id }}'">`（点行跳详情，不用 HTMX）
- 末列 `<a href="/questions/{{ q.id }}">查看</a>` 显式按钮
- 空状态：`<tr><td colspan="7">无匹配题目</td></tr>`

### 6.7 _pagination.html

- 上一页 / 下一页按钮，URL 带当前筛选参数
- 页码 > 1 显示「上一页」，< 总页数显示「下一页」
- 总页数 = ceil(total / page_size)

### 6.8 detail.html

- 标题：`{id} · {question_type} · {difficulty}`
- 题干块：`<h2>题干</h2><div>{{ stem|safe }}</div>`
- 答案块：`<h2>答案</h2><div>{{ answer|safe }}</div>`
- 解析块：`<h2>解析</h2><div>{{ solution|safe }}</div>`
- 元数据表：学段/年级/板块/年份/来源/来源缩写/是否真题/审核状态/知识点 l1/l2/考查角度/核心素养（JSON 列表）/布鲁姆层级（JSON 列表）/题号/分值/引用次数/关联试卷/关联大题
- "返回列表"链接：从 referer 或 query 反推带筛选参数；fallback `/questions`

---

## 7. 测试策略

### 7.1 `tests/test_question_service.py`（单元）

**`parse_list_query`**：
- 空参 → 默认值
- 单值：`?grade=七年级` → `grades=["七年级"]`
- 多值 repeat key：`?grade=七年级&grade=八年级`
- 非法值丢弃
- 年份越界/非数字丢弃
- 非法排序回退默认
- 页码负数/零/非数字回退 1

**`list_questions`**（用 `_seed_questions` fixture 灌入 8-10 条覆盖数据）：
- 空库 → `([], 0)`
- 单条匹配
- 多条件 AND
- 多值 IN
- 三种排序
- 分页边界
- 越界页 → `([], total)`
- 知识点筛选
- 综合场景

**`get_question_detail`**：
- 存在
- 不存在 → `QuestionNotFoundError`
- 非法 ID（不匹配正则）→ `ValueError`（路由层捕获 → 404）

**安全回归**（合并到 `parse_list_query`）：
- `?grade='; DROP TABLE--` 丢弃
- `?source_abbr=A'; DROP TABLE--` 丢弃

### 7.2 `tests/test_questions_router.py`（集成）—— 用 `client` fixture

**`GET /questions`**：
- 默认 200 + 含"题库浏览"标题 + 至少 1 个 `<select>`
- 筛选生效：响应行年级匹配
- 分页：`?page=2` 含分页导航
- 空库：含"暂无题目"占位
- HTMX 头：带 → 响应**不含** `<html>` 标签
- 非 HTMX：响应**含** `<html>`
- 非法参数 → 200 + 全部题（被丢弃）
- 题目链接 `href` 指向 `/questions/{id}`

**`GET /questions/{id}`**：
- 存在 200 + KaTeX 数学块
- 不存在 → 404 + 通用消息
- 非法 id → 404
- 元数据表含全部字段
- "返回列表"链接存在

### 7.3 不做的

- Jinja2 模板快照测试
- Playwright e2e
- 性能/负载测试

### 7.4 覆盖率目标

- `question_service.py`：≥ 95%
- `routers/questions.py`：≥ 90%（404 / 非法 / HTMX 分支全覆盖）

### 7.5 预计新增测试

约 35 个（service 18 + router 17）。

### 7.6 conftest 新增

- `_seed_questions(db_path, n)` fixture：灌入 n 道覆盖 7 维度的示例题，供 service 测试用
- router 测试用较小固定集（5-8 道）

---

## 8. 文件改动清单

| 路径 | 类型 | 说明 |
|---|---|---|
| `app/services/question_service.py` | 新增 | 业务服务（白名单 + SQL 构造） |
| `app/services/demo_seed.py` | 新增 | 示例题种子（独立 issue） |
| `app/routers/__init__.py` | 现有空 | 暂不动 |
| `app/routers/questions.py` | 新增 | 路由层 |
| `app/main.py` | 修改 | 注册 `routers/questions.py` |
| `app/templates/base.html` | 修改 | 加 htmx CDN + 3 block + nav 链接 |
| `app/templates/questions/list.html` | 新增 | 列表完整页 |
| `app/templates/questions/_filters.html` | 新增 | 筛选侧栏 |
| `app/templates/questions/_table.html` | 新增 | 表格片段 |
| `app/templates/questions/_pagination.html` | 新增 | 分页片段 |
| `app/templates/questions/detail.html` | 新增 | 详情页 |
| `app/static/js/app.js` | 修改 | 注册 htmx:afterSwap → KaTeX 重渲染 |
| `tests/conftest.py` | 修改 | 加 `_seed_questions` fixture |
| `tests/test_question_service.py` | 新增 | service 单元测试 |
| `tests/test_questions_router.py` | 新增 | router 集成测试 |
| `scripts/init_db.py` | 修改 | 加 `--demo` 参数 |
| `tests/test_init_db.py` | 修改 | demo 模式测试 |

---

## 9. 依赖与脚本改动

- **requirements.txt**：不变（FastAPI/Jinja2/SQLite 已有）
- **Pillow** 等图片处理：本期不引入（详情页不展示 images 字段）
- **`init_db.py`**：加 `--demo` 参数

---

## 10. 风险与遗留

| 风险 | 应对 |
|---|---|
| 枚举值 URL 含中文，URL 编码/解码需注意 | Starlette 框架已处理，测试覆盖 |
| HTMX 1.9 vs 2.0 行为差异 | 锁定 1.9.10，CDN 固定版本 |
| 大量题目时分页性能 | P1 阶段 25 道示例不构成压力；真实规模在 P4 录入后关注 |
| KaTeX 与 HTMX 局部刷新的 hook 顺序 | `htmx:afterSwap` 事件后渲染，事件在 DOM 替换完成后触发 |
| Node.js 20 deprecation 警告（CI） | 与本期无关，留 P7 |

---

## 11. 拆分建议（独立 issue）

1. **示例题种子**（`--demo` 选项）：本期不阻塞，独立提交
2. **统计仪表盘 / 高频考点**：P3 阶段独立范围
3. **Pillow 图片渲染（详情页 images 字段）**：P5 阶段补

---

## 12. 完成定义（DoD）

- [ ] `mypy app/` 退出码 0
- [ ] `ruff check .` 全过
- [ ] `pytest` 全部用例通过（75 + 新增 ~35 = 110+）
- [ ] CI 三段式（lint + mypy + test）绿灯（Python 3.11 / 3.12）
- [ ] 浏览器手测：列表筛选/分页/排序/详情全通
- [ ] AGENTS.md / PROGRESS.md 同步：P1 阶段标完成
- [ ] README "P1 待开始" 改"完成"
- [ ] 至少 1 个 commit message 引用本 spec 路径
