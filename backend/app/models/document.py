"""Document and RAG (Retrieval-Augmented Generation) models."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Boolean, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY

from app.db.base import Base

# Try to import pgvector, use Text fallback if not available
try:
    from pgvector.sqlalchemy import Vector
    VECTOR_AVAILABLE = True
except ImportError:
    VECTOR_AVAILABLE = False
    Vector = None


class Document(Base):
    """Document model for RAG system."""
    
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    
    # Document identification
    title = Column(String(500), nullable=False, index=True)
    source = Column(String(500), nullable=False)  # File path, URL, etc.
    source_type = Column(String(50), nullable=False, index=True)  # file, url, database, api
    
    # Content
    # Content
    # content and content_hash removed as they are not in DB schema

    
    # Document metadata
    meta_data = Column(JSON, nullable=True)  # Custom metadata
    tags = Column(JSON, nullable=True)  # Document tags (using JSON for SQLite compatibility)
    file_type = Column(String(50), nullable=True)  # pdf, docx, txt, etc.
    file_size = Column(Integer, nullable=True)  # Size in bytes
    
    # Processing status
    is_processed = Column(Boolean, default=False, nullable=False, index=True)
    is_indexed = Column(Boolean, default=False, nullable=False, index=True)
    processing_error = Column(Text, nullable=True)
    
    # Ownership
    uploaded_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # Access control
    is_public = Column(Boolean, default=False, nullable=False)
    required_permission = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_accessed = Column(DateTime, nullable=True)
    
    # Relationships
    uploader = relationship("User")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Document(id={self.id}, title={self.title}, source_type={self.source_type})>"
    
    @property
    def chunk_count(self) -> int:
        """Get number of chunks for this document."""
        return len(self.chunks) if self.chunks else 0


class DocumentChunk(Base):
    """Document chunk model for vector search."""
    
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Chunk details
    chunk_index = Column(Integer, nullable=False)  # Position in document
    content = Column(Text, nullable=False)
    
    # Vector embedding (for semantic search)
    # Supports various embedding dimensions: 384 (MiniLM), 768 (BERT), 1536 (OpenAI), 3072 (text-embedding-3-large)
    if VECTOR_AVAILABLE:
        embedding = Column(Vector(1536), nullable=True)  # Default to OpenAI embedding size
    else:
        embedding = Column(Text, nullable=True)  # Fallback to TEXT when pgvector not installed
    
    # Chunk metadata
    token_count = Column(Integer, nullable=True)
    char_count = Column(Integer, nullable=True)
    meta_data = Column(JSON, nullable=True)  # Page number, section, etc.
    
    # Search optimization
    search_keywords = Column(JSON, nullable=True)  # Extracted keywords (using JSON for SQLite compatibility)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    document = relationship("Document", back_populates="chunks")
    search_results = relationship("SearchResult", back_populates="chunk", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<DocumentChunk(id={self.id}, document_id={self.document_id}, index={self.chunk_index})>"


class SearchResult(Base):
    """Search result model for tracking RAG queries and results."""
    
    __tablename__ = "search_results"

    id = Column(Integer, primary_key=True, index=True)
    
    # Query details
    query = Column(Text, nullable=False, index=True)
    if VECTOR_AVAILABLE:
        query_embedding = Column(Vector(1536), nullable=True)
    else:
        query_embedding = Column(Text, nullable=True)  # Fallback to TEXT when pgvector not installed
    
    # Result details
    chunk_id = Column(Integer, ForeignKey('document_chunks.id', ondelete='CASCADE'), nullable=False, index=True)
    relevance_score = Column(Float, nullable=False)  # Similarity score
    rank = Column(Integer, nullable=False)  # Rank in search results
    
    # Context
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    session_id = Column(Integer, ForeignKey('chat_sessions.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # Search metadata
    search_type = Column(String(50), default="vector")  # vector, keyword, hybrid
    filters_applied = Column(JSON, nullable=True)
    
    # Feedback
    was_helpful = Column(Boolean, nullable=True)  # User feedback
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    chunk = relationship("DocumentChunk", back_populates="search_results")
    user = relationship("User")
    session = relationship("ChatSession")
    
    def __repr__(self) -> str:
        return f"<SearchResult(id={self.id}, chunk_id={self.chunk_id}, score={self.relevance_score})>"


class EmbeddingModel(Base):
    """Embedding model configuration for vector generation."""
    
    __tablename__ = "embedding_models"

    id = Column(Integer, primary_key=True, index=True)
    
    # Model details
    name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    provider = Column(String(50), nullable=False)  # openai, huggingface, local
    model_id = Column(String(255), nullable=False)
    
    # Model configuration
    dimension = Column(Integer, nullable=False)  # Embedding vector size
    max_tokens = Column(Integer, nullable=False)  # Max input tokens
    cost_per_1k_tokens = Column(Float, nullable=True)  # Cost tracking
    
    # Model status
    is_active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    
    # Performance metadata
    avg_latency_ms = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self) -> str:
        return f"<EmbeddingModel(id={self.id}, name={self.name}, dimension={self.dimension})>"