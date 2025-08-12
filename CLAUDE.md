# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Inkognito is a FastMCP server for privacy-preserving document processing. It provides PDF-to-markdown conversion, intelligent PII anonymization with reversible vaults, and document segmentation through FastMCP's tool interface.

Keep code clean, clear, and uncomplicated. Follow FastMCP 2.11+ best practices and idioms. Avoid unecessary complexity. Make clean, breaking changes without regard to backward compatibility.

Handle depencies with "uv add" and "uv remove". Do not edit pyproject.toml directly to add or remove dependencies.

## Key Architecture Components

### FastMCP Server Structure

- **Entry Point**: `sample_code/server.py` - Contains the FastMCP server sample code to build on
- **Server Pattern**: Uses `server = FastMCP("inkognito")` with `@server.tool()` decorators
- **Context Handling**: FastMCP automatically injects context - use `server.get_context()` when needed
- **Progress Reporting**: Use `await report_progress(message, progress)` for streaming updates
- **Transport**: STDIO only - no HTTP/SSE support

### Core Components

1. **Anonymizer** (`src/anonymizer.py`)

   - Universal PII detection using LLM-Guard with 15 default entity types
   - No configuration needed - comprehensive defaults only
   - Consistent faker replacements across documents
   - Vault-based reversibility

2. **Extractors** (`src/extractors/`)

   - Base interface in `base.py` - all extractors must implement this
   - Registry pattern in `__init__.py` for auto-discovery
   - Priority order: Azure DI → LlamaIndex → MinerU → Docling
   - Import path: `sample_code.extractors` (not `inkognito.extractors`)

3. **Vault System** (`src/vault.py`)

   - v2.0 format with [replacement, original] mappings
   - Stores date offset for consistent date shifting
   - Enables complete PII restoration

4. **Segmenter** (`src/segmenter.py`)
   - Two modes: large document chunks (10k-30k tokens) and prompt splitting
   - Uses tiktoken for accurate token counting
   - Preserves heading context across segments

## Development Commands

```bash
# Run the FastMCP server (from project root)
uv run inkognito.server

# Test with FastMCP CLI (preferred)
fastmcp run inkognito
```

## Important Design Decisions

1. **No Custom Patterns**: The project uses universal PII detection only. Do not add domain-specific patterns or `pattern_sets` parameters.

2. **FastMCP Context**: Never pass `context` as a parameter to tools - FastMCP handles this automatically.

3. **Progress Reporting**: Always report progress for long operations but never include file contents in messages.

4. **Error Handling**: Use `InkognitoError` base class and specific subclasses like `ExtractionError` and `AnonymizationError`.

5. **Configuration**: All config via environment variables only:
   - `AZURE_DI_KEY` - For Azure Document Intelligence
   - `LLAMAPARSE_API_KEY` - For LlamaIndex extraction

## Testing New Extractors

When adding a new extractor:

1. Inherit from `BaseExtractor` in `extractors/base.py`
2. Implement all abstract methods
3. Register in `extractors/__init__.py` auto-registration list
4. Add timeout policy to `ExtractorRegistry._timeout_policies`

## Common Issues

- Progress reporting requires FastMCP context - use `server.get_context()`
- Vault format requires a specific structure - don't modify serialization
- Entity types must match LLM-Guard's expected values (e.g., "EMAIL_ADDRESS", not "email")
