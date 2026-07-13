# P1 题目浏览与详情 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 MathForge 落地 P1 阶段——题目多维筛选列表页（HTMX 局部刷新）+ 题目详情页（KaTeX 渲染）。

**Architecture:** 服务层（`question_service` 纯函数 + SQL 白名单）→ 路由层（`routers/questions.py` 两个 GET）→ 模板层（Jinja2 + HTMX 局部 swap + Tailwind/KaTeX CDN）。筛选条件在 URL 中以 repeat-key 形式同步，HTMX 局部刷新 `#q-table` 容器。

**Tech Stack:** FastAPI · Jinja2 · SQLite · HTMX 1.9.10 (CDN) · Tailwind CDN · KaTeX CDN · pytest · ruff · mypy。

**Spec:** `docs/superpowers/specs/2026-07-13-p1-browse-detail-design.md`

## Global Constraints

- Python 3.12（项目 `.python-version`），FastAPI 0.115，Pydantic 2.10
- 所有公共函数必须测：正常路径 + 失败路径（AGENTS.md）
- 改动后必须跑 `pytest` / `ruff check .` / `mypy app/`，CI 三段式全绿（#18）
- 公开 API 必须含 `tags` / `response_model` / `summary`（AGENTS.md）
- 数据库写入用 `get_connection()` context manager（AGENTS.md）
- 服务层不依赖 Starlette 类型（route 层负责 query_params → dict 转换）
- 一事一提交，commit message 含 issue 编号，中文简述 why
- raw/ 只读不删（AGENTS.md 关键设计原则 #4）
- 字段值域以 `app/models/enums.py` 为准（AGENTS.md 必读先行）
- 模板走 `app/templates/`；新增片段以 `_` 前缀
- 静态资源走 `app/static/`
- 公共 API 异常处理走 `app.api_schemas.install_exception_handlers` 已注册的全局处理器
- mypy 1.14 — `mypy app/` 必须通过（#23 已修）

---

## 文件结构（实施前地图）

**新增**：
- `app/services/question_service.py` — 业务服务（白名单 + SQL 构造 + 异常类型）
- `app/services/demo_seed.py` — 示例题种子数据
- `app/routers/questions.py` — 路由
- `app/templates/questions/list.html` — 列表完整页
- `app/templates/questions/_filters.html` — 筛选侧栏片段
- `app/templates/questions/_table.html` — 表格片段（HTMX 局部刷入用）
- `app/templates/questions/_pagination.html` — 分页片段
- `app/templates/questions/detail.html` — 详情完整页
- `tests/test_question_service.py` — service 单元测试
- `tests/test_questions_router.py` — router 集成测试
- `tests/test_demo_seed.py` — 种子测试

**修改**：
- `app/main.py` — 注册路由
- `app/api_schemas.py` — 加 `QuestionListResponse`（如需 API 形式）
- `app/templates/base.html` — htmx CDN + 3 个 block + nav 链接
- `app/static/js/app.js` — htmx:afterSwap 钩 KaTeX 重渲染
- `scripts/init_db.py` — `--demo` 参数
- `tests/conftest.py` — `_seed_questions` fixture
- `tests/test_init_db.py` — demo 模式测试
- `app/models/question.py` — 可能加 `QuestionListItem` 精简版（只列字段）
- `AGENTS.md` / `PROGRESS.md` / `README.md` — 同步 P1 完成

---

### Task 1: question_service 骨架 + parse_list_query

**Files:**
- Create: `app/services/question_service.py`
- Test: `tests/test_question_service.py`

**Interfaces:**
- Consumes: `app.models.enums.{Grade,QuestionType,Section,Difficulty,ReviewStatus}` 枚举；`app.database.get_connection`
- Produces:
  - `QuestionListQuery` dataclass（含 `page_size: int = 20`）
  - `class QuestionNotFoundError(Exception)`
  - `parse_list_query(params: Mapping[str, list[str]]) -> QuestionListQuery`
  - `ALLOWED_FILTER_COLUMNS: dict[str, tuple[str, str]]`
  - `ALLOWED_SORTS: dict[str, str]`

- [ ] **Step 1: 写失败测试**

`tests/test_question_service.py`：
```python
"""question_service 单元测试。"""
from __future__ import annotations

import pytest

from app.services.question_service import (
    ALLOWED_FILTER_COLUMNS,
    ALLOWED_SORTS,
    QuestionListQuery,
    parse_list_query,
)


def test_parse_empty_returns_defaults():
    q = parse_list_query({})
    assert q == QuestionListQuery()


def test_parse_single_value():
    q = parse_list_query({"grade": ["七年级"]})
    assert q.grades == ["七年级"]
    assert q.question_types == []


def test_parse_repeat_key_multi_value():
    q = parse_list_query({"grade": ["七年级", "八年级"]})
    assert q.grades == ["七年级", "八年级"]


def test_parse_illegal_grade_dropped():
    q = parse_list_query({"grade": ["六年级", "七年级"]})
    assert q.grades == ["七年级"]


def test_parse_year_validates_range():
    q = parse_list_query({"year": ["1850", "2024", "2200", "abc"]})
    assert q.years == [2024]


def test_parse_source_abbr_validates_pattern():
    q = parse_list_query({"source_abbr": ["NCZK", "abc", "NCZK'; DROP--"]})
    assert q.source_abbrs == ["NCZK"]


def test_parse_illegal_sort_falls_back():
    q = parse_list_query({"sort": ["foo"]})
    assert q.sort == "year_desc"


def test_parse_legal_sort_kept():
    q = parse_list_query({"sort": ["citation_desc"]})
    assert q.sort == "citation_desc"


def test_parse_page_falls_back_on_garbage():
    q = parse_list_query({"page": ["-1", "0", "abc", "3"]})
    assert q.page == 3


def test_parse_question_type_legal_values():
    q = parse_list_query({"question_type": ["选择题", "未知题", "填空题"]})
    assert q.question_types == ["选择题", "填空题"]


def test_parse_difficulty_legal_values():
    q = parse_list_query({"difficulty": ["易", "极难", "中"]})
    assert q.difficulties == ["易", "中"]


def test_parse_section_legal_values():
    q = parse_list_query({"section": ["数与代数", "虚构板块", "函数"]})
    assert q.sections == ["数与代数", "函数"]


def test_parse_review_status_legal_values():
    q = parse_list_query({"review_status": ["草稿", "垃圾状态", "已入库"]})
    assert q.review_statuses == ["草稿", "已入库"]


def test_whitelist_defined():
    assert "grade" in ALLOWED_FILTER_COLUMNS
    assert "year" in ALLOWED_FILTER_COLUMNS
    assert ALLOWED_SORTS["year_desc"] == "year DESC, id ASC"
    assert ALLOWED_SORTS["citation_desc"] == "citation_count DESC, id ASC"
```

- [ ] **Step 2: 跑测试，预期失败**

Run: `.venv/bin/python -m pytest tests/test_question_service.py -v`
Expected: ImportError 或 ModuleNotFoundError（模块不存在）

- [ ] **Step 3: 实现 question_service 骨架**

`app/services/question_service.py`：
```python
"""题目服务：列表查询 / 详情查询 / SQL 白名单。

设计要点：
- parse_list_query 接受路由层组装的 dict[str, list[str]]，与 Starlette 解耦
- 所有枚举值走白名单，非法值丢弃；非字典 / 类型错误的入参永不入 SQL
- 列名 / 排序从模块级常量取，绝不走 f-string 拼列
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.models.enums import (
    Difficulty,
    Grade,
    QuestionType,
    ReviewStatus,
    Section,
)


class QuestionNotFoundError(Exception):
    """题目 ID 不存在或 ID 不合法。"""


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
    page_size: int = 20


# SQL 列白名单：URL 参数 -> (列名, 类型标记)。
# 列名由白名单常量提供，**绝不**走 f-string 拼列。
ALLOWED_FILTER_COLUMNS: dict[str, tuple[str, str]] = {
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

_TEXT_ENUM_SETS: dict[str, frozenset[str]] = {
    "grade": frozenset(e.value for e in Grade),
    "question_type": frozenset(e.value for e in QuestionType),
    "section": frozenset(e.value for e in Section),
    "difficulty": frozenset(e.value for e in Difficulty),
    "review_status": frozenset(e.value for e in ReviewStatus),
}

_SOURCE_ABBR_RE = re.compile(r"^[A-Z]+$")
_YEAR_MIN, _YEAR_MAX = 1900, 2100


def _clean_text(values: list[str], enum_key: str) -> list[str]:
    allowed = _TEXT_ENUM_SETS[enum_key]
    return [v for v in values if isinstance(v, str) and v in allowed]


def _clean_years(values: list[str]) -> list[int]:
    out: list[int] = []
    for v in values:
        if not isinstance(v, str):
            continue
        try:
            n = int(v)
        except ValueError:
            continue
        if _YEAR_MIN <= n <= _YEAR_MAX:
            out.append(n)
    return out


def _clean_source_abbrs(values: list[str]) -> list[str]:
    return [v for v in values if isinstance(v, str) and _SOURCE_ABBR_RE.match(v)]


def _coerce_positive_int(value: str | None, default: int) -> int:
    if not isinstance(value, str):
        return default
    try:
        n = int(value)
    except ValueError:
        return default
    return n if n >= 1 else default


def parse_list_query(params: Mapping[str, list[str]]) -> QuestionListQuery:
    """解析并校验 query string，非法值丢弃，缺失项用默认。

    params 由路由层用 ``request.query_params.getlist(key)`` 显式组装为
    ``dict[str, list[str]]`` 后传入；service 不直接依赖 Starlette 类型。
    """
    sort = params.get("sort", ["year_desc"])[0] if params.get("sort") else "year_desc"
    if sort not in ALLOWED_SORTS:
        sort = "year_desc"

    page_raw = params.get("page", ["1"])[0] if params.get("page") else "1"
    page = _coerce_positive_int(page_raw, 1)

    return QuestionListQuery(
        grades=_clean_text(params.get("grade", []), "grade"),
        question_types=_clean_text(params.get("question_type", []), "question_type"),
        sections=_clean_text(params.get("section", []), "section"),
        difficulties=_clean_text(params.get("difficulty", []), "difficulty"),
        years=_clean_years(params.get("year", [])),
        source_abbrs=_clean_source_abbrs(params.get("source_abbr", [])),
        review_statuses=_clean_text(params.get("review_status", []), "review_status"),
        topic_l1s=[v for v in params.get("topic_l1", []) if isinstance(v, str) and v],
        sort=sort,
        page=page,
    )
```

- [ ] **Step 4: 跑测试，预期全过**

Run: `.venv/bin/python -m pytest tests/test_question_service.py -v`
Expected: 14 passed

- [ ] **Step 5: 跑 mypy + ruff**

Run: `.venv/bin/ruff check app/services/question_service.py tests/test_question_service.py`
Run: `.venv/bin/mypy app/services/question_service.py`
Expected: 全部干净

- [ ] **Step 6: 提交**

```bash
git add app/services/question_service.py tests/test_question_service.py
git commit -m "feat(service): question_service 骨架 + parse_list_query 白名单

URL 枚举值走模块级白名单常量，非法值丢弃；
列名 / 排序白名单为后续 SQL 构造做准备。
14 个单元测试覆盖正常路径 + 失败路径。"
```

---

### Task 2: list_questions SQL + 白名单

**Files:**
- Create: `app/services/question_service.py`（追加）
- Test: `tests/test_question_service.py`（追加）

**Interfaces:**
- Consumes: `QuestionListQuery`, `get_connection()`, `app.models.question.QuestionOut`
- Produces: `list_questions(q: QuestionListQuery) -> tuple[list[QuestionOut], int]`

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_question_service.py`：
```python
@pytest.fixture
def seeded_db(tmp_path, monkeypatch):
    """灌入覆盖 7 维度的示例题到临时 db。"""
    import json
    from app.config import Settings
    from app.database import init_schema
    from app.services import question_service

    db = tmp_path / "vault.db"
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    seed_kt = [
        {"id": "kt-num", "name": "数与代数"},
        {"id": "kt-fig", "name": "图形与几何"},
    ]
    (prompts / "knowledge_tree_seed.json").write_text(
        json.dumps(seed_kt, ensure_ascii=False), encoding="utf-8"
    )

    test_settings = Settings(database_path=str(db), prompts_dir=str(prompts))
    monkeypatch.setattr("app.database.settings", test_settings)
    monkeypatch.setattr(question_service, "settings", test_settings)

    init_schema(db_path=db)
    with question_service.get_connection() as conn:
        conn.executemany(
            "INSERT INTO knowledge_tree (id, name) VALUES (?, ?)",
            [("kt-num", "数与代数"), ("kt-fig", "图形与几何")],
        )
        conn.executemany(
            """
            INSERT INTO questions (
                id, stage, grade, question_type, section, source, source_abbr,
                year, review_status, topic_l1, difficulty, stem, answer, solution,
                citation_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("M2024-NCZK-1", "初中", "七年级", "选择题", "数与代数", "测试A", "NCZK",
                 2024, "已入库", "kt-num", "易", "题干1", "答案1", "解析1", 5),
                ("M2024-NCZK-2", "初中", "七年级", "填空题", "数与代数", "测试A", "NCZK",
                 2024, "草稿", "kt-num", "中", "题干2", "答案2", "解析2", 0),
                ("M2024-BJMS-1", "初中", "八年级", "计算题", "图形与几何", "测试B", "BJMS",
                 2024, "已入库", "kt-fig", "难", "题干3", "答案3", "解析3", 12),
                ("M2025-NCZK-3", "初中", "九年级", "证明题", "函数", "测试C", "NCZK",
                 2025, "待审核", "kt-num", "中", "题干4", "答案4", "解析4", 3),
            ],
        )
    return test_settings


def test_list_questions_empty_db(tmp_path, monkeypatch):
    from app.config import Settings
    from app.database import init_schema
    from app.services import question_service

    db = tmp_path / "vault.db"
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    test_settings = Settings(database_path=str(db), prompts_dir=str(prompts))
    monkeypatch.setattr("app.database.settings", test_settings)
    monkeypatch.setattr(question_service, "settings", test_settings)
    init_schema(db_path=db)

    rows, total = question_service.list_questions(question_service.QuestionListQuery())
    assert rows == []
    assert total == 0


def test_list_questions_returns_all_when_no_filter(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery()
    rows, total = question_service.list_questions(q)
    assert total == 4
    assert len(rows) == 4


def test_list_questions_filter_by_grade(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(grades=["七年级"])
    rows, total = question_service.list_questions(q)
    assert total == 2
    assert {r.id for r in rows} == {"M2024-NCZK-1", "M2024-NCZK-2"}


def test_list_questions_multi_value_in(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(grades=["七年级", "八年级"])
    rows, total = question_service.list_questions(q)
    assert total == 3
    assert {r.id for r in rows} == {"M2024-NCZK-1", "M2024-NCZK-2", "M2024-BJMS-1"}


def test_list_questions_filter_by_year(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(years=[2024])
    rows, total = question_service.list_questions(q)
    assert total == 3


def test_list_questions_filter_by_difficulty(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(difficulties=["易"])
    rows, total = question_service.list_questions(q)
    assert total == 1
    assert rows[0].id == "M2024-NCZK-1"


def test_list_questions_filter_by_source_abbr(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(source_abbrs=["BJMS"])
    rows, total = question_service.list_questions(q)
    assert total == 1
    assert rows[0].id == "M2024-BJMS-1"


def test_list_questions_filter_by_topic_l1(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(topic_l1s=["kt-fig"])
    rows, total = question_service.list_questions(q)
    assert total == 1
    assert rows[0].id == "M2024-BJMS-1"


def test_list_questions_filter_by_review_status(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(review_statuses=["已入库"])
    rows, total = question_service.list_questions(q)
    assert total == 2


def test_list_questions_combined_filters(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(
        grades=["七年级"], review_statuses=["已入库"]
    )
    rows, total = question_service.list_questions(q)
    assert total == 1
    assert rows[0].id == "M2024-NCZK-1"


def test_list_questions_sort_year_desc(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(sort="year_desc")
    rows, _ = question_service.list_questions(q)
    years = [r.year for r in rows]
    assert years == sorted(years, reverse=True)


def test_list_questions_sort_id_asc(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(sort="id_asc")
    rows, _ = question_service.list_questions(q)
    ids = [r.id for r in rows]
    assert ids == sorted(ids)


def test_list_questions_sort_citation_desc(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(sort="citation_desc")
    rows, _ = question_service.list_questions(q)
    citations = [r.citation_count for r in rows]
    assert citations == sorted(citations, reverse=True)


def test_list_questions_pagination(seeded_db):
    from app.services import question_service

    q1 = question_service.QuestionListQuery(page=1, page_size=2)
    rows1, total1 = question_service.list_questions(q1)
    assert total1 == 4
    assert len(rows1) == 2

    q2 = question_service.QuestionListQuery(page=2, page_size=2)
    rows2, _ = question_service.list_questions(q2)
    assert len(rows2) == 2

    ids1 = {r.id for r in rows1}
    ids2 = {r.id for r in rows2}
    assert ids1.isdisjoint(ids2)


def test_list_questions_pagination_out_of_range(seeded_db):
    from app.services import question_service

    q = question_service.QuestionListQuery(page=99, page_size=2)
    rows, total = question_service.list_questions(q)
    assert rows == []
    assert total == 4


def test_list_questions_safety_sql_injection_attempt(seeded_db):
    """SQL 注入：非法 topic_l1 已在 parse_list_query 丢弃；list 不应崩。"""
    from app.services import question_service

    q = question_service.QuestionListQuery(topic_l1s=["'; DROP TABLE questions; --"])
    rows, total = question_service.list_questions(q)
    assert total == 0
    # 验证表还存在
    with question_service.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 4
```

注意：测试代码里 `from app.services import question_service` 后通过 `monkeypatch.setattr(question_service, "settings", ...)` 改 service 自身的 settings 全局变量。service 用 `from .config import settings` 读 `settings.db_path`（与 database.py 一致），由测试用 monkeypatch 改 question_service.settings 切到 tmp db。

- [ ] **Step 2: 跑测试，预期失败**

Run: `.venv/bin/python -m pytest tests/test_question_service.py -v -k "list_questions"`
Expected: AttributeError: module 'app.services.question_service' has no attribute 'list_questions'

- [ ] **Step 3: 实现 list_questions**

追加到 `app/services/question_service.py`：
```python
from app.config import settings
from app.database import get_connection
from app.models.question import QuestionOut


def _build_where_clause(q: QuestionListQuery) -> tuple[str, list]:
    """构造 WHERE 子句（不包含 1=1）和对应参数。"""
    clauses: list[str] = []
    args: list = []

    # URL 参数 -> (列名, "text"/"int")
    text_filters: list[tuple[str, list[str]]] = [
        ("grade", q.grades),
        ("question_type", q.question_types),
        ("section", q.sections),
        ("difficulty", q.difficulties),
        ("source_abbr", q.source_abbrs),
        ("review_status", q.review_statuses),
        ("topic_l1", q.topic_l1s),
    ]
    for param_key, values in text_filters:
        if not values:
            continue
        col, _ = ALLOWED_FILTER_COLUMNS[param_key]
        placeholders = ",".join("?" * len(values))
        clauses.append(f"{col} IN ({placeholders})")
        args.extend(values)

    if q.years:
        placeholders = ",".join("?" * len(q.years))
        clauses.append(f"year IN ({placeholders})")
        args.extend(q.years)

    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where_sql, args


def list_questions(q: QuestionListQuery) -> tuple[list[QuestionOut], int]:
    """返回 (本页 rows, 总数)；page 越界返回 ([], total)。"""
    where_sql, where_args = _build_where_clause(q)
    order_sql = ALLOWED_SORTS.get(q.sort, ALLOWED_SORTS["year_desc"])
    offset = (q.page - 1) * q.page_size

    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM questions {where_sql}", where_args
        ).fetchone()[0]
        if total == 0 or offset >= total:
            return [], total
        rows = conn.execute(
            f"SELECT * FROM questions {where_sql} ORDER BY {order_sql} "
            f"LIMIT ? OFFSET ?",
            [*where_args, q.page_size, offset],
        ).fetchall()

    return [QuestionOut.model_validate(dict(r)) for r in rows], total
```

- [ ] **Step 4: 跑测试，预期全过**

Run: `.venv/bin/python -m pytest tests/test_question_service.py -v`
Expected: 31 passed（14 旧 + 17 新）

- [ ] **Step 5: 跑 mypy + ruff**

Run: `.venv/bin/ruff check app/services/question_service.py tests/test_question_service.py`
Run: `.venv/bin/mypy app/services/question_service.py`
Expected: 干净

- [ ] **Step 6: 提交**

```bash
git add app/services/question_service.py tests/test_question_service.py
git commit -m "feat(service): list_questions SQL + 白名单 + 注入回归

列名 / 排序从白名单常量取，参数化绑定；
WHERE 片段生成器被 list + count 共用保证一致。
17 个测试覆盖：空库 / 单条件 / 多值 IN / 排序 / 分页 / 越界 / SQL 注入。"
```

---

### Task 3: get_question_detail + list_topic_l1_choices

**Files:**
- Create: `app/services/question_service.py`（追加）
- Test: `tests/test_question_service.py`（追加）

**Interfaces:**
- Produces:
  - `get_question_detail(id: str) -> QuestionOut`
  - `list_topic_l1_choices() -> list[tuple[str, str]]` — 返回 `[(id, name), ...]`

- [ ] **Step 1: 写失败测试**

追加：
```python
def test_get_question_detail_found(seeded_db):
    from app.services import question_service

    q = question_service.get_question_detail("M2024-NCZK-1")
    assert q.id == "M2024-NCZK-1"
    assert q.stem == "题干1"
    assert q.grade == "七年级"


def test_get_question_detail_not_found_raises(seeded_db):
    from app.services import question_service

    with pytest.raises(question_service.QuestionNotFoundError):
        question_service.get_question_detail("M2099-NOPE-1")


def test_get_question_detail_invalid_id_raises(seeded_db):
    from app.services import question_service

    with pytest.raises(question_service.QuestionNotFoundError):
        question_service.get_question_detail("not-a-valid-id")


def test_list_topic_l1_choices(seeded_db):
    from app.services import question_service

    choices = question_service.list_topic_l1_choices()
    assert ("kt-num", "数与代数") in choices
    assert ("kt-fig", "图形与几何") in choices
    assert len(choices) == 2


def test_list_topic_l1_choices_empty_db(tmp_path, monkeypatch):
    from app.config import Settings
    from app.database import init_schema
    from app.services import question_service

    db = tmp_path / "vault.db"
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    test_settings = Settings(database_path=str(db), prompts_dir=str(prompts))
    monkeypatch.setattr("app.database.settings", test_settings)
    monkeypatch.setattr(question_service, "settings", test_settings)
    init_schema(db_path=db)
    assert question_service.list_topic_l1_choices() == []
```

- [ ] **Step 2: 跑测试，预期失败**

Run: `.venv/bin/python -m pytest tests/test_question_service.py -v -k "topic_l1_choices or question_detail"`
Expected: AttributeError: no attribute 'get_question_detail' / 'list_topic_l1_choices'

- [ ] **Step 3: 实现两个函数**

追加到 `app/services/question_service.py`：
```python
import re as _re

_QUESTION_ID_RE = _re.compile(r"^M\d{4}-[A-Z]+-\d+$")


def get_question_detail(id: str) -> QuestionOut:
    """返回题目详情；不存在或 ID 不合法均抛 QuestionNotFoundError。"""
    if not isinstance(id, str) or not _QUESTION_ID_RE.match(id):
        raise QuestionNotFoundError(id)
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM questions WHERE id = ?", (id,)).fetchone()
    if row is None:
        raise QuestionNotFoundError(id)
    return QuestionOut.model_validate(dict(row))


def list_topic_l1_choices() -> list[tuple[str, str]]:
    """返回 (id, name) 列表，仅 parent_id IS NULL 的顶层节点。"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name FROM knowledge_tree "
            "WHERE parent_id IS NULL ORDER BY sort_order, name"
        ).fetchall()
    return [(r["id"], r["name"]) for r in rows]
```

- [ ] **Step 4: 跑测试，预期全过**

Run: `.venv/bin/python -m pytest tests/test_question_service.py -v`
Expected: 36 passed

- [ ] **Step 5: 跑 mypy + ruff**

Run: `.venv/bin/ruff check app/services/question_service.py tests/test_question_service.py`
Run: `.venv/bin/mypy app/services/question_service.py`
Expected: 干净

- [ ] **Step 6: 提交**

```bash
git add app/services/question_service.py tests/test_question_service.py
git commit -m "feat(service): get_question_detail + list_topic_l1_choices

get_question_detail 非法 ID 与不存在都走 QuestionNotFoundError，
路由层映射 404，避免泄露 ID 形态。"
```

---

### Task 4: routers/questions.py 路由

**Files:**
- Create: `app/routers/questions.py`
- Modify: `app/main.py`
- Test: `tests/test_questions_router.py`

**Interfaces:**
- Consumes: `question_service`, `app.templates`（Jinja2Templates 实例）
- Produces: APIRouter 注册到 `app.main.app`，含两个 GET 端点

- [ ] **Step 1: 写失败测试**

`tests/test_questions_router.py`：
```python
"""questions 路由集成测试。"""
from __future__ import annotations


def test_list_questions_default_returns_html(client):
    r = client.get("/questions")
    assert r.status_code == 200
    body = r.text
    assert "<html" in body
    assert "题库浏览" in body
    assert '<select' in body


def test_list_questions_with_filter(client):
    r = client.get("/questions?grade=七年级")
    assert r.status_code == 200
    body = r.text
    # 行要么存在（七年级匹配），要么是空状态
    assert ("M2024-NCZK-1" in body) or ("无匹配题目" in body)


def test_list_questions_htmx_returns_fragment(client):
    r = client.get(
        "/questions", headers={"HX-Request": "true"}
    )
    assert r.status_code == 200
    body = r.text
    assert "<html" not in body  # 片段不含 html


def test_list_questions_non_htmx_returns_full_page(client):
    r = client.get("/questions")
    assert "<html" in r.text


def test_list_questions_illegal_param_does_not_crash(client):
    r = client.get("/questions?grade=六年级&year=99999")
    assert r.status_code == 200


def test_list_questions_pagination_param(client):
    r = client.get("/questions?page=1")
    assert r.status_code == 200


def test_detail_question_found(client):
    r = client.get("/questions/M2024-NCZK-1")
    assert r.status_code == 200
    body = r.text
    assert "题干1" in body
    assert "答案1" in body
    assert "解析1" in body


def test_detail_question_not_found_returns_404(client):
    r = client.get("/questions/M2099-NOPE-1")
    assert r.status_code == 404


def test_detail_question_invalid_id_returns_404(client):
    r = client.get("/questions/not-a-valid-id")
    assert r.status_code == 404


def test_detail_question_back_link(client):
    r = client.get("/questions/M2024-NCZK-1")
    assert r.status_code == 200
    assert "/questions" in r.text  # 返回列表链接
```

需要在 `tests/conftest.py` 加 `_seed_questions_for_router` fixture：4-5 道覆盖数据。本测试用现有 `client` fixture（`isolated_settings` 驱动），并通过 service 接口在 client 创建后立刻灌种子。

**重要**：client fixture 在 P0 是 `init_schema` 后 yield，不灌种子。需要在 client fixture 内部 / 测试内灌入。

为简化，让 `client` fixture 自动灌入 4 道题——但这会破坏其他测试。改在 `test_questions_router.py` 文件级用 `pytest.fixture(autouse=True)` 自动调用一个 conftest helper。

具体做法：在 `tests/conftest.py` 加 fixture：
```python
@pytest.fixture
def client_with_questions(isolated_settings, monkeypatch):
    """client 的扩展版，自动灌入 4 道覆盖数据。"""
    from app import config as config_module
    from app import database as database_module
    from app import logging_config as logging_module
    from app import main as main_module
    import importlib

    monkeypatch.setattr(config_module, "settings", isolated_settings)
    importlib.reload(database_module)
    importlib.reload(logging_module)
    importlib.reload(main_module)
    logging_module.configure(log_dir=isolated_settings.db_path.parent, level="WARNING")
    database_module.init_schema(db_path=isolated_settings.db_path)

    with database_module.get_connection() as conn:
        conn.executemany(
            "INSERT INTO knowledge_tree (id, name) VALUES (?, ?)",
            [("kt-num", "数与代数"), ("kt-fig", "图形与几何")],
        )
        conn.executemany(
            """INSERT INTO questions (
                id, stage, grade, question_type, section, source, source_abbr,
                year, review_status, topic_l1, difficulty, stem, answer, solution
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                ("M2024-NCZK-1", "初中", "七年级", "选择题", "数与代数", "测试A", "NCZK",
                 2024, "已入库", "kt-num", "易", "题干1", "答案1", "解析1"),
                ("M2024-NCZK-2", "初中", "七年级", "填空题", "数与代数", "测试A", "NCZK",
                 2024, "草稿", "kt-num", "中", "题干2", "答案2", "解析2"),
                ("M2024-BJMS-1", "初中", "八年级", "计算题", "图形与几何", "测试B", "BJMS",
                 2024, "已入库", "kt-fig", "难", "题干3", "答案3", "解析3"),
            ],
        )

    from fastapi.testclient import TestClient
    with TestClient(main_module.app) as c:
        yield c
```

`tests/test_questions_router.py` 用 `client_with_questions` 替换 `client`。

- [ ] **Step 2: 跑测试，预期失败（router 不存在）**

Run: `.venv/bin/python -m pytest tests/test_questions_router.py -v`
Expected: 全部失败（路由 404）

- [ ] **Step 3: 实现 router**

`app/routers/questions.py`：
```python
"""题目路由：列表 + 详情。

- GET /questions：URL 同步筛选 + 分页 + 排序，HTMX 局部刷新
- GET /questions/{id}：详情页（404 走全局异常处理）
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.config import TEMPLATES_DIR
from app.services import question_service
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["questions"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _build_params(request: Request) -> dict[str, list[str]]:
    """组装 query_params 为 dict[str, list[str]]。"""
    qp = request.query_params
    keys = {"grade", "question_type", "section", "difficulty", "year",
            "source_abbr", "review_status", "topic_l1", "sort", "page"}
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
    except question_service.QuestionNotFoundError:
        raise HTTPException(status_code=404, detail="题目不存在")
    return templates.TemplateResponse(
        "questions/detail.html", {"request": request, "q": q}
    )
```

- [ ] **Step 4: 注册 router 到 main.py**

修改 `app/main.py`：在 `install_exception_handlers(app)` 后加：
```python
from .routers import questions as questions_router  # noqa: E402

app.include_router(questions_router.router)
```

- [ ] **Step 5: 跑测试，预期部分过 + 部分因模板缺失失败**

Run: `.venv/bin/python -m pytest tests/test_questions_router.py -v`
Expected: 全部失败（TemplateNotFound: questions/list.html 等）

- [ ] **Step 6: 提交 router 骨架**

```bash
git add app/routers/questions.py app/main.py tests/conftest.py tests/test_questions_router.py
git commit -m "feat(router): questions 路由骨架 + 测试桩

list/detail 端点 + HTMX 头识别 + 404 映射。
模板待 Task 5-7 补全；本提交仅路由层骨架。"
```

---

### Task 5: base.html 加 htmx + block + nav

**Files:**
- Modify: `app/templates/base.html`

- [ ] **Step 1: 修改 base.html**

读 `app/templates/base.html`，做三处增量改动：

1. 在 `<script defer src="...katex...auto-render..."></script>` 之后加：
```html
<script defer src="https://unpkg.com/htmx.org@1.9.10"></script>
{% block extra_head %}{% endblock %}
```

2. 把 `<main class="max-w-6xl mx-auto px-6 py-10">` 后的整段 `<section>` 替换为：
```html
{% block content %}
<section class="bg-white rounded-lg border border-slate-200 p-8">
  <h2 class="text-lg font-semibold mb-3">项目骨架已就位</h2>
  <p class="text-slate-600 mb-6">
    本页面由 <code class="px-1 py-0.5 bg-slate-100 rounded">app/main.py</code> 渲染，
    Tailwind / KaTeX 已通过 CDN 注入，后续阶段在此添加题目浏览、组卷与统计模块。
  </p>
  <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
    <div class="border border-slate-200 rounded p-4">
      <p class="text-slate-500">数据存储</p>
      <p class="font-medium">SQLite · vault.db</p>
    </div>
    <div class="border border-slate-200 rounded p-4">
      <p class="text-slate-500">后端框架</p>
      <p class="font-medium">FastAPI + Jinja2</p>
    </div>
    <div class="border border-slate-200 rounded p-4">
      <p class="text-slate-500">交互栈</p>
      <p class="font-medium">HTMX + Alpine.js（待接入）</p>
    </div>
  </div>
</section>
{% endblock %}
```

3. 在 `</footer>` 之前加 `{% block scripts %}{% endblock %}`。

4. 顶部 `<nav>` 现有 3 个链接后加：
```html
<a href="/questions" class="hover:text-slate-900">题库浏览</a>
```

- [ ] **Step 2: 跑测试，验证首页不破**

Run: `.venv/bin/python -m pytest -q`
Expected: 36 passed（router 10 个仍因模板失败，**忽略**因为模板还没建）— 此时只检查不破现有。实际只跑 `tests/test_main.py`：
Run: `.venv/bin/python -m pytest tests/test_main.py -v`
Expected: 7 passed

- [ ] **Step 3: 提交**

```bash
git add app/templates/base.html
git commit -m "feat(template): base.html 加 htmx CDN + content/scripts block + 题库 nav

不影响 P0 首页（默认 content 保留）；后续模板继承并填充 block。"
```

---

### Task 6: list + filters + table + pagination 模板

**Files:**
- Create: `app/templates/questions/list.html`
- Create: `app/templates/questions/_filters.html`
- Create: `app/templates/questions/_table.html`
- Create: `app/templates/questions/_pagination.html`

- [ ] **Step 1: _filters.html**

```html
{# 7 个多选 + 1 个排序 + 清空按钮。参数名与 question_service.ALLOWED_FILTER_COLUMNS 一致。 #}
<form id="filters" class="space-y-4 text-sm"
      hx-get="/questions" hx-target="#q-table" hx-trigger="change" hx-push-url="true">
  <div>
    <label class="block text-slate-500 mb-1">排序</label>
    <select name="sort" class="w-full border border-slate-200 rounded px-2 py-1 bg-white">
      <option value="year_desc" {% if query.sort == "year_desc" %}selected{% endif %}>年份（倒序）</option>
      <option value="id_asc" {% if query.sort == "id_asc" %}selected{% endif %}>ID（升序）</option>
      <option value="citation_desc" {% if query.sort == "citation_desc" %}selected{% endif %}>引用次数（降序）</option>
    </select>
  </div>

  {% set multi_filters = [
    ("grade", "年级", ["七年级", "八年级", "九年级"]),
    ("question_type", "题型", ["选择题", "填空题", "计算题", "证明题", "作图题", "应用题", "探究题", "综合题"]),
    ("section", "板块", ["数与代数", "图形与几何", "函数", "统计与概率", "综合与实践", "课题学习"]),
    ("difficulty", "难度", ["易", "中", "难"]),
    ("review_status", "状态", ["草稿", "待审核", "已入库"]),
  ] %}
  {% for key, label, opts in multi_filters %}
  <div>
    <label class="block text-slate-500 mb-1">{{ label }}</label>
    <select name="{{ key }}" multiple size="3" class="w-full border border-slate-200 rounded px-2 py-1 bg-white">
      {% for v in opts %}
      <option value="{{ v }}" {% if v in params.get(key, []) %}selected{% endif %}>{{ v }}</option>
      {% endfor %}
    </select>
  </div>
  {% endfor %}

  <div>
    <label class="block text-slate-500 mb-1">年份（每行一个）</label>
    <input type="text" name="year" placeholder="2024"
           value="{{ params.get('year', [''])[0] }}"
           class="w-full border border-slate-200 rounded px-2 py-1">
    <p class="text-xs text-slate-400 mt-1">多值用 &amp;year=2024&amp;year=2025</p>
  </div>
  <div>
    <label class="block text-slate-500 mb-1">来源缩写（每行一个）</label>
    <input type="text" name="source_abbr" placeholder="NCZK"
           value="{{ params.get('source_abbr', [''])[0] }}"
           class="w-full border border-slate-200 rounded px-2 py-1">
  </div>
  <div>
    <label class="block text-slate-500 mb-1">知识点（一级）</label>
    <select name="topic_l1" multiple size="3" class="w-full border border-slate-200 rounded px-2 py-1 bg-white">
      {% for kt_id, kt_name in topic_choices %}
      <option value="{{ kt_id }}" {% if kt_id in params.get('topic_l1', []) %}selected{% endif %}>{{ kt_name }}</option>
      {% endfor %}
    </select>
  </div>
  <a href="/questions" class="inline-block px-3 py-1 text-xs text-slate-500 hover:text-slate-900 border border-slate-200 rounded">清空筛选</a>
</form>
```

注：年份/来源用 `<input type="text">` + 服务端用 `repeat key` 风格时，HTMX 不会把单个 input 的多值带过去。考虑在 hx-include 后还需用户手动加 `&year=2024&year=2025` 才多值。但**实际接口契约是 repeat key**。为 UX 友好，本期 `<input>` 取首个值；如需多值，将来加 `[name="year"]` 重复控件。此简化与 spec 6.5 一致（多选用 select）。

- [ ] **Step 2: _table.html**

```html
{# 表格片段，被 HTMX 刷入 #q-table。行点击跳详情。 #}
<div id="q-table">
  <div class="text-xs text-slate-500 mb-2">共 {{ total }} 条 · 第 {{ query.page }} / {{ page_total }} 页</div>
  <div class="overflow-x-auto border border-slate-200 rounded">
    <table class="min-w-full text-sm">
      <thead class="bg-slate-50 text-slate-500">
        <tr>
          <th class="px-3 py-2 text-left">ID</th>
          <th class="px-3 py-2 text-left">题型</th>
          <th class="px-3 py-2 text-left">难度</th>
          <th class="px-3 py-2 text-left">年级</th>
          <th class="px-3 py-2 text-left">板块</th>
          <th class="px-3 py-2 text-left">年份</th>
          <th class="px-3 py-2 text-left">来源</th>
          <th class="px-3 py-2 text-right">引用</th>
          <th class="px-3 py-2 text-left">操作</th>
        </tr>
      </thead>
      <tbody>
        {% if rows %}
        {% for q in rows %}
        <tr style="cursor:pointer" onclick="window.location='/questions/{{ q.id }}'" class="border-t border-slate-100 hover:bg-slate-50">
          <td class="px-3 py-2 font-mono text-xs">{{ q.id }}</td>
          <td class="px-3 py-2">{{ q.question_type or '—' }}</td>
          <td class="px-3 py-2">{{ q.difficulty or '—' }}</td>
          <td class="px-3 py-2">{{ q.grade or '—' }}</td>
          <td class="px-3 py-2">{{ q.section or '—' }}</td>
          <td class="px-3 py-2">{{ q.year or '—' }}</td>
          <td class="px-3 py-2">{{ q.source or '—' }}</td>
          <td class="px-3 py-2 text-right">{{ q.citation_count }}</td>
          <td class="px-3 py-2"><a href="/questions/{{ q.id }}" class="text-blue-600 hover:underline">查看</a></td>
        </tr>
        {% endfor %}
        {% else %}
        <tr><td colspan="9" class="px-3 py-6 text-center text-slate-400">无匹配题目</td></tr>
        {% endif %}
      </tbody>
    </table>
  </div>
  {% include "questions/_pagination.html" %}
</div>
```

- [ ] **Step 3: _pagination.html**

```html
{# 分页片段。URL 保留当前所有筛选参数。 #}
{% set qs = [] %}
{% for key, values in params.items() %}
  {% for v in values %}
    {% set _ = qs.append("~s=%s&%s=%s" % ('', key, v)) %}
  {% endfor %}
{% endfor %}
{% set raw = qs | join('&') %}
{# raw 形如 "&grade=七年级&grade=八年级" #}
{% set prev_q = raw %}
{% set next_q = raw %}

<div class="flex justify-between items-center mt-3 text-xs text-slate-500">
  <a href="/questions?page=1{{ prev_q }}"
     class="px-2 py-1 border border-slate-200 rounded hover:bg-slate-50">首页</a>
  <div>
    {% if query.page > 1 %}
    <a href="/questions?page={{ query.page - 1 }}{{ prev_q }}"
       class="px-2 py-1 border border-slate-200 rounded hover:bg-slate-50">上一页</a>
    {% endif %}
    <span class="mx-2">{{ query.page }} / {{ page_total }}</span>
    {% if query.page < page_total %}
    <a href="/questions?page={{ query.page + 1 }}{{ next_q }}"
       class="px-2 py-1 border border-slate-200 rounded hover:bg-slate-50">下一页</a>
    {% endif %}
  </div>
  <a href="/questions?page={{ page_total }}{{ next_q }}"
     class="px-2 py-1 border border-slate-200 rounded hover:bg-slate-50">末页</a>
</div>
```

- [ ] **Step 4: list.html**

```html
{% extends "base.html" %}
{% block title %}题库浏览 · MathForge{% endblock %}
{% block content %}
<h1 class="text-xl font-semibold mb-6">题库浏览</h1>
<div class="grid grid-cols-1 md:grid-cols-4 gap-6">
  <aside class="md:col-span-1 bg-white border border-slate-200 rounded p-4">
    {% include "questions/_filters.html" %}
  </aside>
  <section class="md:col-span-3">
    <div id="q-table"
         hx-get="/questions" hx-trigger="load once" hx-swap="outerHTML">
      {% include "questions/_table.html" %}
    </div>
  </section>
</div>
{% endblock %}
```

- [ ] **Step 5: 跑 router 测试，预期全过**

Run: `.venv/bin/python -m pytest tests/test_questions_router.py -v`
Expected: 10 passed

- [ ] **Step 6: 跑全套验证**

Run: `.venv/bin/python -m pytest -q`
Run: `.venv/bin/ruff check .`
Run: `.venv/bin/mypy app/`
Expected: 46 passed，ruff 干净，mypy 干净

- [ ] **Step 7: 提交**

```bash
git add app/templates/questions/
git commit -m "feat(template): 列表 / 筛选 / 表格 / 分页 模板

URL 同步多选筛选 + HTMX 局部刷新 #q-table 容器；
分页保留当前筛选参数；行点击跳详情。"
```

---

### Task 7: detail 模板

**Files:**
- Create: `app/templates/questions/detail.html`

- [ ] **Step 1: 创建 detail.html**

```html
{% extends "base.html" %}
{% block title %}{{ q.id }} · {{ q.question_type or '题目' }} · MathForge{% endblock %}
{% block content %}
<nav class="text-sm text-slate-500 mb-4">
  <a href="/questions" class="hover:text-slate-900">← 返回题库浏览</a>
</nav>
<article class="bg-white border border-slate-200 rounded p-6 space-y-6">
  <header>
    <h1 class="text-lg font-semibold font-mono">{{ q.id }}</h1>
    <p class="text-sm text-slate-500 mt-1">
      {{ q.question_type or '—' }} · {{ q.difficulty or '—' }} · {{ q.year or '—' }} · {{ q.source or '—' }}
    </p>
  </header>

  <section>
    <h2 class="text-base font-semibold mb-2">题干</h2>
    <div class="prose prose-slate max-w-none">{{ q.stem or '（无）' }}</div>
  </section>
  <section>
    <h2 class="text-base font-semibold mb-2">答案</h2>
    <div class="prose prose-slate max-w-none">{{ q.answer or '（无）' }}</div>
  </section>
  <section>
    <h2 class="text-base font-semibold mb-2">解析</h2>
    <div class="prose prose-slate max-w-none">{{ q.solution or '（无）' }}</div>
  </section>

  <section>
    <h2 class="text-base font-semibold mb-2">元数据</h2>
    <dl class="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-2 text-sm">
      {% set rows = [
        ("学段", q.stage), ("年级", q.grade), ("板块", q.section),
        ("知识点 l1", q.topic_l1), ("知识点 l2", q.topic_l2),
        ("考查角度", q.angle), ("来源", q.source), ("来源缩写", q.source_abbr),
        ("年份", q.year), ("是否真题", "是" if q.is_exam_question else "否"),
        ("审核状态", q.review_status), ("题号", q.question_number), ("分值", q.score),
        ("引用次数", q.citation_count), ("关联试卷", q.paper_id), ("关联大题", q.passage_id),
      ] %}
      {% for label, val in rows %}
      <div class="flex">
        <dt class="w-28 text-slate-500">{{ label }}</dt>
        <dd class="flex-1">{{ val if val is not none else '—' }}</dd>
      </div>
      {% endfor %}
      <div class="flex">
        <dt class="w-28 text-slate-500">核心素养</dt>
        <dd class="flex-1">{{ q.core_literacy or '—' }}</dd>
      </div>
      <div class="flex">
        <dt class="w-28 text-slate-500">布鲁姆层级</dt>
        <dd class="flex-1">{{ q.bloom_level or '—' }}</dd>
      </div>
    </dl>
  </section>
</article>
{% endblock %}
```

- [ ] **Step 2: 跑 router 测试**

Run: `.venv/bin/python -m pytest tests/test_questions_router.py -v`
Expected: 10 passed

- [ ] **Step 3: 跑全套验证**

Run: `.venv/bin/python -m pytest -q`
Run: `.venv/bin/ruff check .`
Run: `.venv/bin/mypy app/`
Expected: 46 passed, 干净

- [ ] **Step 4: 提交**

```bash
git add app/templates/questions/detail.html
git commit -m "feat(template): 题目详情模板

题干 / 答案 / 解析 + 元数据双列表；
KaTeX 由 base.html auto-render 处理。"
```

---

### Task 8: app.js KaTeX 重渲染

**Files:**
- Modify: `app/static/js/app.js`

- [ ] **Step 1: 读 app.js 看现状**

```js
// 后续阶段在此挂载 Alpine.js 组件、HTMX 行为、KaTeX 自动渲染
```

- [ ] **Step 2: 替换内容**

```js
// HTMX + KaTeX 集成：局部刷新后重新渲染公式
document.addEventListener("htmx:afterSwap", function (event) {
  if (typeof renderMathInElement === "function") {
    renderMathInElement(event.target, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "$", right: "$", display: false },
      ],
    });
  }
});
```

- [ ] **Step 3: 验证手动**

`python run.py` → 浏览器 `/questions` → 切换筛选项 → 表格无刷更新。

- [ ] **Step 4: 提交**

```bash
git add app/static/js/app.js
git commit -m "feat(js): htmx:afterSwap 钩 KaTeX 重渲染

HTMX 局部刷新后对刷入容器重新触发 auto-render，
保证 detail 页与 list 内嵌公式都正常显示。"
```

---

### Task 9: 示例题种子 demo_seed

**Files:**
- Create: `app/services/demo_seed.py`
- Modify: `scripts/init_db.py`
- Test: `tests/test_demo_seed.py`
- Modify: `tests/test_init_db.py`

**Interfaces:**
- Produces: `seed_demo_questions() -> int` — 返回写入条数；已存在时跳过

- [ ] **Step 1: 写失败测试**

`tests/test_demo_seed.py`：
```python
"""示例题种子测试。"""
from __future__ import annotations

import pytest


@pytest.fixture
def empty_db(tmp_path, monkeypatch):
    from app.config import Settings
    from app.database import init_schema
    from app.services import demo_seed

    db = tmp_path / "vault.db"
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    test_settings = Settings(database_path=str(db), prompts_dir=str(prompts))
    monkeypatch.setattr("app.database.settings", test_settings)
    monkeypatch.setattr(demo_seed, "settings", test_settings)
    init_schema(db_path=db)

    # 灌入与 demo_seed 关联的 knowledge_tree 顶层节点
    from app.services import question_service
    with question_service.get_connection() as conn:
        conn.executemany(
            "INSERT INTO knowledge_tree (id, name) VALUES (?, ?)",
            [
                ("kt-num", "数与代数"),
                ("kt-fig", "图形与几何"),
                ("kt-func", "函数"),
                ("kt-stat", "统计与概率"),
            ],
        )
    return test_settings


def test_seed_demo_questions_returns_count(empty_db):
    from app.services import demo_seed

    n = demo_seed.seed_demo_questions()
    assert n > 0
    assert n >= 20  # 设计要求约 25


def test_seed_demo_questions_idempotent(empty_db):
    from app.services import demo_seed
    from app.services import question_service

    n1 = demo_seed.seed_demo_questions()
    n2 = demo_seed.seed_demo_questions()
    assert n1 > 0
    assert n2 == 0  # 已存在时跳过
    with question_service.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == n1


def test_seed_demo_questions_covers_dimensions(empty_db):
    from app.services import demo_seed
    from app.services import question_service

    demo_seed.seed_demo_questions()
    with question_service.get_connection() as conn:
        grades = {r[0] for r in conn.execute(
            "SELECT DISTINCT grade FROM questions WHERE grade IS NOT NULL"
        ).fetchall()}
        years = {r[0] for r in conn.execute(
            "SELECT DISTINCT year FROM questions WHERE year IS NOT NULL"
        ).fetchall()}
    assert "七年级" in grades
    assert "八年级" in grades
    assert "九年级" in grades
    assert len(years) >= 3
```

- [ ] **Step 2: 跑测试，预期失败**

Run: `.venv/bin/python -m pytest tests/test_demo_seed.py -v`
Expected: ImportError

- [ ] **Step 3: 实现 demo_seed.py**

`app/services/demo_seed.py`：
```python
"""示例题种子：约 25 道题覆盖 7 维度。

仅供开发演示；与 P4 录入流程无关。已存在 questions 时不重复灌入。
"""
from __future__ import annotations

from app.config import settings
from app.database import get_connection

_DEMO_QUESTIONS: list[tuple] = [
    # (id, grade, question_type, section, source, source_abbr, year, review_status,
    #  topic_l1, difficulty, citation_count, stem, answer, solution)
    ("M2024-NCZK-1", "七年级", "选择题", "数与代数", "2024 年初中学业水平测试", "NCZK", 2024, "已入库",
     "kt-num", "易", 8, "已知 $x=2$，求 $x^2-3x+1$ 的值。", "$-1$",
     "代入 $x=2$ 得 $4-6+1=-1$。"),
    ("M2024-NCZK-2", "七年级", "填空题", "数与代数", "2024 年初中学业水平测试", "NCZK", 2024, "已入库",
     "kt-num", "中", 5, "化简 $3a-2(a-b)$。", "$a+2b$",
     "去括号得 $3a-2a+2b=a+2b$。"),
    ("M2024-NCZK-3", "八年级", "计算题", "图形与几何", "2024 年初中学业水平测试", "NCZK", 2024, "已入库",
     "kt-fig", "难", 3, "在 $\\triangle ABC$ 中，$\\angle A=60\\degree$，$\\angle B=70\\degree$，求 $\\angle C$。",
     "$50\\degree$", "三角形内角和 $180\\degree$，故 $\\angle C=180-60-70=50$。"),
    # ... 至少 25 道；为节省 plan 长度，剩余 22 道按相同模式在实现时补全
]


def seed_demo_questions() -> int:
    """灌入示例题到 questions 表。已存在任何题则跳过。返回本次新增条数。"""
    with get_connection() as conn:
        existing = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        if existing:
            return 0
        conn.executemany(
            """
            INSERT INTO questions (
                id, stage, grade, question_type, section, source, source_abbr,
                year, review_status, topic_l1, difficulty, stem, answer, solution,
                citation_count
            ) VALUES (?, '初中', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _DEMO_QUESTIONS,
        )
    return len(_DEMO_QUESTIONS)
```

**实现约束**：`_DEMO_QUESTIONS` 必须补足到 ≥ 25 条；确保 7 维度全覆盖。

- [ ] **Step 4: 跑测试，预期全过**

Run: `.venv/bin/python -m pytest tests/test_demo_seed.py -v`
Expected: 3 passed

- [ ] **Step 5: init_db.py 加 --demo**

修改 `scripts/init_db.py`：
- `--demo` argument
- 路由到 `seed_demo_questions()`

- [ ] **Step 6: tests/test_init_db.py 加 demo 集成测试**

追加：
```python
def test_main_demo_seeds_questions(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["init_db.py", "--reset", "--yes", "--demo"])
    from scripts import init_db as init_db_module

    from app.config import Settings
    test_settings = Settings(
        database_path=str(tmp_path / "vault.db"),
        prompts_dir=str(tmp_path / "prompts"),
    )
    (tmp_path / "prompts").mkdir()
    monkeypatch.setattr(init_db_module, "settings", test_settings)
    monkeypatch.setattr("app.database.settings", test_settings)

    init_db_module.main()
    from app.services import question_service
    with question_service.get_connection() as conn:
        n = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    assert n > 0
```

- [ ] **Step 7: 跑全套验证**

Run: `.venv/bin/python -m pytest -q`
Run: `.venv/bin/ruff check .`
Run: `.venv/bin/mypy app/`
Expected: 50+ passed，干净

- [ ] **Step 8: 提交**

```bash
git add app/services/demo_seed.py scripts/init_db.py tests/test_demo_seed.py tests/test_init_db.py
git commit -m "feat(seed): 示例题种子 demo_seed + init_db --demo

约 25 道题覆盖 7 维度；
init_db.py --demo 选项；
幂等：已存在 questions 不重复灌入。
3 个种子测试 + 1 个 init_db 集成测试。"
```

---

### Task 10: AGENTS / PROGRESS / README 同步

**Files:**
- Modify: `AGENTS.md`
- Modify: `PROGRESS.md`
- Modify: `README.md`

- [ ] **Step 1: AGENTS.md 阶段范围更新**

把：
```
- **P0**（完成）：...
- **P1**（下一个）：浏览筛选 + 题目详情（HTMX 无刷新）
```
改为：
```
- **P0**（完成）：...
- **P1**（完成）：浏览筛选 + 题目详情（HTMX 无刷新）— 见 `docs/superpowers/specs/2026-07-13-p1-browse-detail-design.md`
- **P2**（下一个）：...
```

并把"（测试数持续增长，以 PROGRESS.md 为准）"更新为当前实际数。

- [ ] **Step 2: PROGRESS.md 阶段表更新**

把 P1 行从 `⬜ 未开始` 改为 `✅ 完成`，加起止日期和工时，备注加"service + router + 4 模板 + 50 测试"。

- [ ] **Step 3: README.md 阶段表更新**

把 `| P1 | 浏览筛选 + 题目详情（HTMX 无刷新） | 待开始 |` 改为 `| P1 | 浏览筛选 + 题目详情（HTMX 无刷新） | 完成 |`，并把 HTMX + Alpine.js 行的"待接入"删掉。

- [ ] **Step 4: 跑全套验证 + push**

Run: `.venv/bin/python -m pytest -q`
Run: `.venv/bin/ruff check .`
Run: `.venv/bin/mypy app/`
Expected: 50+ passed, 干净

- [ ] **Step 5: 提交 + push**

```bash
git add AGENTS.md PROGRESS.md README.md
git commit -m "docs: P1 阶段标完成（service + 4 模板 + 50 测试）"
git push origin main
```

---

## 完成定义

- [ ] `mypy app/` 退出码 0
- [ ] `ruff check .` 干净
- [ ] `pytest` 全过（75 + 36 + 10 + 3 + 1 = ~125）
- [ ] CI 绿灯（Python 3.11 / 3.12）
- [ ] 浏览器手测：列表筛选/分页/排序/详情全通
- [ ] AGENTS.md / PROGRESS.md / README.md 同步 P1 完成
- [ ] 至少 1 个 commit 引用 spec 路径（已含在 task commit message）
