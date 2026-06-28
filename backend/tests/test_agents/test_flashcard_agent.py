"""Tests for FlashcardAgent - memory flashcard generation with quality review."""
import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.agents.base import AgentResult


class TestFlashcardAgentHelpers:
    """Tests for FlashcardAgent private helper methods."""

    def test_assign_card_types_distributes_cards_across_topic_groups(self):
        """_assign_card_types() distributes cards across topic groups."""
        from app.core.agents.flashcard_agent import FlashcardAgent

        agent = FlashcardAgent()
        topic_groups = {
            "parent_1": {
                "nodes": [{"id": "n1", "title": "T1", "explanation": "E1", "level": 2}],
                "text": "## T1\nE1",
            },
            "parent_2": {
                "nodes": [{"id": "n2", "title": "T2", "explanation": "E2", "level": 2}],
                "text": "## T2\nE2",
            },
        }
        assignments = agent._assign_card_types(topic_groups, total_count=10, allowed_types=["qa", "cloze"])
        assert len(assignments) > 0
        total_assigned = sum(a["count"] for a in assignments)
        assert total_assigned <= 10
        for a in assignments:
            assert a["card_type"] in ("qa", "cloze")
            assert "text" in a
            assert "count" in a

    def test_assign_card_types_respects_max_cards_per_batch(self):
        """_assign_card_types() respects MAX_CARDS_PER_BATCH limit."""
        from app.core.agents.flashcard_agent import FlashcardAgent, QUALITY_MAX_CARDS_PER_BATCH

        agent = FlashcardAgent()
        topic_groups = {
            "p1": {
                "nodes": [{"id": "n1", "title": "T1", "explanation": "E1", "level": 2}],
                "text": "## T1\nE1",
            },
        }
        assignments = agent._assign_card_types(topic_groups, total_count=100, allowed_types=["qa"])
        for a in assignments:
            assert a["count"] <= QUALITY_MAX_CARDS_PER_BATCH

    def test_assign_card_types_respects_allowed_types_filter(self):
        """_assign_card_types() respects allowed_types filter -- only returns allowed types."""
        from app.core.agents.flashcard_agent import FlashcardAgent

        agent = FlashcardAgent()
        topic_groups = {
            "p1": {
                "nodes": [{"id": "n1", "title": "T1", "explanation": "E1", "level": 2}],
                "text": "## T1\nE1",
            },
        }
        assignments = agent._assign_card_types(topic_groups, total_count=5, allowed_types=["cloze"])
        for a in assignments:
            assert a["card_type"] == "cloze"


class TestFlashcardAgentRun:
    """Tests for FlashcardAgent.run() method."""

    @pytest.mark.asyncio
    async def test_run_with_missing_summary_returns_error(self):
        """run() with missing summary returns error AgentResult."""
        from app.core.agents.flashcard_agent import FlashcardAgent

        agent = FlashcardAgent()

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await agent.run(summary_id="bad_sum", document_id="doc_1")

        assert result.status == "error"
        assert "Summary not found" in result.error

    @pytest.mark.asyncio
    async def test_run_with_no_nodes_returns_error(self):
        """run() with no nodes returns error when MD extraction also yields nothing."""
        from app.core.agents.flashcard_agent import FlashcardAgent

        agent = FlashcardAgent()

        mock_summary = MagicMock()
        mock_summary.content_md = ""

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "app.core.agents.flashcard_agent.summary_generator.extract_nodes_from_markdown",
                return_value=[],
            ):
                result = await agent.run(summary_id="sum_1", document_id="doc_1")

        assert result.status == "error"
        assert "No knowledge points found" in result.error

    @pytest.mark.asyncio
    async def test_run_creates_new_deck_when_none_exists(self):
        """run() creates new deck when no deck exists."""
        from app.core.agents.flashcard_agent import FlashcardAgent

        agent = FlashcardAgent()

        mock_summary = MagicMock()
        mock_summary.content_md = "# Test"

        mock_node = MagicMock()
        mock_node.id = "kp_1"
        mock_node.parent_id = "parent_1"
        mock_node.level = 2
        mock_node.sequence = 1
        mock_node.title = "Topic"
        mock_node.explanation = "Explanation"
        mock_node.related_concepts = ""
        mock_node.examples = ""

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_node]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        # First execute returns nodes, second returns None (no deck)
        mock_deck_result = MagicMock()
        mock_deck_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_deck_result])
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("app.core.memory.card_generator") as mock_cg:
                mock_cg.generate = AsyncMock(return_value=[
                    {"knowledge_point_id": "kp_1", "card_type": "qa", "front": "Q1", "back": "A1", "hints": "", "tags": []}
                ])
                mock_cg.validate_card.return_value = (True, "")

                with patch("app.core.memory.fsrs") as mock_fsrs:
                    mock_fsrs.init_card.return_value = {
                        "stability": 0, "difficulty": 0, "retrievability": 0, "state": "new"
                    }
                    result = await agent.run(summary_id="sum_1", document_id="doc_1")

        assert result.status == "success"
        # Deck should have been added to session (new deck creation)
        assert mock_session.add.call_count >= 2  # deck + cards + schedule + coverage

    @pytest.mark.asyncio
    async def test_run_reuses_existing_deck(self):
        """run() reuses existing deck when one is found."""
        from app.core.agents.flashcard_agent import FlashcardAgent

        agent = FlashcardAgent()

        mock_summary = MagicMock()
        mock_summary.content_md = "# Test"

        mock_node = MagicMock()
        mock_node.id = "kp_1"
        mock_node.parent_id = "parent_1"
        mock_node.level = 2
        mock_node.sequence = 1
        mock_node.title = "Topic"
        mock_node.explanation = "Explanation"
        mock_node.related_concepts = ""
        mock_node.examples = ""

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_node]
        mock_node_result = MagicMock()
        mock_node_result.scalars.return_value = mock_scalars

        existing_deck = MagicMock()
        existing_deck.id = "deck_existing"
        existing_deck.name = "DefaultDeck"
        existing_deck.card_count = 5

        mock_deck_result = MagicMock()
        mock_deck_result.scalar_one_or_none.return_value = existing_deck

        mock_session.execute = AsyncMock(side_effect=[mock_node_result, mock_deck_result])
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("app.core.memory.card_generator") as mock_cg:
                mock_cg.generate = AsyncMock(return_value=[
                    {"knowledge_point_id": "kp_1", "card_type": "qa", "front": "Q1", "back": "A1", "hints": "", "tags": []}
                ])
                mock_cg.validate_card.return_value = (True, "")

                with patch("app.core.memory.fsrs") as mock_fsrs:
                    mock_fsrs.init_card.return_value = {
                        "stability": 0, "difficulty": 0, "retrievability": 0, "state": "new"
                    }
                    result = await agent.run(
                        summary_id="sum_1", document_id="doc_1",
                        config={"deck_name": "DefaultDeck"},
                    )

        assert result.status == "success"
        assert result.result["deck_id"] == "deck_existing"

    @pytest.mark.asyncio
    async def test_run_filters_out_invalid_cards_via_validate_card(self):
        """run() filters out invalid cards via validate_card."""
        from app.core.agents.flashcard_agent import FlashcardAgent

        agent = FlashcardAgent()

        mock_summary = MagicMock()
        mock_summary.content_md = "# Test"

        mock_node = MagicMock()
        mock_node.id = "kp_1"
        mock_node.parent_id = "parent_1"
        mock_node.level = 2
        mock_node.sequence = 1
        mock_node.title = "Topic"
        mock_node.explanation = "Explanation"
        mock_node.related_concepts = ""
        mock_node.examples = ""

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_node]
        mock_node_result = MagicMock()
        mock_node_result.scalars.return_value = mock_scalars

        existing_deck = MagicMock()
        existing_deck.id = "deck_0"
        existing_deck.name = "默认牌组"
        existing_deck.card_count = 0

        mock_deck_result = MagicMock()
        mock_deck_result.scalar_one_or_none.return_value = existing_deck
        mock_session.execute = AsyncMock(side_effect=[mock_node_result, mock_deck_result])
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        # Return 3 cards, but validate_card rejects 1
        validate_call_count = [0]

        def validate_side_effect(card, ctype):
            validate_call_count[0] += 1
            # Reject the second card
            if validate_call_count[0] == 2:
                return (False, "empty_front")
            return (True, "")

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("app.core.memory.card_generator") as mock_cg:
                mock_cg.generate = AsyncMock(return_value=[
                    {"knowledge_point_id": "kp_1", "card_type": "qa", "front": "Q1", "back": "A1", "hints": "", "tags": []},
                    {"knowledge_point_id": "kp_1", "card_type": "qa", "front": "", "back": "", "hints": "", "tags": []},
                    {"knowledge_point_id": "kp_1", "card_type": "qa", "front": "Q2", "back": "A2", "hints": "", "tags": []},
                ])
                mock_cg.validate_card.side_effect = validate_side_effect

                with patch("app.core.memory.fsrs") as mock_fsrs:
                    mock_fsrs.init_card.return_value = {
                        "stability": 0, "difficulty": 0, "retrievability": 0, "state": "new"
                    }
                    result = await agent.run(summary_id="sum_1", document_id="doc_1")

        assert result.status == "success"
        assert result.result["generation_stats"]["quality_filtered"] >= 1

    @pytest.mark.asyncio
    async def test_run_skips_quality_review_when_disabled(self):
        """run() skips quality review when enable_quality_review=False."""
        from app.core.agents.flashcard_agent import FlashcardAgent

        agent = FlashcardAgent()

        mock_summary = MagicMock()
        mock_summary.content_md = "# Test"
        # Create 10+ nodes so that enough cards are generated for review eligibility
        nodes = []
        for i in range(10):
            n = MagicMock()
            n.id = f"kp_{i}"
            n.parent_id = "parent_1"
            n.level = 2
            n.sequence = i
            n.title = f"Topic {i}"
            n.explanation = f"Explanation {i}"
            n.related_concepts = ""
            n.examples = ""
            nodes.append(n)

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = nodes
        mock_node_result = MagicMock()
        mock_node_result.scalars.return_value = mock_scalars

        existing_deck = MagicMock()
        existing_deck.id = "deck_x"
        existing_deck.name = "Deck"
        existing_deck.card_count = 0

        mock_deck_result = MagicMock()
        mock_deck_result.scalar_one_or_none.return_value = existing_deck
        mock_session.execute = AsyncMock(side_effect=[mock_node_result, mock_deck_result])
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        cards = []
        for i in range(12):
            cards.append({
                "knowledge_point_id": f"kp_{i % 10}",
                "card_type": "qa",
                "front": f"Q{i}",
                "back": f"A{i}",
                "hints": "",
                "tags": [],
            })

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("app.core.memory.card_generator") as mock_cg:
                mock_cg.generate = AsyncMock(return_value=cards)
                mock_cg.validate_card.return_value = (True, "")

                with patch("app.core.memory.fsrs") as mock_fsrs:
                    mock_fsrs.init_card.return_value = {
                        "stability": 0, "difficulty": 0, "retrievability": 0, "state": "new"
                    }
                    result = await agent.run(
                        summary_id="sum_1", document_id="doc_1",
                        config={"enable_quality_review": False},
                    )

        assert result.status == "success"
        # With quality review disabled, review_action should NOT be present
        stats = result.result.get("generation_stats", {})
        assert "review_action" not in stats

    @pytest.mark.asyncio
    async def test_run_quality_review_low_score_retained(self):
        """run() handles quality review with avg score < 3.0 (low_score_retained)."""
        from app.core.agents.flashcard_agent import FlashcardAgent

        agent = FlashcardAgent()

        mock_summary = MagicMock()
        mock_summary.content_md = "# Test"
        nodes = []
        for i in range(10):
            n = MagicMock()
            n.id = f"kp_{i}"
            n.parent_id = "parent_1"
            n.level = 2
            n.sequence = i
            n.title = f"Topic {i}"
            n.explanation = f"Explanation {i}"
            n.related_concepts = ""
            n.examples = ""
            nodes.append(n)

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = nodes
        mock_node_result = MagicMock()
        mock_node_result.scalars.return_value = mock_scalars

        existing_deck = MagicMock()
        existing_deck.id = "deck_x"
        existing_deck.name = "Deck"
        existing_deck.card_count = 0

        mock_deck_result = MagicMock()
        mock_deck_result.scalar_one_or_none.return_value = existing_deck
        mock_session.execute = AsyncMock(side_effect=[mock_node_result, mock_deck_result])
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        cards = []
        for i in range(12):
            cards.append({
                "knowledge_point_id": f"kp_{i % 10}",
                "card_type": "qa",
                "front": f"Q{i}",
                "back": f"A{i}",
                "hints": "",
                "tags": [],
            })

        # Mock the quality review to return low scores
        mock_review_result = MagicMock()
        mock_review_result.content = '{"total": 2, "passed": false, "suggestions": "improve clarity"}'

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("app.core.memory.card_generator") as mock_cg:
                mock_cg.generate = AsyncMock(return_value=cards)
                mock_cg.validate_card.return_value = (True, "")

                with patch("app.core.memory.fsrs") as mock_fsrs:
                    mock_fsrs.init_card.return_value = {
                        "stability": 0, "difficulty": 0, "retrievability": 0, "state": "new"
                    }
                    with patch("app.core.agents.flashcard_agent.prompt_engine") as mock_pe:
                        mock_pe.render.return_value = [{"role": "system", "content": "test"}]
                        with patch("app.core.agents.flashcard_agent.api_client") as mock_api:
                            mock_api.generate = AsyncMock(return_value=mock_review_result)
                            result = await agent.run(
                                summary_id="sum_1", document_id="doc_1",
                                config={"enable_quality_review": True},
                            )

        assert result.status == "success"
        stats = result.result.get("generation_stats", {})
        # Should have review info since enough cards and review enabled
        assert "review_action" in stats or "review_avg_score" in stats

    @pytest.mark.asyncio
    async def test_run_quality_review_passed(self):
        """run() handles quality review with avg score >= 3.0 (passed)."""
        from app.core.agents.flashcard_agent import FlashcardAgent

        agent = FlashcardAgent()

        mock_summary = MagicMock()
        mock_summary.content_md = "# Test"
        nodes = []
        for i in range(10):
            n = MagicMock()
            n.id = f"kp_{i}"
            n.parent_id = "parent_1"
            n.level = 2
            n.sequence = i
            n.title = f"Topic {i}"
            n.explanation = f"Explanation {i}"
            n.related_concepts = ""
            n.examples = ""
            nodes.append(n)

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = nodes
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        # After first execute for nodes, subsequent ones for deck
        mock_deck_result = MagicMock()
        existing_deck = MagicMock()
        existing_deck.id = "deck_pass"
        existing_deck.name = "Deck"
        existing_deck.card_count = 0
        mock_deck_result.scalar_one_or_none.return_value = existing_deck

        # We need to handle multiple execute calls
        execute_results = [mock_result, mock_deck_result]
        mock_session.execute = AsyncMock(side_effect=execute_results)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        cards = []
        for i in range(12):
            cards.append({
                "knowledge_point_id": f"kp_{i % 10}",
                "card_type": "qa",
                "front": f"Q{i} is a great question with detail",
                "back": f"A{i} has substantial content",
                "hints": "",
                "tags": [],
            })

        mock_review_result = MagicMock()
        mock_review_result.content = '{"total": 4, "passed": true, "suggestions": ""}'

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("app.core.memory.card_generator") as mock_cg:
                mock_cg.generate = AsyncMock(return_value=cards)
                mock_cg.validate_card.return_value = (True, "")

                with patch("app.core.memory.fsrs") as mock_fsrs:
                    mock_fsrs.init_card.return_value = {
                        "stability": 0, "difficulty": 0, "retrievability": 0, "state": "new"
                    }
                    with patch("app.core.agents.flashcard_agent.prompt_engine") as mock_pe:
                        mock_pe.render.return_value = [{"role": "system", "content": "test"}]
                        with patch("app.core.agents.flashcard_agent.api_client") as mock_api:
                            mock_api.generate = AsyncMock(return_value=mock_review_result)
                            result = await agent.run(
                                summary_id="sum_1", document_id="doc_1",
                                config={"enable_quality_review": True},
                            )

        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_run_creates_coverage_records_per_card(self):
        """run() creates KnowledgeCoverage records per card."""
        from app.core.agents.flashcard_agent import FlashcardAgent

        agent = FlashcardAgent()

        mock_summary = MagicMock()
        mock_summary.content_md = "# Test"

        mock_node = MagicMock()
        mock_node.id = "kp_cov"
        mock_node.parent_id = "p1"
        mock_node.level = 2
        mock_node.sequence = 1
        mock_node.title = "Topic"
        mock_node.explanation = "Explanation"
        mock_node.related_concepts = ""
        mock_node.examples = ""

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_node]
        mock_node_result = MagicMock()
        mock_node_result.scalars.return_value = mock_scalars

        existing_deck = MagicMock()
        existing_deck.id = "deck_cov"
        existing_deck.name = "Deck"
        existing_deck.card_count = 0

        mock_deck_result = MagicMock()
        mock_deck_result.scalar_one_or_none.return_value = existing_deck
        mock_session.execute = AsyncMock(side_effect=[mock_node_result, mock_deck_result])
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("app.core.memory.card_generator") as mock_cg:
                mock_cg.generate = AsyncMock(return_value=[
                    {"knowledge_point_id": "kp_cov", "card_type": "qa", "front": "Q1", "back": "A1", "hints": "", "tags": []},
                    {"knowledge_point_id": "kp_cov", "card_type": "cloze", "front": "Q2", "back": "A2", "hints": "", "tags": []},
                ])
                mock_cg.validate_card.return_value = (True, "")

                with patch("app.core.memory.fsrs") as mock_fsrs:
                    mock_fsrs.init_card.return_value = {
                        "stability": 0, "difficulty": 0, "retrievability": 0, "state": "new"
                    }
                    result = await agent.run(summary_id="sum_1", document_id="doc_1")

        assert result.status == "success"
        # Coverage records should be in result
        assert result.result["coverage"]["covered_kp"] >= 1
