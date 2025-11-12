"""
Audit logging Pydantic schemas for request/response validation.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict

from app.models.audit import AuditAction


# Audit Log Schemas
class AuditLogCreate(BaseModel):
    """Schema for creating an audit log entry"""
    action: AuditAction
    resource_type: str = Field(..., max_length=100)
    resource_id: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = Field(None, max_length=45)
    user_agent: Optional[str] = None


class AuditLogResponse(BaseModel):
    """Schema for audit log response"""
    id: int
    user_id: Optional[int]
    username: Optional[str]
    action: AuditAction
    resource_type: str
    resource_id: Optional[int]
    details: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    user_agent: Optional[str]
    session_id: Optional[int]
    tool_execution_id: Optional[int]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(BaseModel):
    """Schema for paginated audit log list"""
    logs: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
    
    model_config = ConfigDict(from_attributes=True)


class AuditLogFilterParams(BaseModel):
    """Schema for audit log filtering"""
    user_id: Optional[int] = None
    action: Optional[AuditAction] = None
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    ip_address: Optional[str] = None


# System Metrics Schemas
class SystemMetricCreate(BaseModel):
    """Schema for creating a system metric"""
    metric_name: str = Field(..., max_length=100)
    metric_value: float
    metric_type: str = Field(default="gauge", max_length=50)
    tags: Optional[Dict[str, Any]] = None


class SystemMetricResponse(BaseModel):
    """Schema for system metric response"""
    id: int
    metric_name: str
    metric_value: float
    metric_type: str
    tags: Optional[Dict[str, Any]]
    recorded_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class SystemMetricListResponse(BaseModel):
    """Schema for paginated system metrics list"""
    metrics: List[SystemMetricResponse]
    total: int
    page: int
    page_size: int
    
    model_config = ConfigDict(from_attributes=True)


# Statistics Schemas
class AuditStatistics(BaseModel):
    """Schema for audit statistics"""
    total_events: int
    events_by_action: Dict[str, int]
    events_by_resource: Dict[str, int]
    unique_users: int
    unique_ips: int
    events_last_24h: int
    events_last_7d: int
    events_last_30d: int
    top_users: List[Dict[str, Any]]
    recent_failures: int


class SystemHealthMetrics(BaseModel):
    """Schema for system health metrics"""
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    disk_usage: Optional[float] = None
    active_sessions: int
    active_executions: int
    cache_hit_rate: Optional[float] = None
    avg_response_time: Optional[float] = None
    error_rate: Optional[float] = None
    uptime_seconds: int