"""Database base configuration and session management."""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings

# Create base class for models
Base = declarative_base()

# Async database engine (will be initialized in main.py lifespan)
async_engine = None
AsyncSessionLocal = None

# Sync database engine for Celery tasks (initialized separately)
sync_engine = None
SyncSessionLocal = None


def init_db():
    """Initialize async database engine and session factory for FastAPI."""
    global async_engine, AsyncSessionLocal
    
    # Convert sync DATABASE_URL to async (postgresql:// -> postgresql+asyncpg://)
    async_url = settings.DATABASE_URL.replace(
        "postgresql://", "postgresql+asyncpg://"
    ).replace(
        "postgres://", "postgresql+asyncpg://"
    )
    
    # Create async engine
    # Create async engine
    engine_args = {
        "echo": settings.is_development,
        "pool_pre_ping": True,
    }
    
    # SQLite doesn't support pool_size/max_overflow with NullPool (default for aiosqlite)
    if "sqlite" not in async_url:
        engine_args["pool_size"] = 20
        engine_args["max_overflow"] = 10
        
    async_engine = create_async_engine(
        async_url,
        **engine_args
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


def init_sync_db():
    """Initialize synchronous database engine and session factory for Celery tasks."""
    global sync_engine, SyncSessionLocal
    
    # Ensure DATABASE_URL uses correct sync driver (psycopg2)
    sync_url = settings.DATABASE_URL.replace(
        "postgresql+asyncpg://", "postgresql://"
    ).replace(
        "postgres+asyncpg://", "postgresql://"
    )
    
    # Create sync engine
    engine_args = {
        "echo": settings.is_development,
        "pool_pre_ping": True,
    }
    
    if "sqlite" not in sync_url:
        engine_args["pool_size"] = 10
        engine_args["max_overflow"] = 5
        
    sync_engine = create_engine(
        sync_url,
        **engine_args
    )
    
    # Create sync session factory
    SyncSessionLocal = sessionmaker(
        bind=sync_engine,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    return sync_engine, SyncSessionLocal


def get_session_factory():
    """
    Get synchronous session factory for Celery tasks.
    
    This function initializes the sync database connection if not already done
    and returns the session factory that Celery tasks can use.
    
    Returns:
        sessionmaker: Synchronous session factory
    """
    global SyncSessionLocal
    
    if SyncSessionLocal is None:
        init_sync_db()
    
    return SyncSessionLocal


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


def close_sync_db():
    """Close sync database connections."""
    global sync_engine
    if sync_engine:
        sync_engine.dispose()