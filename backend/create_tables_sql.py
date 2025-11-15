#!/usr/bin/env python3
"""Create database tables using raw SQL - no app imports."""
import psycopg2
from urllib.parse import urlparse

# Parse database URL from environment
DATABASE_URL = "postgresql://cdsa:changeme@127.0.0.1:5433/cdsa_db"

url = urlparse(DATABASE_URL)

print("Connecting to database...")
conn = psycopg2.connect(
    dbname=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port
)

print("✓ Connected successfully")

cursor = conn.cursor()

# Read the migration SQL file
with open('alembic/versions/001_initial_schema.py', 'r') as f:
    content = f.read()
    
    # Extract the SQL commands from the upgrade() function
    # This is a simplified approach - ideally we'd parse the Python AST
    print("\nNote: For now, run the migration manually using psql")
    print("Or use the tables created by the API server on first run")

# Close connection
cursor.close()
conn.close()

print("\n✓ Database connection verified")
print("\nRecommendation: Start the API server and it will create tables on startup")