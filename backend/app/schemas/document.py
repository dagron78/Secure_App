"""
Document and RAG Pydantic schemas for request/response validation.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


# Document Schemas
class DocumentCreate(BaseModel):
    """Schema for creating a document"""
    title: str = Field(..., min_length=1, max_length=500)
    source_type: str = Field(..., description="file, url, database, api")
    content: Optional[str] = Field(None, description="Text content if provided directly")
    tags: Optional[List[str]] = None
    meta_data: Optional[Dict[str, Any]] = None
    is_public: bool = False
    required_permission: Optional[str] = None


class DocumentUpdate(BaseModel):
    """Schema for updating a document"""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    tags: Optional[List[str]] = None
    meta_data: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = None
    required_permission: Optional[str] = None


class DocumentResponse(BaseModel):
    """Schema for document response"""
    id: int
    title: str
    source: str
    source_type: str
    file_type: Optional[str]
    file_size: Optional[int]
    tags: Optional[List[str]]
    meta_data: Optional[Dict[str, Any]]
    is_processed: bool
    is_indexed: bool
    processing_error: Optional[str]
    uploaded_by: Optional[int]
    is_public: bool
    required_permission: Optional[str]
    chunk_count: int
    created_at: datetime
    updated_at: datetime
    last_accessed: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    """Schema for paginated document list"""
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int
    
    model_config = ConfigDict(from_attributes=True)


class DocumentContentResponse(BaseModel):
    """Schema for document with content"""
    id: int
    title: str
    content: str
    source_type: str
    file_type: Optional[str]
    meta_data: Optional[Dict[str, Any]]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Document Chunk Schemas
class DocumentChunkResponse(BaseModel):
    """Schema for document chunk response"""
    id: int
    document_id: int
    chunk_index: int
    content: str
    token_count: Optional[int]
    char_count: Optional[int]
    meta_data: Optional[Dict[str, Any]]
    search_keywords: Optional[List[str]]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class DocumentChunkListResponse(BaseModel):
    """Schema for document chunks list"""
    chunks: List[DocumentChunkResponse]
    total: int
    document_id: int
    
    model_config = ConfigDict(from_attributes=True)


# Indexing Schemas
class DocumentIndexRequest(BaseModel):
    """Schema for document indexing request"""
    use_docling: bool = Field(default=True, description="Use Docling for enhanced processing")
    extract_tables: bool = Field(default=True, description="Extract table structures")
    extract_images: bool = Field(default=True, description="Extract and caption images")
    chunk_size: Optional[int] = Field(None, ge=100, le=5000, description="Custom chunk size")
    chunk_overlap: Optional[int] = Field(None, ge=0, le=1000, description="Custom chunk overlap")
    embedding_model: Optional[str] = Field(None, description="Specific embedding model to use")


class DocumentIndexResponse(BaseModel):
    """Schema for indexing result"""
    document_id: int
    chunks_created: int
    tables_extracted: int
    images_extracted: int
    total_tokens: int
    processing_time_seconds: float
    success: bool
    error: Optional[str] = None


# Search Schemas
class DocumentSearchRequest(BaseModel):
    """Schema for document search request"""
    query: str = Field(..., min_length=1, max_length=1000)
    search_type: str = Field(default="vector", description="vector, keyword, or hybrid")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of results")
    filters: Optional[Dict[str, Any]] = Field(None, description="Metadata filters")
    min_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum relevance score")


class SearchResultResponse(BaseModel):
    """Schema for search result"""
    chunk_id: int
    document_id: int
    document_title: str
    content: str
    relevance_score: float
    rank: int
    meta_data: Optional[Dict[str, Any]]
    search_type: str
    
    model_config = ConfigDict(from_attributes=True)


class DocumentSearchResponse(BaseModel):
    """Schema for search results"""
    query: str
    results: List[SearchResultResponse]
    total_results: int
    search_type: str
    processing_time_ms: float


# RAG Query Schemas
class RAGQueryRequest(BaseModel):
    """Schema for RAG query request"""
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20, description="Number of context chunks")
    session_id: Optional[int] = Field(None, description="Chat session for context")
    filters: Optional[Dict[str, Any]] = None
    include_metadata: bool = Field(default=True, description="Include chunk metadata")


class RAGContextChunk(BaseModel):
    """Schema for RAG context chunk"""
    content: str
    document_title: str
    relevance_score: float
    meta_data: Optional[Dict[str, Any]]


class RAGQueryResponse(BaseModel):
    """Schema for RAG query response"""
    query: str
    context_chunks: List[RAGContextChunk]
    total_tokens: int
    sources: List[str]
    processing_time_ms: float


# Embedding Model Schemas
class EmbeddingModelResponse(BaseModel):
    """Schema for embedding model"""
    id: int
    name: str
    display_name: str
    provider: str
    model_id: str
    dimension: int
    max_tokens: int
    cost_per_1k_tokens: Optional[float]
    is_active: bool
    is_default: bool
    avg_latency_ms: Optional[float]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class EmbeddingModelListResponse(BaseModel):
    """Schema for embedding models list"""
    models: List[EmbeddingModelResponse]
    total: int


# Document Statistics
class DocumentStatistics(BaseModel):
    """Schema for document statistics"""
    total_documents: int
    processed_documents: int
    indexed_documents: int
    total_chunks: int
    total_searches: int
    documents_by_type: Dict[str, int]
    avg_chunks_per_document: float
    storage_size_mb: float
    recent_uploads: int


# Table Extraction Schemas
class TableExtractionResponse(BaseModel):
    """Schema for extracted table"""
    page_number: int
    table_index: int
    headers: List[str]
    rows: List[List[str]]
    markdown: str
    meta_data: Optional[Dict[str, Any]]


class DocumentTablesResponse(BaseModel):
    """Schema for all tables in document"""
    document_id: int
    document_title: str
    tables: List[TableExtractionResponse]
    total_tables: int


# Image Extraction Schemas
class ImageExtractionResponse(BaseModel):
    """Schema for extracted image"""
    page_number: int
    image_index: int
    caption: Optional[str]
    alt_text: Optional[str]
    image_type: str  # figure, chart, diagram, photo
    meta_data: Optional[Dict[str, Any]]


class DocumentImagesResponse(BaseModel):
    """Schema for all images in document"""
    document_id: int
    document_title: str
    images: List[ImageExtractionResponse]
    total_images: int