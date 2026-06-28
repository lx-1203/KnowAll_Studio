"""Comprehensive tests for BaseAgent and AgentRegistry.

Tests the agent base class, registry decorator pattern,
AgentResult dataclass, and custom agent subclass behavior.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.core.agents.base import BaseAgent, AgentRegistry, AgentResult


# ---------------------------------------------------------------------------
# Fixtures for agent registry isolation
# ---------------------------------------------------------------------------

@pytest.fixture
def isolated_registry():
    """Save and restore the AgentRegistry state for test isolation."""
    saved = dict(AgentRegistry._agents)
    AgentRegistry._agents = {}
    yield
    AgentRegistry._agents = saved


# ---------------------------------------------------------------------------
# Dummy agent subclasses for testing
# ---------------------------------------------------------------------------

class _DummyAgent(BaseAgent):
    """A minimal concrete agent for testing."""
    name = "dummy"
    description = "A dummy agent for testing"

    async def run(self, summary_id: str, document_id: str, **kwargs) -> AgentResult:
        return AgentResult(agent=self.name, status="success")


class _ConditionalAgent(BaseAgent):
    """An agent that overrides should_run() with custom logic."""
    name = "conditional"
    description = "A conditional agent"

    def should_run(self, document_id: str, **kwargs) -> bool:
        # Only run for documents with "lang" in the ID
        return "lang" in document_id

    async def run(self, summary_id: str, document_id: str, **kwargs) -> AgentResult:
        return AgentResult(agent=self.name, status="success")


class _AgentWithConfig(BaseAgent):
    """An agent that provides a config schema."""
    name = "with_config"
    description = "An agent with JSON schema config"

    def get_config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "depth": {"type": "integer", "default": 3},
            },
        }

    async def run(self, summary_id: str, document_id: str, **kwargs) -> AgentResult:
        return AgentResult(agent=self.name, status="success")


# ---------------------------------------------------------------------------
# AgentRegistry tests
# ---------------------------------------------------------------------------

class TestAgentRegistry:
    """Tests for AgentRegistry registration and lookup."""

    def test_register_decorator_stores_class(self, isolated_registry):
        """AgentRegistry.register decorator stores class under correct name."""
        @AgentRegistry.register("test_agent_1")
        class MyAgent(BaseAgent):
            async def run(self, summary_id: str, document_id: str, **kwargs) -> AgentResult:
                return AgentResult(agent=self.name, status="success")

        assert "test_agent_1" in AgentRegistry._agents
        assert AgentRegistry._agents["test_agent_1"] is MyAgent
        assert MyAgent.name == "test_agent_1"

    def test_register_sets_name_on_class(self, isolated_registry):
        """AgentRegistry.register sets the name attribute on the class."""
        @AgentRegistry.register("explicit_name")
        class SomeAgent(BaseAgent):
            async def run(self, summary_id: str, document_id: str, **kwargs) -> AgentResult:
                return AgentResult(agent=self.name, status="success")

        assert SomeAgent.name == "explicit_name"

    def test_get_returns_none_for_unknown_name(self, isolated_registry):
        """AgentRegistry.get() returns None for unknown agent name."""
        result = AgentRegistry.get("nonexistent_agent_xyz")
        assert result is None

    def test_get_returns_class_for_registered_name(self, isolated_registry):
        """AgentRegistry.get() returns the class for a registered name."""
        @AgentRegistry.register("known_agent")
        class KnownAgent(BaseAgent):
            async def run(self, summary_id: str, document_id: str, **kwargs) -> AgentResult:
                return AgentResult(agent=self.name, status="success")

        cls = AgentRegistry.get("known_agent")
        assert cls is KnownAgent

    def test_list_all_returns_all_names(self, isolated_registry):
        """AgentRegistry.list_all() returns all registered names."""
        @AgentRegistry.register("agent_a")
        class AgentA(BaseAgent):
            async def run(self, summary_id: str, document_id: str, **kwargs) -> AgentResult:
                return AgentResult(agent=self.name, status="success")

        @AgentRegistry.register("agent_b")
        class AgentB(BaseAgent):
            async def run(self, summary_id: str, document_id: str, **kwargs) -> AgentResult:
                return AgentResult(agent=self.name, status="success")

        names = AgentRegistry.list_all()
        assert "agent_a" in names
        assert "agent_b" in names

    def test_create_all_none_creates_all_registered(self, isolated_registry):
        """AgentRegistry.create_all() with None creates all registered agents."""
        @AgentRegistry.register("agent_one")
        class AgentOne(BaseAgent):
            async def run(self, summary_id: str, document_id: str, **kwargs) -> AgentResult:
                return AgentResult(agent=self.name, status="success")

        @AgentRegistry.register("agent_two")
        class AgentTwo(BaseAgent):
            async def run(self, summary_id: str, document_id: str, **kwargs) -> AgentResult:
                return AgentResult(agent=self.name, status="success")

        agents = AgentRegistry.create_all()
        assert len(agents) == 2
        names = {a.name for a in agents}
        assert names == {"agent_one", "agent_two"}

    def test_create_all_with_specific_names_filters(self, isolated_registry):
        """AgentRegistry.create_all() with specific names creates only those agents."""
        @AgentRegistry.register("agent_x")
        class AgentX(BaseAgent):
            async def run(self, summary_id: str, document_id: str, **kwargs) -> AgentResult:
                return AgentResult(agent=self.name, status="success")

        @AgentRegistry.register("agent_y")
        class AgentY(BaseAgent):
            async def run(self, summary_id: str, document_id: str, **kwargs) -> AgentResult:
                return AgentResult(agent=self.name, status="success")

        agents = AgentRegistry.create_all(["agent_x"])
        assert len(agents) == 1
        assert agents[0].name == "agent_x"

    def test_create_all_skips_unknown_names_silently(self, isolated_registry):
        """AgentRegistry.create_all() skips unknown names without error."""
        @AgentRegistry.register("real_agent")
        class RealAgent(BaseAgent):
            async def run(self, summary_id: str, document_id: str, **kwargs) -> AgentResult:
                return AgentResult(agent=self.name, status="success")

        # Should not raise, just skip the unknown name
        agents = AgentRegistry.create_all(["real_agent", "fake_agent", "another_fake"])
        assert len(agents) == 1
        assert agents[0].name == "real_agent"

    def test_create_all_empty_list_returns_empty(self, isolated_registry):
        """AgentRegistry.create_all() with empty list returns empty list."""
        @AgentRegistry.register("some_agent")
        class SomeAgent(BaseAgent):
            async def run(self, summary_id: str, document_id: str, **kwargs) -> AgentResult:
                return AgentResult(agent=self.name, status="success")

        agents = AgentRegistry.create_all([])
        assert agents == []


# ---------------------------------------------------------------------------
# BaseAgent tests
# ---------------------------------------------------------------------------

class TestBaseAgent:
    """Tests for BaseAgent default behavior."""

    def test_should_run_returns_true_by_default(self):
        """BaseAgent.should_run() returns True by default."""
        agent = _DummyAgent()
        assert agent.should_run("any_doc_id") is True
        assert agent.should_run("") is True
        assert agent.should_run("doc123", extra="param") is True

    def test_get_config_schema_returns_empty_dict_by_default(self):
        """BaseAgent.get_config_schema() returns empty dict by default."""
        agent = _DummyAgent()
        assert agent.get_config_schema() == {}

    def test_custom_agent_can_override_should_run(self):
        """Custom agent subclass can override should_run() with conditional logic."""
        agent = _ConditionalAgent()
        assert agent.should_run("doc_lang_en") is True
        assert agent.should_run("normal_doc") is False
        assert agent.should_run("") is False

    def test_custom_agent_can_provide_config_schema(self):
        """Custom agent can provide a config schema via get_config_schema()."""
        agent = _AgentWithConfig()
        schema = agent.get_config_schema()
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "depth" in schema["properties"]

    def test_base_agent_is_abstract_cannot_instantiate(self):
        """BaseAgent cannot be instantiated directly (abstract)."""
        with pytest.raises(TypeError):
            BaseAgent()  # Missing abstract method 'run'

    def test_concrete_subclass_can_be_instantiated(self):
        """Concrete subclass with run() implemented can be instantiated."""
        agent = _DummyAgent()
        assert isinstance(agent, BaseAgent)
        assert agent.name == "dummy"


# ---------------------------------------------------------------------------
# AgentResult tests
# ---------------------------------------------------------------------------

class TestAgentResult:
    """Tests for AgentResult dataclass."""

    def test_default_values_are_correct(self):
        """AgentResult dataclass has correct default values (result=None, error=None)."""
        result = AgentResult(agent="test", status="success")
        assert result.agent == "test"
        assert result.status == "success"
        assert result.result is None
        assert result.error is None

    def test_can_set_all_fields(self):
        """AgentResult can hold all fields including result and error."""
        result = AgentResult(
            agent="test_agent",
            status="error",
            result={"key": "value"},
            error="Something went wrong",
        )
        assert result.agent == "test_agent"
        assert result.status == "error"
        assert result.result == {"key": "value"}
        assert result.error == "Something went wrong"

    def test_status_can_be_skipped(self):
        """AgentResult status can be set to 'skipped'."""
        result = AgentResult(agent="test", status="skipped")
        assert result.status == "skipped"
        assert result.result is None
        assert result.error is None


# ---------------------------------------------------------------------------
# Async run integration test
# ---------------------------------------------------------------------------

class TestAgentRunAsync:
    """Tests for agent async run behavior."""

    @pytest.mark.asyncio
    async def test_dummy_agent_run_returns_success(self):
        """Concrete agent run() returns a success AgentResult."""
        agent = _DummyAgent()
        result = await agent.run("summary_1", "doc_1")
        assert isinstance(result, AgentResult)
        assert result.status == "success"
        assert result.agent == "dummy"

    @pytest.mark.asyncio
    async def test_conditional_agent_run(self):
        """Conditional agent run() works correctly."""
        agent = _ConditionalAgent()
        result = await agent.run("summary_1", "doc_lang_en")
        assert result.status == "success"
        assert result.agent == "conditional"

    @pytest.mark.asyncio
    async def test_agent_run_receives_kwargs(self):
        """Agent run() can receive and use extra keyword arguments."""
        # Create a simple agent that captures kwargs
        captured_kwargs = {}

        @AgentRegistry.register("kwargs_agent")
        class KwargsAgent(BaseAgent):
            async def run(self, summary_id: str, document_id: str, **kwargs) -> AgentResult:
                captured_kwargs["received"] = kwargs
                return AgentResult(
                    agent=self.name,
                    status="success",
                    result={"kwargs_keys": list(kwargs.keys())},
                )

        agent = KwargsAgent()
        result = await agent.run(
            "summary_1", "doc_1", config={"depth": 3}, extra_flag=True
        )
        assert result.status == "success"
        assert "config" in result.result["kwargs_keys"]
        assert "extra_flag" in result.result["kwargs_keys"]

        # Clean up registry
        AgentRegistry._agents.pop("kwargs_agent", None)
