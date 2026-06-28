"""Tests for AgentOrchestrator - parallel agent scheduling and coordination."""
import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.agents.base import AgentResult


class TestAgentOrchestrator:
    """Tests for AgentOrchestrator orchestration logic."""

    def _make_agent_mock(self, name, should_run=True, run_result=None, run_exc=None):
        """Helper to create a mock agent with name, should_run, and run behavior."""
        agent = MagicMock()
        agent.name = name
        agent.should_run = MagicMock(return_value=should_run)
        if run_exc:
            agent.run = AsyncMock(side_effect=run_exc)
        elif run_result:
            agent.run = AsyncMock(return_value=run_result)
        else:
            agent.run = AsyncMock(
                return_value=AgentResult(agent=name, status="success", result={"ok": True})
            )
        return agent

    @pytest.mark.asyncio
    async def test_orchestrate_all_agents_succeed_returns_results_dict_with_all_success(self):
        """orchestrate() with all agents succeeding returns results dict with all status='success'."""
        from app.core.agents.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()
        agent_a = self._make_agent_mock("agent_a")
        agent_b = self._make_agent_mock("agent_b")
        agent_c = self._make_agent_mock("agent_c")

        with patch(
            "app.core.agents.orchestrator.AgentRegistry.create_all",
            return_value=[agent_a, agent_b, agent_c],
        ):
            with patch.object(orchestrator, "_generate_coverage_report", return_value={"coverage": 0.5}):
                result = await orchestrator.orchestrate(
                    summary_id="sum_1", document_id="doc_1"
                )

        assert result["results"]["agent_a"].status == "success"
        assert result["results"]["agent_b"].status == "success"
        assert result["results"]["agent_c"].status == "success"
        assert result["coverage_report"] == {"coverage": 0.5}

    @pytest.mark.asyncio
    async def test_orchestrate_one_agent_exception_others_still_complete(self):
        """orchestrate() with one agent raising exception -- others still complete (error isolation)."""
        from app.core.agents.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()
        agent_a = self._make_agent_mock("agent_a")
        agent_b = self._make_agent_mock("agent_b", run_exc=ValueError("B failed"))
        agent_c = self._make_agent_mock("agent_c")

        with patch(
            "app.core.agents.orchestrator.AgentRegistry.create_all",
            return_value=[agent_a, agent_b, agent_c],
        ):
            with patch.object(orchestrator, "_generate_coverage_report", return_value=None):
                result = await orchestrator.orchestrate(
                    summary_id="sum_1", document_id="doc_1"
                )

        assert result["results"]["agent_a"].status == "success"
        assert result["results"]["agent_b"].status == "error"
        assert "B failed" in result["results"]["agent_b"].error
        assert result["results"]["agent_c"].status == "success"

    @pytest.mark.asyncio
    async def test_orchestrate_should_run_returns_false_produces_skipped_result(self):
        """orchestrate() should_run() returning False produces 'skipped' result."""
        from app.core.agents.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()
        agent_active = self._make_agent_mock("active", should_run=True)
        agent_skip = self._make_agent_mock("skip", should_run=False)

        with patch(
            "app.core.agents.orchestrator.AgentRegistry.create_all",
            return_value=[agent_active, agent_skip],
        ):
            with patch.object(orchestrator, "_generate_coverage_report", return_value=None):
                result = await orchestrator.orchestrate(
                    summary_id="sum_1", document_id="doc_1"
                )

        assert result["results"]["active"].status == "success"
        assert result["results"]["skip"].status == "skipped"
        agent_skip.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_orchestrate_empty_agent_list_returns_empty_results(self):
        """orchestrate() with empty agent list returns empty results dict."""
        from app.core.agents.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        with patch(
            "app.core.agents.orchestrator.AgentRegistry.create_all",
            return_value=[],
        ):
            result = await orchestrator.orchestrate(
                summary_id="sum_1", document_id="doc_1"
            )

        assert result["results"] == {}
        assert result["coverage_report"] is None

    @pytest.mark.asyncio
    async def test_orchestrate_specific_agent_names_filters_correctly(self):
        """orchestrate() with specific agent_names filters correctly."""
        from app.core.agents.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        def create_all_side_effect(names=None, **kwargs):
            if names == ["target"]:
                return [self._make_agent_mock("target")]
            if names is None:
                return [
                    self._make_agent_mock("a"),
                    self._make_agent_mock("b"),
                ]
            return []

        with patch(
            "app.core.agents.orchestrator.AgentRegistry.create_all",
            side_effect=create_all_side_effect,
        ):
            with patch.object(orchestrator, "_generate_coverage_report", return_value=None):
                result = await orchestrator.orchestrate(
                    summary_id="sum_1", document_id="doc_1", agent_names=["target"]
                )

        assert "target" in result["results"]
        assert result["results"]["target"].status == "success"

    @pytest.mark.asyncio
    async def test_orchestrate_from_pipeline_always_returns_dict(self):
        """orchestrate_from_pipeline() always returns a dict (never raises)."""
        from app.core.agents.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()
        agent = self._make_agent_mock("agent_a")

        with patch(
            "app.core.agents.orchestrator.AgentRegistry.create_all",
            return_value=[agent],
        ):
            with patch.object(orchestrator, "_generate_coverage_report", return_value=None):
                result = await orchestrator.orchestrate_from_pipeline(
                    summary_id="sum_1", document_id="doc_1"
                )

        assert isinstance(result, dict)
        assert "results" in result
        assert "coverage_report" in result

    @pytest.mark.asyncio
    async def test_orchestrate_from_pipeline_on_internal_error_returns_error_dict(self):
        """orchestrate_from_pipeline() on internal error returns error dict."""
        from app.core.agents.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        with patch(
            "app.core.agents.orchestrator.AgentRegistry.create_all",
            side_effect=RuntimeError("Registry exploded"),
        ):
            result = await orchestrator.orchestrate_from_pipeline(
                summary_id="sum_1", document_id="doc_1"
            )

        assert isinstance(result, dict)
        assert result["results"] == {}
        assert result["coverage_report"] is None
        assert "error" in result
        assert "Registry exploded" in result["error"]

    @pytest.mark.asyncio
    async def test_generate_coverage_report_handles_engine_failure_gracefully(self):
        """_generate_coverage_report() handles coverage engine failure gracefully."""
        from app.core.agents.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        with patch(
            "app.core.memory.coverage.coverage_engine.calculate",
            side_effect=RuntimeError("Coverage engine down"),
        ):
            result = await orchestrator._generate_coverage_report("sum_1")

        assert result is None

    @pytest.mark.asyncio
    async def test_orchestrate_all_agents_skipped_returns_all_skipped(self):
        """orchestrate() when all agents skip returns all skipped statuses."""
        from app.core.agents.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()
        agent_a = self._make_agent_mock("agent_a", should_run=False)
        agent_b = self._make_agent_mock("agent_b", should_run=False)

        with patch(
            "app.core.agents.orchestrator.AgentRegistry.create_all",
            return_value=[agent_a, agent_b],
        ):
            with patch.object(orchestrator, "_generate_coverage_report", return_value=None):
                result = await orchestrator.orchestrate(
                    summary_id="sum_1", document_id="doc_1"
                )

        assert result["results"]["agent_a"].status == "skipped"
        assert result["results"]["agent_b"].status == "skipped"

    @pytest.mark.asyncio
    async def test_orchestrate_passes_config_to_agents(self):
        """orchestrate() passes config and kwargs to should_run() calls."""
        from app.core.agents.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator()
        agent = self._make_agent_mock("agent_a")

        with patch(
            "app.core.agents.orchestrator.AgentRegistry.create_all",
            return_value=[agent],
        ):
            with patch.object(orchestrator, "_generate_coverage_report", return_value=None):
                await orchestrator.orchestrate(
                    summary_id="sum_1",
                    document_id="doc_1",
                    config={"foo": "bar", "baz": 42},
                )

        call_kwargs = agent.should_run.call_args[1]
        assert call_kwargs["foo"] == "bar"
        assert call_kwargs["baz"] == 42


class TestAgentRegistry:
    """Tests for AgentRegistry class methods."""

    def test_create_all_returns_only_registered_agents(self):
        """AgentRegistry.create_all() returns only agents with registered names."""
        from app.core.agents.base import AgentRegistry, BaseAgent, AgentResult

        # Clear the registry for isolation
        original = dict(AgentRegistry._agents)
        AgentRegistry._agents.clear()

        try:

            @AgentRegistry.register("test_a")
            class TestAgentA(BaseAgent):
                name = "test_a"

                async def run(self, summary_id, document_id, **kwargs):
                    return AgentResult(agent="test_a", status="success")

            @AgentRegistry.register("test_b")
            class TestAgentB(BaseAgent):
                name = "test_b"

                async def run(self, summary_id, document_id, **kwargs):
                    return AgentResult(agent="test_b", status="success")

            agents = AgentRegistry.create_all(["test_a"])
            assert len(agents) == 1
            assert agents[0].name == "test_a"

            all_agents = AgentRegistry.create_all()
            assert len(all_agents) == 2

        finally:
            AgentRegistry._agents.clear()
            AgentRegistry._agents.update(original)

    def test_create_all_ignores_unknown_names(self):
        """AgentRegistry.create_all() ignores names not in the registry."""
        from app.core.agents.base import AgentRegistry

        agents = AgentRegistry.create_all(["nonexistent_agent_xyz"])
        assert isinstance(agents, list)
        assert len(agents) == 0

    def test_list_all_returns_names(self):
        """AgentRegistry.list_all() returns an empty list when registry is empty."""
        from app.core.agents.base import AgentRegistry

        names = AgentRegistry.list_all()
        assert isinstance(names, list)


class TestAgentResult:
    """Tests for the AgentResult dataclass."""

    def test_agent_result_defaults(self):
        """AgentResult default fields are None for result and error."""
        result = AgentResult(agent="test", status="success")
        assert result.agent == "test"
        assert result.status == "success"
        assert result.result is None
        assert result.error is None

    def test_agent_result_with_data(self):
        """AgentResult carries result data and error message."""
        result = AgentResult(
            agent="test",
            status="error",
            result={"partial": True},
            error="Something went wrong",
        )
        assert result.agent == "test"
        assert result.status == "error"
        assert result.result == {"partial": True}
        assert result.error == "Something went wrong"
