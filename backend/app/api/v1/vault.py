"""
Secrets vault API endpoints.
Handles secure storage, retrieval, and management of secrets.
"""
from datetime import datetime, timedelta
from typing import List, Optional
import hashlib
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    get_current_user,
    require_permission,
    get_db
)
from app.models.user import User
from app.models.secret import Secret, SecretVersion, SecretAccessLog, SecretType
from app.schemas.secret import (
    SecretCreate,
    SecretUpdate,
    SecretResponse,
    SecretValueResponse,
    SecretListResponse,
    SecretVersionResponse,
    SecretVersionListResponse,
    SecretAccessLogResponse,
    SecretAccessLogListResponse,
    SecretRotateRequest,
    SecretStatistics
)
from app.api.v1.audit import create_audit_log
from app.models.audit import AuditAction

router = APIRouter(prefix="/vault", tags=["vault"])


# ============================================================================
# Helper Functions
# ============================================================================

async def log_secret_access(
    db: AsyncSession,
    secret: Secret,
    user: User,
    access_type: str,
    request: Request
):
    """Log secret access for audit trail"""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    access_log = SecretAccessLog(
        secret_id=secret.id,
        user_id=user.id,
        access_type=access_type,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    db.add(access_log)
    
    # Update secret's last accessed time
    secret.last_accessed_at = datetime.utcnow()
    secret.access_count += 1
    
    # Create audit log
    await create_audit_log(
        db=db,
        user_id=user.id,
        action=AuditAction.SECRET_ACCESSED if access_type == "read" else AuditAction.SECRET_CREATED,
        resource_type="secret",
        resource_id=secret.id,
        details={
            "secret_name": secret.name,
            "access_type": access_type,
            "secret_type": secret.secret_type.value
        },
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    await db.commit()


def _hash_value(value: str) -> str:
    """Generate SHA256 hash of value for versioning"""
    return hashlib.sha256(value.encode()).hexdigest()


# ============================================================================
# Secret Management Endpoints
# ============================================================================

@router.post("/secrets", response_model=SecretResponse, status_code=status.HTTP_201_CREATED)
async def create_secret(
    secret_data: SecretCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("vault.create"))
):
    """
    Create a new secret.
    Requires 'vault.create' permission.
    The value will be encrypted at rest.
    """
    # Check if secret with same name exists
    result = await db.execute(
        select(Secret).where(Secret.name == secret_data.name)
    )
    existing_secret = result.scalar_one_or_none()
    
    if existing_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Secret with name '{secret_data.name}' already exists"
        )
    
    # Create secret
    secret = Secret(
        name=secret_data.name,
        description=secret_data.description,
        secret_type=secret_data.secret_type,
        tags=secret_data.tags,
        expires_at=secret_data.expires_at,
        created_by=current_user.id
    )
    
    # Encrypt and set value (uses property setter)
    secret.value = secret_data.value
    
    db.add(secret)
    await db.commit()
    await db.refresh(secret)
    
    # Create initial version
    value_hash = _hash_value(secret_data.value)
    version = SecretVersion(
        secret_id=secret.id,
        version=1,
        value_hash=value_hash,
        created_by=current_user.id
    )
    db.add(version)
    
    # Log access
    await log_secret_access(db, secret, current_user, "create", request)
    
    return SecretResponse(
        id=secret.id,
        name=secret.name,
        description=secret.description,
        secret_type=secret.secret_type,
        tags=secret.tags,
        is_active=secret.is_active,
        is_expired=secret.is_expired,
        version=secret.version,
        expires_at=secret.expires_at,
        last_accessed_at=secret.last_accessed_at,
        last_rotated_at=secret.last_rotated_at,
        created_by=secret.created_by,
        created_at=secret.created_at,
        updated_at=secret.updated_at
    )


@router.get("/secrets", response_model=SecretListResponse)
async def list_secrets(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    secret_type: Optional[SecretType] = Query(None),
    is_active: Optional[bool] = Query(None),
    include_expired: bool = Query(False, description="Include expired secrets"),
    search: Optional[str] = Query(None, description="Search in name/description"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("vault.list"))
):
    """
    List secrets with filtering and pagination.
    Requires 'vault.list' permission.
    Does not include secret values.
    """
    # Build query
    query = select(Secret)
    
    filters = []
    if secret_type:
        filters.append(Secret.secret_type == secret_type)
    if is_active is not None:
        filters.append(Secret.is_active == is_active)
    if not include_expired:
        filters.append(or_(
            Secret.expires_at.is_(None),
            Secret.expires_at > datetime.utcnow()
        ))
    if search:
        search_term = f"%{search}%"
        filters.append(or_(
            Secret.name.ilike(search_term),
            Secret.description.ilike(search_term)
        ))
    
    if filters:
        query = query.where(and_(*filters))
    
    # Get total count
    count_query = select(func.count()).select_from(Secret)
    if filters:
        count_query = count_query.where(and_(*filters))
    result = await db.execute(count_query)
    total = result.scalar()
    
    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(Secret.name)
    
    result = await db.execute(query)
    secrets = result.scalars().all()
    
    secret_responses = [
        SecretResponse(
            id=s.id,
            name=s.name,
            description=s.description,
            secret_type=s.secret_type,
            tags=s.tags,
            is_active=s.is_active,
            is_expired=s.is_expired,
            version=s.version,
            expires_at=s.expires_at,
            last_accessed_at=s.last_accessed_at,
            last_rotated_at=s.last_rotated_at,
            created_by=s.created_by,
            created_at=s.created_at,
            updated_at=s.updated_at
        )
        for s in secrets
    ]
    
    return SecretListResponse(
        secrets=secret_responses,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/secrets/{secret_id}", response_model=SecretResponse)
async def get_secret_metadata(
    secret_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("vault.read"))
):
    """
    Get secret metadata without the value.
    Requires 'vault.read' permission.
    """
    result = await db.execute(
        select(Secret).where(Secret.id == secret_id)
    )
    secret = result.scalar_one_or_none()
    
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Secret with ID {secret_id} not found"
        )
    
    return SecretResponse(
        id=secret.id,
        name=secret.name,
        description=secret.description,
        secret_type=secret.secret_type,
        tags=secret.tags,
        is_active=secret.is_active,
        is_expired=secret.is_expired,
        version=secret.version,
        expires_at=secret.expires_at,
        last_accessed_at=secret.last_accessed_at,
        last_rotated_at=secret.last_rotated_at,
        created_by=secret.created_by,
        created_at=secret.created_at,
        updated_at=secret.updated_at
    )


@router.get("/secrets/{secret_id}/value", response_model=SecretValueResponse)
async def get_secret_value(
    secret_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("vault.read"))
):
    """
    Get secret with decrypted value.
    Requires 'vault.read' permission.
    Access is logged for audit.
    """
    result = await db.execute(
        select(Secret).where(Secret.id == secret_id)
    )
    secret = result.scalar_one_or_none()
    
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Secret with ID {secret_id} not found"
        )
    
    if not secret.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Secret is not active"
        )
    
    if secret.is_expired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Secret has expired"
        )
    
    # Log access
    await log_secret_access(db, secret, current_user, "read", request)
    
    # Decrypt value (uses property getter)
    decrypted_value = secret.value
    
    return SecretValueResponse(
        id=secret.id,
        name=secret.name,
        description=secret.description,
        secret_type=secret.secret_type,
        value=decrypted_value,
        tags=secret.tags,
        is_active=secret.is_active,
        version=secret.version,
        expires_at=secret.expires_at,
        created_at=secret.created_at
    )


@router.put("/secrets/{secret_id}", response_model=SecretResponse)
async def update_secret(
    secret_id: int,
    secret_data: SecretUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("vault.update"))
):
    """
    Update secret metadata or value.
    Requires 'vault.update' permission.
    Updating the value creates a new version.
    """
    result = await db.execute(
        select(Secret).where(Secret.id == secret_id)
    )
    secret = result.scalar_one_or_none()
    
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Secret with ID {secret_id} not found"
        )
    
    # Update fields
    update_data = secret_data.model_dump(exclude_unset=True)
    
    # Handle value update separately for versioning
    new_value = update_data.pop("value", None)
    
    for field, value in update_data.items():
        setattr(secret, field, value)
    
    if new_value:
        # Create new version
        old_value = secret.value
        secret.value = new_value
        secret.version += 1
        secret.last_rotated_at = datetime.utcnow()
        
        value_hash = _hash_value(new_value)
        version = SecretVersion(
            secret_id=secret.id,
            version=secret.version,
            value_hash=value_hash,
            created_by=current_user.id
        )
        db.add(version)
    
    secret.updated_at = datetime.utcnow()
    
    await log_secret_access(db, secret, current_user, "update", request)
    
    return SecretResponse(
        id=secret.id,
        name=secret.name,
        description=secret.description,
        secret_type=secret.secret_type,
        tags=secret.tags,
        is_active=secret.is_active,
        is_expired=secret.is_expired,
        version=secret.version,
        expires_at=secret.expires_at,
        last_accessed_at=secret.last_accessed_at,
        last_rotated_at=secret.last_rotated_at,
        created_by=secret.created_by,
        created_at=secret.created_at,
        updated_at=secret.updated_at
    )


@router.post("/secrets/{secret_id}/rotate", response_model=SecretResponse)
async def rotate_secret(
    secret_id: int,
    rotate_data: SecretRotateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("vault.rotate"))
):
    """
    Rotate a secret by creating a new version.
    Requires 'vault.rotate' permission.
    """
    result = await db.execute(
        select(Secret).where(Secret.id == secret_id)
    )
    secret = result.scalar_one_or_none()
    
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Secret with ID {secret_id} not found"
        )
    
    # Update value and increment version
    secret.value = rotate_data.new_value
    secret.version += 1
    secret.last_rotated_at = datetime.utcnow()
    secret.updated_at = datetime.utcnow()
    
    # Create version record
    value_hash = _hash_value(rotate_data.new_value)
    version = SecretVersion(
        secret_id=secret.id,
        version=secret.version,
        value_hash=value_hash,
        created_by=current_user.id
    )
    db.add(version)
    
    # Log rotation
    await create_audit_log(
        db=db,
        user_id=current_user.id,
        action=AuditAction.SECRET_ROTATED,
        resource_type="secret",
        resource_id=secret.id,
        details={
            "secret_name": secret.name,
            "new_version": secret.version,
            "reason": rotate_data.reason
        }
    )
    
    await log_secret_access(db, secret, current_user, "rotate", request)
    
    return SecretResponse(
        id=secret.id,
        name=secret.name,
        description=secret.description,
        secret_type=secret.secret_type,
        tags=secret.tags,
        is_active=secret.is_active,
        is_expired=secret.is_expired,
        version=secret.version,
        expires_at=secret.expires_at,
        last_accessed_at=secret.last_accessed_at,
        last_rotated_at=secret.last_rotated_at,
        created_by=secret.created_by,
        created_at=secret.created_at,
        updated_at=secret.updated_at
    )


@router.delete("/secrets/{secret_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_secret(
    secret_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("vault.delete"))
):
    """
    Delete a secret (soft delete by deactivating).
    Requires 'vault.delete' permission.
    """
    result = await db.execute(
        select(Secret).where(Secret.id == secret_id)
    )
    secret = result.scalar_one_or_none()
    
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Secret with ID {secret_id} not found"
        )
    
    # Soft delete
    secret.is_active = False
    secret.updated_at = datetime.utcnow()
    
    # Log deletion
    await create_audit_log(
        db=db,
        user_id=current_user.id,
        action=AuditAction.SECRET_DELETED,
        resource_type="secret",
        resource_id=secret.id,
        details={"secret_name": secret.name}
    )
    
    await db.commit()


# ============================================================================
# Secret Version Endpoints
# ============================================================================

@router.get("/secrets/{secret_id}/versions", response_model=SecretVersionListResponse)
async def list_secret_versions(
    secret_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("vault.read"))
):
    """
    List all versions of a secret.
    Requires 'vault.read' permission.
    """
    # Verify secret exists
    result = await db.execute(
        select(Secret).where(Secret.id == secret_id)
    )
    secret = result.scalar_one_or_none()
    
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Secret with ID {secret_id} not found"
        )
    
    # Get versions
    versions_result = await db.execute(
        select(SecretVersion)
        .where(SecretVersion.secret_id == secret_id)
        .order_by(desc(SecretVersion.version))
    )
    versions = versions_result.scalars().all()
    
    version_responses = [
        SecretVersionResponse(
            id=v.id,
            secret_id=v.secret_id,
            version=v.version,
            value_hash=v.value_hash,
            created_by=v.created_by,
            created_at=v.created_at
        )
        for v in versions
    ]
    
    return SecretVersionListResponse(
        versions=version_responses,
        total=len(versions)
    )


# ============================================================================
# Secret Access Log Endpoints
# ============================================================================

@router.get("/secrets/{secret_id}/access-logs", response_model=SecretAccessLogListResponse)
async def get_secret_access_logs(
    secret_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("vault.audit"))
):
    """
    Get access logs for a specific secret.
    Requires 'vault.audit' permission.
    """
    # Verify secret exists
    result = await db.execute(
        select(Secret).where(Secret.id == secret_id)
    )
    secret = result.scalar_one_or_none()
    
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Secret with ID {secret_id} not found"
        )
    
    # Build query
    query = select(SecretAccessLog).where(SecretAccessLog.secret_id == secret_id)
    
    # Get total count
    count_result = await db.execute(
        select(func.count()).select_from(SecretAccessLog)
        .where(SecretAccessLog.secret_id == secret_id)
    )
    total = count_result.scalar()
    
    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(desc(SecretAccessLog.accessed_at))
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    # Get usernames
    user_ids = [log.user_id for log in logs]
    if user_ids:
        users_result = await db.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users = {u.id: u.username for u in users_result.scalars().all()}
    else:
        users = {}
    
    log_responses = [
        SecretAccessLogResponse(
            id=log.id,
            secret_id=log.secret_id,
            secret_name=secret.name,
            user_id=log.user_id,
            username=users.get(log.user_id, "Unknown"),
            access_type=log.access_type,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            accessed_at=log.accessed_at
        )
        for log in logs
    ]
    
    return SecretAccessLogListResponse(
        logs=log_responses,
        total=total,
        page=page,
        page_size=page_size
    )


# ============================================================================
# Statistics Endpoint
# ============================================================================

@router.get("/statistics", response_model=SecretStatistics)
async def get_vault_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("vault.audit"))
):
    """
    Get vault statistics.
    Requires 'vault.audit' permission.
    """
    # Total secrets
    total_result = await db.execute(
        select(func.count()).select_from(Secret)
    )
    total_secrets = total_result.scalar()
    
    # Active secrets
    active_result = await db.execute(
        select(func.count()).select_from(Secret)
        .where(Secret.is_active == True)
    )
    active_secrets = active_result.scalar()
    
    # Expired secrets
    expired_result = await db.execute(
        select(func.count()).select_from(Secret)
        .where(and_(
            Secret.expires_at.is_not(None),
            Secret.expires_at <= datetime.utcnow()
        ))
    )
    expired_secrets = expired_result.scalar()
    
    # Secrets by type
    type_result = await db.execute(
        select(Secret.secret_type, func.count().label('count'))
        .group_by(Secret.secret_type)
    )
    secrets_by_type = {row.secret_type.value: row.count for row in type_result}
    
    # Recent accesses (last 24h)
    recent_result = await db.execute(
        select(func.count()).select_from(SecretAccessLog)
        .where(SecretAccessLog.accessed_at >= datetime.utcnow() - timedelta(hours=24))
    )
    recent_accesses = recent_result.scalar()
    
    # Secrets expiring soon (next 30 days)
    expiring_result = await db.execute(
        select(func.count()).select_from(Secret)
        .where(and_(
            Secret.expires_at.is_not(None),
            Secret.expires_at > datetime.utcnow(),
            Secret.expires_at <= datetime.utcnow() + timedelta(days=30)
        ))
    )
    secrets_expiring_soon = expiring_result.scalar()
    
    # Never accessed
    never_accessed_result = await db.execute(
        select(func.count()).select_from(Secret)
        .where(Secret.last_accessed_at.is_(None))
    )
    never_accessed = never_accessed_result.scalar()
    
    # Most accessed secrets
    most_accessed_result = await db.execute(
        select(Secret.id, Secret.name, Secret.access_count)
        .order_by(desc(Secret.access_count))
        .limit(10)
    )
    most_accessed = [
        {
            "secret_id": row.id,
            "secret_name": row.name,
            "access_count": row.access_count
        }
        for row in most_accessed_result
    ]
    
    return SecretStatistics(
        total_secrets=total_secrets,
        active_secrets=active_secrets,
        expired_secrets=expired_secrets,
        secrets_by_type=secrets_by_type,
        recent_accesses=recent_accesses,
        secrets_expiring_soon=secrets_expiring_soon,
        never_accessed=never_accessed,
        most_accessed=most_accessed
    )