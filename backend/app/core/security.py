"""Security utilities for authentication and authorization."""
from datetime import datetime, timedelta
from typing import Any, Optional, Union
import hashlib

from jose import JWTError, jwt
import bcrypt

from app.config import settings


def hash_token(token: str) -> str:
    """Hash a token using SHA256 for secure storage.
    
    Args:
        token: The token to hash
        
    Returns:
        The SHA256 hash of the token as a hex string
    """
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash.
    
    Args:
        plain_password: The plain text password
        hashed_password: The hashed password to check against
        
    Returns:
        True if password matches, False otherwise
    """
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def get_password_hash(password: str) -> str:
    """Hash a password for storing.
    
    Args:
        password: The plain text password to hash
        
    Returns:
        The hashed password
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def create_access_token(
    subject: Union[str, int],
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[dict[str, Any]] = None,
) -> str:
    """Create a JWT access token.
    
    Args:
        subject: The subject (usually user ID) for the token
        expires_delta: Optional custom expiration time
        additional_claims: Optional additional claims to include in token
        
    Returns:
        Encoded JWT token string
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "access",
    }
    
    if additional_claims:
        to_encode.update(additional_claims)
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


def create_refresh_token(
    subject: Union[str, int],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT refresh token.
    
    Args:
        subject: The subject (usually user ID) for the token
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT refresh token string
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "refresh",
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[dict[str, Any]]:
    """Decode and validate a JWT token.
    
    Args:
        token: The JWT token to decode
        
    Returns:
        The decoded token payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError:
        return None


def validate_access_token(token: str) -> Optional[str]:
    """Validate an access token and return the subject.
    
    Args:
        token: The access token to validate
        
    Returns:
        The subject (user ID) if valid, None otherwise
    """
    payload = decode_token(token)
    if payload is None:
        return None
    
    # Check token type
    if payload.get("type") != "access":
        return None
    
    # Get subject
    subject: str = payload.get("sub")
    if subject is None:
        return None
    
    return subject


def validate_refresh_token(token: str) -> Optional[str]:
    """Validate a refresh token and return the subject.
    
    Args:
        token: The refresh token to validate
        
    Returns:
        The subject (user ID) if valid, None otherwise
    """
    payload = decode_token(token)
    if payload is None:
        return None
    
    # Check token type
    if payload.get("type") != "refresh":
        return None
    
    # Get subject
    subject: str = payload.get("sub")
    if subject is None:
        return None
    
    return subject