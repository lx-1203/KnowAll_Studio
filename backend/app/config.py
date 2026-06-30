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

    # Database — use MySQL (sensitive data must NOT live in local SQLite)
    # Override in .env:  mysql+asyncmy://user:password@host:port/database
    database_url: str = "mysql+asyncmy://knowall:knowall_dev_2026@localhost:3306/knowall?charset=utf8mb4"

    # ChromaDB
    chroma_persist_dir: str = str(BASE_DIR / "data" / "vector_db")
    embedding_model: str = "BAAI/bge-small-zh-v1.5"

    # GraphRAG (hybrid vector + knowledge graph retrieval)
    graphrag_enabled: bool = True
    graphrag_max_hops: int = 2
    graphrag_top_k_vector: int = 8
    graphrag_top_k_graph: int = 20
    graphrag_max_context_chars: int = 8000

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

    # JWT Authentication
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    # OAuth2 Third-party Login (leave empty to disable)
    oauth_qq_client_id: str = ""
    oauth_qq_client_secret: str = ""
    oauth_wechat_client_id: str = ""
    oauth_wechat_client_secret: str = ""
    oauth_github_client_id: str = ""
    oauth_github_client_secret: str = ""
    oauth_google_client_id: str = ""
    oauth_google_client_secret: str = ""

    # Docling document parsing
    use_docling: bool = True
    docling_ocr: bool = False
    docling_ocr_lang: str = "chi_sim+eng"

    # Native outline
    native_outline_enabled: bool = True
    native_outline_max_depth: int = 4

    # Vision analysis (image → text via vision-capable LLM)
    vision_analysis_enabled: bool = False
    vision_model: str = "gpt-4o"
    vision_max_images: int = 8
    vision_min_image_dimension: int = 100


settings = Settings()

# Auto-generate a persistent JWT secret if none is configured
if not settings.jwt_secret:
    _secret_path = BASE_DIR / "data" / ".jwt_secret"
    try:
        if _secret_path.exists():
            settings.jwt_secret = _secret_path.read_text(encoding="utf-8").strip()
        else:
            import secrets
            _secret = secrets.token_urlsafe(64)
            _secret_path.parent.mkdir(parents=True, exist_ok=True)
            _secret_path.write_text(_secret, encoding="utf-8")
            settings.jwt_secret = _secret
    except Exception:
        import secrets
        settings.jwt_secret = secrets.token_urlsafe(64)  # fallback: in-memory only

# Ensure data directories exist
for d in [settings.document_dir, settings.export_dir, settings.chroma_persist_dir]:
    Path(d).mkdir(parents=True, exist_ok=True)
