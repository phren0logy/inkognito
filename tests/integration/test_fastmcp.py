"""FastMCP integration tests."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import json
from pathlib import Path

from server import server, ProcessingResult
from fastmcp import FastMCP


class TestFastMCPIntegration:
    """Test FastMCP server integration."""
    
    def test_server_instance(self):
        """Test that server is a FastMCP instance."""
        assert isinstance(server, FastMCP)
        assert server.name == "inkognito"
    
    def test_tools_registered(self):
        """Test that all tools are registered with the server."""
        # Get registered tools (this is FastMCP internal, may need adjustment)
        tools = []
        
        # FastMCP decorates functions, check our module
        import server as server_module
        for attr_name in dir(server_module):
            attr = getattr(server_module, attr_name)
            if callable(attr) and hasattr(attr, '__wrapped__'):
                # This is a decorated tool
                tools.append(attr_name)
        
        expected_tools = [
            'anonymize_documents',
            'restore_documents',
            'extract_document',
            'segment_document',
            'split_into_prompts'
        ]
        
        for tool in expected_tools:
            assert tool in dir(server_module)
    
    @pytest.mark.asyncio
    async def test_context_injection(self, mock_context):
        """Test that FastMCP context is properly injected."""
        with patch('server.server.get_context', return_value=mock_context):
            # Call report_progress which uses context
            from server import report_progress
            await report_progress("Test message", 0.5)
            
            mock_context.report_progress.assert_called_once_with("Test message", 0.5)
    
    @pytest.mark.asyncio
    async def test_tool_return_types(self, temp_directory):
        """Test that all tools return ProcessingResult."""
        # Test with minimal valid inputs
        test_file = temp_directory / "test.md"
        test_file.write_text("Test content")
        
        # Test extract_document
        from server import extract_document
        with patch('server.registry.auto_select', return_value=None):
            result = await extract_document(str(test_file))
            assert isinstance(result, ProcessingResult)
        
        # Test segment_document
        from server import segment_document
        result = await segment_document(
            str(test_file),
            str(temp_directory / "segments")
        )
        assert isinstance(result, ProcessingResult)
        
        # Test split_into_prompts
        from server import split_into_prompts
        result = await split_into_prompts(
            str(test_file),
            str(temp_directory / "prompts")
        )
        assert isinstance(result, ProcessingResult)
    
    @pytest.mark.asyncio
    async def test_error_handling_in_tools(self, temp_directory):
        """Test that tools handle errors gracefully."""
        # Test with non-existent file
        from server import anonymize_documents
        
        result = await anonymize_documents(
            output_dir=str(temp_directory),
            files=["/nonexistent/file.txt"]
        )
        
        assert isinstance(result, ProcessingResult)
        assert not result.success
        assert "not found" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_progress_reporting_fallback(self):
        """Test progress reporting without context."""
        with patch('server.server.get_context', return_value=None):
            with patch('server.logger.info') as mock_logger:
                from server import report_progress
                await report_progress("Test without context")
                
                mock_logger.assert_called_once()
                assert "Test without context" in mock_logger.call_args[0][0]
    
    def test_processing_result_serialization(self):
        """Test that ProcessingResult can be serialized for FastMCP."""
        result = ProcessingResult(
            success=True,
            output_paths=["/path/1", "/path/2"],
            statistics={"count": 5, "time": 1.23},
            message="Test complete",
            vault_path="/path/to/vault.json"
        )
        
        # Should be serializable to dict
        result_dict = {
            "success": result.success,
            "output_paths": result.output_paths,
            "statistics": result.statistics,
            "message": result.message,
            "vault_path": result.vault_path
        }
        
        # Should be JSON serializable (requirement for FastMCP)
        json_str = json.dumps(result_dict)
        assert json_str is not None
        
        # Can reconstruct
        parsed = json.loads(json_str)
        assert parsed["success"] == result.success
        assert parsed["output_paths"] == result.output_paths
    
    @pytest.mark.asyncio
    async def test_tool_parameter_validation(self, temp_directory):
        """Test that tools validate parameters properly."""
        from server import anonymize_documents
        
        # Test missing required parameters
        result = await anonymize_documents(
            output_dir=str(temp_directory)
            # Missing both 'files' and 'directory'
        )
        
        assert not result.success
        assert "Either 'files' or 'directory'" in result.message
    
    @pytest.mark.asyncio
    async def test_concurrent_tool_execution(self, temp_directory, sample_files):
        """Test running multiple tools concurrently."""
        from server import segment_document, split_into_prompts
        import asyncio
        
        # Create test files
        file1 = temp_directory / "doc1.md"
        file1.write_text("# Doc 1\n\n## Section A\n\nContent")
        
        file2 = temp_directory / "doc2.md"
        file2.write_text("# Doc 2\n\n## Section B\n\nContent")
        
        # Run tools concurrently
        results = await asyncio.gather(
            segment_document(str(file1), str(temp_directory / "seg1")),
            split_into_prompts(str(file2), str(temp_directory / "split2")),
            return_exceptions=True
        )
        
        # Both should succeed
        assert all(isinstance(r, ProcessingResult) for r in results)
        assert all(r.success for r in results if not isinstance(r, Exception))
    
    def test_tool_docstrings(self):
        """Test that all tools have proper docstrings for FastMCP."""
        import server as server_module
        
        tools = [
            'anonymize_documents',
            'restore_documents', 
            'extract_document',
            'segment_document',
            'split_into_prompts'
        ]
        
        for tool_name in tools:
            tool = getattr(server_module, tool_name)
            assert tool.__doc__ is not None
            assert len(tool.__doc__) > 50  # Meaningful documentation
            assert "Args:" in tool.__doc__  # Documents parameters
            assert "Returns:" in tool.__doc__  # Documents return value
    
    @pytest.mark.asyncio
    async def test_tool_metadata_preservation(self, temp_directory):
        """Test that tools preserve metadata through processing."""
        from server import anonymize_documents
        
        # Mock the anonymizer to include metadata
        with patch('anonymizer.PIIAnonymizer.anonymize_with_vault') as mock_anon:
            mock_anon.return_value = (
                "Anonymized content",
                {"PERSON": 2, "EMAIL": 1},
                {"John": ["Bob", "John"]}
            )
            
            with patch('anonymizer.PIIAnonymizer.create_scanner'):
                result = await anonymize_documents(
                    output_dir=str(temp_directory),
                    files=[str(temp_directory / "test.md")]
                )
        
        # ProcessingResult should contain statistics
        assert result.statistics is not None
        assert isinstance(result.statistics, dict)