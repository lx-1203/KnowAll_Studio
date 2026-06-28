"""Agent package initialization - auto-registers all agents"""
from app.core.agents.base import BaseAgent, AgentRegistry, AgentResult
from app.core.agents.orchestrator import orchestrator, AgentOrchestrator

# Agents are registered via @AgentRegistry.register decorator in their respective modules.
# Import them here to trigger registration.
from app.core.agents.question_bank_agent import QuestionBankAgent  # noqa: F401
from app.core.agents.mindmap_agent import MindMapAgent  # noqa: F401
from app.core.agents.study_plan_agent import StudyPlanAgent  # noqa: F401
from app.core.agents.language_agent import LanguageAgent  # noqa: F401

__all__ = [
    "BaseAgent",
    "AgentRegistry",
    "AgentResult",
    "AgentOrchestrator",
    "orchestrator",
]
