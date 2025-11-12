"""
Audit logging API endpoints.
Handles audit log queries, system metrics, and statistics.
"""
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    get_current_user,
    get_optional_user,
    require_permission,
    get_db
)
from app.models.user import User
from app.models.audit import AuditLog, AuditAction, SystemMetric
from app.models.tool import ToolExecution
from app.models.chat import ChatSession
from app.schemas.audit import (
    AuditLogCreate,
    AuditLogResponse,
    AuditLogListResponse,
    AuditLogFilterParams,
    SystemMetricCreate,
    SystemMetricResponse,
    SystemMetricListResponse,
    AuditStatistics,
    SystemHealthMetrics
)

router = APIRouter(prefix="/audit", tags=["audit"])


# ============================================================================
# Audit Log Management
# ============================================================================

async def create_audit_log(
    db: AsyncSession,
    user_id: Optional[int],
    action: AuditAction,
    resource_type: str,
    resource_id: Optional[int] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_id: Optional[int] = None,
    tool_execution_id: Optional[int] = None
):
    """
    Helper function to create audit log entries.
    Can be called from other parts of the application.
    """
    log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
        session_id=session_id,
        tool_execution_id=tool_execution_id
    )
    
    db.add(log)
    await db.commit()
    await db.refresh(log)
    
    return log


@router.post("/logs", response_model=AuditLogResponse, status_code=status.HTTP_201_CREATED)
async def create_audit_log_entry(
    log_data: AuditLogCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_user)
):
    """
    Create a new audit log entry.
    Can be used by authenticated users or system processes.
    """
    # Get IP address from request
    ip_address = log_data.ip_address or request.client.host if request.client else None
    user_agent = log_data.user_agent or request.headers.get("user-agent")
    
    log = await create_audit_log(
        db=db,
        user_id=current_user.id if current_user else None,
        action=log_data.action,
        resource_type=log_data.resource_type,
        resource_id=log_data.resource_id,
        details=log_data.details,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    # Get username if available
    username = current_user.username if current_user else None
    
    return AuditLogResponse(
        id=log.id,
        user_id=log.user_id,
        username=username,
        action=log.action,
        resource_type=log.resource_type,
        resource_id=log.resource_id,
        details=log.details,
        ip_address=log.ip_address,
        user_agent=log.user_agent,
        session_id=log.session_id,
        tool_execution_id=log.tool_execution_id,
        created_at=log.created_at
    )


@router.get("/logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user_id: Optional[int] = Query(None),
    action: Optional[AuditAction] = Query(None),
    resource_type: Optional[str] = Query(None),
    resource_id: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    search: Optional[str] = Query(None, description="Search in details"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("audit.view"))
):
    """
    List audit logs with filtering and pagination.
    Requires 'audit.view' permission.
    """
    # Build query
    query = select(AuditLog)
    
    # Apply filters
    filters = []
    if user_id:
        filters.append(AuditLog.user_id == user_id)
    if action:
        filters.append(AuditLog.action == action)
    if resource_type:
        filters.append(AuditLog.resource_type == resource_type)
    if resource_id:
        filters.append(AuditLog.resource_id == resource_id)
    if start_date:
        filters.append(AuditLog.created_at >= start_date)
    if end_date:
        filters.append(AuditLog.created_at <= end_date)
    
    if filters:
        query = query.where(and_(*filters))
    
    # Get total count
    count_query = select(func.count()).select_from(AuditLog)
    if filters:
        count_query = count_query.where(and_(*filters))
    result = await db.execute(count_query)
    total = result.scalar()
    
    # Apply pagination and ordering
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(desc(AuditLog.created_at))
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    # Get usernames
    user_ids = [log.user_id for log in logs if log.user_id]
    if user_ids:
        users_result = await db.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users = {u.id: u.username for u in users_result.scalars().all()}
    else:
        users = {}
    
    log_responses = [
        AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            username=users.get(log.user_id) if log.user_id else None,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details=log.details,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            session_id=log.session_id,
            tool_execution_id=log.tool_execution_id,
            created_at=log.created_at
        )
        for log in logs
    ]
    
    return AuditLogListResponse(
        logs=log_responses,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/logs/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("audit.view"))
):
    """
    Get a specific audit log entry.
    Requires 'audit.view' permission.
    """
    result = await db.execute(
        select(AuditLog).where(AuditLog.id == log_id)
    )
    log = result.scalar_one_or_none()
    
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit log with ID {log_id} not found"
        )
    
    # Get username
    username = None
    if log.user_id:
        user_result = await db.execute(
            select(User).where(User.id == log.user_id)
        )
        user = user_result.scalar_one_or_none()
        if user:
            username = user.username
    
    return AuditLogResponse(
        id=log.id,
        user_id=log.user_id,
        username=username,
        action=log.action,
        resource_type=log.resource_type,
        resource_id=log.resource_id,
        details=log.details,
        ip_address=log.ip_address,
        user_agent=log.user_agent,
        session_id=log.session_id,
        tool_execution_id=log.tool_execution_id,
        created_at=log.created_at
    )


# ============================================================================
# Audit Statistics
# ============================================================================

@router.get("/statistics", response_model=AuditStatistics)
async def get_audit_statistics(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("audit.view"))
):
    """
    Get audit statistics for the specified period.
    Requires 'audit.view' permission.
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Total events
    total_result = await db.execute(
        select(func.count()).select_from(AuditLog)
        .where(AuditLog.created_at >= start_date)
    )
    total_events = total_result.scalar()
    
    # Events by action
    action_result = await db.execute(
        select(
            AuditLog.action,
            func.count().label('count')
        )
        .where(AuditLog.created_at >= start_date)
        .group_by(AuditLog.action)
    )
    events_by_action = {row.action.value: row.count for row in action_result}
    
    # Events by resource type
    resource_result = await db.execute(
        select(
            AuditLog.resource_type,
            func.count().label('count')
        )
        .where(AuditLog.created_at >= start_date)
        .group_by(AuditLog.resource_type)
    )
    events_by_resource = {row.resource_type: row.count for row in resource_result}
    
    # Unique users
    users_result = await db.execute(
        select(func.count(func.distinct(AuditLog.user_id)))
        .where(and_(
            AuditLog.created_at >= start_date,
            AuditLog.user_id.is_not(None)
        ))
    )
    unique_users = users_result.scalar()
    
    # Unique IPs
    ips_result = await db.execute(
        select(func.count(func.distinct(AuditLog.ip_address)))
        .where(and_(
            AuditLog.created_at >= start_date,
            AuditLog.ip_address.is_not(None)
        ))
    )
    unique_ips = ips_result.scalar()
    
    # Events last 24h
    last_24h_result = await db.execute(
        select(func.count()).select_from(AuditLog)
        .where(AuditLog.created_at >= datetime.utcnow() - timedelta(hours=24))
    )
    events_last_24h = last_24h_result.scalar()
    
    # Events last 7d
    last_7d_result = await db.execute(
        select(func.count()).select_from(AuditLog)
        .where(AuditLog.created_at >= datetime.utcnow() - timedelta(days=7))
    )
    events_last_7d = last_7d_result.scalar()
    
    # Events last 30d
    last_30d_result = await db.execute(
        select(func.count()).select_from(AuditLog)
        .where(AuditLog.created_at >= datetime.utcnow() - timedelta(days=30))
    )
    events_last_30d = last_30d_result.scalar()
    
    # Top users
    top_users_result = await db.execute(
        select(
            User.id,
            User.username,
            func.count().label('event_count')
        )
        .join(AuditLog, AuditLog.user_id == User.id)
        .where(AuditLog.created_at >= start_date)
        .group_by(User.id, User.username)
        .order_by(desc('event_count'))
        .limit(10)
    )
    top_users = [
        {
            "user_id": row.id,
            "username": row.username,
            "event_count": row.event_count
        }
        for row in top_users_result
    ]
    
    # Recent failures (errors in last 24h)
    failures_result = await db.execute(
        select(func.count()).select_from(AuditLog)
        .where(and_(
            AuditLog.created_at >= datetime.utcnow() - timedelta(hours=24),
            or_(
                AuditLog.action == AuditAction.LOGIN_FAILED,
                AuditLog.action == AuditAction.PERMISSION_DENIED,
                AuditLog.action == AuditAction.TOOL_EXECUTION_FAILED
            )
        ))
    )
    recent_failures = failures_result.scalar()
    
    return AuditStatistics(
        total_events=total_events,
        events_by_action=events_by_action,
        events_by_resource=events_by_resource,
        unique_users=unique_users,
        unique_ips=unique_ips,
        events_last_24h=events_last_24h,
        events_last_7d=events_last_7d,
        events_last_30d=events_last_30d,
        top_users=top_users,
        recent_failures=recent_failures
    )


# ============================================================================
# System Metrics
# ============================================================================

@router.post("/metrics", response_model=SystemMetricResponse, status_code=status.HTTP_201_CREATED)
async def record_metric(
    metric_data: SystemMetricCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("metrics.record"))
):
    """
    Record a system metric.
    Requires 'metrics.record' permission.
    """
    metric = SystemMetric(
        metric_name=metric_data.metric_name,
        metric_value=metric_data.metric_value,
        metric_type=metric_data.metric_type,
        tags=metric_data.tags
    )
    
    db.add(metric)
    await db.commit()
    await db.refresh(metric)
    
    return SystemMetricResponse(
        id=metric.id,
        metric_name=metric.metric_name,
        metric_value=metric.metric_value,
        metric_type=metric.metric_type,
        tags=metric.tags,
        recorded_at=metric.recorded_at
    )


@router.get("/metrics", response_model=SystemMetricListResponse)
async def list_metrics(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    metric_name: Optional[str] = Query(None),
    metric_type: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("metrics.view"))
):
    """
    List system metrics with filtering.
    Requires 'metrics.view' permission.
    """
    # Build query
    query = select(SystemMetric)
    
    filters = []
    if metric_name:
        filters.append(SystemMetric.metric_name == metric_name)
    if metric_type:
        filters.append(SystemMetric.metric_type == metric_type)
    if start_date:
        filters.append(SystemMetric.recorded_at >= start_date)
    if end_date:
        filters.append(SystemMetric.recorded_at <= end_date)
    
    if filters:
        query = query.where(and_(*filters))
    
    # Get total count
    count_query = select(func.count()).select_from(SystemMetric)
    if filters:
        count_query = count_query.where(and_(*filters))
    result = await db.execute(count_query)
    total = result.scalar()
    
    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(desc(SystemMetric.recorded_at))
    
    result = await db.execute(query)
    metrics = result.scalars().all()
    
    metric_responses = [
        SystemMetricResponse(
            id=m.id,
            metric_name=m.metric_name,
            metric_value=m.metric_value,
            metric_type=m.metric_type,
            tags=m.tags,
            recorded_at=m.recorded_at
        )
        for m in metrics
    ]
    
    return SystemMetricListResponse(
        metrics=metric_responses,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/health", response_model=SystemHealthMetrics)
async def get_system_health(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get current system health metrics.
    Requires authentication.
    """
    # Active sessions (last 24h)
    sessions_result = await db.execute(
        select(func.count()).select_from(ChatSession)
        .where(ChatSession.last_activity >= datetime.utcnow() - timedelta(hours=24))
    )
    active_sessions = sessions_result.scalar()
    
    # Active executions (running or pending)
    from app.models.tool import ExecutionStatus
    executions_result = await db.execute(
        select(func.count()).select_from(ToolExecution)
        .where(or_(
            ToolExecution.status == ExecutionStatus.RUNNING,
            ToolExecution.status == ExecutionStatus.PENDING
        ))
    )
    active_executions = executions_result.scalar()
    
    # Get recent metrics
    cpu_metric = await db.execute(
        select(SystemMetric)
        .where(SystemMetric.metric_name == "cpu_usage")
        .order_by(desc(SystemMetric.recorded_at))
        .limit(1)
    )
    cpu = cpu_metric.scalar_one_or_none()
    
    memory_metric = await db.execute(
        select(SystemMetric)
        .where(SystemMetric.metric_name == "memory_usage")
        .order_by(desc(SystemMetric.recorded_at))
        .limit(1)
    )
    memory = memory_metric.scalar_one_or_none()
    
    disk_metric = await db.execute(
        select(SystemMetric)
        .where(SystemMetric.metric_name == "disk_usage")
        .order_by(desc(SystemMetric.recorded_at))
        .limit(1)
    )
    disk = disk_metric.scalar_one_or_none()
    
    # Calculate uptime (time since first audit log)
    first_log_result = await db.execute(
        select(AuditLog.created_at)
        .order_by(AuditLog.created_at)
        .limit(1)
    )
    first_log = first_log_result.scalar_one_or_none()
    uptime_seconds = 0
    if first_log:
        uptime_seconds = int((datetime.utcnow() - first_log).total_seconds())
    
    return SystemHealthMetrics(
        cpu_usage=cpu.metric_value if cpu else None,
        memory_usage=memory.metric_value if memory else None,
        disk_usage=disk.metric_value if disk else None,
        active_sessions=active_sessions,
        active_executions=active_executions,
        cache_hit_rate=None,  # TODO: Calculate from cache stats
        avg_response_time=None,  # TODO: Calculate from request logs
        error_rate=None,  # TODO: Calculate from error logs
        uptime_seconds=uptime_seconds
    )