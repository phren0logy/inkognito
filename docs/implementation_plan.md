
## Overview

This document outlines the implementation plan for converting the Inkognito project from sample code to a fully functional FastMCP server following FastMCP 2.11+ conventions.

## 1. Package Structure

Create the following directory structure:

```
inkognito/
├── pyproject.toml           # FastMCP-compatible packaging
├── src/
│   └── inkognito/
│       ├── __init__.py
│       ├── __main__.py      # FastMCP entry point
│       ├── server.py        # Main FastMCP server with tools
│       ├── anonymizer.py    # PII detection/anonymization
│       ├── vault.py         # Vault management
│       ├── segmenter.py     # Document segmentation
│       └── extractors/
│           ├── __init__.py  # Registry and auto-discovery
│           ├── base.py      # BaseExtractor interface
│           ├── azure_di.py
│           ├── llamaindex.py
│           ├── docling.py
│           └── mineru.py
└── tests/
```

## 2. Core Implementation Requirements

### 2.1 Server Initialization Pattern

The FastMCP server should follow these patterns:

```python
from fastmcp import FastMCP

# Initialize server with lowercase name
server = FastMCP("inkognito")

# Add metadata
server.meta(
    description="Privacy-preserving document processing",
    version="0.1.0"
)

# All tools use @server.tool() decorator
@server.tool()
async def tool_name(...):
    pass
```

### 2.2 Context and Progress Reporting

FastMCP 2.11+ handles context injection automatically. Tools should NOT have context parameters.

```python
# Progress reporting helper
async def report_progress(message: str, progress: float = None):
    """Report progress via FastMCP streaming."""
    context = server.get_context()
    if context and hasattr(context, 'report_progress'):
        await context.report_progress(message, progress)
```

### 2.3 Tool Function Signatures

Remove all `context: Optional[Any] = None` parameters from tool functions:

```python
# Wrong - old pattern
@server.tool()
async def anonymize_documents(
    output_dir: str,
    context: Optional[Any] = None  # REMOVE THIS
) -> ProcessingResult:
    pass

# Correct - FastMCP pattern
@server.tool()
async def anonymize_documents(
    output_dir: str
) -> ProcessingResult:
    pass
```

## 3. Component Implementation

### 3.1 Main Server (server.py)

Implement the five core tools:

1. **anonymize_documents**

   - Find files by pattern or directory
   - Extract text (PDF → Markdown if needed)
   - Use universal PII detection (no custom patterns)
   - Save anonymized files and vault
   - Report progress throughout

2. **restore_documents**

   - Load vault file
   - Find anonymized documents
   - Reverse all replacements
   - Save restored files

3. **extract_document**

   - Auto-select best extractor
   - Convert PDF/DOCX to markdown
   - Report extraction progress
   - Handle timeouts appropriately

4. **segment_document**

   - Read markdown files
   - Split into 10k-30k token chunks
   - Preserve heading context
   - Create segment report

5. **split_into_prompts**
   - Parse markdown structure
   - Split by heading level (configurable)
   - Include parent context
   - Apply optional templates

### 3.2 Anonymizer (anonymizer.py)

Implement universal PII detection:

```python
# Universal PII types - no configuration needed
DEFAULT_ENTITY_TYPES = [
    "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD",
    "US_SSN", "PASSPORT", "US_DRIVER_LICENSE",
    "IP_ADDRESS", "PERSON", "LOCATION",
    "ORGANIZATION", "DATE_TIME", "URL",
    "US_BANK_NUMBER", "CRYPTO", "MEDICAL_LICENSE"
]
```

Key requirements:

- Use LLM-Guard with DISTILBERT_AI4PRIVACY_v2_CONF
- Consistent faker replacements across documents
- No pattern registry or custom patterns
- Generate appropriate faker values for each entity type

### 3.3 Extractors

#### Base Interface (extractors/base.py)

```python
@dataclass
class ExtractionResult:
    markdown_content: str
    metadata: Dict[str, Any]
    page_count: int
    extraction_method: str
    processing_time: float

class BaseExtractor(ABC):
    @abstractmethod
    async def extract(self, file_path: str, progress_callback=None) -> ExtractionResult:
        pass

    @abstractmethod
    def validate(self, file_path: str) -> bool:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass
```

#### Registry (extractors/**init**.py)

- Auto-discovery of available extractors
- Priority order: Azure DI → LlamaIndex → MinerU → Docling
- Timeout policies per extractor
- Import from `inkognito.extractors`, not `sample_code.extractors`

### 3.4 Vault Manager (vault.py)

Implement v2.0 vault format:

```python
{
    "version": "2.0",
    "date_offset": -184,
    "mappings": {
        "John Smith": "Robert Johnson",
        "john.smith@example.com": "rjohnson@example.com",
        "Acme Corp": "TechCo Industries"
    },
    "statistics": {
        "files_processed": 5,
        "total_replacements": 145
    },
    "created_at": "2024-01-15T10:30:00Z"
}
```

### 3.5 Document Segmenter (segmenter.py)

Two segmentation modes:

1. **Large Document Chunks**

   - 10k-30k tokens per segment
   - Break at chapter/section boundaries
   - Preserve heading context

2. **Prompt Splitting**
   - Split by heading level (h1, h2, h3)
   - Include parent context
   - Optional template application

## 4. Dependencies and Configuration

### 4.1 Update pyproject.toml

```toml
[project]
name = "inkognito"
version = "0.1.0"
requires-python = ">=3.9"
dependencies = [
    "fastmcp>=2.11.0",
    "llm-guard>=0.3.0",
    "faker>=20.0.0",
    "tiktoken>=0.5.0",
    "aiofiles>=23.0.0",
    "python-magic>=0.4.0",
]

[project.optional-dependencies]
azure = ["azure-ai-documentintelligence>=1.0.0b1"]
llamaindex = ["llama-index>=0.9.0", "llama-parse>=0.3.0"]
docling = ["docling>=1.0.0"]
mineru = ["magic-pdf>=0.6.0"]
all = ["inkognito[azure,llamaindex,docling,mineru]"]

[project.scripts]
inkognito = "inkognito.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### 4.2 Entry Point (**main**.py)

```python
import asyncio
import sys
import logging
from .server import server

def main():
    """Entry point for FastMCP server."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        print("\nShutting down Inkognito FastMCP server...")
        sys.exit(0)
    except Exception as e:
        print(f"Error running FastMCP server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

## 5. Error Handling

Implement custom exception hierarchy:

```python
class InkognitoError(Exception):
    """Base exception for Inkognito."""
    pass

class ExtractionError(InkognitoError):
    """Document extraction failed."""
    pass

class AnonymizationError(InkognitoError):
    """PII anonymization failed."""
    pass

class VaultError(InkognitoError):
    """Vault operation failed."""
    pass

class SegmentationError(InkognitoError):
    """Document segmentation failed."""
    pass
```

## 6. Testing Strategy

### 6.1 Unit Tests

- Test each component in isolation
- Mock external dependencies
- Verify FastMCP tool signatures

### 6.2 Integration Tests

- Test full workflows with sample documents
- Verify extractor fallback behavior
- Test vault round-trip (anonymize → restore)

### 6.3 FastMCP Testing

```bash
# Test server startup
fastmcp run inkognito

# Test individual tools
fastmcp test inkognito extract_document
fastmcp test inkognito anonymize_documents
```

## 7. Implementation Steps

### Phase 1: Core Structure

1. Create package directory structure
2. Set up pyproject.toml with dependencies
3. Implement **init**.py and **main**.py
4. Create base server.py with tool stubs

### Phase 2: Core Components

1. Implement anonymizer.py with universal PII detection
2. Create vault.py for mapping storage
3. Implement segmenter.py for document splitting
4. Add error handling throughout

### Phase 3: Extractors

1. Create base.py interface
2. Implement registry with auto-discovery
3. Add Azure DI extractor
4. Add LlamaIndex extractor
5. Add Docling extractor
6. Add MinerU extractor

### Phase 4: Tool Implementation

1. Implement anonymize_documents tool
2. Implement restore_documents tool
3. Implement extract_document tool
4. Implement segment_document tool
5. Implement split_into_prompts tool

### Phase 5: Testing and Polish

1. Add comprehensive logging
2. Implement progress reporting
3. Add unit tests
4. Perform integration testing
5. Update documentation

## 8. Key Differences from Sample Code

1. **No Context Parameters**: FastMCP handles context injection automatically
2. **Consistent Naming**: Use `server` variable throughout, not `mcp`
3. **Progress Reporting**: Use `server.get_context()` internally
4. **Import Paths**: Use `inkognito` package imports, not `sample_code`
5. **No Pattern Registry**: Universal PII detection only
6. **Proper Entry Point**: Follow FastMCP conventions for **main**.py

## 9. Configuration and Environment

All configuration via environment variables:

```bash
# Optional API keys
AZURE_DI_KEY=your-key-here
LLAMAPARSE_API_KEY=your-key-here

# Optional timeout override
INKOGNITO_EXTRACTION_TIMEOUT=1200
```

## 10. Success Criteria

The implementation is complete when:

1. All 5 tools function correctly via FastMCP
2. Progress reporting works throughout operations
3. Universal PII detection covers all entity types
4. Extractors auto-select and fallback properly
5. Vault enables perfect round-trip anonymization
6. Document segmentation preserves context
7. All tests pass
8. Server runs via `fastmcp run inkognito`
9. Can be installed via pip/uvx
10. Works seamlessly with Claude Desktop

## 11. Implementation Updates

### 11.1 Docling API Fix (December 2024)

The Docling extractor was updated to use the correct DocumentConverter API:

**Issue**: DocumentConverter was incorrectly using `pipeline_options` parameter
**Fix**: Changed to use `format_options` with InputFormat mapping:

```python
# Correct API usage
self._converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options)
    }
)
```

### 11.2 Current Extractor Status

As of December 2024, the implementation status of extractors is:

1. **Docling** - ✅ Fully implemented with OCR support (OCRMac on macOS, EasyOCR on other platforms)
2. **Azure Document Intelligence** - ⚠️ Placeholder only (raises NotImplementedError)
3. **LlamaIndex** - ⚠️ Placeholder only (raises NotImplementedError)
4. **MinerU** - ⚠️ Placeholder only (raises NotImplementedError)

**Note**: In production, consider disabling the unimplemented extractors in `registry.py` to prevent confusion.

### 11.3 Testing Considerations

The current test suite mocks the entire Docling library, which prevented detection of the API issue. Future improvements should include:
- Integration tests with real libraries (marked with pytest markers)
- Higher-level mocking to catch API misuse
- Validation of constructor parameters in mocked classes
