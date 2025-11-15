"""Test login endpoint with detailed error handling."""
import asyncio
import sys
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

# Add parent directory to path
sys.path.insert(0, '/Users/charleshoward/Applications/Secure App/backend')

from app.db.base import init_db
from app.models.user import User
from app.core.security import verify_password, create_access_token, create_refresh_token

async def test_login():
    """Test the login process step by step."""
    print("=" * 60)
    print("Testing Login Process")
    print("=" * 60)
    
    # Initialize database
    print("\nInitializing database connection...")
    engine, AsyncSessionLocal = init_db()
    print("✓ Database initialized")
    
    username = "admin"
    password = "admin123"
    
    async with AsyncSessionLocal() as db:
        try:
            print(f"\n1. Looking up user: {username}")
            result = await db.execute(
                select(User)
                .options(selectinload(User.roles))
                .where(
                    or_(User.username == username, User.email == username)
                )
            )
            user = result.scalar_one_or_none()
            
            if not user:
                print(f"❌ User not found: {username}")
                return
            
            print(f"✓ User found: {user.email}")
            print(f"  - ID: {user.id}")
            print(f"  - Username: {user.username}")
            print(f"  - Is Active: {user.is_active}")
            print(f"  - Is Superuser: {user.is_superuser}")
            
            print(f"\n2. Verifying password...")
            password_valid = verify_password(password, user.hashed_password)
            if not password_valid:
                print("❌ Invalid password")
                return
            print("✓ Password verified")
            
            print(f"\n3. Checking if user is active...")
            if not user.is_active:
                print("❌ User is not active")
                return
            print("✓ User is active")
            
            print(f"\n4. Getting user ID...")
            user_id = user.id
            print(f"✓ User ID: {user_id}")
            
            print(f"\n5. Creating access token...")
            access_token = create_access_token(subject=user_id)
            print(f"✓ Access token created: {access_token[:50]}...")
            
            print(f"\n6. Creating refresh token...")
            refresh_token = create_refresh_token(subject=user_id)
            print(f"✓ Refresh token created: {refresh_token[:50]}...")
            
            print("\n" + "=" * 60)
            print("✅ LOGIN TEST SUCCESSFUL!")
            print("=" * 60)
            print(f"\nAccess Token: {access_token}")
            print(f"\nRefresh Token: {refresh_token}")
            
        except Exception as e:
            print(f"\n❌ ERROR: {str(e)}")
            import traceback
            print("\nFull traceback:")
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_login())