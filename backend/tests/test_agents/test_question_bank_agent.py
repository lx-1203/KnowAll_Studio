"""Tests for QuestionBankAgent - quiz question generation with Bloom's taxonomy."""
import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.agents.base import AgentResult


class TestQuestionBankHelpers:
    """Tests for helper/static methods on QuestionBankAgent."""

    def test_sample_cognitive_level_respects_distribution_weights(self):
        """_sample_cognitive_level() respects Bloom's taxonomy distribution weights."""
        from app.core.agents.question_bank_agent import QuestionBankAgent

        agent = QuestionBankAgent()
        dist = {
            "L1_remember": 0.10,
            "L2_understand": 0.30,
            "L3_apply": 0.30,
            "L4_analyze": 0.15,
            "L5_evaluate": 0.10,
            "L6_create": 0.05,
        }
        # Run many times, verify all levels can appear
        results = [agent._sample_cognitive_level(dist) for _ in range(1000)]
        for level in dist:
            assert level in results

    def test_sample_cognitive_level_zero_weights_returns_l2_understand(self):
        """_sample_cognitive_level() returns 'L2_understand' when weights sum to 0."""
        from app.core.agents.question_bank_agent import QuestionBankAgent

        agent = QuestionBankAgent()
        result = agent._sample_cognitive_level({"L1_remember": 0, "L2_understand": 0})
        assert result == "L2_understand"

    def test_base_difficulty_for_level_all_six_bloom_levels(self):
        """_base_difficulty_for_level() returns correct values for all 6 Bloom's levels."""
        from app.core.agents.question_bank_agent import QuestionBankAgent

        agent = QuestionBankAgent()
        assert agent._base_difficulty_for_level("L1_remember") == 0.25
        assert agent._base_difficulty_for_level("L2_understand") == 0.40
        assert agent._base_difficulty_for_level("L3_apply") == 0.55
        assert agent._base_difficulty_for_level("L4_analyze") == 0.68
        assert agent._base_difficulty_for_level("L5_evaluate") == 0.78
        assert agent._base_difficulty_for_level("L6_create") == 0.85

    def test_base_difficulty_for_level_unknown_returns_default(self):
        """_base_difficulty_for_level() returns 0.5 for unknown level."""
        from app.core.agents.question_bank_agent import QuestionBankAgent

        agent = QuestionBankAgent()
        assert agent._base_difficulty_for_level("L99_unknown") == 0.5

    def test_group_by_topic_groups_by_parent_id(self):
        """_group_by_topic() groups nodes by parent_id correctly."""
        from app.core.agents.question_bank_agent import QuestionBankAgent

        agent = QuestionBankAgent()

        node_a = MagicMock()
        node_a.parent_id = "parent_1"
        node_a.title = "Topic A"
        node_a.explanation = "Explanation A"
        node_a.related_concepts = ""
        node_a.examples = ""

        node_b = MagicMock()
        node_b.parent_id = "parent_1"
        node_b.title = "Topic B"
        node_b.explanation = "Explanation B"
        node_b.related_concepts = "Concept"
        node_b.examples = "Example"

        node_c = MagicMock()
        node_c.parent_id = "parent_2"
        node_c.title = "Topic C"
        node_c.explanation = "Explanation C"
        node_c.related_concepts = ""
        node_c.examples = ""

        result = agent._group_by_topic([node_a, node_b, node_c])
        assert len(result) == 2
        assert "parent_1" in result
        assert "parent_2" in result
        assert "Topic A" in result["parent_1"]
        assert "Topic B" in result["parent_1"]
        assert "Topic C" in result["parent_2"]

    def test_group_by_topic_handles_plain_dicts(self):
        """_group_by_topic() handles both ORM objects and plain dicts."""
        from app.core.agents.question_bank_agent import QuestionBankAgent

        agent = QuestionBankAgent()

        nodes = [
            {"parent_id": "p1", "title": "T1", "explanation": "E1", "related_concepts": "", "examples": ""},
            {"parent_id": None, "title": "T2", "explanation": "E2", "related_concepts": "", "examples": ""},
        ]

        result = agent._group_by_topic(nodes)
        assert len(result) == 2
        assert "p1" in result
        assert "general" in result  # None parent_id maps to "general"


class TestQuestionBankRun:
    """Tests for QuestionBankAgent.run() method."""

    @pytest.mark.asyncio
    async def test_run_with_missing_summary_returns_error(self):
        """run() with missing summary returns error AgentResult."""
        from app.core.agents.question_bank_agent import QuestionBankAgent

        agent = QuestionBankAgent()

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await agent.run(summary_id="bad_sum", document_id="doc_1")

        assert result.status == "error"
        assert "Summary not found" in result.error

    @pytest.mark.asyncio
    async def test_run_with_no_nodes_falls_back_to_markdown_extraction(self):
        """run() with no nodes falls back to Markdown extraction from summary."""
        from app.core.agents.question_bank_agent import QuestionBankAgent

        agent = QuestionBankAgent()

        mock_summary = MagicMock()
        mock_summary.content_md = "# Knowledge Summary\n\n## Topic 1\nExplanation here."

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)

        # Return empty nodes list
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        extracted_nodes = [
            {
                "id": "kp_1",
                "parent_id": None,
                "level": 1,
                "sequence": 1,
                "title": "Topic 1",
                "explanation": "Explanation here",
                "related_concepts": "",
                "examples": "",
                "tags": [],
            }
        ]

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "app.core.agents.question_bank_agent.summary_generator.extract_nodes_from_markdown",
                return_value=extracted_nodes,
            ):
                with patch(
                    "app.core.agents.question_bank_agent.relation_extractor.extract",
                    new_callable=AsyncMock,
                ) as mock_rel_extract:
                    mock_rel_extract.return_value = ([], [])
                    with patch(
                        "app.core.agents.question_bank_agent.quiz_generator.generate_questions",
                        new_callable=AsyncMock,
                    ) as mock_gen:
                        mock_gen.return_value = [
                            {"id": "q_1", "question_text": "What?", "question_type": "single_choice", "cognitive_level": "L2_understand", "reviewed": True, "review_decision": "pass", "tags": []}
                        ]
                        result = await agent.run(summary_id="sum_1", document_id="doc_1")

        assert result.status == "success"
        assert result.result["total_questions"] >= 1

    @pytest.mark.asyncio
    async def test_run_writes_knowledge_coverage_records_per_question(self):
        """run() writes KnowledgeCoverage records per question."""
        from app.core.agents.question_bank_agent import QuestionBankAgent

        agent = QuestionBankAgent()

        mock_summary = MagicMock()
        mock_summary.content_md = "# Test"

        mock_node = MagicMock()
        mock_node.id = "kp_001"
        mock_node.parent_id = "parent_1"
        mock_node.level = 2
        mock_node.sequence = 1
        mock_node.title = "Topic A"
        mock_node.explanation = "Explanation A"
        mock_node.related_concepts = ""
        mock_node.examples = ""
        mock_node.tags = []

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_node]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "app.core.agents.question_bank_agent.relation_extractor.extract",
                new_callable=AsyncMock,
            ) as mock_rel:
                mock_rel.return_value = ([], [])
                with patch(
                    "app.core.agents.question_bank_agent.quiz_generator.generate_questions",
                    new_callable=AsyncMock,
                ) as mock_gen:
                    mock_gen.return_value = [
                        {"id": "q_1", "question_text": "What?", "question_type": "single_choice", "cognitive_level": "L2_understand", "reviewed": False, "review_decision": "none", "tags": ["Topic"]}
                    ]
                    result = await agent.run(summary_id="sum_1", document_id="doc_1")

        assert result.status == "success"
        # session.add should have been called for the coverage record
        assert mock_session.add.call_count >= 1

    @pytest.mark.asyncio
    async def test_run_handles_kg_relation_extraction_failure_gracefully(self):
        """run() handles KG relation extraction failure gracefully."""
        from app.core.agents.question_bank_agent import QuestionBankAgent

        agent = QuestionBankAgent()

        mock_summary = MagicMock()
        mock_summary.content_md = "# Test"

        mock_node = MagicMock()
        mock_node.id = "kp_001"
        mock_node.parent_id = "parent_1"
        mock_node.level = 2
        mock_node.sequence = 1
        mock_node.title = "Topic"
        mock_node.explanation = "Explanation"
        mock_node.related_concepts = ""
        mock_node.examples = ""
        mock_node.tags = []

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_node]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "app.core.agents.question_bank_agent.relation_extractor.extract",
                new_callable=AsyncMock,
                side_effect=RuntimeError("KG extraction failed"),
            ):
                with patch(
                    "app.core.agents.question_bank_agent.quiz_generator.generate_questions",
                    new_callable=AsyncMock,
                ) as mock_gen:
                    mock_gen.return_value = [
                        {"id": "q_1", "question_text": "What?", "question_type": "single_choice", "cognitive_level": "L2_understand", "reviewed": False, "review_decision": "none", "tags": []}
                    ]
                    result = await agent.run(summary_id="sum_1", document_id="doc_1")

        assert result.status == "success"
        assert result.result["total_questions"] >= 1

    @pytest.mark.asyncio
    async def test_run_respects_enable_kg_relations_false(self):
        """run() respects enable_kg_relations=False config -- skips KG extraction."""
        from app.core.agents.question_bank_agent import QuestionBankAgent

        agent = QuestionBankAgent()

        mock_summary = MagicMock()
        mock_summary.content_md = "# Test"

        mock_node = MagicMock()
        mock_node.id = "kp_001"
        mock_node.parent_id = "parent_1"
        mock_node.level = 2
        mock_node.sequence = 1
        mock_node.title = "Topic"
        mock_node.explanation = "Explanation"
        mock_node.related_concepts = ""
        mock_node.examples = ""
        mock_node.tags = []

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_node]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "app.core.agents.question_bank_agent.relation_extractor.extract",
                new_callable=AsyncMock,
            ) as mock_rel_extract:
                with patch(
                    "app.core.agents.question_bank_agent.quiz_generator.generate_questions",
                    new_callable=AsyncMock,
                ) as mock_gen:
                    mock_gen.return_value = [
                        {"id": "q_1", "question_text": "What?", "question_type": "single_choice", "cognitive_level": "L2_understand", "reviewed": False, "review_decision": "none", "tags": []}
                    ]
                    result = await agent.run(
                        summary_id="sum_1",
                        document_id="doc_1",
                        config={"enable_kg_relations": False},
                    )

        assert result.status == "success"
        # KG extraction should NOT have been called
        mock_rel_extract.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_handles_db_exception_gracefully(self):
        """run() handles DB exception gracefully with error AgentResult."""
        from app.core.agents.question_bank_agent import QuestionBankAgent

        agent = QuestionBankAgent()

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.side_effect = RuntimeError("DB crash")

            result = await agent.run(summary_id="sum_1", document_id="doc_1")

        assert result.status == "error"
        assert "DB crash" in result.error
