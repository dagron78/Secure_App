"""Database base configuration and session management."""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from app.config import settings

# Create base class for models
Base = declarative_base()

# Async database engine (will be initialized in main.py lifespan)
async_engine = None
AsyncSessionLocal = None


def init_db():
    """Initialize database engine and session factory."""
    global async_engine, AsyncSessionLocal
    
    # Convert sync DATABASE_URL to async (postgresql:// -> postgresql+asyncpg://)
    async_url = settings.DATABASE_URL.replace(
        "postgresql://", "postgresql+asyncpg://"
    ).replace(
        "postgres://", "postgresql+asyncpg://"
    )
    
    # Create async engine
    async_engine = create_async_engine(
        async_url,
        echo=settings.is_development,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=10,
    )
    
    # Create async session factory
    AsyncSessionLocal = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    return async_engine, AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session dependency."""
    if AsyncSessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def close_db():
    """Close database connections."""
    global async_engine
    if async_engine:
        await async_engine.dispose()