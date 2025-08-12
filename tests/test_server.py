"""Tests for FastMCP server and tools."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import json

from server import (
    find_files, ensure_output_dir,
    anonymize_documents, restore_documents, extract_document,
    segment_document, split_into_prompts,
    ProcessingResult, server
)

# Access the actual functions from FastMCP FunctionTool wrappers
anonymize_documents_fn = anonymize_documents.fn
restore_documents_fn = restore_documents.fn
extract_document_fn = extract_document.fn
segment_document_fn = segment_document.fn
split_into_prompts_fn = split_into_prompts.fn


class TestFindFiles:
    """Test the find_files utility function."""
    
    def test_find_files_with_explicit_list(self, temp_directory):
        """Test finding files with explicit file list."""
        # Create test files
        file1 = temp_directory / "test1.txt"
        file2 = temp_directory / "test2.md"
        file1.write_text("content1")
        file2.write_text("content2")
        
        # Test with explicit file list
        result = find_files(files=[str(file1), str(file2)])
        assert len(result) == 2
        assert str(file1) in result
        assert str(file2) in result
    
    def test_find_files_with_missing_file(self):
        """Test error handling for missing files."""
        with pytest.raises(FileNotFoundError, match="File not found"):
            find_files(files=["/nonexistent/file.txt"])
    
    def test_find_files_with_directory_patterns(self, sample_files):
        """Test finding files in directory with patterns."""
        result = find_files(
            directory=sample_files["directory"],
            patterns=["*.md"],
            recursive=True
        )
        assert len(result) == 3  # sample.md, sample_with_pii.md, nested.md
        assert all(path.endswith(".md") for path in result)
    
    def test_find_files_non_recursive(self, sample_files):
        """Test non-recursive file finding."""
        result = find_files(
            directory=sample_files["directory"],
            patterns=["*.md"],
            recursive=False
        )
        assert len(result) == 2  # Only files in root, not subdirectory
        assert "nested.md" not in str(result)
    
    def test_find_files_multiple_patterns(self, sample_files):
        """Test finding files with multiple patterns."""
        result = find_files(
            directory=sample_files["directory"],
            patterns=["*.md", "*.txt"],
            recursive=True
        )
        assert len(result) == 4  # 3 .md files + 1 .txt file
    
    def test_find_files_missing_directory(self):
        """Test error handling for missing directory."""
        with pytest.raises(FileNotFoundError, match="Directory not found"):
            find_files(directory="/nonexistent/directory")
    
    def test_find_files_no_inputs(self):
        """Test error when neither files nor directory provided."""
        with pytest.raises(ValueError, match="Either 'files' or 'directory'"):
            find_files()


class TestEnsureOutputDir:
    """Test the ensure_output_dir utility function."""
    
    def test_create_new_directory(self, temp_directory):
        """Test creating a new directory."""
        new_dir = temp_directory / "output"
        result = ensure_output_dir(str(new_dir))
        assert result.exists()
        assert result.is_dir()
    
    def test_existing_directory(self, temp_directory):
        """Test with existing directory."""
        existing_dir = temp_directory / "existing"
        existing_dir.mkdir()
        result = ensure_output_dir(str(existing_dir))
        assert result.exists()
        assert result.is_dir()
    
    def test_nested_directory_creation(self, temp_directory):
        """Test creating nested directories."""
        nested_dir = temp_directory / "a" / "b" / "c"
        result = ensure_output_dir(str(nested_dir))
        assert result.exists()
        assert result.is_dir()



class TestAnonymizeDocuments:
    """Test the anonymize_documents tool."""
    
    @pytest.mark.asyncio
    async def test_anonymize_markdown_files(
        self, temp_directory, sample_files, mock_llm_guard, mock_faker, mock_context
    ):
        """Test anonymizing markdown files."""
        # Mock PIIAnonymizer instead of its internal components
        with patch('server.PIIAnonymizer') as mock_anonymizer_class:
            mock_anonymizer = Mock()
            mock_anonymizer_class.return_value = mock_anonymizer
            mock_anonymizer.generate_date_offset.return_value = 180
            mock_anonymizer.anonymize_with_vault.return_value = (
                "Anonymized content",
                {"PERSON": 2, "EMAIL_ADDRESS": 1},  # statistics
                {"John Smith": "Robert Johnson"}  # mappings
            )
            result = await anonymize_documents_fn(
                output_dir=str(temp_directory / "output"),
                ctx=mock_context,
                files=[sample_files["md_with_pii"]]
            )
        
        assert result.success
        assert len(result.output_paths) == 1
        assert "anonymized" in result.output_paths[0]
        assert result.vault_path is not None
        assert "PERSON" in result.statistics
    
    @pytest.mark.asyncio
    async def test_anonymize_pdf_file(
        self, temp_directory, sample_pdf_path, mock_extractor_registry,
        mock_llm_guard, mock_faker, mock_context
    ):
        """Test anonymizing PDF files with extraction."""
        scanner, vault = mock_llm_guard
        
        with patch('server.registry', mock_extractor_registry):
            with patch('anonymizer.PIIAnonymizer.create_scanner', return_value=scanner):
                with patch('anonymizer.Faker', return_value=mock_faker):
                    result = await anonymize_documents_fn(
                        output_dir=str(temp_directory / "output"),
                        ctx=mock_context,
                        files=[str(sample_pdf_path)]
                    )
        
        assert result.success
        assert len(result.output_paths) == 1
        assert result.output_paths[0].endswith(".md")
    
    @pytest.mark.asyncio
    async def test_anonymize_no_files_found(self, temp_directory, mock_context):
        """Test handling when no files are found."""
        result = await anonymize_documents_fn(
            output_dir=str(temp_directory / "output"),
            ctx=mock_context,
            directory=str(temp_directory),
            patterns=["*.nonexistent"]
        )
        
        assert not result.success
        assert "No files found" in result.message
    
    @pytest.mark.asyncio
    async def test_anonymize_with_directory_scan(
        self, temp_directory, sample_files, mock_llm_guard, mock_faker, mock_context
    ):
        """Test anonymizing files found by directory scan."""
        scanner, vault = mock_llm_guard
        
        with patch('anonymizer.PIIAnonymizer.create_scanner', return_value=scanner):
            with patch('anonymizer.Faker', return_value=mock_faker):
                result = await anonymize_documents_fn(
                    output_dir=str(temp_directory / "output"),
                    ctx=mock_context,
                    directory=sample_files["directory"],
                    patterns=["*.md"],
                    recursive=True
                )
        
        assert result.success
        assert len(result.output_paths) == 3  # All .md files
    
    @pytest.mark.asyncio
    async def test_anonymize_creates_report(
        self, temp_directory, sample_files, mock_llm_guard, mock_faker, mock_context
    ):
        """Test that anonymization creates a report file."""
        scanner, vault = mock_llm_guard
        
        with patch('anonymizer.PIIAnonymizer.create_scanner', return_value=scanner):
            with patch('anonymizer.Faker', return_value=mock_faker):
                result = await anonymize_documents_fn(
                    output_dir=str(temp_directory / "output"),
                    ctx=mock_context,
                    files=[sample_files["md_with_pii"]]
                )
        
        report_path = Path(temp_directory) / "output" / "REPORT.md"
        assert report_path.exists()
        report_content = report_path.read_text()
        assert "Anonymization Report" in report_content
        assert "Statistics" in report_content


class TestRestoreDocuments:
    """Test the restore_documents tool."""
    
    @pytest.mark.asyncio
    async def test_restore_with_vault(
        self, temp_directory, sample_files, mock_vault_data, mock_context
    ):
        """Test restoring documents with vault."""
        # Create anonymized file
        anon_dir = temp_directory / "anonymized"
        anon_dir.mkdir()
        anon_file = anon_dir / "anonymized.md"
        anon_file.write_text("Hello Robert Johnson at robert.johnson@example.com")
        
        # Create vault file
        vault_path = temp_directory / "vault.json"
        vault_path.write_text(json.dumps(mock_vault_data))
        
        result = await restore_documents_fn(
            output_dir=str(temp_directory / "restored"),
            ctx=mock_context,
            files=[str(anon_file)],
            vault_path=str(vault_path)
        )
        
        assert result.success
        assert len(result.output_paths) == 1
        assert "restored" in result.output_paths[0]
        
        # Check restored content
        restored_file = Path(result.output_paths[0])
        content = restored_file.read_text()
        assert "John Smith" in content
        assert "john.smith@example.com" in content
    
    @pytest.mark.asyncio
    async def test_restore_auto_detect_vault(self, temp_directory, mock_vault_data, mock_context):
        """Test auto-detecting vault file."""
        # Create directory structure
        anon_dir = temp_directory / "anonymized"
        anon_dir.mkdir()
        anon_file = anon_dir / "test.md"
        anon_file.write_text("Anonymized content")
        
        # Create vault in parent directory
        vault_path = temp_directory / "vault.json"
        vault_path.write_text(json.dumps(mock_vault_data))
        
        result = await restore_documents_fn(
            output_dir=str(temp_directory / "restored"),
            ctx=mock_context,
            directory=str(anon_dir)
        )
        
        assert result.success
    
    @pytest.mark.asyncio
    async def test_restore_no_vault_found(self, temp_directory, sample_files, mock_context):
        """Test error when vault is not found."""
        result = await restore_documents_fn(
            output_dir=str(temp_directory / "restored"),
            ctx=mock_context,
            files=[sample_files["md"]]
        )
        
        assert not result.success
        assert "Vault file not found" in result.message
    
    @pytest.mark.asyncio
    async def test_restore_creates_report(
        self, temp_directory, mock_vault_data, mock_context
    ):
        """Test that restoration creates a report file."""
        # Setup
        anon_file = temp_directory / "test.md"
        anon_file.write_text("Test content")
        vault_path = temp_directory / "vault.json"
        vault_path.write_text(json.dumps(mock_vault_data))
        
        result = await restore_documents_fn(
            output_dir=str(temp_directory / "restored"),
            ctx=mock_context,
            files=[str(anon_file)],
            vault_path=str(vault_path)
        )
        
        report_path = Path(temp_directory) / "restored" / "RESTORATION_REPORT.md"
        assert report_path.exists()
        assert "Restoration Report" in report_path.read_text()


class TestExtractDocument:
    """Test the extract_document tool."""
    
    @pytest.mark.asyncio
    async def test_extract_pdf_auto_selection(
        self, temp_directory, sample_pdf_path, mock_extractor_registry, mock_context
    ):
        """Test PDF extraction with auto extractor selection."""
        with patch('server.registry', mock_extractor_registry):
            result = await extract_document_fn(
                file_path=str(sample_pdf_path),
                ctx=mock_context,
                output_path=str(temp_directory / "output.md")
            )
        
        assert result.success
        assert result.statistics["extractor_name"] == "MockExtractor"
        assert Path(temp_directory / "output.md").exists()
    
    @pytest.mark.asyncio
    async def test_extract_specific_method(
        self, temp_directory, sample_pdf_path, mock_extractor_registry, mock_context
    ):
        """Test extraction with specific method."""
        with patch('server.registry', mock_extractor_registry):
            result = await extract_document_fn(
                file_path=str(sample_pdf_path),
                ctx=mock_context,
                extraction_method="azure"
            )
        
        assert result.success
        mock_extractor_registry.get.assert_called_once_with("azure")
    
    @pytest.mark.asyncio
    async def test_extract_file_not_found(self, mock_context):
        """Test error handling for missing input file."""
        result = await extract_document_fn(
            file_path="/nonexistent/file.pdf",
            ctx=mock_context
        )
        
        assert not result.success
        assert "Input file not found" in result.message
    
    @pytest.mark.asyncio
    async def test_extract_no_extractor_available(
        self, sample_pdf_path, mock_extractor_registry, mock_context
    ):
        """Test handling when no extractor is available."""
        mock_extractor_registry.auto_select.return_value = None
        
        with patch('server.registry', mock_extractor_registry):
            result = await extract_document_fn(
                file_path=str(sample_pdf_path),
                ctx=mock_context
            )
        
        assert not result.success
        assert "No suitable extractor available" in result.message
    
    @pytest.mark.asyncio
    async def test_extract_with_progress_callback(
        self, temp_directory, sample_pdf_path, mock_extractor_registry, mock_context
    ):
        """Test extraction with progress reporting."""
        # Capture progress callback
        progress_callback = None
        
        async def capture_extract(file_path, callback=None):
            nonlocal progress_callback
            progress_callback = callback
            if callback:
                await callback({'percent': 0.5, 'current': 1, 'total': 2})
            from extractors.base import ExtractionResult
            return ExtractionResult(
                markdown_content="Test content",
                page_count=1,
                extraction_method="test",
                processing_time=0.1,
                metadata={}
            )
        
        mock_extractor_registry.auto_select.return_value.extract = capture_extract
        
        with patch('server.registry', mock_extractor_registry):
            result = await extract_document_fn(
                file_path=str(sample_pdf_path),
                ctx=mock_context
            )
        
        assert result.success
        assert progress_callback is not None


class TestSegmentDocument:
    """Test the segment_document tool."""
    
    @pytest.mark.asyncio
    async def test_segment_markdown_document(
        self, temp_directory, long_document, mock_tiktoken, mock_context
    ):
        """Test segmenting a long markdown document."""
        # Create test file
        input_file = temp_directory / "long.md"
        input_file.write_text(long_document)
        
        with patch('segmenter.tiktoken.get_encoding', return_value=mock_tiktoken):
            result = await segment_document_fn(
                file_path=str(input_file),
                output_dir=str(temp_directory / "segments"),
                ctx=mock_context,
                max_tokens=5000,
                min_tokens=3000
            )
        
        assert result.success
        assert len(result.output_paths) > 1
        assert all("_of_" in path for path in result.output_paths)
        assert "total_segments" in result.statistics
    
    @pytest.mark.asyncio
    async def test_segment_file_not_found(self, temp_directory, mock_context):
        """Test error handling for missing file."""
        result = await segment_document_fn(
            file_path="/nonexistent/file.md",
            output_dir=str(temp_directory),
            ctx=mock_context
        )
        
        assert not result.success
        assert "Input file not found" in result.message
    
    @pytest.mark.asyncio
    async def test_segment_non_markdown_file(self, temp_directory, mock_context):
        """Test error for non-markdown files."""
        pdf_file = temp_directory / "test.pdf"
        pdf_file.write_bytes(b"PDF content")
        
        result = await segment_document_fn(
            file_path=str(pdf_file),
            output_dir=str(temp_directory),
            ctx=mock_context
        )
        
        assert not result.success
        assert "Only markdown or text files" in result.message
    
    @pytest.mark.asyncio
    async def test_segment_creates_report(
        self, temp_directory, sample_markdown, mock_tiktoken, mock_context
    ):
        """Test that segmentation creates a report."""
        input_file = temp_directory / "test.md"
        input_file.write_text(sample_markdown * 100)  # Make it longer
        
        with patch('segmenter.tiktoken.get_encoding', return_value=mock_tiktoken):
            result = await segment_document_fn(
                file_path=str(input_file),
                output_dir=str(temp_directory / "output"),
                ctx=mock_context
            )
        
        report_path = Path(temp_directory) / "output" / "SEGMENTATION_REPORT.md"
        assert report_path.exists()
        assert "Segmentation Report" in report_path.read_text()


class TestSplitIntoPrompts:
    """Test the split_into_prompts tool."""
    
    @pytest.mark.asyncio
    async def test_split_by_heading_level(
        self, temp_directory, sample_markdown, mock_context
    ):
        """Test splitting document by heading level."""
        input_file = temp_directory / "test.md"
        input_file.write_text(sample_markdown)
        
        result = await split_into_prompts_fn(
            file_path=str(input_file),
            output_dir=str(temp_directory / "prompts"),
            ctx=mock_context,
            split_level="h2"
        )
        
        assert result.success
        assert len(result.output_paths) == 2  # Two h2 sections
        assert all("Section" in Path(p).name for p in result.output_paths)
    
    @pytest.mark.asyncio
    async def test_split_with_parent_context(
        self, temp_directory, sample_markdown, mock_context
    ):
        """Test splitting with parent heading context."""
        input_file = temp_directory / "test.md"
        input_file.write_text(sample_markdown)
        
        result = await split_into_prompts_fn(
            file_path=str(input_file),
            output_dir=str(temp_directory / "prompts"),
            ctx=mock_context,
            split_level="h3",
            include_parent_context=True
        )
        
        assert result.success
        # Check that files contain parent context metadata
        for path in result.output_paths:
            content = Path(path).read_text()
            assert "Parent:" in content
    
    @pytest.mark.asyncio
    async def test_split_with_template(self, temp_directory, sample_markdown, mock_context):
        """Test splitting with custom prompt template."""
        input_file = temp_directory / "test.md"
        input_file.write_text(sample_markdown)
        
        template = "# {heading}\nParent: {parent}\n\n{content}"
        
        result = await split_into_prompts_fn(
            file_path=str(input_file),
            output_dir=str(temp_directory / "prompts"),
            ctx=mock_context,
            split_level="h2",
            prompt_template=template
        )
        
        assert result.success
        assert result.statistics["template_used"]
    
    @pytest.mark.asyncio
    async def test_split_no_headings_found(self, temp_directory, mock_context):
        """Test error when no headings at specified level."""
        input_file = temp_directory / "test.md"
        input_file.write_text("Just plain text without headings")
        
        result = await split_into_prompts_fn(
            file_path=str(input_file),
            output_dir=str(temp_directory / "prompts"),
            ctx=mock_context,
            split_level="h2"
        )
        
        # If no h2 headings are found, it creates a single prompt from the whole content
        assert result.success
        assert len(result.output_paths) == 1
    
    @pytest.mark.asyncio
    async def test_split_creates_report(
        self, temp_directory, sample_markdown, mock_context
    ):
        """Test that prompt splitting creates a report."""
        input_file = temp_directory / "test.md"
        input_file.write_text(sample_markdown)
        
        result = await split_into_prompts_fn(
            file_path=str(input_file),
            output_dir=str(temp_directory / "output"),
            ctx=mock_context,
            split_level="h2"
        )
        
        report_path = Path(temp_directory) / "output" / "PROMPT_REPORT.md"
        assert report_path.exists()
        assert "Prompt Generation Report" in report_path.read_text()


class TestProcessingResult:
    """Test the ProcessingResult dataclass."""
    
    def test_processing_result_creation(self):
        """Test creating a ProcessingResult."""
        result = ProcessingResult(
            success=True,
            output_paths=["/path/1", "/path/2"],
            statistics={"count": 2},
            message="Test complete"
        )
        
        assert result.success
        assert len(result.output_paths) == 2
        assert result.statistics["count"] == 2
        assert result.message == "Test complete"
        assert result.vault_path is None
    
    def test_processing_result_with_vault(self):
        """Test ProcessingResult with vault path."""
        result = ProcessingResult(
            success=True,
            output_paths=[],
            statistics={},
            message="Done",
            vault_path="/path/to/vault.json"
        )
        
        assert result.vault_path == "/path/to/vault.json"