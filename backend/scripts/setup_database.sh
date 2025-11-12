#!/bin/bash

# CDSA Database Setup Script
# This script initializes the database, runs migrations, and seeds initial data

set -e  # Exit on error

echo "=========================================="
echo "CDSA Database Setup"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    echo "Please create a .env file with your database configuration"
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

echo "📋 Configuration:"
echo "  Database: $DATABASE_URL"
echo ""

# Step 1: Check database connection
echo "1️⃣  Checking database connection..."
if python -c "
import psycopg2
from urllib.parse import urlparse
url = urlparse('$DATABASE_URL')
try:
    conn = psycopg2.connect(
        dbname=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )
    conn.close()
    print('✓ Database connection successful')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    exit(1)
" 2>/dev/null; then
    echo -e "${GREEN}✓ Database connection verified${NC}"
else
    echo -e "${RED}❌ Database connection failed${NC}"
    echo "Please check your DATABASE_URL in .env file"
    exit 1
fi

echo ""

# Step 2: Run Alembic migrations
echo "2️⃣  Running database migrations..."
if alembic upgrade head; then
    echo -e "${GREEN}✓ Migrations completed successfully${NC}"
else
    echo -e "${RED}❌ Migration failed${NC}"
    exit 1
fi

echo ""

# Step 3: Seed initial data
echo "3️⃣  Seeding initial data..."
if python scripts/seed_data.py; then
    echo -e "${GREEN}✓ Data seeding completed successfully${NC}"
else
    echo -e "${RED}❌ Data seeding failed${NC}"
    exit 1
fi

echo ""
echo "=========================================="
echo -e "${GREEN}✓ Database setup completed!${NC}"
echo "=========================================="
echo ""
echo "📝 Next steps:"
echo "  1. Start the backend server: ./run.sh"
echo "  2. Access API docs: http://localhost:8000/docs"
echo "  3. Login with default admin credentials:"
echo "     Email: admin@cdsa.local"
echo "     Password: admin123"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT: Change the admin password immediately!${NC}"
echo ""