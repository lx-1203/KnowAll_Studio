# Agent 系统修复与完善 - 实现任务清单

## 并行策略

```
Phase 1: Pipeline 集成 (核心，必须先完成)
    │
    ├── Phase 2a: 后端测试 — 纯函数 (可与 Phase 2b 并行)
    ├── Phase 2b: 前端页面 (可与 Phase 2a 并行)
    │       │
    │       ├── Phase 3a: 后端测试 — Agent 单元测试 (可与 Phase 3b 并行)
    │       └── Phase 3b: 前端路由集成 (可与 Phase 3a 并行)
    │               │
    │               └── Phase 4: 端到端验证 (依赖所有 Phase)
```

- **Phase 1** 是阻塞依赖，修改 Pipeline 核心逻辑
- **Phase 2a 和 Phase 2b** 完全独立，可并行执行
- **Phase 3a 和 Phase 3b** 完全独立，可并行执行
- **Phase 4** 在所有开发完成后验证

---

### Phase 1: Pipeline-Agent 集成（必须先完成）

- [x] 1.1 在 PipelineStage 枚举中新增 AGENTS 阶段
  - 文件: `backend/app/core/pipeline.py`
  - 新增: `AGENTS = "agents"`

- [x] 1.2 扩展 PipelineState 数据类
  - 文件: `backend/app/core/pipeline.py`
  - 新增字段: `summary_id: str | None = None`
  - 新增字段: `agent_results: dict | None = None`

- [x] 1.3 在 OUTLINE 阶段后生成 KnowledgeSummary
  - 文件: `backend/app/core/pipeline.py`
  - 调用 SummaryGenerator 生成完整知识点总结
  - 持久化 KnowledgeSummary + KnowledgePointNode
  - 将 summary_id 写入 state

- [x] 1.4 在 run_full_chain 中新增 AGENTS 阶段
  - 文件: `backend/app/core/pipeline.py`
  - 在 OUTLINE 阶段完成后插入 AGENTS 阶段
  - 调用 `AgentOrchestrator.orchestrate_from_pipeline()` 并行调度所有 Agent
  - Agent 失败不中止 Pipeline（error isolation）
  - 将 Agent 结果存入 `state.result["agent_results"]`
  - 将覆盖率报告存入 `state.result["coverage_report"]`

- [x] 1.5 在 AgentOrchestrator 中新增 `orchestrate_from_pipeline()` 方法
  - 文件: `backend/app/core/agents/orchestrator.py`
  - 接受 document_id 和 summary_id，返回兼容 Pipeline 的结果格式
  - 内部调用 orchestrate()，异常安全（永不高抛）

- [x] 1.6 验证向后兼容性
  - 确保现有 `/api/v1/pipeline/run` 端点行为不变
  - 确保 SSE 事件格式兼容现有前端
  - PipelineState.result 扩展字段为增量添加

---

### Phase 2a: 后端测试 — 纯函数层（可与 Phase 2b 并行）

- [x] 2a.1 创建测试基础设施 conftest.py
  - 文件: `backend/tests/conftest.py`
  - 提供 fixtures: `mock_db_session`, `mock_api_client`, `sample_markdown`, `sample_nodes`

- [x] 2a.2 创建 test_knowledge 目录
  - 文件: `backend/tests/test_knowledge/__init__.py`

- [x] 2a.3 编写 BOISAnalyzer 单元测试 (50 测试用例)
  - 文件: `backend/tests/test_knowledge/test_bois_analyzer.py`
  - 覆盖: analyze(), _compute_balance, _compute_coverage, _compute_score, _generate_suggestions, suggest_restructure, _build_category_framework, _count_by_level, _group_by_level, _compute_peer_variance

- [x] 2a.4 编写 SummaryGenerator 单元测试 (34 测试用例)
  - 文件: `backend/tests/test_knowledge/test_summary_generator.py`
  - 覆盖: extract_nodes_from_markdown, _extract_tag, _clean_title, _clean_explanation, _compute_level_stats

- [x] 2a.5 编写 Agent 基类单元测试 (21 测试用例)
  - 文件: `backend/tests/test_agents/__init__.py`
  - 文件: `backend/tests/test_agents/test_base.py`
  - 覆盖: AgentRegistry.register/get/list_all/create_all, AgentResult, BaseAgent

- [x] 2a.6 编写 StudyPlanAgent 纯函数单元测试 (22 测试用例)
  - 文件: `backend/tests/test_agents/test_study_plan_agent.py`
  - 覆盖: _retention_rate, _build_short_term_plan, _build_long_term_plan, Ebbinghaus intervals

---

### Phase 2b: 前端页面开发（可与 Phase 2a 并行）

- [x] 2b.1 创建 LanguageLearningPage 页面 (462 行)
  - 文件: `frontend/src/pages/LanguageLearningPage.tsx`
  - 功能: 生词表展示、词性/难度筛选、关键词搜索、生成生词表、标记已掌握、统计栏
  - 使用: 已有 API 函数 (generateVocabulary, getVocabulary, markVocabularyMastered)
  - 使用: Ant Design Table, Tag, Button, Select, Input, Space, Card, Progress, Modal, Tooltip

- [x] 2b.2 LanguageLearningPage 默认入口处理
  - 无 docId 时显示 Empty 状态引导用户选择文档
  - 支持 `/language` 和 `/language/:docId` 双路由

---

### Phase 3a: 后端测试 — Agent 单元测试（可与 Phase 3b 并行）

- [x] 3a.1 编写 AgentOrchestrator 单元测试 (15 测试用例)
  - 文件: `backend/tests/test_agents/test_orchestrator.py`
  - 覆盖: orchestrate 并行执行、错误隔离、should_run 过滤、空列表、agent 筛选、orchestrate_from_pipeline

- [x] 3a.2 编写 CoverageEngine 单元测试 (15 测试用例)
  - 文件: `backend/tests/test_memory/__init__.py`
  - 文件: `backend/tests/test_memory/test_coverage.py`
  - 覆盖: calculate, _get_accuracy, ensure_full_coverage, uncovered/weak points

- [x] 3a.3 编写 LanguageAgent 单元测试 (19 测试用例)
  - 文件: `backend/tests/test_agents/test_language_agent.py`
  - 覆盖: should_run, _auto_detect_language_material, _estimate_difficulty, run (JSON 解析 fallback)

- [x] 3a.4 编写 QuestionBankAgent 单元测试 (12 测试用例)
  - 文件: `backend/tests/test_agents/test_question_bank_agent.py`
  - 覆盖: _sample_cognitive_level, _base_difficulty_for_level, _group_by_topic, run, coverage records

- [x] 3a.5 编写 FlashcardAgent 单元测试 (12 测试用例)
  - 文件: `backend/tests/test_agents/test_flashcard_agent.py`
  - 覆盖: _assign_card_types, run (deck 创建/复用/验证/质量审查/覆盖率)

- [x] 3a.6 编写 MindMapAgent 单元测试 (22 测试用例)
  - 文件: `backend/tests/test_agents/test_mindmap_agent.py`
  - 覆盖: _labels_related, _nodes_to_tree_json, _flatten_tree, _score_to_grade, _build_mindmap, _bois_edge_enhancement, run (LLM restructure 条件)

- [x] 3a.7 编写 FeedbackEngine 单元测试 (19 测试用例)
  - 文件: `backend/tests/test_memory/test_feedback_loop.py`
  - 覆盖: scan, get_review_queue, mark_completed, record_answer_result, get_memory_stats

---

### Phase 3b: 前端路由集成（可与 Phase 3a 并行）

- [x] 3b.1 在 App.tsx 中注册 LanguageLearningPage 路由
  - 文件: `frontend/src/App.tsx`
  - 新增 lazy import
  - 新增 Route: `/language` 和 `/language/:docId`

- [x] 3b.2 在 App.tsx 中注册 PipelinePage 路由
  - 文件: `frontend/src/App.tsx`
  - 新增 lazy import
  - 新增 Route: `/pipeline`

- [x] 3b.3 更新导航菜单
  - 文件: `frontend/src/App.tsx`
  - "学习中心"组新增: 词汇学习 (`/language`, `BookOutlined`)
  - "知识管理"组新增: 处理流水线 (`/pipeline`, `NodeIndexOutlined`)

---

### Phase 4: 集成与验证（依赖所有 Phase）

- [x] 4.1 运行完整测试套件
  - 结果: **257 passed**, 2 failed (均为已有的 test_core.py TestPromptEngine，与本次变更无关)
  - 新增测试: **241 个**，全部通过

- [x] 4.2 验证 Pipeline-Agent 集成
  - PipelineStage.AGENTS 已注册
  - SummaryGenerator 在 Pipeline 中集成调用
  - AgentOrchestrator.orchestrate_from_pipeline() 已实现
  - 异常隔离正确（Agent 失败不中止 Pipeline）

- [x] 4.3 验证 LanguageLearningPage
  - 页面已创建 (462 行)
  - 路由已注册
  - API 函数和类型均已就绪

- [x] 4.4 验证 PipelinePage
  - 路由已注册
  - 导航菜单入口已添加

- [x] 4.5 代码无回归
  - 不修改任何现有 Agent 核心逻辑
  - 不修改数据模型
  - 不修改现有 API 端点签名
