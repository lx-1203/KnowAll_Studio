"""KnowAll Studio - Backend Configuration"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "KnowAll Studio"
    app_version: str = "0.1.0"
    debug: bool = True

    # Database (single SQLite for MVP)
    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR}/data/app.db"

    # ChromaDB
    chroma_persist_dir: str = str(BASE_DIR / "data" / "vector_db")
    embedding_model: str = "BAAI/bge-small-zh-v1.5"

    # API Scheduler
    default_model: str = "claude-opus-4-6"
    default_temperature: float = 0.7
    default_max_tokens: int = 4096
    cache_ttl_days: int = 30
    max_retries: int = 3
    request_timeout: int = 120
    max_concurrent_requests: int = 5
    daily_token_limit: int = 10_000_000

    # File Storage
    document_dir: str = str(BASE_DIR / "data" / "documents")
    export_dir: str = str(BASE_DIR / "data" / "exports")
    max_upload_size_mb: int = 100
    chunk_size_tokens: int = 2000  # target tokens per chunk
    chunk_overlap_ratio: float = 0.1

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000", "app://."]


settings = Settings()

# Ensure data directories exist
for d in [settings.document_dir, settings.export_dir, settings.chroma_persist_dir]:
    Path(d).mkdir(parents=True, exist_ok=True)
