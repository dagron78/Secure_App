# CSDA Backend Security & Architecture Remediation Plan

**Document Version:** 1.0  
**Date:** 2025-11-15  
**Status:** Active  

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Critical Issues (Week 1)](#critical-issues-week-1)
3. [High Priority Issues (Weeks 2-3)](#high-priority-issues-weeks-2-3)
4. [Medium Priority Issues (Weeks 4-6)](#medium-priority-issues-weeks-4-6)
5. [Implementation Checklist](#implementation-checklist)
6. [Testing Requirements](#testing-requirements)
7. [Deployment Considerations](#deployment-considerations)

---

## Executive Summary

This document outlines the remediation plan for security, architecture, and code quality issues identified in the CSDA backend. Issues are prioritized by severity and business impact, with specific implementation guidance for each.

**Total Issues Identified:** 10  
**Critical:** 3  
**Medium:** 5  
**Minor:** 2  

**Estimated Timeline:** 6 weeks  
**Required Resources:** 2-3 backend engineers  

---

## Critical Issues (Week 1)

### 🔴 Issue #1: Missing Vault Encryption Implementation

**Priority:** P0 - Critical Security Vulnerability  
**Severity:** High  
**Location:** `app/models/secret.py`, `app/config.py`  
**Estimated Effort:** 3 days  

#### Problem Description
The secrets vault stores sensitive credentials in plaintext despite having an `encrypted_value` field. The `ENCRYPTION_KEY` in config is defined but never used. No encryption/decryption logic exists.

#### Impact
- All secrets stored in database are in plaintext
- Complete compromise if database is accessed
- Violates security compliance requirements (SOC 2, GDPR, HIPAA)

#### Solution

**File:** `app/models/secret.py`

```python
from cryptography.fernet import Fernet
from app.config import settings

class Secret(Base):
    # ... existing fields ...
    
    @property
    def value(self) -> str:
        """Decrypt and return secret value."""
        if not self.encrypted_value:
            return None
        try:
            f = Fernet(settings.ENCRYPTION_KEY.encode())
            return f.decrypt(self.encrypted_value.encode()).decode()
        except Exception as e:
            logger.error(f"Failed to decrypt secret {self.id}: {e}")
            raise ValueError("Failed to decrypt secret value")
    
    @value.setter
    def value(self, plaintext: str):
        """Encrypt and store secret value."""
        if plaintext:
            f = Fernet(settings.ENCRYPTION_KEY.encode())
            self.encrypted_value = f.encrypt(plaintext.encode()).decode()
            self.encryption_key_id = "fernet_v1"  # Track encryption version
```

**File:** `app/core/crypto.py` (new file)

```python
"""Cryptography utilities for secure data handling."""
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import base64
import os

def generate_encryption_key() -> str:
    """Generate a new Fernet encryption key."""
    return Fernet.generate_key().decode()

def derive_key_from_password(password: str, salt: bytes = None) -> tuple[str, bytes]:
    """Derive encryption key from password using PBKDF2."""
    if salt is None:
        salt = os.urandom(16)
    
    kdf = PBKDF2(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key.decode(), salt
```

#### Implementation Steps

1. **Add cryptography dependency**
   ```bash
   uv add cryptography
   ```

2. **Generate encryption key**
   ```python
   # In .env.example
   ENCRYPTION_KEY=<generate_with_Fernet.generate_key()>
   ```

3. **Update Secret model** with property getters/setters

4. **Create migration** to mark existing secrets as "needs_encryption"
   ```python
   # alembic/versions/xxx_encrypt_existing_secrets.py
   def upgrade():
       # Add is_encrypted column
       op.add_column('secrets', sa.Column('is_encrypted', sa.Boolean(), default=False))
       # Mark all existing as unencrypted
       op.execute("UPDATE secrets SET is_encrypted = false")
   ```

5. **Create data migration script** to encrypt existing secrets
   ```python
   # scripts/encrypt_existing_secrets.py
   # Fetch all unencrypted secrets, encrypt, update
   ```

6. **Update vault API endpoints** to handle encrypted values

7. **Add encryption key rotation capability**

#### Testing Requirements
- [ ] Unit tests for encrypt/decrypt functions
- [ ] Test with various secret types
- [ ] Test decryption failure handling
- [ ] Test key rotation scenario
- [ ] Load test with 10,000+ secrets

#### Rollout Plan
1. Deploy encryption code (reads both encrypted/unencrypted)
2. Run migration script to encrypt existing secrets
3. Enable encryption-only mode
4. Monitor logs for any decryption failures

---

### 🔴 Issue #2: Hardcoded Default Admin Password

**Priority:** P0 - Critical Security Vulnerability  
**Severity:** High  
**Location:** `scripts/seed_data.py:207`  
**Estimated Effort:** 1 day  

#### Problem Description
The seed script creates an admin user with hardcoded password `admin123`. This creates a known attack vector.

#### Impact
- Anyone with access to source code knows admin credentials
- Common password in breach databases
- Immediate security risk on any deployed environment

#### Solution

**File:** `scripts/seed_data.py`

```python
import secrets
import os

async def create_admin_user(db: AsyncSession, roles_map: dict[str, Role]):
    """Create default admin user with secure password."""
    print("\nCreating admin user...")
    
    admin_email = "admin@cdsa.local"
    admin_username = "admin"
    
    # Check if admin user exists
    result = await db.execute(
        select(User).where(User.email == admin_email)
    )
    admin_user = result.scalar_one_or_none()
    
    if admin_user is None:
        # Get password from environment or generate secure random
        admin_password = os.getenv("ADMIN_INITIAL_PASSWORD")
        
        if not admin_password:
            # Generate cryptographically secure random password
            admin_password = secrets.token_urlsafe(24)
            print(f"\n{'='*60}")
            print(f"⚠️  GENERATED ADMIN PASSWORD")
            print(f"{'='*60}")
            print(f"  Username: {admin_username}")
            print(f"  Email:    {admin_email}")
            print(f"  Password: {admin_password}")
            print(f"\n  🔐 SAVE THIS PASSWORD - IT WILL NOT BE SHOWN AGAIN!")
            print(f"{'='*60}\n")
        else:
            print(f"  ✓ Using password from ADMIN_INITIAL_PASSWORD env var")
        
        admin_user = User(
            email=admin_email,
            username=admin_username,
            hashed_password=get_password_hash(admin_password),
            full_name="System Administrator",
            is_active=True,
            is_superuser=True,
            is_verified=True
        )
        
        if "ADMIN" in roles_map:
            admin_user.roles.append(roles_map["ADMIN"])
        
        db.add(admin_user)
        await db.commit()
        
        print(f"  ✓ Created admin user: {admin_email}")
    else:
        print(f"  • Admin user already exists: {admin_email}")
```

#### Implementation Steps

1. **Update seed_data.py** with secure password generation
2. **Update documentation** to explain password generation
3. **Add to .env.example**
   ```bash
   # Optional: Set initial admin password
   # If not set, a random password will be generated and displayed
   ADMIN_INITIAL_PASSWORD=
   ```
4. **Update deployment guide** with instructions to set password

#### Testing Requirements
- [ ] Test with ADMIN_INITIAL_PASSWORD set
- [ ] Test with ADMIN_INITIAL_PASSWORD unset (random generation)
- [ ] Verify password strength (length, entropy)
- [ ] Test that password is not logged anywhere

---

### 🔴 Issue #3: Generic Error Handling

**Priority:** P1 - High Impact  
**Severity:** Medium  
**Location:** `app/main.py:130-137`  
**Estimated Effort:** 2 days  

#### Problem Description
All exceptions return a generic "Internal server error" message, making debugging and troubleshooting difficult for both developers and API consumers.

#### Impact
- Poor developer experience
- Difficult troubleshooting
- No structured error responses
- Missing actionable error messages

#### Solution

**File:** `app/core/exceptions.py` (new file)

```python
"""Custom exceptions and error handling."""
from typing import Any, Dict, Optional
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pydantic import ValidationError
import logging

logger = logging.getLogger(__name__)

class CDSAException(Exception):
    """Base exception for CDSA application."""
    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

class DatabaseError(CDSAException):
    """Database operation failed."""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            status_code=500,
            details=details
        )

class NotFoundError(CDSAException):
    """Resource not found."""
    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} with id {identifier} not found",
            error_code="NOT_FOUND",
            status_code=404,
            details={"resource": resource, "identifier": str(identifier)}
        )

class AuthenticationError(CDSAException):
    """Authentication failed."""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=401
        )

class AuthorizationError(CDSAException):
    """User not authorized for this action."""
    def __init__(self, message: str = "Not authorized"):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=403
        )

class ValidationError(CDSAException):
    """Data validation failed."""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=422,
            details=details
        )

class ExternalServiceError(CDSAException):
    """External service (LLM, etc.) failed."""
    def __init__(self, service: str, message: str):
        super().__init__(
            message=f"{service} service error: {message}",
            error_code="EXTERNAL_SERVICE_ERROR",
            status_code=503,
            details={"service": service}
        )
```

**File:** `app/main.py` (update exception handlers)

```python
from app.core.exceptions import (
    CDSAException,
    DatabaseError,
    NotFoundError,
    AuthenticationError,
    AuthorizationError,
    ValidationError as CDSAValidationError,
    ExternalServiceError
)

# Specific exception handlers
@app.exception_handler(CDSAException)
async def cdsa_exception_handler(request: Request, exc: CDSAException):
    """Handle custom CDSA exceptions."""
    logger.error(
        f"CDSA Exception: {exc.error_code} - {exc.message}",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path
        }
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details
            }
        }
    )

@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Handle database integrity errors."""
    logger.error(f"Database integrity error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=409,
        content={
            "error": {
                "code": "INTEGRITY_ERROR",
                "message": "Database constraint violation",
                "details": {"constraint": str(exc.orig) if hasattr(exc, 'orig') else None}
            }
        }
    )

@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    """Handle general database errors."""
    logger.error(f"Database error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "DATABASE_ERROR",
                "message": "Database operation failed",
                "details": {}
            }
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions."""
    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,
        extra={"path": request.url.path, "method": request.method}
    )
    
    # Don't expose internal errors in production
    if settings.is_production:
        message = "An internal error occurred"
    else:
        message = str(exc)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": message,
                "details": {}
            }
        }
    )
```

#### Implementation Steps

1. **Create exceptions module** with custom exception classes
2. **Update main.py** with specific exception handlers
3. **Update all endpoints** to raise specific exceptions
4. **Add error response schemas** to OpenAPI docs
5. **Update error logging** with structured data

#### Testing Requirements
- [ ] Test each exception type
- [ ] Verify error response format
- [ ] Test production vs development error messages
- [ ] Verify logging includes all required context

---

## High Priority Issues (Weeks 2-3)

### 🟡 Issue #4: Missing Celery Tasks for Secret Rotation

**Priority:** P2 - Core Feature Incomplete  
**Severity:** Medium  
**Location:** `app/tasks.py` (missing), `docker-compose.yml:68`  
**Estimated Effort:** 4 days  

#### Problem Description
The Secret model has rotation fields and docker-compose defines a celery_worker, but no Celery tasks exist. The rotation feature is completely non-functional.

#### Solution

**File:** `app/celeryconfig.py` (new file)

```python
"""Celery configuration."""
from kombu import Exchange, Queue
from app.config import settings

# Broker settings
broker_url = settings.REDIS_URL
result_backend = settings.REDIS_URL

# Task settings
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']
timezone = 'UTC'
enable_utc = True

# Beat schedule
beat_schedule = {
    'check-secret-rotation': {
        'task': 'app.tasks.check_secret_rotation',
        'schedule': 3600.0,  # Every hour
    },
    'cleanup-expired-secrets': {
        'task': 'app.tasks.cleanup_expired_secrets',
        'schedule': 86400.0,  # Daily
    },
}

# Task routing
task_routes = {
    'app.tasks.rotate_secret': {'queue': 'secrets'},
    'app.tasks.process_document': {'queue': 'documents'},
}

# Define queues
task_queues = (
    Queue('default', Exchange('default'), routing_key='default'),
    Queue('secrets', Exchange('secrets'), routing_key='secrets'),
    Queue('documents', Exchange('documents'), routing_key='documents'),
)
```

**File:** `app/tasks.py` (new file)

```python
"""Celery tasks for background processing."""
from celery import Celery
from datetime import datetime, timedelta
from sqlalchemy import select
from app.db.base import get_session_factory
from app.models.secret import Secret, SecretVersion
from app.models.audit import AuditLog
import logging

logger = logging.getLogger(__name__)

celery = Celery('csda')
celery.config_from_object('app.celeryconfig')

@celery.task(name='app.tasks.check_secret_rotation')
def check_secret_rotation():
    """Check for secrets that need rotation and queue rotation tasks."""
    logger.info("Checking for secrets that need rotation")
    
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        # Find secrets due for rotation
        result = session.execute(
            select(Secret).where(
                Secret.rotation_enabled == True,
                Secret.is_active == True,
                Secret.next_rotation <= datetime.utcnow()
            )
        )
        secrets = result.scalars().all()
        
        logger.info(f"Found {len(secrets)} secrets due for rotation")
        
        for secret in secrets:
            # Queue individual rotation task
            rotate_secret.delay(secret.id)
        
        return {"secrets_queued": len(secrets)}
        
    finally:
        session.close()

@celery.task(name='app.tasks.rotate_secret', bind=True, max_retries=3)
def rotate_secret(self, secret_id: int):
    """Rotate a specific secret."""
    logger.info(f"Rotating secret {secret_id}")
    
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        secret = session.get(Secret, secret_id)
        if not secret:
            logger.error(f"Secret {secret_id} not found")
            return {"error": "Secret not found"}
        
        # Create new version with current value
        current_version = len(secret.versions)
        new_version = SecretVersion(
            secret_id=secret.id,
            version_number=current_version + 1,
            encrypted_value=secret.encrypted_value,
            encryption_key_id=secret.encryption_key_id,
            rotation_reason="automatic_rotation"
        )
        
        # Deactivate old versions
        for version in secret.versions:
            version.is_active = False
        
        # Activate new version
        new_version.is_active = True
        session.add(new_version)
        
        # Update secret rotation metadata
        secret.last_rotated = datetime.utcnow()
        if secret.rotation_days:
            secret.next_rotation = datetime.utcnow() + timedelta(days=secret.rotation_days)
        
        # Create audit log
        audit = AuditLog(
            user_id=None,  # System action
            action="secret.rotate",
            resource_type="secret",
            resource_id=secret.id,
            details={
                "version": new_version.version_number,
                "rotation_type": "automatic"
            }
        )
        session.add(audit)
        
        session.commit()
        
        logger.info(f"Successfully rotated secret {secret_id}")
        return {"success": True, "version": new_version.version_number}
        
    except Exception as exc:
        logger.error(f"Error rotating secret {secret_id}: {exc}")
        session.rollback()
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
        
    finally:
        session.close()

@celery.task(name='app.tasks.cleanup_expired_secrets')
def cleanup_expired_secrets():
    """Archive or delete expired secrets."""
    logger.info("Cleaning up expired secrets")
    
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        # Find expired secrets
        result = session.execute(
            select(Secret).where(
                Secret.expires_at <= datetime.utcnow(),
                Secret.is_active == True
            )
        )
        secrets = result.scalars().all()
        
        for secret in secrets:
            secret.is_active = False
            logger.info(f"Deactivated expired secret {secret.id}")
        
        session.commit()
        return {"secrets_deactivated": len(secrets)}
        
    finally:
        session.close()

@celery.task(name='app.tasks.process_document', bind=True)
def process_document(self, document_id: int, file_bytes: bytes, filename: str, file_ext: str):
    """Process and index a document in background."""
    # Implementation for document processing
    pass
```

#### Implementation Steps

1. **Install Celery dependencies**
   ```bash
   uv add celery redis kombu
   ```

2. **Create celeryconfig.py** with broker and beat schedule

3. **Create tasks.py** with rotation tasks

4. **Update docker-compose.yml** to fix celery command
   ```yaml
   celery_worker:
     command: celery -A app.tasks worker --loglevel=info -Q default,secrets,documents
   
   celery_beat:
     build: .
     command: celery -A app.tasks beat --loglevel=info
     depends_on:
       - redis
   ```

5. **Add task monitoring** (Flower)
   ```yaml
   flower:
     build: .
     command: celery -A app.tasks flower --port=5555
     ports:
       - "5555:5555"
   ```

#### Testing Requirements
- [ ] Test rotation task execution
- [ ] Test task retry logic
- [ ] Test beat schedule
- [ ] Test queue routing
- [ ] Load test with 1000+ secrets

---

### 🟡 Issue #5: Tool Execution Placeholder

**Priority:** P2 - Core Feature Incomplete  
**Severity:** Medium  
**Location:** `app/api/v1/tools.py:272-341`  
**Estimated Effort:** 5 days  

#### Problem Description
The `_execute_tool` function is a mock that sleeps for 1 second and returns a hardcoded success response. No actual tool execution framework exists.

#### Solution

**File:** `app/services/tool_executor.py` (new file)

```python
"""Tool execution service."""
from typing import Any, Dict
from enum import Enum
import subprocess
import json
import asyncio
from app.models.tool import Tool, ToolExecution

class ToolType(str, Enum):
    PYTHON_SCRIPT = "python_script"
    SHELL_COMMAND = "shell_command"
    API_CALL = "api_call"
    SQL_QUERY = "sql_query"

class ToolExecutor:
    """Execute tools with proper isolation and error handling."""
    
    async def execute(
        self,
        tool: Tool,
        execution: ToolExecution,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a tool based on its type."""
        
        if tool.tool_type == ToolType.PYTHON_SCRIPT:
            return await self._execute_python(tool, input_data)
        elif tool.tool_type == ToolType.SHELL_COMMAND:
            return await self._execute_shell(tool, input_data)
        elif tool.tool_type == ToolType.API_CALL:
            return await self._execute_api(tool, input_data)
        elif tool.tool_type == ToolType.SQL_QUERY:
            return await self._execute_sql(tool, input_data)
        else:
            raise ValueError(f"Unsupported tool type: {tool.tool_type}")
    
    async def _execute_python(self, tool: Tool, input_data: Dict) -> Dict:
        """Execute Python script in isolated environment."""
        # Implementation with subprocess and timeout
        pass
    
    async def _execute_shell(self, tool: Tool, input_data: Dict) -> Dict:
        """Execute shell command with proper sanitization."""
        # Implementation with shell command execution
        pass
    
    async def _execute_api(self, tool: Tool, input_data: Dict) -> Dict:
        """Make API call with retries and timeout."""
        # Implementation with httpx
        pass
    
    async def _execute_sql(self, tool: Tool, input_data: Dict) -> Dict:
        """Execute SQL query in read-only connection."""
        # Implementation with SQL execution
        pass

tool_executor = ToolExecutor()
```

Update `app/api/v1/tools.py`:

```python
from app.services.tool_executor import tool_executor

async def _execute_tool(
    execution: ToolExecution,
    tool: Tool,
    db: AsyncSession
):
    """Execute a tool using the tool executor service."""
    try:
        execution.status = ExecutionStatus.RUNNING
        execution.started_at = datetime.utcnow()
        await db.commit()
        
        # Execute tool
        result = await tool_executor.execute(tool, execution, execution.input_data)
        
        execution.status = ExecutionStatus.COMPLETED
        execution.completed_at = datetime.utcnow()
        execution.execution_time = (
            execution.completed_at - execution.started_at
        ).total_seconds()
        execution.output_data = result
        
        # Update tool statistics
        tool.execution_count += 1
        tool.success_count += 1
        tool.last_executed_at = datetime.utcnow()
        
        await db.commit()
        
    except Exception as e:
        execution.status = ExecutionStatus.FAILED
        execution.error_message = str(e)
        execution.completed_at = datetime.utcnow()
        
        tool.execution_count += 1
        tool.failure_count += 1
        
        await db.commit()
```

#### Implementation Steps

1. **Create tool executor service**
2. **Implement execution methods** for each tool type
3. **Add sandbox/isolation** for script execution
4. **Implement timeout handling**
5. **Add result validation**
6. **Update tool model** with execution configuration

---

### 🟡 Issue #6: Vector Search Placeholder

**Priority:** P2 - Core Feature Incomplete  
**Severity:** Medium  
**Location:** `app/api/v1/documents.py:713`  
**Estimated Effort:** 5 days  

#### Problem Description
The `vector_search` function exists but is likely a placeholder. No pgvector operators or similarity calculations are implemented.

#### Solution

**File:** `app/api/v1/documents.py` (update vector_search)

```python
from sqlalchemy import text
from pgvector.sqlalchemy import Vector

async def vector_search(
    query_embedding: List[float],
    top_k: int,
    filters: Optional[Dict[str, Any]],
    min_score: float,
    user_id: int,
    db: Session
) -> List[SearchResultResponse]:
    """
    Perform vector similarity search using pgvector.
    
    Uses cosine distance for similarity calculation.
    """
    
    # Build base query with pgvector operators
    query = """
        SELECT 
            dc.id,
            dc.document_id,
            dc.content,
            dc.chunk_index,
            d.title,
            d.source,
            1 - (dc.embedding <=> :query_embedding) as similarity_score
        FROM document_chunks dc
        JOIN documents d ON dc.document_id = d.id
        WHERE 
            dc.embedding IS NOT NULL
            AND (d.is_public = true OR d.uploaded_by = :user_id)
            AND (1 - (dc.embedding <=> :query_embedding)) >= :min_score
    """
    
    # Add filters
    if filters:
        if filters.get('document_ids'):
            query += " AND dc.document_id = ANY(:document_ids)"
        if filters.get('tags'):
            query += " AND d.tags && :tags"
    
    query += """
        ORDER BY dc.embedding <=> :query_embedding
        LIMIT :top_k
    """
    
    # Execute query
    result = db.execute(
        text(query),
        {
            'query_embedding': query_embedding,
            'user_id': user_id,
            'min_score': min_score,
            'top_k': top_k,
            **filters if filters else {}
        }
    )
    
    # Format results
    results = []
    for row in result:
        results.append(SearchResultResponse(
            chunk_id=row.id,
            document_id=row.document_id,
            content=row.content,
            chunk_index=row.chunk_index,
            document_title=row.title,
            document_source=row.source,
            similarity_score=row.similarity_score,
            metadata={}
        ))
    
    return results
```

**File:** `app/models/document.py` (update DocumentChunk)

```python
from pgvector.sqlalchemy import Vector

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    # ... existing fields ...
    
    # Add vector embedding column
    embedding = Column(Vector(1536), nullable=True)  # OpenAI ada-002 dimension
    
    # Add index for vector search
    __table_args__ = (
        Index('idx_document_chunk_embedding', 'embedding', postgresql_using='ivfflat'),
    )
```

#### Implementation Steps

1. **Install pgvector extension** in PostgreSQL
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

2. **Add pgvector SQLAlchemy support**
   ```bash
   uv add pgvector
   ```

3. **Create migration** for embedding column and indexes

4. **Implement vector_search** with pgvector operators

5. **Implement keyword_search** for hybrid search

6. **Test search performance** and optimize indexes

---

## Medium Priority Issues (Weeks 4-6)

### 🔵 Issue #7: Document Processing with BackgroundTasks

**Priority:** P3 - UX Improvement  
**Severity:** Low  
**Location:** `app/api/v1/documents.py:97-104`  
**Estimated Effort:** 3 days  

#### Solution
Migrate document processing to Celery tasks with status tracking endpoint.

#### Implementation
```python
# Add task
@celery.task
def process_document(document_id: int, file_bytes: bytes):
    # Process document
    pass

# Add status endpoint
@router.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    result = AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.state,
        "result": result.result if result.ready() else None
    }
```

---

### 🔵 Issue #8: Limited Caching Strategy

**Priority:** P3 - Performance  
**Severity:** Low  
**Location:** `app/api/v1/tools.py:242-269`  
**Estimated Effort:** 3 days  

#### Solution
Implement Redis caching for frequently accessed endpoints.

#### Implementation
```python
from functools import wraps
import json
import redis

def cache_result(ttl: int = 300):
    """Decorator to cache function results in Redis."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{func.__name__}:{json.dumps(kwargs, sort_keys=True)}"
            
            # Check cache
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            await redis_client.setex(cache_key, ttl, json.dumps(result))
            
            return result
        return wrapper
    return decorator

@router.get("/tools", response_model=ToolListResponse)
@cache_result(ttl=600)  # Cache for 10 minutes
async def list_tools(...):
    pass
```

---

### 🔵 Issue #9: Migrations at Container Startup

**Priority:** P3 - Deployment Safety  
**Severity:** Low  
**Location:** `Dockerfile:40`  
**Estimated Effort:** 2 days  

#### Solution
Decouple migrations from application startup.

#### Implementation

**Update Dockerfile:**
```dockerfile
# Remove migration from CMD
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Add migration script:**
```bash
# scripts/run-migrations.sh
#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head
echo "Migrations complete"
```

**Update deployment process:**
```bash
# Run migrations as separate step
docker-compose run --rm api ./scripts/run-migrations.sh

# Then start services
docker-compose up -d
```

---

### 🔵 Issue #10: No Test Suite

**Priority:** P3 - Quality Assurance  
**Severity:** Medium  
**Location:** `backend/tests/`  
**Estimated Effort:** 10 days (ongoing)  

#### Solution
Implement comprehensive test suite with pytest.

#### Implementation Structure

```
tests/
├── conftest.py              # Test fixtures
├── unit/
│   ├── test_crypto.py      # Encryption tests
│   ├── test_models.py      # Model tests
│   └── test_services.py    # Service tests
├── integration/
│   ├── test_auth_api.py    # Auth endpoint tests
│   ├── test_vault_api.py   # Vault endpoint tests
│   └── test_tools_api.py   # Tools endpoint tests
└── e2e/
    └── test_user_flows.py  # End-to-end tests
```

**Sample Test:**
```python
# tests/unit/test_crypto.py
import pytest
from app.core.crypto import encrypt_value, decrypt_value

def test_encrypt_decrypt():
    """Test encryption and decryption roundtrip."""
    plaintext = "secret_value_123"
    encrypted = encrypt_value(plaintext)
    decrypted = decrypt_value(encrypted)
    assert decrypted == plaintext
    assert encrypted != plaintext

def test_encrypt_empty():
    """Test encryption of empty string."""
    with pytest.raises(ValueError):
        encrypt_value("")
```

---

## Implementation Checklist

### Week 1 - Critical Issues
- [ ] Implement vault encryption
  - [ ] Add cryptography dependency
  - [ ] Create crypto utilities
  - [ ] Update Secret model with properties
  - [ ] Create migration for encryption
  - [ ] Write data migration script
  - [ ] Add unit tests
- [ ] Fix admin password
  - [ ] Update seed_data.py
  - [ ] Update documentation
  - [ ] Test password generation
- [ ] Implement error handling
  - [ ] Create exceptions module
  - [ ] Add exception handlers
  - [ ] Update all endpoints
  - [ ] Add tests

### Week 2-3 - High Priority
- [ ] Implement Celery tasks
  - [ ] Add dependencies
  - [ ] Create celeryconfig.py
  - [ ] Create tasks.py
  - [ ] Update docker-compose
  - [ ] Add monitoring (Flower)
  - [ ] Add tests
- [ ] Implement tool execution
  - [ ] Create tool executor service
  - [ ] Implement execution methods
  - [ ] Add sandbox isolation
  - [ ] Add timeout handling
  - [ ] Add tests
- [ ] Implement vector search
  - [ ] Install pgvector
  - [ ] Create migration
  - [ ] Implement search function
  - [ ] Optimize indexes
  - [ ] Add tests

### Week 4-6 - Medium Priority
- [ ] Migrate document processing to Celery
- [ ] Implement caching layer
- [ ] Decouple migrations
- [ ] Start test suite implementation

---

## Testing Requirements

### Unit Tests
- [ ] Encryption/decryption functions
- [ ] Password generation
- [ ] Custom exceptions
- [ ] Celery tasks (mocked)
- [ ] Tool executor methods

### Integration Tests
- [ ] Auth API endpoints
- [ ] Vault API endpoints
- [ ] Tool execution API
- [ ] Document search API
- [ ] Error responses

### End-to-End Tests
- [ ] User registration and login
- [ ] Secret creation and retrieval
- [ ] Tool execution workflow
- [ ] Document upload and search

### Performance Tests
- [ ] Vector search with 100k documents
- [ ] Concurrent tool executions
- [ ] Secret rotation at scale
- [ ] Cache hit rates

---

## Deployment Considerations

### Pre-Deployment Checklist
- [ ] All critical issues resolved
- [ ] Test suite passing
- [ ] Security audit completed
- [ ] Documentation updated
- [ ] Migration plan documented
- [ ] Rollback plan documented

### Rollout Strategy
1. **Staging Deployment**
   - Deploy to staging environment
   - Run full test suite
   - Perform security scan
   - Monitor for 24 hours

2. **Production Deployment**
   - Schedule maintenance window
   - Backup database
   - Run migrations
   - Deploy new version
   - Monitor logs and metrics
   - Verify critical workflows

3. **Post-Deployment**
   - Monitor error rates
   - Check performance metrics
   - Verify security features
   - Collect user feedback

### Monitoring
- [ ] Application logs
- [ ] Error rates
- [ ] API response times
- [ ] Database performance
- [ ] Celery task status
- [ ] Cache hit rates

---

## Appendix

### Useful Commands

```bash
# Run migrations
docker-compose run --rm api alembic upgrade head

# Generate new migration
docker-compose run --rm api alembic revision --autogenerate -m "description"

# Run tests
docker-compose run --rm api pytest

# Start Celery worker
docker-compose up -d celery_worker

# Monitor Celery tasks
docker-compose up -d flower
# Visit http://localhost:5555

# Check encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### References
- [Cryptography Documentation](https://cryptography.io/)
- [Celery Documentation](https://docs.celeryq.dev/)
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/bigger-applications/)

---

**Document Status:** Active  
**Next Review:** After Week 1 completion  
**Owner:** Backend Team Lead