"""Feedback loop engine - detects weak knowledge points and pushes to review queue"""
import logging
from datetime import datetime, timezone
from sqlalchemy import select, func, and_
from app.database import async_session
from app.models import (
    AnswerRecord, Flashcard, ReviewQueue, KnowledgeCoverage,
    KnowledgePointNode, ReviewSchedule,
)

logger = logging.getLogger(__name__)


class FeedbackEngine:
    """Memory feedback loop: detect weak points and auto-push to review queue."""

    DEFAULT_THRESHOLD = 0.7  # Accuracy below 70% triggers review

    async def scan(
        self,
        user_id: str = "local_user",
        threshold: float = DEFAULT_THRESHOLD,
    ) -> dict:
        """Scan all knowledge points and push weak ones to review queue.

        Args:
            user_id: User to scan for
            threshold: Accuracy threshold (default 0.7 = 70%)

        Returns:
            Dict with scan results
        """
        total_scanned = 0
        weak_found = 0
        pushed_to_queue = 0

        async with async_session() as session:
            # Find all knowledge points with answer records
            # Get all answer records with knowledge_point_ids
            ans_stmt = select(AnswerRecord).where(
                AnswerRecord.user_id == user_id,
                AnswerRecord.knowledge_point_ids != None,
            )
            ans_result = await session.execute(ans_stmt)
            answer_records = ans_result.scalars().all()

            # Aggregate by knowledge point
            kp_stats: dict[str, dict] = {}
            for record in answer_records:
                if not record.knowledge_point_ids:
                    continue
                for kp_id in record.knowledge_point_ids:
                    if kp_id not in kp_stats:
                        kp_stats[kp_id] = {"total": 0, "correct": 0}
                    kp_stats[kp_id]["total"] += 1
                    if record.is_correct:
                        kp_stats[kp_id]["correct"] += 1

            total_scanned = len(kp_stats)

            # Check flashcard accuracy too
            card_stmt = select(Flashcard).where(
                Flashcard.review_count > 0,
            )
            card_result = await session.execute(card_stmt)
            cards = card_result.scalars().all()

            for card in cards:
                if card.knowledge_point_id:
                    if card.knowledge_point_id not in kp_stats:
                        kp_stats[card.knowledge_point_id] = {"total": 0, "correct": 0}
                    kp_stats[card.knowledge_point_id]["total"] += card.review_count
                    kp_stats[card.knowledge_point_id]["correct"] += card.correct_count

            total_scanned = len(kp_stats)

            # Identify weak points and push to queue
            for kp_id, stats in kp_stats.items():
                if stats["total"] == 0:
                    continue

                accuracy = stats["correct"] / stats["total"]
                if accuracy < threshold:
                    weak_found += 1

                    # Find resources for this knowledge point
                    cov_stmt = select(KnowledgeCoverage).where(
                        KnowledgeCoverage.knowledge_point_id == kp_id,
                    )
                    cov_result = await session.execute(cov_stmt)
                    coverages = cov_result.scalars().all()

                    # Check if already in queue
                    existing_stmt = select(ReviewQueue).where(
                        and_(
                            ReviewQueue.user_id == user_id,
                            ReviewQueue.knowledge_point_id == kp_id,
                            ReviewQueue.completed == False,
                        )
                    )
                    existing_result = await session.execute(existing_stmt)
                    already_queued = existing_result.scalars().first() is not None

                    if already_queued:
                        continue

                    for cov in coverages:
                        priority = int((1.0 - accuracy) * 10)  # Lower accuracy = higher priority
                        queue_item = ReviewQueue(
                            user_id=user_id,
                            resource_type=cov.resource_type,
                            resource_id=cov.resource_id,
                            knowledge_point_id=kp_id,
                            priority=priority,
                            reason="low_accuracy",
                        )
                        session.add(queue_item)
                        pushed_to_queue += 1

            await session.commit()

        return {
            "total_scanned": total_scanned,
            "weak_found": weak_found,
            "pushed_to_queue": pushed_to_queue,
            "threshold": threshold,
        }

    async def get_review_queue(
        self,
        user_id: str = "local_user",
        limit: int = 20,
    ) -> list[dict]:
        """Get the review queue for a user, sorted by priority."""
        async with async_session() as session:
            stmt = select(ReviewQueue).where(
                and_(
                    ReviewQueue.user_id == user_id,
                    ReviewQueue.completed == False,
                )
            ).order_by(ReviewQueue.priority.desc()).limit(limit)
            result = await session.execute(stmt)
            items = result.scalars().all()

            return [
                {
                    "queue_id": item.id,
                    "resource_type": item.resource_type,
                    "resource_id": item.resource_id,
                    "knowledge_point_id": item.knowledge_point_id,
                    "priority": item.priority,
                    "reason": item.reason,
                    "pushed_at": item.pushed_at.isoformat() if item.pushed_at else None,
                    "completed": item.completed,
                }
                for item in items
            ]

    async def mark_completed(self, queue_id: str) -> bool:
        """Mark a review queue item as completed."""
        async with async_session() as session:
            item = await session.get(ReviewQueue, queue_id)
            if not item:
                return False
            item.completed = True
            item.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await session.commit()
            return True

    async def record_answer_result(
        self,
        card_id: str,
        is_correct: bool,
    ) -> None:
        """Update flashcard accuracy stats after a review."""
        async with async_session() as session:
            card = await session.get(Flashcard, card_id)
            if not card:
                return

            card.review_count = (card.review_count or 0) + 1
            if is_correct:
                card.correct_count = (card.correct_count or 0) + 1

            if card.review_count > 0:
                card.accuracy_rate = card.correct_count / card.review_count

            card.last_review_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await session.commit()

    async def get_memory_stats(self, user_id: str = "local_user") -> dict:
        """Get memory/learning statistics for a user."""
        async with async_session() as session:
            # Total flashcards
            total_stmt = select(func.count()).select_from(Flashcard)
            total_result = await session.execute(total_stmt)
            total_cards = total_result.scalar() or 0

            # Total reviews
            review_stmt = select(func.sum(Flashcard.review_count)).select_from(Flashcard)
            review_result = await session.execute(review_stmt)
            total_reviews = review_result.scalar() or 0

            # Average accuracy
            acc_stmt = select(func.avg(Flashcard.accuracy_rate)).where(
                Flashcard.review_count > 0,
            )
            acc_result = await session.execute(acc_stmt)
            avg_accuracy = acc_result.scalar() or 0.0

            # Weak points (accuracy < 0.7)
            weak_stmt = select(func.count()).where(
                and_(
                    Flashcard.review_count > 0,
                    Flashcard.accuracy_rate < self.DEFAULT_THRESHOLD,
                )
            )
            weak_result = await session.execute(weak_stmt)
            weak_count = weak_result.scalar() or 0

            # Due today
            from datetime import datetime as dt
            now = dt.now(timezone.utc).replace(tzinfo=None)
            due_stmt = select(func.count()).select_from(ReviewSchedule).where(
                ReviewSchedule.next_review_at <= now,
            )
            due_result = await session.execute(due_stmt)
            due_today = due_result.scalar() or 0

            # Queue count
            queue_stmt = select(func.count()).select_from(ReviewQueue).where(
                and_(
                    ReviewQueue.user_id == user_id,
                    ReviewQueue.completed == False,
                )
            )
            queue_result = await session.execute(queue_stmt)
            queue_count = queue_result.scalar() or 0

            return {
                "total_cards": total_cards,
                "total_reviews": total_reviews,
                "average_accuracy": round(float(avg_accuracy), 4),
                "weak_points_count": weak_count,
                "due_today": due_today,
                "review_queue_count": queue_count,
            }


feedback_engine = FeedbackEngine()
