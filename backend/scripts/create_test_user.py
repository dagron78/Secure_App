#!/usr/bin/env python3
"""
Script to create a test user for CDSA authentication testing
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.user import User
from app.core.security import get_password_hash
from app.config import settings


async def create_test_user():
    """Create a test user in the database"""
    
    # Create async engine
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # Check if user already exists
            from sqlalchemy import select
            result = await session.execute(
                select(User).where(User.username == "admin")
            )
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                print("Test user 'admin' already exists!")
                print(f"  Username: admin")
                print(f"  Email: {existing_user.email}")
                print(f"  Is Active: {existing_user.is_active}")
                return
            
            # Create new test user
            hashed_password = get_password_hash("admin123")
            
            test_user = User(
                username="admin",
                email="admin@example.com",
                full_name="Admin User",
                hashed_password=hashed_password,
                is_active=True,
                is_superuser=True  # Make superuser for testing (has all permissions)
            )
            
            session.add(test_user)
            await session.commit()
            await session.refresh(test_user)
            
            print("✅ Test user created successfully!")
            print(f"  Username: admin")
            print(f"  Password: admin123")
            print(f"  Email: admin@example.com")
            print(f"  Is Superuser: {test_user.is_superuser}")
            print(f"  User ID: {test_user.id}")
            
        except Exception as e:
            print(f"❌ Error creating test user: {e}")
            await session.rollback()
            raise
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_test_user())