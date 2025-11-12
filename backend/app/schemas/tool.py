"""
Tool-related Pydantic schemas for request/response validation.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


# Enums matching the database models
class ToolStatus(str, Enum):
    """Tool registration status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


class ExecutionStatus(str, Enum):
    """Tool execution status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalStatus(str, Enum):
    """Approval request status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


# Tool Schemas
class ToolBase(BaseModel):
    """Base tool schema"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    requires_approval: bool = False
    is_dangerous: bool = False
    timeout_seconds: Optional[int] = Field(default=300, ge=1, le=3600)
    max_retries: int = Field(default=3, ge=0, le=10)
    config: Optional[Dict[str, Any]] = None
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None


class ToolCreate(ToolBase):
    """Schema for creating a tool"""
    pass


class ToolUpdate(BaseModel):
    """Schema for updating a tool"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    requires_approval: Optional[bool] = None
    is_dangerous: Optional[bool] = None
    timeout_seconds: Optional[int] = Field(None, ge=1, le=3600)
    max_retries: Optional[int] = Field(None, ge=0, le=10)
    status: Optional[ToolStatus] = None
    config: Optional[Dict[str, Any]] = None
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None


class ToolResponse(ToolBase):
    """Schema for tool response"""
    id: int
    status: ToolStatus
    execution_count: int
    success_count: int
    failure_count: int
    avg_execution_time: Optional[float]
    last_executed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ToolListResponse(BaseModel):
    """Schema for paginated tool list"""
    tools: List[ToolResponse]
    total: int
    page: int
    page_size: int
    
    model_config = ConfigDict(from_attributes=True)


# Tool Execution Schemas
class ToolExecutionCreate(BaseModel):
    """Schema for creating a tool execution"""
    tool_id: int
    session_id: Optional[int] = None
    input_data: Dict[str, Any]
    approval_reason: Optional[str] = None


class ToolExecutionUpdate(BaseModel):
    """Schema for updating a tool execution"""
    status: Optional[ExecutionStatus] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class ToolExecutionResponse(BaseModel):
    """Schema for tool execution response"""
    id: int
    tool_id: int
    tool_name: str
    user_id: int
    session_id: Optional[int]
    status: ExecutionStatus
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    execution_time: Optional[float]
    retry_count: int
    requires_approval: bool
    approval_id: Optional[int]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ToolExecutionListResponse(BaseModel):
    """Schema for paginated tool execution list"""
    executions: List[ToolExecutionResponse]
    total: int
    page: int
    page_size: int
    
    model_config = ConfigDict(from_attributes=True)


# Tool Approval Schemas
class ToolApprovalCreate(BaseModel):
    """Schema for creating a tool approval request"""
    execution_id: int
    reason: Optional[str] = None


class ToolApprovalUpdate(BaseModel):
    """Schema for updating a tool approval"""
    status: ApprovalStatus
    notes: Optional[str] = None


class ToolApprovalResponse(BaseModel):
    """Schema for tool approval response"""
    id: int
    execution_id: int
    tool_name: str
    requester_id: int
    requester_name: str
    approver_id: Optional[int]
    approver_name: Optional[str]
    status: ApprovalStatus
    reason: Optional[str]
    notes: Optional[str]
    requested_at: datetime
    responded_at: Optional[datetime]
    expires_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class ToolApprovalListResponse(BaseModel):
    """Schema for paginated tool approval list"""
    approvals: List[ToolApprovalResponse]
    total: int
    page: int
    page_size: int
    
    model_config = ConfigDict(from_attributes=True)


# Tool Cache Schemas
class ToolCacheResponse(BaseModel):
    """Schema for tool cache entry response"""
    id: int
    tool_id: int
    tool_name: str
    cache_key: str
    input_hash: str
    output_data: Dict[str, Any]
    hit_count: int
    last_hit_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Tool Statistics Schemas
class ToolStatistics(BaseModel):
    """Schema for tool usage statistics"""
    tool_id: int
    tool_name: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    avg_execution_time: float
    success_rate: float
    last_executed: Optional[datetime]


class SystemToolStatistics(BaseModel):
    """Schema for system-wide tool statistics"""
    total_tools: int
    active_tools: int
    total_executions: int
    pending_approvals: int
    execution_success_rate: float
    avg_execution_time: float
    top_tools: List[ToolStatistics]