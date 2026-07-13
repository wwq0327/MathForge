# 阶段进度

按 PLAN.md 第 305-313 行的 P0-P7 路线图追踪。

## 当前状态

**最近完成**：P0 + P1（#1-#22 + R4 实施）— P0 项目骨架与审计打磨，P1 浏览筛选 + 题目详情落地

**最近完成**：P2 组卷 + 答案模式 + 导出（#29-#35）

**进行中**：P3 规划（统计仪表盘 + 高频考点排行）

## 阶段完成情况

| 阶段 | 名称 | 状态 | 起止 | 实际工时 | 备注 |
|---|---|---|---|---|---|
| P0 | 项目骨架 + SQLite 建表 + 初始脚本 | ✅ 完成 | 2026-07-13 | 0.5 天 | 75 测试 / 97% 覆盖（审计后修正） |
| P1 | 浏览筛选 + 题目详情（HTMX） | ✅ 完成 | 2026-07-13 | - | service + router + 4 模板 + 50 测试 |
| P2 | 组卷 + 答案模式 + 导出 HTML/LaTeX | ✅ 完成 | 2026-07-13 | 1 天 | 161 测试 / 手动验证通过 |
| P3 | 统计仪表盘 + 高频考点排行 | ⬜ 未开始 | - | - | - |
| P4 | 录入引擎（三模式 + 审查 + OCR） | ⬜ 未开始 | - | - | - |
| P5 | 管理后台（编辑 + 知识树 + 源文件） | ⬜ 未开始 | - | - | - |
| P6 | 旧数据迁移（wiki → DB） | ⬜ 未开始 | - | - | - |
| P7 | 打磨（原子写入、错误处理、体验） | ⬜ 未开始 | - | - | 部分已在 P0 提前做 |

> 注：issue 标签 `priority/p0-p3` 表**优先级**，不是 PLAN.md 的 **阶段**。两者同名易混，判断阶段进度以代码功能落地为准。

## P0 详细交付（已完成）

- [x] 项目骨架（22 文件 / 7 目录）
- [x] SQLite 5 张表 + 7 索引
- [x] run.py 一键启动（自动建库 + 灌种子）
- [x] 知识树 6 板块种子
- [x] 日志系统（stderr + 10MB 轮转 file handler）
- [x] 75 个 pytest 用例 / 97% 覆盖率
- [x] README + 项目 AGENTS.md
- [x] ruff + mypy + pre-commit 配置入口
- [x] 7 个 P0 优先级 issue 全部关闭
- [x] 7 个 P1 优先级 issue 全部关闭（基建打磨，非 P1 阶段功能）

## P1 详细交付（已完成）

- [x] `app/services/question_service.py` — 题目查询服务（列表/筛选/分页/详情）
- [x] `app/routers/questions.py` — 题目路由（HTMX 列表 + 详情）
- [x] 4 个 Jinja2 模板：list / detail / 筛选 / 表格（base + 分页 partial 配套）
- [x] HTMX 无刷新筛选 + KaTeX 重渲染钩子（`htmx:afterSwap`）
- [x] 测试增量：P0 75 → P1 后 124（+49 用例 / 新增 service + router 覆盖）
- [x] 详细设计：`docs/superpowers/specs/2026-07-13-p1-browse-detail-design.md`

## P2 详细交付（已完成）

- [x] `app/services/paper_service.py` — 组卷业务（cart CRUD + generate + citation_count + latex_escape）
- [x] `app/services/cart_middleware.py` — Cart session cookie 中间件
- [x] `app/routers/papers.py` — 组卷路由（9 个端点：cart API + 生成/预览/导出）
- [x] 5 个 Jinja2 模板：cart 浮条 / 组卷表单 / 结果页 / HTML 打印 / LaTeX
- [x] 浏览页 inline 勾选（checkbox + HTMX 浮条实时更新）
- [x] 4 种答案模式（0-完整 / 1-留白 / 2-固定空白 / 3-完全隐藏）
- [x] 导出 HTML 打印版 + LaTeX `.tex`（含 `\solution` 环境）
- [x] `cart_items` 表 + `generated_papers` 引用计数
- [x] 测试增量：P1 135 → P2 后 161（+26 新测试 / 100% 通过）
- [x] 详细设计 + 实施计划：`docs/superpowers/specs/2026-07-13-p2-composition-design.md`
- [x] 手动验证：勾选 → cart → 生成 → 预览 → 下载 全流程通过

## 阻塞项 / 风险

- **LLM 接入**未配置真实 API Key，P4 录入引擎需先有可用 LLM 才能联调
- **PaddleOCR** 未部署，P4 OCR 流程同样待基础设施
- **旧数据迁移**（P6）依赖 mathVault 现有数据状态，需要单独评估

## 工具链

- Python 3.12 · FastAPI 0.139 · Starlette 1.0.0 · Uvicorn · Pydantic 2.10 · SQLite 3
- Jinja2 3.1.6 · HTMX 1.9.10 · Tailwind CSS · KaTeX 0.16.11
- pytest 9.0.3
- GitHub: https://github.com/wwq0327/MathForge
