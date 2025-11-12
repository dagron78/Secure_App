"""
Document chunking service for token-optimized splitting.
Preserves document structure and hierarchy for better context in RAG.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ChunkingService:
    """
    Advanced chunking service for document splitting.
    
    Features:
    - Token-based chunking optimized for LLM context windows
    - Preserves document hierarchy (headings, sections)
    - Configurable chunk size and overlap
    - Rich metadata preservation (page numbers, bounding boxes)
    - Smart boundary detection (avoids splitting mid-sentence)
    - Support for tables and figures as separate chunks
    """
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        max_chunk_size: int = 2000
    ):
        """
        Initialize chunking service.
        
        Args:
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks in characters
            max_chunk_size: Maximum chunk size in characters
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_chunk_size = max_chunk_size
        
        logger.info(
            f"ChunkingService initialized - Size: {chunk_size}, "
            f"Overlap: {chunk_overlap}, Max: {max_chunk_size}"
        )
    
    def chunk_document(
        self,
        text: str,
        doc_structure: Optional[Dict[str, Any]] = None,
        tables: Optional[List[Dict[str, Any]]] = None,
        images: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Chunk a document into optimized segments for embedding.
        
        Args:
            text: Full document text (markdown format)
            doc_structure: Document structure from processor
            tables: Extracted tables
            images: Extracted images
            metadata: Document metadata
            
        Returns:
            List of chunks with metadata
        """
        chunks = []
        
        try:
            # Create basic text chunks
            text_chunks = self._chunk_text(text)
            
            # Add text chunks
            for idx, chunk_text in enumerate(text_chunks):
                chunk_meta = {
                    "chunk_type": "text",
                    "chunk_index": len(chunks),
                    "position_in_document": idx / len(text_chunks),
                    "char_count": len(chunk_text),
                    "token_count": self._estimate_tokens(chunk_text)
                }
                
                # Add structural metadata if available
                if doc_structure:
                    chunk_meta.update(self._get_structural_metadata(idx, doc_structure))
                
                # Add document metadata
                if metadata:
                    chunk_meta["document_metadata"] = metadata
                
                chunks.append({
                    "content": chunk_text,
                    "meta_data": chunk_meta,
                    "search_keywords": self._extract_keywords(chunk_text)
                })
            
            # Add table chunks
            if tables:
                for table in tables:
                    chunk_meta = {
                        "chunk_type": "table",
                        "chunk_index": len(chunks),
                        "page_number": table.get("page_number"),
                        "table_index": table.get("table_index"),
                        "row_count": table.get("row_count"),
                        "col_count": table.get("col_count"),
                        "char_count": len(table.get("markdown", "")),
                        "token_count": self._estimate_tokens(table.get("markdown", ""))
                    }
                    
                    # Create table content
                    table_content = self._format_table_content(table)
                    
                    chunks.append({
                        "content": table_content,
                        "meta_data": chunk_meta,
                        "search_keywords": self._extract_keywords(table_content)
                    })
            
            # Add image chunks
            if images:
                for image in images:
                    if image.get("caption") or image.get("alt_text"):
                        chunk_meta = {
                            "chunk_type": "image",
                            "chunk_index": len(chunks),
                            "page_number": image.get("page_number"),
                            "image_index": image.get("image_index"),
                            "image_type": image.get("image_type"),
                            "char_count": len(image.get("caption", "") + image.get("alt_text", "")),
                            "token_count": self._estimate_tokens(
                                image.get("caption", "") + image.get("alt_text", "")
                            )
                        }
                        
                        # Create image content
                        image_content = self._format_image_content(image)
                        
                        chunks.append({
                            "content": image_content,
                            "meta_data": chunk_meta,
                            "search_keywords": self._extract_keywords(image_content)
                        })
            
            logger.info(
                f"Created {len(chunks)} chunks - "
                f"Text: {len(text_chunks)}, Tables: {len(tables) if tables else 0}, "
                f"Images: {len([c for c in chunks if c['meta_data']['chunk_type'] == 'image'])}"
            )
            
            return chunks
            
        except Exception as e:
            logger.error(f"Error chunking document: {str(e)}", exc_info=True)
            # Return a single chunk with the full text as fallback
            return [{
                "content": text[:self.max_chunk_size],
                "meta_data": {
                    "chunk_type": "text",
                    "chunk_index": 0,
                    "char_count": len(text[:self.max_chunk_size]),
                    "token_count": self._estimate_tokens(text[:self.max_chunk_size]),
                    "error": "Chunking failed, using fallback"
                },
                "search_keywords": []
            }]
    
    def _chunk_text(self, text: str) -> List[str]:
        """Split text into chunks using smart boundary detection."""
        if not text:
            return []
        
        chunks = []
        current_chunk = []
        current_size = 0
        
        # Split by paragraphs first
        paragraphs = text.split('\n\n')
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            para_size = len(para)
            
            # If paragraph fits in current chunk
            if current_size + para_size <= self.chunk_size:
                current_chunk.append(para)
                current_size += para_size + 2  # +2 for \n\n
            else:
                # Save current chunk if not empty
                if current_chunk:
                    chunk_text = '\n\n'.join(current_chunk)
                    chunks.append(chunk_text)
                    
                    # Add overlap from end of previous chunk
                    if self.chunk_overlap > 0:
                        overlap_text = chunk_text[-self.chunk_overlap:]
                        current_chunk = [overlap_text, para]
                        current_size = len(overlap_text) + para_size + 2
                    else:
                        current_chunk = [para]
                        current_size = para_size
                else:
                    # Paragraph is larger than chunk size, split it
                    if para_size > self.max_chunk_size:
                        sub_chunks = self._split_large_paragraph(para)
                        chunks.extend(sub_chunks[:-1])
                        current_chunk = [sub_chunks[-1]]
                        current_size = len(sub_chunks[-1])
                    else:
                        current_chunk = [para]
                        current_size = para_size
        
        # Add final chunk
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        return chunks
    
    def _split_large_paragraph(self, text: str) -> List[str]:
        """Split a large paragraph into smaller chunks by sentences."""
        chunks = []
        sentences = text.replace('? ', '?|').replace('! ', '!|').replace('. ', '.|').split('|')
        
        current_chunk = []
        current_size = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sentence_size = len(sentence)
            
            if current_size + sentence_size <= self.chunk_size:
                current_chunk.append(sentence)
                current_size += sentence_size + 1
            else:
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_size = sentence_size
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def _format_table_content(self, table: Dict[str, Any]) -> str:
        """Format table as searchable text content."""
        content_parts = [
            f"[TABLE on page {table.get('page_number', '?')}]",
            ""
        ]
        
        # Add headers
        if table.get("headers"):
            content_parts.append("Headers: " + " | ".join(table["headers"]))
            content_parts.append("")
        
        # Add markdown representation
        if table.get("markdown"):
            content_parts.append(table["markdown"])
        
        # Add row count summary
        if table.get("row_count"):
            content_parts.append("")
            content_parts.append(
                f"Table contains {table['row_count']} rows and "
                f"{table.get('col_count', 0)} columns"
            )
        
        return "\n".join(content_parts)
    
    def _format_image_content(self, image: Dict[str, Any]) -> str:
        """Format image metadata as searchable text content."""
        content_parts = [
            f"[{image.get('image_type', 'IMAGE').upper()} on page {image.get('page_number', '?')}]",
            ""
        ]
        
        if image.get("caption"):
            content_parts.append(f"Caption: {image['caption']}")
        
        if image.get("alt_text") and image.get("alt_text") != image.get("caption"):
            content_parts.append(f"Description: {image['alt_text']}")
        
        return "\n".join(content_parts)
    
    def _get_structural_metadata(
        self,
        chunk_index: int,
        structure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract structural metadata for a chunk."""
        metadata = {}
        
        # Estimate page number based on chunk position
        if structure.get("pages"):
            total_pages = len(structure["pages"])
            estimated_page = int((chunk_index / total_pages) * total_pages) + 1
            metadata["estimated_page"] = min(estimated_page, total_pages)
        
        # Add section information if available
        if structure.get("sections"):
            metadata["has_sections"] = True
            metadata["section_count"] = len(structure["sections"])
        
        return metadata
    
    def _extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """Extract simple keywords from text for search optimization."""
        # Remove special characters and split
        words = text.lower().replace('\n', ' ').split()
        
        # Filter out common words and short words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
            'this', 'that', 'these', 'those', 'it', 'its', 'can', 'will', 'would'
        }
        
        keywords = [
            word.strip('.,;:!?"\'()[]{}')
            for word in words
            if len(word) > 3 and word not in stop_words
        ]
        
        # Count frequency
        keyword_freq = {}
        for word in keywords:
            keyword_freq[word] = keyword_freq.get(word, 0) + 1
        
        # Sort by frequency and return top keywords
        sorted_keywords = sorted(
            keyword_freq.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [kw[0] for kw in sorted_keywords[:max_keywords]]
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough approximation: 1 token ≈ 4 chars)."""
        return len(text) // 4
    
    def _chars_to_tokens(self, chars: int) -> int:
        """Convert character count to approximate token count."""
        return chars // 4
    
    def update_config(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        max_chunk_size: Optional[int] = None
    ):
        """Update chunking configuration."""
        if chunk_size is not None:
            self.chunk_size = chunk_size
        if chunk_overlap is not None:
            self.chunk_overlap = chunk_overlap
        if max_chunk_size is not None:
            self.max_chunk_size = max_chunk_size
        
        logger.info(
            f"ChunkingService config updated - Size: {self.chunk_size}, "
            f"Overlap: {self.chunk_overlap}, Max: {self.max_chunk_size}"
        )


# Create singleton instance
chunking_service = ChunkingService(
    chunk_size=1000,
    chunk_overlap=200,
    max_chunk_size=2000
)