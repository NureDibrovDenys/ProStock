from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL.get_secret_value()
        if hasattr(settings.DATABASE_URL, "get_secret_value")
        else settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    
    # Pool parameters for production
    
    # Checks for an active session before use (prevents DB connection drops)
    pool_pre_ping=True,
    # Number of persistent connections in the pool
    pool_size=10,
    # Additional connections that may be created beyond 'pool_size' during peak loads
    max_overflow=20,
)

async_session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)

class Base(DeclarativeBase):
    pass

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    A dependency for FastAPI that provides a DB session
    with automatic rollback in the event of errors.
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
