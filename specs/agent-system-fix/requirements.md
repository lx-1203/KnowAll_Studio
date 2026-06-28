# Agent 系统修复与完善 - 需求文档

## 1. 功能概述

对 KnowAll_Studio 现有 Agent 系统进行修复和完善，解决 6 个关键缺口：

1. **Pipeline 与 Agent 系统集成**：旧 PipelineOrchestrator 与新 AgentOrchestrator 各自独立运行，上传文件后 Pipeline 完成知识点生成即终止，不会自动触发 Agent 并行调度
2. **前端 LanguageLearningPage 缺失**：后端 LanguageAgent 和 API 已完整实现，但前端无对应页面，SummaryPage 中的语言学习入口链接失效
3. **PipelinePage 未路由**：文件已存在但未注册路由和导航入口
4. **后端测试覆盖为零**：Agent 系统（~1500 行）、Memory 系统（~480 行）、Knowledge 系统（~720 行）均无任何测试
5. **QuizInteractiveAgent 未注册**：设计文档规划的独立交互式答题 Agent 未实现，功能拆分在 API 层
6. **前端组件内联化**：设计文档规划的 5 个独立组件未抽取

---

## 2. 用户故事

### 2.1 Pipeline-Agent 集成

**US-01**: 作为学生，我上传一份教材 PDF 后，希望系统在生成知识点总结后，自动为我生成配套练习题、思维导图和学习计划，而不需要我手动去每个功能页面逐个触发。

**US-02**: 作为学生，我希望在上传页面就能看到完整的处理进度——从解析文档到生成知识点，再到各个 Agent 并行工作的全过程。

### 2.2 前端页面补全

**US-03**: 作为语言学习者，当我上传英语/日语学习材料后，希望有一个专门的词汇学习页面，可以查看生词表、听发音、标记已掌握的单词。

**US-04**: 作为学生，我希望在知识点总结页面点击"生词表"标签时，能正常跳转到词汇学习页面，而不是看到一个空白页。

**US-05**: 作为学生，我希望能在侧边栏菜单中找到"数据处理流水线"入口，查看文档处理的完整进度。

### 2.3 后端测试

**US-06**: 作为开发者，我希望 Agent 系统有完整的单元测试覆盖，确保题库生成、思维导图构建、学习计划生成等核心功能在代码变更后不会退化。

**US-07**: 作为开发者，我希望 BOIS 分析器和 Markdown 节点提取器等纯计算模块有充分的测试，因为它们是所有 Agent 的基础依赖。

---

## 3. 验收标准

### 3.1 Pipeline-Agent 集成

| 编号 | Given | When | Then |
|------|-------|------|------|
| AC-01 | 用户上传一份文档并触发 Pipeline | Pipeline 完成知识点总结生成 | 自动调用 AgentOrchestrator 并行执行已注册的 Agent |
| AC-02 | Pipeline 进入 Agent 调度阶段 | SSE 流推送进度 | 前端能收到各 Agent 的启动/进度/完成事件 |
| AC-03 | 某个 Agent 执行失败 | 其他 Agent 继续执行 | 失败的 Agent 返回错误信息，不影响其他 Agent 结果 |
| AC-04 | LanguageAgent.should_run() 返回 false | Pipeline 调度 Agent | LanguageAgent 被标记为 skipped，其余 Agent 正常运行 |

### 3.2 LanguageLearningPage

| 编号 | Given | When | Then |
|------|-------|------|------|
| AC-05 | 用户上传了英语学习材料并已生成生词表 | 访问 `/language/:docId` | 展示完整的生词表（单词、音标、释义、例句、词性、难度） |
| AC-06 | 生词表页面加载完成 | 用户点击某个单词行 | 显示单词详情（翻转卡片效果），包含完整释义和例句 |
| AC-07 | 用户查看生词表 | 点击"标记已掌握"按钮 | 该单词状态更新，视觉上标记为已掌握 |
| AC-08 | 用户从 SummaryPage 的生词表标签页 | 点击"打开完整词汇页面" | 正确跳转到 `/language/:docId` 页面 |

### 3.3 PipelinePage 路由

| 编号 | Given | When | Then |
|------|-------|------|------|
| AC-09 | 用户登录系统 | 查看侧边栏导航 | "数据处理流水线"入口显示在"知识管理"分组中 |
| AC-10 | 用户点击流水线菜单 | 导航到 `/pipeline` | 显示 PipelinePage，可选择文档并查看处理进度 |

### 3.4 后端测试

| 编号 | Given | When | Then |
|------|-------|------|------|
| AC-11 | 运行 `pytest backend/tests/` | 测试执行完成 | Agent 系统测试覆盖率 ≥ 80%（纯函数 100%） |
| AC-12 | `extract_nodes_from_markdown` 接收 3 级 Markdown | 调用函数 | 正确解析 H1/H2/H3 层级，生成正确的 parent_id 和 auto-id |
| AC-13 | BOISAnalyzer 接收完美平衡的 3 级树 | 调用 analyze() | 返回 score ≥ 85 |
| AC-14 | AgentOrchestrator 并行执行 3 个 Agent | 一个 Agent 抛异常 | 其余 2 个正常完成，异常 Agent 返回 error 状态 |

---

## 4. 非功能性需求

### 4.1 性能
- Pipeline → Agent 调度增量不超过 3 秒
- 测试套件完整运行 < 60 秒（不含集成测试）
- LanguageLearningPage 首屏加载 < 2 秒

### 4.2 可靠性
- Pipeline 集成后向后兼容：现有 `/api/v1/pipeline/run` 端点行为不变
- 测试不依赖外部 LLM API（全部 mock）
- 前端新页面使用与现有页面一致的错误处理模式

### 4.3 可维护性
- 测试文件按模块组织：`tests/test_agents/`, `tests/test_memory/`, `tests/test_knowledge/`
- 抽取共享的测试 fixtures（mock DB session, mock LLM client）
- 前端新页面遵循现有代码风格（Ant Design + React Hooks + TypeScript）

---

## 5. 影响范围

### 5.1 新增文件

| 文件 | 说明 |
|------|------|
| `backend/tests/conftest.py` | 共享测试 fixtures（mock DB, mock LLM） |
| `backend/tests/test_agents/test_base.py` | AgentRegistry + BaseAgent 单元测试 |
| `backend/tests/test_agents/test_orchestrator.py` | AgentOrchestrator 单元测试 |
| `backend/tests/test_agents/test_study_plan_agent.py` | StudyPlanAgent 测试 |
| `backend/tests/test_agents/test_language_agent.py` | LanguageAgent 测试 |
| `backend/tests/test_agents/test_mindmap_agent.py` | MindMapAgent 测试 |
| `backend/tests/test_agents/test_question_bank_agent.py` | QuestionBankAgent 测试 |
| `backend/tests/test_agents/test_flashcard_agent.py` | FlashcardAgent 测试 |
| `backend/tests/test_knowledge/test_bois_analyzer.py` | BOISAnalyzer 纯函数测试 |
| `backend/tests/test_knowledge/test_summary_generator.py` | SummaryGenerator + extract_nodes 测试 |
| `backend/tests/test_memory/test_feedback_loop.py` | FeedbackEngine 测试 |
| `backend/tests/test_memory/test_coverage.py` | CoverageEngine 测试 |
| `backend/tests/__init__.py` | (已存在，为空) |
| `frontend/src/pages/LanguageLearningPage.tsx` | 词汇学习页面 |

### 5.2 修改文件

| 文件 | 修改内容 |
|------|----------|
| `backend/app/core/pipeline.py` | 在知识点总结生成完成后，集成 AgentOrchestrator 调度 |
| `backend/app/core/agents/orchestrator.py` | 新增 `orchestrate_from_pipeline()` 方法，兼容 Pipeline 的 SSE 格式 |
| `frontend/src/App.tsx` | 新增 `/language/:docId` 和 `/pipeline` 路由，导航菜单新增入口 |
| `frontend/src/api.ts` | (LanguageLearningPage 所需 API 函数已存在，无需修改) |
| `frontend/src/types.ts` | (所需类型已存在，无需修改) |
| `backend/app/main.py` | (路由注册已存在，无需修改) |

### 5.3 不涉及的模块
- 用户认证系统
- 文档解析模块
- 向量搜索模块
- 游戏模块
- Electron 桌面包装
- 已有的 4 个 Agent 核心逻辑（仅添加测试，不修改实现）
