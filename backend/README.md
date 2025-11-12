# CDSA Backend - Confidential Data Steward Agent

Backend API for the Confidential Data Steward Agent, built with FastAPI, PostgreSQL, Redis, and AI/ML frameworks.

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- [uv](https://github.com/astral-sh/uv) package manager (optional, for faster installs)

### Setup with Docker (Recommended)

1. **Clone and navigate to backend:**
```bash
cd backend
```

2. **Copy environment variables:**
```bash
cp .env.example .env
# Edit .env with your API keys and secrets
```

3. **Start services:**
```bash
docker-compose up -d
```

4. **Run database migrations:**
```bash
docker-compose exec api alembic upgrade head
```

5. **Access the API:**
- API: http://localhost:8000
- Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

### Local Development Setup

1. **Install uv (if not installed):**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. **Create virtual environment and install dependencies:**
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
```

3. **Set up environment variables:**
```bash
cp .env.example .env
# Edit .env file with your configuration
```

4. **Start PostgreSQL and Redis (via Docker):**
```bash
docker-compose up -d postgres redis
```

5. **Run migrations:**
```bash
alembic upgrade head
```

6. **Start development server:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📁 Project Structure

```
backend/
├── app/
│   ├── api/              # API endpoints
│   │   └── v1/           # API version 1
│   ├── core/             # Core functionality (auth, security, logging)
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic
│   ├── tools/            # Tool implementations
│   ├── db/               # Database configuration
│   ├── middleware/       # Custom middleware
│   └── utils/            # Utility functions
├── tests/                # Test suite
├── alembic/              # Database migrations
├── scripts/              # Utility scripts
├── docker-compose.yml    # Docker services
├── Dockerfile            # Application container
└── pyproject.toml        # Python dependencies
```

## 🔧 Configuration

### Environment Variables

Key configuration variables (see `.env.example` for full list):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://cdsa:password@localhost:5432/cdsa_db

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-here
ENCRYPTION_KEY=your-encryption-key-base64

# LLM APIs (optional)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...

# Local LLM (Ollama)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=llama3:8b
```

## 🗄️ Database

### Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current version
alembic current
```

### Schema

The database includes tables for:
- Users & Authentication
- Chat Messages & Sessions
- Tools Registry & Executions
- Approval Workflows
- Audit Events
- Secrets Vault
- Documents & Embeddings
- Notifications
- LLM Models Registry

## 🤖 AI/ML Integration

### Supported LLM Providers

1. **OpenAI** (GPT-4, GPT-3.5)
2. **Anthropic** (Claude 3)
3. **Google** (Gemini)
4. **Local Models** (via Ollama)

### Setting up Local Models

```bash
# Pull a model with Ollama
docker-compose exec ollama ollama pull llama3:8b

# List available models
docker-compose exec ollama ollama list
```

## 🔐 Security Features

- JWT-based authentication
- Role-Based Access Control (RBAC)
- Field-level encryption for sensitive data
- Complete audit logging
- Rate limiting
- CORS protection
- Request validation

## 📊 Monitoring & Logging

### Logs

```bash
# View application logs
docker-compose logs -f api

# View all service logs
docker-compose logs -f
```

### Health Checks

```bash
# Basic health check
curl http://localhost:8000/health

# Database connection check
curl http://localhost:8000/health/db
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_auth.py

# Run with verbose output
pytest -v
```

## 🚢 Deployment

### Production Build

```bash
# Build production image
docker build -t cdsa-backend:latest .

# Run with production settings
docker-compose -f docker-compose.prod.yml up -d
```

### Environment-Specific Configs

- Development: `.env`
- Production: `.env.production`
- Staging: `.env.staging`

## 📝 API Documentation

### Interactive Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### API Endpoints

#### Authentication
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/login` - User login
- `GET /api/v1/auth/me` - Get current user

#### Chat
- `POST /api/v1/chat/stream` - Streaming chat (SSE)
- `POST /api/v1/chat/continue` - Continue after approval

#### Notifications
- `GET /api/v1/notifications/stream` - Real-time notifications (SSE)
- `GET /api/v1/notifications` - Get notification history

#### Tools
- `GET /api/v1/tools` - List available tools
- `POST /api/v1/tools/{id}/execute` - Execute tool

## 🛠️ Development

### Code Quality

```bash
# Format code
black app tests

# Sort imports
isort app tests

# Lint code
flake8 app tests

# Type checking
mypy app
```

### Adding a New Tool

1. Create tool class in `app/tools/`
2. Inherit from `BaseTool`
3. Implement `execute()` method
4. Register in tool registry
5. Add tests

### Adding a New API Endpoint

1. Create router in `app/api/v1/`
2. Define schemas in `app/schemas/`
3. Implement business logic in `app/services/`
4. Add tests
5. Register router in `app/main.py`

## 🐛 Troubleshooting

### Common Issues

**Database connection error:**
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# View PostgreSQL logs
docker-compose logs postgres
```

**Redis connection error:**
```bash
# Check if Redis is running
docker-compose ps redis

# Test Redis connection
docker-compose exec redis redis-cli ping
```

**Migration errors:**
```bash
# Reset database (WARNING: deletes all data)
alembic downgrade base
alembic upgrade head
```

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [LangChain Documentation](https://python.langchain.com/)
- [Architecture Plan](../backend-architecture-plan.md)
- [Notification System](../NOTIFICATION_SYSTEM_ENHANCEMENT.md)

## 🤝 Contributing

1. Create a feature branch
2. Make your changes
3. Add tests
4. Run code quality checks
5. Submit a pull request

## 📄 License

Proprietary - All rights reserved

## 👥 Team

- Architecture: AI Architect
- Development: [Your Team]

---

**Version:** 1.0.0  
**Last Updated:** 2025-11-12