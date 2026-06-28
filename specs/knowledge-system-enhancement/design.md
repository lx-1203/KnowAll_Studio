# 知识点学习系统增强 - 技术设计文档

## 1. 架构概述

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (React 18)                  │
│  SummaryPage  MindMapPage  InteractiveQuizPage          │
│  LanguageLearningPage  CoverageReportPage               │
│  ReviewQueuePanel  StudyPlanPage (enhanced)             │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP/SSE
┌──────────────────────▼──────────────────────────────────┐
│                   FastAPI Backend                        │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │         Agent Orchestrator (NEW)                  │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐     │   │
│  │  │Question│ │ Quiz   │ │MindMap │ │Language│     │   │
│  │  │Bank    │ │Interactive│Agent  │ │Agent   │     │   │
│  │  │Agent   │ │Agent   │ │        │ │        │     │   │
│  │  └────────┘ └────────┘ └────────┘ └────────┘     │   │
│  │  ┌────────┐                                       │   │
│  │  │Study   │  ← All agents run in parallel         │   │
│  │  │Plan    │                                        │   │
│  │  │Agent   │                                        │   │
│  │  └────────┘                                        │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │      Memory Feedback Loop (NEW)                   │   │
│  │  CoverageMapper → FeedbackDetector → ReviewQueue  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │      Existing Modules (reused)                    │   │
│  │  DocumentParser  KnowledgeGenerator  QuizGenerator│   │
│  │  FlashcardGenerator  FSRS  Pipeline  API Scheduler│   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

### 1.2 关键技术决策

| 决策 | 选择 | 理由 |
|------|------|------|
| Agent 并行框架 | 自建 `asyncio.gather` + `TaskGroup` | 项目无 LangChain/CrewAI 依赖，自建轻量、可控，与现有 `UnifiedAPIClient` 无缝集成 |
| 知识点总结格式 | Markdown（3级嵌套） | 结构化 + 可人读，LLM 原生支持，前端用 `react-markdown` 渲染 |
| 知识点 ID 体系 | `kp_{doc_id}_{level}_{seq}` （例：`kp_abc123_L1_01`） | 全局唯一、可追溯文档来源、体现层级关系 |
| 覆盖率映射 | 知识点 ↔ 题目/记忆卡 多对多关系表 | 一个知识点可对应多道题/多张卡，支持灵活映射 |
| 回流反馈算法 | FSRS（现有）+ 正确率阈值检测（新增） | 复用现有 FSRS 算法，新增薄弱点检测层：正确率 < 70% → 强制进入复习队列 |
| 学习计划复习节点 | 艾宾浩斯间隔：1/2/4/7/15 天 + FSRS 动态调整 | 初始计划用艾宾浩斯固定节点，实际执行中用 FSRS 动态反馈优化 |
| 语言检测 | LLM 判断 + 关键词匹配双通道 | `POST` 端点接收 `language_type` 参数，也支持自动检测（英文关键词/日语假名检测） |

---

## 2. 数据模型变更

### 2.1 新增表

#### `knowledge_summaries` — 知识点总结（完整 Markdown）
```sql
CREATE TABLE knowledge_summaries (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content_md    TEXT NOT NULL,                    -- 完整 Markdown 内容
    node_count    INTEGER DEFAULT 0,                -- 知识点节点总数
    level_stats   JSON DEFAULT '{}',                -- {"L1":3,"L2":12,"L3":45}
    generated_at  TIMESTAMP DEFAULT NOW(),
    model_used    VARCHAR(64),
    generation_cache_key VARCHAR(64) UNIQUE
);
```

#### `knowledge_point_nodes` — 知识点节点（结构化拆分）
```sql
CREATE TABLE knowledge_point_nodes (
    id              VARCHAR(64) PRIMARY KEY,         -- kp_{doc_id}_L{level}_{seq}
    summary_id      UUID REFERENCES knowledge_summaries(id),
    document_id     UUID NOT NULL REFERENCES documents(id),
    parent_id       VARCHAR(64) REFERENCES knowledge_point_nodes(id),
    level           INTEGER NOT NULL CHECK(level BETWEEN 1 AND 3),
    sequence        INTEGER NOT NULL,                -- 同级排序序号
    title           VARCHAR(256) NOT NULL,
    explanation     TEXT NOT NULL,                   -- 详细解释
    related_concepts TEXT,                           -- 关联概念（JSON 数组）
    examples        TEXT,                            -- 示例（Markdown）
    tags            JSON DEFAULT '[]',
    UNIQUE(document_id, id)
);
```

#### `knowledge_coverage` — 知识点覆盖率映射
```sql
CREATE TABLE knowledge_coverage (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    knowledge_point_id  VARCHAR(64) NOT NULL REFERENCES knowledge_point_nodes(id),
    resource_type       VARCHAR(32) NOT NULL,        -- 'question' | 'flashcard'
    resource_id         UUID NOT NULL,               -- question_bank.id 或 flashcards.id
    is_primary          BOOLEAN DEFAULT TRUE,        -- 是否为主要覆盖（每知识点至少一条 is_primary=TRUE）
    created_at          TIMESTAMP DEFAULT NOW(),
    UNIQUE(knowledge_point_id, resource_type, resource_id)
);
```

#### `answer_records_extended` — 扩展答题记录（在现有 `answer_records` 基础上扩展）
```sql
-- 修改现有 answer_records 表，新增字段
ALTER TABLE answer_records ADD COLUMN time_spent_ms INTEGER DEFAULT 0;
ALTER TABLE answer_records ADD COLUMN attempt_count INTEGER DEFAULT 1;
ALTER TABLE answer_records ADD COLUMN knowledge_point_ids JSON DEFAULT '[]';
ALTER TABLE answer_records ADD COLUMN is_review_queue BOOLEAN DEFAULT FALSE;
```

#### `memory_cards_extended` — 记忆卡扩展（在现有 `flashcards` 基础上扩展）
```sql
-- 修改现有 flashcards 表，新增字段
ALTER TABLE flashcards ADD COLUMN knowledge_point_id VARCHAR(64) REFERENCES knowledge_point_nodes(id);
ALTER TABLE flashcards ADD COLUMN card_type_ext VARCHAR(32) DEFAULT 'basic';  -- 'basic' | 'cloze' | 'concept_map'
ALTER TABLE flashcards ADD COLUMN review_count INTEGER DEFAULT 0;
ALTER TABLE flashcards ADD COLUMN correct_count INTEGER DEFAULT 0;
ALTER TABLE flashcards ADD COLUMN last_review_at TIMESTAMP;
ALTER TABLE flashcards ADD COLUMN accuracy_rate FLOAT DEFAULT 0.0;
```

#### `review_queue` — 复习推送队列
```sql
CREATE TABLE review_queue (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id),
    resource_type   VARCHAR(32) NOT NULL,            -- 'flashcard' | 'question'
    resource_id     UUID NOT NULL,
    knowledge_point_id VARCHAR(64) REFERENCES knowledge_point_nodes(id),
    priority        INTEGER DEFAULT 0,               -- 优先级（正确率越低越高）
    reason          VARCHAR(64),                     -- 'low_accuracy' | 'overdue' | 'manual'
    pushed_at       TIMESTAMP DEFAULT NOW(),
    completed       BOOLEAN DEFAULT FALSE,
    completed_at    TIMESTAMP
);
```

#### `study_plans_enhanced` — 增强学习计划（扩展现有 `study_plans`）
```sql
-- 修改现有 study_plans 表，新增字段
ALTER TABLE study_plans ADD COLUMN plan_type VARCHAR(16) DEFAULT 'long';
  -- 'short' = 短期(1-3天,按小时) | 'long' = 长期(1-4周,按天)
ALTER TABLE study_plans ADD COLUMN ebbinghaus_nodes JSON DEFAULT '[]';
  -- [{day:1, review:true}, {day:2, review:true}, {day:4, review:true}, ...]
ALTER TABLE study_plans ADD COLUMN daily_hours FLOAT DEFAULT 2.0;
ALTER TABLE study_plans ADD COLUMN knowledge_point_ids JSON DEFAULT '[]';
```

#### `language_vocabulary` — 生词表
```sql
CREATE TABLE language_vocabulary (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id),
    word            VARCHAR(128) NOT NULL,
    phonetic        VARCHAR(64),                     -- 音标
    part_of_speech  VARCHAR(32),                     -- 词性
    definition      TEXT NOT NULL,                   -- 释义
    example_sentence TEXT,                           -- 例句
    difficulty      VARCHAR(16) DEFAULT 'medium',    -- easy/medium/hard
    knowledge_point_id VARCHAR(64) REFERENCES knowledge_point_nodes(id),
    UNIQUE(document_id, word)
);
```

### 2.2 数据模型 ER 关系

```
documents ──1:N──> knowledge_summaries
documents ──1:N──> knowledge_point_nodes
documents ──1:N──> language_vocabulary

knowledge_point_nodes ──1:N──> knowledge_coverage
knowledge_coverage ──> question_bank (via resource_id)
knowledge_coverage ──> flashcards (via resource_id)

knowledge_point_nodes ──1:N──> flashcards (via knowledge_point_id)
knowledge_point_nodes ──1:N──> review_queue

users ──1:N──> review_queue
users ──1:N──> answer_records_extended
```

---

## 3. 接口设计

### 3.1 知识点总结生成

**`POST /api/v1/knowledge/summary/generate`**

- **认证**: Bearer Token
- **参数**:
  ```json
  {
    "document_id": "uuid (required)",
    "model": "string (optional, default: 'deepseek-chat')",
    "language_type": "string (optional, 'auto' | 'chinese' | 'english' | 'japanese')",
    "max_depth": "integer (optional, default: 3, 最大层级深度)"
  }
  ```
- **响应** (SSE 流式):
  ```
  event: progress
  data: {"stage":"generating","progress":0.5,"message":"正在生成第2章知识点..."}

  event: complete
  data: {"summary_id":"uuid","content_md":"...","node_count":120,"level_stats":{"L1":5,"L2":18,"L3":97}}
  ```
- **错误**:
  - `404`: 文档不存在
  - `429`: API 配额不足
  - `502`: LLM 调用失败

**`GET /api/v1/knowledge/summary/{summary_id}`**

- 返回完整 Markdown 内容 + 结构化节点树
- **响应**: `{summary_id, document_id, content_md, nodes: [...], level_stats, generated_at}`

**`GET /api/v1/knowledge/summary/{summary_id}/nodes`**

- 返回知识点节点列表（支持 `?level=2` 按层级过滤）

### 3.2 Agent 调度

**`POST /api/v1/agents/orchestrate`**

- **认证**: Bearer Token
- **参数**:
  ```json
  {
    "summary_id": "uuid (required)",
    "document_id": "uuid (required)",
    "agents": ["question_bank", "mindmap", "study_plan"],  // 可指定，默认全部
    "language_type": "string (optional)",
    "config": {
      "question_count": 30,
      "question_types": ["single_choice", "fill_blank", "short_answer"],
      "study_plan": {"type": "both", "daily_hours": 2.0}
    }
  }
  ```
- **响应** (SSE 流式，并行 Agent 状态推送):
  ```
  event: agent_start
  data: {"agent":"question_bank","status":"started"}

  event: agent_start
  data: {"agent":"mindmap","status":"started"}

  event: agent_progress
  data: {"agent":"question_bank","progress":0.6,"message":"已生成 18/30 题"}

  event: agent_complete
  data: {"agent":"question_bank","result":{"total":30,"types":{...}}}

  event: agent_complete
  data: {"agent":"mindmap","result":{"nodes":120,"edges":150}}

  event: orchestrate_complete
  data: {"results":{"question_bank":{...},"mindmap":{...},"study_plan":{...}},"coverage_report":{...}}
  ```

### 3.3 交互式答题

**`GET /api/v1/quiz/interactive/start?summary_id=uuid&count=10&mode=sequential`**

- 返回首批题目（支持分页加载，每批10题）

**`POST /api/v1/quiz/interactive/submit`**

- **参数**:
  ```json
  {
    "question_id": "uuid",
    "user_answer": "string | array",
    "time_spent_ms": 12000,
    "knowledge_point_id": "kp_xxx"
  }
  ```
- **响应**:
  ```json
  {
    "is_correct": true,
    "correct_answer": "B",
    "analysis": "详细解析...",
    "stats": {"total_answered": 5, "correct": 4, "accuracy": 0.8}
  }
  ```

### 3.4 思维导图数据

**`GET /api/v1/knowledge/summary/{summary_id}/mindmap`**

- 返回思维导图结构数据（ReactFlow 兼容格式）
- **响应**:
  ```json
  {
    "nodes": [{"id":"kp_xxx","label":"知识点名称","level":1,"children":[...]}],
    "edges": [{"source":"kp_a","target":"kp_b","relation":"parent_child"}]
  }
  ```

### 3.5 外语学习

**`GET /api/v1/language/vocabulary?document_id=uuid&summary_id=uuid`**

- 返回生词表，支持按词性/难度过滤和排序

**`POST /api/v1/language/vocabulary/generate`**

- **参数**: `{document_id, summary_id, language_type}`
- 由外语学习 Agent 处理，从知识点中提取并翻译生词

### 3.6 学习计划（增强）

**`POST /api/v1/study/generate-plan-enhanced`**

- **参数**:
  ```json
  {
    "summary_id": "uuid",
    "plan_type": "both",
    "daily_hours": 2.0,
    "start_date": "2026-06-29",
    "ebbinghaus_enabled": true
  }
  ```
- **响应**: 短期计划（按小时）+ 长期计划（按天）+ 艾宾浩斯复习节点

### 3.7 覆盖率报告

**`GET /api/v1/knowledge/summary/{summary_id}/coverage`**

- **响应**:
  ```json
  {
    "total_knowledge_points": 120,
    "covered_by_questions": 115,
    "covered_by_flashcards": 110,
    "full_coverage": 108,
    "coverage_rate_questions": 0.958,
    "coverage_rate_flashcards": 0.917,
    "full_coverage_rate": 0.90,
    "uncovered_points": [
      {"id":"kp_xxx","title":"未被覆盖的知识点","level":3}
    ],
    "weak_points": [
      {"id":"kp_yyy","title":"薄弱知识点","accuracy":0.55,"recommendation":"建议重新复习"}
    ]
  }
  ```

### 3.8 记忆回流反馈

**`POST /api/v1/memory/feedback/scan`**

- 触发回流检测，扫描所有用户的记忆卡和答题记录
- 将正确率 < 阈值的卡片/题目推送至复习队列
- **参数**: `{threshold: 0.7}` (可选，默认 0.7)

**`GET /api/v1/memory/review-queue?limit=20`**

- 获取当前用户的复习队列（按优先级排序）

**`POST /api/v1/memory/review-queue/{queue_id}/complete`**

- 标记复习队列项已完成

**`GET /api/v1/memory/stats`**

- 返回记忆统计：总卡片数、平均正确率、薄弱知识点数、今日待复习数

---

## 4. 前端设计

### 4.1 新增页面

| 页面 | 路由 | 说明 |
|------|------|------|
| `SummaryPage` | `/summary/:id` | 知识点总结展示，Markdown 渲染 + 目录导航 |
| `MindMapPage` | `/mindmap/:summaryId` | 思维导图可视化（ReactFlow） |
| `InteractiveQuizPage` | `/quiz/interactive/:summaryId` | 交互式逐题作答界面 |
| `LanguageLearningPage` | `/language/:docId` | 生词表展示与学习 |
| `CoverageReportPage` | `/coverage/:summaryId` | 覆盖率报告 + 薄弱知识点面板 |

### 4.2 新增组件

| 组件 | 说明 |
|------|------|
| `MarkdownTOC` | Markdown 目录导航（侧边栏，可折叠） |
| `KnowledgePointCard` | 知识点卡片组件（显示名称、解释、关联、示例） |
| `MindMapViewer` | ReactFlow 思维导图渲染器 |
| `InteractiveQuestionCard` | 交互式答题卡（逐题显示 + 即时判分） |
| `ReviewQueuePanel` | 复习队列面板（优先级排序 + 一键复习） |
| `CoverageChart` | 覆盖率饼图/柱状图 |
| `VocabularyTable` | 生词表（单词、音标、释义、例句、操作） |
| `StudyPlanTimeline` | 学习计划时间轴组件 |

### 4.3 状态管理扩展

在 `stores/index.ts` 中新增：
```typescript
interface SummaryStore {
  currentSummary: KnowledgeSummary | null;
  nodes: KnowledgePointNode[];
  mindmapData: MindMapData | null;
  // actions
  loadSummary: (id: string) => Promise<void>;
  loadMindmap: (id: string) => Promise<void>;
}

interface MemoryStore {
  reviewQueue: ReviewQueueItem[];
  coverageReport: CoverageReport | null;
  memoryStats: MemoryStats | null;
  // actions
  loadReviewQueue: () => Promise<void>;
  loadCoverageReport: (summaryId: string) => Promise<void>;
  triggerFeedbackScan: () => Promise<void>;
}
```

---

## 5. 可复用资产

基于对现有代码的分析，以下模块可直接复用或小幅扩展：

| 现有模块 | 复用方式 | 说明 |
|----------|----------|------|
| `UnifiedAPIClient` | 直接复用 | 所有 Agent 共用此 LLM 调用客户端 |
| `PromptEngine` | 扩展 | 新增 `summary.yaml`、`language.yaml` 模板 |
| `KnowledgeGenerator` | 扩展 | 新增 `generate_summary()` 方法 |
| `QuizGenerator` | 直接复用 | 题库 Agent 复用其 9 种题型生成逻辑 |
| `ExamEngine` | 直接复用 | 交互式答题复用其判分逻辑 |
| `FSRS` | 扩展 | 新增正确率追踪、回流触发 |
| `FlashcardGenerator` | 扩展 | 新增知识点关联字段 |
| `PipelineOrchestrator` | 重构 | 从顺序执行改为并行 Agent 调度 |
| `DocumentParser` | 直接复用 | 文档上传解析流程不变 |
| `api.ts` (前端) | 扩展 | 新增 API 调用函数 |
| `stores/index.ts` | 扩展 | 新增 Store |

---

## 6. 文件变更清单

### 6.1 新增文件（后端）

```
backend/app/core/knowledge/summary_generator.py        # 知识点总结生成器
backend/app/core/agents/__init__.py                     # Agent 框架入口
backend/app/core/agents/orchestrator.py                 # Agent 并行调度器
backend/app/core/agents/base.py                         # Agent 基类
backend/app/core/agents/question_bank_agent.py          # 题库生成 Agent
backend/app/core/agents/quiz_interactive_agent.py       # 交互式答题 Agent
backend/app/core/agents/mindmap_agent.py                # 思维导图 Agent
backend/app/core/agents/language_agent.py               # 外语学习 Agent
backend/app/core/agents/study_plan_agent.py             # 学习计划 Agent
backend/app/core/memory/feedback_loop.py                # 记忆回流反馈引擎
backend/app/core/memory/coverage.py                     # 覆盖率计算引擎
backend/app/api/agents.py                               # Agent 调度 API 路由
backend/app/api/language.py                             # 外语学习 API 路由
backend/app/api/memory_feedback.py                      # 记忆反馈 API 路由
backend/app/api/coverage.py                             # 覆盖率 API 路由
backend/app/api/interactive_quiz.py                     # 交互式答题 API 路由
backend/app/prompts/summary.yaml                        # 知识点总结提示词
backend/app/prompts/language.yaml                       # 外语学习提示词
backend/alembic/versions/xxxx_enhance_knowledge.py      # 数据库迁移
```

### 6.2 新增文件（前端）

```
frontend/src/pages/SummaryPage.tsx                      # 知识点总结页
frontend/src/pages/MindMapPage.tsx                      # 思维导图页
frontend/src/pages/InteractiveQuizPage.tsx              # 交互式答题页
frontend/src/pages/LanguageLearningPage.tsx              # 外语学习页
frontend/src/pages/CoverageReportPage.tsx                # 覆盖率报告页
frontend/src/components/MarkdownTOC.tsx                  # Markdown 目录导航
frontend/src/components/KnowledgePointCard.tsx           # 知识点卡片
frontend/src/components/MindMapViewer.tsx                # 思维导图渲染
frontend/src/components/InteractiveQuestionCard.tsx      # 交互式答题卡
frontend/src/components/ReviewQueuePanel.tsx             # 复习队列面板
frontend/src/components/CoverageChart.tsx                # 覆盖率图表
frontend/src/components/VocabularyTable.tsx              # 生词表
frontend/src/components/StudyPlanTimeline.tsx            # 学习计划时间轴
```

### 6.3 修改文件

```
backend/app/main.py                          # 注册新路由
backend/app/models/__init__.py               # 新增/扩展数据模型
backend/app/schemas.py                       # 新增 Schema
backend/app/api/knowledge.py                 # 新增总结生成端点
backend/app/api/study.py                     # 新增增强计划端点
backend/app/core/pipeline.py                 # 集成 Agent 调度
backend/app/core/knowledge/__init__.py       # 扩展生成器
backend/app/core/memory/__init__.py          # 扩展 FSRS / 记忆卡
backend/app/core/quiz/__init__.py            # 扩展判分逻辑（耗时、知识ID）
backend/app/prompts/__init__.py              # 注册新模板
backend/alembic/env.py                       # 迁移环境（如需调整）
frontend/src/App.tsx                         # 新增路由 + 导航菜单项
frontend/src/api.ts                          # 新增 API 函数（~15个）
frontend/src/types.ts                        # 新增 TS 类型
frontend/src/stores/index.ts                 # 新增 Store
```

---

## 7. 技术决策与权衡

### 7.1 Agent 并行 vs 串行
- **选择**: 使用 `asyncio.TaskGroup` 实现真正的并发（非线程池）
- **理由**: 所有 Agent 都是 I/O 密集型（LLM API 调用），asyncio 并发效率高
- **权衡**: 增加并发 API 调用量，需要确保配额和速率限制（复用现有 `RateLimiter`）

### 7.2 知识点存储：Markdown vs 结构化 JSON
- **选择**: 双重存储——完整 Markdown（`content_md`）+ 结构化节点表（`knowledge_point_nodes`）
- **理由**: Markdown 用于人读和导出；结构化节点用于映射、覆盖率计算、思维导图生成
- **权衡**: 存储冗余，但查询效率和解耦性更好

### 7.3 覆盖率映射：实时 vs 定时
- **选择**: 实时查询 + 增量更新（生成题目/记忆卡时立即写入 `knowledge_coverage` 表）
- **理由**: 用户期望生成后立即看到覆盖率报告
- **权衡**: 增加写入开销，但避免了离线计算的不一致问题

### 7.4 回流检测：定时 vs 事件驱动
- **选择**: 混合模式——每次答题后增量更新统计，提供手动 `/scan` 端点 + 可选的定时任务
- **理由**: 实时性 + 灵活性；暂不引入 cron 依赖
- **权衡**: 不主动推送（无 WebSocket），用户需手动触发或页面刷新

### 7.5 外语检测：规则 vs LLM
- **选择**: 双通道——LLM 判断为主，规则匹配（Unicode 范围检测）为辅助降级
- **理由**: LLM 准确但慢/贵；规则快但局限。双通道保证可用性
- **权衡**: 两种检测可能不一致，优先信任 LLM
