"""KnowAll Studio - Main FastAPI Application"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("knowall")


async def startup_init():
    """Initialize databases on startup."""
    import os
    from pathlib import Path

    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized")

    # Load .env file explicitly for API configuration.
    # The .env file holds the project's intended API settings and should
    # take precedence over host-environment variables (e.g. Claude Code proxy).
    _env_vals = {}
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        for _line in _env_path.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                _env_vals[_k.strip()] = _v.strip().strip('"').strip("'")

    # .env file values take priority over shell env for API config
    api_key = _env_vals.get("ANTHROPIC_AUTH_TOKEN") or os.getenv("ANTHROPIC_AUTH_TOKEN") or os.getenv("OPENAI_API_KEY") or _env_vals.get("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    api_base = _env_vals.get("ANTHROPIC_BASE_URL") or os.getenv("ANTHROPIC_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    model = _env_vals.get("ANTHROPIC_MODEL") or os.getenv("ANTHROPIC_MODEL") or settings.default_model

    if api_key:
        from app.core.api_scheduler import api_client

        # Detect provider from the base URL / env vars
        if _env_vals.get("DEEPSEEK_API_KEY") or (os.getenv("DEEPSEEK_API_KEY") and not _env_vals.get("ANTHROPIC_AUTH_TOKEN")):
            provider = "deepseek"
            model = "deepseek-chat"
            api_base = api_base or "https://api.deepseek.com/v1"
        elif api_base and "deepseek" in api_base.lower():
            # DeepSeek's Anthropic-compatible endpoint uses the Anthropic adapter
            provider = "anthropic"
            api_base = api_base.rstrip("/")  # e.g. https://api.deepseek.com/anthropic
        elif os.getenv("ANTHROPIC_AUTH_TOKEN") and not _env_vals.get("ANTHROPIC_AUTH_TOKEN"):
            provider = "anthropic"
            api_base = api_base or "https://api.anthropic.com/v1"
        else:
            provider = "openai"
            api_base = api_base or "https://api.openai.com/v1"

        api_client.configure_adapter(provider, api_key, base_url=api_base, model_name=model)
        logger.info("API adapter configured: provider=%s model=%s base=%s", provider, model, api_base)

    # Pre-warm the GraphRAG knowledge graph index
    if settings.graphrag_enabled:
        try:
            from app.core.graph_rag import rebuild_graph
            node_count = await rebuild_graph()
            logger.info("GraphRAG index built: %d nodes", node_count)
        except Exception as e:
            logger.warning("GraphRAG index build skipped (will lazy-load): %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup_init()
    from app.websocket import start_background_tasks, stop_background_tasks
    start_background_tasks()
    yield
    await stop_background_tasks()


app = FastAPI(
    title="KnowAll Studio API",
    description="智识工坊 - 一站式AI知识内化学习工作台",
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS - allow all origins in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and register API routes
from app.api.documents import router as doc_router
from app.api.knowledge import router as knowledge_router
from app.api.questions import router as quiz_router
from app.api import (
    flashcards_router, chat_router, admin_router,
    search_router, pipeline_router, stats_router,
    backup_router, game_router, study_router, share_router,
    auth_router, kp_router, user_router, notifications_router,
    reading_router,
)
from app.api.agents import router as agents_router
from app.api.language import router as language_router
from app.api.memory_feedback import router as memory_router
from app.api.coverage import router as coverage_router
from app.api.interactive_quiz import router as interactive_quiz_router
from app.api.answer_review import router as answer_review_router
from app.api.sync_upload import router as sync_upload_router
from app.api.version_control import router as version_control_router
from app.api.game_quiz import router as game_quiz_router
from app.api.commercial import router as commercial_router
from app.websocket import sync_router
from app.middleware import setup_middleware

# Register middleware (order matters: last added = first executed)
setup_middleware(app)

app.include_router(doc_router)
app.include_router(knowledge_router)
app.include_router(quiz_router)
app.include_router(flashcards_router)
app.include_router(chat_router)
app.include_router(search_router)
app.include_router(pipeline_router)
app.include_router(stats_router)
app.include_router(backup_router)
app.include_router(game_router)
app.include_router(study_router)
app.include_router(share_router)
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(kp_router)
app.include_router(user_router)
app.include_router(notifications_router)
app.include_router(reading_router)
app.include_router(agents_router)
app.include_router(language_router)
app.include_router(memory_router)
app.include_router(coverage_router)
app.include_router(interactive_quiz_router)
app.include_router(answer_review_router)
app.include_router(sync_router)
app.include_router(sync_upload_router)
app.include_router(version_control_router)
app.include_router(game_quiz_router)
app.include_router(commercial_router)


@app.get("/")
async def root():
    return {
        "name": "KnowAll Studio",
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=settings.debug)
