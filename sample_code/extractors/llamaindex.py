"""LlamaIndex Cloud extractor implementation."""

import os
import time
import asyncio
from typing import Optional, Dict, Any, Callable
from pathlib import Path

from .base import BaseExtractor, ExtractionResult


class LlamaIndexExtractor(BaseExtractor):
    """LlamaIndex Cloud (LlamaParse) extractor."""
    
    def __init__(self):
        self.api_key = os.getenv("LLAMAPARSE_API_KEY")
    
    @property
    def name(self) -> str:
        return "LlamaIndex Cloud"
    
    @property
    def capabilities(self) -> Dict[str, Any]:
        return {
            "supports_ocr": True,
            "supports_tables": True,
            "supports_images": True,
            "max_file_size_mb": 300,
            "supported_formats": [".pdf", ".docx", ".pptx"],
            "requires_api_key": True,
            "average_speed": "1-2 seconds per page",
            "layout_preservation": True,
            "code_extraction": True,
            "formula_support": True
        }
    
    def is_available(self) -> bool:
        """Check if LlamaParse is configured."""
        return bool(self.api_key)
    
    def validate(self, file_path: str) -> bool:
        """Check if file can be processed."""
        path = Path(file_path)
        if not path.exists():
            return False
        
        # Check file extension
        if path.suffix.lower() not in self.capabilities["supported_formats"]:
            return False
        
        # Check file size
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > self.capabilities["max_file_size_mb"]:
            return False
        
        return True
    
    async def extract(
        self, 
        file_path: str, 
        progress_callback: Optional[Callable] = None
    ) -> ExtractionResult:
        """Extract document using LlamaParse."""
        start_time = time.time()
        
        try:
            from llama_parse import LlamaParse
        except ImportError:
            raise ImportError(
                "LlamaParse not installed. "
                "Install with: pip install llama-parse"
            )
        
        # Initialize parser
        parser = LlamaParse(
            api_key=self.api_key,
            result_type="markdown",
            parsing_instruction="Extract all content including tables, code blocks, and formulas. Preserve document structure."
        )
        
        if progress_callback:
            await progress_callback({"current": 0, "total": 100, "percent": 0.1})
        
        # Parse document (async operation)
        documents = await parser.aload_data(file_path)
        
        # Combine all document chunks
        markdown_content = "\n\n".join([doc.text for doc in documents])
        
        # Extract metadata
        page_count = documents[0].metadata.get("page_count", 1) if documents else 1
        metadata = {
            "processor_type": "LlamaParse",
            "page_count": page_count,
            "processing_time_seconds": time.time() - start_time,
            "document_id": documents[0].metadata.get("document_id") if documents else None
        }
        
        if progress_callback:
            await progress_callback({"current": 100, "total": 100, "percent": 1.0})
        
        return ExtractionResult(
            markdown_content=markdown_content,
            metadata=metadata,
            page_count=page_count,
            extraction_method="llamaindex",
            processing_time=time.time() - start_time
        )