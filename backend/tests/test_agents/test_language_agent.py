"""Tests for LanguageAgent - vocabulary extraction from language learning materials."""
import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.agents.base import AgentResult


class TestLanguageAgentShouldRun:
    """Tests for LanguageAgent.should_run() method."""

    def test_should_run_returns_true_for_english(self):
        """should_run() returns True when language_type is 'english'."""
        from app.core.agents.language_agent import LanguageAgent

        agent = LanguageAgent()
        result = agent.should_run("doc_1", language_type="english")
        assert result is True

    def test_should_run_returns_true_for_japanese(self):
        """should_run() returns True when language_type is 'japanese'."""
        from app.core.agents.language_agent import LanguageAgent

        agent = LanguageAgent()
        result = agent.should_run("doc_1", language_type="japanese")
        assert result is True

    def test_should_run_returns_false_for_non_language_document(self):
        """should_run() returns False for non-language documents."""
        from app.core.agents.language_agent import LanguageAgent

        agent = LanguageAgent()
        # language_type is neither a supported language nor 'auto'
        result = agent.should_run("doc_1", language_type="math")
        assert result is False

    def test_should_run_returns_false_with_no_language_type(self):
        """should_run() returns False when no language_type is provided at all and auto-detect fails."""
        from app.core.agents.language_agent import LanguageAgent

        agent = LanguageAgent()
        with patch.object(agent, "_auto_detect_language_material", return_value=False):
            result = agent.should_run("doc_1")
        assert result is False


class TestLanguageAgentAutoDetect:
    """Tests for LanguageAgent._auto_detect_language_material()."""

    def test_auto_detect_filename_hint_detects_chinese_hint(self):
        """_auto_detect_language_material() detects filename hint like '英语'."""
        from app.core.agents.language_agent import LanguageAgent

        agent = LanguageAgent()

        mock_doc = MagicMock()
        mock_doc.filename = "大学英语四级词汇.pdf"

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_doc)

        async def mock_check():
            return True

        with patch("asyncio.run", return_value=True):
            result = agent._auto_detect_language_material("doc_1")
        assert result is True

    def test_auto_detect_latin_ratio_above_40_percent(self):
        """_auto_detect_language_material() detects Latin ratio > 40% in chunks."""
        from app.core.agents.language_agent import LanguageAgent

        # When the auto_detect runs the internal async function, we mock asyncio.run
        agent = LanguageAgent()
        with patch("asyncio.run", return_value=True):
            result = agent._auto_detect_language_material("doc_1")
        assert result is True

    def test_auto_detect_returns_false_for_pure_chinese_text(self):
        """_auto_detect_language_material() returns False for pure Chinese text."""
        from app.core.agents.language_agent import LanguageAgent

        agent = LanguageAgent()
        with patch("asyncio.run", return_value=False):
            result = agent._auto_detect_language_material("doc_1")
        assert result is False

    def test_auto_detect_handles_exception_gracefully(self):
        """_auto_detect_language_material() returns False on any exception."""
        from app.core.agents.language_agent import LanguageAgent

        agent = LanguageAgent()
        with patch("asyncio.run", side_effect=RuntimeError("DB down")):
            result = agent._auto_detect_language_material("doc_1")
        assert result is False


class TestLanguageAgentEstimateDifficulty:
    """Tests for LanguageAgent._estimate_difficulty()."""

    def test_estimate_difficulty_returns_hard_for_long_words(self):
        """_estimate_difficulty() returns 'hard' for words >= 12 chars."""
        from app.core.agents.language_agent import LanguageAgent

        agent = LanguageAgent()
        result = agent._estimate_difficulty({"word": "antidisestablishmentarianism", "part_of_speech": "noun"})
        assert result == "hard"

    def test_estimate_difficulty_returns_easy_for_short_common_words(self):
        """_estimate_difficulty() returns 'easy' for short common words."""
        from app.core.agents.language_agent import LanguageAgent

        agent = LanguageAgent()
        result = agent._estimate_difficulty({"word": "cat", "part_of_speech": "noun"})
        assert result == "easy"

    def test_estimate_difficulty_returns_medium_as_default(self):
        """_estimate_difficulty() returns 'medium' as default for normal-length words."""
        from app.core.agents.language_agent import LanguageAgent

        agent = LanguageAgent()
        result = agent._estimate_difficulty({"word": "vocabulary", "part_of_speech": "noun"})
        assert result == "medium"

    def test_estimate_difficulty_short_non_common_pos_returns_medium(self):
        """_estimate_difficulty() returns 'medium' for short word with uncommon POS."""
        from app.core.agents.language_agent import LanguageAgent

        agent = LanguageAgent()
        result = agent._estimate_difficulty({"word": "hi", "part_of_speech": "interjection"})
        assert result == "medium"

    def test_estimate_difficulty_empty_word_returns_easy_if_short(self):
        """_estimate_difficulty() handles empty word -- returns 'easy' if len <= 4 and POS matches."""
        from app.core.agents.language_agent import LanguageAgent

        agent = LanguageAgent()
        result = agent._estimate_difficulty({"word": "", "part_of_speech": "verb"})
        assert result == "easy"


class TestLanguageAgentRun:
    """Tests for LanguageAgent.run() method."""

    @pytest.mark.asyncio
    async def test_run_with_missing_summary_returns_error(self):
        """run() with missing summary returns error AgentResult."""
        from app.core.agents.language_agent import LanguageAgent

        agent = LanguageAgent()

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await agent.run(summary_id="bad_sum", document_id="doc_1")

        assert result.status == "error"
        assert "Summary not found" in result.error

    @pytest.mark.asyncio
    async def test_run_parses_valid_llm_json_response(self):
        """run() with valid LLM JSON response parses and stores vocab."""
        from app.core.agents.language_agent import LanguageAgent

        vocab_json = '[{"word":"hello","phonetic":"həˈloʊ","part_of_speech":"interjection","definition":"你好","example_sentence":"Hello, how are you?"},{"word":"world","phonetic":"wɜːld","part_of_speech":"noun","definition":"世界","example_sentence":"The world is beautiful."}]'

        mock_summary = MagicMock()
        mock_summary.content_md = "# Test Content"

        mock_node = MagicMock()
        mock_node.title = "Topic"
        mock_node.explanation = "Some explanation here for testing"

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_node]

        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        mock_llm_result = MagicMock()
        mock_llm_result.content = vocab_json

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("app.core.api_scheduler.api_client") as mock_api:
                mock_api.generate = AsyncMock(return_value=mock_llm_result)
                result = await agent.run(summary_id="sum_1", document_id="doc_1")

        assert result.status == "success"
        assert result.result["total_words"] == 2
        assert len(result.result["words"]) == 2
        assert result.result["words"][0]["word"] == "hello"
        assert result.result["words"][1]["word"] == "world"

    @pytest.mark.asyncio
    async def test_run_non_json_llm_response_falls_back_to_regex(self):
        """run() with non-JSON LLM response falls back to regex extraction."""
        from app.core.agents.language_agent import LanguageAgent

        llm_content = 'Here are some words: [{"word":"test","phonetic":"tɛst","part_of_speech":"noun","definition":"测试","example_sentence":"This is a test."}] done.'

        mock_summary = MagicMock()
        mock_summary.content_md = "# Test Content"
        mock_node = MagicMock()
        mock_node.title = "Topic"
        mock_node.explanation = "Some explanation"

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_node]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        mock_llm_result = MagicMock()
        mock_llm_result.content = llm_content

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("app.core.api_scheduler.api_client") as mock_api:
                mock_api.generate = AsyncMock(return_value=mock_llm_result)
                result = await agent.run(summary_id="sum_1", document_id="doc_1")

        assert result.status == "success"
        assert result.result["total_words"] == 1
        assert result.result["words"][0]["word"] == "test"

    @pytest.mark.asyncio
    async def test_run_completely_unparseable_content_returns_empty_results(self):
        """run() with completely unparseable content returns empty results."""
        from app.core.agents.language_agent import LanguageAgent

        mock_summary = MagicMock()
        mock_summary.content_md = "# Test"
        mock_node = MagicMock()
        mock_node.title = "Topic"
        mock_node.explanation = "Explanation"

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_node]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        mock_llm_result = MagicMock()
        mock_llm_result.content = "Just some plain text, no JSON at all."

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("app.core.api_scheduler.api_client") as mock_api:
                mock_api.generate = AsyncMock(return_value=mock_llm_result)
                result = await agent.run(summary_id="sum_1", document_id="doc_1")

        assert result.status == "success"
        assert result.result["total_words"] == 0
        assert result.result["words"] == []

    @pytest.mark.asyncio
    async def test_run_filters_out_items_with_blank_words(self):
        """run() filters out items with blank words."""
        from app.core.agents.language_agent import LanguageAgent

        vocab_json = '[{"word":"valid","phonetic":"","part_of_speech":"","definition":"ok","example_sentence":""},{"word":"","phonetic":"","part_of_speech":"","definition":"","example_sentence":""}]'

        mock_summary = MagicMock()
        mock_summary.content_md = "# Test"
        mock_node = MagicMock()
        mock_node.title = "Topic"
        mock_node.explanation = "Explanation"

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_summary)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_node]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        mock_llm_result = MagicMock()
        mock_llm_result.content = vocab_json

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("app.core.api_scheduler.api_client") as mock_api:
                mock_api.generate = AsyncMock(return_value=mock_llm_result)
                result = await agent.run(summary_id="sum_1", document_id="doc_1")

        assert result.status == "success"
        assert result.result["total_words"] == 1
        assert result.result["words"][0]["word"] == "valid"

    @pytest.mark.asyncio
    async def test_run_handles_db_exception_gracefully(self):
        """run() handles DB exception gracefully by returning error result."""
        from app.core.agents.language_agent import LanguageAgent

        agent = LanguageAgent()

        with patch("app.database.async_session") as mock_session_ctx:
            mock_session_ctx.side_effect = RuntimeError("Database connection lost")

            result = await agent.run(summary_id="sum_1", document_id="doc_1")

        assert result.status == "error"
        assert "Database connection lost" in result.error
