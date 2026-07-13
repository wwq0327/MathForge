# MathForge

![CI](https://github.com/wwq0327/MathForge/actions/workflows/ci.yml/badge.svg)

AI 驱动的本地数学题库管理系统。

初中数学题库 · 数据库存储 · AI 辅助 OCR/LLM · 人机协作审查。

## 特性

- **结构化存储**：SQLite + 五张表（题目 / 大题 / 试卷 / 知识树 / 组卷记录）
- **AI 辅助**：OCR 文本识别 + LLM 元数据推断（提示词外部化、可热重载）
- **录入模式**：单题 / 同卷 / 批量 三种
- **组卷导出**：HTML 即时预览 + LaTeX 专业排版
- **答案模式**：完整 / 留白 / 固定空白 / 完全隐藏 四档
- **引用追踪**：每道题被组卷引用自动累加 `citation_count`

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.12 + FastAPI + Uvicorn |
| 数据库 | SQLite 3（WAL 模式） |
| 模板 | Jinja2 |
| 前端 | Tailwind CSS + KaTeX + HTMX + Alpine.js |
| AI | OpenAI 兼容 LLM + PaddleOCR |
| 公式 | KaTeX（渲染）· LaTeX（导出） |
| 图表 | Chart.js |
| 排版导出 | Jinja2 → HTML / xelatex → PDF |

零 Node.js 构建步骤，`python run.py` 一键启动。

## 快速开始

```bash
# 1. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt -r requirements-dev.txt

# 3. 复制环境变量
cp .env.example .env
# 编辑 .env 填入 LLM_API_KEY 等

# 4. 启动
python run.py
# 访问 http://localhost:8000
```

服务启动时会自动建库（若 `data/vault.db` 不存在），并灌入六大板块知识树种子。

## 访问入口

| 路径 | 说明 |
|---|---|
| `/` | 首页 |
| `/health` | 健康检查（DB 异常返回 503） |
| `/api/stats/summary` | 表行数摘要 |
| `/docs` | Swagger UI |
| `/redoc` | ReDoc |

## 目录结构

```
MathForge/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # pydantic-settings
│   ├── database.py          # SQLite 初始化 + 原子写入
│   ├── logging_config.py    # logging 配置
│   ├── models/              # Pydantic 模型 + 业务枚举
│   ├── services/            # 业务服务（prompt_loader 等）
│   ├── routers/             # API 路由（questions 等）
│   ├── templates/           # Jinja2 页面
│   └── static/              # 静态资源
├── data/
│   ├── vault.db             # SQLite 数据库
│   ├── app.log              # 应用日志（10MB 轮转）
│   └── uploads/             # 上传临时
├── raw/                     # 原始试卷（只读）
├── outputs/                 # 组卷导出
├── prompts/                 # 提示词模板（*.txt，可热重载）
│   ├── ocr_prompt.txt
│   └── metadata_prompt.txt
├── .backups/                # 数据库自动备份
├── scripts/                 # 独立脚本
│   └── init_db.py
├── tests/                   # pytest 测试（124 用例 / 97% 覆盖）
├── run.py                   # 一键启动
├── requirements.txt
├── requirements-dev.txt
├── PLAN.md                  # 建设方案
├── AGENTS.md                # 项目级 AI 协作规则
└── .env.example
```

## 阶段进度

| 阶段 | 内容 | 状态 |
|---|---|---|
| P0 | 项目骨架 + SQLite 建表 + 初始脚本 | 完成 |
| P1 | 浏览筛选 + 题目详情（HTMX 无刷新） | 完成 |
| P2 | 组卷 + 答案模式 + 导出 HTML/LaTeX | 待开始 |
| P3 | 统计仪表盘 + 高频考点排行 | 待开始 |
| P4 | 录入引擎（三种模式 + 审查界面 + OCR 集成） | 待开始 |
| P5 | 管理后台（单题编辑 + 知识树 + 源文件管理） | 待开始 |
| P6 | 旧数据迁移 | 待开始 |
| P7 | 打磨（原子写入、错误处理、体验优化） | 待开始 |

## 开发命令

```bash
pytest                          # 运行所有测试
pytest --cov=app                # 带覆盖率
pytest tests/test_database.py   # 单文件测试
ruff check .                    # 代码风格
mypy app/                       # 类型检查
python scripts/init_db.py --reset --yes --seed  # 重置数据库
```

## 知识体系

初中数学六大板块（来自《义务教育数学课程标准（2022年版）》）：

- 数与代数
- 图形与几何
- 函数
- 统计与概率
- 综合与实践
- 课题学习

知识树种子位于 `prompts/knowledge_tree_seed.json`。

## ID 编码

- 题目：`M{4位年份}-{大写来源缩写}-{序号}`，例 `M2024-NCZK-001`
- 大题：`{4位年份}-{大写来源缩写}-{序号}`，例 `2024-NCZK-001`
- 试卷：`{4位年份}-{大写来源缩写}`，例 `2024-NCZK`

## 许可证

个人教学项目，未指定。
