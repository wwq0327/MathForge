# 数据库迁移记录

每次 schema 变更追加一条：日期 · 阶段 · 变更摘要 · 涉及文件。

## 2026-07-13 · P0 起点

**变更**：建表 5 张
- `knowledge_tree` (id, parent_id, name, code, sort_order, description, created_at)
- `papers` (id, title, year, source, source_abbr, stage, source_path, status, total_questions, total_score, created_at, updated_at)
- `passages` (id, title, content, source, source_abbr, year, stage, grade, section, topic_l1, topic_l2, images, created_at, updated_at)
- `questions` (id, 27 字段详见 app/database.py SCHEMA_SQL)
- `generated_papers` (id, title, config, answer_mode, format, output_path, question_ids, created_at)

**索引**：7 个（knowledge_parent / q_paper / q_passage / q_topic_l1 / q_difficulty / q_year / q_type）

**配置**：
- PRAGMA journal_mode = WAL
- PRAGMA foreign_keys = ON
- foreign_keys 行为：
  - knowledge_tree.parent_id → knowledge_tree.id (ON DELETE CASCADE)
  - questions.passage_id → passages.id (ON DELETE SET NULL)
  - questions.paper_id → papers.id (ON DELETE SET NULL)

**初始化**：知识树 6 板块种子（prompts/knowledge_tree_seed.json）

**涉及文件**：
- `app/database.py` (SCHEMA_SQL)
- `app/config.py` (ALLOWED_TABLES 等常量)
- `scripts/init_db.py`
- `prompts/knowledge_tree_seed.json`

---

## 2026-07-13 · P0 安全 / 校验加固

**变更**：
- `app/database.py`：删除 `atomic_write_text` 函数内 import；`backup_database` 改用 `Connection.backup()`；新增 `ALLOWED_TABLES` 白名单
- `app/config.py`：app_debug 默认值 True → False；新增 `PROJECT_ROOT` / `TEMPLATES_DIR` / `STATIC_DIR` 模块常量
- `app/logging_config.py`（新增）：stderr + 10MB 轮转 file handler
- `app/main.py`：健康检查失败返回 503 + 通用错误信息（不泄露堆栈）；SQL 表名查询走白名单
- `scripts/init_db.py`：`--reset` 需 `--yes` 二次确认；删前 wal_checkpoint

**涉及文件**：
- `app/logging_config.py`（新增）
- `app/database.py` / `app/config.py` / `app/main.py` / `scripts/init_db.py`
- `.env.example`（每项加注释 + APP_DEBUG 默认 false）

---

## 2026-07-13 · P1 ID 与枚举

**变更**：
- `app/models/enums.py`（新增）：Stage / Grade / QuestionType / Section / Difficulty / ReviewStatus / PaperStatus / BloomLevel（StrEnum）；QUESTION_ID / PASSAGE_ID / PAPER_ID 三正则常量
- `app/models/question.py` / `paper.py` / `passage.py`：字段改用枚举 + `model_config = ConfigDict(from_attributes, str_strip_whitespace)`；ID 字段加 pattern 校验；数值字段加 ge/le 约束

**涉及文件**：
- `app/models/enums.py`（新增）
- `app/models/question.py` / `paper.py` / `passage.py`

---

## 2026-07-13 · P1 路径安全与 API 增强

**变更**：
- `app/services/file_service.py`（新增）：WRITABLE_ROOTS 白名单 + assert_writable + safe_join 防穿越
- `app/api_schemas.py`（新增）：ErrorResponse / HealthResponse / StatsSummaryResponse + install_exception_handlers
- `app/main.py`：路由加 response_model + tags + summary
- `app/config.py`：llm_api_key / paddleocr_token 改 `pydantic.SecretStr`

**涉及文件**：
- `app/services/file_service.py`（新增）
- `app/api_schemas.py`（新增）
- `app/main.py` / `app/config.py`

---

（按时间倒序追加，模板见上方）
