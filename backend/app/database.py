"""SQLAlchemy database setup with async support + Alembic migrations.

Supports SQLite (local dev) and MySQL (production).
*Never* commit local SQLite data — .gitignore covers backend/data/.
Set DATABASE_URL in your .env to switch drivers.
"""
import logging
from urllib.parse import urlparse

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

logger = logging.getLogger("knowall.db")

_db_scheme = urlparse(settings.database_url).scheme
_is_sqlite = "sqlite" in _db_scheme

connect_args: dict = {}
if _is_sqlite:
    connect_args["timeout"] = 30
else:
    # MySQL / other client-server DBs
    connect_args["connect_timeout"] = 30

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args=connect_args,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    pool_pre_ping=True,
)

if _is_sqlite:

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        dbapi_connection.execute("PRAGMA journal_mode=WAL;")
        dbapi_connection.execute("PRAGMA busy_timeout=5000;")

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Run Alembic migrations to bring DB up to date.

    If migrations fail (e.g., broken chain from empty initial migration),
    falls back to dropping all tables and recreating from models.
    This is safe for development but DESTROYS DATA on schema mismatch.
    """
    import subprocess
    import sys
    from pathlib import Path

    alembic_cfg_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    migration_failed = False

    if alembic_cfg_path.exists():
        logger.info("Running Alembic migrations...")
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", str(alembic_cfg_path), "upgrade", "head"],
            cwd=str(alembic_cfg_path.parent),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            migration_failed = True
            stderr = result.stderr.strip()
            if stderr:
                logger.warning("Alembic migration failed (will recreate tables): %s", stderr[:500])
        else:
            logger.info("Alembic migrations complete. stdout: %s", result.stdout.strip()[:200] or "(no output)")

    if migration_failed:
        # In debug mode, drop and recreate from models (development only)
        if not settings.debug:
            logger.error("Alembic migration failed in production mode. Refusing to drop tables.")
            raise RuntimeError(
                "数据库迁移失败，无法在非调试模式下自动重建。请手动运行 alembic upgrade head 排查问题。"
            )
        logger.warning("Dropping all tables and recreating from models (debug mode)...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        # Stamp alembic head so future migrations work
        subprocess.run(
            [sys.executable, "-m", "alembic", "-c", str(alembic_cfg_path), "stamp", "head"],
            cwd=str(alembic_cfg_path.parent),
            capture_output=True,
            text=True,
            timeout=30,
        )
        logger.info("Database recreated from models and alembic head stamped.")
    else:
        # Ensure any tables not covered by migrations exist (idempotent)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
