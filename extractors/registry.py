"""Extractor registry and auto-discovery."""

from typing import Dict, Type, Optional, List, Any
import os
import logging
from pathlib import Path

from .base import BaseExtractor, ExtractionResult

logger = logging.getLogger(__name__)


class ExtractorRegistry:
    """Registry for document extractor discovery and management."""
    
    def __init__(self):
        self._extractors: Dict[str, BaseExtractor] = {}
        self._timeout_policies: Dict[str, Dict[str, int]] = {
            # Cloud extractors - generally faster
            "azure": {"default": 300, "per_page": 2, "max": 900},
            "llamaindex": {"default": 600, "per_page": 3, "max": 1200},
            # Local extractors - can be slower
            "docling": {"default": 900, "per_page": 10, "max": 1800},
            "mineru": {"default": 1200, "per_page": 7, "max": 2400}
        }
    
    def register(self, name: str, extractor: BaseExtractor) -> None:
        """
        Register an extractor.
        
        Args:
            name: Unique name for the extractor
            extractor: Extractor instance
        """
        self._extractors[name] = extractor
        logger.info(f"Registered extractor: {name} ({extractor.name})")
    
    def get(self, name: str) -> Optional[BaseExtractor]:
        """
        Get an extractor by name.
        
        Args:
            name: Extractor name
            
        Returns:
            Extractor instance or None
        """
        return self._extractors.get(name)
    
    def list_available(self) -> List[Dict[str, Any]]:
        """
        List all registered extractors and their availability.
        
        Returns:
            List of extractor info dictionaries
        """
        available = []
        for name, extractor in self._extractors.items():
            try:
                is_available = extractor.is_available()
            except Exception as e:
                logger.warning(f"Error checking availability for {name}: {e}")
                is_available = False
            
            available.append({
                "name": name,
                "display_name": extractor.name,
                "available": is_available,
                "capabilities": extractor.capabilities,
                "type": "cloud" if extractor.capabilities.get("requires_api_key") else "local"
            })
        
        return available
    
    def get_timeout_policy(self, extractor_name: str, page_count: int = 1) -> int:
        """
        Get timeout for an extractor based on page count.
        
        Args:
            extractor_name: Name of the extractor
            page_count: Number of pages to process
            
        Returns:
            Timeout in seconds
        """
        # Allow override from environment
        env_timeout = os.getenv("INKOGNITO_EXTRACTION_TIMEOUT")
        if env_timeout:
            try:
                return int(env_timeout)
            except ValueError:
                pass
        
        # Use per-extractor policy
        policy = self._timeout_policies.get(extractor_name, {})
        default = policy.get("default", 600)
        per_page = policy.get("per_page", 10)
        max_timeout = policy.get("max", 3600)
        
        calculated = min(default + (page_count * per_page), max_timeout)
        return calculated
    
    def auto_select(self, file_path: str) -> Optional[BaseExtractor]:
        """
        Automatically select the best available extractor.
        
        Priority order:
        1. Cloud extractors (faster when available)
        2. Advanced local extractors
        3. Basic local extractors
        
        Args:
            file_path: Path to document
            
        Returns:
            Best available extractor or None
        """
        priority_order = ["azure", "llamaindex", "mineru", "docling"]
        
        for name in priority_order:
            extractor = self.get(name)
            if extractor and extractor.is_available() and extractor.validate(file_path):
                logger.info(f"Auto-selected extractor: {name}")
                return extractor
        
        logger.warning("No suitable extractor found")
        return None


# Global registry instance
registry = ExtractorRegistry()


# Auto-register extractors when available
def _auto_register():
    """Auto-register available extractors."""
    
    # Try to import and register each extractor
    # Note: Only Docling is currently implemented, others are placeholders
    extractors_to_try = [
        # ("azure_di", "AzureDIExtractor", "azure"),        # Not implemented
        # ("llamaindex", "LlamaIndexExtractor", "llamaindex"),  # Not implemented
        ("docling", "DoclingExtractor", "docling"),
        # ("mineru", "MinerUExtractor", "mineru")           # Not implemented
    ]
    
    for module_name, class_name, registry_name in extractors_to_try:
        try:
            module = __import__(f"extractors.{module_name}", fromlist=[class_name])
            extractor_class = getattr(module, class_name)
            extractor = extractor_class()
            registry.register(registry_name, extractor)
        except ImportError as e:
            logger.debug(f"Extractor {module_name} not available: {e}")
        except Exception as e:
            logger.warning(f"Failed to register {module_name}: {e}")


# Run auto-registration on import
_auto_register()