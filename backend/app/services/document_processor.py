"""
Document processing service using IBM's Docling for enhanced document parsing.
Handles PDF, DOCX, PPTX, and other document formats with AI-powered extraction.
"""
import io
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling_core.types.doc import ImageRefMode, PictureItem, TableItem

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Advanced document processor using Docling for AI-powered extraction.
    
    Features:
    - Multi-format support (PDF, DOCX, PPTX, HTML, images)
    - AI-powered table extraction with TableFormer
    - Image captioning with SmolDocling VLM
    - OCR support for scanned documents
    - Hierarchical structure preservation
    - Rich metadata extraction
    """
    
    def __init__(
        self,
        extract_tables: bool = True,
        extract_images: bool = True,
        ocr_enabled: bool = True,
        table_mode: str = "accurate"
    ):
        """
        Initialize document processor with Docling.
        
        Args:
            extract_tables: Enable AI table extraction
            extract_images: Enable image extraction and captioning
            ocr_enabled: Enable OCR for scanned documents
            table_mode: "fast" or "accurate" for TableFormer
        """
        self.extract_tables = extract_tables
        self.extract_images = extract_images
        self.ocr_enabled = ocr_enabled
        
        # Configure Docling pipeline
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_table_structure = extract_tables
        pipeline_options.do_ocr = ocr_enabled
        
        # Set TableFormer mode
        if table_mode == "accurate":
            pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE
        else:
            pipeline_options.table_structure_options.mode = TableFormerMode.FAST
        
        # Initialize converter
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        
        logger.info(
            f"DocumentProcessor initialized - Tables: {extract_tables}, "
            f"Images: {extract_images}, OCR: {ocr_enabled}, Mode: {table_mode}"
        )
    
    def process_document(
        self,
        file_path: str,
        file_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a document and extract all content with metadata.
        
        Args:
            file_path: Path to the document file
            file_type: File extension (pdf, docx, etc.)
            
        Returns:
            Dict containing:
                - text: Full text content
                - tables: List of extracted tables
                - images: List of extracted images with captions
                - metadata: Document metadata
                - structure: Hierarchical document structure
        """
        try:
            start_time = datetime.utcnow()
            
            # Convert document
            result = self.converter.convert(file_path)
            
            # Extract document
            doc = result.document
            
            # Get full text
            text = doc.export_to_markdown()
            
            # Extract tables
            tables = []
            if self.extract_tables:
                tables = self._extract_tables(doc)
            
            # Extract images
            images = []
            if self.extract_images:
                images = self._extract_images(doc)
            
            # Extract metadata
            metadata = self._extract_metadata(doc, file_path)
            
            # Extract structure
            structure = self._extract_structure(doc)
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            return {
                "text": text,
                "tables": tables,
                "images": images,
                "metadata": metadata,
                "structure": structure,
                "success": True,
                "processing_time": processing_time,
                "page_count": len(doc.pages),
                "char_count": len(text),
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {str(e)}", exc_info=True)
            return {
                "text": "",
                "tables": [],
                "images": [],
                "metadata": {},
                "structure": {},
                "success": False,
                "processing_time": 0,
                "page_count": 0,
                "char_count": 0,
                "error": str(e)
            }
    
    def process_from_bytes(
        self,
        file_bytes: bytes,
        filename: str,
        file_type: str
    ) -> Dict[str, Any]:
        """
        Process document from bytes (for uploaded files).
        
        Args:
            file_bytes: Document bytes
            filename: Original filename
            file_type: File extension
            
        Returns:
            Processing result dict
        """
        try:
            # Write to temp file
            temp_path = Path(f"/tmp/{filename}")
            temp_path.write_bytes(file_bytes)
            
            # Process
            result = self.process_document(str(temp_path), file_type)
            
            # Cleanup
            temp_path.unlink(missing_ok=True)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing bytes for {filename}: {str(e)}", exc_info=True)
            return {
                "text": "",
                "tables": [],
                "images": [],
                "metadata": {},
                "structure": {},
                "success": False,
                "processing_time": 0,
                "page_count": 0,
                "char_count": 0,
                "error": str(e)
            }
    
    def _extract_tables(self, doc) -> List[Dict[str, Any]]:
        """Extract tables with structure preservation."""
        tables = []
        
        try:
            for page_idx, page in enumerate(doc.pages):
                for item in page.items:
                    if isinstance(item, TableItem):
                        # Get table as markdown
                        table_markdown = item.export_to_markdown()
                        
                        # Extract headers and rows
                        headers = []
                        rows = []
                        
                        if hasattr(item, 'data') and item.data:
                            # Parse table data if available
                            if item.data.grid:
                                for row_idx, row in enumerate(item.data.grid):
                                    row_cells = [cell.text if cell else "" for cell in row]
                                    if row_idx == 0:
                                        headers = row_cells
                                    else:
                                        rows.append(row_cells)
                        
                        tables.append({
                            "page_number": page_idx + 1,
                            "table_index": len([t for t in tables if t["page_number"] == page_idx + 1]),
                            "markdown": table_markdown,
                            "headers": headers,
                            "rows": rows,
                            "row_count": len(rows),
                            "col_count": len(headers) if headers else 0,
                            "meta_data": {
                                "bbox": item.prov[0].bbox.as_tuple() if item.prov else None,
                                "confidence": getattr(item, 'confidence', None)
                            }
                        })
            
            logger.info(f"Extracted {len(tables)} tables from document")
            
        except Exception as e:
            logger.error(f"Error extracting tables: {str(e)}", exc_info=True)
        
        return tables
    
    def _extract_images(self, doc) -> List[Dict[str, Any]]:
        """Extract images with AI-generated captions."""
        images = []
        
        try:
            for page_idx, page in enumerate(doc.pages):
                for item in page.items:
                    if isinstance(item, PictureItem):
                        # Get image caption/alt text
                        caption = item.caption if hasattr(item, 'caption') else None
                        
                        # Determine image type
                        image_type = "figure"
                        if hasattr(item, 'label'):
                            label = item.label.lower()
                            if 'chart' in label or 'graph' in label:
                                image_type = "chart"
                            elif 'diagram' in label:
                                image_type = "diagram"
                            elif 'photo' in label:
                                image_type = "photo"
                        
                        images.append({
                            "page_number": page_idx + 1,
                            "image_index": len([i for i in images if i["page_number"] == page_idx + 1]),
                            "caption": caption,
                            "alt_text": item.text if hasattr(item, 'text') else caption,
                            "image_type": image_type,
                            "meta_data": {
                                "bbox": item.prov[0].bbox.as_tuple() if item.prov else None,
                                "image_format": getattr(item, 'image_format', None)
                            }
                        })
            
            logger.info(f"Extracted {len(images)} images from document")
            
        except Exception as e:
            logger.error(f"Error extracting images: {str(e)}", exc_info=True)
        
        return images
    
    def _extract_metadata(self, doc, file_path: str) -> Dict[str, Any]:
        """Extract document metadata."""
        metadata = {
            "file_path": file_path,
            "page_count": len(doc.pages),
            "processed_at": datetime.utcnow().isoformat()
        }
        
        # Add document properties if available
        if hasattr(doc, 'properties'):
            props = doc.properties
            metadata.update({
                "title": getattr(props, 'title', None),
                "author": getattr(props, 'author', None),
                "subject": getattr(props, 'subject', None),
                "keywords": getattr(props, 'keywords', None),
                "creator": getattr(props, 'creator', None),
                "producer": getattr(props, 'producer', None),
                "creation_date": getattr(props, 'creation_date', None),
                "modification_date": getattr(props, 'modification_date', None)
            })
        
        return metadata
    
    def _extract_structure(self, doc) -> Dict[str, Any]:
        """Extract hierarchical document structure."""
        structure = {
            "pages": [],
            "has_toc": False,
            "sections": []
        }
        
        try:
            for page_idx, page in enumerate(doc.pages):
                page_structure = {
                    "page_number": page_idx + 1,
                    "item_count": len(page.items),
                    "has_tables": any(isinstance(item, TableItem) for item in page.items),
                    "has_images": any(isinstance(item, PictureItem) for item in page.items)
                }
                structure["pages"].append(page_structure)
            
            # Extract table of contents if available
            if hasattr(doc, 'outline') and doc.outline:
                structure["has_toc"] = True
                structure["sections"] = [
                    {
                        "title": item.title,
                        "level": item.level,
                        "page": item.page_number
                    }
                    for item in doc.outline
                ]
            
        except Exception as e:
            logger.error(f"Error extracting structure: {str(e)}", exc_info=True)
        
        return structure
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported document formats."""
        return [
            "pdf",
            "docx",
            "pptx",
            "html",
            "md",
            "asciidoc",
            "png",
            "jpg",
            "jpeg",
            "tiff",
            "bmp"
        ]
    
    def validate_file_type(self, file_type: str) -> bool:
        """Check if file type is supported."""
        return file_type.lower().lstrip('.') in self.get_supported_formats()


# Create singleton instance
document_processor = DocumentProcessor(
    extract_tables=True,
    extract_images=True,
    ocr_enabled=True,
    table_mode="accurate"
)