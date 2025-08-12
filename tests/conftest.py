"""Shared test fixtures and configuration for Inkognito tests."""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock
from datetime import datetime
import json
from typing import Dict, List, Any

# Sample data constants
SAMPLE_MARKDOWN = """# Sample Document

This is a sample markdown document without any PII.

## Section 1

Some regular text content here.

### Subsection 1.1

More content without personal information.

## Section 2

Final section with normal text.
"""

SAMPLE_MARKDOWN_WITH_PII = """# Employee Records

## John Smith Profile

- Name: John Smith
- Email: john.smith@example.com
- Phone: +1-555-123-4567
- SSN: 123-45-6789
- Address: 123 Main Street, New York, NY 10001
- Company: Acme Corporation
- Employee ID: EMP001
- Credit Card: 4111-1111-1111-1111
- Date of Birth: 1985-03-15
- Medical License: MD-1234567
- IP Address: 192.168.1.100
- Website: https://johnsmith.com
- Passport: US12345678
- Driver's License: DL-12345678
- Bank Account: 1234567890
- Crypto Wallet: 0x742d35Cc6634C0532925a3b844Bc9e7595f5b41a

## Meeting Notes

John Smith (john.smith@example.com) met with Jane Doe from Tech Solutions Inc. 
on 2024-01-15 at their office at 456 Oak Avenue, San Francisco, CA 94102.
"""

SAMPLE_VAULT_DATA = {
    "version": "2.0",
    "created_at": "2024-01-01T00:00:00",
    "statistics": {
        "files_processed": 1,
        "total_replacements": 5
    },
    "date_offset": 180,
    "mappings": {
        "John Smith": "Robert Johnson",
        "john.smith@example.com": "robert.johnson@example.com",
        "+1-555-123-4567": "+1-555-987-6543",
        "123-45-6789": "987-65-4321",
        "Acme Corporation": "Global Industries"
    }
}


@pytest.fixture
def sample_markdown():
    """Return sample markdown content without PII."""
    return SAMPLE_MARKDOWN


@pytest.fixture
def sample_markdown_with_pii():
    """Return sample markdown with known PII entities."""
    return SAMPLE_MARKDOWN_WITH_PII


@pytest.fixture
def temp_directory(tmp_path):
    """Create a temporary directory for file operations."""
    return tmp_path


@pytest.fixture
def mock_vault_data():
    """Return sample vault data structure."""
    return SAMPLE_VAULT_DATA.copy()


@pytest.fixture
def mock_extractor():
    """Create a mocked document extractor."""
    from extractors.base import ExtractionResult
    
    extractor = Mock()
    extractor.name = "MockExtractor"
    extractor.is_available.return_value = True
    extractor.extract = AsyncMock(return_value=ExtractionResult(
        markdown_content=SAMPLE_MARKDOWN,
        page_count=1,
        extraction_method="mock",
        processing_time=0.1,
        metadata={"mock": True}
    ))
    return extractor


@pytest.fixture
def mock_llm_guard():
    """Create a mocked LLM-Guard scanner."""
    scanner = Mock()
    vault = Mock()
    
    # Mock vault.get() to return list of (placeholder, original) tuples
    vault.get.return_value = [
        ("[REDACTED_PERSON_1]", "John Smith"),
        ("[REDACTED_PERSON_2]", "Jane Doe"),
        ("[REDACTED_EMAIL_ADDRESS_1]", "john.smith@example.com"),
        ("[REDACTED_PHONE_NUMBER_1]", "+1-555-123-4567"),
        ("[REDACTED_US_SSN_1]", "123-45-6789"),
        ("[REDACTED_ORGANIZATION_1]", "Acme Corporation"),
        ("[REDACTED_ORGANIZATION_2]", "Tech Solutions Inc."),
        ("[REDACTED_LOCATION_1]", "New York, NY 10001"),
        ("[REDACTED_LOCATION_2]", "San Francisco, CA 94102"),
        ("[REDACTED_IP_ADDRESS_1]", "192.168.1.100"),
        ("[REDACTED_CREDIT_CARD_1]", "4111-1111-1111-1111"),
        ("[REDACTED_URL_1]", "https://johnsmith.com"),
        ("[REDACTED_DATE_TIME_1]", "1985-03-15"),
        ("[REDACTED_DATE_TIME_2]", "2024-01-15")
    ]
    
    # Mock scan result with numbered placeholders
    scanner.scan.return_value = (
        SAMPLE_MARKDOWN_WITH_PII.replace("John Smith", "[REDACTED_PERSON_1]")
                                .replace("john.smith@example.com", "[REDACTED_EMAIL_ADDRESS_1]")
                                .replace("+1-555-123-4567", "[REDACTED_PHONE_NUMBER_1]")
                                .replace("123-45-6789", "[REDACTED_US_SSN_1]"),
        False,  # is_valid (False means PII was detected)
        0.95    # risk_score
    )
    
    return scanner, vault


@pytest.fixture
async def mock_context():
    """Create a mocked FastMCP context with all required methods."""
    context = Mock()
    # Progress reporting
    context.report_progress = Mock()  # Note: not async in FastMCP
    # Logging methods (all async)
    context.info = AsyncMock()
    context.debug = AsyncMock()
    context.warning = AsyncMock()
    context.error = AsyncMock()
    # State management
    context.set_state = Mock()
    context.get_state = Mock()
    return context


@pytest.fixture
def mock_faker():
    """Create a mocked Faker instance with deterministic outputs."""
    faker = Mock()
    faker.name.return_value = "Robert Johnson"
    faker.email.return_value = "robert.johnson@example.com"
    faker.phone_number.return_value = "+1-555-987-6543"
    faker.ssn.return_value = "987-65-4321"
    faker.company.return_value = "Global Industries"
    faker.city.return_value = "Chicago"
    faker.ipv4.return_value = "10.0.0.1"
    faker.credit_card_number.return_value = "4222-2222-2222-2222"
    faker.url.return_value = "https://example.com"
    faker.date_time.return_value = datetime(2023, 6, 15)
    faker.bban.return_value = "9876543210"
    faker.sha256.return_value = "0x" + "a" * 64
    faker.bothify.side_effect = lambda text: text.replace('#', '9').replace('?', 'X')
    return faker


@pytest.fixture
def mock_tiktoken():
    """Create a mocked tiktoken encoder."""
    encoder = Mock()
    # Simple token counting: ~4 chars per token
    encoder.encode.side_effect = lambda text: ["token"] * (len(text) // 4)
    return encoder


@pytest.fixture
def sample_pdf_path(temp_directory):
    """Create a path for a sample PDF file."""
    pdf_path = temp_directory / "sample.pdf"
    # Create a minimal PDF-like file (just for path testing)
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")
    return pdf_path


@pytest.fixture
def sample_files(temp_directory, sample_markdown, sample_markdown_with_pii):
    """Create sample files in temporary directory."""
    # Create markdown files
    md_file = temp_directory / "sample.md"
    md_file.write_text(sample_markdown)
    
    md_with_pii = temp_directory / "sample_with_pii.md"
    md_with_pii.write_text(sample_markdown_with_pii)
    
    # Create a text file
    txt_file = temp_directory / "sample.txt"
    txt_file.write_text("This is a plain text file.")
    
    # Create a subdirectory with files
    subdir = temp_directory / "subdirectory"
    subdir.mkdir()
    sub_file = subdir / "nested.md"
    sub_file.write_text("# Nested Document\n\nContent in subdirectory.")
    
    return {
        "md": str(md_file),
        "md_with_pii": str(md_with_pii),
        "txt": str(txt_file),
        "nested": str(sub_file),
        "directory": str(temp_directory)
    }


@pytest.fixture
def mock_extractor_registry(mock_extractor):
    """Create a mocked extractor registry."""
    registry = Mock()
    registry.auto_select.return_value = mock_extractor
    registry.get.return_value = mock_extractor
    registry.list.return_value = ["mock"]
    return registry


@pytest.fixture
def mock_processing_result():
    """Create a sample ProcessingResult object."""
    from server import ProcessingResult
    return ProcessingResult(
        success=True,
        output_paths=["/tmp/output.md"],
        statistics={"files_processed": 1},
        message="Success",
        vault_path="/tmp/vault.json"
    )


# Configure asyncio for all tests
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Test data generators
@pytest.fixture
def pii_entity_samples():
    """Generate samples for each PII entity type."""
    return {
        "EMAIL_ADDRESS": ["test@example.com", "user@domain.org"],
        "PHONE_NUMBER": ["+1-555-0123", "(555) 456-7890"],
        "CREDIT_CARD": ["4111111111111111", "5500-0000-0000-0004"],
        "US_SSN": ["123-45-6789", "987654321"],
        "PASSPORT": ["US12345678", "GB987654321"],
        "US_DRIVER_LICENSE": ["DL-12345678", "A123-456-789"],
        "IP_ADDRESS": ["192.168.1.1", "10.0.0.1"],
        "PERSON": ["Alice Johnson", "Bob Smith"],
        "LOCATION": ["New York", "123 Main St"],
        "ORGANIZATION": ["Acme Corp", "Tech Solutions Inc"],
        "DATE_TIME": ["2024-01-15", "January 15, 2024"],
        "URL": ["https://example.com", "http://test.org"],
        "US_BANK_NUMBER": ["123456789", "987654321"],
        "CRYPTO": ["0x742d35Cc6634C0532925a3b844Bc9e7595f5b41a", "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"],
        "MEDICAL_LICENSE": ["MD-1234567", "RN-9876543"]
    }


@pytest.fixture
def long_document():
    """Generate a long document for segmentation testing."""
    sections = []
    for i in range(1, 11):
        sections.append(f"""# Chapter {i}

## Introduction to Chapter {i}

This is the introduction to chapter {i}. """ + "Lorem ipsum " * 500 + """

### Section {i}.1

Details for section {i}.1. """ + "Dolor sit amet " * 300 + """

### Section {i}.2

Details for section {i}.2. """ + "Consectetur adipiscing " * 300)
    
    return "\n\n".join(sections)