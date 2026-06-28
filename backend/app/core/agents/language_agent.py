"""Language Learning Agent - extracts vocabulary from language learning materials"""
import logging
from app.core.agents.base import BaseAgent, AgentRegistry, AgentResult

logger = logging.getLogger(__name__)

# Unicode ranges for language detection
CJK_RANGE = (0x4E00, 0x9FFF)
HIRAGANA_RANGE = (0x3040, 0x309F)
KATAKANA_RANGE = (0x30A0, 0x30FF)
LATIN_RANGE = (0x0041, 0x007A)


@AgentRegistry.register("language")
class LanguageAgent(BaseAgent):
    """Extracts vocabulary items from language learning documents.

    Activated only when the document is detected as language learning material
    (English, Japanese, etc.).
    """

    name = "language"
    description = "检测语言学习材料并提取生词表（单词、音标、释义、例句、词性）"

    def should_run(self, document_id: str, **kwargs) -> bool:
        """Check if this is a language learning document."""
        language_type = kwargs.get("language_type", "auto")

        if language_type in ("english", "japanese", "korean", "french", "german"):
            return True

        # Auto-detect from chunks
        if language_type == "auto":
            return self._auto_detect_language_material(document_id)

        return False

    def _auto_detect_language_material(self, document_id: str) -> bool:
        """Auto-detect if document is language learning material by checking content."""
        try:
            from app.database import async_session_ctx
            from app.models import Document, DocumentChunk
            from sqlalchemy import select

            # Simple sync check using document metadata
            import asyncio
            async def check():
                async for session in get_session_ctx():
                    doc = await session.get(Document, document_id)
                    if not doc:
                        return False

                    # Check filename for language hints
                    filename_lower = doc.filename.lower()
                    lang_hints = ["英语", "english", "日语", "japanese", "语法", "grammar",
                                  "词汇", "vocabulary", "单词", "word", "韩语", "korean",
                                  "法语", "french", "德语", "german"]
                    for hint in lang_hints:
                        if hint in filename_lower:
                            return True

                    # Check first chunk for language indicators
                    stmt = select(DocumentChunk).where(
                        DocumentChunk.doc_id == document_id
                    ).order_by(DocumentChunk.chunk_index).limit(3)
                    result = await session.execute(stmt)
                    chunks = result.scalars().all()

                    if chunks:
                        combined = " ".join(c.text_content[:500] for c in chunks)
                        # Count Latin words vs CJK characters
                        latin_count = sum(1 for c in combined if LATIN_RANGE[0] <= ord(c) <= LATIN_RANGE[1])
                        total_chars = len(combined)
                        if total_chars > 0 and latin_count / total_chars > 0.4:
                            return True

                    return False

            return asyncio.run(check())
        except Exception as e:
            logger.warning(f"Language auto-detection failed: {e}")
            return False

    async def run(self, summary_id: str, document_id: str, **kwargs) -> AgentResult:
        from app.database import async_session
        from app.models import KnowledgeSummary, KnowledgePointNode, LanguageVocabulary
        from app.prompts import prompt_engine
        from app.core.api_scheduler import api_client, TaskType, GenerationConfig
        from sqlalchemy import select

        try:
            async with async_session() as session:
                summary = await session.get(KnowledgeSummary, summary_id)
                if not summary:
                    return AgentResult(agent=self.name, status="error", error="Summary not found")

                # Load knowledge points
                stmt = select(KnowledgePointNode).where(
                    KnowledgePointNode.summary_id == summary_id
                ).order_by(KnowledgePointNode.level, KnowledgePointNode.sequence)
                result = await session.execute(stmt)
                nodes = result.scalars().all()

                if not nodes:
                    from app.core.knowledge.summary_generator import summary_generator
                    node_dicts = summary_generator.extract_nodes_from_markdown(summary.content_md, document_id)
                    knowledge_text = "\n".join(
                        f"{n['title']}: {n['explanation'][:300]}" for n in node_dicts
                    )
                else:
                    knowledge_text = "\n".join(
                        f"{n.title}: {n.explanation[:300]}" for n in nodes
                    )

                # Generate vocabulary via LLM
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "你是一位语言教学专家。请从以下知识内容中提取重要的生词/术语，"
                            "为每个词提供：单词（原词）、音标、词性、中文释义、英文例句。"
                            "输出严格JSON数组格式："
                            '[{"word":"...","phonetic":"...","part_of_speech":"...","definition":"...","example_sentence":"..."}]'
                            "\n只输出JSON，不要任何额外文字。限制30个词。"
                        ),
                    },
                    {"role": "user", "content": knowledge_text[:8000]},
                ]

                llm_result = await api_client.generate(
                    task_type=TaskType.KNOWLEDGE_TREE,
                    messages=messages,
                    prompt_template_id="language.vocabulary_extract",
                    generation_content=knowledge_text[:8000],
                    config=GenerationConfig(model=kwargs.get("model", "deepseek-chat"), temperature=0.3),
                )

                # Parse vocabulary
                import json
                try:
                    vocab_items = json.loads(llm_result.content)
                except json.JSONDecodeError:
                    # Try to extract JSON array
                    import re
                    match = re.search(r'\[.*\]', llm_result.content, re.DOTALL)
                    if match:
                        vocab_items = json.loads(match.group(0))
                    else:
                        vocab_items = []

                # Store vocabulary
                stored_words = []
                for item in vocab_items:
                    word = item.get("word", "").strip()
                    if not word:
                        continue

                    vocab = LanguageVocabulary(
                        document_id=document_id,
                        word=word,
                        phonetic=item.get("phonetic", ""),
                        part_of_speech=item.get("part_of_speech", ""),
                        definition=item.get("definition", ""),
                        example_sentence=item.get("example_sentence", ""),
                        difficulty=self._estimate_difficulty(item),
                        knowledge_point_id=None,
                    )
                    session.add(vocab)
                    stored_words.append({
                        "id": vocab.id,
                        "word": word,
                        "phonetic": vocab.phonetic,
                        "part_of_speech": vocab.part_of_speech,
                        "definition": vocab.definition,
                        "example_sentence": vocab.example_sentence,
                        "difficulty": vocab.difficulty,
                    })

                await session.commit()

                return AgentResult(
                    agent=self.name,
                    status="success",
                    result={
                        "total_words": len(stored_words),
                        "words": stored_words,
                    },
                )

        except Exception as e:
            logger.error(f"LanguageAgent failed: {e}", exc_info=True)
            return AgentResult(agent=self.name, status="error", error=str(e))

    def _estimate_difficulty(self, item: dict) -> str:
        """Estimate word difficulty based on length and type."""
        word = item.get("word", "")
        pos = item.get("part_of_speech", "")

        if len(word) >= 12:
            return "hard"
        if len(word) <= 4 and pos in ("noun", "verb", "adj"):
            return "easy"
        return "medium"
