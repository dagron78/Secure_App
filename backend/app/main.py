"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pydantic import ValidationError as PydanticValidationError

from app.config import settings
from app.core.logging import setup_logging
from app.db.base import init_db, close_db, Base
from app.services.notification_service import notification_service
from app.core.exceptions import (
    CDSAException,
    DatabaseError,
    NotFoundError,
    AuthenticationError,
    AuthorizationError,
    ValidationError,
    ExternalServiceError,
    RateLimitError,
    EncryptionError,
    ConfigurationError
)

# Import all models to ensure they're registered with Base.metadata
import app.models  # This imports all models from __init__.py

# Setup logging
logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
    # Startup
    try:
        # Initialize database connection
        logger.info("Initializing database connection...")
        engine, session_factory = init_db()
        logger.info("✓ Database connection initialized")
        
        # Create database tables
        logger.info("Creating database tables...")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✓ Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            # Don't raise - allow app to continue if tables already exist
            logger.info("Tables may already exist, continuing...")
        
        # Initialize Redis connection (optional, for notifications pub/sub)
        try:
            import redis.asyncio as redis
            redis_client = await redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            notification_service.set_redis(redis_client)
            await notification_service.start_redis_listener()
            logger.info("✓ Redis connection initialized")
        except Exception as e:
            logger.warning(f"Redis not available (notifications will work locally only): {e}")
        
        logger.info(f"{settings.APP_NAME} startup complete")
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    
    try:
        # Stop notification service
        await notification_service.stop_redis_listener()
        logger.info("✓ Notification service stopped")
        
        # Close database connections
        await close_db()
        logger.info("✓ Database connections closed")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    
    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Confidential Data Steward Agent - Backend API",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # TODO: Add actual health checks for database, redis, etc.
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "services": {
            "database": "pending",
            "redis": "pending",
            "llm": "pending",
        }
    }


# Exception handlers
@app.exception_handler(CDSAException)
async def cdsa_exception_handler(request: Request, exc: CDSAException):
    """Handle custom CDSA exceptions."""
    logger.error(
        f"CDSA Exception: {exc.error_code} - {exc.message}",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path
        }
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details
            }
        }
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Handle database integrity errors."""
    logger.error(f"Database integrity error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=409,
        content={
            "error": {
                "code": "INTEGRITY_ERROR",
                "message": "Database constraint violation",
                "details": {"constraint": str(exc.orig) if hasattr(exc, 'orig') else None}
            }
        }
    )


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    """Handle general database errors."""
    logger.error(f"Database error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "DATABASE_ERROR",
                "message": "Database operation failed",
                "details": {}
            }
        }
    )


@app.exception_handler(PydanticValidationError)
async def validation_error_handler(request: Request, exc: PydanticValidationError):
    """Handle Pydantic validation errors."""
    logger.error(f"Validation error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": exc.errors()}
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions."""
    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,
        extra={"path": request.url.path, "method": request.method}
    )
    
    # Don't expose internal errors in production
    if settings.is_production:
        message = "An internal error occurred"
    else:
        message = str(exc)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": message,
                "details": {}
            }
        }
    )


# Register API routers
from app.api.v1 import auth, chat, tools, audit, vault, documents, llm, notifications

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(tools.router, prefix="/api/v1", tags=["Tools"])
app.include_router(audit.router, prefix="/api/v1", tags=["Audit"])
app.include_router(vault.router, prefix="/api/v1", tags=["Vault"])
app.include_router(documents.router, prefix="/api/v1", tags=["Documents"])
app.include_router(llm.router, prefix="/api/v1", tags=["LLM"])
app.include_router(notifications.router, prefix="/api/v1", tags=["Notifications"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD,
    )