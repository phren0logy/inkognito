"""Integration tests with live FastMCP server using fastmcp CLI."""

import pytest
import subprocess
import json
import time
from pathlib import Path
import tempfile
import os
from typing import Dict, Any


class TestLiveFastMCPServer:
    """Test suite that runs against a live FastMCP server."""
    
    @pytest.fixture
    def test_documents(self, tmp_path):
        """Create test documents for the integration tests."""
        # Create a markdown file with PII
        pii_doc = tmp_path / "confidential.md"
        pii_doc.write_text("""# Confidential Employee Information

## Personal Details

**Name:** Sarah Johnson
**Email:** sarah.johnson@acmecorp.com
**Phone:** +1 (415) 555-0123
**SSN:** 234-56-7890
**Date of Birth:** March 15, 1985
**Address:** 789 Market Street, Suite 500, San Francisco, CA 94103

## Emergency Contact

**Name:** Michael Johnson
**Relationship:** Spouse
**Phone:** +1 (415) 555-0124

## Banking Information

**Bank:** First National Bank
**Account Number:** 1234567890
**Routing:** 121000248

## Performance Review - Q4 2023

Sarah Johnson has exceeded expectations this quarter. On December 15, 2023, 
she successfully led the product launch that resulted in $2.5M in revenue.

Her manager, David Chen (david.chen@acmecorp.com), recommends a 15% salary increase.
""")
        
        # Create a large document for segmentation testing
        large_doc = tmp_path / "technical_manual.md"
        content = "# Technical Manual\n\n"
        
        # Generate 50+ sections to ensure multiple segments
        for chapter in range(1, 11):
            content += f"# Chapter {chapter}: System Architecture\n\n"
            content += f"This chapter covers the detailed architecture of component {chapter}.\n\n"
            
            for section in range(1, 6):
                content += f"## {chapter}.{section} Subsystem Design\n\n"
                content += "This subsystem handles critical operations including:\n"
                content += "- Data processing and validation\n"
                content += "- Error handling and recovery\n"
                content += "- Performance optimization\n\n"
                
                # Add substantial content to each section
                content += "Detailed technical explanation follows. " * 50
                content += "\n\n"
                
                content += "### Implementation Details\n\n"
                content += "The implementation uses advanced algorithms. " * 30
                content += "\n\n"
        
        large_doc.write_text(content)
        
        # Create a structured doc for prompt splitting
        api_doc = tmp_path / "api_docs.md"
        api_doc.write_text("""# API Documentation

## Authentication APIs

### Login Endpoint
POST /api/v1/auth/login

Authenticates a user and returns a JWT token.

Request body:
```json
{
  "username": "string",
  "password": "string"
}
```

Response:
```json
{
  "token": "jwt_token_here",
  "expires_in": 3600
}
```

### Logout Endpoint
POST /api/v1/auth/logout

Invalidates the current session token.

## User Management APIs

### List Users
GET /api/v1/users

Returns a paginated list of users.

Query parameters:
- page (int): Page number
- limit (int): Items per page

### Create User
POST /api/v1/users

Creates a new user account.

Request body:
```json
{
  "username": "string",
  "email": "string",
  "role": "admin|user"
}
```

## Data APIs

### Export Data
GET /api/v1/data/export

Exports data in the requested format.

Query parameters:
- format: "csv", "json", or "xml"
- start_date: ISO 8601 date
- end_date: ISO 8601 date
""")
        
        return {
            'pii_doc': pii_doc,
            'large_doc': large_doc,
            'api_doc': api_doc,
            'test_dir': tmp_path
        }
    
    def run_fastmcp_tool(self, tool_name: str, **params) -> Dict[str, Any]:
        """Run a FastMCP tool using the CLI and return the result."""
        # Build the command
        cmd = ["uv", "run", "fastmcp", "run", "server.py", "--call", tool_name]
        
        # Add parameters as JSON
        if params:
            cmd.extend(["--params", json.dumps(params)])
        
        # Run the command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"FastMCP command failed: {result.stderr}")
        
        # Parse the JSON output
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            # If not JSON, return as string
            return {"output": result.stdout, "error": result.stderr}
    
    def test_anonymize_single_document(self, test_documents):
        """Test anonymizing a single document with PII."""
        output_dir = test_documents['test_dir'] / "anonymized"
        
        # Run anonymization
        result = self.run_fastmcp_tool(
            "anonymize_documents",
            output_dir=str(output_dir),
            files=[str(test_documents['pii_doc'])]
        )
        
        # Verify success
        assert result['success'] is True
        assert len(result['output_paths']) == 1
        assert result['vault_path'] is not None
        
        # Check output files exist
        output_file = Path(result['output_paths'][0])
        vault_file = Path(result['vault_path'])
        assert output_file.exists()
        assert vault_file.exists()
        
        # Read anonymized content
        anonymized_content = output_file.read_text()
        
        # Verify PII was replaced
        assert "Sarah Johnson" not in anonymized_content
        assert "sarah.johnson@acmecorp.com" not in anonymized_content
        assert "234-56-7890" not in anonymized_content
        assert "1234567890" not in anonymized_content  # Account number
        
        # Verify structure is preserved
        assert "# Confidential Employee Information" in anonymized_content
        assert "## Personal Details" in anonymized_content
        assert "**Name:**" in anonymized_content
        assert "**Email:**" in anonymized_content
        
        # Check statistics
        assert result['statistics']['PERSON'] >= 3  # Sarah, Michael, David
        assert result['statistics']['EMAIL_ADDRESS'] >= 2
        assert result['statistics']['PHONE_NUMBER'] >= 2
        
        # Verify vault structure
        vault_data = json.loads(vault_file.read_text())
        assert 'version' in vault_data
        assert 'date_offset' in vault_data
        assert 'mappings' in vault_data
        assert len(vault_data['mappings']) > 0
    
    def test_restore_anonymized_document(self, test_documents):
        """Test restoring an anonymized document using vault."""
        anon_dir = test_documents['test_dir'] / "anon_test"
        restore_dir = test_documents['test_dir'] / "restore_test"
        
        # First anonymize
        anon_result = self.run_fastmcp_tool(
            "anonymize_documents",
            output_dir=str(anon_dir),
            files=[str(test_documents['pii_doc'])]
        )
        
        assert anon_result['success'] is True
        
        # Then restore
        restore_result = self.run_fastmcp_tool(
            "restore_documents",
            output_dir=str(restore_dir),
            files=anon_result['output_paths'],
            vault_path=anon_result['vault_path']
        )
        
        # Verify restoration
        assert restore_result['success'] is True
        assert len(restore_result['output_paths']) == 1
        
        # Compare content
        original_content = test_documents['pii_doc'].read_text()
        restored_content = Path(restore_result['output_paths'][0]).read_text()
        
        # Check key PII is restored
        assert "Sarah Johnson" in restored_content
        assert "sarah.johnson@acmecorp.com" in restored_content
        assert "234-56-7890" in restored_content
        assert "Michael Johnson" in restored_content
        assert "David Chen" in restored_content
    
    def test_segment_large_document(self, test_documents):
        """Test segmenting a large document into chunks."""
        output_dir = test_documents['test_dir'] / "segments"
        
        result = self.run_fastmcp_tool(
            "segment_document",
            file_path=str(test_documents['large_doc']),
            output_dir=str(output_dir),
            max_tokens=5000,
            min_tokens=3000,
            break_at_headings=["h1", "h2"]
        )
        
        # Verify segmentation
        assert result['success'] is True
        assert len(result['output_paths']) >= 3  # Should create multiple segments
        
        # Check each segment
        total_content = ""
        for i, segment_path in enumerate(result['output_paths']):
            segment_file = Path(segment_path)
            assert segment_file.exists()
            
            content = segment_file.read_text()
            
            # Verify metadata comments
            assert f"Segment {i+1} of {len(result['output_paths'])}" in content
            assert "Tokens:" in content
            assert "Lines:" in content
            
            total_content += content
        
        # Verify all chapters are included
        for chapter in range(1, 11):
            assert f"Chapter {chapter}" in total_content
        
        # Check statistics
        assert result['statistics']['total_segments'] >= 3
        assert result['statistics']['min_tokens'] >= 3000
        assert result['statistics']['max_tokens'] <= 5000
        
        # Verify report exists
        report_path = Path(output_dir) / "SEGMENTATION_REPORT.md"
        assert report_path.exists()
    
    def test_split_into_prompts(self, test_documents):
        """Test splitting a document into individual prompts."""
        output_dir = test_documents['test_dir'] / "prompts"
        
        # Split by h2 headings
        result = self.run_fastmcp_tool(
            "split_into_prompts",
            file_path=str(test_documents['api_doc']),
            output_dir=str(output_dir),
            split_level="h2",
            include_parent_context=True
        )
        
        # Verify prompt generation
        assert result['success'] is True
        assert len(result['output_paths']) == 3  # Three h2 sections
        
        # Check generated prompts
        prompts_content = []
        for prompt_path in result['output_paths']:
            prompt_file = Path(prompt_path)
            assert prompt_file.exists()
            
            content = prompt_file.read_text()
            prompts_content.append(content)
            
            # Verify metadata
            assert "<!-- Prompt" in content
            assert "<!-- Heading:" in content
            assert "<!-- Level: H2" in content
        
        # Verify each section became a prompt
        assert any("Authentication APIs" in c for c in prompts_content)
        assert any("User Management APIs" in c for c in prompts_content)
        assert any("Data APIs" in c for c in prompts_content)
        
        # Check report
        report_path = Path(output_dir) / "PROMPT_REPORT.md"
        assert report_path.exists()
    
    def test_anonymize_directory(self, test_documents):
        """Test anonymizing all files in a directory."""
        # Create multiple files with shared PII
        docs_dir = test_documents['test_dir'] / "multiple_docs"
        docs_dir.mkdir()
        
        # Create related documents
        for i in range(3):
            doc = docs_dir / f"report_{i+1}.md"
            doc.write_text(f"""# Monthly Report {i+1}

**Author:** Sarah Johnson
**Email:** sarah.johnson@acmecorp.com
**Date:** 2024-0{i+1}-15

## Summary

This month, Sarah Johnson worked with Michael Chen on Project Alpha.
Contact Michael at michael.chen@acmecorp.com or (555) 555-{1000+i}.

## Financial Data

Transaction ID: TXN-2024-{1000+i}
Amount: ${10000 + i * 1000}
Approved by: David Wilson (david.wilson@acmecorp.com)
""")
        
        # Anonymize directory
        output_dir = test_documents['test_dir'] / "anon_batch"
        result = self.run_fastmcp_tool(
            "anonymize_documents",
            output_dir=str(output_dir),
            directory=str(docs_dir),
            patterns=["*.md"]
        )
        
        # Verify results
        assert result['success'] is True
        assert len(result['output_paths']) == 3
        
        # Check consistency across files
        sarah_replacements = set()
        michael_replacements = set()
        
        for output_path in result['output_paths']:
            content = Path(output_path).read_text()
            
            # Extract author name (the replacement for Sarah)
            for line in content.split('\n'):
                if line.startswith("**Author:**"):
                    sarah_replacements.add(line.split(":**")[1].strip())
                elif "worked with" in line and "on Project Alpha" in line:
                    # Extract Michael's replacement
                    parts = line.split("worked with")[1].split("on Project Alpha")[0]
                    michael_replacements.add(parts.strip())
        
        # Same person should have same replacement
        assert len(sarah_replacements) == 1, "Sarah should have consistent replacement"
        assert len(michael_replacements) == 1, "Michael should have consistent replacement"
        
        # Different people should have different replacements
        assert sarah_replacements != michael_replacements
    
    def test_error_handling(self, test_documents):
        """Test error handling for invalid inputs."""
        # Test with non-existent file
        result = self.run_fastmcp_tool(
            "anonymize_documents",
            output_dir=str(test_documents['test_dir'] / "error_test"),
            files=["/non/existent/file.md"]
        )
        
        assert result['success'] is False
        assert "not found" in result['message'].lower()
        
        # Test with missing required parameters
        result = self.run_fastmcp_tool(
            "segment_document",
            file_path="/non/existent.md",
            output_dir=str(test_documents['test_dir'] / "error_test2")
        )
        
        assert result['success'] is False
    
    def test_custom_prompt_template(self, test_documents):
        """Test using a custom prompt template for splitting."""
        output_dir = test_documents['test_dir'] / "custom_prompts"
        
        template = """# Prompt: {heading}

**Level:** H{level}
**Parent Section:** {parent}

## Content

{content}

---
*Generated from API documentation*
"""
        
        result = self.run_fastmcp_tool(
            "split_into_prompts",
            file_path=str(test_documents['api_doc']),
            output_dir=str(output_dir),
            split_level="h3",
            include_parent_context=True,
            prompt_template=template
        )
        
        assert result['success'] is True
        
        # Verify template was applied
        for prompt_path in result['output_paths']:
            content = Path(prompt_path).read_text()
            assert "# Prompt:" in content
            assert "**Level:** H3" in content
            assert "**Parent Section:**" in content
            assert "*Generated from API documentation*" in content


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])