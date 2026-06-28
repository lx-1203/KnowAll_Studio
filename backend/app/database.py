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
    """Run Alembic migrations to bring DB up to date."""
    import subprocess
    import sys
    from pathlib import Path

    alembic_cfg_path = Path(__file__).resolve().parent.parent / "alembic.ini"

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
            stderr = result.stderr.strip()
            if stderr:
                logger.warning("Alembic stderr: %s", stderr[:500])
        logger.info("Alembic migrations complete. stdout: %s", result.stdout.strip()[:200] or "(no output)")

    # Always create any tables not yet covered by migrations (idempotent)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
