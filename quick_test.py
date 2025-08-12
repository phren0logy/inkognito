#!/usr/bin/env python3
"""Quick test to verify server functionality."""

import asyncio
from pathlib import Path
from server import anonymize_documents, ProcessingResult
from fastmcp import Context
from unittest.mock import Mock, AsyncMock


async def test_anonymization():
    """Test anonymizing a document directly."""
    # Create mock context
    mock_context = Mock(spec=Context)
    mock_context.info = AsyncMock()
    mock_context.debug = AsyncMock()
    mock_context.warning = AsyncMock()
    mock_context.error = AsyncMock()
    mock_context.report_progress = Mock()
    
    # Paths
    fixtures_dir = Path("tests/fixtures")
    medical_record = fixtures_dir / "medical_record.md"
    output_dir = Path("test_output/quick_test")
    
    print(f"Testing anonymization of: {medical_record}")
    print(f"Output directory: {output_dir}")
    
    if not medical_record.exists():
        print("ERROR: Test file not found!")
        return
    
    # Run anonymization
    result = await anonymize_documents.fn(
        output_dir=str(output_dir),
        ctx=mock_context,
        files=[str(medical_record)]
    )
    
    print(f"\nResult: {result}")
    print(f"Success: {result.success}")
    print(f"Message: {result.message}")
    
    if result.success:
        print(f"\nOutput files: {result.output_paths}")
        print(f"Vault: {result.vault_path}")
        print(f"Statistics: {result.statistics}")
        
        # Check anonymized content
        anon_file = Path(result.output_paths[0])
        if anon_file.exists():
            content = anon_file.read_text()
            
            # Check PII was removed
            original_content = medical_record.read_text()
            
            print("\nPII Check:")
            pii_items = [
                "Elizabeth Thompson",
                "456-78-9012",
                "elizabeth.thompson@email.com",
                "Dr. Michael Chen"
            ]
            
            for pii in pii_items:
                in_original = pii in original_content
                in_anonymized = pii in content
                print(f"  {pii}: Original={in_original}, Anonymized={in_anonymized}")


if __name__ == "__main__":
    asyncio.run(test_anonymization())