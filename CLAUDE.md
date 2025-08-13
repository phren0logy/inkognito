# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Inkognito is a FastMCP server for privacy-preserving document processing. It provides PDF-to-markdown conversion, intelligent PII anonymization with reversible vaults, and document segmentation through FastMCP's tool interface.

Keep code clean, clear, and uncomplicated. Follow FastMCP 2.11+ best practices and idioms. Avoid unecessary complexity. Make clean, breaking changes without regard to backward compatibility.

Handle depencies with "uv add" and "uv remove". Do not edit pyproject.toml directly to add or remove dependencies.

## Key Architecture Components

### FastMCP Server Structure

- **Entry Point**: `server.py` - Contains the FastMCP server
- **Server Pattern**: Uses `server = FastMCP("inkognito")` with `@server.tool()` decorators
- **Context Handling**: FastMCP automatically injects context via type hints - add `ctx: Context` parameter to tools
- **Transport**: STDIO only - no HTTP/SSE support

### Core Components

1. **Anonymizer** (`anonymizer.py`)

   - Universal PII detection using LLM-Guard with 15 default entity types
   - No configuration needed - comprehensive defaults only
   - Consistent faker replacements across documents
   - Vault-based reversibility

2. **Extractors** (`extractors/`)

   - Base interface in `base.py` - all extractors must implement this
   - Registry pattern in `__init__.py` for auto-discovery
   - Priority order: Azure DI → LlamaIndex → MinerU → Docling
   - Import path: `extractors`
   - Docling uses platform-specific OCR:
     - macOS: OCRMac with livetext framework
     - Other platforms: EasyOCR

3. **Vault System** (`vault.py`)

   - v2.0 format with [replacement, original] mappings
   - Stores date offset for consistent date shifting
   - Enables complete PII restoration

4. **Segmenter** (`segmenter.py`)
   - Two modes: large document chunks (10k-30k tokens) and prompt splitting
   - Uses tiktoken for accurate token counting
   - Preserves heading context across segments

## FastMCP Context and Progress Monitoring

FastMCP uses dependency injection to provide context to tools:

- **Context Injection**: Add `ctx: Context` parameter to any tool function to receive context
- **Progress Reporting**: Use `ctx.report_progress(current, total, message)` for progress tracking
- **Logging Methods**:
  - `await ctx.info(message)` - Information messages
  - `await ctx.debug(message)` - Debug messages
  - `await ctx.warning(message)` - Warning messages
  - `await ctx.error(message)` - Error messages
- **Never use**: `server.get_context()` - this doesn't exist in FastMCP

Example tool signature:
```python
@server.tool()
async def my_tool(file_path: str, ctx: Context) -> ProcessingResult:
    await ctx.info("Starting processing...")
    ctx.report_progress(1, 10, "Processing file")
    # ... tool logic
```

## Running the FastMCP Server

### Installation

For development, install the package in editable mode:
```bash
uv pip install -e .
```

### Starting the Server

Following FastMCP best practices, use one of these methods:

1. **FastMCP CLI (recommended)**:
   ```bash
   uv run fastmcp run server.py
   ```

2. **Direct Python execution**:
   ```bash
   uv run python server.py
   ```

3. **With FastMCP dev mode** (includes MCP Inspector):
   ```bash
   uv run fastmcp dev server.py
   ```

Note: The project includes a `[project.scripts]` entry point (`inkognito = "server:main"`) for both local development and PyPI distribution via uvx. This enables `uvx inkognito` usage while maintaining compatibility with direct FastMCP CLI commands.

## Important Design Decisions

1. **No Custom Patterns**: The project uses universal PII detection only. Do not add domain-specific patterns or `pattern_sets` parameters.

2. **FastMCP Context**: FastMCP injects context automatically when you add `ctx: Context` parameter to tool functions.

3. **Progress Reporting**: Always report progress for long operations but never include file contents in messages.

4. **Error Handling**: Use `InkognitoError` base class and specific subclasses like `ExtractionError` and `AnonymizationError`.

5. **Configuration**: All config via environment variables only:
   - `AZURE_DI_KEY` - For Azure Document Intelligence
   - `LLAMAPARSE_API_KEY` - For LlamaIndex extraction
   - `INKOGNITO_OCR_LANGUAGES` - Comma-separated list of OCR languages (e.g., "en,fr,de")

## Testing FastMCP Servers

FastMCP provides a native `Client` class for in-memory testing. **Do not use subprocess or custom MCP protocol implementations.**

### Correct Testing Approach

```python
from fastmcp import Client
from server import server
import pytest

@pytest.fixture
async def client():
    """Create a FastMCP client connected to the server."""
    async with Client(server) as client:
        yield client

async def test_tool(client):
    result = await client.call_tool("tool_name", {"param": "value"})
    # result.data contains the ProcessingResult object
    assert result.data.success is True
```

### Key Testing Patterns

1. **Direct Server Connection**: Pass the server instance directly to `Client(server)`
2. **No Subprocess Management**: FastMCP handles everything in-memory
3. **Access Tool Results**: Use `result.data` to access the returned object (not a dict)
4. **Async Testing**: All tests should be `async` and use `pytest.mark.asyncio`

### Running Tests

```bash
# Run all FastMCP integration tests
uv run pytest tests/test_fastmcp_client.py -v

# Run a specific test
uv run pytest tests/test_fastmcp_client.py::TestFastMCPClient::test_anonymize_document -xvs
```

### Common Testing Mistakes to Avoid

- ❌ Don't spawn server processes with subprocess
- ❌ Don't implement custom MCP protocol handling  
- ❌ Don't use JSON-RPC directly
- ❌ Don't treat `result.data` as a dictionary (it's the actual return object)

## Testing New Extractors

When adding a new extractor:

1. Inherit from `BaseExtractor` in `extractors/base.py`
2. Implement all abstract methods
3. Register in `extractors/__init__.py` auto-registration list
4. Add timeout policy to `ExtractorRegistry._timeout_policies`

## Common Issues

- Progress reporting requires FastMCP context - use the injected `ctx` parameter
- Vault format requires a specific structure - don't modify serialization
- Entity types must match LLM-Guard's expected values (e.g., "EMAIL_ADDRESS", not "email")
- When testing, remember that `result.data` is the actual ProcessingResult object, not a dict
