
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

# Run only unit tests (fast, no server required)
uv run pytest tests/test_*.py -k "not integration and not mcp"

# Run integration tests (uses real libraries)
uv run pytest -m integration

# Run MCP tests (requires running server)
uv run pytest -m mcp

# Run end-to-end tests through MCP
uv run pytest tests/integration/test_with_live_server.py

# Run with coverage
uv run pytest --cov=. --cov-report=html
```

### 3.2 Test Coverage

- **Unit tests**: Mock all external dependencies, direct function calls
- **Integration tests**: Use real libraries when available
- **MCP tests**: Test through running FastMCP server
- **Performance tests**: Marked with `@pytest.mark.benchmark`
- **End-to-end tests**: Complete workflows through MCP protocol
- All tests pass in CI/CD pipeline

### 3.3 MCP Test Infrastructure

#### Test Client Setup

```python
from fastmcp import Client
import pytest

@pytest.fixture
async def mcp_server():
    """Start FastMCP server for testing."""
    # Server lifecycle management
    server_process = await start_server()
    yield server_process
    await stop_server(server_process)

@pytest.fixture
async def mcp_client(mcp_server):
    """Create MCP client connected to test server."""
    client = Client(
        server_params={
            "command": ["python", "server.py"],
            "args": []
        }
    )
    await client.connect()
    yield client
    await client.disconnect()
```

#### Writing MCP Tests

```python
@pytest.mark.mcp
async def test_anonymize_through_mcp(mcp_client, test_documents):
    """Test anonymization using MCP protocol."""
    result = await mcp_client.call_tool(
        "anonymize_documents",
        output_dir="./output",
        files=[str(test_documents["medical_record"])]
    )
    
    assert result["success"] is True
    assert "vault_path" in result
    assert len(result["output_paths"]) == 1
```

#### Test Utilities

- **Fixtures**: Server lifecycle, client setup, test data
- **Markers**: `@pytest.mark.mcp` for MCP-specific tests
- **Helpers**: Response parsing, error checking, file verification
- **Mocks**: Network delays, server errors, concurrent requests

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

1. Complete MCP integration testing infrastructure
2. Refine MCP tool prompts for better user interaction
3. Implement remaining extractors based on user needs
4. Add more comprehensive integration tests through MCP
5. Consider adding GUI using pywebview for local usage
6. Consider adding streaming support for large documents
7. Add metrics/telemetry for production monitoring
8. Create Docker image for easier deployment

## 6. MCP Integration Testing

### 6.1 Overview

Testing through the MCP (Model Context Protocol) server ensures our tests accurately reflect real-world usage. Instead of testing functions directly, MCP tests communicate with a running FastMCP server using the protocol, providing better coverage of:

- Protocol serialization/deserialization
- Error handling across process boundaries
- Concurrent request handling
- Real server lifecycle management
- Authentication and transport layers

### 6.2 Test Architecture

```
┌─────────────┐     MCP Protocol      ┌──────────────┐
│   Test      │ ◄──────────────────► │   FastMCP    │
│   Client    │     (JSON-RPC)        │   Server     │
└─────────────┘                       └──────────────┘
      │                                      │
      │                                      │
      ▼                                      ▼
┌─────────────┐                       ┌──────────────┐
│   Pytest    │                       │  Inkognito   │
│  Fixtures   │                       │    Tools     │
└─────────────┘                       └──────────────┘
```

### 6.3 Implementation Phases

#### Phase 1: Basic Infrastructure (Completed)
- ✅ Created test fixtures and documents
- ✅ Set up basic test structure
- ✅ Verified server can be started reliably

#### Phase 2: MCP Client Integration (In Progress)
- Create reusable MCP test client
- Implement server lifecycle fixtures
- Add helper utilities for common test patterns

#### Phase 3: Test Migration
- Convert high-value integration tests to use MCP
- Maintain unit tests for fast feedback
- Add new end-to-end test scenarios

#### Phase 4: Advanced Testing
- Performance benchmarks through MCP
- Concurrent request testing
- Error injection and recovery testing

### 6.4 Test Categories

1. **Unit Tests** (Direct Function Calls)
   - Fast, isolated tests
   - Mock external dependencies
   - Test business logic directly
   - Run without server

2. **MCP Integration Tests** (Through Protocol)
   - Test complete request/response cycle
   - Verify protocol compliance
   - Test error handling
   - Require running server

3. **End-to-End Tests** (Full Workflows)
   - Test complete user scenarios
   - Multiple tool calls in sequence
   - Verify data persistence (vaults)
   - Performance validation

### 6.5 Key Test Scenarios

1. **PDF Processing Pipeline**
   ```
   extract_document → anonymize_documents → restore_documents
   ```

2. **Batch Processing**
   ```
   Multiple files → Consistent PII replacement → Single vault
   ```

3. **Error Handling**
   ```
   Invalid inputs → Graceful errors → Proper cleanup
   ```

4. **Concurrent Operations**
   ```
   Multiple clients → Parallel requests → Correct isolation
   ```

### 6.6 Benefits of MCP Testing

1. **Real-world Accuracy**: Tests reflect actual client usage patterns
2. **Protocol Validation**: Ensures correct serialization/deserialization
3. **Transport Testing**: Validates STDIO, HTTP, and other transports
4. **Error Boundaries**: Tests error handling across process boundaries
5. **Performance Insights**: Measures actual server response times
6. **Concurrency Testing**: Validates multi-client scenarios

### 6.7 Best Practices

1. **Test Pyramid**
   - Many unit tests (fast, focused)
   - Some integration tests (feature validation)
   - Few end-to-end MCP tests (critical paths)

2. **Test Data Management**
   - Use fixtures for consistent test documents
   - Clean up test outputs after each run
   - Version control test PDFs and markdown files

3. **Server Management**
   - Use session-scoped fixtures for expensive operations
   - Implement proper cleanup in fixtures
   - Handle server crashes gracefully

4. **Debugging MCP Tests**
   - Enable server logging during test runs
   - Capture and display server stderr on failures
   - Use MCP Inspector for interactive debugging

5. **CI/CD Considerations**
   - Ensure test environment has all dependencies
   - Set appropriate timeouts for MCP operations
   - Run MCP tests in isolated environments

## 7. GUI Development (Tentative)

### 7.1 Overview

Consider adding a graphical user interface using [pywebview](https://pywebview.flowrl.com/blog/pywebview6.html) to make Inkognito more accessible to non-technical users. This would provide a local desktop application that communicates with the FastMCP server.

### 7.2 Potential Features

1. **Document Processing**
   - Drag-and-drop interface for files
   - Visual progress indicators
   - Preview of anonymized documents
   - Batch processing queue

2. **Vault Management**
   - Visual vault browser
   - Search and filter capabilities
   - Export/import vault data
   - Statistics dashboard

3. **Configuration**
   - GUI for setting extraction methods
   - Entity type selection
   - Output directory management
   - API key configuration

### 7.3 Architecture Considerations

```
┌─────────────┐     HTTP/IPC      ┌──────────────┐
│  pywebview  │ ◄──────────────► │   FastMCP    │
│     GUI     │                   │   Server     │
└─────────────┘                   └──────────────┘
      │                                  │
      ▼                                  ▼
┌─────────────┐                   ┌──────────────┐
│   Web UI    │                   │  Inkognito   │
│  (HTML/JS)  │                   │    Core      │
└─────────────┘                   └──────────────┘
```

### 7.4 Implementation Notes

- Keep GUI optional - core functionality remains CLI/MCP-based
- Use modern web technologies for the UI (React/Vue/Svelte)
- Implement secure communication between GUI and server
- Consider electron-like packaging for distribution

## 8. MCP Tool Prompt Refinements

### 8.1 User Permission for File Access

Update tool prompts to emphasize that LLMs should:

1. **Ask permission before reading file contents**
   - "May I read the contents of [filename] to proceed with anonymization?"
   - "I need to examine [filename]. Is that okay?"
   - Explain why file access is needed

2. **Confirm sensitive operations**
   - "This will scan [X] files for PII. Continue?"
   - "Anonymization will create new files. Proceed?"

### 8.2 Output Location Prompts

Enhance tools to encourage LLMs to:

1. **Ask for output directory**
   ```
   Current tool: anonymize_documents(output_dir: str, ...)
   
   Prompt enhancement:
   "Where would you like me to save the anonymized documents?"
   "Please specify an output directory for the results:"
   ```

2. **Suggest sensible defaults**
   ```
   "Would you like to save to './anonymized' or specify a different location?"
   "I can save the extracted markdown to './extracted' or another directory of your choice."
   ```

3. **Confirm overwrites**
   ```
   "The directory './output' already exists. Overwrite or choose a new location?"
   ```

### 8.3 Implementation Approach

1. **Update tool docstrings** with clear guidance for LLMs
2. **Add examples** in docstrings showing permission-seeking behavior
3. **Create prompt templates** that LLMs can use
4. **Test with various LLMs** to ensure consistent behavior

### 8.4 Example Enhanced Docstring

```python
@server.tool()
async def anonymize_documents(
    output_dir: str,
    ctx: Context,
    files: Optional[List[str]] = None,
    ...
) -> ProcessingResult:
    """
    Anonymize documents by replacing PII with realistic fake data.
    
    IMPORTANT FOR LLMs:
    - Always ask user permission before reading file contents
    - Always ask where to save output files if not specified
    - Explain what the anonymization process will do
    
    Example interaction:
    User: "Anonymize my medical records"
    LLM: "I can help anonymize your medical records. May I read the files to identify what needs to be anonymized?"
    User: "Yes"
    LLM: "Where would you like me to save the anonymized versions? (default: ./anonymized)"
    User: "./private/anonymized"
    LLM: "I'll anonymize the documents and save them to ./private/anonymized..."
    
    Args:
        output_dir: Directory to save anonymized files (ALWAYS ASK if not provided)
        files: List of files to anonymize (REQUEST PERMISSION before reading)
    """
```
