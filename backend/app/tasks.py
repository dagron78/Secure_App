"""Celery tasks for background processing."""
from celery import Celery
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
import logging

from app.config import settings
from app.db.base import get_session_factory
from app.models.secret import Secret, SecretVersion
from app.models.audit import AuditLog

logger = logging.getLogger(__name__)

# Initialize Celery app
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
        
    except Exception as e:
        logger.error(f"Error checking secret rotation: {e}")
        return {"error": str(e)}
    finally:
        session.close()


@celery.task(name='app.tasks.rotate_secret', bind=True, max_retries=3)
def rotate_secret(self, secret_id: int):
    """
    Rotate a specific secret.
    
    Args:
        secret_id: ID of the secret to rotate
        
    Returns:
        dict: Result of the rotation operation
    """
    logger.info(f"Rotating secret {secret_id}")
    
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        secret = session.get(Secret, secret_id)
        if not secret:
            logger.error(f"Secret {secret_id} not found")
            return {"error": "Secret not found"}
        
        # Create new version with current value
        current_version = len(secret.versions) if secret.versions else 0
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
        # Retry with exponential backoff
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
        
        expired_count = 0
        for secret in secrets:
            secret.is_active = False
            logger.info(f"Deactivated expired secret {secret.id}")
            
            # Create audit log
            audit = AuditLog(
                user_id=None,  # System action
                action="secret.expire",
                resource_type="secret",
                resource_id=secret.id,
                details={
                    "expired_at": secret.expires_at.isoformat() if secret.expires_at else None,
                    "reason": "automatic_expiration"
                }
            )
            session.add(audit)
            expired_count += 1
        
        session.commit()
        logger.info(f"Deactivated {expired_count} expired secrets")
        return {"secrets_deactivated": expired_count}
        
    except Exception as e:
        logger.error(f"Error cleaning up expired secrets: {e}")
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()


@celery.task(name='app.tasks.process_document', bind=True)
def process_document(self, document_id: int, file_path: str = None):
    """
    Process and index a document in background.
    
    Args:
        document_id: ID of the document to process
        file_path: Optional path to the document file
        
    Returns:
        dict: Result of the processing operation
    """
    logger.info(f"Processing document {document_id}")
    
    try:
        # TODO: Implement document processing
        # This would include:
        # 1. Load document from storage
        # 2. Extract text content
        # 3. Chunk the content
        # 4. Generate embeddings
        # 5. Store in vector database
        
        logger.info(f"Document {document_id} processed successfully")
        return {"success": True, "document_id": document_id}
        
    except Exception as exc:
        logger.error(f"Error processing document {document_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)