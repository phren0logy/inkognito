"""Tests for FastMCP tools with proper context injection and minimal mocking.

These tests focus on testing real tool behavior with context, only mocking external
dependencies like APIs and cloud services.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import json
from typing import Dict, Any

from server import (
    anonymize_documents, restore_documents, extract_document,
    segment_document, split_into_prompts,
    ProcessingResult
)

# Access the actual functions from FastMCP FunctionTool wrappers
anonymize_documents_fn = anonymize_documents.fn
restore_documents_fn = restore_documents.fn
extract_document_fn = extract_document.fn
segment_document_fn = segment_document.fn
split_into_prompts_fn = split_into_prompts.fn
from fastmcp import Context


class TestToolsWithContext:
    """Test tools with proper FastMCP context injection."""
    
    @pytest.mark.asyncio
    async def test_anonymize_documents_with_real_files(self, mock_context, temp_directory, sample_markdown_with_pii):
        """Test anonymize_documents with real file operations and context."""
        # Create real test file
        input_file = temp_directory / "test_with_pii.md"
        input_file.write_text(sample_markdown_with_pii)
        
        # Mock only external dependencies (PIIAnonymizer)
        with patch('server.PIIAnonymizer') as mock_anonymizer_class:
            # Create mock anonymizer instance
            mock_anonymizer = Mock()
            mock_anonymizer_class.return_value = mock_anonymizer
            
            # Mock generate_date_offset
            mock_anonymizer.generate_date_offset.return_value = 180
            
            # Mock anonymize_with_vault to return anonymized text and statistics
            mock_anonymizer.anonymize_with_vault.return_value = (
                sample_markdown_with_pii.replace("John Smith", "Robert Johnson")
                                      .replace("john.smith@example.com", "robert@example.com"),
                {"PERSON": 2, "EMAIL_ADDRESS": 1},  # statistics
                {  # new_mappings
                    "Robert Johnson": "John Smith",
                    "robert@example.com": "john.smith@example.com"
                }
            )
            
            # Call the tool with context
            result = await anonymize_documents_fn(
                output_dir=str(temp_directory / "output"),
                ctx=mock_context,
                files=[str(input_file)]
            )
            
            # Verify result
            assert result.success
            assert len(result.output_paths) == 1
            assert "anonymized" in result.output_paths[0]
            
            # Verify context methods were called
            mock_context.info.assert_any_call("Scanning for documents...")
            mock_context.info.assert_any_call("Found 1 files to anonymize")
            mock_context.report_progress.assert_called()
            
            # Verify output file exists
            output_path = Path(result.output_paths[0])
            assert output_path.exists()
            
            # Verify vault was created
            assert result.vault_path is not None
            vault_path = Path(result.vault_path)
            assert vault_path.exists()
    
    @pytest.mark.asyncio
    async def test_segment_document_with_real_markdown(self, mock_context, temp_directory, long_document):
        """Test segment_document with real markdown processing."""
        # Create a long markdown file
        input_file = temp_directory / "long_document.md"
        input_file.write_text(long_document)
        
        # No external mocking needed for segmentation
        result = await segment_document_fn(
            file_path=str(input_file),
            output_dir=str(temp_directory / "segments"),
            ctx=mock_context,
            max_tokens=1000,
            min_tokens=500
        )
        
        # Verify result
        assert result.success
        assert len(result.output_paths) > 1  # Should create multiple segments
        
        # Verify context methods were called
        mock_context.info.assert_any_call("Reading document...")
        mock_context.info.assert_any_call("Analyzing document structure...")
        mock_context.report_progress.assert_called()
        
        # Verify all output files exist and are valid
        for output_path in result.output_paths:
            path = Path(output_path)
            assert path.exists()
            content = path.read_text()
            assert "<!-- Segment" in content
            assert "<!-- Tokens:" in content
    
    @pytest.mark.asyncio
    async def test_extract_document_with_context_progress(self, mock_context, temp_directory, mock_extractor):
        """Test extract_document with progress reporting through context."""
        # Create a mock PDF file
        pdf_file = temp_directory / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n%%EOF")
        
        # Mock the registry to return our mock extractor
        with patch('server.registry') as mock_registry:
            mock_registry.auto_select.return_value = mock_extractor
            
            # Set up progress callback capture
            progress_callback = None
            async def capture_callback(file_path, callback=None):
                nonlocal progress_callback
                progress_callback = callback
                if callback:
                    await callback({'current': 1, 'total': 10, 'percent': 0.1})
                    await callback({'current': 5, 'total': 10, 'percent': 0.5})
                    await callback({'current': 10, 'total': 10, 'percent': 1.0})
                return mock_extractor.extract.return_value
            
            mock_extractor.extract.side_effect = capture_callback
            
            # Call the tool
            result = await extract_document_fn(
                file_path=str(pdf_file),
                ctx=mock_context
            )
            
            # Verify result
            assert result.success
            assert len(result.output_paths) == 1
            
            # Verify context methods were called
            mock_context.info.assert_any_call(f"Extracting {pdf_file.name}...")
            mock_context.info.assert_any_call(f"Using {mock_extractor.name}...")
            
            # Verify progress was reported through context
            mock_context.report_progress.assert_any_call(1, 10, "Processing page 1/10")
            mock_context.report_progress.assert_any_call(5, 10, "Processing page 5/10")
            mock_context.report_progress.assert_any_call(10, 10, "Processing page 10/10")
    
    @pytest.mark.asyncio
    async def test_split_into_prompts_with_real_content(self, mock_context, temp_directory):
        """Test split_into_prompts with real markdown content."""
        # Create structured markdown
        markdown_content = """# Main Title

## Section 1
Content for section 1.

### Subsection 1.1
Details for subsection 1.1.

## Section 2
Content for section 2.

### Subsection 2.1
Details for subsection 2.1.
"""
        input_file = temp_directory / "structured.md"
        input_file.write_text(markdown_content)
        
        # Call the tool
        result = await split_into_prompts_fn(
            file_path=str(input_file),
            output_dir=str(temp_directory / "prompts"),
            ctx=mock_context,
            split_level="h2"
        )
        
        # Verify result
        assert result.success
        assert len(result.output_paths) == 2  # Two h2 sections
        
        # Verify context methods
        mock_context.info.assert_any_call("Splitting by h2 headings...")
        mock_context.report_progress.assert_called()
        
        # Verify output files
        for output_path in result.output_paths:
            path = Path(output_path)
            assert path.exists()
            content = path.read_text()
            assert "<!-- Prompt" in content
            assert "<!-- Heading:" in content
    
    @pytest.mark.asyncio
    async def test_restore_documents_end_to_end(self, mock_context, temp_directory):
        """Test complete anonymize -> restore cycle with real files."""
        # Create test file with PII
        original_content = """# Employee Record
Name: Jane Doe
Email: jane.doe@example.com
Phone: 555-1234
"""
        input_file = temp_directory / "employee.md"
        input_file.write_text(original_content)
        
        # Step 1: Anonymize with mocked PIIAnonymizer
        with patch('server.PIIAnonymizer') as mock_anonymizer_class:
            # Create mock anonymizer instance
            mock_anonymizer = Mock()
            mock_anonymizer_class.return_value = mock_anonymizer
            
            # Mock generate_date_offset
            mock_anonymizer.generate_date_offset.return_value = 0
            
            # Mock the anonymization
            anonymized_content = """# Employee Record
Name: [REDACTED_PERSON_1]
Email: [REDACTED_EMAIL_1]
Phone: [REDACTED_PHONE_1]
"""
            mock_anonymizer.anonymize_with_vault.return_value = (
                anonymized_content,
                {"PERSON": 1, "EMAIL_ADDRESS": 1, "PHONE_NUMBER": 1},
                {
                    "[REDACTED_PERSON_1]": "Jane Doe",
                    "[REDACTED_EMAIL_1]": "jane.doe@example.com",
                    "[REDACTED_PHONE_1]": "555-1234"
                }
            )
            
            # Anonymize
            anon_result = await anonymize_documents_fn(
                output_dir=str(temp_directory / "anonymized"),
                ctx=mock_context,
                files=[str(input_file)]
            )
            
            assert anon_result.success
            assert anon_result.vault_path is not None
        
        # Step 2: Write fake anonymized content (simulate what anonymizer would do)
        anon_file = Path(anon_result.output_paths[0])
        anon_file.parent.mkdir(parents=True, exist_ok=True)
        anon_file.write_text(anonymized_content)
        
        # Write a real vault file
        vault_data = {
            "version": "2.0",
            "created_at": "2024-01-01T00:00:00",
            "statistics": {"files_processed": 1},
            "date_offset": 0,
            "mappings": {
                "Jane Doe": "[REDACTED_PERSON_1]",
                "jane.doe@example.com": "[REDACTED_EMAIL_1]",
                "555-1234": "[REDACTED_PHONE_1]"
            }
        }
        vault_path = Path(anon_result.vault_path)
        vault_path.write_text(json.dumps(vault_data, indent=2))
        
        # Reset mock calls
        mock_context.reset_mock()
        
        # Step 3: Restore
        restore_result = await restore_documents_fn(
            output_dir=str(temp_directory / "restored"),
            ctx=mock_context,
            files=[str(anon_file)],
            vault_path=str(vault_path)
        )
        
        assert restore_result.success
        assert len(restore_result.output_paths) == 1
        
        # Verify restored content matches original
        restored_file = Path(restore_result.output_paths[0])
        assert restored_file.exists()
        restored_content = restored_file.read_text()
        
        # Check that PII was restored
        assert "Jane Doe" in restored_content
        assert "jane.doe@example.com" in restored_content
        assert "555-1234" in restored_content
        assert "[REDACTED_" not in restored_content
        
        # Verify context logging
        mock_context.info.assert_any_call("Loading vault data...")
        mock_context.info.assert_any_call("Restoration complete!")


class TestContextErrorHandling:
    """Test error handling with context."""
    
    @pytest.mark.asyncio
    async def test_missing_file_error_logging(self, mock_context, temp_directory):
        """Test that errors are properly logged through context."""
        # Try to process non-existent file
        result = await extract_document_fn(
            file_path="/nonexistent/file.pdf",
            ctx=mock_context
        )
        
        # Should fail gracefully
        assert not result.success
        assert "not found" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_invalid_parameters_with_context(self, mock_context, temp_directory):
        """Test parameter validation with context logging."""
        # Create a non-markdown file for segmentation
        binary_file = temp_directory / "test.bin"
        binary_file.write_bytes(b"\x00\x01\x02\x03")
        
        result = await segment_document_fn(
            file_path=str(binary_file),
            output_dir=str(temp_directory / "output"),
            ctx=mock_context
        )
        
        # Should fail with appropriate message
        assert not result.success
        assert "markdown" in result.message.lower()