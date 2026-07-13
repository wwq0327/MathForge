# MathForge 项目级 AI 协作规则

> 继承父目录 `Projects/AGENTS.md` 全部规则。本文件是项目专属规范。
> 详细方案见 `PLAN.md`（建设方案），测试与脚本约定见本文。

## 项目身份

- **名称**：MathForge
- **目标**：AI 驱动的本地数学题库管理系统（初中数学）
- **当前阶段**：P0 完成，P1 起步

## 工作约定

### 必读先行
- 改动前必读 `PLAN.md` 对应阶段章节
- 数据库 schema 变更必读 `app/database.py` 的 `SCHEMA_SQL`
- 改动模型必读 `app/models/enums.py` 合法值域

### 命令约定
| 操作 | 命令 |
|---|---|
| 启动服务 | `python run.py`（自动建库 + 灌种子） |
| 重置数据库 | `python scripts/init_db.py --reset --yes --seed` |
| 运行测试 | `pytest`（默认配置） |
| 覆盖率 | `pytest --cov=app` |
| 单文件测试 | `pytest tests/test_xxx.py` |
| Lint | `ruff check .` |
| 类型检查 | `mypy app/` |

### 提交约定
- 一事一提交，commit message 含 issue 编号（如 `(#1, #7)`）
- 中文 commit message，简述 why 而非 what
- 改动前先跑测试，确保全部用例通过（截至 P0 审计为 75 个，后续见 PROGRESS.md）
- 改动后 push 远端（用户明确允许时）

### 文件位置
- 业务服务：`app/services/`
- 路由：`app/routers/`
- 模型：`app/models/`
- 提示词：`prompts/*.txt`（外部化、可热重载）
- 原始试卷：`raw/`（只读，禁止应用层写入/删除）
- 临时上传：`data/uploads/`
- 备份：`.backups/`
- 导出：`outputs/`

### 归档约定
废弃内容移入 `archive/`，不直接删除。

## 关键设计原则（PLAN.md 318-326 行）

1. **AI 是建议者，不是决策者** — 所有 AI 输出经用户确认后才写入
2. **校验是写入的门禁** — Pydantic 字段约束 + 数据库 NOT NULL/CHECK
3. **原子写入** — `atomic_write_text` 用于文件写入；数据库事务用 `get_connection()` context manager
4. **raw/ 只读不删** — 源文件永久保留（`#9` issue 跟踪代码层保护）
5. **wiki/ 可废弃** — 新系统以 DB 为唯一真相
6. **提示词外部化** — `prompts/*.txt`，通过 `app.services.prompt_loader.load_prompt()` 加载
7. **引用计数追踪** — `questions.citation_count` 字段支撑高频考点分析
8. **新项目独立** — 不与 `mathVault` 目录耦合

## 阶段范围

- **P0**（完成）：项目骨架 + SQLite 建表 + 初始脚本 + 75 测试 / 97% 覆盖（测试数持续增长，以 PROGRESS.md 为准）
- **P1**（下一个）：浏览筛选 + 题目详情（HTMX 无刷新）
- **P2-P7**：见 `PLAN.md` 第 305-313 行

## ID 编码（必读）

- 题目：`M{4位年份}-{大写来源缩写}-{序号}`，正则 `^M\d{4}-[A-Z]+-\d+$`
- 大题：`{4位年份}-{大写来源缩写}-{序号}`，正则 `^\d{4}-[A-Z]+-\d+$`
- 试卷：`{4位年份}-{大写来源缩写}`，正则 `^\d{4}-[A-Z]+$`

应用层校验在 `app/models/enums.py` 的 `*_ID_PATTERN` 常量。

## 错误处理约定

- 用户可见错误：返回通用消息，详情记日志（`log.exception`）
- 数据库错误：`get_connection()` 已在 `except` 中 rollback
- LLM 调用失败：用户层捕获，返回重试提示
- 写入前必须 `init_schema()` 已执行

## 公开 API 稳定性

- `/health`：返回 200 / 503 二态 JSON
- `/api/stats/summary`：返回 `{table: count}` 字典
- 后续 P1+ 添加的 API 必须含 `tags` / `response_model` / `summary`

## 测试约定

- 单元测试位于 `tests/`，文件名 `test_xxx.py`
- 公共函数必须测：正常路径 + 失败路径
- 数据库测试用 `tmp_db_path` fixture（自动 `tmp_path` 隔离）
- FastAPI 测试用 `client` fixture（`TestClient` + 隔离 settings）
- 修改代码前先看测试通过；修改后必须跑全部测试

## 自主边界（与父 AGENTS.md 一致）

以下操作必须先问：
- 删除文件、目录或 git 历史
- 修改 .env、密钥、token、CI/CD 配置
- git push、rebase、reset --hard、强制推送
- 安装全局依赖或修改系统配置
- 公开发布
