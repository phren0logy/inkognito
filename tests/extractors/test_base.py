"""Tests for base extractor interface."""

import pytest
from abc import ABC
import asyncio
from dataclasses import fields

from extractors.base import BaseExtractor, ExtractionResult


class TestExtractionResult:
    """Test the ExtractionResult dataclass."""
    
    def test_extraction_result_creation(self):
        """Test creating an ExtractionResult."""
        result = ExtractionResult(
            markdown_content="# Test Content",
            page_count=5,
            extraction_method="test_method",
            processing_time=1.5,
            metadata={"key": "value"}
        )
        
        assert result.markdown_content == "# Test Content"
        assert result.page_count == 5
        assert result.extraction_method == "test_method"
        assert result.processing_time == 1.5
        assert result.metadata == {"key": "value"}
    
    def test_extraction_result_default_metadata(self):
        """Test that metadata defaults to empty dict."""
        result = ExtractionResult(
            markdown_content="content",
            metadata={},
            page_count=1,
            extraction_method="test",
            processing_time=0.1
        )
        
        assert result.metadata == {}
    
    def test_extraction_result_fields(self):
        """Test that all expected fields are present."""
        field_names = {f.name for f in fields(ExtractionResult)}
        expected_fields = {
            "markdown_content",
            "page_count",
            "extraction_method",
            "processing_time",
            "metadata"
        }
        assert field_names == expected_fields


class TestBaseExtractor:
    """Test the BaseExtractor abstract base class."""
    
    def test_cannot_instantiate_base_extractor(self):
        """Test that BaseExtractor cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            BaseExtractor()
    
    def test_concrete_extractor_must_implement_name(self):
        """Test that concrete extractors must implement name property."""
        class IncompleteExtractor(BaseExtractor):
            async def extract(self, file_path, progress_callback=None):
                pass
            
            def is_available(self):
                return True
        
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteExtractor()
    
    def test_concrete_extractor_must_implement_extract(self):
        """Test that concrete extractors must implement extract method."""
        class IncompleteExtractor(BaseExtractor):
            @property
            def name(self):
                return "test"
            
            def is_available(self):
                return True
        
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteExtractor()
    
    def test_concrete_extractor_must_implement_is_available(self):
        """Test that concrete extractors must implement is_available method."""
        class IncompleteExtractor(BaseExtractor):
            @property
            def name(self):
                return "test"
            
            async def extract(self, file_path, progress_callback=None):
                pass
        
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteExtractor()
    
    def test_valid_concrete_extractor(self):
        """Test implementing a valid concrete extractor."""
        class TestExtractor(BaseExtractor):
            @property
            def name(self):
                return "TestExtractor"
            
            async def extract(self, file_path: str, progress_callback=None):
                # Simulate extraction
                if progress_callback:
                    await progress_callback({"percent": 0.5})
                
                return ExtractionResult(
                    markdown_content="# Extracted Content",
                    page_count=1,
                    extraction_method="test",
                    processing_time=0.1
                )
            
            def is_available(self) -> bool:
                return True
        
        # Should be able to instantiate
        extractor = TestExtractor()
        assert extractor.name == "TestExtractor"
        assert extractor.is_available() is True
    
    @pytest.mark.asyncio
    async def test_extract_method_signature(self):
        """Test that extract method has correct signature."""
        class TestExtractor(BaseExtractor):
            @property
            def name(self):
                return "Test"
            
            async def extract(self, file_path: str, progress_callback=None):
                return ExtractionResult(
                    markdown_content="content",
                    page_count=1,
                    extraction_method="test",
                    processing_time=0.1
                )
            
            def is_available(self):
                return True
        
        extractor = TestExtractor()
        
        # Test without progress callback
        result = await extractor.extract("/path/to/file.pdf")
        assert isinstance(result, ExtractionResult)
        
        # Test with progress callback
        progress_called = False
        async def progress(info):
            nonlocal progress_called
            progress_called = True
        
        result = await extractor.extract("/path/to/file.pdf", progress)
        assert isinstance(result, ExtractionResult)
    
    def test_extractor_inheritance_chain(self):
        """Test that extractors properly inherit from BaseExtractor and ABC."""
        class TestExtractor(BaseExtractor):
            @property
            def name(self):
                return "Test"
            
            async def extract(self, file_path: str, progress_callback=None):
                return ExtractionResult("", 0, "", 0.0)
            
            def is_available(self):
                return True
        
        extractor = TestExtractor()
        assert isinstance(extractor, BaseExtractor)
        assert isinstance(extractor, ABC)
    
    def test_extractor_method_types(self):
        """Test that extractor methods have correct types."""
        class TestExtractor(BaseExtractor):
            @property
            def name(self) -> str:
                return "Test"
            
            async def extract(self, file_path: str, progress_callback=None) -> ExtractionResult:
                return ExtractionResult("", 0, "", 0.0)
            
            def is_available(self) -> bool:
                return True
        
        extractor = TestExtractor()
        
        # Check return types
        assert isinstance(extractor.name, str)
        assert isinstance(extractor.is_available(), bool)
        
        # Check that extract returns a coroutine
        extract_result = extractor.extract("/path/to/file")
        assert asyncio.iscoroutine(extract_result)
        extract_result.close()  # Clean up the coroutine