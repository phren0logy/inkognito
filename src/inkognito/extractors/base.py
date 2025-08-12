"""Base extractor interface for document processing."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, Callable
from pathlib import Path
import time


@dataclass
class ExtractionResult:
    """Result from document extraction."""
    markdown_content: str
    metadata: Dict[str, Any]
    page_count: int
    extraction_method: str
    processing_time: float


class BaseExtractor(ABC):
    """Abstract base class for document extractors."""
    
    @abstractmethod
    async def extract(
        self, 
        file_path: str, 
        progress_callback: Optional[Callable] = None
    ) -> ExtractionResult:
        """
        Extract document content to markdown.
        
        Args:
            file_path: Path to the document file
            progress_callback: Optional callback for progress updates
                              Called with dict: {'current': int, 'total': int, 'percent': float}
        
        Returns:
            ExtractionResult with markdown content and metadata
        """
        pass
    
    @abstractmethod
    def validate(self, file_path: str) -> bool:
        """
        Check if file can be processed by this extractor.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if file can be processed
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if extractor is properly configured and available.
        
        Returns:
            True if extractor can be used
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the extractor."""
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> Dict[str, Any]:
        """
        Extractor capabilities and features.
        
        Example:
            {
                'supports_ocr': True,
                'supports_tables': True,
                'supports_images': False,
                'max_file_size_mb': 100,
                'supported_formats': ['.pdf', '.docx'],
                'requires_api_key': False,
                'average_speed': '5-10 seconds per page'
            }
        """
        pass
    
    def estimate_page_count(self, file_path: str) -> int:
        """
        Estimate page count for timeout calculation.
        
        Args:
            file_path: Path to document
            
        Returns:
            Estimated number of pages (default: 10)
        """
        # Default implementation - subclasses can override with actual counting
        file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)
        # Rough estimate: 1 page per 50KB
        return max(1, int(file_size_mb * 20))