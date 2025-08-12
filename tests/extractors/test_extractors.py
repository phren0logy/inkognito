"""Tests for individual extractor implementations."""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import os
from pathlib import Path

from extractors.base import ExtractionResult
from extractors.azure_di import AzureDIExtractor
from extractors.llamaindex import LlamaIndexExtractor
from extractors.docling import DoclingExtractor
from extractors.mineru import MinerUExtractor


class TestAzureDIExtractor:
    """Test Azure Document Intelligence extractor."""
    
    @pytest.fixture
    def extractor(self):
        return AzureDIExtractor()
    
    def test_name(self, extractor):
        """Test extractor name."""
        assert extractor.name == "azure"
    
    def test_is_available_no_key(self, extractor):
        """Test availability check without API key."""
        with patch.dict(os.environ, {}, clear=True):
            assert extractor.is_available() is False
    
    def test_is_available_with_key(self, extractor):
        """Test availability check with API key."""
        with patch.dict(os.environ, {"AZURE_DI_KEY": "test-key"}):
            # Mock the import check
            with patch.object(extractor, '_check_imports', return_value=True):
                assert extractor.is_available() is True
    
    def test_is_available_missing_imports(self, extractor):
        """Test availability when Azure SDK is not installed."""
        with patch.dict(os.environ, {"AZURE_DI_KEY": "test-key"}):
            with patch.object(extractor, '_check_imports', return_value=False):
                assert extractor.is_available() is False
    
    @pytest.mark.asyncio
    async def test_extract_success(self, extractor):
        """Test successful extraction."""
        # Mock Azure client
        mock_client = Mock()
        mock_poller = AsyncMock()
        mock_result = Mock()
        mock_result.content = "# Extracted Content\n\nThis is extracted text."
        mock_result.pages = [Mock(), Mock()]  # 2 pages
        
        mock_poller.result.return_value = mock_result
        mock_client.begin_analyze_document.return_value = mock_poller
        
        with patch('extractors.azure_di.DocumentIntelligenceClient', return_value=mock_client):
            with patch('builtins.open', mock_open(read_data=b'PDF content')):
                result = await extractor.extract("/test/file.pdf")
        
        assert isinstance(result, ExtractionResult)
        assert result.extraction_method == "azure"
        assert result.page_count == 2
        assert "Extracted Content" in result.markdown_content
    
    @pytest.mark.asyncio
    async def test_extract_with_progress(self, extractor):
        """Test extraction with progress callback."""
        progress_calls = []
        
        async def progress_callback(info):
            progress_calls.append(info)
        
        # Mock extraction
        with patch.object(extractor, '_extract_with_azure', return_value=ExtractionResult(
            markdown_content="Test",
            page_count=1,
            extraction_method="azure",
            processing_time=0.1
        )):
            await extractor.extract("/test/file.pdf", progress_callback)
        
        # Should have progress calls
        assert len(progress_calls) > 0
    
    @pytest.mark.asyncio
    async def test_extract_error_handling(self, extractor):
        """Test error handling during extraction."""
        with patch('extractors.azure_di.DocumentIntelligenceClient', side_effect=Exception("API Error")):
            with pytest.raises(Exception, match="API Error"):
                await extractor.extract("/test/file.pdf")


class TestLlamaIndexExtractor:
    """Test LlamaIndex extractor."""
    
    @pytest.fixture
    def extractor(self):
        return LlamaIndexExtractor()
    
    def test_name(self, extractor):
        """Test extractor name."""
        assert extractor.name == "llamaindex"
    
    def test_is_available_no_key(self, extractor):
        """Test availability without API key."""
        with patch.dict(os.environ, {}, clear=True):
            assert extractor.is_available() is False
    
    def test_is_available_with_key(self, extractor):
        """Test availability with API key."""
        with patch.dict(os.environ, {"LLAMAPARSE_API_KEY": "test-key"}):
            with patch.object(extractor, '_check_imports', return_value=True):
                assert extractor.is_available() is True
    
    @pytest.mark.asyncio
    async def test_extract_success(self, extractor):
        """Test successful extraction with LlamaParse."""
        # Mock LlamaParse
        mock_parser = Mock()
        mock_documents = [
            Mock(text="Page 1 content"),
            Mock(text="Page 2 content")
        ]
        mock_parser.load_data.return_value = mock_documents
        
        with patch('extractors.llamaindex.LlamaParse', return_value=mock_parser):
            result = await extractor.extract("/test/file.pdf")
        
        assert result.extraction_method == "llamaindex"
        assert result.page_count == 2
        assert "Page 1 content" in result.markdown_content
        assert "Page 2 content" in result.markdown_content
    
    @pytest.mark.asyncio
    async def test_extract_empty_document(self, extractor):
        """Test extraction of empty document."""
        mock_parser = Mock()
        mock_parser.load_data.return_value = []
        
        with patch('extractors.llamaindex.LlamaParse', return_value=mock_parser):
            result = await extractor.extract("/test/file.pdf")
        
        assert result.page_count == 0
        assert result.markdown_content == ""


class TestDoclingExtractor:
    """Test Docling extractor."""
    
    @pytest.fixture
    def extractor(self):
        return DoclingExtractor()
    
    def test_name(self, extractor):
        """Test extractor name."""
        assert extractor.name == "docling"
    
    def test_is_available_with_imports(self, extractor):
        """Test availability when docling is installed."""
        with patch.object(extractor, '_check_imports', return_value=True):
            assert extractor.is_available() is True
    
    def test_is_available_missing_imports(self, extractor):
        """Test availability when docling is not installed."""
        with patch.object(extractor, '_check_imports', return_value=False):
            assert extractor.is_available() is False
    
    @pytest.mark.asyncio
    async def test_extract_success(self, extractor):
        """Test successful extraction."""
        # Mock docling components
        mock_doc = Mock()
        mock_doc.export_to_markdown.return_value = "# Extracted Document\n\nContent here."
        mock_doc.pages = [Mock(), Mock(), Mock()]  # 3 pages
        
        mock_converter = Mock()
        mock_converter.convert.return_value = Mock(documents=[mock_doc])
        
        with patch('extractors.docling.DocumentConverter', return_value=mock_converter):
            result = await extractor.extract("/test/file.pdf")
        
        assert result.extraction_method == "docling"
        assert result.page_count == 3
        assert "Extracted Document" in result.markdown_content
    
    @pytest.mark.asyncio
    async def test_extract_with_options(self, extractor):
        """Test extraction with custom options."""
        mock_converter = Mock()
        mock_doc = Mock()
        mock_doc.export_to_markdown.return_value = "Content"
        mock_doc.pages = [Mock()]
        mock_converter.convert.return_value = Mock(documents=[mock_doc])
        
        with patch('extractors.docling.DocumentConverter', return_value=mock_converter):
            with patch('extractors.docling.PdfPipelineOptions') as mock_options:
                await extractor.extract("/test/file.pdf")
                
                # Verify options were created
                mock_options.assert_called_once()


class TestMinerUExtractor:
    """Test MinerU extractor."""
    
    @pytest.fixture
    def extractor(self):
        return MinerUExtractor()
    
    def test_name(self, extractor):
        """Test extractor name."""
        assert extractor.name == "mineru"
    
    def test_is_available_with_imports(self, extractor):
        """Test availability when magic-pdf is installed."""
        with patch.object(extractor, '_check_imports', return_value=True):
            assert extractor.is_available() is True
    
    def test_is_available_missing_imports(self, extractor):
        """Test availability when magic-pdf is not installed."""
        with patch.object(extractor, '_check_imports', return_value=False):
            assert extractor.is_available() is False
    
    @pytest.mark.asyncio
    async def test_extract_success(self, extractor):
        """Test successful extraction."""
        # Mock magic-pdf parse function
        mock_parse_result = {
            "markdown": "# Parsed Content\n\nThis is the content.",
            "pages": 5
        }
        
        with patch('extractors.mineru.parse_pdf', return_value=mock_parse_result):
            with patch('builtins.open', mock_open(read_data=b'PDF content')):
                result = await extractor.extract("/test/file.pdf")
        
        assert result.extraction_method == "mineru"
        assert result.page_count == 5
        assert "Parsed Content" in result.markdown_content
    
    @pytest.mark.asyncio
    async def test_extract_error_handling(self, extractor):
        """Test error handling in extraction."""
        with patch('extractors.mineru.parse_pdf', side_effect=Exception("Parse error")):
            with pytest.raises(Exception, match="Parse error"):
                await extractor.extract("/test/file.pdf")
    
    @pytest.mark.asyncio
    async def test_extract_with_progress(self, extractor):
        """Test extraction with progress updates."""
        progress_calls = []
        
        async def progress_callback(info):
            progress_calls.append(info)
        
        mock_result = {"markdown": "Content", "pages": 1}
        
        with patch('extractors.mineru.parse_pdf', return_value=mock_result):
            with patch('builtins.open', mock_open(read_data=b'PDF')):
                await extractor.extract("/test/file.pdf", progress_callback)
        
        # Should report progress
        assert len(progress_calls) > 0
        assert any("percent" in call for call in progress_calls)


def mock_open(read_data=None):
    """Helper to create a mock file open context manager."""
    m = MagicMock()
    m.__enter__.return_value.read.return_value = read_data
    m.__exit__.return_value = None
    return m