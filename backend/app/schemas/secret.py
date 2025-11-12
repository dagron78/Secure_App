"""
Secrets vault Pydantic schemas for request/response validation.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict

from app.models.secret import SecretType


# Secret Schemas
class SecretCreate(BaseModel):
    """Schema for creating a secret"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    secret_type: SecretType
    value: str = Field(..., description="Secret value (will be encrypted)")
    tags: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None


class SecretUpdate(BaseModel):
    """Schema for updating a secret"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    value: Optional[str] = Field(None, description="New secret value")
    tags: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None
    is_active: Optional[bool] = None


class SecretResponse(BaseModel):
    """Schema for secret response (without value)"""
    id: int
    name: str
    description: Optional[str]
    secret_type: SecretType
    tags: Optional[Dict[str, Any]]
    is_active: bool
    is_expired: bool
    version: int
    expires_at: Optional[datetime]
    last_accessed_at: Optional[datetime]
    last_rotated_at: Optional[datetime]
    created_by: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class SecretValueResponse(BaseModel):
    """Schema for secret response with decrypted value"""
    id: int
    name: str
    description: Optional[str]
    secret_type: SecretType
    value: str  # Decrypted value
    tags: Optional[Dict[str, Any]]
    is_active: bool
    version: int
    expires_at: Optional[datetime]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class SecretListResponse(BaseModel):
    """Schema for paginated secret list"""
    secrets: List[SecretResponse]
    total: int
    page: int
    page_size: int
    
    model_config = ConfigDict(from_attributes=True)


# Secret Version Schemas
class SecretVersionResponse(BaseModel):
    """Schema for secret version response"""
    id: int
    secret_id: int
    version: int
    value_hash: str
    created_by: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class SecretVersionListResponse(BaseModel):
    """Schema for secret version list"""
    versions: List[SecretVersionResponse]
    total: int
    
    model_config = ConfigDict(from_attributes=True)


# Secret Access Log Schemas
class SecretAccessLogResponse(BaseModel):
    """Schema for secret access log response"""
    id: int
    secret_id: int
    secret_name: str
    user_id: int
    username: str
    access_type: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    accessed_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class SecretAccessLogListResponse(BaseModel):
    """Schema for secret access log list"""
    logs: List[SecretAccessLogResponse]
    total: int
    page: int
    page_size: int
    
    model_config = ConfigDict(from_attributes=True)


# Secret Rotation Schema
class SecretRotateRequest(BaseModel):
    """Schema for rotating a secret"""
    new_value: str = Field(..., description="New secret value")
    reason: Optional[str] = Field(None, description="Reason for rotation")


# Secret Statistics
class SecretStatistics(BaseModel):
    """Schema for secret statistics"""
    total_secrets: int
    active_secrets: int
    expired_secrets: int
    secrets_by_type: Dict[str, int]
    recent_accesses: int
    secrets_expiring_soon: int
    never_accessed: int
    most_accessed: List[Dict[str, Any]]