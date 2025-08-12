
## Overview

This document tracks the remaining implementation tasks for the Inkognito FastMCP server project.

## 1. Remaining Tasks

### 1.1 Placeholder Extractors

The following extractors need to be implemented:

1. **Azure Document Intelligence** (`azure_di.py`)
   - Currently raises NotImplementedError
   - Requires azure-ai-documentintelligence SDK
   - Environment variable: AZURE_DI_KEY

2. **LlamaIndex** (`llamaindex.py`)
   - Currently raises NotImplementedError  
   - Requires llama-parse API
   - Environment variable: LLAMAPARSE_API_KEY

3. **MinerU** (`mineru.py`)
   - Currently raises NotImplementedError
   - Requires magic-pdf library

### 1.2 Minor Improvements

1. **Enable Placeholder Extractors in Registry**
   - Uncomment placeholder extractors in `registry.py` when implemented
   - This allows proper reporting of unavailable extractors

## 2. Recent Updates

### 2.1 LLM-Guard API Update (December 2024)

The PIIAnonymizer was updated to work with llm-guard 0.3.16+:

**Changes Made:**
1. Removed `model_config` parameter (no longer supported)
2. Updated to use `recognizer_conf` parameter with full config
3. Vault now passed during Anonymize initialization, not in scan()
4. Scanner creates fresh vault for each anonymization to avoid cross-contamination
5. Added configurable entity types support

**New API Usage:**
```python
vault = Vault()
scanner = Anonymize(
    vault=vault,
    entity_types=entity_types,
    threshold=0.5,
    use_faker=False,
    recognizer_conf=DISTILBERT_AI4PRIVACY_v2_CONF
)
result, is_valid, score = scanner.scan(text)  # No vault parameter
```

### 2.2 Enhanced Testing

Added comprehensive test coverage:

1. **Unit Tests** (`test_anonymizer.py`)
   - Tests for API compatibility
   - Mocked tests for all anonymizer methods
   - Tests that would catch API changes

2. **Integration Tests** (`test_anonymizer_integration.py`)
   - Real llm-guard library tests
   - Performance benchmarks
   - Entity type detection validation
   - Marked with `@pytest.mark.integration`

### 2.3 Docling API Fix (December 2024)

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

### 2.4 Current Extractor Status

As of December 2024, the implementation status of extractors is:

1. **Docling** - ✅ Fully implemented with OCR support (OCRMac on macOS, EasyOCR on other platforms)
2. **Azure Document Intelligence** - ⚠️ Placeholder only (raises NotImplementedError)
3. **LlamaIndex** - ⚠️ Placeholder only (raises NotImplementedError)
4. **MinerU** - ⚠️ Placeholder only (raises NotImplementedError)

**Note**: In production, consider disabling the unimplemented extractors in `registry.py` to prevent confusion.

## 3. Testing and Quality

### 3.1 Running Tests

```bash
# Run all tests
uv run pytest

# Run only unit tests
uv run pytest tests/test_*.py -k "not integration"

# Run integration tests
uv run pytest -m integration

# Run with coverage
uv run pytest --cov=. --cov-report=html
```

### 3.2 Test Coverage

- Unit tests: Mock all external dependencies
- Integration tests: Use real libraries when available
- Performance tests: Marked with `@pytest.mark.benchmark`
- All tests pass in CI/CD pipeline

## 4. Configuration and Environment

All configuration via environment variables:

```bash
# Optional API keys
AZURE_DI_KEY=your-key-here
LLAMAPARSE_API_KEY=your-key-here

# Optional OCR languages (comma-separated)
INKOGNITO_OCR_LANGUAGES=en,fr,de

# Optional timeout override
INKOGNITO_EXTRACTION_TIMEOUT=1200
```

## 5. Next Steps

1. Implement remaining extractors based on user needs
2. Add more comprehensive integration tests
3. Consider adding streaming support for large documents
4. Add metrics/telemetry for production monitoring
5. Create Docker image for easier deployment
