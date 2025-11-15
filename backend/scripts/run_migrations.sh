#!/bin/bash
set -e

echo "Starting database migrations..."

# Wait for database to be ready
echo "Waiting for database..."
while ! pg_isready -h ${DATABASE_HOST:-postgres} -p ${DATABASE_PORT:-5432} -U ${DATABASE_USER:-cdsa}; do
    sleep 1
done

echo "Database is ready"

# Run Alembic migrations
echo "Running Alembic migrations..."
cd /app
alembic upgrade head

echo "Migrations completed successfully"