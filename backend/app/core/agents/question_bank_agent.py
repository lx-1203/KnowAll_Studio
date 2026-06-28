"""Question Bank Agent - generates quiz questions from knowledge points (v2 with Bloom + Review + KG Relations)"""
import logging
import random
from app.core.agents.base import BaseAgent, AgentRegistry, AgentResult

logger = logging.getLogger(__name__)


# Default configuration for question distribution across cognitive levels
DEFAULT_COGNITIVE_DISTRIBUTION = {
    "L1_remember": 0.10,    # 10% 记忆题
    "L2_understand": 0.30,  # 30% 理解题
    "L3_apply": 0.30,       # 30% 应用题
    "L4_analyze": 0.15,     # 15% 分析题
    "L5_evaluate": 0.10,    # 10% 评价题
    "L6_create": 0.05,      # 5% 创造题
}

# Default question types per cognitive level
COGNITIVE_LEVEL_QUESTION_TYPES = {
    "L1_remember": ["single_choice", "true_false", "fill_blank"],
    "L2_understand": ["single_choice", "multi_choice", "true_false", "fill_blank", "short_answer"],
    "L3_apply": ["single_choice", "calculation", "formula", "coding", "short_answer"],
    "L4_analyze": ["short_answer", "material_analysis", "multi_choice", "coding"],
    "L5_evaluate": ["material_analysis", "short_answer", "multi_choice"],
    "L6_create": ["coding", "short_answer", "material_analysis"],
}


@AgentRegistry.register("question_bank")
class QuestionBankAgent(BaseAgent):
    """Generates quiz questions covering all knowledge points in a summary.

    v2 features:
    - Bloom's Taxonomy cognitive level distribution
    - Continuous difficulty scoring
    - Multi-type question generation per topic
    - LLM-as-Judge quality review
    """

    name = "question_bank"
    description = "基于知识点总结生成多认知层次、多题型的测验题目（含自动质量审核）"

    async def run(self, summary_id: str, document_id: str, **kwargs) -> AgentResult:
        from app.database import async_session
        from app.models import KnowledgeSummary, KnowledgePointNode, KnowledgeCoverage

        config = kwargs.get("config", {})
        question_count = config.get("question_count", 30)
        question_types = config.get("question_types", [
            "single_choice", "multi_choice", "true_false", "fill_blank", "short_answer"
        ])
        cognitive_distribution = config.get("cognitive_distribution", DEFAULT_COGNITIVE_DISTRIBUTION)
        enable_review = config.get("enable_review", True)
        model = kwargs.get("model", "deepseek-chat")

        try:
            async with async_session() as session:
                # Load summary and nodes
                from sqlalchemy import select

                summary = await session.get(KnowledgeSummary, summary_id)
                if not summary:
                    return AgentResult(agent=self.name, status="error", error="Summary not found")

                # Get all L2 and L3 knowledge points
                stmt = select(KnowledgePointNode).where(
                    KnowledgePointNode.summary_id == summary_id,
                    KnowledgePointNode.level >= 2
                ).order_by(KnowledgePointNode.level, KnowledgePointNode.sequence)
                result = await session.execute(stmt)
                nodes = result.scalars().all()

                if not nodes:
                    from app.core.knowledge.summary_generator import summary_generator
                    node_dicts = summary_generator.extract_nodes_from_markdown(summary.content_md, document_id)
                    nodes = [KnowledgePointNode(**nd) for nd in node_dicts]

                # Build knowledge text grouped by topic
                knowledge_texts = self._group_by_topic(nodes)

                # ---- KG Relation Extraction ----
                from app.core.quiz.relation_extractor import relation_extractor

                confusion_map: dict = {}
                relations: list = []
                cross_topic_hints: list = []

                if config.get("enable_kg_relations", True) and len(nodes) >= 4:
                    try:
                        node_dicts = [
                            {
                                "id": n.id if hasattr(n, 'id') else n.get('id', ''),
                                "title": n.title if hasattr(n, 'title') else n.get('title', ''),
                                "explanation": n.explanation if hasattr(n, 'explanation') else n.get('explanation', ''),
                                "level": n.level if hasattr(n, 'level') else n.get('level', 0),
                            }
                            for n in nodes
                        ]
                        relations, confusion_pairs = await relation_extractor.extract(node_dicts, model)
                        confusion_map = relation_extractor.build_confusion_map(confusion_pairs)
                        cross_topic_hints = relation_extractor.get_cross_topic_pairs(relations)
                        logger.info(
                            f"KG relations extracted: {len(relations)} edges, "
                            f"{len(confusion_pairs)} confusion pairs, "
                            f"{len(cross_topic_hints)} cross-topic candidates"
                        )
                    except Exception as e:
                        logger.warning(f"KG relation extraction skipped: {e}")

                # Calculate question distribution across cognitive levels
                from app.core.quiz import quiz_generator

                all_questions = []
                topics = list(knowledge_texts.items())
                random.shuffle(topics)

                # Distribute questions across topics and cognitive levels
                for topic, points in topics:
                    if len(all_questions) >= question_count:
                        break

                    # Determine cognitive level for this batch
                    cognitive_level = self._sample_cognitive_level(cognitive_distribution)

                    # Determine question type appropriate for this cognitive level
                    suitable_types = COGNITIVE_LEVEL_QUESTION_TYPES.get(
                        cognitive_level, ["single_choice", "short_answer"]
                    )
                    # Prefer types the user requested
                    preferred = [t for t in suitable_types if t in question_types]
                    if not preferred:
                        preferred = suitable_types[:1]
                    qtype = random.choice(preferred)

                    # Determine difficulty based on cognitive level (higher level → harder)
                    base_difficulty = self._base_difficulty_for_level(cognitive_level)
                    difficulty_score = min(1.0, max(0.15, base_difficulty + random.uniform(-0.15, 0.15)))

                    # Map float to legacy categorical for prompt compatibility
                    if difficulty_score <= 0.35:
                        diff_legacy = "easy"
                    elif difficulty_score <= 0.65:
                        diff_legacy = "medium"
                    else:
                        diff_legacy = "hard"

                    questions_per_topic = max(1, min(3, (question_count - len(all_questions)) // max(1, len(topics))))

                    try:
                        questions = await quiz_generator.generate_questions(
                            chunk_texts=[points],
                            question_type=qtype,
                            count=questions_per_topic,
                            model=model,
                            difficulty=diff_legacy,
                            difficulty_score=difficulty_score,
                            cognitive_level=cognitive_level,
                            enable_review=enable_review,
                        )
                        all_questions.extend(questions)

                        # Write coverage for each question
                        for q in questions:
                            if isinstance(q, dict):
                                node = self._find_best_matching_node(q, nodes)
                                if node:
                                    node_id = node.id if hasattr(node, 'id') else node.get('id', '')
                                    coverage = KnowledgeCoverage(
                                        knowledge_point_id=node_id,
                                        resource_type="question",
                                        resource_id=q.get("id", ""),
                                        is_primary=True,
                                    )
                                    session.add(coverage)

                    except Exception as e:
                        logger.error(f"Failed to generate questions for topic '{topic}': {e}")

                await session.commit()

                # Calculate cognitive distribution stats
                level_counts = {}
                for q in all_questions:
                    cl = q.get("cognitive_level", "unknown")
                    level_counts[cl] = level_counts.get(cl, 0) + 1

                # Count reviewed / passed
                reviewed_count = sum(1 for q in all_questions if q.get("reviewed"))
                passed_count = sum(1 for q in all_questions if q.get("review_decision") == "pass")

                return AgentResult(
                    agent=self.name,
                    status="success",
                    result={
                        "total_questions": len(all_questions),
                        "question_types": list(set(q.get("question_type", q.get("type", "")) for q in all_questions)),
                        "question_ids": [q.get("id", "") for q in all_questions],
                        "cognitive_distribution": level_counts,
                        "reviewed_count": reviewed_count,
                        "passed_review_count": passed_count,
                    },
                )

        except Exception as e:
            logger.error(f"QuestionBankAgent failed: {e}", exc_info=True)
            return AgentResult(agent=self.name, status="error", error=str(e))

    # -------- Private Helpers --------

    def _sample_cognitive_level(self, distribution: dict[str, float]) -> str:
        """Sample a cognitive level based on the configured distribution."""
        levels = list(distribution.keys())
        weights = list(distribution.values())
        # Normalize weights
        total = sum(weights)
        if total == 0:
            return "L2_understand"
        weights = [w / total for w in weights]
        return random.choices(levels, weights=weights, k=1)[0]

    @staticmethod
    def _base_difficulty_for_level(level: str) -> float:
        """Return base difficulty score for a cognitive level."""
        mapping = {
            "L1_remember": 0.25,
            "L2_understand": 0.40,
            "L3_apply": 0.55,
            "L4_analyze": 0.68,
            "L5_evaluate": 0.78,
            "L6_create": 0.85,
        }
        return mapping.get(level, 0.5)

    def _group_by_topic(self, nodes: list) -> dict[str, str]:
        """Group nodes by parent topic for contextual question generation."""
        topics: dict[str, list[str]] = {}
        for node in nodes:
            if hasattr(node, 'parent_id'):
                parent = node.parent_id or "general"
            else:
                parent = node.get("parent_id", "general") or "general"

            title = node.title if hasattr(node, 'title') else node.get('title', '')
            expl = node.explanation if hasattr(node, 'explanation') else node.get('explanation', '')
            related = node.related_concepts if hasattr(node, 'related_concepts') else node.get('related_concepts', '')
            examples = node.examples if hasattr(node, 'examples') else node.get('examples', '')

            parts = [f"## {title}", expl]
            if related:
                parts.append(f"关联概念: {related}")
            if examples:
                parts.append(f"示例: {examples}")
            content = "\n".join(parts)

            if parent not in topics:
                topics[parent] = []
            topics[parent].append(content)

        return {k: "\n\n".join(v) for k, v in topics.items()}

    def _find_best_matching_node(self, question: dict, nodes: list) -> dict | None:
        """Find the most relevant knowledge point node for a question."""
        if not nodes:
            return None

        q_text = question.get("question_text", "")
        tags = question.get("tags", [])

        best_node = nodes[0]
        best_score = 0
        for node in nodes:
            title = node.title if hasattr(node, 'title') else node.get('title', '')
            expl = node.explanation if hasattr(node, 'explanation') else node.get('explanation', '')
            score = 0
            for tag in tags:
                if tag in title or tag in expl:
                    score += 3
            # Word-level matching
            title_words = set(title.split())
            for word in title_words:
                if len(word) >= 2 and word in q_text:
                    score += 1
            if score > best_score:
                best_score = score
                best_node = node

        return best_node
