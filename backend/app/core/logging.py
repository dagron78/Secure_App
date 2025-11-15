"""Logging configuration using structlog."""
import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from app.config import settings


def add_app_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add application context to log events."""
    event_dict["app"] = settings.APP_NAME
    event_dict["environment"] = settings.ENVIRONMENT
    return event_dict


def setup_logging() -> structlog.BoundLogger:
    """Configure structured logging."""
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper()),
    )
    
    # Processors for structlog
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        add_app_context,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    
    # Add development-friendly formatting
    if settings.is_development:
        processors.extend([
            structlog.dev.set_exc_info,
            structlog.dev.ConsoleRenderer(colors=True),
        ])
    else:
        # Production: JSON formatting
        processors.extend([
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ])
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.LOG_LEVEL.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    return structlog.get_logger()


def log_api_call(func):
    """Decorator to log API calls with timing information."""
    import functools
    import time
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        logger = structlog.get_logger()
        start_time = time.time()
        
        # Get function info
        func_name = func.__name__
        
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            
            logger.info(
                "api_call_completed",
                function=func_name,
                duration_seconds=round(duration, 3),
                status="success"
            )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            
            logger.error(
                "api_call_failed",
                function=func_name,
                duration_seconds=round(duration, 3),
                error=str(e),
                status="error"
            )
            raise
    
    return wrapper