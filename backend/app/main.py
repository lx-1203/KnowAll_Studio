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
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized")

    # Auto-configure API adapter from environment
    import os
    api_key = os.getenv("ANTHROPIC_AUTH_TOKEN") or os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    api_base = os.getenv("ANTHROPIC_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    if api_key:
        from app.core.api_scheduler import api_client
        provider = "openai"
        model = os.getenv("ANTHROPIC_MODEL") or settings.default_model
        api_client.configure_adapter(provider, api_key, base_url=api_base or "https://api.openai.com/v1", model_name=model)
        logger.info("API adapter configured: model=%s base=%s", model, api_base or "default")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup_init()
    yield


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
    backup_router, game_router,
)
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
app.include_router(admin_router)


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
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
