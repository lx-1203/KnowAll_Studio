"""Agent package initialization - auto-registers all agents"""
from app.core.agents.base import BaseAgent, AgentRegistry, AgentResult
from app.core.agents.orchestrator import orchestrator, AgentOrchestrator

# Lazy import agents to avoid circular dependencies
def _register_agents():
    """Import agents once to trigger @AgentRegistry.register decorators."""
    from app.core.agents.question_bank_agent import QuestionBankAgent  # noqa: F401
    from app.core.agents.mindmap_agent import MindMapAgent  # noqa: F401
    from app.core.agents.study_plan_agent import StudyPlanAgent  # noqa: F401
    from app.core.agents.language_agent import LanguageAgent  # noqa: F401
    from app.core.agents.flashcard_agent import FlashcardAgent  # noqa: F401


# Register on first access via AgentRegistry
import atexit
_register_agents()

__all__ = [
    "BaseAgent",
    "AgentRegistry",
    "AgentResult",
    "AgentOrchestrator",
    "orchestrator",
]
