"""Authentication API endpoints."""
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, update
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.deps import get_current_user, get_current_superuser, get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    validate_refresh_token,
    verify_password,
    hash_token,
)
from app.models.user import User, Session as UserSession
from app.schemas.auth import (
    UserCreate,
    UserResponse,
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    PasswordChange,
    UserWithRoles,
)
from app.middleware.rate_limit import auth_rate_limit

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@auth_rate_limit()
async def register(
    request: Request,
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Register a new user.
    
    Args:
        user_data: User registration data
        db: Database session
        
    Returns:
        The created user
        
    Raises:
        HTTPException: If username or email already exists
    """
    # Check if username exists
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )
    
    # Check if email exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Create new user
    user = User(
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password),
        is_active=True,
        is_superuser=False,
        is_verified=False,
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return user


@router.post("/login", response_model=TokenResponse)
@auth_rate_limit()
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Authenticate user and return access and refresh tokens.
    
    Args:
        login_data: Login credentials (username/email and password)
        db: Database session
        
    Returns:
        Access and refresh tokens
        
    Raises:
        HTTPException: If credentials are invalid
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"[AUTH] Login attempt for username: {login_data.username}")
    
    # Try to find user by username or email - query specific columns only
    result = await db.execute(
        select(User.id, User.username, User.email, User.hashed_password, User.is_active).where(
            or_(User.username == login_data.username, User.email == login_data.username)
        )
    )
    row = result.one_or_none()
    
    if not row:
        logger.warning(f"[AUTH] User not found: {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id, username, email, hashed_password, is_active = row
    logger.info(f"[AUTH] User found: {username} (ID: {user_id}, active: {is_active})")
    
    if not verify_password(login_data.password, hashed_password):
        logger.warning(f"[AUTH] Invalid password for user: {username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.info(f"[AUTH] Password verified for user: {username}")
    
    if not is_active:
        logger.warning(f"[AUTH] Inactive user attempted login: {username}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    
    # Store user_id as string (for UUID compatibility)
    user_id_str = str(user_id)
    
    # Create tokens
    access_token = create_access_token(subject=user_id_str)
    refresh_token = create_refresh_token(subject=user_id_str)
    logger.info(f"[AUTH] Tokens generated for user: {username}")
    
    # Update last login
    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(last_login=datetime.utcnow())
    )
    
    # Create session record for token rotation and logout
    # Store hashed tokens for security
    session = UserSession(
        user_id=user_id,
        token=hash_token(access_token),
        refresh_token=hash_token(refresh_token),
        is_active=True,
        expires_at=datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    db.add(session)
    await db.commit()
    
    logger.info(f"[AUTH] Login successful for user: {username} (ID: {user_id})")
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/refresh", response_model=TokenResponse)
@auth_rate_limit()
async def refresh_token(
    request: Request,
    token_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Refresh access token using refresh token.
    
    Args:
        refresh_data: Refresh token
        db: Database session
        
    Returns:
        New access and refresh tokens
        
    Raises:
        HTTPException: If refresh token is invalid
    """
    # Validate refresh token
    user_id = validate_refresh_token(token_data.refresh_token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    # Invalidate old session by looking up hashed token
    hashed_refresh_token = hash_token(token_data.refresh_token)
    result = await db.execute(
        select(UserSession).where(UserSession.refresh_token == hashed_refresh_token)
    )
    old_session = result.scalar_one_or_none()
    if old_session:
        old_session.is_active = False
        await db.commit()
    
    # Create new tokens
    access_token = create_access_token(subject=user.id)
    new_refresh_token = create_refresh_token(subject=user.id)
    
    # Create new session with hashed tokens
    session = UserSession(
        user_id=user.id,
        token=hash_token(access_token),
        refresh_token=hash_token(new_refresh_token),
        is_active=True,
        expires_at=datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    db.add(session)
    await db.commit()
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Logout current user by invalidating their sessions.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Success message
    """
    # Invalidate all active sessions for this user
    result = await db.execute(
        select(UserSession).where(
            UserSession.user_id == current_user.id,
            UserSession.is_active == True
        )
    )
    sessions = result.scalars().all()
    for session in sessions:
        session.is_active = False
    await db.commit()
    
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserWithRoles)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get current user information with roles and permissions.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User information with roles and permissions
    """
    return {
        **UserResponse.from_orm(current_user).dict(),
        "roles": [role.name for role in current_user.roles],
        "permissions": current_user.permissions,
    }


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    update_data: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update current user information.
    
    Args:
        update_data: Fields to update
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Updated user information
        
    Raises:
        HTTPException: If username/email already exists
    """
    # Check if username is being changed and if it already exists
    if "username" in update_data and update_data["username"] != current_user.username:
        result = await db.execute(select(User).where(User.username == update_data["username"]))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )
    
    # Check if email is being changed and if it already exists
    if "email" in update_data and update_data["email"] != current_user.email:
        result = await db.execute(select(User).where(User.email == update_data["email"]))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
    
    # Update allowed fields
    allowed_fields = ["username", "email", "full_name"]
    for field in allowed_fields:
        if field in update_data:
            setattr(current_user, field, update_data[field])
    
    current_user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(current_user)
    
    return current_user


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Change current user's password.
    
    Args:
        password_data: Current and new password
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If current password is incorrect
    """
    # Verify current password
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password",
        )
    
    # Update password
    current_user.hashed_password = get_password_hash(password_data.new_password)
    current_user.updated_at = datetime.utcnow()
    
    # Invalidate all sessions (force re-login)
    result = await db.execute(
        select(UserSession).where(
            UserSession.user_id == current_user.id,
            UserSession.is_active == True
        )
    )
    sessions = result.scalars().all()
    for session in sessions:
        session.is_active = False
    
    await db.commit()
    
    return {"message": "Password changed successfully. Please login again."}


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """List all users (superuser only).
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        current_user: Current authenticated superuser
        db: Database session
        
    Returns:
        List of users
    """
    result = await db.execute(select(User).offset(skip).limit(limit))
    users = result.scalars().all()
    return users


@router.get("/users/{user_id}", response_model=UserWithRoles)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get user by ID (superuser only).
    
    Args:
        user_id: User ID
        current_user: Current authenticated superuser
        db: Database session
        
    Returns:
        User information with roles
        
    Raises:
        HTTPException: If user not found
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    return {
        **UserResponse.from_orm(user).dict(),
        "roles": [role.name for role in user.roles],
        "permissions": user.permissions,
    }