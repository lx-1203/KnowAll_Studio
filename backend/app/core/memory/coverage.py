"""Coverage engine - calculates knowledge point coverage by questions and flashcards"""
import logging
from sqlalchemy import select, func
from app.database import async_session
from app.models import KnowledgePointNode, KnowledgeCoverage, AnswerRecord, Flashcard

logger = logging.getLogger(__name__)


class CoverageEngine:
    """Calculates how well knowledge points are covered by questions and flashcards."""

    async def calculate(self, summary_id: str, user_id: str = "local_user") -> dict:
        """Calculate coverage report for a knowledge summary.

        Returns:
            Coverage report dict with total, covered, rates, uncovered, weak points
        """
        async with async_session() as session:
            # Get all knowledge points for this summary
            stmt = select(KnowledgePointNode).where(
                KnowledgePointNode.summary_id == summary_id
            )
            result = await session.execute(stmt)
            all_nodes = result.scalars().all()

            total_kp = len(all_nodes)
            if total_kp == 0:
                return {
                    "total_knowledge_points": 0,
                    "covered_by_questions": 0,
                    "covered_by_flashcards": 0,
                    "full_coverage": 0,
                    "coverage_rate_questions": 0.0,
                    "coverage_rate_flashcards": 0.0,
                    "full_coverage_rate": 0.0,
                    "uncovered_points": [],
                    "weak_points": [],
                }

            # Count coverage
            kp_ids = [n.id for n in all_nodes]

            # Questions coverage
            q_stmt = select(
                KnowledgeCoverage.knowledge_point_id,
                func.count().label("count"),
            ).where(
                KnowledgeCoverage.knowledge_point_id.in_(kp_ids),
                KnowledgeCoverage.resource_type == "question",
            ).group_by(KnowledgeCoverage.knowledge_point_id)
            q_result = await session.execute(q_stmt)
            question_coverage = {row[0]: row[1] for row in q_result.fetchall()}

            # Flashcards coverage
            f_stmt = select(
                KnowledgeCoverage.knowledge_point_id,
                func.count().label("count"),
            ).where(
                KnowledgeCoverage.knowledge_point_id.in_(kp_ids),
                KnowledgeCoverage.resource_type == "flashcard",
            ).group_by(KnowledgeCoverage.knowledge_point_id)
            f_result = await session.execute(f_stmt)
            flashcard_coverage = {row[0]: row[1] for row in f_result.fetchall()}

            # Calculate statistics
            covered_by_q = len(question_coverage)
            covered_by_f = len(flashcard_coverage)
            full_coverage = len(set(question_coverage.keys()) & set(flashcard_coverage.keys()))

            # Find uncovered points
            uncovered = []
            weak = []

            for node in all_nodes:
                has_q = node.id in question_coverage
                has_f = node.id in flashcard_coverage

                if not has_q and not has_f:
                    uncovered.append({
                        "id": node.id,
                        "title": node.title,
                        "level": node.level,
                    })

                # Check answer accuracy for this knowledge point
                acc = await self._get_accuracy(node.id, session)
                if acc is not None and acc < 0.7:
                    weak.append({
                        "id": node.id,
                        "title": node.title,
                        "accuracy": round(acc, 2),
                        "recommendation": "建议重新复习此知识点，多做相关练习题",
                    })

            return {
                "total_knowledge_points": total_kp,
                "covered_by_questions": covered_by_q,
                "covered_by_flashcards": covered_by_f,
                "full_coverage": full_coverage,
                "coverage_rate_questions": round(covered_by_q / total_kp, 4),
                "coverage_rate_flashcards": round(covered_by_f / total_kp, 4),
                "full_coverage_rate": round(full_coverage / total_kp, 4),
                "uncovered_points": uncovered,
                "weak_points": weak,
            }

    async def _get_accuracy(self, kp_id: str, session) -> float | None:
        """Calculate accuracy rate for a knowledge point from answer records."""
        try:
            # Find questions linked to this knowledge point
            cov_stmt = select(KnowledgeCoverage.resource_id).where(
                KnowledgeCoverage.knowledge_point_id == kp_id,
                KnowledgeCoverage.resource_type == "question",
            )
            cov_result = await session.execute(cov_stmt)
            question_ids = [row[0] for row in cov_result.fetchall()]

            if not question_ids:
                return None

            # Get answer records
            ans_stmt = select(
                func.count().label("total"),
                func.sum(AnswerRecord.is_correct.cast(int)).label("correct"),
            ).where(
                AnswerRecord.question_id.in_(question_ids),
            )
            ans_result = await session.execute(ans_stmt)
            row = ans_result.fetchone()
            if row and row[0] > 0:
                return (row[1] or 0) / row[0]

            return None
        except Exception as e:
            logger.warning(f"Failed to get accuracy for {kp_id}: {e}")
            return None

    async def ensure_full_coverage(
        self,
        summary_id: str,
        document_id: str,
        model: str = "deepseek-chat",
    ) -> dict:
        """Check coverage and auto-generate missing questions/cards.

        Returns:
            Dict with generated items count and updated coverage.
        """
        report = await self.calculate(summary_id)

        if not report["uncovered_points"]:
            return {"status": "already_covered", "generated": 0, "report": report}

        # Generate missing coverage
        from app.core.quiz import quiz_generator
        from app.core.memory import flashcard_generator

        uncovered = report["uncovered_points"]
        generated_questions = 0
        generated_cards = 0

        async with async_session() as session:
            from app.models import KnowledgePointNode, KnowledgeCoverage

            for pt in uncovered:
                # Get knowledge point details
                node = await session.get(KnowledgePointNode, pt["id"])
                if not node:
                    continue

                knowledge_text = f"{node.title}\n{node.explanation}"

                # Generate a question
                try:
                    questions = await quiz_generator.generate_questions(
                        chunk_texts=[knowledge_text],
                        question_type="single_choice",
                        count=1,
                        model=model,
                    )
                    for q in questions:
                        if isinstance(q, dict):
                            coverage = KnowledgeCoverage(
                                knowledge_point_id=pt["id"],
                                resource_type="question",
                                resource_id=q.get("id", ""),
                                is_primary=True,
                            )
                            session.add(coverage)
                            generated_questions += 1
                except Exception as e:
                    logger.error(f"Failed to generate question for {pt['id']}: {e}")

                # Generate a flashcard
                try:
                    cards = await flashcard_generator.generate_cards(
                        knowledge_text=knowledge_text,
                        card_type="qa",
                        count=1,
                        deck_name="自动补全牌组",
                        model=model,
                    )
                    for c in cards:
                        if isinstance(c, dict):
                            coverage = KnowledgeCoverage(
                                knowledge_point_id=pt["id"],
                                resource_type="flashcard",
                                resource_id=c.get("id", ""),
                                is_primary=True,
                            )
                            session.add(coverage)
                            generated_cards += 1
                except Exception as e:
                    logger.error(f"Failed to generate flashcard for {pt['id']}: {e}")

            await session.commit()

        updated_report = await self.calculate(summary_id)
        return {
            "status": "filled",
            "generated_questions": generated_questions,
            "generated_cards": generated_cards,
            "report": updated_report,
        }


coverage_engine = CoverageEngine()
