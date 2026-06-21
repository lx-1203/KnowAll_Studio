"""SQLAlchemy database setup with async support + Alembic migrations"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

logger = logging.getLogger("knowall.db")

# Single SQLite database for MVP (simplifies deployment)
engine = create_async_engine(settings.database_url, echo=settings.debug)
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
    from pathlib import Path

    alembic_cfg_path = Path(__file__).resolve().parent.parent / "alembic.ini"

    if alembic_cfg_path.exists():
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config(str(alembic_cfg_path))
        alembic_cfg.set_main_option("script_location", str(alembic_cfg_path.parent / "alembic"))

        logger.info("Running Alembic migrations...")
        async with engine.begin() as conn:
            await conn.run_sync(command.upgrade, alembic_cfg, "head")
        logger.info("Alembic migrations complete.")
    else:
        logger.warning("alembic.ini not found, using create_all (no migration support)")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
