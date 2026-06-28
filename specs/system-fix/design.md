# 系统功能完善 - 技术设计文档

## 1. 架构概述

本项目为 FastAPI + React + SQLite + ChromaDB 三层架构。修复涉及后端 API 层、核心业务逻辑层、数据访问层的局部修改，不引入新依赖或新架构模式。

**关键原则**：
- 修改最小化：每个修复只改变必要的代码
- 模式复用：使用项目已有的编码模式（如 chat.py 的分页模式、pipeline.py 的独立 session 管理）
- 向后兼容：优先保持现有 API 契约不变

## 2. 数据模型变更

### 2.1 DocumentChunk.vector_id 填充（US-02）

现有列 `vector_id` 已定义但从未填充。修改 `index_document_chunks` 在索引时回写 `vector_id`。

```python
# backend/app/api/search.py - index_document_chunks
# 索引后更新 DB 中的 vector_id
for i, chunk in enumerate(chunks):
    chunk.vector_id = ids[i]  # ChromaDB 返回的 ID
await db.commit()
```

### 2.2 去重字段利用（US-07）

现有 `generation_cache_key` 列已定义但未使用。修改方案：基于 `(document_id, question_type, difficulty)` 组合生成缓存 key，存入 `generation_cache_key`。Pipeline 运行前先检查是否存在相同 key 的记录。

## 3. 接口设计

### 3.1 US-01: 上传返回有效 chunk ID

**文件**: `backend/app/api/documents.py`

**变更**: 在插入 DocumentChunk ORM 对象时收集引用，用 ORM 对象构建响应而非解析器返回的 dataclass。

```python
# Before (line 93-121):
for chunk in chunks:
    db.add(DocumentChunk(...))
# ... later uses `chunks` (parser objects) for response

# After:
orm_chunks = []
for chunk in chunks:
    orm_chunk = DocumentChunk(...)
    db.add(orm_chunk)
    orm_chunks.append(orm_chunk)
await db.flush()  # 生成 ID
# 用 orm_chunks 构建响应
```

### 3.2 US-02: 向量清理

**文件**: `backend/app/core/rag.py`（新增方法）、`backend/app/api/documents.py`（调用）

**rag.py 新增**:
```python
def delete_vectors_by_doc_id(doc_id: str) -> int:
    """删除与文档关联的所有向量"""
    collection = get_or_create_collection()
    collection.delete(where={"doc_id": doc_id})
```

**documents.py 变更**: 在 `delete_document()` 中调用 `delete_vectors_by_doc_id(doc_id)`。

### 3.3 US-03: 全部 chunk 参与生成

**文件**: `backend/app/api/questions.py`、`backend/app/core/pipeline.py`

**方案**: 不再硬编码 `[:5]`，改为按 token 预算智能截断。引入配置 `max_generation_tokens` 限制单次 LLM 输入的文本量。

```python
# 计算每个 chunk 的 token 数，合并直到接近上限
MAX_INPUT_TOKENS = 8000  # 留出 prompt + response 空间
combined = ""
for text in chunk_texts:
    if token_count(combined + text) > MAX_INPUT_TOKENS:
        break
    combined += text + "\n\n"
```

如果 chunk 总量超限，分批生成然后合并结果。

### 3.4 US-04: 严格答案检查

**文件**: `backend/app/core/quiz/__init__.py`

**方案**: 替换子串匹配为更严格的规则：

```python
# 对于 short_answer / fill_blank / material_analysis:
# 1. 空答案 → 错误
# 2. 单字符答案 → 错误（除非正确答案也是单字符）
# 3. 关键词覆盖检查：提取正确答案的关键词，检查用户答案是否覆盖了大部分关键词
# 4. 如果仍未确定，使用简单的编辑距离相似度（> 0.6 才算对）
```

使用 Python 标准库 `difflib.SequenceMatcher`（无需额外依赖）进行相似度计算。

### 3.5 US-05: Pipeline 大纲阶段

**文件**: `backend/app/core/pipeline.py`

在 `run_full_chain()` 的知识树阶段 (35%) 和题库阶段 (40%) 之间插入大纲生成：

```python
# Stage 2.5: Generate outline
yield self._progress(state, PipelineStage.OUTLINE, 37, "正在生成知识大纲...")
try:
    outline_md = await knowledge_generator.generate_outline(state.chunk_texts, model)
    async with async_session() as db:
        outline = Outline(title=f"Outline-{document_id[:8]}", content_markdown=outline_md)
        db.add(outline)
        await db.commit()
        state.outline_id = outline.id
except Exception as e:
    yield self._error(state, PipelineStage.OUTLINE, str(e))
    return
```

`PipelineState` 数据类新增 `outline_id: str = ""` 字段。

### 3.6 US-06: FSRS 使用 w 参数

**文件**: `backend/app/core/memory/__init__.py`

将硬编码值替换为基于 `self.w` 的计算。FSRS-5 的核心公式：

```python
# 稳定性增长 = w[6] * (1 + w[8])^w[7] 等
# 具体实现参考 open-spaced-repetition/fsrs4anki 的 Python 参考实现
```

由于完整的 FSRS 算法相当复杂，本次修复采用**最小化改进方案**：将 `_difficulty_delta` 和 `_stability_increase` 中的硬编码数字替换为 `self.w[i]` 引用，至少让已定义的参数生效。

```python
def _difficulty_delta(self, rating: int) -> float:
    return {
        self.AGAIN: self.w[4],   # 原 0.15
        self.HARD: self.w[5],    # 原 0.05
        self.GOOD: -self.w[4],   # 对称
        self.EASY: -self.w[6],   # 原 -0.15
    }[rating]
```

### 3.7 US-07: Pipeline 去重

**文件**: `backend/app/core/pipeline.py`

**方案**: 在 `run_full_chain()` 开始时检查 `generation_cache_key`：

```python
# 生成 cache key
cache_key = f"{document_id}:{question_type}:{difficulty}:{card_type}"
# 检查是否已存在
from sqlalchemy import select
async with async_session() as db:
    result = await db.execute(
        select(KnowledgeTree).where(KnowledgeTree.generation_cache_key == cache_key)
    )
    if result.scalar_one_or_none():
        # 已有结果，跳过或返回已有数据
        ...
```

`KnowledgeTree.generation_cache_key` 在创建时设置为 `cache_key`。

### 3.8 US-08: 流式会话修复

**文件**: `backend/app/api/chat.py`

**方案**: 复用 pipeline.py 的独立 session 管理模式。在 generator 内部创建新的 session：

```python
async def event_generator():
    from app.database import async_session
    full_response = ""
    try:
        async for chunk in ai_assistant.chat_stream(...):
            full_response += chunk
            yield f"data: ..."
        # 使用独立 session 保存
        async with async_session() as save_db:
            save_db.add(Message(...))
            await save_db.commit()
    except Exception as e:
        yield f"data: ..."
```

### 3.9 US-09: 题目溯源

**文件**: `backend/app/core/pipeline.py`、`backend/app/api/questions.py`

**方案**: 改为让 LLM 以 chunk-indexed 方式生成，或在生成后通过文本相似度匹配将每道题关联到最相关的 chunk。

**实施简化方案**: 既然每道题都关联到它从中生成的知识段落，如果使用合并文本生成，则将 `source_chunk_id` 设为 None（表示多源），而不是错误地指向第一个 chunk。

```python
# 使用合并文本 → 标记为复合来源
source_chunk_id=None  # 表示来自多个 chunk 的综合内容
```

### 3.10 US-10: 分享验证

**文件**: `backend/app/api/share.py`

**变更**: 在第 42-46 行添加实际的 QuestionBank 查询：

```python
elif req.resource_type == "question_bank":
    result = await db.execute(
        select(QuestionBank).where(QuestionBank.id == req.resource_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Question not found")
```

### 3.11 US-11: 列表分页

**文件**: 6 个 API 文件 + 1 个前端文件

**方案**: 复用 chat.py:106 的 `limit` + `offset` 模式。

**后端统一模式**:
```python
@router.get("/")
async def list_items(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Model).order_by(Model.created_at.desc()).offset(offset).limit(limit)
    )
    items = result.scalars().all()
    # 返回 total count 以便前端分页
    count_result = await db.execute(select(func.count(Model.id)))
    total = count_result.scalar() or 0
    return {"items": [...], "total": total, "limit": limit, "offset": offset}
```

**前端**: 各列表页面添加 Ant Design `Pagination` 组件或使用 `Table` 组件的分页功能。

## 4. 前端设计

### 4.1 分页 UI（US-11）

使用 Ant Design 的 `Table` 组件内置分页。修改以下页面：
- `UploadPage.tsx` - 文档列表
- `KnowledgePage.tsx` - 知识树列表
- `QuizPage.tsx` - 题库列表
- `FlashcardPage.tsx` - 牌组列表
- `StudyPage.tsx` - 学习计划列表
- `SharePage.tsx` - 分享链接列表

### 4.2 Pipeline 进度（US-05）

`PipelineProgress.tsx` 需要支持新的 OUTLINE 阶段显示。

## 5. 可复用资产

| 资产 | 来源 | 用途 |
|------|------|------|
| 分页模式 (limit+offset) | `chat.py:106` | US-11 |
| 独立 session 管理 | `pipeline.py:76,108,138,170` | US-08 |
| 去重模式 (预查 set) | `backup.py:133-152` | US-07 |
| ChromaDB collection.delete() | `rag.py:100` | US-02 |
| 输入验证中间件 | `middleware.py:21-49` | US-03 |

## 6. 文件变更清单

### 新增文件
无

### 修改文件

**后端 (10 个文件)**:
| 文件 | 修复 |
|------|------|
| `backend/app/api/documents.py` | US-01 (chunk ID), US-02 (向量清理) |
| `backend/app/api/chat.py` | US-08 (流式会话) |
| `backend/app/api/questions.py` | US-03 (chunk 限制), US-09 (溯源), US-11 (分页) |
| `backend/app/api/share.py` | US-10 (验证) |
| `backend/app/api/flashcards.py` | US-11 (分页) |
| `backend/app/api/knowledge.py` | US-11 (分页) |
| `backend/app/api/study.py` | US-11 (分页) |
| `backend/app/core/pipeline.py` | US-03 (chunk), US-05 (outline), US-07 (去重), US-09 (溯源) |
| `backend/app/core/quiz/__init__.py` | US-04 (答案检查) |
| `backend/app/core/memory/__init__.py` | US-06 (FSRS w 参数) |
| `backend/app/core/rag.py` | US-02 (delete_vectors 方法) |

**前端 (7 个文件)**:
| 文件 | 修复 |
|------|------|
| `frontend/src/api.ts` | US-11 (分页参数) |
| `frontend/src/pages/UploadPage.tsx` | US-11 (分页 UI) |
| `frontend/src/pages/KnowledgePage.tsx` | US-11 (分页 UI) |
| `frontend/src/pages/QuizPage.tsx` | US-11 (分页 UI) |
| `frontend/src/pages/FlashcardPage.tsx` | US-11 (分页 UI) |
| `frontend/src/pages/StudyPage.tsx` | US-11 (分页 UI) |
| `frontend/src/pages/SharePage.tsx` | US-11 (分页 UI) |
| `frontend/src/components/PipelineProgress.tsx` | US-05 (大纲阶段) |

## 7. 技术决策与权衡

| 决策 | 方案 | 理由 |
|------|------|------|
| Chunk 限制 | 按 token 预算而非全部拼接 | 避免 LLM context 溢出和高额 API 费用 |
| FSRS | 最小化参数生效，非完整重写 | 完整 FSRS 实现复杂度高，当前版本让已有参数生效即满足需求 |
| 去重 | 基于 generation_cache_key | 复用已有数据库列，不引入新约束 |
| 溯源 | 合并来源标记为 None | 精确溯源需要 LLM 结构化输出，MVP 阶段成本过高 |
| 答案检查 | difflib 相似度 | Python 标准库，无需额外依赖 |
| 分页 | 后端统一 limit+offset + total | 复用已有 chat.py 模式 |
