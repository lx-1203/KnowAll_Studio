# 系统功能完善 - 实现任务清单

## 并行策略

```
Phase 1 (后端低风险修复) ──── 可完全并行 ────┐
Phase 2 (算法修复) ────── 可完全并行 ────────┤ 全部完成后进入
Phase 3 (Pipeline 修复) ── 可完全并行 ───────┤ Phase 4
Phase 4 (分页) ────────── 后端+前端可并行 ───┘
Phase 5 (集成验证)
```

---

### Phase 1: 后端低风险修复 ✅

- [x] 1.1 US-01: 上传返回有效 chunk ID
  - 文件: `backend/app/api/documents.py`
  - 方案: 在插入循环中收集 ORM 对象，flush 后用 ORM 对象构建响应

- [x] 1.2 US-10: 分享 question_bank 验证
  - 文件: `backend/app/api/share.py`
  - 方案: 添加 QuestionBank 存在性查询

- [x] 1.3 US-08: 流式对话会话修复
  - 文件: `backend/app/api/chat.py`
  - 方案: generator 内创建独立 session，复用 pipeline.py 模式

- [x] 1.4 US-02: 文档删除时清理 ChromaDB 向量
  - 文件: `backend/app/core/rag.py`, `backend/app/api/documents.py`
  - 方案: rag.py 新增 delete_vectors_by_doc_id，documents.py 的 delete 中调用

---

### Phase 2: 算法修复 ✅

- [x] 2.1 US-04: 严格文本答案检查
  - 文件: `backend/app/core/quiz/__init__.py`
  - 方案: 替换子串匹配为关键词覆盖率检查（空答案/单字符拒绝，50% 关键词重叠阈值）

- [x] 2.2 US-06: FSRS 使用 w 参数
  - 文件: `backend/app/core/memory/__init__.py`
  - 方案: _difficulty_delta、_stability_increase、_first_review 全部引用 self.w

---

### Phase 3: Pipeline 修复 ✅

- [x] 3.1 US-03: 解除 chunk[:5] 限制
  - 文件: `backend/app/core/pipeline.py`, `backend/app/api/questions.py`
  - 方案: 按 MAX_CHARS=12000 字符预算智能截断

- [x] 3.2 US-05: Pipeline 增加大纲阶段
  - 文件: `backend/app/core/pipeline.py`, `frontend/src/components/PipelineProgress.tsx`
  - 方案: 在知识树和题库之间插入 outline 生成（进度 30%→40%）

- [x] 3.3 US-07 + US-09: Pipeline 去重 + 溯源修复
  - 文件: `backend/app/core/pipeline.py`
  - 方案: generation_cache_key 去重 + source_chunk_id 修正（合并文本→None）

---

### Phase 4: 分页 ✅

- [x] 4.1 US-11: 后端分页（6 个 API 文件）
  - 文件: `backend/app/api/documents.py`, `flashcards.py`, `knowledge.py`, `questions.py`, `study.py`, `share.py`
  - 方案: 统一添加 limit/offset 参数（默认 limit=1000，向后兼容）

- [x] 4.2 US-11: 前端分页（6 个页面组件 + api.ts）
  - 文件: `frontend/src/api.ts`, `UploadPage.tsx`, `KnowledgePage.tsx`, `QuizPage.tsx`, `FlashcardPage.tsx`, `StudyPage.tsx`, `SharePage.tsx`
  - 方案: 各列表页添加 Ant Design Table 分页

---

### Phase 5: 集成与验证 ✅

- [x] 5.1 全面检查所有修改的文件
- [x] 5.2 验证后端服务正常启动 — 78 routes, imports OK
- [x] 5.3 验证前端构建通过 — npx tsc --noEmit: 0 errors
- [x] 5.4 端到端流程验证（文档上传→知识树→题库→闪卡→删除→分享）
