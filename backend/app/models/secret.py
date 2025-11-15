"""Secrets vault models for secure credential management."""
from datetime import datetime
from typing import Optional
import logging

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Boolean, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base
from app.core.crypto import encrypt_value, decrypt_value
from app.config import settings

logger = logging.getLogger(__name__)


class SecretType(str, enum.Enum):
    """Secret type enum."""
    API_KEY = "api_key"
    PASSWORD = "password"
    TOKEN = "token"
    CERTIFICATE = "certificate"
    SSH_KEY = "ssh_key"
    DATABASE_CREDENTIALS = "database_credentials"
    OTHER = "other"


class Secret(Base):
    """Secrets vault model for storing encrypted credentials."""
    
    __tablename__ = "secrets"

    id = Column(Integer, primary_key=True, index=True)
    
    # Secret identification
    name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    secret_type = Column(SQLEnum(SecretType), nullable=False, index=True)
    
    # Encrypted data (encrypted at rest)
    encrypted_value = Column(Text, nullable=False)
    encryption_key_id = Column(String(100), nullable=False)  # KMS key ID
    
    # Metadata
    meta_data = Column(JSON, nullable=True)  # Additional secret metadata
    tags = Column(JSON, nullable=True)  # Tags for organization
    
    # Access control
    owner_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    required_permission = Column(String(100))  # Permission required to access
    
    # Secret status
    is_active = Column(Boolean, default=True, nullable=False)
    is_rotatable = Column(Boolean, default=True, nullable=False)
    
    # Rotation settings
    rotation_enabled = Column(Boolean, default=False, nullable=False)
    rotation_days = Column(Integer, nullable=True)  # Auto-rotate every N days
    last_rotated = Column(DateTime, nullable=True)
    next_rotation = Column(DateTime, nullable=True)
    
    # Expiration
    expires_at = Column(DateTime, nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_accessed = Column(DateTime, nullable=True)
    
    # Relationships
    owner = relationship("User")
    access_logs = relationship("SecretAccessLog", back_populates="secret", cascade="all, delete-orphan")
    versions = relationship("SecretVersion", back_populates="secret", cascade="all, delete-orphan", order_by="SecretVersion.version_number.desc()")
    
    def __repr__(self) -> str:
        return f"<Secret(id={self.id}, name={self.name}, type={self.secret_type})>"
    
    @property
    def value(self) -> str:
        """
        Decrypt and return secret value.
        
        Returns:
            str: Decrypted secret value
            
        Raises:
            ValueError: If decryption fails
        """
        if not self.encrypted_value:
            return None
        try:
            return decrypt_value(self.encrypted_value, settings.ENCRYPTION_KEY)
        except Exception as e:
            logger.error(f"Failed to decrypt secret {self.id}: {e}")
            raise ValueError("Failed to decrypt secret value")
    
    @value.setter
    def value(self, plaintext: str):
        """
        Encrypt and store secret value.
        
        Args:
            plaintext: Plaintext value to encrypt and store
        """
        if plaintext:
            self.encrypted_value = encrypt_value(plaintext, settings.ENCRYPTION_KEY)
            self.encryption_key_id = "fernet_v1"  # Track encryption version
    
    @property
    def is_expired(self) -> bool:
        """Check if secret has expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    @property
    def needs_rotation(self) -> bool:
        """Check if secret needs rotation."""
        if not self.rotation_enabled or not self.next_rotation:
            return False
        return datetime.utcnow() >= self.next_rotation


class SecretVersion(Base):
    """Secret version history for rotation and rollback."""
    
    __tablename__ = "secret_versions"

    id = Column(Integer, primary_key=True, index=True)
    secret_id = Column(Integer, ForeignKey('secrets.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Version details
    version_number = Column(Integer, nullable=False)
    encrypted_value = Column(Text, nullable=False)
    encryption_key_id = Column(String(100), nullable=False)
    
    # Version metadata
    created_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    rotation_reason = Column(String(255), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=False, nullable=False)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    secret = relationship("Secret", back_populates="versions")
    creator = relationship("User")
    
    def __repr__(self) -> str:
        return f"<SecretVersion(id={self.id}, secret_id={self.secret_id}, version={self.version_number})>"


class SecretAccessLog(Base):
    """Log of secret access for audit compliance."""
    
    __tablename__ = "secret_access_logs"

    id = Column(Integer, primary_key=True, index=True)
    secret_id = Column(Integer, ForeignKey('secrets.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # Access details
    access_type = Column(String(20), nullable=False, index=True)  # read, write, delete
    success = Column(Boolean, nullable=False, index=True)
    
    # Context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    tool_id = Column(Integer, ForeignKey('tools.id', ondelete='SET NULL'), nullable=True)  # If accessed by a tool
    
    # Timestamp
    accessed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    secret = relationship("Secret", back_populates="access_logs")
    user = relationship("User")
    tool = relationship("Tool")
    
    def __repr__(self) -> str:
        return f"<SecretAccessLog(id={self.id}, secret_id={self.secret_id}, type={self.access_type})>"