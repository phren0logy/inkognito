"""Integration tests that run against a real FastMCP server."""

import pytest
import asyncio
import subprocess
import time
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
import tempfile
import shutil
from datetime import datetime
import os

# FastMCP client for testing
from fastmcp import Client


class FastMCPTestServer:
    """Helper to manage a FastMCP server process for testing."""
    
    def __init__(self, server_path: str = "server.py"):
        self.server_path = server_path
        self.process = None
        self.client = None
        
    async def start(self):
        """Start the FastMCP server process."""
        # Start server with subprocess
        self.process = subprocess.Popen(
            [sys.executable, self.server_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Give server time to start
        await asyncio.sleep(2)
        
        # Create client connected to the server
        self.client = Client(
            server_params={
                "command": [sys.executable, self.server_path],
                "args": []
            }
        )
        
        # Initialize the client
        await self.client.initialize()
        
    async def stop(self):
        """Stop the FastMCP server process."""
        if self.client:
            await self.client.close()
            
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            
    async def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call a tool on the server and return the result."""
        return await self.client.call_tool(tool_name, **kwargs)


@pytest.fixture
async def fastmcp_server():
    """Fixture that provides a running FastMCP server."""
    server = FastMCPTestServer()
    await server.start()
    yield server
    await server.stop()


@pytest.fixture
def test_documents(tmp_path):
    """Create test documents with various content."""
    docs_dir = tmp_path / "test_docs"
    docs_dir.mkdir()
    
    # Create a markdown file with PII
    pii_doc = docs_dir / "employee_records.md"
    pii_doc.write_text("""# Employee Records

## Engineering Team

### John Smith
- Email: john.smith@techcorp.com
- Phone: (555) 123-4567
- SSN: 123-45-6789
- Date of Birth: 1985-03-15
- Address: 123 Main Street, San Francisco, CA 94105

### Jane Doe
- Email: jane.doe@techcorp.com
- Phone: (555) 987-6543
- SSN: 987-65-4321
- Date of Birth: 1990-07-22
- Address: 456 Oak Avenue, San Jose, CA 95110

## Recent Transactions

On 2024-01-15, John Smith processed payment of $50,000 to vendor Acme Corp.
Jane Doe approved the transaction on 2024-01-16.

## Meeting Notes

Meeting held on 2024-02-10 with John Smith and Jane Doe to discuss Q1 targets.
Follow-up scheduled for 2024-02-17.
""")
    
    # Create a large document for segmentation
    large_doc = docs_dir / "technical_guide.md"
    content = "# Technical Documentation\n\n"
    for i in range(10):
        content += f"## Chapter {i+1}: Topic {i+1}\n\n"
        content += "This is a detailed explanation of the topic. " * 100
        content += "\n\n"
        for j in range(3):
            content += f"### Section {i+1}.{j+1}\n\n"
            content += "Detailed content for this section. " * 50
            content += "\n\n"
    large_doc.write_text(content)
    
    # Create a structured document for prompt splitting
    structured_doc = docs_dir / "api_reference.md"
    structured_doc.write_text("""# API Reference

## Authentication

### GET /auth/login
Login endpoint for user authentication.

Parameters:
- username: string (required)
- password: string (required)

Returns: JWT token

### POST /auth/logout
Logout endpoint to invalidate session.

## User Management

### GET /users
List all users in the system.

Parameters:
- page: integer (optional)
- limit: integer (optional)

### POST /users
Create a new user account.

Parameters:
- name: string (required)
- email: string (required)
- role: string (optional)

## Data Operations

### GET /data/export
Export data in various formats.

Parameters:
- format: string (csv, json, xml)
- date_from: date (optional)
- date_to: date (optional)
""")
    
    # Return paths
    return {
        'pii_doc': pii_doc,
        'large_doc': large_doc,
        'structured_doc': structured_doc,
        'docs_dir': docs_dir
    }


class TestRealServerIntegration:
    """Test suite for real FastMCP server integration."""
    
    @pytest.mark.asyncio
    async def test_server_startup(self, fastmcp_server):
        """Test that the server starts and responds to requests."""
        # Server should be running and client connected
        assert fastmcp_server.process is not None
        assert fastmcp_server.client is not None
        
        # Try to list available tools
        tools = await fastmcp_server.client.list_tools()
        assert len(tools) > 0
        
        expected_tools = [
            'anonymize_documents',
            'restore_documents',
            'extract_document',
            'segment_document',
            'split_into_prompts'
        ]
        
        tool_names = [tool['name'] for tool in tools]
        for expected in expected_tools:
            assert expected in tool_names
    
    @pytest.mark.asyncio
    async def test_anonymize_documents_e2e(self, fastmcp_server, test_documents, tmp_path):
        """Test end-to-end document anonymization with real server."""
        output_dir = tmp_path / "anonymized_output"
        
        # Call anonymize_documents tool
        result = await fastmcp_server.call_tool(
            "anonymize_documents",
            output_dir=str(output_dir),
            files=[str(test_documents['pii_doc'])]
        )
        
        # Verify result
        assert result['success'] is True
        assert len(result['output_paths']) == 1
        assert result['vault_path'] is not None
        
        # Check that output files exist
        assert Path(result['output_paths'][0]).exists()
        assert Path(result['vault_path']).exists()
        
        # Read anonymized content
        anonymized_content = Path(result['output_paths'][0]).read_text()
        
        # Verify PII was replaced
        assert "John Smith" not in anonymized_content
        assert "jane.doe@techcorp.com" not in anonymized_content
        assert "123-45-6789" not in anonymized_content
        
        # Verify statistics
        assert 'statistics' in result
        assert result['statistics'].get('PERSON', 0) > 0
        assert result['statistics'].get('EMAIL_ADDRESS', 0) > 0
    
    @pytest.mark.asyncio
    async def test_restore_documents_e2e(self, fastmcp_server, test_documents, tmp_path):
        """Test document restoration with real server."""
        anon_output = tmp_path / "anonymized"
        restore_output = tmp_path / "restored"
        
        # First anonymize
        anon_result = await fastmcp_server.call_tool(
            "anonymize_documents",
            output_dir=str(anon_output),
            files=[str(test_documents['pii_doc'])]
        )
        
        assert anon_result['success'] is True
        vault_path = anon_result['vault_path']
        
        # Then restore
        restore_result = await fastmcp_server.call_tool(
            "restore_documents",
            output_dir=str(restore_output),
            files=anon_result['output_paths'],
            vault_path=vault_path
        )
        
        # Verify restoration
        assert restore_result['success'] is True
        assert len(restore_result['output_paths']) == 1
        
        # Compare with original
        original_content = test_documents['pii_doc'].read_text()
        restored_content = Path(restore_result['output_paths'][0]).read_text()
        
        # Should contain original PII
        assert "John Smith" in restored_content
        assert "jane.doe@techcorp.com" in restored_content
        assert "123-45-6789" in restored_content
    
    @pytest.mark.asyncio
    async def test_segment_document_e2e(self, fastmcp_server, test_documents, tmp_path):
        """Test document segmentation with real server."""
        output_dir = tmp_path / "segments"
        
        result = await fastmcp_server.call_tool(
            "segment_document",
            file_path=str(test_documents['large_doc']),
            output_dir=str(output_dir),
            max_tokens=5000,
            min_tokens=3000
        )
        
        # Verify segmentation
        assert result['success'] is True
        assert len(result['output_paths']) > 1  # Should create multiple segments
        
        # Verify statistics
        assert 'statistics' in result
        assert result['statistics']['total_segments'] > 1
        assert result['statistics']['average_tokens'] > 0
        
        # Check segment files exist
        for path in result['output_paths']:
            assert Path(path).exists()
            
        # Verify report was created
        report_path = output_dir / "SEGMENTATION_REPORT.md"
        assert report_path.exists()
    
    @pytest.mark.asyncio
    async def test_split_into_prompts_e2e(self, fastmcp_server, test_documents, tmp_path):
        """Test prompt splitting with real server."""
        output_dir = tmp_path / "prompts"
        
        result = await fastmcp_server.call_tool(
            "split_into_prompts",
            file_path=str(test_documents['structured_doc']),
            output_dir=str(output_dir),
            split_level="h2"
        )
        
        # Verify prompt generation
        assert result['success'] is True
        assert len(result['output_paths']) == 3  # Three H2 sections
        
        # Check that prompts were created correctly
        prompts_created = []
        for path in result['output_paths']:
            assert Path(path).exists()
            content = Path(path).read_text()
            prompts_created.append(content)
        
        # Verify each major section became a prompt
        assert any("Authentication" in p for p in prompts_created)
        assert any("User Management" in p for p in prompts_created)
        assert any("Data Operations" in p for p in prompts_created)
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self, fastmcp_server, test_documents, tmp_path):
        """Test running multiple operations concurrently."""
        tasks = [
            fastmcp_server.call_tool(
                "anonymize_documents",
                output_dir=str(tmp_path / "anon1"),
                files=[str(test_documents['pii_doc'])]
            ),
            fastmcp_server.call_tool(
                "segment_document",
                file_path=str(test_documents['large_doc']),
                output_dir=str(tmp_path / "seg1"),
                max_tokens=10000
            ),
            fastmcp_server.call_tool(
                "split_into_prompts",
                file_path=str(test_documents['structured_doc']),
                output_dir=str(tmp_path / "prompts1"),
                split_level="h3"
            )
        ]
        
        # Run all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should succeed
        for result in results:
            assert not isinstance(result, Exception)
            assert result['success'] is True
    
    @pytest.mark.asyncio
    async def test_error_handling(self, fastmcp_server, tmp_path):
        """Test server error handling with invalid inputs."""
        # Test with non-existent file
        result = await fastmcp_server.call_tool(
            "anonymize_documents",
            output_dir=str(tmp_path / "output"),
            files=["/non/existent/file.md"]
        )
        
        assert result['success'] is False
        assert "not found" in result['message'].lower()
        
        # Test with invalid parameters
        result = await fastmcp_server.call_tool(
            "segment_document",
            file_path="/non/existent.md",
            output_dir=str(tmp_path / "output")
        )
        
        assert result['success'] is False
    
    @pytest.mark.asyncio
    async def test_large_scale_anonymization(self, fastmcp_server, tmp_path):
        """Test anonymizing multiple documents with consistent replacements."""
        docs_dir = tmp_path / "multi_docs"
        docs_dir.mkdir()
        
        # Create multiple documents with overlapping PII
        for i in range(5):
            doc = docs_dir / f"doc_{i}.md"
            doc.write_text(f"""# Document {i}

Author: John Smith
Email: john.smith@company.com

Reviewed by: Jane Doe
Email: jane.doe@company.com

Content specific to document {i}.
Meeting date: 2024-03-{10+i}
""")
        
        # Anonymize all documents
        result = await fastmcp_server.call_tool(
            "anonymize_documents",
            output_dir=str(tmp_path / "anon_output"),
            directory=str(docs_dir),
            patterns=["*.md"]
        )
        
        assert result['success'] is True
        assert len(result['output_paths']) == 5
        
        # Verify consistent replacements across all documents
        john_replacements = set()
        jane_replacements = set()
        
        for output_path in result['output_paths']:
            content = Path(output_path).read_text()
            
            # Extract the replacement names
            lines = content.split('\n')
            for line in lines:
                if line.startswith("Author:"):
                    john_replacements.add(line.split(":")[1].strip())
                elif line.startswith("Reviewed by:"):
                    jane_replacements.add(line.split(":")[1].strip())
        
        # Same person should have same replacement across all docs
        assert len(john_replacements) == 1
        assert len(jane_replacements) == 1
        assert john_replacements != jane_replacements