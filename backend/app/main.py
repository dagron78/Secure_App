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
from app.core.cache import cache_manager
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
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.rate_limit import limiter
from slowapi.errors import RateLimitExceeded
from app.core.validation import enforce_production_validation

# Import all models to ensure they're registered with Base.metadata
import app.models  # This imports all models from __init__.py

# Setup logging
logger = setup_logging()

# Validate production configuration before app starts
enforce_production_validation()


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
        
        # Initialize cache manager
        try:
            await cache_manager.connect()
            logger.info("✓ Cache manager initialized")
        except Exception as e:
            logger.warning(f"Cache not available: {e}")
        
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
        
        # Disconnect cache manager
        await cache_manager.disconnect()
        logger.info("✓ Cache manager disconnected")
        
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

# Add rate limiter state
app.state.limiter = limiter

# Security headers middleware (add first for all responses)
app.add_middleware(SecurityHeadersMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],  # Specific methods only
    allow_headers=["Content-Type", "Authorization", "X-Request-ID", "Accept"],  # Specific headers only
    expose_headers=["X-Request-ID"],
    max_age=3600,  # Cache preflight requests for 1 hour
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
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health/ready")
async def readiness_check():
    """Readiness probe - checks if app is ready to serve traffic."""
    from app.db.base import get_session_factory
    from app.core.cache import cache_manager
    from sqlalchemy import text
    
    services_status = {
        "database": "unknown",
        "redis": "unknown",
    }
    
    # Check database connectivity
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        services_status["database"] = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        services_status["database"] = "unhealthy"
    
    # Check Redis connectivity  
    try:
        if cache_manager._redis is not None:
            await cache_manager._redis.ping()
            services_status["redis"] = "healthy"
        else:
            services_status["redis"] = "not_configured"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        services_status["redis"] = "unhealthy"
    
    # Overall health status
    all_healthy = all(
        status in ["healthy", "not_configured"]
        for status in services_status.values()
    )
    
    status_code = 200 if all_healthy else 503
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_healthy else "not_ready",
            "version": settings.APP_VERSION,
            "services": services_status,
        }
    )


@app.get("/health/live")
async def liveness_check():
    """Liveness probe - checks if app is running."""
    return {
        "status": "alive",
        "version": settings.APP_VERSION,
    }


@app.get("/cache/stats")
async def cache_stats():
    """Get cache statistics."""
    from app.core.cache import get_cache_stats
    return await get_cache_stats()


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


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded errors."""
    logger.warning(
        f"Rate limit exceeded for {request.client.host}",
        extra={"path": request.url.path, "method": request.method}
    )
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests. Please try again later.",
                "details": {}
            }
        },
        headers={"Retry-After": str(exc.detail)}
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