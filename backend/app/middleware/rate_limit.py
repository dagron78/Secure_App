"""Rate limiting middleware using slowapi."""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.config import settings


# Create rate limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_PERIOD}second"],
    storage_uri=settings.REDIS_URL,  # Use Redis for distributed rate limiting
    strategy="fixed-window",  # Can also use "moving-window" for more accuracy
)


# Pre-defined rate limit decorators for common use cases
def auth_rate_limit():
    """Strict rate limit for authentication endpoints: 5 requests per 15 minutes."""
    return limiter.limit("5/15minute")


def standard_rate_limit():
    """Standard rate limit: 100 requests per minute."""
    return limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_PERIOD}second")


def expensive_operation_rate_limit():
    """Rate limit for expensive operations: 10 requests per minute."""
    return limiter.limit("10/minute")
