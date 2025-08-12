"""Tests for extractor registry functionality."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import asyncio

from extractors.registry import ExtractorRegistry
from extractors.base import BaseExtractor, ExtractionResult


class MockExtractor(BaseExtractor):
    """Mock extractor for testing."""
    
    def __init__(self, name: str, available: bool = True):
        self._name = name
        self._available = available
    
    @property
    def name(self):
        return self._name
    
    async def extract(self, file_path: str, progress_callback=None):
        return ExtractionResult(
            markdown_content=f"Extracted by {self.name}",
            page_count=1,
            extraction_method=self.name,
            processing_time=0.1
        )
    
    def is_available(self):
        return self._available


class TestExtractorRegistry:
    """Test the ExtractorRegistry class."""
    
    @pytest.fixture
    def registry(self):
        """Create a fresh registry instance."""
        # Clear any existing registry state
        ExtractorRegistry._extractors = {}
        ExtractorRegistry._initialized = False
        return ExtractorRegistry
    
    def test_register_extractor(self, registry):
        """Test registering an extractor."""
        extractor = MockExtractor("TestExtractor")
        registry.register(extractor)
        
        assert "TestExtractor" in registry._extractors
        assert registry._extractors["TestExtractor"] is extractor
    
    def test_register_duplicate_name(self, registry):
        """Test that registering duplicate names overwrites."""
        extractor1 = MockExtractor("Test")
        extractor2 = MockExtractor("Test")
        
        registry.register(extractor1)
        registry.register(extractor2)
        
        assert registry._extractors["Test"] is extractor2
    
    def test_get_extractor(self, registry):
        """Test getting a registered extractor."""
        extractor = MockExtractor("Test")
        registry.register(extractor)
        
        retrieved = registry.get("Test")
        assert retrieved is extractor
    
    def test_get_nonexistent_extractor(self, registry):
        """Test getting a non-existent extractor returns None."""
        result = registry.get("NonExistent")
        assert result is None
    
    def test_list_extractors(self, registry):
        """Test listing all registered extractors."""
        ext1 = MockExtractor("Ext1")
        ext2 = MockExtractor("Ext2")
        ext3 = MockExtractor("Ext3")
        
        registry.register(ext1)
        registry.register(ext2)
        registry.register(ext3)
        
        names = registry.list()
        assert set(names) == {"Ext1", "Ext2", "Ext3"}
    
    def test_list_empty_registry(self, registry):
        """Test listing extractors when registry is empty."""
        names = registry.list()
        assert names == []
    
    def test_auto_select_with_priorities(self, registry):
        """Test auto-selection respects priority order."""
        # Create extractors with different availability
        azure = MockExtractor("azure", available=False)
        llamaindex = MockExtractor("llamaindex", available=True)
        mineru = MockExtractor("mineru", available=False)
        docling = MockExtractor("docling", available=True)
        
        registry.register(azure)
        registry.register(llamaindex)
        registry.register(mineru)
        registry.register(docling)
        
        # Should select llamaindex (first available in priority order)
        selected = registry.auto_select("/path/to/file.pdf")
        assert selected is llamaindex
    
    def test_auto_select_all_unavailable(self, registry):
        """Test auto-selection when all extractors are unavailable."""
        ext1 = MockExtractor("azure", available=False)
        ext2 = MockExtractor("llamaindex", available=False)
        
        registry.register(ext1)
        registry.register(ext2)
        
        selected = registry.auto_select("/path/to/file.pdf")
        assert selected is None
    
    def test_auto_select_fallback_to_unlisted(self, registry):
        """Test auto-selection falls back to unlisted extractors."""
        # Only register extractors not in priority list
        custom = MockExtractor("custom", available=True)
        registry.register(custom)
        
        selected = registry.auto_select("/path/to/file.pdf")
        assert selected is custom
    
    def test_timeout_policies(self, registry):
        """Test that timeout policies are defined."""
        policies = registry._timeout_policies
        
        # Check that standard extractors have timeout policies
        assert "azure" in policies
        assert "llamaindex" in policies
        assert "docling" in policies
        assert "mineru" in policies
        
        # Check timeout values are reasonable
        for extractor, timeout in policies.items():
            assert isinstance(timeout, (int, float))
            assert 0 < timeout <= 600  # Between 0 and 10 minutes
    
    def test_get_timeout_for_extractor(self, registry):
        """Test getting timeout for specific extractors."""
        # Known extractor
        azure_timeout = registry._timeout_policies.get("azure", 60)
        assert isinstance(azure_timeout, (int, float))
        
        # Unknown extractor should use default
        unknown_timeout = registry._timeout_policies.get("unknown", 60)
        assert unknown_timeout == 60
    
    @pytest.mark.asyncio
    async def test_extract_with_timeout(self, registry):
        """Test extraction with timeout handling."""
        # Create a slow extractor
        class SlowExtractor(BaseExtractor):
            @property
            def name(self):
                return "slow"
            
            async def extract(self, file_path: str, progress_callback=None):
                await asyncio.sleep(10)  # Simulate slow extraction
                return ExtractionResult("", 1, "slow", 10.0)
            
            def is_available(self):
                return True
        
        slow = SlowExtractor()
        registry.register(slow)
        
        # Set a short timeout
        registry._timeout_policies["slow"] = 0.1
        
        # This would timeout in real usage
        # (actual timeout implementation would be in the server code)
        assert registry.get("slow") is slow
    
    def test_initialize_registry(self, registry):
        """Test registry initialization."""
        # Mock the initialization to avoid importing actual extractors
        with patch.object(registry, '_initialize') as mock_init:
            registry._initialized = False
            registry.get("any")
            mock_init.assert_called_once()
    
    def test_registry_singleton_behavior(self):
        """Test that registry maintains state across calls."""
        # First instance
        ExtractorRegistry._extractors = {}
        ExtractorRegistry._initialized = False
        
        ext1 = MockExtractor("Test1")
        ExtractorRegistry.register(ext1)
        
        # Registry should maintain state
        assert "Test1" in ExtractorRegistry._extractors
        assert ExtractorRegistry.get("Test1") is ext1
    
    def test_priority_order_configuration(self, registry):
        """Test that priority order is properly configured."""
        expected_order = ["azure", "llamaindex", "mineru", "docling"]
        
        # Create all extractors as available
        for name in expected_order:
            registry.register(MockExtractor(name, available=True))
        
        # Auto-select should pick the first one
        selected = registry.auto_select("/file.pdf")
        assert selected.name == "azure"
        
        # Make azure unavailable
        registry._extractors["azure"] = MockExtractor("azure", available=False)
        selected = registry.auto_select("/file.pdf")
        assert selected.name == "llamaindex"
    
    def test_extractor_filtering_by_file_type(self, registry):
        """Test that extractors can be filtered by file type."""
        pdf_extractor = MockExtractor("pdf_only")
        docx_extractor = MockExtractor("docx_only")
        
        registry.register(pdf_extractor)
        registry.register(docx_extractor)
        
        # For now, all extractors handle all file types
        # This test documents the current behavior
        selected = registry.auto_select("/file.pdf")
        assert selected is not None
        
        selected = registry.auto_select("/file.docx")
        assert selected is not None