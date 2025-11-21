"""
Pytest configuration and fixtures for the CDSA test suite.

Provides:
- Database fixtures (test database, session)
- API client fixtures
- Authentication fixtures
- Mock data fixtures
"""
import pytest
import asyncio
from typing import Generator, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from httpx import AsyncClient
import os

# Mock environment variables BEFORE importing app modules
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["SECRET_KEY"] = "mock-secret-key"
os.environ["JWT_SECRET_KEY"] = "mock-jwt-secret-key"
os.environ["ENCRYPTION_KEY"] = "mock-encryption-key"

from app.main import app
from app.db.base import Base, get_db
from app.config import settings
from app.models.user import User, Role, Permission
from app.core.security import get_password_hash


# Test database URL (use in-memory SQLite for fast tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        echo=False
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture(scope="function")
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session


@pytest.fixture(scope="function")
async def client(test_session) -> AsyncGenerator[AsyncClient, None]:
    """Create a test API client."""
    async def override_get_db():
        yield test_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(test_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        hashed_password=get_password_hash("testpass123"),
        is_active=True,
        is_verified=True
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest.fixture
async def test_admin_user(test_session: AsyncSession) -> User:
    """Create a test admin user."""
    user = User(
        email="admin@example.com",
        username="admin",
        full_name="Admin User",
        hashed_password=get_password_hash("adminpass123"),
        is_active=True,
        is_verified=True,
        is_superuser=True
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest.fixture
async def test_role(test_session: AsyncSession) -> Role:
    """Create a test role."""
    role = Role(
        name="analyst",
        description="Data Analyst Role"
    )
    test_session.add(role)
    await test_session.commit()
    await test_session.refresh(role)
    return role


@pytest.fixture
async def test_permission(test_session: AsyncSession) -> Permission:
    """Create a test permission."""
    permission = Permission(
        name="read_documents",
        description="Read Documents",
        resource="documents",
        action="read"
    )
    test_session.add(permission)
    await test_session.commit()
    await test_session.refresh(permission)
    return permission


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Create authentication headers for test user."""
    from app.core.security import create_access_token
    
    token = create_access_token(data={"sub": test_user.email})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(test_admin_user: User) -> dict:
    """Create authentication headers for admin user."""
    from app.core.security import create_access_token
    
    token = create_access_token(data={"sub": test_admin_user.email})
    return {"Authorization": f"Bearer {token}"}