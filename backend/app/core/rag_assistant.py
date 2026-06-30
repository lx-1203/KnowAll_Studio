"""RAG-powered AI Assistant - combines vector search with LLM chat"""
import logging
from app.core.assistant import assistant as base_assistant
from app.core.rag import rag_query, search

logger = logging.getLogger("knowall.rag_assistant")


class RAGAssistant:
    """Extends the base Assistant with RAG capabilities.

    Before answering, retrieves relevant document chunks from the vector store
    and injects them as context into the model prompt.

    Supports two retrieval modes:
      - "rag": standard vector-only RAG (default)
      - "graphrag": hybrid vector + knowledge graph retrieval
    """

    async def chat_with_rag(
        self,
        user_message: str,
        role_preset: str = "tutor",
        history: list[dict] | None = None,
        model: str = "deepseek-chat",
        top_k: int = 3,
        user_id: str | None = None,
        mode: str = "rag",
    ) -> str:
        """Answer a question using RAG: retrieve context -> augment prompt -> generate.

        Args:
            mode: "rag" for vector-only, "graphrag" for hybrid vector+graph retrieval.
        """
        if mode == "graphrag":
            return await self._chat_with_graphrag(
                user_message, role_preset, history, model, top_k, user_id
            )

        # Standard RAG flow
        context = rag_query(user_message, top_k=top_k)

        if not context:
            logger.info("No RAG context found for query, using base assistant")
            return await base_assistant.chat(user_message, role_preset, history, model, user_id=user_id)

        logger.info("RAG context retrieved: %d chars", len(context))

        augmented_message = f"""请仅根据以下参考文档内容回答问题。如果文档中没有明确答案，请说明"文档中未找到相关信息"。

参考文档内容：
---
{context[:4000]}
---

用户问题：{user_message}

请基于上述文档内容给出准确回答，并标注信息来源（如果有）。"""

        return await base_assistant.chat(augmented_message, role_preset, history, model, user_id=user_id)

    async def chat_stream_with_rag(
        self,
        user_message: str,
        role_preset: str = "tutor",
        history: list[dict] | None = None,
        model: str = "deepseek-chat",
        top_k: int = 3,
        user_id: str | None = None,
        mode: str = "rag",
    ):
        """Streaming version of RAG chat.

        Args:
            mode: "rag" for vector-only, "graphrag" for hybrid vector+graph retrieval.
        """
        if mode == "graphrag":
            async for chunk in self._chat_stream_with_graphrag(
                user_message, role_preset, history, model, top_k, user_id
            ):
                yield chunk
            return

        context = rag_query(user_message, top_k=top_k)

        if not context:
            async for chunk in base_assistant.chat_stream(user_message, role_preset, history, model, user_id=user_id):
                yield chunk
            return

        augmented_message = f"""请仅根据以下参考文档内容回答问题。如果文档中没有明确答案，请说明"文档中未找到相关信息"。

参考文档内容：
---
{context[:4000]}
---

用户问题：{user_message}

请基于上述文档内容给出准确回答。"""

        async for chunk in base_assistant.chat_stream(augmented_message, role_preset, history, model, user_id=user_id):
            yield chunk

    async def search_only(self, query: str, top_k: int = 5) -> list[dict]:
        """Search documents without calling LLM. Returns raw search results."""
        return search(query, n_results=top_k)

    # ------------------------------------------------------------------
    # GraphRAG (hybrid vector + knowledge graph retrieval)
    # ------------------------------------------------------------------

    async def _chat_with_graphrag(
        self,
        user_message: str,
        role_preset: str = "tutor",
        history: list[dict] | None = None,
        model: str = "deepseek-chat",
        top_k: int = 8,
        user_id: str | None = None,
    ) -> str:
        """Chat using hybrid GraphRAG retrieval."""
        from app.core.graph_rag import graph_rag_query, get_graph_stats

        context, raw_results = await graph_rag_query(
            query=user_message,
            top_k_vector=top_k,
            max_hops=2,
            max_context_chars=8000,
        )

        if not context:
            logger.info("No GraphRAG context found, falling back to base assistant")
            return await base_assistant.chat(user_message, role_preset, history, model, user_id=user_id)

        # Log retrieval stats
        stats = await get_graph_stats()
        logger.info(
            "GraphRAG: %d results over %d nodes, context=%d chars",
            len(raw_results), stats["node_count"], len(context),
        )

        augmented_message = f"""你是一个智能学习助手，已经检索了知识库中的相关文档和知识关联图谱。

请根据下面的知识上下文回答用户问题。上下文包括：
- 直接匹配的文档内容
- 通过知识图谱关联到的相关知识点
- 知识节点之间的关联关系（前置依赖、扩展延伸、易混淆等）

如果有关系路径说明知识点间的联系，请在你的回答中体现这些关联。

---
{context}
---

用户问题：{user_message}

请给出详细、结构化的回答。如果涉及多个相关知识点，请说明它们之间的联系。"""

        return await base_assistant.chat(augmented_message, role_preset, history, model, user_id=user_id)

    async def _chat_stream_with_graphrag(
        self,
        user_message: str,
        role_preset: str = "tutor",
        history: list[dict] | None = None,
        model: str = "deepseek-chat",
        top_k: int = 8,
        user_id: str | None = None,
    ):
        """Streaming version of GraphRAG chat."""
        from app.core.graph_rag import graph_rag_query

        context, raw_results = await graph_rag_query(
            query=user_message,
            top_k_vector=top_k,
            max_hops=2,
            max_context_chars=8000,
        )

        if not context:
            async for chunk in base_assistant.chat_stream(user_message, role_preset, history, model, user_id=user_id):
                yield chunk
            return

        augmented_message = f"""你是一个智能学习助手，已经检索了知识库中的相关文档和知识关联图谱。

请根据下面的知识上下文回答用户问题。上下文包括直接匹配的文档内容和通过知识图谱关联到的相关知识点。

---
{context}
---

用户问题：{user_message}

请给出详细、结构化的回答。如果涉及多个相关知识点，请说明它们之间的联系。"""

        async for chunk in base_assistant.chat_stream(augmented_message, role_preset, history, model, user_id=user_id):
            yield chunk

    async def search_graphrag(self, query: str, top_k: int = 8) -> dict:
        """Search with GraphRAG and return both raw results and formatted context."""
        from app.core.graph_rag import graph_rag_query, get_graph_stats

        context, raw_results = await graph_rag_query(
            query=query,
            top_k_vector=top_k,
            max_hops=2,
        )

        stats = await get_graph_stats()

        return {
            "query": query,
            "mode": "graphrag",
            "context": context,
            "result_count": len(raw_results),
            "results": [
                {
                    "source": r.source,
                    "title": r.title,
                    "text": r.text[:500],
                    "relevance_score": r.relevance_score,
                    "relation_path": r.relation_path,
                }
                for r in raw_results
            ],
            "graph_stats": stats,
        }


rag_assistant = RAGAssistant()
