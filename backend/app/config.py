"""Application configuration using Pydantic Settings."""
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    # Application
    APP_NAME: str = "CDSA Backend"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_RELOAD: bool = False
    CORS_ORIGINS: str = "http://localhost:3000"
    
    @field_validator("CORS_ORIGINS")
    @classmethod
    def parse_cors_origins(cls, v: str) -> List[str]:
        """Parse comma-separated CORS origins."""
        return [origin.strip() for origin in v.split(",")]
    
    # Database
    DATABASE_URL: str = Field(..., description="PostgreSQL database URL")
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 0
    DB_ECHO: bool = False
    
    # Redis
    REDIS_URL: str = Field(..., description="Redis connection URL")
    REDIS_CACHE_DB: int = 1
    REDIS_SESSION_DB: int = 2
    REDIS_NOTIFICATION_DB: int = 4
    
    # Security
    SECRET_KEY: str = Field(..., description="Secret key for signing")
    JWT_SECRET_KEY: str = Field(..., description="JWT secret key")
    JWT_ALGORITHM: str = "HS256"
    ALGORITHM: str = "HS256"  # Alias for JWT_ALGORITHM
    JWT_EXPIRATION_MINUTES: int = 60
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # Alias for JWT_EXPIRATION_MINUTES
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ENCRYPTION_KEY: str = Field(..., description="Encryption key for vault")
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60
    
    # LLM Configuration
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_TEMPERATURE: float = 0.7
    
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-opus-20240229"
    
    GEMINI_API_KEY: str = ""
    
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_DEFAULT_MODEL: str = "llama3:8b"
    
    # Embeddings
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536
    
    # RAG Configuration
    RAG_CHUNK_SIZE: int = 1000
    RAG_CHUNK_OVERLAP: int = 200
    RAG_TOP_K: int = 5
    
    # Celery
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/3")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/3")
    
    # Context Window
    MAX_CONTEXT_WINDOW: int = 4096
    CONTEXT_PRUNING_THRESHOLD: int = 3500
    
    # Notifications
    NOTIFICATION_RETENTION_DAYS: int = 30
    NOTIFICATION_BATCH_SIZE: int = 100
    
    # File Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 10485760  # 10MB
    
    # Monitoring
    SENTRY_DSN: str = ""
    ENABLE_METRICS: bool = True
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.ENVIRONMENT.lower() == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.ENVIRONMENT.lower() == "production"


# Global settings instance
settings = Settings()