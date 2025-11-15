#!/usr/bin/env python3
"""
Script to update the test user's email to a valid format
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.models.user import User
from app.config import settings


async def update_user_email():
    """Update test user's email to a valid format"""
    
    # Create async engine
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # Find the admin user
            result = await session.execute(
                select(User).where(User.username == "admin")
            )
            user = result.scalar_one_or_none()
            
            if not user:
                print("❌ User 'admin' not found!")
                return
            
            print(f"Found user: {user.username}")
            print(f"Current email: {user.email}")
            
            # Update email
            user.email = "admin@example.com"
            await session.commit()
            
            print("✅ User email updated successfully!")
            print(f"  Username: {user.username}")
            print(f"  New Email: {user.email}")
            
        except Exception as e:
            print(f"❌ Error updating user: {e}")
            await session.rollback()
            raise
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(update_user_email())