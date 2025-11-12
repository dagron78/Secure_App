#!/bin/bash
# Simple startup script for CDSA Backend

echo "🚀 Starting CDSA Backend..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env created - please update with your API keys if needed"
    echo ""
fi

# Check if running in Docker or locally
if command -v docker &> /dev/null && docker info &> /dev/null; then
    echo "🐳 Docker is available"
    echo "Starting services with Docker Compose..."
    echo ""
    docker-compose up -d
    echo ""
    echo "✅ Services started!"
    echo ""
    echo "📍 Access points:"
    echo "   API:      http://localhost:8000"
    echo "   Docs:     http://localhost:8000/docs"
    echo "   Health:   http://localhost:8000/health"
    echo ""
    echo "📊 View logs: docker-compose logs -f api"
    echo "🛑 Stop: docker-compose down"
else
    echo "⚠️  Docker not available, trying local Python..."
    echo ""
    
    # Install minimal dependencies if needed
    python3 -m pip install fastapi uvicorn[standard] pydantic pydantic-settings structlog python-dotenv --quiet --break-system-packages 2>/dev/null || \
    python3 -m pip install fastapi uvicorn[standard] pydantic pydantic-settings structlog python-dotenv --quiet --user
    
    echo "🐍 Starting with uvicorn..."
    echo ""
    python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
fi