"""Pipeline Orchestrator - Automates the full learning chain from document to flashcards.

One-click flow:
  Document → Parse → Clean → Split → Knowledge Tree → Quiz → Flashcards → Done

Each stage produces structured output; stages can be run individually or as a full chain.
"""
import json
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import AsyncGenerator, Any

logger = logging.getLogger("knowall.pipeline")


class PipelineStage(str, Enum):
    PARSE = "parse"
    KNOWLEDGE_TREE = "knowledge_tree"
    QUIZ = "quiz"
    FLASHCARDS = "flashcards"
    OUTLINE = "outline"
    AGENTS = "agents"
    DONE = "done"
    ERROR = "error"


@dataclass
class PipelineState:
    """Tracks progress through the pipeline."""
    stage: PipelineStage = PipelineStage.PARSE
    progress_pct: int = 0
    message: str = ""
    result: dict | None = None
    error: str | None = None
    # Intermediate results fed between stages
    doc_id: str = ""
    chunk_ids: list[str] = field(default_factory=list)
    chunk_texts: list[str] = field(default_factory=list)
    tree_id: str = ""
    outline_id: str = ""
    question_ids: list[str] = field(default_factory=list)
    deck_id: str = ""
    structure_context: str = ""
    image_descriptions: list[str] | None = None


class PipelineOrchestrator:
    """Coordinates the full learning content generation pipeline.

    Usage:
        orchestrator = PipelineOrchestrator()
        async for state in orchestrator.run_full_chain("doc_id", model="deepseek-chat"):
            print(f"[{state.progress_pct}%] {state.stage}: {state.message}")
    """

    def __init__(self):
        pass

    async def run_full_chain(
        self,
        document_id: str,
        model: str = "deepseek-chat",
        question_count: int = 15,
        question_type: str = "single_choice",
        difficulty: str = "medium",
        card_count: int = 20,
        card_type: str = "qa",
    ) -> AsyncGenerator[PipelineState, None]:
        """Run the complete pipeline. Yields progress updates at each stage."""
        state = PipelineState(doc_id=document_id)

        # Check for existing pipeline results
        cache_key = f"pipeline:{document_id}:{question_type}:{difficulty}:{card_type}"
        from app.database import async_session
        async with async_session() as db:
            from sqlalchemy import select as sel_check
            from app.models import KnowledgeTree as KT
            result = await db.execute(
                sel_check(KT).where(KT.generation_cache_key == cache_key)
            )
            existing_tree = result.scalar_one_or_none()
            if existing_tree:
                logger.info("Document %s already has pipeline results (tree %s)", document_id, existing_tree.id)

        # ---- Stage 1: Load document chunks ----
        yield self._progress(state, PipelineStage.PARSE, 5, "加载文档分片...")
        try:
            from app.database import async_session
            from sqlalchemy import select
            from app.models import Document, DocumentChunk

            async with async_session() as db:
                result = await db.execute(select(Document).where(Document.id == document_id))
                doc = result.scalar_one_or_none()
                if not doc:
                    raise ValueError(f"Document not found: {document_id}")

                result = await db.execute(
                    select(DocumentChunk)
                    .where(DocumentChunk.doc_id == document_id)
                    .order_by(DocumentChunk.chunk_index)
                )
                chunks = result.scalars().all()
                if not chunks:
                    raise ValueError("No chunks found for document")

                state.chunk_ids = [c.id for c in chunks]
                state.chunk_texts = [c.text_content for c in chunks]
                logger.info("Loaded %d chunks from document %s", len(chunks), document_id)

                # Extract native structure context from document metadata
                structure_context = ""
                image_descriptions = None
                if doc.metadata_:
                    headings = doc.metadata_.get("headings", [])
                    if headings:
                        from app.core.parsing.docling_parser import HeadingNode

                        def _dicts_to_nodes(dicts):
                            nodes = []
                            for d in dicts:
                                node = HeadingNode(
                                    id=d.get("id", ""),
                                    label=d.get("label", ""),
                                    level=d.get("level", 1),
                                    page=d.get("page", 0),
                                    children=_dicts_to_nodes(d.get("children", [])),
                                )
                                nodes.append(node)
                            return nodes

                        from app.core.parsing.outline_extractor import outline_extractor
                        heading_nodes = _dicts_to_nodes(headings)
                        structure_context = outline_extractor.inject_context(heading_nodes)

                    analyses = doc.metadata_.get("image_analyses", [])
                    if analyses:
                        image_descriptions = [a["analysis"] for a in analyses]

                state.structure_context = structure_context
                state.image_descriptions = image_descriptions
        except Exception as e:
            yield self._error(state, PipelineStage.PARSE, str(e))
            return

        yield self._progress(state, PipelineStage.PARSE, 10, f"已加载 {len(state.chunk_texts)} 个分片")

        # ---- Stage 2: Generate knowledge tree ----
        yield self._progress(state, PipelineStage.KNOWLEDGE_TREE, 15, "正在生成知识树...")
        try:
            from app.core.knowledge import knowledge_generator
            from app.models import KnowledgeTree

            tree_data = await knowledge_generator.generate_tree(
                state.chunk_texts, model,
                structure_context=state.structure_context,
                image_descriptions=state.image_descriptions,
            )

            async with async_session() as db:
                tree = KnowledgeTree(
                    name=f"Pipeline-{document_id[:8]}",
                    doc_ids=[document_id],
                    tree_data=tree_data,
                    generation_cache_key=cache_key,
                )
                db.add(tree)
                await db.commit()
                state.tree_id = tree.id
                logger.info("Knowledge tree created: %s", tree.id)
        except Exception as e:
            yield self._error(state, PipelineStage.KNOWLEDGE_TREE, str(e))
            return

        yield self._progress(state, PipelineStage.KNOWLEDGE_TREE, 30, "知识树生成完成")

        # ---- Stage 2.5: Generate outline ----
        yield self._progress(state, PipelineStage.OUTLINE, 37, "正在生成知识大纲...")
        try:
            from app.core.knowledge import knowledge_generator
            from app.models import Outline

            outline_md = await knowledge_generator.generate_outline(
                state.chunk_texts, model,
                structure_context=state.structure_context,
            )

            async with async_session() as db:
                outline = Outline(
                    title=f"Outline-{document_id[:8]}",
                    content_markdown=outline_md,
                )
                db.add(outline)
                await db.commit()
                state.outline_id = outline.id
                logger.info("Outline created: %s", outline.id)
        except Exception as e:
            yield self._error(state, PipelineStage.OUTLINE, str(e))
            return

        yield self._progress(state, PipelineStage.OUTLINE, 40, "知识大纲生成完成")

        # ---- Stage 3: Generate quiz questions ----
        yield self._progress(state, PipelineStage.QUIZ, 40, f"正在生成 {question_count} 道题目...")
        try:
            from app.core.quiz import quiz_generator, QuizGenerationConfig
            from app.models import QuestionBank

            # Use all chunks, cap at reasonable token budget
            MAX_CHARS = 12000
            knowledge_text = "\n\n".join(state.chunk_texts)
            if len(knowledge_text) > MAX_CHARS:
                knowledge_text = knowledge_text[:MAX_CHARS] + "\n\n...(content truncated)"
            config = QuizGenerationConfig(
                question_type=question_type,
                count=question_count,
                difficulty=difficulty,
            )
            questions = await quiz_generator.generate(knowledge_text, config, model)

            async with async_session() as db:
                for q in questions:
                    db_q = QuestionBank(
                        question_type=q.get("type", question_type),
                        difficulty=q.get("difficulty", difficulty),
                        tags=q.get("tags", []),
                        question_text=q.get("question_text", ""),
                        options=q.get("options", []),
                        correct_answer=str(q.get("answer", q.get("correct_answer", ""))),
                        analysis=q.get("analysis", ""),
                        source_chunk_id=None,  # combined multi-chunk source
                    )
                    db.add(db_q)
                    await db.flush()
                    state.question_ids.append(db_q.id)
                await db.commit()
                logger.info("Generated %d questions", len(state.question_ids))
        except Exception as e:
            yield self._error(state, PipelineStage.QUIZ, str(e))
            return

        yield self._progress(state, PipelineStage.QUIZ, 65, f"已生成 {len(state.question_ids)} 道题目")

        # ---- Stage 4: Generate flashcards ----
        yield self._progress(state, PipelineStage.FLASHCARDS, 65, f"正在生成 {card_count} 张闪卡...")
        try:
            from app.core.memory import card_generator as cg
            from app.models import Flashcard, Deck, ReviewSchedule

            # Use all chunks, cap at reasonable token budget
            MAX_CHARS = 12000
            knowledge_text = "\n\n".join(state.chunk_texts)
            if len(knowledge_text) > MAX_CHARS:
                knowledge_text = knowledge_text[:MAX_CHARS] + "\n\n...(content truncated)"
            cards = await cg.generate(knowledge_text, card_type, card_count, model)

            async with async_session() as db:
                from sqlalchemy import select as sel
                result = await db.execute(sel(Deck).where(Deck.name == "全链路生成"))
                deck = result.scalar_one_or_none()
                if not deck:
                    deck = Deck(name="全链路生成", description="自动化流水线生成")
                    db.add(deck)
                    await db.flush()

                for c in cards:
                    card = Flashcard(
                        card_type=c.get("card_type", card_type),
                        front=c.get("front", ""),
                        back=c.get("back", ""),
                        hints=c.get("hints", ""),
                        tags=c.get("tags", []),
                        deck_id=deck.id,
                    )
                    db.add(card)
                    await db.flush()

                    # Initialize FSRS schedule
                    from app.core.memory import fsrs
                    s = fsrs.init_card()
                    db.add(ReviewSchedule(
                        card_id=card.id,
                        fsrs_stability=s["stability"],
                        fsrs_difficulty=s["difficulty"],
                        state=s["state"],
                    ))

                deck.card_count += len(cards)
                state.deck_id = deck.id
                await db.commit()
                logger.info("Generated %d flashcards in deck %s", len(cards), deck.id)
        except Exception as e:
            yield self._error(state, PipelineStage.FLASHCARDS, str(e))
            return

        yield self._progress(state, PipelineStage.FLASHCARDS, 95, f"已生成 {card_count} 张闪卡")

        yield self._progress(state, PipelineStage.DONE, 100, "全链路生成完成！")
        state.result = {
            "document_id": document_id,
            "tree_id": state.tree_id,
            "question_count": len(state.question_ids),
            "question_ids": state.question_ids,
            "deck_id": state.deck_id,
            "card_count": card_count,
        }

    async def run_partial(
        self,
        document_id: str,
        stages: list[PipelineStage],
        model: str = "deepseek-chat",
    ) -> AsyncGenerator[PipelineState, None]:
        """Run only selected stages. e.g., [KNOWLEDGE_TREE, QUIZ]"""
        # Reuse full chain but skip stages not requested
        # For simplicity, we run the full chain and filter
        async for state in self.run_full_chain(document_id, model):
            if state.stage in stages or state.stage == PipelineStage.ERROR:
                yield state

    # -- helpers --

    def _progress(self, state: PipelineState, stage: PipelineStage, pct: int, msg: str) -> PipelineState:
        state.stage = stage
        state.progress_pct = pct
        state.message = msg
        return state

    def _error(self, state: PipelineState, stage: PipelineStage, error: str) -> PipelineState:
        state.stage = PipelineStage.ERROR
        state.error = error
        state.message = f"错误 ({stage.value}): {error}"
        logger.error("Pipeline error at %s: %s", stage.value, error)
        return state


# Singleton
pipeline = PipelineOrchestrator()
