"""Tests for FeedbackEngine - memory feedback loop and review queue management."""
import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestFeedbackScan:
    """Tests for FeedbackEngine.scan() method."""

    @pytest.mark.asyncio
    async def test_scan_no_answer_records_returns_zero_results(self):
        """scan() with no answer records returns zero results."""
        from app.core.memory.feedback_loop import FeedbackEngine

        engine = FeedbackEngine()

        mock_session = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with patch("app.core.memory.feedback_loop.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await engine.scan()

        assert result["total_scanned"] == 0
        assert result["weak_found"] == 0
        assert result["pushed_to_queue"] == 0

    @pytest.mark.asyncio
    async def test_scan_identifies_weak_points_below_threshold(self):
        """scan() identifies knowledge points with accuracy < threshold as weak."""
        from app.core.memory.feedback_loop import FeedbackEngine

        engine = FeedbackEngine()

        # Create answer records with low accuracy
        mock_record = MagicMock()
        mock_record.user_id = "local_user"
        mock_record.knowledge_point_ids = ["kp_weak"]
        mock_record.is_correct = False  # Only 1 out of 3 correct -> accuracy 0.33

        mock_record2 = MagicMock()
        mock_record2.user_id = "local_user"
        mock_record2.knowledge_point_ids = ["kp_weak"]
        mock_record2.is_correct = True

        mock_session = AsyncMock()

        # First execute: answer records
        mock_ans_scalars = MagicMock()
        mock_ans_scalars.all.side_effect = [
            [mock_record, mock_record, mock_record2],  # 3 answer_records (2 wrong, 1 right for kp_weak)
        ]

        # We'll handle multiple executes by returning appropriate results
        execute_count = [0]

        async def execute_side_effect(stmt):
            execute_count[0] += 1
            r = MagicMock()
            if execute_count[0] == 1:
                # Answer records query
                r.scalars.return_value = mock_ans_scalars
            elif execute_count[0] == 2:
                # Flashcard query
                mock_card_scalars = MagicMock()
                mock_card_scalars.all.return_value = []
                r.scalars.return_value = mock_card_scalars
            elif execute_count[0] == 3:
                # KnowledgeCoverage lookup
                mock_cov = MagicMock()
                mock_cov.knowledge_point_id = "kp_weak"
                mock_cov.resource_type = "question"
                mock_cov.resource_id = "q_test"
                mock_cov_scalars = MagicMock()
                mock_cov_scalars.all.return_value = [mock_cov]
                r.scalars.return_value = mock_cov_scalars
            else:
                # ReviewQueue existing check
                mock_rq_scalars = MagicMock()
                mock_rq_scalars.first.return_value = None
                r.scalars.return_value = mock_rq_scalars
            return r

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        with patch("app.core.memory.feedback_loop.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await engine.scan()

        assert result["total_scanned"] == 1
        assert result["weak_found"] == 1

    @pytest.mark.asyncio
    async def test_scan_skips_points_above_threshold(self):
        """scan() skips knowledge points with accuracy >= threshold."""
        from app.core.memory.feedback_loop import FeedbackEngine

        engine = FeedbackEngine()

        # All answers correct -> accuracy 1.0
        mock_record = MagicMock()
        mock_record.user_id = "local_user"
        mock_record.knowledge_point_ids = ["kp_strong"]
        mock_record.is_correct = True

        mock_session = AsyncMock()

        execute_count = [0]

        async def execute_side_effect(stmt):
            execute_count[0] += 1
            r = MagicMock()
            if execute_count[0] == 1:
                mock_ans_scalars = MagicMock()
                mock_ans_scalars.all.return_value = [mock_record]
                r.scalars.return_value = mock_ans_scalars
            elif execute_count[0] == 2:
                mock_card_scalars = MagicMock()
                mock_card_scalars.all.return_value = []
                r.scalars.return_value = mock_card_scalars
            return r

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)
        mock_session.commit = AsyncMock()

        with patch("app.core.memory.feedback_loop.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await engine.scan()

        assert result["weak_found"] == 0
        assert result["pushed_to_queue"] == 0

    @pytest.mark.asyncio
    async def test_scan_does_not_requeue_already_queued(self):
        """scan() does not re-queue already-queued uncompleted items."""
        from app.core.memory.feedback_loop import FeedbackEngine

        engine = FeedbackEngine()

        mock_record = MagicMock()
        mock_record.user_id = "local_user"
        mock_record.knowledge_point_ids = ["kp_queued"]
        mock_record.is_correct = False

        mock_session = AsyncMock()

        execute_count = [0]

        async def execute_side_effect(stmt):
            execute_count[0] += 1
            r = MagicMock()
            if execute_count[0] == 1:
                mock_ans_scalars = MagicMock()
                mock_ans_scalars.all.return_value = [mock_record]
                r.scalars.return_value = mock_ans_scalars
            elif execute_count[0] == 2:
                mock_card_scalars = MagicMock()
                mock_card_scalars.all.return_value = []
                r.scalars.return_value = mock_card_scalars
            elif execute_count[0] == 3:
                # KnowledgeCoverage lookup
                mock_cov = MagicMock()
                mock_cov_scalars = MagicMock()
                mock_cov_scalars.all.return_value = [mock_cov]
                r.scalars.return_value = mock_cov_scalars
            else:
                # Already queued
                mock_rq = MagicMock()
                mock_rq_scalars = MagicMock()
                mock_rq_scalars.first.return_value = mock_rq  # Not None means already queued
                r.scalars.return_value = mock_rq_scalars
            return r

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        with patch("app.core.memory.feedback_loop.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await engine.scan()

        # Weak point was found but not pushed since already queued
        assert result["pushed_to_queue"] == 0

    @pytest.mark.asyncio
    async def test_scan_includes_flashcard_accuracy(self):
        """scan() includes flashcard accuracy in calculation."""
        from app.core.memory.feedback_loop import FeedbackEngine

        engine = FeedbackEngine()

        mock_card = MagicMock()
        mock_card.knowledge_point_id = "kp_fc"
        mock_card.review_count = 10
        mock_card.correct_count = 2  # accuracy 0.2 -> very weak

        mock_session = AsyncMock()

        execute_count = [0]

        async def execute_side_effect(stmt):
            execute_count[0] += 1
            r = MagicMock()
            if execute_count[0] == 1:
                mock_ans_scalars = MagicMock()
                mock_ans_scalars.all.return_value = []
                r.scalars.return_value = mock_ans_scalars
            elif execute_count[0] == 2:
                mock_card_scalars = MagicMock()
                mock_card_scalars.all.return_value = [mock_card]
                r.scalars.return_value = mock_card_scalars
            elif execute_count[0] == 3:
                mock_cov = MagicMock()
                mock_cov.knowledge_point_id = "kp_fc"
                mock_cov.resource_type = "flashcard"
                mock_cov.resource_id = "fc_1"
                mock_cov_scalars = MagicMock()
                mock_cov_scalars.all.return_value = [mock_cov]
                r.scalars.return_value = mock_cov_scalars
            else:
                mock_rq_scalars = MagicMock()
                mock_rq_scalars.first.return_value = None
                r.scalars.return_value = mock_rq_scalars
            return r

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        with patch("app.core.memory.feedback_loop.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await engine.scan()

        assert result["total_scanned"] >= 1
        assert result["weak_found"] >= 1


class TestReviewQueue:
    """Tests for get_review_queue(), mark_completed(), and record_answer_result()."""

    @pytest.mark.asyncio
    async def test_get_review_queue_returns_sorted_by_priority(self):
        """get_review_queue() returns items sorted by priority descending."""
        from app.core.memory.feedback_loop import FeedbackEngine

        engine = FeedbackEngine()

        mock_item_high = MagicMock()
        mock_item_high.id = "q_high"
        mock_item_high.resource_type = "question"
        mock_item_high.resource_id = "r1"
        mock_item_high.knowledge_point_id = "kp_1"
        mock_item_high.priority = 10
        mock_item_high.reason = "urgent"
        mock_item_high.pushed_at = datetime(2025, 1, 1)
        mock_item_high.completed = False

        mock_item_low = MagicMock()
        mock_item_low.id = "q_low"
        mock_item_low.resource_type = "flashcard"
        mock_item_low.resource_id = "r2"
        mock_item_low.knowledge_point_id = "kp_2"
        mock_item_low.priority = 1
        mock_item_low.reason = "monitor"
        mock_item_low.pushed_at = datetime(2025, 1, 1)
        mock_item_low.completed = False

        mock_session = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_item_high, mock_item_low]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("app.core.memory.feedback_loop.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            queue = await engine.get_review_queue()

        assert len(queue) == 2
        assert queue[0]["priority"] == 10
        assert queue[1]["priority"] == 1

    @pytest.mark.asyncio
    async def test_get_review_queue_respects_limit(self):
        """get_review_queue() respects limit parameter."""
        from app.core.memory.feedback_loop import FeedbackEngine

        engine = FeedbackEngine()

        items = []
        for i in range(10):
            m = MagicMock()
            m.id = f"q_{i}"
            m.resource_type = "question"
            m.resource_id = f"r_{i}"
            m.knowledge_point_id = f"kp_{i}"
            m.priority = 10 - i
            m.reason = "review"
            m.pushed_at = datetime(2025, 1, 1)
            m.completed = False
            items.append(m)

        mock_session = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = items
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("app.core.memory.feedback_loop.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            queue = await engine.get_review_queue(limit=3)

        assert len(queue) == 3

    @pytest.mark.asyncio
    async def test_get_review_queue_filters_out_completed(self):
        """get_review_queue() filters out completed items."""
        from app.core.memory.feedback_loop import FeedbackEngine

        engine = FeedbackEngine()

        mock_item_pending = MagicMock()
        mock_item_pending.id = "q_pending"
        mock_item_pending.resource_type = "question"
        mock_item_pending.resource_id = "r1"
        mock_item_pending.knowledge_point_id = "kp_1"
        mock_item_pending.priority = 5
        mock_item_pending.reason = "review"
        mock_item_pending.pushed_at = datetime(2025, 1, 1)
        mock_item_pending.completed = False

        # Note: get_review_queue filters at the SQL level (completed == False),
        # not in Python. So mock the query result to only contain uncompleted.

        mock_session = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_item_pending]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("app.core.memory.feedback_loop.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            queue = await engine.get_review_queue()

        # Only the non-completed item should be in results
        assert len(queue) == 1
        assert queue[0]["completed"] is False

    @pytest.mark.asyncio
    async def test_mark_completed_returns_false_for_nonexistent(self):
        """mark_completed() returns False for non-existent queue_id."""
        from app.core.memory.feedback_loop import FeedbackEngine

        engine = FeedbackEngine()

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)

        with patch("app.core.memory.feedback_loop.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await engine.mark_completed("nonexistent_id")

        assert result is False

    @pytest.mark.asyncio
    async def test_mark_completed_sets_completed_at_on_success(self):
        """mark_completed() returns True and sets completed_at on success."""
        from app.core.memory.feedback_loop import FeedbackEngine

        engine = FeedbackEngine()

        mock_item = MagicMock()
        mock_item.completed = False
        mock_item.completed_at = None

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_item)
        mock_session.commit = AsyncMock()

        with patch("app.core.memory.feedback_loop.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await engine.mark_completed("valid_queue_id")

        assert result is True
        assert mock_item.completed is True
        assert mock_item.completed_at is not None

    @pytest.mark.asyncio
    async def test_record_answer_result_updates_review_and_correct_count(self):
        """record_answer_result() updates review_count and correct_count."""
        from app.core.memory.feedback_loop import FeedbackEngine

        engine = FeedbackEngine()

        mock_card = MagicMock()
        mock_card.id = "card_1"
        mock_card.review_count = 5
        mock_card.correct_count = 3

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_card)
        mock_session.commit = AsyncMock()

        with patch("app.core.memory.feedback_loop.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            await engine.record_answer_result("card_1", is_correct=True)

        assert mock_card.review_count == 6
        assert mock_card.correct_count == 4

    @pytest.mark.asyncio
    async def test_record_answer_result_calculates_accuracy_rate(self):
        """record_answer_result() calculates accuracy_rate correctly."""
        from app.core.memory.feedback_loop import FeedbackEngine

        engine = FeedbackEngine()

        mock_card = MagicMock()
        mock_card.id = "card_1"
        mock_card.review_count = 3
        mock_card.correct_count = 1

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_card)
        mock_session.commit = AsyncMock()

        with patch("app.core.memory.feedback_loop.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            await engine.record_answer_result("card_1", is_correct=True)

        # After: review_count=4, correct_count=2 -> accuracy = 0.5
        assert mock_card.accuracy_rate == 0.5


class TestMemoryStats:
    """Tests for get_memory_stats() method."""

    @pytest.mark.asyncio
    async def test_get_memory_stats_empty_db_returns_zeros(self):
        """get_memory_stats() returns zero values when DB is empty."""
        from app.core.memory.feedback_loop import FeedbackEngine

        engine = FeedbackEngine()

        mock_session = AsyncMock()

        # All queries return 0 or None
        execute_count = [0]

        async def execute_side_effect(stmt):
            execute_count[0] += 1
            r = MagicMock()
            # For COUNT queries, return 0
            # For SUM/AVG, return None
            if execute_count[0] <= 4:
                r.scalar.return_value = 0 if execute_count[0] <= 2 else (0.0 if execute_count[0] == 4 else None)
            elif execute_count[0] == 5:
                # Flashcard select for tier counting
                mock_card_scalars = MagicMock()
                mock_card_scalars.all.return_value = []
                r.scalars.return_value = mock_card_scalars
            else:
                r.scalar.return_value = 0
            return r

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)

        with patch("app.core.memory.feedback_loop.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            stats = await engine.get_memory_stats()

        assert stats["total_cards"] == 0
        assert stats["total_reviews"] == 0
        assert stats["weak_points_count"] == 0

    @pytest.mark.asyncio
    async def test_get_memory_stats_computes_correct_averages(self):
        """get_memory_stats() computes correct averages with mixed data."""
        from app.core.memory.feedback_loop import FeedbackEngine

        engine = FeedbackEngine()

        mock_session = AsyncMock()

        execute_count = [0]

        async def execute_side_effect(stmt):
            execute_count[0] += 1
            r = MagicMock()
            if execute_count[0] == 1:
                r.scalar.return_value = 10  # total_cards
            elif execute_count[0] == 2:
                r.scalar.return_value = 50  # total_reviews
            elif execute_count[0] == 3:
                r.scalar.return_value = 0.75  # avg_accuracy
            elif execute_count[0] == 4:
                r.scalar.return_value = 0  # unused
            elif execute_count[0] == 5:
                # Flashcard select for tier counting
                card_urgent = MagicMock()
                card_urgent.accuracy_rate = 0.3
                card_review = MagicMock()
                card_review.accuracy_rate = 0.5
                card_monitor = MagicMock()
                card_monitor.accuracy_rate = 0.8
                mock_card_scalars = MagicMock()
                mock_card_scalars.all.return_value = [card_urgent, card_review, card_monitor]
                r.scalars.return_value = mock_card_scalars
            else:
                if execute_count[0] == 6:
                    r.scalar.return_value = 3  # due_today
                elif execute_count[0] == 7:
                    r.scalar.return_value = 2  # queue_count
                else:
                    r.scalar.return_value = 1  # decay_count
            return r

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)

        with patch("app.core.memory.feedback_loop.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            stats = await engine.get_memory_stats()

        assert stats["total_cards"] == 10
        assert stats["total_reviews"] == 50
        assert stats["average_accuracy"] == 0.75
        # weak_points_count = urgent + review = 1 + 1 = 2
        assert stats["weak_points_count"] == 2
        assert stats["due_today"] == 3
        assert stats["review_queue_count"] == 2
        assert stats["decay_count"] == 1
