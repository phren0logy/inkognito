#!/usr/bin/env python3
"""Manual testing script for Inkognito server with real files."""

import subprocess
import sys
import json
from pathlib import Path
import time


def run_tool(tool_name: str, **params):
    """Run a FastMCP tool and print results."""
    print(f"\n{'='*60}")
    print(f"Running: {tool_name}")
    print(f"Params: {json.dumps(params, indent=2)}")
    print('='*60)
    
    # Start the server and call the tool
    cmd = [
        sys.executable, 
        "server.py"
    ]
    
    # Create the MCP request
    request = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": params
        },
        "id": 1
    }
    
    try:
        # Run the server
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Send request
        process.stdin.write(json.dumps(request) + '\n')
        process.stdin.flush()
        
        # Wait for response
        response = process.stdout.readline()
        
        # Terminate server
        process.terminate()
        
        # Parse and print result
        if response:
            result = json.loads(response)
            print(f"Result: {json.dumps(result, indent=2)}")
        else:
            print("No response received")
            
    except Exception as e:
        print(f"Error: {e}")


def main():
    """Run manual tests."""
    print("Inkognito Manual Testing")
    print("========================")
    
    # Setup paths
    fixtures_dir = Path("tests/fixtures")
    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)
    
    # Test 1: Extract PDF
    print("\n1. Testing PDF extraction...")
    if (fixtures_dir / "simple.pdf").exists():
        run_tool(
            "extract_document",
            file_path=str(fixtures_dir / "simple.pdf"),
            output_path=str(output_dir / "simple_extracted.md")
        )
    else:
        print("PDF file not found. Run tests/fixtures/generate_test_pdfs.py first.")
    
    # Test 2: Anonymize document
    print("\n2. Testing document anonymization...")
    if (fixtures_dir / "medical_record.md").exists():
        run_tool(
            "anonymize_documents",
            output_dir=str(output_dir / "anonymized"),
            files=[str(fixtures_dir / "medical_record.md")]
        )
    
    # Test 3: Segment document
    print("\n3. Testing document segmentation...")
    if (fixtures_dir / "technical_manual.pdf").exists():
        # First extract it
        extracted_path = output_dir / "technical_manual.md"
        run_tool(
            "extract_document",
            file_path=str(fixtures_dir / "technical_manual.pdf"),
            output_path=str(extracted_path)
        )
        
        # Then segment it
        if extracted_path.exists():
            run_tool(
                "segment_document",
                file_path=str(extracted_path),
                output_dir=str(output_dir / "segments"),
                max_tokens=5000
            )
    
    print("\n" + "="*60)
    print("Manual testing complete!")
    print(f"Check output in: {output_dir}")


if __name__ == "__main__":
    main()