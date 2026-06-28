# 知识点学习系统增强 - 实现任务清单

## 并行策略

```
Phase 1 (数据层) ── 必须先完成
    │
    ├── Phase 2 (后端核心) ── 依赖 Phase 1
    │       │
    │       ├── Phase 3a (后端 API)   ── 可与 Phase 3b 并行
    │       └── Phase 3b (前端页面)   ── 可与 Phase 3a 并行(用 Mock 先行)
    │               │
    │               └── Phase 4 (集成验证) ── 依赖 Phase 3a + 3b
```

- **Phase 1** 是阻塞依赖，必须最先完成
- **Phase 2** 依赖 Phase 1 的数据模型
- **Phase 3a 和 Phase 3b** 可以并行执行
- **Phase 4** 在所有开发完成后集成

---

### Phase 1: 数据层（必须先完成）

- [ ] 1.1 新增数据模型到 `backend/app/models/__init__.py`
  - 文件: `backend/app/models/__init__.py`
  - 新增: `KnowledgeSummary`, `KnowledgePointNode`, `KnowledgeCoverage`, `ReviewQueue`, `LanguageVocabulary`
  - 扩展: `AnswerRecord` (+time_spent_ms, +attempt_count, +knowledge_point_ids, +is_review_queue)
  - 扩展: `Flashcard` (+knowledge_point_id, +review_count, +correct_count, +last_review_at, +accuracy_rate)
  - 扩展: `StudyPlan` (+plan_type, +ebbinghaus_nodes, +daily_hours, +knowledge_point_ids)

- [ ] 1.2 创建数据库迁移文件
  - 文件: `backend/alembic/versions/xxxx_enhance_knowledge_system.py`
  - 包含所有新增表和字段变更

- [ ] 1.3 更新 Pydantic Schema
  - 文件: `backend/app/schemas.py`
  - 新增: `KnowledgeSummaryCreate/Response`, `KnowledgePointNodeResponse`, `CoverageReportResponse`, `ReviewQueueItemResponse`, `LanguageVocabularyResponse`, `AgentOrchestrateRequest/Response`, `InteractiveAnswerSubmit/Response`, `MemoryStatsResponse`, `StudyPlanEnhancedRequest/Response`

- [ ] 1.4 更新前端 TypeScript 类型
  - 文件: `frontend/src/types.ts`
  - 新增接口: `KnowledgeSummary`, `KnowledgePointNode`, `CoverageReport`, `ReviewQueueItem`, `LanguageVocabulary`, `MindMapData`, `AgentOrchestrateConfig`, `InteractiveQuizState`, `MemoryStats`, `StudyPlanEnhanced`

---

### Phase 2: 后端核心引擎（依赖 Phase 1）

- [ ] 2.1 创建知识点总结生成器
  - 文件: `backend/app/core/knowledge/summary_generator.py`
  - 类: `SummaryGenerator`
  - 方法: `generate(document_id, max_depth=3)` → 流式输出完整 Markdown
  - 逻辑: 加载文档 chunks → 组装 prompt（注入 native outline 做结构引导）→ LLM 生成 → 解析 Markdown 提取节点 → 写入 `knowledge_summaries` + `knowledge_point_nodes`

- [ ] 2.2 创建知识点总结提示词模板
  - 文件: `backend/app/prompts/summary.yaml`
  - 模板: `full_summary` — 要求 LLM 输出完整 Markdown（3级标题+知识点详解+关联概念+示例）
  - 约束: 不限制输出长度，宁可多生成不可遗漏；每个三级知识点必须包含4要素

- [ ] 2.3 创建 Agent 基类和调度器
  - 文件: `backend/app/core/agents/__init__.py`
  - 文件: `backend/app/core/agents/base.py` — `BaseAgent` 抽象类（run/sse_run 方法）
  - 文件: `backend/app/core/agents/orchestrator.py` — `AgentOrchestrator` 类
  - 调度逻辑: `asyncio.TaskGroup` 并行启动所有注册 Agent → 收集结果 → SSE 流式推送进度 → 写入 coverage 映射 → 返回汇总 + 覆盖率报告

- [ ] 2.4 创建题库生成 Agent
  - 文件: `backend/app/core/agents/question_bank_agent.py`
  - 类: `QuestionBankAgent(BaseAgent)`
  - 逻辑: 遍历知识点节点 → 按知识点分组调用 `QuizGenerator` → 每道题写入 `knowledge_coverage` 表（resource_type='question'）→ 确保每知识点 ≥ 1 道基础题

- [ ] 2.5 创建思维导图 Agent
  - 文件: `backend/app/core/agents/mindmap_agent.py`
  - 类: `MindMapAgent(BaseAgent)`
  - 逻辑: 读取 `knowledge_point_nodes` → 构建 parent-child 树结构 → 添加跨知识点关联边（复用现有 `knowledge_edges`）→ 输出 ReactFlow 兼容 JSON

- [ ] 2.6 创建外语学习 Agent
  - 文件: `backend/app/core/agents/language_agent.py`
  - 类: `LanguageAgent(BaseAgent)`
  - 逻辑: 检测文档语言类型（LLM + Unicode 范围双通道）→ 非语言类材料自动跳过 → 语言类材料：提取生词 + 调用 LLM 生成音标/释义/例句/词性 → 写入 `language_vocabulary` 表

- [ ] 2.7 创建外语学习提示词模板
  - 文件: `backend/app/prompts/language.yaml`
  - 模板: `vocabulary_extract` — 从知识点文本中提取生词，输出 JSON 数组

- [ ] 2.8 创建学习计划 Agent
  - 文件: `backend/app/core/agents/study_plan_agent.py`
  - 类: `StudyPlanAgent(BaseAgent)`
  - 逻辑: 读取知识点总结 → 按知识点数量和难度分配学时 → 短期计划（1-3天按小时排程）→ 长期计划（1-4周按天排程）→ 嵌入艾宾浩斯复习节点（day 1/2/4/7/15）→ 写入增强的 `study_plans` 表

- [ ] 2.9 创建覆盖率计算引擎
  - 文件: `backend/app/core/memory/coverage.py`
  - 类: `CoverageEngine`
  - 方法: `calculate(summary_id)` → 统计 total / covered_by_questions / covered_by_flashcards / full_coverage → 返回 `CoverageReport`

- [ ] 2.10 创建记忆回流反馈引擎
  - 文件: `backend/app/core/memory/feedback_loop.py`
  - 类: `FeedbackEngine`
  - 方法: `scan(user_id, threshold=0.7)` → 查询所有答题记录和记忆卡 → 计算每知识点正确率 → 低于阈值 → 推入 `review_queue`
  - 方法: `get_review_queue(user_id, limit=20)` → 按优先级排序返回
  - 方法: `mark_completed(queue_id)` → 标记完成

- [ ] 2.11 扩展现有 `KnowledgeGenerator`
  - 文件: `backend/app/core/knowledge/__init__.py`
  - 新增方法: `generate_summary()` 委托给 `SummaryGenerator`
  - 新增方法: `extract_nodes_from_markdown(content_md)` → 解析 Markdown 标题层级提取节点

- [ ] 2.12 扩展现有 `FSRS` 和 `FlashcardGenerator`
  - 文件: `backend/app/core/memory/__init__.py`
  - `FSRS`: 新增 `record_answer_result(card_id, is_correct)` → 更新 `accuracy_rate` + `review_count`
  - `FlashcardGenerator`: generate 时自动关联 `knowledge_point_id` + 写入 `knowledge_coverage`

- [ ] 2.13 扩展 `ExamEngine` 判分逻辑
  - 文件: `backend/app/core/quiz/__init__.py`
  - grade 方法新增: 接收 `time_spent_ms` 和 `knowledge_point_ids` 参数 → 写入扩展字段

---

### Phase 3a: 后端 API 层（可与 Phase 3b 并行）

- [ ] 3a.1 新增知识点总结 API 端点
  - 文件: `backend/app/api/knowledge.py`（扩展现有文件）
  - 端点: `POST /api/v1/knowledge/summary/generate` (SSE)
  - 端点: `GET /api/v1/knowledge/summary/{summary_id}`
  - 端点: `GET /api/v1/knowledge/summary/{summary_id}/nodes`
  - 端点: `GET /api/v1/knowledge/summary/{summary_id}/mindmap`

- [ ] 3a.2 新增 Agent 调度 API
  - 文件: `backend/app/api/agents.py`
  - 端点: `POST /api/v1/agents/orchestrate` (SSE)
  - 端点: `GET /api/v1/agents/status/{task_id}`

- [ ] 3a.3 新增交互式答题 API
  - 文件: `backend/app/api/interactive_quiz.py`
  - 端点: `GET /api/v1/quiz/interactive/start?summary_id=&count=&mode=`
  - 端点: `POST /api/v1/quiz/interactive/submit`
  - 端点: `GET /api/v1/quiz/interactive/session/{session_id}/stats`

- [ ] 3a.4 新增外语学习 API
  - 文件: `backend/app/api/language.py`
  - 端点: `POST /api/v1/language/vocabulary/generate`
  - 端点: `GET /api/v1/language/vocabulary?document_id=&summary_id=`
  - 端点: `PATCH /api/v1/language/vocabulary/{vocab_id}` (标记已掌握)

- [ ] 3a.5 新增覆盖率报告 API
  - 文件: `backend/app/api/coverage.py`
  - 端点: `GET /api/v1/knowledge/summary/{summary_id}/coverage`
  - 端点: `POST /api/v1/knowledge/coverage/refresh` (强制刷新覆盖率)

- [ ] 3a.6 新增记忆反馈 API
  - 文件: `backend/app/api/memory_feedback.py`
  - 端点: `POST /api/v1/memory/feedback/scan`
  - 端点: `GET /api/v1/memory/review-queue`
  - 端点: `POST /api/v1/memory/review-queue/{queue_id}/complete`
  - 端点: `GET /api/v1/memory/stats`

- [ ] 3a.7 增强学习计划 API
  - 文件: `backend/app/api/study.py`（扩展现有文件）
  - 端点: `POST /api/v1/study/generate-plan-enhanced`
  - 端点: `GET /api/v1/study/plans/{plan_id}/ebbinghaus` (查看复习节点)

- [ ] 3a.8 注册所有新路由
  - 文件: `backend/app/main.py`
  - 新增 router 注册: agents, language, interactive_quiz, coverage, memory_feedback

---

### Phase 3b: 前端页面（可与 Phase 3a 并行）

- [ ] 3b.1 新增知识点总结展示页面
  - 文件: `frontend/src/pages/SummaryPage.tsx`
  - 功能: 左侧 Markdown TOC 目录导航 + 右侧 Markdown 渲染正文
  - 组件: `MarkdownTOC` (侧边栏目录)

- [ ] 3b.2 新增 Markdown 目录导航组件
  - 文件: `frontend/src/components/MarkdownTOC.tsx`
  - 功能: 解析 Markdown 标题 → 生成可折叠目录树 → 点击跳转

- [ ] 3b.3 新增知识点卡片组件
  - 文件: `frontend/src/components/KnowledgePointCard.tsx`
  - 功能: 卡片式展示知识点（名称/解释/关联概念/示例）→ 悬浮操作按钮（生成题目/添加到复习）

- [ ] 3b.4 新增思维导图页面
  - 文件: `frontend/src/pages/MindMapPage.tsx`
  - 文件: `frontend/src/components/MindMapViewer.tsx`
  - 功能: ReactFlow 渲染层级思维导图 → 节点展开/折叠 → 缩放/平移 → 导出图片

- [ ] 3b.5 新增交互式答题页面
  - 文件: `frontend/src/pages/InteractiveQuizPage.tsx`
  - 文件: `frontend/src/components/InteractiveQuestionCard.tsx`
  - 功能: 逐题显示 → 选择/输入答案 → 即时判分 → 显示解析 → 进度条 → 完成统计

- [ ] 3b.6 新增外语学习页面
  - 文件: `frontend/src/pages/LanguageLearningPage.tsx`
  - 文件: `frontend/src/components/VocabularyTable.tsx`
  - 功能: 生词表（可排序/过滤）→ 单词卡片翻转 → 发音按钮 → 标记已掌握

- [ ] 3b.7 新增覆盖率报告页面
  - 文件: `frontend/src/pages/CoverageReportPage.tsx`
  - 文件: `frontend/src/components/CoverageChart.tsx`
  - 功能: 覆盖率饼图 → 已覆盖/未覆盖知识点列表 → 薄弱知识点突出显示 → 一键生成补充题目

- [ ] 3b.8 新增复习队列面板组件
  - 文件: `frontend/src/components/ReviewQueuePanel.tsx`
  - 功能: 优先级排序的复习列表 → 点击进入复习模式 → 完成标记 → 统计更新

- [ ] 3b.9 新增学习计划时间轴组件
  - 文件: `frontend/src/components/StudyPlanTimeline.tsx`
  - 功能: 短期（小时刻度）/长期（天刻度）时间轴 → 艾宾浩斯节点标记 → 进度追踪

- [ ] 3b.10 扩展前端 API 客户端
  - 文件: `frontend/src/api.ts`
  - 新增 ~15 个 API 函数: `generateSummary`, `getSummary`, `getMindmapData`, `orchestrateAgents`, `startInteractiveQuiz`, `submitInteractiveAnswer`, `generateVocabulary`, `getVocabulary`, `getCoverageReport`, `scanFeedback`, `getReviewQueue`, `completeReviewItem`, `getMemoryStats`, `generateEnhancedPlan`, `getEbbinghausNodes`

- [ ] 3b.11 扩展前端状态管理
  - 文件: `frontend/src/stores/index.ts`
  - 新增: `useSummaryStore` (summary/nodes/mindmap loading)
  - 新增: `useMemoryStore` (reviewQueue/coverageReport/memoryStats)
  - 新增: `useInteractiveQuizStore` (currentQuestion/answers/stats)

- [ ] 3b.12 更新前端路由和导航
  - 文件: `frontend/src/App.tsx`
  - 新增路由: `/summary/:id`, `/mindmap/:summaryId`, `/quiz/interactive/:summaryId`, `/language/:docId`, `/coverage/:summaryId`
  - 导航菜单: 在现有侧边栏中增加"知识点总结""思维导图""交互式答题""词汇学习""覆盖率报告"入口

---

### Phase 4: 集成与验证（依赖 Phase 3a + 3b）

- [ ] 4.1 重构 Pipeline 集成 Agent 调度
  - 文件: `backend/app/core/pipeline.py`
  - 将现有顺序执行的 5 阶段改为: Parse → Summary Generate → Agent Orchestrator 并行调度
  - SSE 事件格式兼容现有前端

- [ ] 4.2 前后端联调
  - 验证文件上传 → 知识点总结生成 → 并行 Agent 调度 → 覆盖率报告 完整流程
  - 验证交互式答题 → 记忆记录 → 回流反馈 → 复习队列推送 闭环流程
  - 验证外语学习 Agent 对语言类/非语言类文档的自动识别

- [ ] 4.3 覆盖率全映射校验
  - 测试: 生成 50 个知识点 → 验证至少 50 道基础题 + 50 张记忆卡
  - 测试: 覆盖率报告数据准确（total/covered/uncovered 数量一致）

- [ ] 4.4 端到端流程验证
  - 上传一份 50+ 页教材 PDF
  - 生成完整知识点总结（验证无遗漏、层级正确）
  - 自动触发 5 个并行 Agent（验证全部成功完成）
  - 查看覆盖率报告（验证 100% 覆盖）
  - 进行交互式答题 20 题（验证即时判分和解析）
  - 查看复习队列（验证薄弱知识点已推送）
  - 查看学习计划（验证艾宾浩斯节点）

- [ ] 4.5 运行现有测试确保无回归
  - 文件: `backend/tests/`
  - 运行 `pytest` 确保现有测试用例通过
  - 修复因数据模型变更导致的测试失败

- [ ] 4.6 运行数据库迁移
  - 执行 `alembic upgrade head` 确保迁移脚本正常运行
  - 验证新旧表结构兼容
