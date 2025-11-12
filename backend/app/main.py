"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.logging import setup_logging

# Setup logging
logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
    # Startup
    # TODO: Initialize database connection
    # TODO: Initialize Redis connection
    # TODO: Initialize notification service
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    # TODO: Close database connections
    # TODO: Close Redis connections


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
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Register API routers
from app.api.v1 import auth, chat, tools, audit, vault, documents, llm

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(tools.router, prefix="/api/v1", tags=["Tools"])
app.include_router(audit.router, prefix="/api/v1", tags=["Audit"])
app.include_router(vault.router, prefix="/api/v1", tags=["Vault"])
app.include_router(documents.router, prefix="/api/v1", tags=["Documents"])
app.include_router(llm.router, prefix="/api/v1", tags=["LLM"])

# TODO: Register additional routers
# from app.api.v1 import notifications
# app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notifications"])
# ... etc


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD,
    )