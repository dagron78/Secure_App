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


@celery.task(name='app.tasks.process_document', bind=True, max_retries=3)
def process_document(
    self,
    document_id: int,
    file_bytes: bytes,
    filename: str,
    file_type: str
):
    """
    Process and index a document in background using Celery.
    
    This task:
    1. Processes the document using Docling (extracts text, tables, images)
    2. Chunks the content using chunking service
    3. Generates embeddings for each chunk
    4. Stores chunks with embeddings in the database
    5. Updates document status throughout the process
    
    Args:
        document_id: ID of the document to process
        file_bytes: Raw bytes of the uploaded file
        filename: Original filename
        file_type: File extension (pdf, docx, etc.)
        
    Returns:
        dict: Result of the processing operation with statistics
    """
    from app.services.document_processor import document_processor
    from app.services.chunking_service import chunking_service
    from app.services.embedding_service import get_embedding_service
    from app.models.document import Document, DocumentChunk
    from app.models.audit import AuditLog
    import asyncio
    
    logger.info(f"Starting Celery task to process document {document_id}")
    
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        # Get document from database
        document = session.get(Document, document_id)
        if not document:
            logger.error(f"Document {document_id} not found")
            return {"success": False, "error": "Document not found"}
        
        # Update status to processing
        document.is_processed = False
        document.processing_error = None
        session.commit()
        
        # Step 1: Process document with Docling
        logger.info(f"Processing document {document_id} with Docling")
        result = document_processor.process_from_bytes(file_bytes, filename, file_type)
        
        if not result["success"]:
            document.processing_error = result["error"]
            document.is_processed = False
            session.commit()
            logger.error(f"Document processing failed: {result['error']}")
            return {
                "success": False,
                "error": result["error"],
                "document_id": document_id
            }
        
        # Update document with processing results
        document.is_processed = True
        document.meta_data = result["metadata"]
        session.commit()
        logger.info(f"Document {document_id} processed successfully")
        
        # Step 2: Create chunks
        logger.info(f"Chunking document {document_id}")
        chunks = chunking_service.chunk_document(
            result["text"],
            result["structure"],
            result["tables"],
            result["images"],
            result["metadata"]
        )
        logger.info(f"Created {len(chunks)} chunks for document {document_id}")
        
        # Step 3: Generate embeddings (async operation)
        logger.info(f"Generating embeddings for {len(chunks)} chunks")
        chunk_texts = [c["content"] for c in chunks]
        embedding_service = get_embedding_service()
        
        # Run async embedding generation in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            embeddings = loop.run_until_complete(
                embedding_service.generate_embeddings(chunk_texts)
            )
        finally:
            loop.close()
        
        logger.info(f"Generated {len(embeddings)} embeddings")
        
        # Step 4: Save chunks with embeddings to database
        logger.info(f"Saving chunks to database")
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            db_chunk = DocumentChunk(
                document_id=document_id,
                chunk_index=idx,
                content=chunk["content"],
                embedding=embedding,
                token_count=chunk["meta_data"].get("token_count"),
                char_count=chunk["meta_data"].get("char_count"),
                meta_data=chunk["meta_data"],
                search_keywords=chunk["search_keywords"]
            )
            session.add(db_chunk)
        
        # Step 5: Update document final status
        document.chunk_count = len(chunks)
        document.is_indexed = True
        session.commit()
        
        # Create audit log
        audit = AuditLog(
            user_id=document.uploaded_by,
            action="document.index_complete",
            resource_type="document",
            resource_id=document.id,
            details={
                "chunk_count": len(chunks),
                "processing_time": result["processing_time"],
                "page_count": result["page_count"],
                "char_count": result["char_count"]
            },
            success=True
        )
        session.add(audit)
        session.commit()
        
        logger.info(
            f"Successfully indexed document {document_id} with {len(chunks)} chunks "
            f"in {result['processing_time']:.2f}s"
        )
        
        return {
            "success": True,
            "document_id": document_id,
            "chunk_count": len(chunks),
            "processing_time": result["processing_time"],
            "page_count": result["page_count"],
            "char_count": result["char_count"]
        }
        
    except Exception as exc:
        logger.error(f"Error processing document {document_id}: {exc}", exc_info=True)
        
        # Update document with error
        try:
            document = session.get(Document, document_id)
            if document:
                document.processing_error = str(exc)
                document.is_processed = False
                document.is_indexed = False
                
                # Create audit log for failure
                audit = AuditLog(
                    user_id=document.uploaded_by,
                    action="document.index_failed",
                    resource_type="document",
                    resource_id=document.id,
                    details={"error": str(exc)},
                    success=False,
                    error_message=str(exc)
                )
                session.add(audit)
                session.commit()
        except Exception as e:
            logger.error(f"Error updating document status: {e}")
        
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
        
    finally:
        session.close()