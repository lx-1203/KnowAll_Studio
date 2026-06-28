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

- [ ] 1.1 在 PipelineStage 枚举中新增 AGENTS 阶段
  - 文件: `backend/app/core/pipeline.py`
  - 新增: `AGENTS = "agents"`

- [ ] 1.2 扩展 PipelineState 数据类
  - 文件: `backend/app/core/pipeline.py`
  - 新增字段: `summary_id: str | None = None`
  - 新增字段: `agent_results: dict | None = None`

- [ ] 1.3 在 OUTLINE 阶段保存 summary_id 到 state
  - 文件: `backend/app/core/pipeline.py`
  - 在 `_run_stage_outline()` 方法中：生成 KnowledgeSummary 后，将 summary_id 写入 state

- [ ] 1.4 在 run_full_chain 中新增 AGENTS 阶段
  - 文件: `backend/app/core/pipeline.py`
  - 在 OUTLINE 阶段完成后插入 AGENTS 阶段
  - 调用 `AgentOrchestrator.orchestrate()` 并行调度所有 Agent
  - Agent 失败不中止 Pipeline（error isolation）
  - 将 Agent 结果存入 `state.result["agent_results"]`
  - 将覆盖率报告存入 `state.result["coverage_report"]`

- [ ] 1.5 在 AgentOrchestrator 中新增 `orchestrate_from_pipeline()` 方法
  - 文件: `backend/app/core/agents/orchestrator.py`
  - 接受 document_id 和 summary_id，返回兼容 Pipeline 的结果格式
  - 自动获取 summary_id（如果未提供，从 document 查找最新的 KnowledgeSummary）

- [ ] 1.6 验证向后兼容性
  - 确保现有 `/api/v1/pipeline/run` 端点行为不变
  - 确保 SSE 事件格式兼容现有前端

---

### Phase 2a: 后端测试 — 纯函数层（可与 Phase 2b 并行）

- [ ] 2a.1 创建测试基础设施 conftest.py
  - 文件: `backend/tests/conftest.py`
  - 提供 fixtures: `mock_db_session`, `mock_api_client`, `sample_markdown`, `sample_nodes`

- [ ] 2a.2 创建 test_knowledge 目录和测试
  - 文件: `backend/tests/test_knowledge/__init__.py`

- [ ] 2a.3 编写 BOISAnalyzer 单元测试
  - 文件: `backend/tests/test_knowledge/test_bois_analyzer.py`
  - 覆盖: analyze() 各种树结构、_compute_score、_generate_suggestions、suggest_restructure、_build_category_framework
  - 预计: ~30 测试用例

- [ ] 2a.4 编写 SummaryGenerator extract_nodes 单元测试
  - 文件: `backend/tests/test_knowledge/test_summary_generator.py`
  - 覆盖: extract_nodes_from_markdown（各种 Markdown 结构）、_extract_tag、_clean_title、_compute_level_stats
  - 预计: ~20 测试用例

- [ ] 2a.5 编写 Agent 基类单元测试
  - 文件: `backend/tests/test_agents/__init__.py`
  - 文件: `backend/tests/test_agents/test_base.py`
  - 覆盖: AgentRegistry.register/get/list_all/create_all、AgentResult、BaseAgent.should_run/get_config_schema
  - 预计: ~10 测试用例

- [ ] 2a.6 编写 StudyPlanAgent 纯函数单元测试
  - 文件: `backend/tests/test_agents/test_study_plan_agent.py`
  - 覆盖: _build_short_term_plan、_build_long_term_plan、_retention_rate
  - 预计: ~10 测试用例

---

### Phase 2b: 前端页面开发（可与 Phase 2a 并行）

- [ ] 2b.1 创建 LanguageLearningPage 页面
  - 文件: `frontend/src/pages/LanguageLearningPage.tsx`
  - 功能:
    - 根据 URL param `:docId` 加载文档生词表
    - 表格展示：单词、音标、释义、词性、难度、例句
    - 筛选栏：按词性、难度过滤 + 关键词搜索
    - "生成生词表"按钮（调用 generateVocabulary）
    - "标记已掌握"操作（调用 markVocabularyMastered）
    - 统计栏：总数、已掌握数、掌握率
    - 加载状态（Spin）、空状态（Empty）、错误处理（message.error）
  - 使用: 已有的 `generateVocabulary`, `getVocabulary`, `markVocabularyMastered` API 函数
  - 使用: Ant Design Table, Tag, Button, Select, Input, Space, Card, Progress

- [ ] 2b.2 创建 LanguageLearningPage 默认入口处理
  - 当 URL 为 `/language`（无 docId）时，显示文档选择提示或重定向到最近的语言文档
  - 文件: `frontend/src/pages/LanguageLearningPage.tsx`（同一文件内处理）

---

### Phase 3a: 后端测试 — Agent 单元测试（可与 Phase 3b 并行）

- [ ] 3a.1 编写 AgentOrchestrator 单元测试
  - 文件: `backend/tests/test_agents/test_orchestrator.py`
  - 覆盖: orchestrate 并行执行、错误隔离、should_run 过滤、空 Agent 列表、覆盖率报告
  - 预计: ~12 测试用例
  - Mock: AgentRegistry.create_all, BaseAgent.run, BaseAgent.should_run

- [ ] 3a.2 编写 CoverageEngine 单元测试
  - 文件: `backend/tests/test_memory/__init__.py`
  - 文件: `backend/tests/test_memory/test_coverage.py`
  - 覆盖: calculate（各种覆盖场景）、_get_accuracy、ensure_full_coverage
  - 预计: ~15 测试用例

- [ ] 3a.3 编写 LanguageAgent 单元测试
  - 文件: `backend/tests/test_agents/test_language_agent.py`
  - 覆盖: should_run、_auto_detect_language_material、_estimate_difficulty、run（含 JSON 解析 fallback）
  - 预计: ~15 测试用例

- [ ] 3a.4 编写 QuestionBankAgent 单元测试
  - 文件: `backend/tests/test_agents/test_question_bank_agent.py`
  - 覆盖: _sample_cognitive_level、_base_difficulty_for_level、_group_by_topic、run
  - 预计: ~12 测试用例

- [ ] 3a.5 编写 FlashcardAgent 单元测试
  - 文件: `backend/tests/test_agents/test_flashcard_agent.py`
  - 覆盖: _assign_card_types、_quality_review_sample、run（含 deck 创建/复用）
  - 预计: ~12 测试用例

- [ ] 3a.6 编写 MindMapAgent 单元测试
  - 文件: `backend/tests/test_agents/test_mindmap_agent.py`
  - 覆盖: _build_mindmap、_bois_edge_enhancement、_labels_related、_nodes_to_tree_json、_flatten_tree、_score_to_grade、LLM restructure 触发条件
  - 预计: ~18 测试用例

- [ ] 3a.7 编写 FeedbackEngine 单元测试
  - 文件: `backend/tests/test_memory/test_feedback_loop.py`
  - 覆盖: scan（弱项检测、阈值、去重）、get_review_queue、mark_completed、get_memory_stats
  - 预计: ~15 测试用例

---

### Phase 3b: 前端路由集成（可与 Phase 3a 并行）

- [ ] 3b.1 在 App.tsx 中注册 LanguageLearningPage 路由
  - 文件: `frontend/src/App.tsx`
  - 新增 lazy import: `const LanguageLearningPage = lazy(() => import('./pages/LanguageLearningPage'))`
  - 新增 Route: `<Route path="/language" element={<LanguageLearningPage />} />`
  - 新增 Route: `<Route path="/language/:docId" element={<LanguageLearningPage />} />`

- [ ] 3b.2 在 App.tsx 中注册 PipelinePage 路由
  - 文件: `frontend/src/App.tsx`
  - 新增 lazy import: `const PipelinePage = lazy(() => import('./pages/PipelinePage'))`
  - 新增 Route: `<Route path="/pipeline" element={<PipelinePage />} />`

- [ ] 3b.3 更新导航菜单
  - 文件: `frontend/src/App.tsx`
  - "学习中心"组新增: 词汇学习 (`/language`, icon: `BookOutlined`)
  - "知识管理"组新增: 处理流水线 (`/pipeline`, icon: `NodeIndexOutlined`)

---

### Phase 4: 集成与验证（依赖所有 Phase）

- [ ] 4.1 运行完整测试套件
  - 执行: `cd backend && python -m pytest tests/ -v`
  - 确保所有新增测试通过
  - 确保现有 18 个测试用例无回归

- [ ] 4.2 验证 Pipeline-Agent 集成
  - 上传一份测试文档
  - 调用 `/api/v1/pipeline/run` 或 `/api/v1/pipeline/run/stream`
  - 验证 AGENTS 阶段正常执行
  - 验证 Agent 结果出现在 Pipeline 返回的 result 中
  - 验证覆盖率报告已生成

- [ ] 4.3 验证 LanguageLearningPage
  - 访问 `/language/:docId`（替换为真实的已生成生词表的文档 ID）
  - 验证表格正确展示生词数据
  - 验证筛选和搜索功能
  - 验证"标记已掌握"功能
  - 验证从 SummaryPage 生词表标签跳转

- [ ] 4.4 验证 PipelinePage
  - 访问 `/pipeline`
  - 验证页面正常渲染
  - 验证能从导航菜单访问

- [ ] 4.5 端到端流程验证
  - 上传文档 → Pipeline 处理 → 自动 Agent 调度 → 查看覆盖率报告
  - 确认整个流程无报错
