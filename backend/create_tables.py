#!/usr/bin/env python3
"""Direct table creation script - bypasses alembic model imports."""
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, text
from app.config import settings

# Use sync psycopg2 driver
database_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

print(f"Connecting to database: {database_url}")

engine = create_engine(database_url, echo=True)

# Read and execute the migration SQL
migration_file = Path(__file__).parent / "alembic" / "versions" / "001_initial_schema.py"

print(f"\nReading migration from: {migration_file}")

# Import the migration module
import importlib.util
spec = importlib.util.spec_from_file_location("migration", migration_file)
migration = importlib.util.module_from_spec(spec)

# Execute upgrade function
print("\nExecuting database migrations...")

try:
    # Import necessary alembic components
    from alembic import op
    from alembic.runtime.migration import MigrationContext
    from alembic.operations import Operations
    
    with engine.begin() as connection:
        ctx = MigrationContext.configure(connection)
        op_obj = Operations(ctx)
        
        # Load the migration module properly
        spec.loader.exec_module(migration)
        
        # Execute the upgrade
        migration.upgrade()
        
    print("\n✓ Database tables created successfully!")
    
    # Verify tables
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            ORDER BY tablename
        """))
        tables = [row[0] for row in result]
        print(f"\n✓ Created {len(tables)} tables:")
        for table in tables:
            print(f"  - {table}")
            
except Exception as e:
    print(f"\n✗ Error creating tables: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)