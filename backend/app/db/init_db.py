"""Database schema initialization helper."""

from app.db.base import Base
from app.db.session import engine


async def init_db() -> None:
    """Creates all database tables defined in metadata."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db() -> None:
    """Drops all database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
