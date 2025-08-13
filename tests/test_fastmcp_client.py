"""Test Inkognito using FastMCP's native Client class."""

import pytest
import json
from pathlib import Path
from fastmcp import Client

# Import the server directly
from server import server


class TestFastMCPClient:
    """Test core workflows using FastMCP's Client class."""
    
    @pytest.fixture
    async def client(self):
        """Create a FastMCP client connected to the server."""
        # Pass the server instance directly to Client
        async with Client(server) as client:
            yield client
    
    @pytest.fixture
    def fixtures_dir(self):
        """Get fixtures directory."""
        return Path(__file__).parent / "fixtures"
    
    @pytest.fixture
    def test_output_dir(self, tmp_path):
        """Create test output directory."""
        output_dir = tmp_path / "fastmcp_test"
        output_dir.mkdir()
        return output_dir
    
    @pytest.mark.asyncio
    async def test_list_tools(self, client):
        """Test listing available tools."""
        tools = await client.list_tools()
        tool_names = [tool.name for tool in tools]
        
        expected_tools = [
            "extract_document",
            "anonymize_documents",
            "restore_documents", 
            "segment_document",
            "split_into_prompts"
        ]
        
        for expected in expected_tools:
            assert expected in tool_names
            
        # Check tools have descriptions
        for tool in tools:
            assert tool.description is not None
            assert len(tool.description) > 10
    
    @pytest.mark.asyncio
    async def test_pdf_to_markdown(self, client, fixtures_dir, test_output_dir):
        """Test extracting PDF to Markdown."""
        pdf_file = fixtures_dir / "simple.pdf"
        if not pdf_file.exists():
            pytest.skip("Test PDF not found. Run generate_test_pdfs.py first.")
            
        output_file = test_output_dir / "simple.md"
        
        # Call extract_document tool
        result = await client.call_tool(
            "extract_document",
            {
                "file_path": str(pdf_file),
                "output_path": str(output_file)
            }
        )
        
        # Parse the result - result.data is the ProcessingResult object
        assert result.data.success is True
        assert output_file.exists()
        
        # Check content
        content = output_file.read_text()
        assert len(content) > 0
        assert "test document" in content.lower()
    
    @pytest.mark.asyncio 
    async def test_anonymize_document(self, client, fixtures_dir, test_output_dir):
        """Test anonymizing a markdown document."""
        input_file = fixtures_dir / "medical_record.md"
        assert input_file.exists()
        
        anon_dir = test_output_dir / "anonymized"
        
        # Call anonymize_documents tool
        result = await client.call_tool(
            "anonymize_documents",
            {
                "output_dir": str(anon_dir),
                "files": [str(input_file)]
            }
        )
        
        # result.data is the ProcessingResult object
        assert result.data.success is True
        assert result.data.vault_path is not None
        assert len(result.data.output_paths) == 1
        
        # Check anonymized file
        anon_file = Path(result.data.output_paths[0])
        assert anon_file.exists()
        
        # Verify PII was removed
        original_content = input_file.read_text()
        anon_content = anon_file.read_text()
        
        pii_items = [
            "Elizabeth Thompson",
            "456-78-9012",
            "elizabeth.thompson@email.com",
            "Dr. Michael Chen"
        ]
        
        for pii in pii_items:
            assert pii in original_content
            assert pii not in anon_content
    
    @pytest.mark.asyncio
    async def test_restore_documents(self, client, fixtures_dir, test_output_dir):
        """Test the full anonymize and restore cycle."""
        input_file = fixtures_dir / "medical_record.md"
        anon_dir = test_output_dir / "anonymized"
        restore_dir = test_output_dir / "restored"
        
        # Step 1: Anonymize
        anon_result = await client.call_tool(
            "anonymize_documents",
            {
                "output_dir": str(anon_dir),
                "files": [str(input_file)]
            }
        )
        
        assert anon_result.data.success is True
        
        # Step 2: Restore
        restore_result = await client.call_tool(
            "restore_documents",
            {
                "output_dir": str(restore_dir),
                "files": anon_result.data.output_paths,
                "vault_path": anon_result.data.vault_path
            }
        )
        
        assert restore_result.data.success is True
        assert len(restore_result.data.output_paths) == 1
        
        # Verify restoration
        restored_file = Path(restore_result.data.output_paths[0])
        restored_content = restored_file.read_text()
        original_content = input_file.read_text()
        
        # Check that key PII was restored
        key_pii = ["Elizabeth Thompson", "456-78-9012", "elizabeth.thompson@email.com"]
        for pii in key_pii:
            assert pii in restored_content, f"PII '{pii}' not restored"
        
        # The content might not be exactly the same if additional PII was detected
        # but the key information should be restored
        assert len(restored_content) > 0
    
    @pytest.mark.asyncio
    async def test_batch_anonymization(self, client, fixtures_dir, test_output_dir):
        """Test batch anonymization with consistent replacements."""
        test_files = [
            fixtures_dir / "medical_record.md",
            fixtures_dir / "financial_report.md",
            fixtures_dir / "legal_document.md"
        ]
        
        existing_files = [f for f in test_files if f.exists()]
        if len(existing_files) < 2:
            pytest.skip("Not enough test files for batch test")
            
        anon_dir = test_output_dir / "batch_anon"
        
        # Anonymize multiple files
        result = await client.call_tool(
            "anonymize_documents",
            {
                "output_dir": str(anon_dir),
                "files": [str(f) for f in existing_files[:2]]
            }
        )
        
        assert result.data.success is True
        assert len(result.data.output_paths) == 2
        
        # Verify single vault was created
        vault_path = Path(result.data.vault_path)
        assert vault_path.exists()
        
        vault_data = json.loads(vault_path.read_text())
        assert vault_data["version"] == "2.0"
        assert len(vault_data["mappings"]) > 0
    
    @pytest.mark.asyncio
    async def test_segment_document(self, client, test_output_dir):
        """Test document segmentation."""
        # Create a long test document
        test_doc = test_output_dir / "long_doc.md"
        
        content = ["# Long Document\n\n"]
        for i in range(20):
            content.append(f"## Section {i+1}\n\n")
            content.append(f"Content for section {i+1}. " * 50)
            content.append("\n\n")
            
        test_doc.write_text("".join(content))
        
        # Segment the document
        segments_dir = test_output_dir / "segments"
        
        result = await client.call_tool(
            "segment_document",
            {
                "file_path": str(test_doc),
                "output_dir": str(segments_dir),
                "max_tokens": 1000
            }
        )
        
        assert result.data.success is True
        # Check output paths instead
        assert len(result.data.output_paths) > 1, "Should create multiple segments"
        
        # Verify files exist
        for path in result.data.output_paths:
            assert Path(path).exists()
    
    @pytest.mark.asyncio
    async def test_error_handling(self, client, test_output_dir):
        """Test error handling for invalid inputs."""
        # Test with non-existent file
        result = await client.call_tool(
            "extract_document",
            {
                "file_path": "/non/existent/file.pdf",
                "output_path": str(test_output_dir / "output.md")
            }
        )
        
        assert result.data.success is False
        assert "not found" in result.data.message.lower()
    
    @pytest.mark.asyncio
    async def test_full_pdf_workflow(self, client, fixtures_dir, test_output_dir):
        """Test complete workflow: PDF -> Extract -> Anonymize -> Restore."""
        pdf_file = fixtures_dir / "employee_records.pdf"
        if not pdf_file.exists():
            pytest.skip("Employee records PDF not found.")
            
        # Step 1: Extract PDF
        extracted_file = test_output_dir / "employees.md"
        
        extract_result = await client.call_tool(
            "extract_document",
            {
                "file_path": str(pdf_file),
                "output_path": str(extracted_file)
            }
        )
        
        assert extract_result.data.success is True
        assert extracted_file.exists()
        
        # Step 2: Anonymize
        anon_dir = test_output_dir / "anonymized"
        
        anon_result = await client.call_tool(
            "anonymize_documents",
            {
                "output_dir": str(anon_dir),
                "files": [str(extracted_file)]
            }
        )
        
        assert anon_result.data.success is True
        
        # Step 3: Verify anonymization
        anon_file = Path(anon_result.data.output_paths[0])
        anon_content = anon_file.read_text()
        
        # Emails should be replaced with fake ones
        assert "@" not in anon_content or "@example." in anon_content
        
        # Step 4: Restore
        restore_dir = test_output_dir / "restored"
        
        restore_result = await client.call_tool(
            "restore_documents",
            {
                "output_dir": str(restore_dir),
                "files": anon_result.data.output_paths,
                "vault_path": anon_result.data.vault_path
            }
        )
        
        assert restore_result.data.success is True


if __name__ == "__main__":
    # Run a specific test
    pytest.main([__file__, "-v", "-s", "-k", "test_list_tools"])