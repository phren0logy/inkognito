"""Docling extractor for document processing."""

import time
from typing import Dict, Any, Optional, Callable
import logging
import asyncio
import platform
import os
from pathlib import Path

from .base import BaseExtractor, ExtractionResult
from exceptions import ExtractionError

logger = logging.getLogger(__name__)


class DoclingExtractor(BaseExtractor):
    """Docling extractor for local PDF and DOCX processing."""
    
    def __init__(self):
        self._available = self._check_docling()
        self._converter = None
    
    def _check_docling(self) -> bool:
        """Check if Docling is installed and properly configured."""
        try:
            from docling.document_converter import DocumentConverter
            # Try to create a converter to verify full installation
            converter = DocumentConverter()
            return True
        except ImportError as e:
            logger.debug(f"Docling not available: {e}")
            return False
        except Exception as e:
            logger.warning(f"Docling initialization failed: {e}")
            return False
    
    def _get_ocr_options(self):
        """Get platform-specific OCR options."""
        # Get languages from environment or use defaults
        languages = os.getenv('INKOGNITO_OCR_LANGUAGES', '').split(',')
        languages = [lang.strip() for lang in languages if lang.strip()]
        
        if platform.system() == 'Darwin':  # macOS
            # Map common language codes to macOS format
            mac_lang_map = {
                'en': 'en-US',
                'fr': 'fr-FR',
                'de': 'de-DE',
                'es': 'es-ES',
                'it': 'it-IT',
                'pt': 'pt-BR',
                'nl': 'nl-NL',
                'ja': 'ja-JP',
                'ko': 'ko-KR',
                'zh': 'zh-CN'
            }
            mac_languages = [mac_lang_map.get(lang, lang) for lang in languages] or ['en-US']
            
            logger.info(f"Using OCRMac with livetext framework for languages: {mac_languages}")
            
            from docling.datamodel.pipeline_options import OcrMacOptions
            return OcrMacOptions(
                framework='livetext',
                lang=mac_languages,
                recognition='accurate',
                force_full_page_ocr=False,
                bitmap_area_threshold=0.05
            )
        else:
            # EasyOCR languages
            languages = languages or ['en']
            
            logger.info(f"Using EasyOCR for languages: {languages}")
            
            from docling.datamodel.pipeline_options import EasyOcrOptions
            return EasyOcrOptions(
                lang=languages,
                use_gpu=False,  # Can be made configurable via env var
                confidence_threshold=0.5
            )
    
    def _get_converter(self):
        """Get or create the document converter with platform-specific OCR."""
        if not self._converter:
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.datamodel.base_models import InputFormat
            
            # Get platform-specific OCR options
            ocr_options = self._get_ocr_options()
            
            # Create PDF pipeline options with OCR
            pdf_options = PdfPipelineOptions(
                do_ocr=True,
                ocr_options=ocr_options
            )
            
            # Create converter with format_options (correct API)
            self._converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options)
                }
            )
        return self._converter
    
    async def extract(
        self, 
        file_path: str, 
        progress_callback: Optional[Callable] = None
    ) -> ExtractionResult:
        """Extract document using Docling."""
        start_time = time.time()
        
        try:
            # Validate file exists
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                raise ExtractionError(f"File not found: {file_path}")
            
            # Report starting progress
            if progress_callback:
                await progress_callback({
                    'current': 0, 
                    'total': 100, 
                    'percent': 0,
                    'message': f'Starting extraction of {file_path_obj.name}'
                })
            
            # Import Docling components
            from docling.document_converter import DocumentConverter
            from docling.datamodel.base_models import ConversionStatus
            
            # Create converter
            converter = self._get_converter()
            
            # Report conversion progress
            if progress_callback:
                await progress_callback({
                    'current': 25, 
                    'total': 100, 
                    'percent': 25,
                    'message': 'Converting document...'
                })
            
            # Convert document synchronously in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                converter.convert, 
                str(file_path)
            )
            
            # Check conversion status
            if result.status != ConversionStatus.SUCCESS:
                raise ExtractionError(
                    f"Document conversion failed with status: {result.status}"
                )
            
            # Report markdown export progress
            if progress_callback:
                await progress_callback({
                    'current': 75, 
                    'total': 100, 
                    'percent': 75,
                    'message': 'Exporting to markdown...'
                })
            
            # Export to markdown
            markdown_content = await loop.run_in_executor(
                None,
                result.document.export_to_markdown
            )
            
            # Extract metadata
            metadata = {
                'filename': file_path_obj.name,
                'file_size': file_path_obj.stat().st_size,
                'conversion_status': str(result.status),
            }
            
            # Try to get page count
            page_count = 1  # Default
            try:
                if hasattr(result, 'pages') and result.pages:
                    page_count = len(result.pages)
                elif hasattr(result.document, 'pages') and result.document.pages:
                    page_count = len(result.document.pages)
                elif hasattr(result.document, '_items') and result.document._items:
                    # Estimate based on content structure
                    page_count = max(1, len(result.document._items) // 10)
            except Exception as e:
                logger.debug(f"Could not determine exact page count: {e}")
            
            # Report completion
            if progress_callback:
                await progress_callback({
                    'current': 100, 
                    'total': 100, 
                    'percent': 100,
                    'message': 'Extraction complete'
                })
            
            processing_time = time.time() - start_time
            
            return ExtractionResult(
                markdown_content=markdown_content,
                metadata=metadata,
                page_count=page_count,
                extraction_method="Docling",
                processing_time=processing_time
            )
            
        except ImportError as e:
            raise ExtractionError(f"Docling dependencies not installed: {e}")
        except Exception as e:
            if isinstance(e, ExtractionError):
                raise
            raise ExtractionError(f"Docling extraction failed: {e}")
    
    def validate(self, file_path: str) -> bool:
        """Check if file can be processed by Docling."""
        supported_extensions = ('.pdf', '.docx', '.pptx', '.xlsx', '.html', '.jpg', '.jpeg', '.png')
        return file_path.lower().endswith(supported_extensions)
    
    def is_available(self) -> bool:
        """Check if Docling is available."""
        return self._available
    
    @property
    def name(self) -> str:
        return "Docling"
    
    @property
    def capabilities(self) -> Dict[str, Any]:
        # Determine which OCR engine is being used
        ocr_engine = 'OCRMac (livetext)' if platform.system() == 'Darwin' else 'EasyOCR'
        
        return {
            'supports_ocr': True,  # Docling has OCR capabilities
            'ocr_engine': ocr_engine,
            'supports_tables': True,
            'supports_images': True,
            'max_file_size_mb': 200,
            'supported_formats': ['.pdf', '.docx', '.pptx', '.xlsx', '.html', '.jpg', '.jpeg', '.png'],
            'requires_api_key': False,
            'average_speed': '3-8 seconds per page',
            'features': [
                'Advanced layout understanding',
                'Table extraction',
                f'OCR support with {ocr_engine}',
                'Multiple format support',
                'Local processing (no cloud dependency)',
                'Platform-optimized OCR engine'
            ]
        }
    
    def estimate_page_count(self, file_path: str) -> int:
        """
        Estimate page count for timeout calculation.
        Docling is generally faster, so we use a conservative estimate.
        """
        file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)
        # Docling is efficient - estimate 1 page per 100KB
        return max(1, int(file_size_mb * 10))