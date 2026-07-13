# 数学题库应用程序 —— 建设方案

> 2026-07-13 | 王老师 × AI 协作设计
> 参考：MathCyclus 高中数学题库项目
> 目标：构建一个 AI 驱动的本地题库管理系统，覆盖初中数学

---

## 核心理念

**数据库存储 + AI 辅助 + 人机协作**，替代现有的"AI Agent + Markdown 文件"模式。

```
          AI 服务 (OCR/LLM)
              │
              ▼
  用户 ──→ 应用 (FastAPI) ──→ SQLite 数据库
              │
              ▼
    编辑/浏览/组卷/统计 ←── 用户
```

AI 做转换和字段建议，用户做审查裁决。

---

## 完整工作流

### 第一阶段：录入

三种录入模式，根据场景选择：

| 模式 | 适用场景 | 差异 |
|------|---------|------|
| **单题录入** | 补录单道题、截图录入 | 独立表单，OCR 后逐道填充 |
| **同卷录入** | 整份试卷连续多题 | 统一年份/来源/试卷名，自动分配题号 |
| **批量录入** | 多张图片中的不同试卷 | 每张图片独立识别，并联处理 |

#### 同卷录入流程（主力模式）

```
原始试卷 PDF/DOCX
     │
     ▼
① 上传 ──→ 自动存入 raw/，命名为 {年份}-{来源缩写}.{pdf/docx}
     │
     ▼
② OCR ──→ PaddleOCR 识别 → Markdown 文本 + 自动裁切配图
           提示词从外部文件加载，不写死在代码中
     │
     ▼
③ AI 拆分 ──→ LLM 按题号分割 → 每道题得到三字段：
               题干(stem) | 答案(answer) | 解析(solution)
     │
     ▼
④ 审查界面 ──→ 左栏：原始试卷片段
               右栏：OCR 结果 + 可编辑文本框
               Alpine.js 驱动的逐题滑动校对
               确认每道题的配图归属
     │
     ▼
⑤ AI 建议元数据 ──→ LLM 根据题干推断：
                    题型 | 知识点 | 难度 | 核心素养 | 布鲁姆层级
                    用户以下拉菜单确认/修改
     │
     ▼
⑥ 答案核对 ──→ 输入该卷标准答案 → 逐题自动比对 → 标记差异
     │
     ▼
⑦ 写入数据库 ──→ INSERT questions 表
                  写入时自动校验（必填字段、值域合法性）
                  建立 paper_questions 关联
                  原子写入（临时文件 → fsync → 原子替换）
                  失败则回滚并提示具体字段错误
     │
     ▼
    ✅ 该套试卷录入完成，进入消费端
```

### 第二阶段：管理

```
┌─ 单题编辑 ── 搜索/定位 → 修改任意字段 → 实时 KaTeX 预览 → 保存校验
├─ 元数据批量 ─ 选中多题 → 批量修改题型/知识点/难度等
├─ 知识树维护 ─ 增删知识点节点 → 自动更新关联题目统计
└─ 源文件管理 ─ 查看 raw/ 清单，标记已录入/待录入
```

### 第三阶段：消费（组卷与导出）

#### 组卷流程

```
阶段一：选题                   阶段二：排版                   阶段三：输出
─────────────────  ─────────────────  ─────────────────
AI 预组卷 或             调整题目顺序             选择导出格式
手动浏览筛选             试卷结构编排             一键导出
购物车管理              答案模式选择
```

#### AI 预组卷策略

按难度分层抽题，确保覆盖：

| 层级 | 难度映射 | 占比参考 |
|------|---------|---------|
| 基础题 | 易 | 50% |
| 中档题 | 中 | 30% |
| 难题 | 难 | 20% |

输入：目标知识点 + 难度分布 + 题型要求 → AI 推荐最优题单。

#### 答案显示模式（组卷时可选）

| 模式 | 效果 | 适用场景 |
|------|------|---------|
| 0 — 完整显示 | 显示题干、解答、答案 | 讲义类 |
| 1 — 留白篇幅 | 保留题干的解答区占位空白，答案隐藏 | 练习册 |
| 2 — 固定空白 | 题后固定分页留白，答案隐藏 | 考试卷 |
| 3 — 完全隐藏 | 仅题干，不显示解答和答案 | 测试卷 |

#### 导出格式

| 格式 | 实现方式 | 场景 |
|------|---------|------|
| HTML 打印版 | Jinja2 模板 + KaTeX | 即时预览，浏览器打印/另存 PDF |
| LaTeX → PDF | LaTeX 模板 → xelatex 编译 | 正式印刷，专业排版 |

#### 引用次数追踪

每道题被组卷引用时自动递增 `citation_count` 字段，用于统计高频考点。

### 第四阶段：统计

```
知识点覆盖雷达图 | 难度分布饼图 | 来源/年份柱状图 | 题型占比
审核进度 | 高频考点排行（引用次数排序）
```

---

## 数据库设计

### 题目表 `questions`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT PK | `M{年份}-{来源缩写}-{序号}` |
| `stage` | TEXT | 学段：初中 |
| `grade` | TEXT | 七年级/八年级/九年级 |
| `question_type` | TEXT | 选择题/填空题/计算题/证明题/作图题/应用题/探究题/综合题 |
| `section` | TEXT | 六大板块 |
| `source` | TEXT | 完整来源描述 |
| `source_abbr` | TEXT | 缩写如 NCZK |
| `year` | INTEGER | |
| `is_exam_question` | BOOL | 是否真题 |
| `review_status` | TEXT | 草稿/待审核/已入库 |
| `topic_l1` | TEXT | 知识点一级 |
| `topic_l2` | TEXT | 知识点二级 |
| `angle` | TEXT | 考查角度 |
| `core_literacy` | TEXT | JSON 数组 |
| `difficulty` | TEXT | 易/中/难 |
| `bloom_level` | TEXT | JSON 数组 |
| **`stem`** | TEXT | **题干（LaTeX）** |
| **`answer`** | TEXT | **答案（LaTeX）** |
| **`solution`** | TEXT | **解析（LaTeX）** |
| `images` | TEXT | JSON 数组 |
| `passage_id` | TEXT | FK → passages |
| `paper_id` | TEXT | FK → papers |
| `question_number` | INT | 在原卷中题号 |
| `score` | REAL | 分值 |
| `citation_count` | INT | 被组卷引用次数，默认 0 |
| `created_at` | DATETIME | |
| `updated_at` | DATETIME | |

### 大题表 `passages`

| 字段 | 说明 |
|------|------|
| `id` | `{年份}-{来源缩写}-{序号}` |
| `title` | 标题 |
| `content` | 共享题干（LaTeX） |
| 元数据字段 | 同 questions 公共字段 |
| `images` | JSON 数组 |

### 试卷表 `papers`

| 字段 | 说明 |
|------|------|
| `id` | `{年份}-{来源缩写}` |
| `title` | 完整标题 |
| `year`/`source`/`source_abbr`/`stage` | |
| `source_path` | raw/ 中的源文件路径 |
| `status` | 待录入/录入中/已录入 |
| `total_questions` | 题量 |
| `total_score` | 总分 |

### 知识点表 `knowledge_tree`

树形结构，自引用 parent_id，从现有 knowledge-tree.md 初始化。

### 组卷记录表 `generated_papers`

| 字段 | 说明 |
|------|------|
| `id` | 自增 PK |
| `title` | 组卷标题 |
| `config` | JSON：选中的条件 |
| `answer_mode` | 答案显示模式 0-3 |
| `format` | 导出格式 |
| `output_path` | 导出文件路径 |
| `created_at` | |
| `question_ids` | JSON 数组，引用的题目 ID |

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | Python FastAPI |
| 数据库 | SQLite |
| 前端模板 | Jinja2 + Tailwind CSS (CDN) |
| 交互 | HTMX（页面切换/筛选）+ Alpine.js（复杂表单/审查界面） |
| 公式渲染 | KaTeX (CDN) |
| 图表 | Chart.js (CDN) |
| OCR | PaddleOCR API |
| LLM | OpenAI 兼容接口（提示词外部文件，可热重载） |
| LaTeX 编译 | xelatex（备选导出路径） |

零 Node.js 构建步骤，`python run.py` 一键启动。

---

## 目录结构

```
MathForge/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── config.py             # 配置
│   ├── database.py           # SQLite 初始化 + 连接
│   ├── models/               # Pydantic 模型
│   │   ├── question.py
│   │   ├── paper.py
│   │   └── passage.py
│   ├── services/             # 业务逻辑
│   │   ├── question_service.py
│   │   ├── ingest_service.py  # 录入引擎（含三种模式）
│   │   ├── ocr_service.py     # PaddleOCR 调用（提示词外部化）
│   │   ├── export_service.py  # 组卷导出（HTML / LaTeX）
│   │   └── file_service.py    # 原子写入 + 备份
│   ├── routers/              # API 路由
│   │   ├── questions.py
│   │   ├── papers.py
│   │   ├── ingest.py
│   │   └── stats.py
│   ├── templates/            # Jinja2 页面
│   │   ├── base.html
│   │   ├── browse.html
│   │   ├── detail.html
│   │   ├── review.html       # 录入审查
│   │   ├── generate.html     # 组卷配置
│   │   ├── preview.html      # 卷面预览
│   │   └── stats.html
│   └── static/
│       ├── css/style.css
│       └── js/app.js
├── data/
│   ├── vault.db              # SQLite 数据库
│   └── uploads/              # 上传临时文件
├── raw/                      # 原始试卷（只读存储）
├── outputs/                  # 组卷导出
├── prompts/
│   ├── ocr_prompt.txt        # OCR 提示词模板（外部化，可热重载）
│   └── metadata_prompt.txt   # 元数据推断提示词
├── .backups/                 # 文件写入自动备份
├── scripts/
│   ├── import_legacy.py      # 从 wiki/ 导入旧数据
│   └── init_db.py            # 建表 + 初始化知识点树
├── run.py                    # 一键启动
└── requirements.txt
```

---

## 现有数据迁移

`scripts/import_legacy.py` 一次性导入现有 531 道题：

```
扫描 wiki/{题型}/*.md
解析 YAML frontmatter → 字段入库
分割 ## 题目正文 / ## 答案 / ## 解析 → stem/answer/solution
从 manifest 建立 paper 关联
```

新旧系统完全切割，之后新流程走 DB。

---

## 分阶段实施

| 阶段 | 内容 | 预估 |
|------|------|------|
| P0 | 项目骨架 + SQLite 建表 + 初始脚本 | 2 天 |
| P1 | 浏览筛选 + 题目详情（HTMX 无刷新） | 3 天 |
| P2 | 组卷 + 答案模式 + 导出 HTML/LaTeX | 4 天 |
| P3 | 统计仪表盘 + 高频考点排行 | 2 天 |
| P4 | 录入引擎（三种模式 + 审查界面 + OCR 集成） | 5 天 |
| P5 | 管理后台（单题编辑 + 知识树 + 源文件管理） | 3 天 |
| P6 | 旧数据迁移 | 1 天 |
| P7 | 打磨（原子写入、错误处理、体验优化） | 2 天 |

---

## 关键设计原则

1. **AI 是建议者，不是决策者** — 所有 AI 输出经用户确认后才写入
2. **校验是写入的门禁** — 字段完整、值域正确、关联完整，不通过则回滚
3. **原子写入** — 临时文件 → fsync → 原子替换，避免文件半写损坏；写入前自动备份
4. **raw/ 只读不删** — 源文件永久保留，临时文件清理
5. **wiki/ 可废弃** — 新系统以 DB 为唯一真相，wiki/ 仅在需要导出时重建
6. **提示词外部化** — OCR/LLM 提示词写在 .txt 文件中，不写死在代码里，可热重载
7. **引用计数追踪** — 每道题被组卷引用的次数自动累加，支撑高频考点分析
8. **新项目独立建设** — 不与现有 mathVault 目录耦合，另起项目目录

---

## 参考来源

本文档的设计融合以下来源：
- MathVault 现有题库规范（知识体系、字段合法值、校验逻辑）
- MathCyclus 高中数学题库项目（三种录入模式、答案显示模式、AI 分层组卷策略、原子写入、引用计数追踪、提示词外部化）
- 《义务教育数学课程标准（2022年版）》
