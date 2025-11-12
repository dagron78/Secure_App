"""
Tool execution API endpoints.
Handles tool registration, execution, approvals, and caching.
"""
from datetime import datetime, timedelta
from typing import List, Optional
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    get_current_user,
    require_permission,
    get_db
)
from app.models.user import User
from app.models.tool import (
    Tool, 
    ToolExecution, 
    ToolApproval, 
    ToolCache,
    ExecutionStatus,
    ApprovalStatus,
    ToolStatus
)
from app.models.chat import ChatSession
from app.schemas.tool import (
    ToolCreate,
    ToolUpdate,
    ToolResponse,
    ToolListResponse,
    ToolExecutionCreate,
    ToolExecutionUpdate,
    ToolExecutionResponse,
    ToolExecutionListResponse,
    ToolApprovalCreate,
    ToolApprovalUpdate,
    ToolApprovalResponse,
    ToolApprovalListResponse,
    ToolCacheResponse,
    ToolStatistics,
    SystemToolStatistics
)

router = APIRouter(prefix="/tools", tags=["tools"])


# ============================================================================
# Tool Management Endpoints
# ============================================================================

@router.post("/", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
async def create_tool(
    tool_data: ToolCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("tools.create"))
):
    """
    Create a new tool.
    Requires 'tools.create' permission.
    """
    # Check if tool with same name exists
    result = await db.execute(
        select(Tool).where(Tool.name == tool_data.name)
    )
    existing_tool = result.scalar_one_or_none()
    
    if existing_tool:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tool with name '{tool_data.name}' already exists"
        )
    
    # Create tool
    tool = Tool(
        **tool_data.model_dump(),
        created_by=current_user.id
    )
    
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    
    return tool


@router.get("/", response_model=ToolListResponse)
async def list_tools(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    status_filter: Optional[ToolStatus] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search in name/description"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all tools with pagination and filtering.
    """
    # Build query
    query = select(Tool)
    
    # Apply filters
    filters = []
    if status_filter:
        filters.append(Tool.status == status_filter)
    if category:
        filters.append(Tool.category == category)
    if search:
        search_term = f"%{search}%"
        filters.append(
            or_(
                Tool.name.ilike(search_term),
                Tool.description.ilike(search_term)
            )
        )
    
    if filters:
        query = query.where(and_(*filters))
    
    # Get total count
    count_query = select(func.count()).select_from(Tool)
    if filters:
        count_query = count_query.where(and_(*filters))
    result = await db.execute(count_query)
    total = result.scalar()
    
    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(Tool.name)
    
    result = await db.execute(query)
    tools = result.scalars().all()
    
    return ToolListResponse(
        tools=tools,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific tool by ID.
    """
    result = await db.execute(
        select(Tool).where(Tool.id == tool_id)
    )
    tool = result.scalar_one_or_none()
    
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with ID {tool_id} not found"
        )
    
    return tool


@router.put("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: int,
    tool_data: ToolUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("tools.update"))
):
    """
    Update a tool.
    Requires 'tools.update' permission.
    """
    result = await db.execute(
        select(Tool).where(Tool.id == tool_id)
    )
    tool = result.scalar_one_or_none()
    
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with ID {tool_id} not found"
        )
    
    # Update fields
    update_data = tool_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tool, field, value)
    
    tool.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(tool)
    
    return tool


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("tools.delete"))
):
    """
    Delete a tool (soft delete by setting status to inactive).
    Requires 'tools.delete' permission.
    """
    result = await db.execute(
        select(Tool).where(Tool.id == tool_id)
    )
    tool = result.scalar_one_or_none()
    
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with ID {tool_id} not found"
        )
    
    # Soft delete
    tool.status = ToolStatus.INACTIVE
    tool.updated_at = datetime.utcnow()
    
    await db.commit()


# ============================================================================
# Tool Execution Endpoints
# ============================================================================

def _generate_cache_key(tool_id: int, input_data: dict) -> str:
    """Generate a cache key from tool ID and input data."""
    input_str = json.dumps(input_data, sort_keys=True)
    input_hash = hashlib.sha256(input_str.encode()).hexdigest()
    return f"tool:{tool_id}:{input_hash}"


async def _check_cache(
    db: AsyncSession,
    tool_id: int,
    input_data: dict
) -> Optional[ToolCache]:
    """Check if a cached result exists for this tool execution."""
    cache_key = _generate_cache_key(tool_id, input_data)
    
    result = await db.execute(
        select(ToolCache).where(
            and_(
                ToolCache.cache_key == cache_key,
                or_(
                    ToolCache.expires_at.is_(None),
                    ToolCache.expires_at > datetime.utcnow()
                )
            )
        )
    )
    cache = result.scalar_one_or_none()
    
    if cache:
        # Update hit count
        cache.hit_count += 1
        cache.last_hit_at = datetime.utcnow()
        await db.commit()
    
    return cache


async def _execute_tool(
    execution: ToolExecution,
    tool: Tool,
    db: AsyncSession
):
    """
    Execute a tool (background task).
    This is a placeholder - actual execution would integrate with tool runners.
    """
    try:
        execution.status = ExecutionStatus.RUNNING
        execution.started_at = datetime.utcnow()
        await db.commit()
        
        # TODO: Integrate with actual tool execution framework
        # For now, simulate execution
        import asyncio
        await asyncio.sleep(1)
        
        # Mock successful execution
        execution.status = ExecutionStatus.COMPLETED
        execution.completed_at = datetime.utcnow()
        execution.execution_time = (
            execution.completed_at - execution.started_at
        ).total_seconds()
        execution.output_data = {
            "result": "Tool executed successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Update tool statistics
        tool.execution_count += 1
        tool.success_count += 1
        
        # Calculate average execution time
        if tool.avg_execution_time:
            tool.avg_execution_time = (
                (tool.avg_execution_time * (tool.execution_count - 1) + 
                 execution.execution_time) / tool.execution_count
            )
        else:
            tool.avg_execution_time = execution.execution_time
        
        tool.last_executed_at = datetime.utcnow()
        
        # Cache the result
        input_str = json.dumps(execution.input_data, sort_keys=True)
        input_hash = hashlib.sha256(input_str.encode()).hexdigest()
        cache_key = _generate_cache_key(tool.id, execution.input_data)
        
        cache = ToolCache(
            tool_id=tool.id,
            cache_key=cache_key,
            input_hash=input_hash,
            output_data=execution.output_data,
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        db.add(cache)
        
        await db.commit()
        
    except Exception as e:
        execution.status = ExecutionStatus.FAILED
        execution.error_message = str(e)
        execution.completed_at = datetime.utcnow()
        
        tool.execution_count += 1
        tool.failure_count += 1
        
        await db.commit()


@router.post("/execute", response_model=ToolExecutionResponse, status_code=status.HTTP_201_CREATED)
async def execute_tool(
    execution_data: ToolExecutionCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Execute a tool.
    If tool requires approval, creates a pending approval request.
    Otherwise, executes immediately.
    """
    # Get tool
    result = await db.execute(
        select(Tool).where(Tool.id == execution_data.tool_id)
    )
    tool = result.scalar_one_or_none()
    
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with ID {execution_data.tool_id} not found"
        )
    
    if tool.status != ToolStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tool '{tool.name}' is not active"
        )
    
    # Check cache first
    cache = await _check_cache(db, tool.id, execution_data.input_data)
    if cache:
        # Return cached result
        execution = ToolExecution(
            tool_id=tool.id,
            user_id=current_user.id,
            session_id=execution_data.session_id,
            status=ExecutionStatus.COMPLETED,
            input_data=execution_data.input_data,
            output_data=cache.output_data,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            execution_time=0.0,
            requires_approval=False
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)
        
        return ToolExecutionResponse(
            id=execution.id,
            tool_id=execution.tool_id,
            tool_name=tool.name,
            user_id=execution.user_id,
            session_id=execution.session_id,
            status=execution.status,
            input_data=execution.input_data,
            output_data=execution.output_data,
            error_message=execution.error_message,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            execution_time=execution.execution_time,
            retry_count=execution.retry_count,
            requires_approval=execution.requires_approval,
            approval_id=execution.approval_id,
            created_at=execution.created_at
        )
    
    # Create execution record
    execution = ToolExecution(
        tool_id=tool.id,
        user_id=current_user.id,
        session_id=execution_data.session_id,
        status=ExecutionStatus.PENDING,
        input_data=execution_data.input_data,
        requires_approval=tool.requires_approval
    )
    
    db.add(execution)
    await db.commit()
    await db.refresh(execution)
    
    # If requires approval, create approval request
    if tool.requires_approval:
        approval = ToolApproval(
            execution_id=execution.id,
            requested_by=current_user.id,
            status=ApprovalStatus.PENDING,
            reason=execution_data.approval_reason,
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        db.add(approval)
        await db.commit()
        await db.refresh(approval)
        
        execution.approval_id = approval.id
        await db.commit()
    else:
        # Execute immediately in background
        background_tasks.add_task(_execute_tool, execution, tool, db)
    
    await db.refresh(execution)
    
    return ToolExecutionResponse(
        id=execution.id,
        tool_id=execution.tool_id,
        tool_name=tool.name,
        user_id=execution.user_id,
        session_id=execution.session_id,
        status=execution.status,
        input_data=execution.input_data,
        output_data=execution.output_data,
        error_message=execution.error_message,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        execution_time=execution.execution_time,
        retry_count=execution.retry_count,
        requires_approval=execution.requires_approval,
        approval_id=execution.approval_id,
        created_at=execution.created_at
    )


@router.get("/executions/", response_model=ToolExecutionListResponse)
async def list_executions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    tool_id: Optional[int] = Query(None),
    session_id: Optional[int] = Query(None),
    status_filter: Optional[ExecutionStatus] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List tool executions with filtering.
    Users can see their own executions, admins can see all.
    """
    # Build query
    query = select(ToolExecution)
    
    # Apply filters
    filters = [ToolExecution.user_id == current_user.id]
    
    # Admins can see all executions
    if await current_user.is_superuser():
        filters = []
    
    if tool_id:
        filters.append(ToolExecution.tool_id == tool_id)
    if session_id:
        filters.append(ToolExecution.session_id == session_id)
    if status_filter:
        filters.append(ToolExecution.status == status_filter)
    
    if filters:
        query = query.where(and_(*filters))
    
    # Get total count
    count_query = select(func.count()).select_from(ToolExecution)
    if filters:
        count_query = count_query.where(and_(*filters))
    result = await db.execute(count_query)
    total = result.scalar()
    
    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(desc(ToolExecution.created_at))
    
    result = await db.execute(query)
    executions = result.scalars().all()
    
    # Get tool names
    tool_ids = [e.tool_id for e in executions]
    tools_result = await db.execute(
        select(Tool).where(Tool.id.in_(tool_ids))
    )
    tools = {t.id: t.name for t in tools_result.scalars().all()}
    
    execution_responses = [
        ToolExecutionResponse(
            id=e.id,
            tool_id=e.tool_id,
            tool_name=tools.get(e.tool_id, "Unknown"),
            user_id=e.user_id,
            session_id=e.session_id,
            status=e.status,
            input_data=e.input_data,
            output_data=e.output_data,
            error_message=e.error_message,
            started_at=e.started_at,
            completed_at=e.completed_at,
            execution_time=e.execution_time,
            retry_count=e.retry_count,
            requires_approval=e.requires_approval,
            approval_id=e.approval_id,
            created_at=e.created_at
        )
        for e in executions
    ]
    
    return ToolExecutionListResponse(
        executions=execution_responses,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/executions/{execution_id}", response_model=ToolExecutionResponse)
async def get_execution(
    execution_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific tool execution.
    """
    result = await db.execute(
        select(ToolExecution).where(ToolExecution.id == execution_id)
    )
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution with ID {execution_id} not found"
        )
    
    # Check access
    if execution.user_id != current_user.id and not await current_user.is_superuser():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this execution"
        )
    
    # Get tool name
    tool_result = await db.execute(
        select(Tool).where(Tool.id == execution.tool_id)
    )
    tool = tool_result.scalar_one_or_none()
    
    return ToolExecutionResponse(
        id=execution.id,
        tool_id=execution.tool_id,
        tool_name=tool.name if tool else "Unknown",
        user_id=execution.user_id,
        session_id=execution.session_id,
        status=execution.status,
        input_data=execution.input_data,
        output_data=execution.output_data,
        error_message=execution.error_message,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        execution_time=execution.execution_time,
        retry_count=execution.retry_count,
        requires_approval=execution.requires_approval,
        approval_id=execution.approval_id,
        created_at=execution.created_at
    )


# ============================================================================
# Tool Approval Endpoints
# ============================================================================

@router.get("/approvals/", response_model=ToolApprovalListResponse)
async def list_approvals(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status_filter: Optional[ApprovalStatus] = Query(None),
    pending_only: bool = Query(False, description="Show only pending approvals"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("tools.approve"))
):
    """
    List tool approval requests.
    Requires 'tools.approve' permission.
    """
    # Build query
    query = select(ToolApproval)
    
    filters = []
    if status_filter:
        filters.append(ToolApproval.status == status_filter)
    if pending_only:
        filters.append(ToolApproval.status == ApprovalStatus.PENDING)
    
    if filters:
        query = query.where(and_(*filters))
    
    # Get total count
    count_query = select(func.count()).select_from(ToolApproval)
    if filters:
        count_query = count_query.where(and_(*filters))
    result = await db.execute(count_query)
    total = result.scalar()
    
    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(desc(ToolApproval.requested_at))
    
    result = await db.execute(query)
    approvals = result.scalars().all()
    
    # Get related data
    execution_ids = [a.execution_id for a in approvals]
    executions_result = await db.execute(
        select(ToolExecution).where(ToolExecution.id.in_(execution_ids))
    )
    executions = {e.id: e for e in executions_result.scalars().all()}
    
    tool_ids = [e.tool_id for e in executions.values()]
    tools_result = await db.execute(
        select(Tool).where(Tool.id.in_(tool_ids))
    )
    tools = {t.id: t.name for t in tools_result.scalars().all()}
    
    user_ids = [a.requested_by for a in approvals]
    if any(a.approved_by for a in approvals):
        user_ids.extend([a.approved_by for a in approvals if a.approved_by])
    users_result = await db.execute(
        select(User).where(User.id.in_(user_ids))
    )
    users = {u.id: u.username for u in users_result.scalars().all()}
    
    approval_responses = [
        ToolApprovalResponse(
            id=a.id,
            execution_id=a.execution_id,
            tool_name=tools.get(executions[a.execution_id].tool_id, "Unknown"),
            requester_id=a.requested_by,
            requester_name=users.get(a.requested_by, "Unknown"),
            approver_id=a.approved_by,
            approver_name=users.get(a.approved_by) if a.approved_by else None,
            status=a.status,
            reason=a.reason,
            notes=a.notes,
            requested_at=a.requested_at,
            responded_at=a.responded_at,
            expires_at=a.expires_at
        )
        for a in approvals
    ]
    
    return ToolApprovalListResponse(
        approvals=approval_responses,
        total=total,
        page=page,
        page_size=page_size
    )


@router.put("/approvals/{approval_id}", response_model=ToolApprovalResponse)
async def update_approval(
    approval_id: int,
    approval_data: ToolApprovalUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("tools.approve"))
):
    """
    Approve or reject a tool execution request.
    Requires 'tools.approve' permission.
    """
    result = await db.execute(
        select(ToolApproval).where(ToolApproval.id == approval_id)
    )
    approval = result.scalar_one_or_none()
    
    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval with ID {approval_id} not found"
        )
    
    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approval is already {approval.status.value}"
        )
    
    # Update approval
    approval.status = approval_data.status
    approval.notes = approval_data.notes
    approval.approved_by = current_user.id
    approval.responded_at = datetime.utcnow()
    
    # Get execution
    exec_result = await db.execute(
        select(ToolExecution).where(ToolExecution.id == approval.execution_id)
    )
    execution = exec_result.scalar_one()
    
    if approval_data.status == ApprovalStatus.APPROVED:
        # Execute tool in background
        execution.status = ExecutionStatus.APPROVED
        
        tool_result = await db.execute(
            select(Tool).where(Tool.id == execution.tool_id)
        )
        tool = tool_result.scalar_one()
        
        background_tasks.add_task(_execute_tool, execution, tool, db)
    else:
        # Reject execution
        execution.status = ExecutionStatus.REJECTED
        execution.completed_at = datetime.utcnow()
        execution.error_message = f"Execution rejected by {current_user.username}"
    
    await db.commit()
    await db.refresh(approval)
    
    # Get related data for response
    user_result = await db.execute(
        select(User).where(User.id == approval.requested_by)
    )
    requester = user_result.scalar_one()
    
    tool_result = await db.execute(
        select(Tool).where(Tool.id == execution.tool_id)
    )
    tool = tool_result.scalar_one()
    
    return ToolApprovalResponse(
        id=approval.id,
        execution_id=approval.execution_id,
        tool_name=tool.name,
        requester_id=approval.requested_by,
        requester_name=requester.username,
        approver_id=approval.approved_by,
        approver_name=current_user.username,
        status=approval.status,
        reason=approval.reason,
        notes=approval.notes,
        requested_at=approval.requested_at,
        responded_at=approval.responded_at,
        expires_at=approval.expires_at
    )


# ============================================================================
# Tool Statistics Endpoints
# ============================================================================

@router.get("/statistics/system", response_model=SystemToolStatistics)
async def get_system_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("tools.view_stats"))
):
    """
    Get system-wide tool statistics.
    Requires 'tools.view_stats' permission.
    """
    # Get total tools
    total_tools_result = await db.execute(select(func.count()).select_from(Tool))
    total_tools = total_tools_result.scalar()
    
    # Get active tools
    active_tools_result = await db.execute(
        select(func.count()).select_from(Tool).where(Tool.status == ToolStatus.ACTIVE)
    )
    active_tools = active_tools_result.scalar()
    
    # Get total executions
    total_exec_result = await db.execute(
        select(func.count()).select_from(ToolExecution)
    )
    total_executions = total_exec_result.scalar()
    
    # Get pending approvals
    pending_approvals_result = await db.execute(
        select(func.count()).select_from(ToolApproval)
        .where(ToolApproval.status == ApprovalStatus.PENDING)
    )
    pending_approvals = pending_approvals_result.scalar()
    
    # Get success rate
    completed_result = await db.execute(
        select(func.count()).select_from(ToolExecution)
        .where(ToolExecution.status == ExecutionStatus.COMPLETED)
    )
    completed_count = completed_result.scalar()
    
    success_rate = (completed_count / total_executions * 100) if total_executions > 0 else 0
    
    # Get average execution time
    avg_time_result = await db.execute(
        select(func.avg(ToolExecution.execution_time))
        .where(ToolExecution.execution_time.is_not(None))
    )
    avg_time = avg_time_result.scalar() or 0.0
    
    # Get top tools
    top_tools_result = await db.execute(
        select(Tool).order_by(desc(Tool.execution_count)).limit(10)
    )
    top_tools = top_tools_result.scalars().all()
    
    top_tool_stats = [
        ToolStatistics(
            tool_id=tool.id,
            tool_name=tool.name,
            total_executions=tool.execution_count,
            successful_executions=tool.success_count,
            failed_executions=tool.failure_count,
            avg_execution_time=tool.avg_execution_time or 0.0,
            success_rate=(tool.success_count / tool.execution_count * 100) 
                if tool.execution_count > 0 else 0,
            last_executed=tool.last_executed_at
        )
        for tool in top_tools
    ]
    
    return SystemToolStatistics(
        total_tools=total_tools,
        active_tools=active_tools,
        total_executions=total_executions,
        pending_approvals=pending_approvals,
        execution_success_rate=success_rate,
        avg_execution_time=avg_time,
        top_tools=top_tool_stats
    )


@router.get("/statistics/{tool_id}", response_model=ToolStatistics)
async def get_tool_statistics(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get statistics for a specific tool.
    """
    result = await db.execute(
        select(Tool).where(Tool.id == tool_id)
    )
    tool = result.scalar_one_or_none()
    
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with ID {tool_id} not found"
        )
    
    success_rate = (
        (tool.success_count / tool.execution_count * 100) 
        if tool.execution_count > 0 
        else 0
    )
    
    return ToolStatistics(
        tool_id=tool.id,
        tool_name=tool.name,
        total_executions=tool.execution_count,
        successful_executions=tool.success_count,
        failed_executions=tool.failure_count,
        avg_execution_time=tool.avg_execution_time or 0.0,
        success_rate=success_rate,
        last_executed=tool.last_executed_at
    )