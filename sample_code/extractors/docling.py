"""Docling local extractor implementation."""

import time
import asyncio
from typing import Optional, Dict, Any, Callable
from pathlib import Path
import logging

from .base import BaseExtractor, ExtractionResult

logger = logging.getLogger(__name__)


class DoclingExtractor(BaseExtractor):
    """IBM Docling extractor for local PDF processing."""
    
    @property
    def name(self) -> str:
        return "Docling (Local)"
    
    @property
    def capabilities(self) -> Dict[str, Any]:
        return {
            "supports_ocr": True,
            "supports_tables": True,
            "supports_images": False,
            "max_file_size_mb": 200,
            "supported_formats": [".pdf", ".docx", ".pptx", ".html", ".md"],
            "requires_api_key": False,
            "average_speed": "5-10 seconds per page",
            "layout_preservation": True,
            "local_processing": True
        }
    
    def is_available(self) -> bool:
        """Check if Docling is available."""
        try:
            import docling
            return True
        except ImportError:
            return False
    
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
    
    def estimate_page_count(self, file_path: str) -> int:
        """Estimate page count for PDFs."""
        if Path(file_path).suffix.lower() == ".pdf":
            try:
                import pypdf
                with open(file_path, 'rb') as f:
                    reader = pypdf.PdfReader(f)
                    return len(reader.pages)
            except Exception:
                pass
        
        # Fall back to base implementation
        return super().estimate_page_count(file_path)
    
    async def extract(
        self, 
        file_path: str, 
        progress_callback: Optional[Callable] = None
    ) -> ExtractionResult:
        """Extract document using Docling."""
        start_time = time.time()
        
        try:
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.base_models import InputFormat
        except ImportError:
            raise ImportError(
                "Docling not installed. "
                "Install with: pip install docling"
            )
        
        # Estimate page count for progress
        page_count = self.estimate_page_count(file_path)
        
        if progress_callback:
            await progress_callback({"current": 0, "total": page_count, "percent": 0.0})
        
        # Configure Docling
        pdf_options = PdfFormatOption(
            do_ocr=True,  # Enable OCR for scanned documents
            do_table_structure=True,  # Extract table structure
        )
        
        converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF, InputFormat.DOCX, InputFormat.PPTX],
            format_options={InputFormat.PDF: pdf_options}
        )
        
        # Run extraction in thread pool (Docling is CPU-intensive)
        loop = asyncio.get_event_loop()
        
        # Create progress tracking wrapper
        processed_pages = 0
        
        async def progress_wrapper():
            nonlocal processed_pages
            while processed_pages < page_count:
                # Simulate progress based on time
                elapsed = time.time() - start_time
                estimated_progress = min(0.95, elapsed / (page_count * 7))  # ~7 sec/page
                processed_pages = int(estimated_progress * page_count)
                
                if progress_callback:
                    await progress_callback({
                        "current": processed_pages,
                        "total": page_count,
                        "percent": estimated_progress
                    })
                
                await asyncio.sleep(1)
        
        # Start progress tracking
        progress_task = asyncio.create_task(progress_wrapper())
        
        try:
            # Run conversion in executor
            result = await loop.run_in_executor(
                None,
                converter.convert,
                file_path
            )
            
            # Cancel progress tracking
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass
            
            # Convert to markdown
            markdown_content = result.document.export_to_markdown()
            
            # Extract metadata
            metadata = {
                "processor_type": "Docling",
                "page_count": page_count,
                "format": Path(file_path).suffix.lower(),
                "processing_time_seconds": time.time() - start_time,
                "ocr_applied": pdf_options.do_ocr,
                "tables_extracted": pdf_options.do_table_structure
            }
            
            if progress_callback:
                await progress_callback({
                    "current": page_count,
                    "total": page_count,
                    "percent": 1.0
                })
            
            return ExtractionResult(
                markdown_content=markdown_content,
                metadata=metadata,
                page_count=page_count,
                extraction_method="docling",
                processing_time=time.time() - start_time
            )
            
        except Exception as e:
            # Cancel progress tracking on error
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass
            raise e