"""Question Bank Agent - generates quiz questions from knowledge points"""
import logging
from app.core.agents.base import BaseAgent, AgentRegistry, AgentResult
from app.core.api_scheduler import api_client, TaskType, GenerationConfig

logger = logging.getLogger(__name__)


@AgentRegistry.register("question_bank")
class QuestionBankAgent(BaseAgent):
    """Generates quiz questions covering all knowledge points in a summary."""

    name = "question_bank"
    description = "基于知识点总结生成选择题、填空题、简答题等多种题型"

    async def run(self, summary_id: str, document_id: str, **kwargs) -> AgentResult:
        from app.database import get_session
        from app.models import KnowledgeSummary, KnowledgePointNode, QuestionBank, KnowledgeCoverage

        config = kwargs.get("config", {})
        question_count = config.get("question_count", 30)
        question_types = config.get("question_types", [
            "single_choice", "multi_choice", "true_false", "fill_blank", "short_answer"
        ])
        model = kwargs.get("model", "deepseek-chat")

        try:
            from app.database import async_session
            async with async_session() as session:
                # Load summary and nodes
                summary = await session.get(KnowledgeSummary, summary_id)
                if not summary:
                    return AgentResult(agent=self.name, status="error", error="Summary not found")

                # Get all L2 and L3 knowledge points
                from sqlalchemy import select
                stmt = select(KnowledgePointNode).where(
                    KnowledgePointNode.summary_id == summary_id,
                    KnowledgePointNode.level >= 2
                ).order_by(KnowledgePointNode.level, KnowledgePointNode.sequence)
                result = await session.execute(stmt)
                nodes = result.scalars().all()

                if not nodes:
                    # Try loading nodes from content_md
                    from app.core.knowledge.summary_generator import summary_generator
                    node_dicts = summary_generator.extract_nodes_from_markdown(summary.content_md, document_id)
                    nodes = [KnowledgePointNode(**nd) for nd in node_dicts]

                # Build knowledge text grouped by topic
                knowledge_texts = self._group_by_topic(nodes)

                # Generate questions
                from app.core.quiz import quiz_generator

                all_questions = []
                questions_per_topic = max(1, question_count // len(knowledge_texts))

                for topic, points in knowledge_texts.items():
                    try:
                        questions = await quiz_generator.generate_questions(
                            chunk_texts=[points],
                            question_type=question_types[0],
                            count=questions_per_topic,
                            model=model,
                        )
                        all_questions.extend(questions)

                        # Write coverage for each question
                        for q in questions:
                            if isinstance(q, dict):
                                node = self._find_best_matching_node(q, nodes)
                                if node:
                                    coverage = KnowledgeCoverage(
                                        knowledge_point_id=node.id if hasattr(node, 'id') else node.get('id', ''),
                                        resource_type="question",
                                        resource_id=q.get("id", ""),
                                        is_primary=True,
                                    )
                                    session.add(coverage)
                    except Exception as e:
                        logger.error(f"Failed to generate questions for topic '{topic}': {e}")

                await session.commit()

                return AgentResult(
                    agent=self.name,
                    status="success",
                    result={
                        "total_questions": len(all_questions),
                        "question_types": list(set(q.get("question_type", "") for q in all_questions)),
                        "question_ids": [q.get("id", "") for q in all_questions],
                    },
                )

        except Exception as e:
            logger.error(f"QuestionBankAgent failed: {e}", exc_info=True)
            return AgentResult(agent=self.name, status="error", error=str(e))

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
            content = f"{title}\n{expl}"

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

        # Simple keyword matching
        best_node = nodes[0]
        best_score = 0
        for node in nodes:
            title = node.title if hasattr(node, 'title') else node.get('title', '')
            score = 0
            for tag in tags:
                if tag in title:
                    score += 2
            for word in title.split():
                if word in q_text:
                    score += 1
            if score > best_score:
                best_score = score
                best_node = node

        return best_node
