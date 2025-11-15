"""User authentication models."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Table, ForeignKey
from sqlalchemy.orm import relationship

from app.db.base import Base

# Association tables for many-to-many relationships
user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
)

role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
    Column('permission_id', Integer, ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True),
)


class User(Base):
    """User model for authentication and authorization."""
    
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    
    # Account status
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    roles = relationship("Role", secondary=user_roles, back_populates="users", lazy="select")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
    tool_approvals = relationship("ToolApproval", back_populates="user", foreign_keys="ToolApproval.requested_by", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    notification_preferences = relationship("NotificationPreference", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, username={self.username})>"
    
    @property
    def permissions(self) -> List[str]:
        """Get all permissions for this user from their roles."""
        perms = set()
        for role in self.roles:
            for perm in role.permissions:
                perms.add(perm.name)
        return list(perms)
    
    def has_permission(self, permission_name: str) -> bool:
        """Check if user has a specific permission."""
        if self.is_superuser:
            return True
        return permission_name in self.permissions
    
    def has_role(self, role_name: str) -> bool:
        """Check if user has a specific role."""
        if self.is_superuser:
            return True
        return any(role.name == role_name for role in self.roles)


class Role(Base):
    """Role model for RBAC."""
    
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(255))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    users = relationship("User", secondary=user_roles, back_populates="roles")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles", lazy="select")
    
    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name={self.name})>"


class Permission(Base):
    """Permission model for fine-grained access control."""
    
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(255))
    resource = Column(String(50), nullable=False, index=True)  # e.g., 'chat', 'tools', 'secrets'
    action = Column(String(50), nullable=False, index=True)     # e.g., 'read', 'write', 'execute', 'approve'
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")
    
    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, name={self.name}, resource={self.resource}, action={self.action})>"


class Session(Base):
    """User session model for tracking active sessions."""
    
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    token = Column(String(1024), unique=True, nullable=False, index=True)
    refresh_token = Column(String(1024), unique=True, nullable=True, index=True)
    
    # Session metadata
    ip_address = Column(String(45))  # IPv6 compatible
    user_agent = Column(String(500))
    
    # Session status
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_activity = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    def __repr__(self) -> str:
        return f"<Session(id={self.id}, user_id={self.user_id}, is_active={self.is_active})>"
    
    @property
    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.utcnow() > self.expires_at