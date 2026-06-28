"""RAG-powered AI Assistant - combines vector search with LLM chat"""
import logging
from app.core.assistant import assistant as base_assistant
from app.core.rag import rag_query, search

logger = logging.getLogger("knowall.rag_assistant")


class RAGAssistant:
    """Extends the base Assistant with RAG capabilities.

    Before answering, retrieves relevant document chunks from the vector store
    and injects them as context into the model prompt.
    """

    async def chat_with_rag(
        self,
        user_message: str,
        role_preset: str = "tutor",
        history: list[dict] | None = None,
        model: str = "deepseek-chat",
        top_k: int = 3,
        user_id: str | None = None,
    ) -> str:
        """Answer a question using RAG: retrieve context → augment prompt → generate."""
        # Search for relevant context
        context = rag_query(user_message, top_k=top_k)

        if not context:
            # No relevant documents found, fall back to regular chat
            logger.info("No RAG context found for query, using base assistant")
            return await base_assistant.chat(user_message, role_preset, history, model, user_id=user_id)

        logger.info("RAG context retrieved: %d chars", len(context))

        # Augment the system prompt with retrieved context
        augmented_message = f"""请仅根据以下参考文档内容回答问题。如果文档中没有明确答案，请说明"文档中未找到相关信息"。

参考文档内容：
---
{context[:4000]}
---

用户问题：{user_message}

请基于上述文档内容给出准确回答，并标注信息来源（如果有）。"""

        # Use the base assistant with the augmented message
        return await base_assistant.chat(augmented_message, role_preset, history, model, user_id=user_id)

    async def chat_stream_with_rag(
        self,
        user_message: str,
        role_preset: str = "tutor",
        history: list[dict] | None = None,
        model: str = "deepseek-chat",
        top_k: int = 3,
        user_id: str | None = None,
    ):
        """Streaming version of RAG chat."""
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


rag_assistant = RAGAssistant()
