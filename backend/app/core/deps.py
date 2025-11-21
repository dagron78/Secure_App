"""FastAPI dependencies for authentication and authorization."""
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.security import validate_access_token
from app.db.base import get_db
from app.models.user import User, Role, Permission

# HTTP Bearer token authentication
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get the current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer credentials with JWT token
        db: Async database session
        
    Returns:
        The authenticated user
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    # Extract token
    token = credentials.credentials
    
    # Validate token and get user ID
    user_id = validate_access_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database with roles and permissions eagerly loaded
    result = await db.execute(
        select(User)
        .where(User.id == int(user_id))
        .options(
            selectinload(User.roles).selectinload(Role.permissions)
        )
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current active user (alias for clarity).
    
    Args:
        current_user: The current user from get_current_user
        
    Returns:
        The authenticated active user
    """
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current user if they are a superuser.
    
    Args:
        current_user: The current user from get_current_user
        
    Returns:
        The authenticated superuser
        
    Raises:
        HTTPException: If user is not a superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


def require_permission(permission: str):
    """Create a dependency that requires a specific permission.
    
    Args:
        permission: The permission name required
        
    Returns:
        A dependency function that checks the permission
    """
    async def permission_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if not current_user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission}",
            )
        return current_user
    
    return permission_checker


def require_role(role: str):
    """Create a dependency that requires a specific role.
    
    Args:
        role: The role name required
        
    Returns:
        A dependency function that checks the role
    """
    async def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if not current_user.has_role(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role required: {role}",
            )
        return current_user
    
    return role_checker


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Get the current user if authenticated, None otherwise.
    
    Useful for endpoints that work with or without authentication.
    
    Args:
        credentials: Optional HTTP Bearer credentials
        db: Async database session
        
    Returns:
        The authenticated user or None
    """
    if credentials is None:
        return None
    
    # Extract token
    token = credentials.credentials
    
    # Validate token and get user ID
    user_id = validate_access_token(token)
    if user_id is None:
        return None
    
    # Get user from database
    result = await db.execute(
        select(User).where(User.id == int(user_id))
    )
    user = result.scalar_one_or_none()
    
    if user is None or not user.is_active:
        return None
    
    return user