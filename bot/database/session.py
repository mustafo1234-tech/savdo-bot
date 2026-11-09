from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from bot.config import get_config
from bot.database.base import Base

logger = logging.getLogger(__name__)

SCHEMA_PATCHES: tuple[tuple[str, str, str], ...] = (
    ("users", "profile_consent", "ALTER TABLE users ADD COLUMN profile_consent VARCHAR(16)"),
)


def create_engine_and_session() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    config = get_config()
    engine = create_async_engine(
        config.async_database_url,
        echo=False,
        pool_pre_ping=True,
        future=True,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return engine, session_factory


async def create_tables(engine: AsyncEngine) -> None:
    from bot.database import models  # noqa: F401  (metadata uchun)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def ensure_schema_compatibility(engine: AsyncEngine) -> None:
    """Eski bazaga `create_all` qo'sha olmaydigan yangi ustunlarni qo'shadi."""

    async with engine.begin() as conn:

        def _missing_ddl(sync_conn) -> list[str]:
            inspector = inspect(sync_conn)
            tables = set(inspector.get_table_names())
            existing_columns: dict[str, set[str]] = {}
            missing: list[str] = []
            for table, column, ddl in SCHEMA_PATCHES:
                if table not in tables:
                    continue
                if table not in existing_columns:
                    existing_columns[table] = {
                        col["name"] for col in inspector.get_columns(table)
                    }
                if column not in existing_columns[table]:
                    missing.append(ddl)
            return missing

        statements = await conn.run_sync(_missing_ddl)
        for statement in statements:
            logger.warning("Eski bazaga yetishmayotgan ustun qo'shilmoqda: %s", statement)
            await conn.execute(text(statement))
