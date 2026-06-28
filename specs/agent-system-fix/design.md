# Agent 系统修复与完善 - 技术设计文档

## 1. 架构概述

### 1.1 当前问题架构

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (React 18)                  │
│  SummaryPage  MindMapPage  InteractiveQuizPage          │
│  CoverageReportPage  StudyPage                          │
│  LanguageLearningPage ← MISSING                         │
│  PipelinePage ← EXISTS BUT NOT ROUTED                   │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP/SSE
┌──────────────────────▼──────────────────────────────────┐
│                   FastAPI Backend                        │
│                                                          │
│  ┌─ PipelineOrchestrator ──┐  ┌─ AgentOrchestrator ──┐  │
│  │ PARSE → TREE → OUTLINE  │  │ QuestionBank          │  │
│  │ → QUIZ → FLASHCARDS     │  │ MindMap               │  │
│  │            ↓             │  │ Language              │  │
│  │        DONE (stops)     │  │ StudyPlan             │  │
│  └─────────────────────────┘  │ Flashcard             │  │
│              ✗                 └──────────────────────┘  │
│         NOT CONNECTED                                   │
│                                                          │
│  Tests: 18 cases, zero agent/memory/knowledge coverage  │
└──────────────────────────────────────────────────────────┘
```

### 1.2 目标架构

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (React 18)                  │
│  + LanguageLearningPage  + PipelinePage (routed)        │
│  SummaryPage  MindMapPage  InteractiveQuizPage          │
│  CoverageReportPage  StudyPage                          │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP/SSE (unified format)
┌──────────────────────▼──────────────────────────────────┐
│                   FastAPI Backend                        │
│                                                          │
│  ┌─ PipelineOrchestrator ───────────────────────────┐   │
│  │ PARSE → TREE → OUTLINE → SUMMARY                 │   │
│  │          ↓                                        │   │
│  │     AgentOrchestrator.orchestrate_from_pipeline() │   │
│  │          ↓                                        │   │
│  │     QuestionBank | MindMap | Language |           │   │
│  │     StudyPlan | Flashcard  (parallel)             │   │
│  │          ↓                                        │   │
│  │     Coverage Report → DONE                        │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  Tests: 150+ cases covering agents/memory/knowledge     │
└──────────────────────────────────────────────────────────┘
```

### 1.3 关键技术决策

| 决策 | 选择 | 理由 |
|------|------|------|
| Pipeline 集成方式 | 在 Pipeline 中调用 AgentOrchestrator（松耦合） | 不改动 AgentOrchestrator 核心逻辑，仅在 Pipeline 末尾增加调度步骤 |
| SSE 格式 | 保持两套格式并存，Pipeline 输出同时包含两种事件 | 向后兼容现有前端；新增 `event:` 行让新前端可区分 Agent 事件 |
| 测试策略 | 纯函数优先 + Mock DB/LLM | 纯函数（BOIS、extract_nodes）直接测试；Agent run() 用 mock |
| LanguageLearningPage | 新建独立页面 | 复用已有的 API 函数和 TypeScript 类型 |
| PipelinePage | 添加路由 + 菜单项 | 文件已存在，仅需注册 |
| QuizInteractiveAgent | 不新建独立 Agent | 当前 API 层实现已满足需求，新建 Agent 无额外价值 |

---

## 2. Pipeline-Agent 集成设计

### 2.1 修改点

**文件**: `backend/app/core/pipeline.py`

在 PipelineOrchestrator.run_full_chain() 中，OUTLINE 阶段完成后（即知识点总结生成后），新增一个 AGENTS 阶段：

```python
# 在 _run_stage_outline() 完成后插入
# Stage: AGENTS (new)
try:
    yield self._progress(state, PipelineStage.AGENTS, 65, "正在并行调度学习Agent...")
    from app.core.agents.orchestrator import orchestrator as agent_orch
    agent_results = await agent_orch.orchestrate(
        summary_id=state.summary_id,
        document_id=document_id,
        config={
            "question_count": question_count,
            "question_types": question_type,
        }
    )
    state.result["agent_results"] = agent_results
    yield self._progress(state, PipelineStage.AGENTS, 95, "Agent调度完成")
except Exception as e:
    # Agent 失败不中止整个 Pipeline
    logger.error(f"Agent调度失败: {e}")
    state.result["agent_error"] = str(e)
    yield self._progress(state, PipelineStage.AGENTS, 95, f"Agent调度部分失败: {e}")
```

**关键设计点**:
- 新增 `PipelineStage.AGENTS` 枚举值
- Agent 调度失败不阻塞 Pipeline（error isolation）
- 需要从 OUTLINE 阶段获取 `summary_id`（需要 SummaryGenerator 在 OUTLINE 阶段生成并持久化 KnowledgeSummary）
- 复用 AgentOrchestrator 现有的并行调度和覆盖率报告

### 2.2 SSE 格式兼容

Pipeline SSE 当前格式: `data: {"stage":"...", "progress": N, "message":"..."}\n\n`

在 AGENTS 阶段，同时发送：
- 传统 `data:` 格式（向后兼容旧前端）
- Agent 的 `event:` 格式（新前端可解析）

```python
# Pipeline SSE 增强
yield f"data: {json.dumps({'stage': 'agents', 'progress': 70, 'message': '...'})}\n\n"
yield f"event: agent_start\ndata: {json.dumps({'agent': 'question_bank', 'status': 'started'})}\n\n"
```

---

## 3. 前端设计

### 3.1 LanguageLearningPage

**路由**: `/language/:docId`
**菜单**: "学习中心" → "词汇学习"

**页面结构**:
```
┌──────────────────────────────────────────────┐
│  词汇学习 — [文档名]              [生成生词表] │
├──────────────────────────────────────────────┤
│  ┌─ 筛选栏 ─────────────────────────────────┐ │
│  │ [全部词性 ▼] [全部难度 ▼] [搜索...]      │ │
│  ├──────────────────────────────────────────┤ │
│  │ 单词      │ 音标    │ 释义  │ 词性 │ 难度 │ │
│  │ abandon   │ /əˈbæn/ │ 放弃  │ verb │ med  │ │
│  │ ...       │ ...     │ ...   │ ...  │ ...  │ │
│  └──────────────────────────────────────────┘ │
│  共 N 个单词  |  已掌握: M  |  掌握率: X%    │
└──────────────────────────────────────────────┘
```

**数据流**:
- 页面加载 → `getVocabulary(document_id)` → 渲染表格
- 点击"生成生词表" → `generateVocabulary(document_id, summary_id)` → 刷新表格
- 点击"标记已掌握" → `markVocabularyMastered(vocab_id)` → 更新行状态

**使用的现有 API 函数**（全部已存在于 `api.ts`）:
- `generateVocabulary(documentId, summaryId, languageType)`
- `getVocabulary(params)` — 支持 `document_id`, `part_of_speech`, `difficulty`, `search`
- `markVocabularyMastered(vocabId)`

**使用的现有类型**（全部已存在于 `types.ts`）:
- `LanguageVocabulary` 接口（word, phonetic, part_of_speech, definition, example_sentence, difficulty）

### 3.2 PipelinePage 路由注册

**修改**: `frontend/src/App.tsx`

1. 添加 lazy import:
```typescript
const PipelinePage = lazy(() => import('./pages/PipelinePage'));
```

2. 添加 Route:
```tsx
<Route path="/pipeline" element={<PipelinePage />} />
```

3. 添加菜单项（"知识管理"分组）:
```tsx
{
  key: '/pipeline',
  icon: <NodeIndexOutlined />,
  label: '处理流水线',
}
```

### 3.3 导航菜单调整

在现有 4 个分组中新增：

- "学习中心"组 → 新增 "词汇学习" (`/language`)
- "知识管理"组 → 新增 "处理流水线" (`/pipeline`)

注：`/language/:docId` 是参数化路由，菜单中需要一个默认入口。可使用 `/language` 重定向到最近的语言文档，或显示文档选择页面。

---

## 4. 测试设计

### 4.1 测试基础设施

**新建 `conftest.py`** 提供共享 fixtures：

```python
# 核心 fixtures
@pytest.fixture
def mock_db_session():
    """创建 mock AsyncSession，支持 Query/MagicMock"""
    
@pytest.fixture
def mock_api_client():
    """创建 mock UnifiedAPIClient，返回可配置的假 LLM 响应"""

@pytest.fixture
def sample_nodes():
    """构建示例 KnowledgePointNode 数据"""

@pytest.fixture  
def sample_markdown():
    """标准 3 级 Markdown 测试文本"""
```

### 4.2 测试组织

```
tests/
├── __init__.py
├── conftest.py                          # 共享 fixtures
├── test_core.py                         # (已有，不改动)
├── test_knowledge/
│   ├── __init__.py
│   ├── test_bois_analyzer.py            # ~35 测试用例
│   └── test_summary_generator.py        # ~25 测试用例
├── test_agents/
│   ├── __init__.py
│   ├── test_base.py                     # ~10 测试用例
│   ├── test_orchestrator.py             # ~12 测试用例
│   ├── test_study_plan_agent.py         # ~15 测试用例
│   ├── test_language_agent.py           # ~15 测试用例
│   ├── test_question_bank_agent.py      # ~15 测试用例
│   ├── test_flashcard_agent.py          # ~15 测试用例
│   └── test_mindmap_agent.py            # ~20 测试用例
└── test_memory/
    ├── __init__.py
    ├── test_coverage.py                 # ~15 测试用例
    └── test_feedback_loop.py            # ~15 测试用例
```

### 4.3 优先级排序

**第一批（纯函数，无 Mock 依赖）**:
1. `test_bois_analyzer.py` — 483 行纯计算逻辑，最高 ROI
2. `test_summary_generator.py` — extract_nodes_from_markdown 是所有 Agent 的 fallback 依赖
3. `test_base.py` — AgentRegistry 注册逻辑，快速建立框架信心

**第二批（需 Mock DB/LLM）**:
4. `test_study_plan_agent.py` — _build_*_plan 是纯函数，run() 需 Mock
5. `test_orchestrator.py` — 核心调度逻辑
6. `test_coverage.py` — 覆盖率计算

**第三批（复杂 Agent，多依赖）**:
7. `test_language_agent.py`
8. `test_question_bank_agent.py`
9. `test_flashcard_agent.py`
10. `test_mindmap_agent.py` — 最复杂
11. `test_feedback_loop.py`

---

## 5. 文件变更清单

### 5.1 新增文件（14 个）

```
后端测试 (13 个):
backend/tests/conftest.py
backend/tests/test_knowledge/__init__.py
backend/tests/test_knowledge/test_bois_analyzer.py
backend/tests/test_knowledge/test_summary_generator.py
backend/tests/test_agents/__init__.py
backend/tests/test_agents/test_base.py
backend/tests/test_agents/test_orchestrator.py
backend/tests/test_agents/test_study_plan_agent.py
backend/tests/test_agents/test_language_agent.py
backend/tests/test_agents/test_question_bank_agent.py
backend/tests/test_agents/test_flashcard_agent.py
backend/tests/test_agents/test_mindmap_agent.py
backend/tests/test_memory/__init__.py
backend/tests/test_memory/test_coverage.py
backend/tests/test_memory/test_feedback_loop.py

前端 (1 个):
frontend/src/pages/LanguageLearningPage.tsx
```

### 5.2 修改文件（4 个）

```
backend/app/core/pipeline.py          # 新增 PipelineStage.AGENTS，集成 AgentOrchestrator
backend/app/core/agents/orchestrator.py  # 新增 orchestrate_from_pipeline() 方法
frontend/src/App.tsx                  # 新增 /language, /pipeline 路由 + 菜单项
```

### 5.3 不需要修改的文件

- 所有 Agent 核心逻辑（QuestionBankAgent、MindMapAgent 等）— 仅添加测试
- `backend/app/models/__init__.py` — 数据模型已完整
- `backend/app/schemas.py` — Schema 已完整
- `backend/app/main.py` — 路由注册已完整
- `frontend/src/api.ts` — API 函数已完整
- `frontend/src/types.ts` — TypeScript 类型已完整

---

## 6. 技术决策与权衡

### 6.1 Pipeline 集成：松耦合 vs 重写
- **选择**: 松耦合——在 Pipeline 末尾增加一个 AGENTS 阶段调用 AgentOrchestrator
- **理由**: 不改动 AgentOrchestrator 核心，风险最小，向后兼容
- **权衡**: Pipeline 代码中多了一个调用点，未来如需完全解耦可再重构

### 6.2 QuizInteractiveAgent：新建 vs 接受现状
- **选择**: 不新建独立 Agent，接受 API 层实现
- **理由**: 交互式答题的有状态特性（session）与 Agent 的无状态 run() 模型不匹配；API 层实现更自然
- **权衡**: Agent 注册表少了一个 Agent，但不影响功能

### 6.3 测试框架：pytest + unittest.mock vs 引入 factory_boy
- **选择**: 纯 pytest + unittest.mock
- **理由**: 项目已配置 pytest，无需引入新依赖；Agent 测试的 mock 需求简单
- **权衡**: 缺少 ORM model factory，需手动构造 mock 对象

### 6.4 LanguageLearningPage 入口路由
- **选择**: `/language/:docId` + `/language` 默认入口（显示文档选择或重定向）
- **理由**: 与现有路由模式一致（如 `/summary/:id`）
- **权衡**: 需要用户先选择文档；可在 SummaryPage 的生词表标签中提供直接跳转链接
