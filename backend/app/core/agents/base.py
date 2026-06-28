"""Agent framework - base class and registry"""
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator
from dataclasses import dataclass, field


@dataclass
class AgentResult:
    """Result from an agent execution."""
    agent: str
    status: str  # success / error / skipped
    result: dict | None = None
    error: str | None = None


class BaseAgent(ABC):
    """Base class for all sub-agents in the system.

    Each agent is responsible for one type of content generation
    and runs independently (can be parallelized with other agents).
    """

    name: str = "base"
    description: str = "Base agent"

    @abstractmethod
    async def run(self, summary_id: str, document_id: str, **kwargs) -> AgentResult:
        """Execute the agent's task.

        Args:
            summary_id: The knowledge summary ID
            document_id: The document ID
            **kwargs: Additional config options

        Returns:
            AgentResult with status and output
        """
        ...

    def should_run(self, document_id: str, **kwargs) -> bool:
        """Determine if this agent should be activated.

        Override in subclasses for conditional activation
        (e.g., LanguageAgent only activates for language materials).
        """
        return True

    def get_config_schema(self) -> dict:
        """Return JSON Schema for this agent's config options."""
        return {}


class AgentRegistry:
    """Registry of all available agents."""

    _agents: dict[str, type[BaseAgent]] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator to register an agent class."""
        def decorator(agent_cls: type[BaseAgent]):
            cls._agents[name] = agent_cls
            agent_cls.name = name
            return agent_cls
        return decorator

    @classmethod
    def get(cls, name: str) -> type[BaseAgent] | None:
        return cls._agents.get(name)

    @classmethod
    def list_all(cls) -> list[str]:
        return list(cls._agents.keys())

    @classmethod
    def create_all(cls, names: list[str] | None = None, **kwargs) -> list[BaseAgent]:
        """Instantiate agents by name. If names is None, create all."""
        if names is None:
            names = list(cls._agents.keys())
        return [cls._agents[name](**kwargs) for name in names if name in cls._agents]
