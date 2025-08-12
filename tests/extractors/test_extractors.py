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
    
    @pytest.fixture
    def mock_conversion_result(self):
        """Create a mock conversion result."""
        from unittest.mock import Mock
        
        # Mock the conversion result
        result = Mock()
        result.status = Mock()  # Will be set to SUCCESS
        result.status.name = "SUCCESS"
        
        # Add pages at result level (this is what Docling returns)
        result.pages = [Mock(), Mock()]  # 2 pages
        
        # Mock document with export_to_markdown method
        result.document = Mock()
        result.document.export_to_markdown.return_value = "# Test Document\n\nThis is test content with **bold** text."
        result.document.pages = [Mock(), Mock()]  # 2 pages as fallback
        
        return result
    
    def test_name(self, extractor):
        """Test extractor name."""
        assert extractor.name == "Docling"
    
    def test_capabilities(self, extractor):
        """Test extractor capabilities."""
        caps = extractor.capabilities
        assert caps['supports_ocr'] is True
        assert caps['supports_tables'] is True
        assert caps['supports_images'] is True
        assert caps['requires_api_key'] is False
        assert '.pdf' in caps['supported_formats']
        assert '.docx' in caps['supported_formats']
    
    def test_validate(self, extractor):
        """Test file validation."""
        assert extractor.validate("/test/file.pdf") is True
        assert extractor.validate("/test/document.docx") is True
        assert extractor.validate("/test/slides.pptx") is True
        assert extractor.validate("/test/image.jpg") is True
        assert extractor.validate("/test/file.txt") is False
        assert extractor.validate("/test/file.mp3") is False
    
    def test_is_available_with_imports(self, extractor):
        """Test availability when docling is installed."""
        mock_converter = Mock()
        with patch('docling.document_converter.DocumentConverter', mock_converter):
            assert extractor._check_docling() is True
    
    def test_is_available_missing_imports(self, extractor):
        """Test availability when docling is not installed."""
        with patch('docling.document_converter.DocumentConverter', side_effect=ImportError):
            extractor._available = extractor._check_docling()
            assert extractor.is_available() is False
    
    def test_is_available_init_error(self, extractor):
        """Test availability when docling initialization fails."""
        with patch('docling.document_converter.DocumentConverter', side_effect=Exception("Init failed")):
            extractor._available = extractor._check_docling()
            assert extractor.is_available() is False
    
    @pytest.mark.asyncio
    async def test_extract_success(self, extractor, mock_conversion_result):
        """Test successful extraction."""
        # Create a mock file that exists
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.stat') as mock_stat:
                mock_stat.return_value.st_size = 1024 * 100  # 100KB
                
                # Mock the ConversionStatus enum
                mock_status = Mock()
                mock_status.SUCCESS = "SUCCESS"
                
                with patch('docling.document_converter.DocumentConverter') as mock_converter_class:
                    with patch('docling.datamodel.base_models.ConversionStatus', mock_status):
                        # Set up the converter
                        mock_converter = Mock()
                        mock_converter.convert.return_value = mock_conversion_result
                        mock_converter_class.return_value = mock_converter
                        
                        # Set the status to SUCCESS
                        mock_conversion_result.status = "SUCCESS"
                        
                        # Extract the document
                        result = await extractor.extract("/test/file.pdf")
        
        assert isinstance(result, ExtractionResult)
        assert result.extraction_method == "Docling"
        assert result.page_count == 2
        assert "Test Document" in result.markdown_content
        assert result.processing_time > 0
    
    @pytest.mark.asyncio
    async def test_extract_with_progress(self, extractor, mock_conversion_result):
        """Test extraction with progress callback."""
        progress_calls = []
        
        async def progress_callback(info):
            progress_calls.append(info)
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.stat') as mock_stat:
                mock_stat.return_value.st_size = 1024 * 100
                
                mock_status = Mock()
                mock_status.SUCCESS = "SUCCESS"
                
                with patch('docling.document_converter.DocumentConverter') as mock_converter_class:
                    with patch('docling.datamodel.base_models.ConversionStatus', mock_status):
                        mock_converter = Mock()
                        mock_converter.convert.return_value = mock_conversion_result
                        mock_converter_class.return_value = mock_converter
                        mock_conversion_result.status = "SUCCESS"
                        
                        await extractor.extract("/test/file.pdf", progress_callback)
        
        # Should have progress calls
        assert len(progress_calls) >= 4  # Start, convert, export, complete
        assert any(p['percent'] == 0 for p in progress_calls)
        assert any(p['percent'] == 100 for p in progress_calls)
        assert any('Starting extraction' in p.get('message', '') for p in progress_calls)
    
    @pytest.mark.asyncio
    async def test_extract_file_not_found(self, extractor):
        """Test extraction with non-existent file."""
        from exceptions import ExtractionError
        
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(ExtractionError, match="File not found"):
                await extractor.extract("/test/missing.pdf")
    
    @pytest.mark.asyncio
    async def test_extract_conversion_failed(self, extractor, mock_conversion_result):
        """Test extraction when conversion fails."""
        from exceptions import ExtractionError
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.stat') as mock_stat:
                mock_stat.return_value.st_size = 1024 * 100
                
                mock_status = Mock()
                mock_status.SUCCESS = "SUCCESS"
                mock_status.FAILURE = "FAILURE"
                
                with patch('docling.document_converter.DocumentConverter') as mock_converter_class:
                    with patch('docling.datamodel.base_models.ConversionStatus', mock_status):
                        mock_converter = Mock()
                        mock_conversion_result.status = "FAILURE"  # Set to failure
                        mock_converter.convert.return_value = mock_conversion_result
                        mock_converter_class.return_value = mock_converter
                        
                        with pytest.raises(ExtractionError, match="Document conversion failed"):
                            await extractor.extract("/test/file.pdf")
    
    @pytest.mark.asyncio
    async def test_extract_import_error(self, extractor):
        """Test extraction when docling is not installed."""
        from exceptions import ExtractionError
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('docling.document_converter.DocumentConverter', side_effect=ImportError("No module")):
                with pytest.raises(ExtractionError, match="Docling dependencies not installed"):
                    await extractor.extract("/test/file.pdf")
    
    def test_estimate_page_count(self, extractor):
        """Test page count estimation."""
        with patch('pathlib.Path.stat') as mock_stat:
            # 1MB file
            mock_stat.return_value.st_size = 1024 * 1024
            assert extractor.estimate_page_count("/test/file.pdf") == 10
            
            # 10MB file  
            mock_stat.return_value.st_size = 10 * 1024 * 1024
            assert extractor.estimate_page_count("/test/file.pdf") == 100
            
            # Small file
            mock_stat.return_value.st_size = 10 * 1024  # 10KB
            assert extractor.estimate_page_count("/test/file.pdf") == 1
    
    def test_ocr_options_mac(self, extractor):
        """Test OCR options on macOS."""
        with patch('platform.system', return_value='Darwin'):
            with patch('os.getenv', return_value=''):  # No custom languages
                with patch('docling.datamodel.pipeline_options.OcrMacOptions') as mock_ocr:
                    extractor._converter = None  # Reset converter
                    ocr_options = extractor._get_ocr_options()
                    
                    # Verify OcrMacOptions was called with correct params
                    mock_ocr.assert_called_once_with(
                        framework='livetext',
                        lang=['en-US'],
                        recognition='accurate',
                        force_full_page_ocr=False,
                        bitmap_area_threshold=0.05
                    )
    
    def test_ocr_options_other(self, extractor):
        """Test OCR options on non-macOS platforms."""
        with patch('platform.system', return_value='Linux'):
            with patch('os.getenv', return_value=''):  # No custom languages
                with patch('docling.datamodel.pipeline_options.EasyOcrOptions') as mock_ocr:
                    extractor._converter = None  # Reset converter
                    ocr_options = extractor._get_ocr_options()
                    
                    # Verify EasyOcrOptions was called with correct params
                    mock_ocr.assert_called_once_with(
                        lang=['en'],
                        use_gpu=False,
                        confidence_threshold=0.5
                    )
    
    def test_ocr_options_with_languages(self, extractor):
        """Test OCR options with custom languages."""
        with patch('platform.system', return_value='Darwin'):
            with patch('os.getenv', return_value='en,fr,de'):
                with patch('docling.datamodel.pipeline_options.OcrMacOptions') as mock_ocr:
                    extractor._converter = None  # Reset converter
                    ocr_options = extractor._get_ocr_options()
                    
                    # Verify language mapping
                    mock_ocr.assert_called_once_with(
                        framework='livetext',
                        lang=['en-US', 'fr-FR', 'de-DE'],
                        recognition='accurate',
                        force_full_page_ocr=False,
                        bitmap_area_threshold=0.05
                    )
    
    def test_capabilities_shows_ocr_engine(self, extractor):
        """Test that capabilities show the correct OCR engine."""
        # Test on Mac
        with patch('platform.system', return_value='Darwin'):
            caps = extractor.capabilities
            assert caps['ocr_engine'] == 'OCRMac (livetext)'
            assert 'OCR support with OCRMac (livetext)' in caps['features']
        
        # Test on Linux
        with patch('platform.system', return_value='Linux'):
            caps = extractor.capabilities
            assert caps['ocr_engine'] == 'EasyOCR'
            assert 'OCR support with EasyOCR' in caps['features']


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