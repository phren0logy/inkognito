"""Azure Document Intelligence extractor (placeholder)."""

import os
import time
from typing import Dict, Any, Optional, Callable
import logging

from .base import BaseExtractor, ExtractionResult

logger = logging.getLogger(__name__)


class AzureDIExtractor(BaseExtractor):
    """Azure Document Intelligence extractor."""
    
    def __init__(self):
        self.api_key = os.getenv("AZURE_DI_KEY")
    
    async def extract(
        self, 
        file_path: str, 
        progress_callback: Optional[Callable] = None
    ) -> ExtractionResult:
        """Extract document using Azure Document Intelligence."""
        start_time = time.time()
        
        # Placeholder implementation
        # In a real implementation, this would:
        # 1. Upload document to Azure
        # 2. Process with Document Intelligence
        # 3. Convert to markdown
        # 4. Return results
        
        raise NotImplementedError("Azure DI extractor not yet implemented")
    
    def validate(self, file_path: str) -> bool:
        """Check if file can be processed."""
        return file_path.lower().endswith(('.pdf', '.docx'))
    
    def is_available(self) -> bool:
        """Check if Azure DI is configured."""
        return bool(self.api_key)
    
    @property
    def name(self) -> str:
        return "Azure Document Intelligence"
    
    @property
    def capabilities(self) -> Dict[str, Any]:
        return {
            'supports_ocr': True,
            'supports_tables': True,
            'supports_images': True,
            'max_file_size_mb': 500,
            'supported_formats': ['.pdf', '.docx'],
            'requires_api_key': True,
            'average_speed': '0.2-1 seconds per page'
        }