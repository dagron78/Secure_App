"""Production environment validation utilities."""
import sys
from typing import List
from app.config import settings
from app.core.logging import setup_logging

logger = setup_logging()


def validate_production_config() -> List[str]:
    """Validate configuration for production deployment.
    
    Returns:
        List of validation errors (empty if all validations pass)
    """
    errors = []
    
    # Validate SECRET_KEY
    if not settings.SECRET_KEY or len(settings.SECRET_KEY) < 32:
        errors.append("SECRET_KEY must be at least 32 characters long")
    
    if "your-" in settings.SECRET_KEY.lower() or "change" in settings.SECRET_KEY.lower():
        errors.append("SECRET_KEY appears to be a default/placeholder value - must be changed for production")
    
    # Validate JWT_SECRET_KEY
    if not settings.JWT_SECRET_KEY or len(settings.JWT_SECRET_KEY) < 32:
        errors.append("JWT_SECRET_KEY must be at least 32 characters long")
    
    if "your-" in settings.JWT_SECRET_KEY.lower() or "change" in settings.JWT_SECRET_KEY.lower():
        errors.append("JWT_SECRET_KEY appears to be a default/placeholder value - must be changed for production")
    
    # Validate ENCRYPTION_KEY
    if not settings.ENCRYPTION_KEY:
        errors.append("ENCRYPTION_KEY is required for production")
    elif "your-" in settings.ENCRYPTION_KEY.lower() or "change-me" in settings.ENCRYPTION_KEY.lower():
        errors.append("ENCRYPTION_KEY appears to be a default/placeholder value - must be changed for production")
    else:
        # Try to validate the encryption key format
        try:
            from cryptography.fernet import Fernet
            import base64
            # Fernet keys must be 32 url-safe base64-encoded bytes
            key_bytes = base64.urlsafe_b64decode(settings.ENCRYPTION_KEY)
            if len(key_bytes) != 32:
                errors.append("ENCRYPTION_KEY must be 32 bytes when base64-decoded (use Fernet.generate_key())")
        except Exception as e:
            errors.append(f"ENCRYPTION_KEY is not a valid Fernet key: {e}")
    
    # Validate database configuration
    if "changeme" in settings.DATABASE_URL.lower():
        errors.append("DATABASE_URL contains default password 'changeme' - must be changed for production")
    
    # Validate CORS origins
    if "*" in settings.CORS_ORIGINS:
        errors.append("CORS_ORIGINS should not contain wildcard '*' in production")
    
    if "localhost" in " ".join(settings.CORS_ORIGINS):
        logger.warning("CORS_ORIGINS contains 'localhost' - this may be intentional for development access")
    
    # Validate DEBUG mode
    if settings.DEBUG:
        errors.append("DEBUG mode should be disabled in production (set DEBUG=false)")
    
    return errors


def enforce_production_validation():
    """Enforce production configuration validation.
    
    Exits the application if validation fails in production environment.
    """
    if not settings.is_production:
        logger.info("Development environment detected - skipping strict validation")
        return
    
    logger.info("Production environment detected - validating configuration...")
    errors = validate_production_config()
    
    if errors:
        logger.error("Production configuration validation failed:")
        for error in errors:
            logger.error(f"  ❌ {error}")
        
        logger.error("\n" + "="*80)
        logger.error("CRITICAL: Application cannot start with invalid production configuration")
        logger.error("Please fix the above errors and restart the application")
        logger.error("="*80 + "\n")
        
        sys.exit(1)
    
    logger.info("✓ Production configuration validation passed")
