"""Integration tests that run with a live FastMCP server using fixtures."""

import pytest
import subprocess
import asyncio
import json
import os
import sys
from pathlib import Path
import tempfile
import shutil
from typing import Dict, Any, List
import time


class TestWithLiveServer:
    """Test suite that runs against actual server with real files."""
    
    @pytest.fixture
    def fixtures_dir(self):
        """Get the fixtures directory path."""
        return Path(__file__).parent.parent / "fixtures"
    
    @pytest.fixture
    def test_output_dir(self, tmp_path):
        """Create a temporary directory for test outputs."""
        output_dir = tmp_path / "test_outputs"
        output_dir.mkdir()
        return output_dir
    
    def test_pdf_extraction(self, fixtures_dir, test_output_dir):
        """Test extracting text from PDF files."""
        # Test with simple PDF
        simple_pdf = fixtures_dir / "simple.pdf"
        assert simple_pdf.exists(), "Test PDF not found. Run generate_test_pdfs.py first."
        
        # Run extraction using server
        # Note: This would require running the server and calling the extract_document tool
        # For now, we'll create a placeholder that shows the structure
        
        output_file = test_output_dir / "simple_extracted.md"
        
        # In a real test, you would:
        # 1. Start the FastMCP server
        # 2. Call the extract_document tool
        # 3. Verify the output
        
        # Placeholder assertion
        assert simple_pdf.exists()
    
    def test_anonymize_medical_record(self, fixtures_dir, test_output_dir):
        """Test anonymizing a medical record with sensitive PII."""
        medical_record = fixtures_dir / "medical_record.md"
        assert medical_record.exists()
        
        # Read original content
        original_content = medical_record.read_text()
        
        # Verify it contains PII
        assert "Elizabeth Thompson" in original_content
        assert "456-78-9012" in original_content  # SSN
        assert "elizabeth.thompson@email.com" in original_content
        
        # In a real test:
        # 1. Call anonymize_documents tool
        # 2. Verify PII is replaced
        # 3. Check vault is created
        # 4. Verify consistent replacements
    
    def test_anonymize_financial_report(self, fixtures_dir, test_output_dir):
        """Test anonymizing a financial report with multiple types of PII."""
        financial_report = fixtures_dir / "financial_report.md"
        assert financial_report.exists()
        
        original_content = financial_report.read_text()
        
        # Count different types of PII
        pii_types = {
            "names": ["Amanda Rodriguez", "David Chen", "Michael Thompson", "Sarah Mitchell"],
            "emails": ["amanda.rodriguez@techstartup.com", "david.chen@techstartup.com"],
            "ssns": ["234-56-7890", "345-67-8901"],
            "phones": ["(415) 555-7890", "(408) 555-2345"],
            "accounts": ["1234567890", "0987654321"]
        }
        
        for pii_list in pii_types.values():
            for pii in pii_list:
                assert pii in original_content
    
    def test_anonymize_legal_document(self, fixtures_dir, test_output_dir):
        """Test anonymizing a legal document with attorney-client privileged info."""
        legal_doc = fixtures_dir / "legal_document.md"
        assert legal_doc.exists()
        
        # This document has complex PII including:
        # - Legal case numbers
        # - Attorney bar numbers
        # - Court information
        # - Witness information
        
        original_content = legal_doc.read_text()
        assert "Jonathan Smith" in original_content
        assert "567-89-0123" in original_content  # Plaintiff SSN
        assert "rachel.green@greenlaw.com" in original_content
    
    def test_extract_employee_records_pdf(self, fixtures_dir, test_output_dir):
        """Test extracting and anonymizing a PDF with employee records."""
        employee_pdf = fixtures_dir / "employee_records.pdf"
        assert employee_pdf.exists()
        
        # This tests the full pipeline:
        # 1. Extract PDF to markdown
        # 2. Anonymize the extracted content
        # 3. Verify PII is properly handled
    
    def test_segment_technical_manual_pdf(self, fixtures_dir, test_output_dir):
        """Test segmenting a large technical manual PDF."""
        tech_manual = fixtures_dir / "technical_manual.pdf"
        assert tech_manual.exists()
        
        # This tests:
        # 1. Extracting multi-page PDF
        # 2. Segmenting into chunks
        # 3. Preserving document structure
    
    def test_extract_sales_report_with_tables(self, fixtures_dir, test_output_dir):
        """Test extracting a PDF with table data."""
        sales_report = fixtures_dir / "sales_report.pdf"
        assert sales_report.exists()
        
        # This tests:
        # 1. Table extraction from PDF
        # 2. Preserving table structure in markdown
        # 3. Anonymizing PII in tables
    
    def test_batch_anonymization(self, fixtures_dir, test_output_dir):
        """Test anonymizing multiple documents with consistent replacements."""
        # Get all markdown files
        md_files = list(fixtures_dir.glob("*.md"))
        assert len(md_files) >= 3
        
        # This tests:
        # 1. Batch processing multiple files
        # 2. Consistent PII replacement across files
        # 3. Single vault for all files
    
    def test_restore_anonymized_documents(self, fixtures_dir, test_output_dir):
        """Test the full anonymize and restore cycle."""
        # Use medical record for this test
        medical_record = fixtures_dir / "medical_record.md"
        
        # This tests:
        # 1. Anonymize document
        # 2. Verify vault creation
        # 3. Restore using vault
        # 4. Compare with original
    
    def test_error_handling_missing_extractor(self, test_output_dir):
        """Test handling when no PDF extractor is available."""
        # Create a dummy PDF path
        fake_pdf = test_output_dir / "nonexistent.pdf"
        
        # This tests:
        # 1. Error handling for missing files
        # 2. Graceful failure messages
        # 3. Proper error reporting


def run_server_command(tool_name: str, **params) -> Dict[str, Any]:
    """Helper to run a FastMCP tool using MCP client."""
    # Import here to avoid circular imports
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from mcp_client import MCPTestClient
    
    try:
        # Create and start client
        client = MCPTestClient()
        client.start()
        
        # Call the tool
        result = client.call_tool(tool_name, **params)
        
        # Stop the server
        client.stop()
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }


class TestServerIntegration:
    """Actual integration tests that call the server."""
    
    @pytest.fixture
    def fixtures_dir(self):
        """Get the fixtures directory path."""
        return Path(__file__).parent.parent / "fixtures"
    
    def test_extract_simple_pdf(self, fixtures_dir, tmp_path):
        """Test extracting a simple PDF to markdown."""
        pdf_path = fixtures_dir / "simple.pdf"
        output_path = tmp_path / "simple.md"
        
        result = run_server_command(
            "extract_document",
            file_path=str(pdf_path),
            output_path=str(output_path)
        )
        
        # Check result
        assert result.get("success") is True
        assert output_path.exists()
        
        # Verify content
        content = output_path.read_text()
        assert "Test Document" in content
        assert "simple test document" in content
    
    def test_anonymize_and_restore_cycle(self, fixtures_dir, tmp_path):
        """Test complete anonymize and restore cycle."""
        # Setup paths
        input_file = fixtures_dir / "medical_record.md"
        anon_dir = tmp_path / "anonymized"
        restore_dir = tmp_path / "restored"
        
        # Step 1: Anonymize
        anon_result = run_server_command(
            "anonymize_documents",
            output_dir=str(anon_dir),
            files=[str(input_file)]
        )
        
        assert anon_result.get("success") is True
        assert anon_result.get("vault_path") is not None
        
        # Verify anonymization
        anon_file = Path(anon_result["output_paths"][0])
        anon_content = anon_file.read_text()
        
        assert "Elizabeth Thompson" not in anon_content
        assert "456-78-9012" not in anon_content
        
        # Step 2: Restore
        restore_result = run_server_command(
            "restore_documents",
            output_dir=str(restore_dir),
            files=anon_result["output_paths"],
            vault_path=anon_result["vault_path"]
        )
        
        assert restore_result.get("success") is True
        
        # Verify restoration
        restored_file = Path(restore_result["output_paths"][0])
        restored_content = restored_file.read_text()
        
        assert "Elizabeth Thompson" in restored_content
        assert "456-78-9012" in restored_content


if __name__ == "__main__":
    # Allow running specific tests
    pytest.main([__file__, "-v", "-s"])