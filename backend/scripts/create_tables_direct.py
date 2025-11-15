#!/usr/bin/env python3
"""
Create database tables directly using SQLAlchemy.
Bypasses Alembic to avoid import issues during migration.
"""
import os
import sys
import asyncio
from pathlib import Path

# Add the project root directory to the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Set minimal environment to avoid service initialization
os.environ['SKIP_SERVICE_INIT'] = '1'

from app.db.base import Base, init_db
from app.config import settings

# Import all models to register them with Base.metadata
from app.models import (
    User, Role, Permission, Session,
    ChatSession, ChatMessage, ContextWindow,
    Tool, ToolExecution, ToolApproval, ToolCache,
    AuditLog, SystemMetric,
    Secret, SecretVersion, SecretAccessLog,
    Document, DocumentChunk, SearchResult, EmbeddingModel,
    Notification, NotificationPreference
)

async def create_tables():
    """Create all database tables."""
    print("=" * 60)
    print("CDSA Database Table Creation")
    print("=" * 60)
    print(f"\nDatabase URL: {settings.DATABASE_URL}")
    print(f"Environment: {settings.ENVIRONMENT}")
    print("\nImporting models...")
    
    # Get all registered models
    tables = Base.metadata.tables
    print(f"✓ Found {len(tables)} models to create")
    
    print("\nCreating tables...")
    
    try:
        # Initialize database connection
        engine, session_factory = init_db()
        
        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        print("\n✓ All tables created successfully!")
        
        # Verify tables were created
        async with engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public' 
                ORDER BY tablename
            """))
            created_tables = [row[0] for row in result]
            
        print(f"\n✓ Verified {len(created_tables)} tables in database:")
        for table in sorted(created_tables):
            print(f"  - {table}")
        
        await engine.dispose()
        
        print("\n" + "=" * 60)
        print("Database initialization complete!")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print(f"\n✗ Error creating tables: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    from sqlalchemy import text
    sys.exit(asyncio.run(create_tables()))