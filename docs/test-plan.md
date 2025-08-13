# Inkognito Test Plan

## Overview

This document outlines the comprehensive testing strategy for the Inkognito FastMCP server. The test suite ensures reliability, correctness, and robustness of all components while maintaining fast execution through proper mocking.

## Test Structure

```
tests/
├── __init__.py                 # Test package initialization
├── conftest.py                 # Shared fixtures and configuration
├── test_server.py              # Test FastMCP tools and server functionality
├── test_anonymizer.py          # Test PII detection and anonymization
├── test_vault.py               # Test vault serialization and restoration
├── test_segmenter.py           # Test document segmentation
├── test_exceptions.py          # Test custom exceptions
├── test_fastmcp_client.py      # FastMCP Client integration tests (PRIMARY)
├── extractors/
│   ├── __init__.py
│   ├── test_base.py           # Test base extractor interface
│   ├── test_registry.py       # Test extractor registry
│   └── test_extractors.py     # Test individual extractors
├── fixtures/                   # Test data
│   ├── sample.pdf             # Simple PDF for testing
│   ├── sample.md              # Markdown without PII
│   └── sample_with_pii.md     # Markdown with known PII
└── integration/               # Integration tests
    ├── test_end_to_end.py     # Full workflow tests
    └── test_with_live_server.py # FastMCP live server tests
```

## Test Dependencies

```toml
[project.optional-dependencies]
test = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "pytest-mock>=3.0.0",
]
```

## Testing Strategy

### 1. Unit Tests

#### test_server.py
- **Test find_files function**
  - With explicit file list
  - With directory and patterns
  - With recursive/non-recursive search
  - Error handling for missing files/directories
  - Empty results handling

- **Test FastMCP tools**
  - Mock file I/O operations
  - Mock extractor registry
  - Test progress reporting
  - Test error handling and recovery
  - Validate ProcessingResult outputs

- **Test each tool individually**
  - `anonymize_documents`: Test with various file types, PII detection, vault creation
  - `restore_documents`: Test vault loading, reverse mapping, file restoration
  - `extract_document`: Test PDF extraction with mocked extractors
  - `segment_document`: Test token counting, segment boundaries
  - `split_into_prompts`: Test heading detection, prompt generation

#### test_anonymizer.py
- **Test PIIAnonymizer class**
  - Scanner creation with default entity types
  - Faker value generation for each entity type
  - Consistent replacements (same input → same output)
  - Date offset generation
  - Empty text handling
  - Text with no PII
  - Text with mixed PII types

- **Test anonymize_with_vault**
  - New anonymization (no existing mappings)
  - Anonymization with existing mappings
  - Statistics collection
  - Vault entry processing

- **Mock dependencies**
  - Mock LLM-Guard scanner
  - Mock Faker with deterministic outputs
  - Mock Vault operations

#### test_vault.py
- **Test VaultManager class**
  - Vault serialization (save_vault)
  - Vault deserialization (load_vault)
  - Version compatibility checking
  - Reverse mapping creation
  - Empty vault handling
  - Corrupt vault handling

- **Test vault format**
  - Correct JSON structure
  - Metadata preservation
  - Mapping integrity

#### test_segmenter.py
- **Test DocumentSegmenter class**
  - Large document segmentation
  - Token counting accuracy
  - Heading detection
  - Context preservation
  - Boundary detection

- **Test segment_large_document**
  - Min/max token enforcement
  - Heading break preferences
  - Edge cases (no headings, very small/large documents)
  - Code block handling
  - Table preservation

- **Test split_into_prompts**
  - Heading level detection
  - Parent context inclusion
  - Prompt template application
  - Empty section handling

- **Mock tiktoken for consistent token counts**

#### test_exceptions.py
- **Test exception hierarchy**
  - InkognitoError base class
  - ExtractionError
  - AnonymizationError
  - VaultError
  - SegmentationError
  - Error message propagation

### 2. Extractor Tests

#### test_base.py
- **Test BaseExtractor interface**
  - Abstract method enforcement
  - ExtractionResult dataclass
  - is_available method
  - extract method signature

#### test_registry.py
- **Test ExtractorRegistry**
  - Auto-registration mechanism
  - Priority ordering
  - Timeout policies
  - Auto-selection logic
  - get/list methods

- **Mock all external dependencies**
  - Environment variables
  - Import availability
  - API responses

#### test_extractors.py
- **Test each extractor implementation**
  - Mock external API calls
  - Test error handling
  - Test timeout behavior
  - Test extraction result format
  - Test progress reporting

### 3. Integration Tests

#### test_fastmcp_client.py (PRIMARY TESTING APPROACH)
- **Test using FastMCP's native Client class**
  - Direct in-memory server connection with `Client(server)`
  - No subprocess management needed
  - Tests all tools through actual MCP protocol
  - Verifies complete workflows: PDF → Extract → Anonymize → Restore
  - Tests error handling, batch processing, and segmentation
  - Access results via `result.data` (the actual ProcessingResult object)

#### test_end_to_end.py
- **Test complete workflows**
  - PDF → Anonymize → Restore cycle
  - Extract → Segment → Split workflow
  - Error propagation through pipeline
  - Large file handling

#### test_with_live_server.py
- **Test FastMCP server integration**
  - Tool registration
  - Context injection via type hints
  - Progress reporting through context
  - Error handling with context
  - Verify all tools accept `ctx: Context` parameter

## Test Fixtures (conftest.py)

```python
# Key fixtures to implement

# PRIMARY: FastMCP Client fixture
@pytest.fixture
async def client():
    """Create a FastMCP client connected to the server."""
    from fastmcp import Client
    from server import server
    async with Client(server) as client:
        yield client

@pytest.fixture
def sample_markdown():
    """Markdown content without PII."""

@pytest.fixture
def sample_markdown_with_pii():
    """Markdown with known PII entities."""

@pytest.fixture
def mock_extractor():
    """Mocked extractor for testing."""

@pytest.fixture
def mock_llm_guard():
    """Mocked LLM-Guard scanner."""

@pytest.fixture
def temp_directory(tmp_path):
    """Temporary directory for file operations."""

@pytest.fixture
def mock_vault_data():
    """Sample vault data structure."""

@pytest.fixture
async def mock_context():
    """Mocked FastMCP context with report_progress."""
```

## Test Data Strategy

### Sample Files
1. **sample.pdf** - Simple single-page PDF with text
2. **sample.md** - Clean markdown without PII
3. **sample_with_pii.md** - Markdown with all PII types:
   - Email addresses
   - Phone numbers
   - Names
   - Organizations
   - Dates
   - Credit cards
   - SSNs
   - etc.

### Generated Test Data
- Use factories for creating test documents
- Parameterized tests for edge cases
- Property-based testing for anonymization consistency

## Mocking Strategy

### External Dependencies to Mock
1. **LLM-Guard**
   - Anonymize scanner
   - Vault operations
   - PII detection results

2. **Faker**
   - Deterministic outputs for testing
   - Consistent replacements

3. **Tiktoken**
   - Token counting
   - Encoding/decoding

4. **File I/O**
   - aiofiles operations
   - Path operations

5. **External APIs**
   - Azure Document Intelligence
   - LlamaIndex/LlamaParse
   - HTTP requests

6. **FastMCP Context**
   - Context methods: info, debug, warning, error
   - report_progress(current, total, message)
   - State management methods

## FastMCP Context Testing

### Context Injection Tests
- **Test proper context parameter handling**
  - Verify all tools have `ctx: Context` parameter
  - Test that context is properly injected by FastMCP
  - Ensure context methods are callable
  - Test async context methods (info, debug, etc.)

### Progress Reporting Tests
- **Test progress reporting through context**
  - Verify `ctx.report_progress(current, total, message)` works
  - Test progress values are properly formatted
  - Test progress messages are logged
  - Test concurrent progress reporting

### Context Method Tests
- **Test all context logging methods**
  - `await ctx.info(message)`
  - `await ctx.debug(message)`
  - `await ctx.warning(message)`
  - `await ctx.error(message)`
  - Test message formatting and output

## Real Tool Testing

### Minimal Mocking Strategy
- **Test actual tool execution**
  - Only mock external services (APIs, cloud services)
  - Use real file I/O with temp directories
  - Test with actual FastMCP context
  - Verify real output files are created

### Tool Integration Tests
- **Test each tool with real inputs**
  - `anonymize_documents`: Test with real markdown/PDF files
  - `restore_documents`: Test with real vault files
  - `extract_document`: Test with sample PDFs (mock only API calls)
  - `segment_document`: Test with real markdown, verify segments
  - `split_into_prompts`: Test with structured markdown

### End-to-End Tool Tests
- **Test complete workflows without mocks**
  - Create temp files → anonymize → verify vault → restore → compare
  - Extract PDF → segment → verify all segments valid
  - Test error conditions with real file operations
  - Verify all progress reporting works end-to-end

### Test File: test_tools_with_context.py
```python
# Example structure for real tool tests
@pytest.mark.asyncio
async def test_anonymize_with_real_context(temp_directory):
    """Test anonymize_documents with minimal mocking."""
    # Create real test files
    # Create mock context with real methods
    # Call tool with context
    # Verify real outputs
```

## Test Execution

### Running Tests
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=. --cov-report=html

# Run FastMCP Client integration tests (RECOMMENDED)
uv run pytest tests/test_fastmcp_client.py -v

# Run specific test
uv run pytest tests/test_fastmcp_client.py::TestFastMCPClient::test_anonymize_document -xvs

# Run with verbose output
uv run pytest -v

# Run only unit tests (exclude integration)
uv run pytest tests/ --ignore=tests/integration/
```

### FastMCP Client Testing (Primary Approach)

The recommended way to test FastMCP servers is using the native `Client` class:

```python
from fastmcp import Client
from server import server
import pytest

@pytest.mark.asyncio
async def test_tool_workflow():
    async with Client(server) as client:
        # Call tools through the client
        result = await client.call_tool(
            "anonymize_documents",
            {
                "output_dir": "test_output",
                "files": ["test.md"]
            }
        )
        # Access the ProcessingResult object directly
        assert result.data.success is True
        assert len(result.data.output_paths) > 0
```

**Important Notes:**
- `result.data` is the actual ProcessingResult object, not a dictionary
- No subprocess management needed - FastMCP handles everything in-memory
- All tests should be async and use `pytest.mark.asyncio`
- This approach tests the actual MCP protocol implementation

### Coverage Goals
- Overall coverage: >80%
- Critical paths: 100%
- Error handling: 100%
- External API mocking: 100%

## Performance Testing

### Benchmarks
- Document processing speed
- Memory usage for large files
- Concurrent request handling
- Token counting accuracy

### Load Testing
- Multiple simultaneous anonymizations
- Large document handling (>100MB)
- Many small files processing

## CI/CD Integration

### GitHub Actions Workflow
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install uv
          uv pip install -e ".[test]"
      - name: Run tests
        run: uv run pytest --cov
```

## Test Maintenance

### Best Practices
1. Keep tests independent and isolated
2. Use descriptive test names
3. One assertion per test when possible
4. Mock at the boundary (external services)
5. Test behavior, not implementation
6. Regular fixture cleanup
7. Avoid testing FastMCP framework itself
8. **Use FastMCP's Client class for integration tests - no custom MCP implementations**
9. **Remember that `result.data` returns the actual object, not a dictionary**
10. **All FastMCP client tests should be async**

### Test Organization
- Group related tests in classes
- Use clear naming: `test_<function>_<scenario>_<expected_result>`
- Keep test files focused and manageable
- Document complex test setups

## Future Considerations

### Additional Testing Areas
1. **Security Testing**
   - Injection attacks
   - Path traversal
   - Malformed input handling

2. **Compatibility Testing**
   - Different Python versions
   - Various file encodings
   - Platform-specific paths

3. **Stress Testing**
   - Memory leaks
   - Resource cleanup
   - Concurrent processing limits

4. **Regression Testing**
   - Vault format compatibility
   - API compatibility
   - Output format stability