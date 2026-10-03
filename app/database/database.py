from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

async_session_factory: async_sessionmaker[AsyncSession] = (
    async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Создаёт SQLAlchemy-сессию на время операции."""

    async with async_session_factory() as session:
        yield session


async def close_database() -> None:
    """Закрывает пул соединений с БД."""

    await engine.dispose()
