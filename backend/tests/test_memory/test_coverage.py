"""Tests for CoverageEngine - knowledge point coverage calculation."""
import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestCoverageCalculate:
    """Tests for CoverageEngine.calculate() method."""

    @pytest.mark.asyncio
    async def test_calculate_zero_nodes_returns_empty_report_with_zeros(self):
        """calculate() with zero nodes returns empty report with zeros."""
        from app.core.memory.coverage import CoverageEngine

        engine = CoverageEngine()

        mock_session = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("app.core.memory.coverage.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            report = await engine.calculate("sum_1")

        assert report["total_knowledge_points"] == 0
        assert report["covered_by_questions"] == 0
        assert report["covered_by_flashcards"] == 0
        assert report["full_coverage"] == 0
        assert report["coverage_rate_questions"] == 0.0
        assert report["coverage_rate_flashcards"] == 0.0
        assert report["full_coverage_rate"] == 0.0
        assert report["uncovered_points"] == []
        assert report["weak_points"] == []

    @pytest.mark.asyncio
    async def test_calculate_correctly_counts_covered_by_questions(self):
        """calculate() correctly counts covered_by_questions."""
        from app.core.memory.coverage import CoverageEngine

        engine = CoverageEngine()

        mock_node = MagicMock()
        mock_node.id = "kp_1"
        mock_node.title = "Topic 1"
        mock_node.level = 2

        mock_session = AsyncMock()

        # First execute: all nodes
        mock_scalars_nodes = MagicMock()
        mock_scalars_nodes.all.return_value = [mock_node]

        # Second execute: question coverage
        mock_q_fetchall = MagicMock()
        mock_q_fetchall.fetchall.return_value = [("kp_1", 3)]

        # Third execute: flashcard coverage
        mock_f_fetchall = MagicMock()
        mock_f_fetchall.fetchall.return_value = [("kp_1", 2)]

        # _get_accuracy inner execute for coverage lookup
        mock_cov_fetchall = MagicMock()
        mock_cov_fetchall.fetchall.return_value = [("q_1",)]

        mock_ans_fetchone = MagicMock()
        mock_ans_fetchone.fetchone.return_value = (5, 4)

        execute_responses = [
            MagicMock(scalars=MagicMock(return_value=mock_scalars_nodes)),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
        ]
        # Set up each response's fetchall/fetchone
        execute_responses[1].fetchall = mock_q_fetchall.fetchall
        execute_responses[2].fetchall = mock_f_fetchall.fetchall
        execute_responses[3].fetchall = mock_cov_fetchall.fetchall
        execute_responses[4].fetchone = mock_ans_fetchone.fetchone

        mock_session.execute = AsyncMock(side_effect=execute_responses)

        with patch("app.core.memory.coverage.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            report = await engine.calculate("sum_1")

        assert report["total_knowledge_points"] == 1
        assert report["covered_by_questions"] == 1

    @pytest.mark.asyncio
    async def test_calculate_correctly_counts_covered_by_flashcards(self):
        """calculate() correctly counts covered_by_flashcards."""
        from app.core.memory.coverage import CoverageEngine

        engine = CoverageEngine()

        mock_node = MagicMock()
        mock_node.id = "kp_1"
        mock_node.title = "Topic"
        mock_node.level = 2

        mock_session = AsyncMock()

        mock_scalars_nodes = MagicMock()
        mock_scalars_nodes.all.return_value = [mock_node]

        # Question coverage: empty
        mock_q_fetchall = MagicMock()
        mock_q_fetchall.fetchall.return_value = []

        # Flashcard coverage: has one
        mock_f_fetchall = MagicMock()
        mock_f_fetchall.fetchall.return_value = [("kp_1", 5)]

        execute_responses = [
            MagicMock(scalars=MagicMock(return_value=mock_scalars_nodes)),
            MagicMock(),
            MagicMock(),
        ]
        execute_responses[1].fetchall = mock_q_fetchall.fetchall
        execute_responses[2].fetchall = mock_f_fetchall.fetchall

        mock_session.execute = AsyncMock(side_effect=execute_responses)

        with patch("app.core.memory.coverage.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch.object(engine, "_get_accuracy", new_callable=AsyncMock) as mock_acc:
                mock_acc.return_value = None
                report = await engine.calculate("sum_1")

        assert report["covered_by_questions"] == 0
        assert report["covered_by_flashcards"] == 1

    @pytest.mark.asyncio
    async def test_calculate_full_coverage_is_intersection(self):
        """calculate() computes full_coverage as intersection of questions and flashcards."""
        from app.core.memory.coverage import CoverageEngine

        engine = CoverageEngine()

        mock_node_a = MagicMock()
        mock_node_a.id = "kp_A"
        mock_node_a.title = "A"
        mock_node_a.level = 2

        mock_node_b = MagicMock()
        mock_node_b.id = "kp_B"
        mock_node_b.title = "B"
        mock_node_b.level = 2

        mock_node_c = MagicMock()
        mock_node_c.id = "kp_C"
        mock_node_c.title = "C"
        mock_node_c.level = 2

        mock_session = AsyncMock()

        mock_scalars_nodes = MagicMock()
        mock_scalars_nodes.all.return_value = [mock_node_a, mock_node_b, mock_node_c]

        # Question covers A and B
        mock_q_fetchall = MagicMock()
        mock_q_fetchall.fetchall.return_value = [("kp_A", 2), ("kp_B", 1)]

        # Flashcard covers B and C
        mock_f_fetchall = MagicMock()
        mock_f_fetchall.fetchall.return_value = [("kp_B", 3), ("kp_C", 1)]

        execute_responses = [
            MagicMock(scalars=MagicMock(return_value=mock_scalars_nodes)),
            MagicMock(),
            MagicMock(),
        ]
        execute_responses[1].fetchall = mock_q_fetchall.fetchall
        execute_responses[2].fetchall = mock_f_fetchall.fetchall

        mock_session.execute = AsyncMock(side_effect=execute_responses)

        with patch("app.core.memory.coverage.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch.object(engine, "_get_accuracy", new_callable=AsyncMock) as mock_acc:
                mock_acc.return_value = None
                report = await engine.calculate("sum_1")

        # Only B has both question and flashcard coverage
        assert report["full_coverage"] == 1
        assert report["covered_by_questions"] == 2
        assert report["covered_by_flashcards"] == 2

    @pytest.mark.asyncio
    async def test_calculate_identifies_uncovered_points(self):
        """calculate() identifies uncovered points correctly."""
        from app.core.memory.coverage import CoverageEngine

        engine = CoverageEngine()

        mock_node = MagicMock()
        mock_node.id = "kp_uncov"
        mock_node.title = "Uncovered"
        mock_node.level = 1

        mock_session = AsyncMock()

        mock_scalars_nodes = MagicMock()
        mock_scalars_nodes.all.return_value = [mock_node]

        # Neither question nor flashcard coverage
        mock_q_fetchall = MagicMock()
        mock_q_fetchall.fetchall.return_value = []
        mock_f_fetchall = MagicMock()
        mock_f_fetchall.fetchall.return_value = []

        execute_responses = [
            MagicMock(scalars=MagicMock(return_value=mock_scalars_nodes)),
            MagicMock(),
            MagicMock(),
        ]
        execute_responses[1].fetchall = mock_q_fetchall.fetchall
        execute_responses[2].fetchall = mock_f_fetchall.fetchall

        mock_session.execute = AsyncMock(side_effect=execute_responses)

        with patch("app.core.memory.coverage.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch.object(engine, "_get_accuracy", new_callable=AsyncMock) as mock_acc:
                mock_acc.return_value = None
                report = await engine.calculate("sum_1")

        assert len(report["uncovered_points"]) == 1
        assert report["uncovered_points"][0]["id"] == "kp_uncov"

    @pytest.mark.asyncio
    async def test_calculate_identifies_weak_points(self):
        """calculate() identifies weak points (accuracy < 0.7)."""
        from app.core.memory.coverage import CoverageEngine

        engine = CoverageEngine()

        mock_node = MagicMock()
        mock_node.id = "kp_weak"
        mock_node.title = "WeakTopic"
        mock_node.level = 2

        mock_session = AsyncMock()

        mock_scalars_nodes = MagicMock()
        mock_scalars_nodes.all.return_value = [mock_node]

        mock_q_fetchall = MagicMock()
        mock_q_fetchall.fetchall.return_value = [("kp_weak", 2)]
        mock_f_fetchall = MagicMock()
        mock_f_fetchall.fetchall.return_value = [("kp_weak", 3)]

        execute_responses = [
            MagicMock(scalars=MagicMock(return_value=mock_scalars_nodes)),
            MagicMock(),
            MagicMock(),
        ]
        execute_responses[1].fetchall = mock_q_fetchall.fetchall
        execute_responses[2].fetchall = mock_f_fetchall.fetchall

        mock_session.execute = AsyncMock(side_effect=execute_responses)

        with patch("app.core.memory.coverage.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch.object(engine, "_get_accuracy", new_callable=AsyncMock) as mock_acc:
                mock_acc.return_value = 0.55  # Below 0.7 threshold
                report = await engine.calculate("sum_1")

        assert len(report["weak_points"]) == 1
        assert report["weak_points"][0]["id"] == "kp_weak"
        assert report["weak_points"][0]["accuracy"] == 0.55

    @pytest.mark.asyncio
    async def test_calculate_coverage_rates_correct(self):
        """calculate() computes correct coverage rates."""
        from app.core.memory.coverage import CoverageEngine

        engine = CoverageEngine()

        nodes = []
        for i in range(10):
            n = MagicMock()
            n.id = f"kp_{i}"
            n.title = f"Topic {i}"
            n.level = 2
            nodes.append(n)

        mock_session = AsyncMock()

        mock_scalars_nodes = MagicMock()
        mock_scalars_nodes.all.return_value = nodes

        # Question covers 5 of 10
        mock_q_fetchall = MagicMock()
        mock_q_fetchall.fetchall.return_value = [(f"kp_{i}", 1) for i in range(5)]

        # Flashcard covers 8 of 10
        mock_f_fetchall = MagicMock()
        mock_f_fetchall.fetchall.return_value = [(f"kp_{i}", 1) for i in range(8)]

        execute_responses = [
            MagicMock(scalars=MagicMock(return_value=mock_scalars_nodes)),
            MagicMock(),
            MagicMock(),
        ]
        execute_responses[1].fetchall = mock_q_fetchall.fetchall
        execute_responses[2].fetchall = mock_f_fetchall.fetchall

        mock_session.execute = AsyncMock(side_effect=execute_responses)

        with patch("app.core.memory.coverage.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch.object(engine, "_get_accuracy", new_callable=AsyncMock) as mock_acc:
                mock_acc.return_value = None
                report = await engine.calculate("sum_1")

        assert report["coverage_rate_questions"] == 0.5  # 5/10
        assert report["coverage_rate_flashcards"] == 0.8  # 8/10


class TestCoverageAccuracy:
    """Tests for _get_accuracy() method."""

    @pytest.mark.asyncio
    async def test_get_accuracy_returns_none_when_no_questions(self):
        """_get_accuracy() returns None when no questions cover the knowledge point."""
        from app.core.memory.coverage import CoverageEngine

        engine = CoverageEngine()

        mock_session = AsyncMock()

        mock_cov_fetchall = MagicMock()
        mock_cov_fetchall.fetchall.return_value = []

        mock_cov_result = MagicMock()
        mock_session.execute = AsyncMock(return_value=mock_cov_result)
        # The execute returns object with fetchall method
        async def execute_side_effect(stmt):
            r = MagicMock()
            r.fetchall.return_value = []
            return r

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)

        # Patch the execute to return empty
        with patch("app.core.memory.coverage.async_session", return_value=MagicMock()):
            result = await engine._get_accuracy("kp_1", mock_session)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_accuracy_computes_correct_rate(self):
        """_get_accuracy() computes correct_rate correctly."""
        from app.core.memory.coverage import CoverageEngine

        engine = CoverageEngine()

        mock_session = AsyncMock()

        # The _get_accuracy method does two executes:
        # 1. select resource_id from KnowledgeCoverage
        # 2. select count, sum(is_correct) from AnswerRecord
        async def execute_side_effect(stmt):
            r = MagicMock()
            # First call: coverage lookup
            if not hasattr(execute_side_effect, "call_count"):
                execute_side_effect.call_count = 0
            execute_side_effect.call_count += 1

            if execute_side_effect.call_count == 1:
                r.fetchall.return_value = [("q_1",), ("q_2",)]
            else:
                mock_row = MagicMock()
                mock_row.__getitem__ = lambda self, idx: [8, 6][idx]
                r.fetchone.return_value = (8, 6)  # 8 total, 6 correct
            return r

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)

        with patch("app.core.memory.coverage.async_session", return_value=MagicMock()):
            result = await engine._get_accuracy("kp_1", mock_session)

        assert result is not None
        # 6/8 = 0.75
        assert abs(result - 0.75) < 0.001


class TestEnsureFullCoverage:
    """Tests for CoverageEngine.ensure_full_coverage()."""

    @pytest.mark.asyncio
    async def test_ensure_full_coverage_already_covered(self):
        """ensure_full_coverage() returns 'already_covered' when all points covered."""
        from app.core.memory.coverage import CoverageEngine

        engine = CoverageEngine()

        with patch.object(engine, "calculate", new_callable=AsyncMock) as mock_calc:
            mock_calc.return_value = {
                "uncovered_points": [],
                "total_knowledge_points": 5,
            }
            result = await engine.ensure_full_coverage("sum_1", "doc_1")

        assert result["status"] == "already_covered"
        assert result["generated"] == 0

    @pytest.mark.asyncio
    async def test_ensure_full_coverage_generates_for_uncovered(self):
        """ensure_full_coverage() generates questions and flashcards for uncovered points."""
        from app.core.memory.coverage import CoverageEngine

        engine = CoverageEngine()

        with patch.object(engine, "calculate", new_callable=AsyncMock) as mock_calc:
            mock_calc.return_value = {
                "uncovered_points": [{"id": "kp_1", "title": "Topic", "level": 2}],
                "total_knowledge_points": 3,
            }

            mock_node = MagicMock()
            mock_node.title = "Topic"
            mock_node.explanation = "Explanation"

            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=mock_node)
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()

            with patch("app.core.memory.coverage.async_session") as mock_session_ctx:
                mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

                with patch("app.core.memory.coverage.quiz_generator") as mock_qg:
                    mock_qg.generate_questions = AsyncMock(return_value=[
                        {"id": "q_new", "question_text": "New Q?"}
                    ])
                    with patch("app.core.memory.coverage.card_generator") as mock_cg:
                        mock_cg.generate_cards = AsyncMock(return_value=[
                            {"id": "c_new", "card_type": "qa"}
                        ])
                        result = await engine.ensure_full_coverage("sum_1", "doc_1")

        assert result["status"] == "filled"
        assert result["generated_questions"] >= 1
        assert result["generated_cards"] >= 1

    @pytest.mark.asyncio
    async def test_ensure_full_coverage_catches_per_point_exceptions(self):
        """ensure_full_coverage() catches per-point generation exceptions."""
        from app.core.memory.coverage import CoverageEngine

        engine = CoverageEngine()

        with patch.object(engine, "calculate", new_callable=AsyncMock) as mock_calc:
            mock_calc.return_value = {
                "uncovered_points": [
                    {"id": "kp_bad", "title": "Bad", "level": 2},
                    {"id": "kp_good", "title": "Good", "level": 2},
                ],
                "total_knowledge_points": 3,
            }

            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=None)  # First node not found
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()

            with patch("app.core.memory.coverage.async_session") as mock_session_ctx:
                mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

                result = await engine.ensure_full_coverage("sum_1", "doc_1")

        # Should not raise even if individual point generation fails
        assert "status" in result
