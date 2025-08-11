"""Azure Document Intelligence extractor implementation."""

import os
import time
import asyncio
from typing import Optional, Dict, Any, Callable
from pathlib import Path

from .base import BaseExtractor, ExtractionResult


class AzureDIExtractor(BaseExtractor):
    """Azure Document Intelligence extractor using layout model."""
    
    def __init__(self):
        self.api_key = os.getenv("AZURE_DI_KEY")
        self.endpoint = os.getenv("AZURE_DI_ENDPOINT")
    
    @property
    def name(self) -> str:
        return "Azure Document Intelligence"
    
    @property
    def capabilities(self) -> Dict[str, Any]:
        return {
            "supports_ocr": True,
            "supports_tables": True,
            "supports_images": True,
            "max_file_size_mb": 500,
            "supported_formats": [".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff"],
            "requires_api_key": True,
            "average_speed": "0.2-1 seconds per page",
            "layout_preservation": True,
            "handwriting_support": True
        }
    
    def is_available(self) -> bool:
        """Check if Azure DI is configured."""
        return bool(self.api_key and self.endpoint)
    
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
        """Extract document using Azure DI."""
        start_time = time.time()
        
        try:
            from azure.ai.documentintelligence import DocumentIntelligenceClient
            from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
            from azure.core.credentials import AzureKeyCredential
        except ImportError:
            raise ImportError(
                "Azure Document Intelligence SDK not installed. "
                "Install with: pip install azure-ai-documentintelligence"
            )
        
        # Initialize client
        client = DocumentIntelligenceClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.api_key)
        )
        
        # Read file
        with open(file_path, "rb") as f:
            document_bytes = f.read()
        
        # Start analysis
        if progress_callback:
            await progress_callback({"current": 0, "total": 100, "percent": 0.1})
        
        # Analyze document using layout model
        poller = client.begin_analyze_document(
            model_id="prebuilt-layout",
            body=AnalyzeDocumentRequest(bytes_source=document_bytes)
        )
        
        # Poll for completion with progress updates
        while not poller.done():
            if progress_callback:
                # Estimate progress based on polling
                percent = min(0.9, 0.1 + (time.time() - start_time) / 30)
                await progress_callback({
                    "current": int(percent * 100), 
                    "total": 100, 
                    "percent": percent
                })
            await asyncio.sleep(1)
        
        # Get result
        result = poller.result()
        
        # Convert to markdown
        markdown_content = self._convert_to_markdown(result)
        
        # Extract metadata
        page_count = len(result.pages) if result.pages else 1
        metadata = {
            "processor_type": "Azure Document Intelligence",
            "model_id": "prebuilt-layout",
            "page_count": page_count,
            "language": result.languages[0] if result.languages else "unknown",
            "content_format": result.content_format,
            "processing_time_seconds": time.time() - start_time
        }
        
        if progress_callback:
            await progress_callback({"current": 100, "total": 100, "percent": 1.0})
        
        return ExtractionResult(
            markdown_content=markdown_content,
            metadata=metadata,
            page_count=page_count,
            extraction_method="azure_di",
            processing_time=time.time() - start_time
        )
    
    def _convert_to_markdown(self, result) -> str:
        """Convert Azure DI result to markdown."""
        # This is a simplified version - in production you'd want more sophisticated conversion
        markdown_lines = []
        
        # Process paragraphs
        if hasattr(result, 'paragraphs') and result.paragraphs:
            for para in result.paragraphs:
                if para.role == "title":
                    markdown_lines.append(f"# {para.content}\n")
                elif para.role == "sectionHeading":
                    markdown_lines.append(f"## {para.content}\n")
                else:
                    markdown_lines.append(f"{para.content}\n")
        
        # Process tables
        if hasattr(result, 'tables') and result.tables:
            for table in result.tables:
                markdown_lines.append(self._table_to_markdown(table))
                markdown_lines.append("")
        
        # Fallback to raw content if no structured data
        if not markdown_lines and hasattr(result, 'content'):
            markdown_lines.append(result.content)
        
        return "\n".join(markdown_lines)
    
    def _table_to_markdown(self, table) -> str:
        """Convert Azure DI table to markdown table."""
        if not table.cells:
            return ""
        
        # Build table structure
        max_row = max(cell.row_index for cell in table.cells)
        max_col = max(cell.column_index for cell in table.cells)
        
        # Initialize grid
        grid = [["" for _ in range(max_col + 1)] for _ in range(max_row + 1)]
        
        # Fill grid
        for cell in table.cells:
            grid[cell.row_index][cell.column_index] = cell.content or ""
        
        # Convert to markdown
        lines = []
        for i, row in enumerate(grid):
            lines.append("| " + " | ".join(row) + " |")
            if i == 0:  # Add header separator
                lines.append("| " + " | ".join(["-" * max(3, len(cell)) for cell in row]) + " |")
        
        return "\n".join(lines)