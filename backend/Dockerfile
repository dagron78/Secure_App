FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Copy project files
COPY pyproject.toml ./

# Install Python dependencies using uv
RUN uv pip install --system --no-cache -e .

# Copy application code
COPY ./app ./app
COPY ./alembic ./alembic
COPY ./alembic.ini ./

# Create non-root user
RUN useradd -m -u 1000 cdsa && chown -R cdsa:cdsa /app
USER cdsa

# Expose port
EXPOSE 8000

# Copy scripts
COPY ./scripts ./scripts
RUN chmod +x ./scripts/*.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start server (migrations run separately)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]