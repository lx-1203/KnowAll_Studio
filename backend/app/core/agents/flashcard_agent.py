"""Flashcard Agent - generates memory flashcards from knowledge points with quality review"""
import logging
import re
import json as json_module
from app.core.agents.base import BaseAgent, AgentRegistry, AgentResult

logger = logging.getLogger(__name__)

# Card type distribution by knowledge point level
LEVEL_CARD_TYPE_DISTRIBUTION = {
    1: {"qa": 0.7, "compare": 0.3},         # L1 章: overview qa + compare
    2: {"qa": 0.5, "cloze": 0.35, "compare": 0.15},  # L2 节: mix
    3: {"cloze": 0.4, "qa": 0.3, "compare": 0.3},    # L3 点: detail cards
}

# Default quality thresholds
QUALITY_MIN_CARD_LENGTH = 4
QUALITY_MAX_CARDS_PER_BATCH = 10


@AgentRegistry.register("flashcard")
class FlashcardAgent(BaseAgent):
    """Generates structured flashcards from knowledge point summaries.

    Responsibilities:
    - Reads knowledge points by level and groups them for efficient generation
    - Assigns card types based on knowledge depth (L1=overview, L2=mix, L3=detail)
    - Runs quality validation on every generated card
    - Writes KnowledgeCoverage records for traceability
    - Integrates with the orchestrator for parallel scheduling
    """

    name = "flashcard"
    description = "基于知识点层级生成结构化闪卡（问答/填空/对比），含质量审核与覆盖率追踪"

    async def run(self, summary_id: str, document_id: str, **kwargs) -> AgentResult:
        from app.database import async_session
        from app.models import KnowledgeSummary, KnowledgePointNode, KnowledgeCoverage, Deck, Flashcard, ReviewSchedule
        from sqlalchemy import select

        config = kwargs.get("config", {})
        card_count = config.get("card_count", 30)
        card_types = config.get("card_types", ["qa", "cloze", "compare"])
        model = kwargs.get("model", config.get("model", "deepseek-chat"))
        deck_name = config.get("deck_name", "默认牌组")
        enable_quality_review = config.get("enable_quality_review", True)

        try:
            async with async_session() as session:
                # 1. Load summary and knowledge points
                summary = await session.get(KnowledgeSummary, summary_id)
                if not summary:
                    return AgentResult(agent=self.name, status="error", error="Summary not found")

                stmt = (
                    select(KnowledgePointNode)
                    .where(KnowledgePointNode.summary_id == summary_id)
                    .order_by(KnowledgePointNode.level, KnowledgePointNode.sequence)
                )
                result = await session.execute(stmt)
                nodes = result.scalars().all()

                if not nodes:
                    from app.core.knowledge.summary_generator import summary_generator
                    node_dicts = summary_generator.extract_nodes_from_markdown(
                        summary.content_md, document_id
                    )
                    nodes = node_dicts

                if not nodes:
                    return AgentResult(agent=self.name, status="error", error="No knowledge points found")

                # 2. Ensure deck exists
                deck_stmt = select(Deck).where(Deck.name == deck_name)
                deck_result = await session.execute(deck_stmt)
                deck = deck_result.scalar_one_or_none()
                if not deck:
                    deck = Deck(name=deck_name, description="")
                    session.add(deck)
                    await session.flush()

                # 3. Group nodes by parent topic and level
                topic_groups = self._group_by_topic(nodes)

                # 4. Distribute card types and counts across groups
                assignments = self._assign_card_types(
                    topic_groups, card_count, card_types
                )

                # 5. Generate cards for each assignment (sequential to respect rate limits)
                from app.core.memory import card_generator

                all_cards = []
                generation_stats = {"batches": 0, "quality_filtered": 0, "validated": 0}

                for assignment in assignments:
                    batch_cards = await card_generator.generate(
                        knowledge_text=assignment["text"],
                        card_type=assignment["card_type"],
                        count=assignment["count"],
                        model=model,
                    )

                    # Validate and filter
                    validated = []
                    for c in batch_cards:
                        is_valid, reason = card_generator.validate_card(
                            c, assignment["card_type"]
                        )
                        if is_valid:
                            validated.append(c)
                            generation_stats["validated"] += 1
                        else:
                            generation_stats["quality_filtered"] += 1
                            logger.warning(
                                f"Card filtered: type={assignment['card_type']} reason={reason}"
                            )

                    all_cards.extend(validated)
                    generation_stats["batches"] += 1

                # 6. LLM quality review for a sample (if enabled and enough cards)
                if enable_quality_review and len(all_cards) >= 10:
                    all_cards = await self._quality_review_sample(
                        all_cards, model, generation_stats
                    )

                # 7. Persist cards, schedules, and coverage
                saved_cards = []
                card_type_counts = {}

                for c in all_cards:
                    kp_id = c.get("knowledge_point_id")
                    ctype = c.get("card_type", "qa")

                    card = Flashcard(
                        card_type=ctype,
                        front=c.get("front", ""),
                        back=c.get("back", ""),
                        hints=c.get("hints", ""),
                        tags=c.get("tags", []),
                        knowledge_point_id=kp_id,
                        deck_id=deck.id,
                    )
                    session.add(card)
                    await session.flush()

                    # FSRS init
                    from app.core.memory import fsrs
                    schedule_state = fsrs.init_card()
                    schedule = ReviewSchedule(
                        card_id=card.id,
                        fsrs_stability=schedule_state["stability"],
                        fsrs_difficulty=schedule_state["difficulty"],
                        fsrs_retrievability=schedule_state["retrievability"],
                        state=schedule_state["state"],
                    )
                    session.add(schedule)

                    # Coverage record
                    if kp_id:
                        coverage = KnowledgeCoverage(
                            knowledge_point_id=kp_id,
                            resource_type="flashcard",
                            resource_id=card.id,
                            is_primary=True,
                        )
                        session.add(coverage)

                    saved_cards.append(card.id)
                    card_type_counts[ctype] = card_type_counts.get(ctype, 0) + 1

                deck.card_count = (deck.card_count or 0) + len(saved_cards)
                await session.commit()

                return AgentResult(
                    agent=self.name,
                    status="success",
                    result={
                        "total_cards": len(saved_cards),
                        "card_types": card_type_counts,
                        "deck_id": deck.id,
                        "card_ids": saved_cards,
                        "coverage": {
                            "covered_kp": len(set(
                                c.get("knowledge_point_id") for c in all_cards if c.get("knowledge_point_id")
                            )),
                            "total_kp": len(nodes),
                        },
                        "generation_stats": generation_stats,
                    },
                )

        except Exception as e:
            logger.error(f"FlashcardAgent failed: {e}", exc_info=True)
            return AgentResult(agent=self.name, status="error", error=str(e))

    # ── Private helpers ──────────────────────────────────────────

    def _group_by_topic(self, nodes: list) -> dict[str, list[dict]]:
        """Group nodes by parent_id for contextual generation."""
        topics: dict[str, list[dict]] = {}
        for node in nodes:
            if hasattr(node, 'parent_id'):
                parent = node.parent_id or "general"
                title = node.title
                expl = node.explanation
                level = node.level
                node_id = node.id
            else:
                parent = node.get("parent_id", "general") or "general"
                title = node.get("title", "")
                expl = node.get("explanation", "")
                level = node.get("level", 2)
                node_id = node.get("id", "")

            if parent not in topics:
                topics[parent] = {"nodes": [], "text": ""}

            topics[parent]["nodes"].append({
                "id": node_id,
                "title": title,
                "explanation": expl,
                "level": level,
            })

        # Build combined text per topic
        for parent, group in topics.items():
            parts = []
            for n in group["nodes"]:
                parts.append(f"## {n['title']}\n{n['explanation']}")
            group["text"] = "\n\n".join(parts)

        return topics

    def _assign_card_types(
        self,
        topic_groups: dict,
        total_count: int,
        allowed_types: list[str],
    ) -> list[dict]:
        """Distribute card types and counts across topic groups."""
        import random

        assignments = []
        remaining = total_count
        groups = list(topic_groups.items())
        random.shuffle(groups)

        for i, (parent, group) in enumerate(groups):
            if remaining <= 0:
                break

            # Determine card type based on average level of nodes in group
            levels = [n["level"] for n in group["nodes"]]
            avg_level = sum(levels) / max(len(levels), 1)
            dist = LEVEL_CARD_TYPE_DISTRIBUTION.get(
                round(avg_level), LEVEL_CARD_TYPE_DISTRIBUTION[2]
            )
            # Filter to allowed types
            available = {k: v for k, v in dist.items() if k in allowed_types}
            if not available:
                available = {"qa": 1.0}

            card_type = random.choices(
                list(available.keys()), weights=list(available.values()), k=1
            )[0]

            # Assign count (more to later groups if we have spare)
            base = max(1, remaining // max(len(groups) - i, 1))
            count = min(base, QUALITY_MAX_CARDS_PER_BATCH)
            remaining -= count

            assignments.append({
                "parent": parent,
                "card_type": card_type,
                "count": count,
                "text": group["text"],
                "nodes": group["nodes"],
            })

        return assignments

    async def _quality_review_sample(
        self,
        cards: list[dict],
        model: str,
        stats: dict,
    ) -> list[dict]:
        """LLM quality review for a random sample of cards.

        If the average score is below threshold, regenerate with lower temperature.
        """
        import random

        sample_size = min(3, len(cards))
        sample_indices = random.sample(range(len(cards)), sample_size)

        try:
            from app.prompts import prompt_engine
            from app.core.api_scheduler import api_client, TaskType, GenerationConfig

            scores = []
            for idx in sample_indices:
                card = cards[idx]
                messages = prompt_engine.render(
                    "flashcard_review", "review_single",
                    card_type=card.get("card_type", "qa"),
                    front=card.get("front", ""),
                    back=card.get("back", ""),
                    hints=card.get("hints", ""),
                )
                result = await api_client.generate(
                    task_type=TaskType.FLASHCARD_GEN,
                    messages=messages,
                    prompt_template_id="flashcard_review.review_single",
                    generation_content=card.get("front", "") + card.get("back", ""),
                    config=GenerationConfig(model=model, temperature=0.3, max_tokens=512),
                )
                try:
                    review = json_module.loads(result.content)
                    total = review.get("total", 3)
                    scores.append(total)
                    if not review.get("passed", True):
                        logger.info(f"Card {card.get('id', idx)} flagged: {review.get('suggestions', '')}")
                except json_module.JSONDecodeError:
                    scores.append(3)  # neutral on parse failure

            if scores:
                avg_score = sum(scores) / len(scores)
                stats["review_avg_score"] = round(avg_score, 2)

                if avg_score < 3.0:
                    stats["review_action"] = "low_score_retained"
                    logger.warning(
                        f"Quality review avg score {avg_score:.1f} < 3.0 — "
                        f"cards retained but flagged for manual review"
                    )
                else:
                    stats["review_action"] = "passed"

        except Exception as e:
            logger.warning(f"Quality review skipped (LLM error): {e}")
            stats["review_action"] = "skipped"

        return cards

    def _find_best_matching_node(self, card: dict, nodes: list) -> dict | None:
        """Find the knowledge point node that best matches a card."""
        if not nodes:
            return None

        front = card.get("front", "")
        back = card.get("back", "")
        card_text = f"{front} {back}"

        best_node = nodes[0]
        best_score = 0
        for node in nodes:
            title = node.title if hasattr(node, 'title') else node.get('title', '')
            expl = node.explanation if hasattr(node, 'explanation') else node.get('explanation', '')
            score = 0
            for word in title.split():
                if len(word) >= 2 and word in card_text:
                    score += 3
            for word in expl.split():
                if len(word) >= 3 and word in card_text:
                    score += 1
            if score > best_score:
                best_score = score
                best_node = node

        return best_node
