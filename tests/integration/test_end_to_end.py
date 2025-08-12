"""End-to-end integration tests for Inkognito."""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, Mock, AsyncMock

from server import (
    anonymize_documents, restore_documents, extract_document,
    segment_document, split_into_prompts
)
from tests.conftest import SAMPLE_MARKDOWN_WITH_PII


class TestAnonymizeRestoreCycle:
    """Test complete anonymize and restore workflows."""
    
    @pytest.mark.asyncio
    async def test_anonymize_and_restore_markdown(
        self, temp_directory, mock_llm_guard, mock_faker
    ):
        """Test full cycle: anonymize markdown then restore it."""
        # Create input file
        input_file = temp_directory / "original.md"
        input_file.write_text(SAMPLE_MARKDOWN_WITH_PII)
        
        scanner, vault = mock_llm_guard
        
        # Step 1: Anonymize
        with patch('anonymizer.PIIAnonymizer.create_scanner', return_value=scanner):
            with patch('anonymizer.Faker', return_value=mock_faker):
                anon_result = await anonymize_documents(
                    output_dir=str(temp_directory / "anonymized"),
                    files=[str(input_file)]
                )
        
        assert anon_result.success
        assert len(anon_result.output_paths) == 1
        assert anon_result.vault_path is not None
        
        # Verify anonymized content
        anon_file = Path(anon_result.output_paths[0])
        anon_content = anon_file.read_text()
        assert "John Smith" not in anon_content
        assert "Robert Johnson" in anon_content  # Faker replacement
        
        # Step 2: Restore
        restore_result = await restore_documents(
            output_dir=str(temp_directory / "restored"),
            files=anon_result.output_paths,
            vault_path=anon_result.vault_path
        )
        
        assert restore_result.success
        assert len(restore_result.output_paths) == 1
        
        # Verify restored content matches original
        restored_file = Path(restore_result.output_paths[0])
        restored_content = restored_file.read_text()
        
        # Check key PII was restored
        assert "John Smith" in restored_content
        assert "john.smith@example.com" in restored_content
        assert "+1-555-234-5678" in restored_content
        assert "Robert Johnson" not in restored_content
    
    @pytest.mark.asyncio
    async def test_anonymize_multiple_files_consistency(
        self, temp_directory, mock_llm_guard, mock_faker
    ):
        """Test that same entities get same replacements across files."""
        # Create multiple files with overlapping PII
        file1 = temp_directory / "doc1.md"
        file1.write_text("Contact John Smith at john.smith@example.com")
        
        file2 = temp_directory / "doc2.md"
        file2.write_text("John Smith works at Acme Corporation")
        
        file3 = temp_directory / "doc3.md"
        file3.write_text("Email john.smith@example.com for Acme Corporation info")
        
        scanner, vault = mock_llm_guard
        
        # Anonymize all files
        with patch('anonymizer.PIIAnonymizer.create_scanner', return_value=scanner):
            with patch('anonymizer.Faker', return_value=mock_faker):
                result = await anonymize_documents(
                    output_dir=str(temp_directory / "output"),
                    files=[str(file1), str(file2), str(file3)]
                )
        
        assert result.success
        assert len(result.output_paths) == 3
        
        # Check consistency across files
        contents = []
        for output_path in result.output_paths:
            content = Path(output_path).read_text()
            contents.append(content)
        
        # All files should have same replacement for John Smith
        johns_replacement = None
        for content in contents:
            if "Robert Johnson" in content:
                johns_replacement = "Robert Johnson"
                break
        
        assert johns_replacement is not None
        for content in contents:
            if "Smith" in SAMPLE_MARKDOWN_WITH_PII:  # Original had Smith
                assert johns_replacement in content
    
    @pytest.mark.asyncio
    async def test_pdf_extraction_and_anonymization(
        self, temp_directory, sample_pdf_path, mock_extractor_registry,
        mock_llm_guard, mock_faker
    ):
        """Test extracting PDF then anonymizing the content."""
        scanner, vault = mock_llm_guard
        
        # Step 1: Extract PDF
        with patch('server.registry', mock_extractor_registry):
            extract_result = await extract_document(
                file_path=str(sample_pdf_path),
                output_path=str(temp_directory / "extracted.md")
            )
        
        assert extract_result.success
        
        # Step 2: Anonymize extracted content
        with patch('anonymizer.PIIAnonymizer.create_scanner', return_value=scanner):
            with patch('anonymizer.Faker', return_value=mock_faker):
                anon_result = await anonymize_documents(
                    output_dir=str(temp_directory / "anonymized"),
                    files=[extract_result.output_paths[0]]
                )
        
        assert anon_result.success
        assert Path(anon_result.output_paths[0]).exists()


class TestDocumentProcessingPipeline:
    """Test complete document processing workflows."""
    
    @pytest.mark.asyncio
    async def test_extract_segment_workflow(
        self, temp_directory, sample_pdf_path, mock_extractor_registry,
        mock_tiktoken, long_document
    ):
        """Test extracting a document then segmenting it."""
        # Create a mock extractor that returns long content
        mock_extractor_registry.auto_select.return_value.extract = AsyncMock(
            return_value=Mock(
                markdown_content=long_document,
                page_count=10,
                extraction_method="mock",
                processing_time=0.1,
                metadata={}
            )
        )
        
        # Step 1: Extract
        with patch('server.registry', mock_extractor_registry):
            extract_result = await extract_document(
                file_path=str(sample_pdf_path),
                output_path=str(temp_directory / "extracted.md")
            )
        
        assert extract_result.success
        
        # Step 2: Segment
        with patch('segmenter.tiktoken.get_encoding', return_value=mock_tiktoken):
            segment_result = await segment_document(
                file_path=extract_result.output_paths[0],
                output_dir=str(temp_directory / "segments"),
                max_tokens=1000,
                min_tokens=500
            )
        
        assert segment_result.success
        assert len(segment_result.output_paths) > 1
        
        # Verify segments
        for segment_path in segment_result.output_paths:
            content = Path(segment_path).read_text()
            assert "<!-- Segment" in content
            assert "<!-- Tokens:" in content
    
    @pytest.mark.asyncio
    async def test_segment_and_split_workflow(
        self, temp_directory, long_document, mock_tiktoken
    ):
        """Test segmenting then splitting into prompts."""
        # Create input file
        input_file = temp_directory / "long_doc.md"
        input_file.write_text(long_document)
        
        # Step 1: Segment large document
        with patch('segmenter.tiktoken.get_encoding', return_value=mock_tiktoken):
            segment_result = await segment_document(
                file_path=str(input_file),
                output_dir=str(temp_directory / "segments"),
                max_tokens=5000
            )
        
        assert segment_result.success
        
        # Step 2: Split first segment into prompts
        first_segment = segment_result.output_paths[0]
        split_result = await split_into_prompts(
            file_path=first_segment,
            output_dir=str(temp_directory / "prompts"),
            split_level="h2"
        )
        
        # Should have prompts from the segment
        assert split_result.success
        if split_result.output_paths:  # May be empty if segment has no h2
            prompt_content = Path(split_result.output_paths[0]).read_text()
            assert "<!-- Prompt" in prompt_content
    
    @pytest.mark.asyncio
    async def test_full_pipeline_with_error_recovery(
        self, temp_directory, mock_extractor_registry
    ):
        """Test pipeline with error handling."""
        # Create a file that will fail extraction
        bad_file = temp_directory / "corrupt.pdf"
        bad_file.write_bytes(b"Not a real PDF")
        
        # Mock extractor to fail
        mock_extractor_registry.auto_select.return_value = None
        
        # Step 1: Extract should fail gracefully
        with patch('server.registry', mock_extractor_registry):
            extract_result = await extract_document(
                file_path=str(bad_file)
            )
        
        assert not extract_result.success
        assert "No suitable extractor" in extract_result.message
        
        # Pipeline should stop here, not crash
        
    @pytest.mark.asyncio
    async def test_anonymize_with_progress_reporting(
        self, temp_directory, sample_files, mock_llm_guard, mock_faker,
        mock_context
    ):
        """Test that progress is reported during operations."""
        scanner, vault = mock_llm_guard
        
        with patch('server.server.get_context', return_value=mock_context):
            with patch('anonymizer.PIIAnonymizer.create_scanner', return_value=scanner):
                with patch('anonymizer.Faker', return_value=mock_faker):
                    result = await anonymize_documents(
                        output_dir=str(temp_directory / "output"),
                        directory=sample_files["directory"],
                        patterns=["*.md"]
                    )
        
        assert result.success
        
        # Verify progress was reported
        assert mock_context.report_progress.called
        progress_calls = mock_context.report_progress.call_args_list
        
        # Should have various progress messages
        messages = [call[0][0] for call in progress_calls]
        assert any("Scanning for documents" in msg for msg in messages)
        assert any("Processing file" in msg for msg in messages)
        assert any("complete" in msg.lower() for msg in messages)


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.mark.asyncio
    async def test_empty_directory_handling(self, temp_directory):
        """Test handling of empty directories."""
        empty_dir = temp_directory / "empty"
        empty_dir.mkdir()
        
        result = await anonymize_documents(
            output_dir=str(temp_directory / "output"),
            directory=str(empty_dir)
        )
        
        assert not result.success
        assert "No files found" in result.message
    
    @pytest.mark.asyncio
    async def test_large_file_handling(
        self, temp_directory, mock_llm_guard, mock_faker
    ):
        """Test handling of large files."""
        # Create a large file (simulate with repetition)
        large_content = SAMPLE_MARKDOWN_WITH_PII * 100
        large_file = temp_directory / "large.md"
        large_file.write_text(large_content)
        
        scanner, vault = mock_llm_guard
        
        with patch('anonymizer.PIIAnonymizer.create_scanner', return_value=scanner):
            with patch('anonymizer.Faker', return_value=mock_faker):
                result = await anonymize_documents(
                    output_dir=str(temp_directory / "output"),
                    files=[str(large_file)]
                )
        
        assert result.success
        
        # Check output file was created and is reasonable size
        output_file = Path(result.output_paths[0])
        assert output_file.exists()
        assert output_file.stat().st_size > 0
    
    @pytest.mark.asyncio
    async def test_concurrent_file_processing(
        self, temp_directory, sample_files, mock_llm_guard, mock_faker
    ):
        """Test processing multiple files concurrently."""
        scanner, vault = mock_llm_guard
        
        # Create multiple files
        files = []
        for i in range(5):
            file_path = temp_directory / f"doc_{i}.md"
            file_path.write_text(f"Document {i} with email test{i}@example.com")
            files.append(str(file_path))
        
        with patch('anonymizer.PIIAnonymizer.create_scanner', return_value=scanner):
            with patch('anonymizer.Faker', return_value=mock_faker):
                result = await anonymize_documents(
                    output_dir=str(temp_directory / "output"),
                    files=files
                )
        
        assert result.success
        assert len(result.output_paths) == 5
        
        # Verify vault has entries for all unique emails
        vault_data = json.loads(Path(result.vault_path).read_text())
        assert len(vault_data["mappings"]) >= 5  # At least one entry per file