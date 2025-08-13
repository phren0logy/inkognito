## Overview

This document tracks the remaining implementation tasks for the Inkognito FastMCP server project.

## 1. Immediate Priority Tasks

### 1.1 Complete MCP Integration Testing (Critical)

The MCP testing infrastructure needs to be completed to ensure the server works correctly with real clients.

**Current Status**: Phase 1 (Basic Infrastructure) ✅ Completed

**Next Steps**:
1. **Phase 2: MCP Client Integration** (In Progress)
   - Create reusable MCP test client
   - Implement server lifecycle fixtures
   - Add helper utilities for common test patterns

2. **Phase 3: Test Migration**
   - Convert high-value integration tests to use MCP
   - Add new end-to-end test scenarios

3. **Phase 4: Advanced Testing**
   - Performance benchmarks through MCP
   - Concurrent request testing
   - Error injection and recovery testing

### 1.2 Tool Prompt Refinements (High Impact)

Enhance tool docstrings to guide LLMs for better user interactions:

1. **Permission Seeking**
   - Update all tool docstrings to encourage LLMs to ask permission before file access
   - Add examples showing proper permission-seeking behavior

2. **Output Directory Prompts**
   - Guide LLMs to ask where to save files if not specified
   - Suggest sensible defaults
   - Confirm overwrites

3. **Implementation**
   - Update `extract_document`, `anonymize_documents`, and `segment_document` docstrings
   - Add prompt templates and examples
   - Test with various LLMs

## 2. Extractor Implementation (User-Driven)

### 2.1 Current Status

1. **Docling** - ✅ Fully implemented with OCR support
2. **Azure Document Intelligence** - ⚠️ Placeholder only
3. **LlamaIndex** - ⚠️ Placeholder only
4. **MinerU** - ⚠️ Placeholder only

### 2.2 Placeholder Extractors

Implement based on user needs:

1. **Azure Document Intelligence** (`azure_di.py`)
   - Requires azure-ai-documentintelligence SDK
   - Environment variable: AZURE_DI_KEY
   - High accuracy for forms and tables

2. **LlamaIndex** (`llamaindex.py`)
   - Requires llama-parse API
   - Environment variable: LLAMAPARSE_API_KEY
   - Good for complex document structures

3. **MinerU** (`mineru.py`)
   - Requires magic-pdf library
   - Open source alternative

## 3. Future Enhancements

### 3.1 GUI Development (Optional)

Consider adding a graphical interface using pywebview:
- Drag-and-drop file processing
- Visual vault management
- Progress indicators
- Configuration UI

### 3.2 Additional Features

1. **Streaming Support** - For large documents
2. **Docker Image** - For easier deployment
3. **Metrics/Telemetry** - Production monitoring
4. **Batch Processing UI** - Queue management

## 4. Testing and Quality

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

## 5. Configuration and Environment

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

## 6. Quick Action Items

1. **Immediate**: Complete MCP test client implementation
2. **This Week**: Update all tool docstrings with LLM guidance
3. **Documentation**: Update README to clarify extractor availability
4. **As Needed**: Implement extractors based on user feedback

## 7. MCP Integration Testing Details

### 7.1 Overview

Testing through the MCP (Model Context Protocol) server ensures our tests accurately reflect real-world usage. Instead of testing functions directly, MCP tests communicate with a running FastMCP server using the protocol, providing better coverage of:

- Protocol serialization/deserialization
- Error handling across process boundaries
- Concurrent request handling
- Real server lifecycle management
- Authentication and transport layers

### 7.2 Test Architecture

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

### 7.3 Implementation Status

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

### 7.4 Test Categories

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

### 7.5 Key Test Scenarios

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

### 7.6 Benefits of MCP Testing

1. **Real-world Accuracy**: Tests reflect actual client usage patterns
2. **Protocol Validation**: Ensures correct serialization/deserialization
3. **Transport Testing**: Validates STDIO, HTTP, and other transports
4. **Error Boundaries**: Tests error handling across process boundaries
5. **Performance Insights**: Measures actual server response times
6. **Concurrency Testing**: Validates multi-client scenarios

### 7.7 Best Practices

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

## 8. Example Enhanced Tool Docstring

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
