"""Security headers middleware for FastAPI."""
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response.
        
        Args:
            request: The incoming request
            call_next: The next middleware/handler
            
        Returns:
            Response with security headers added
        """
        response = await call_next(request)
        
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Prevent clickjacking attacks
        response.headers["X-Frame-Options"] = "DENY"
        
        # Enable XSS filter in older browsers
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Enforce HTTPS in production
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Content Security Policy - restrictive default
        # Allow self for scripts/styles, block inline scripts by default
        csp_directives = [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline'",  # Allow inline styles for React
            "img-src 'self' data: https:",
            "font-src 'self' data:",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'"
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
        
        # Referrer policy - don't leak URLs to external sites
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions policy - disable unused browser features
        permissions_directives = [
            "geolocation=()",
            "microphone=()",
            "camera=()",
            "payment=()",
            "usb=()",
            "magnetometer=()",
            "gyroscope=()",
            "accelerometer=()"
        ]
        response.headers["Permissions-Policy"] = ", ".join(permissions_directives)
        
        return response
