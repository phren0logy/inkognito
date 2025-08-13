# Inkognito Design Document

## Overview

Inkognito is a privacy-preserving document processing FastMCP server. It provides PDF-to-markdown conversion with multiple backends, intelligent PII anonymization, and document segmentation - all through FastMCP's modern tool interface.

## Core Architecture

```
┌─────────────────────────────────────────────────┐
│            MCP Client (Claude/Any)               │
└─────────────────────────────────────────────────┘
                          │
           FastMCP Protocol (STDIO)
                          │
┌─────────────────────────────────────────────────┐
│            Inkognito FastMCP Server              │
│  ┌────────────────────────────────────────────┐ │
│  │           5 Core FastMCP Tools              │ │
│  │  - anonymize_documents                      │ │
│  │  - restore_documents                        │ │
│  │  - extract_document                         │ │
│  │  - segment_document                         │ │
│  │  - split_into_prompts                       │ │
│  └────────────────────────────────────────────┘ │
│                                                  │
│  ┌──────────────┐  ┌─────────────────────────┐ │
│  │  Extractors  │  │    Core Components      │ │
│  │              │  │                         │ │
│  │ - Azure DI   │  │ - Anonymizer (LLM-Guard)│ │
│  │ - LlamaIndex │  │ - Vault Manager         │ │
│  │ - Docling    │  │ - Segmenter             │ │
│  │ - MinerU     │  │                         │ │
│  └──────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

## Key Design Principles

1. **Simplicity First**: No job queues, no complex config files, no unnecessary abstractions
2. **Modular Extractors**: Easy to add/remove PDF processors without touching core code
3. **Privacy by Design**: Local processing options, reversible anonymization
4. **Smart Defaults**: Works out of the box, configurable via environment variables
5. **FastMCP Native**: Leverages FastMCP 2.11+ features for streaming, state management, and progress reporting

## Component Design

### 1. Extractor System

**Base Extractor Interface:**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class ExtractionResult:
    """Result from document extraction."""
    markdown_content: str
    metadata: Dict[str, Any]
    page_count: int
    extraction_method: str
    processing_time: float

class BaseExtractor(ABC):
    """Abstract base class for document extractors."""

    @abstractmethod
    async def extract(self, file_path: str, progress_callback=None) -> ExtractionResult:
        """Extract document content to markdown."""
        pass

    @abstractmethod
    def validate(self, file_path: str) -> bool:
        """Check if file can be processed by this extractor."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if extractor is properly configured."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> Dict[str, Any]:
        """Extractor capabilities and features."""
        pass
```

**Registry Pattern:**

```python
class ExtractorRegistry:
    """Simple registry for extractor discovery."""

    def __init__(self):
        self._extractors: Dict[str, BaseExtractor] = {}

    def register(self, name: str, extractor: BaseExtractor):
        self._extractors[name] = extractor

    def get(self, name: str) -> Optional[BaseExtractor]:
        return self._extractors.get(name)

    def list_available(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "display_name": ext.name,
                "available": ext.is_available(),
                "capabilities": ext.capabilities
            }
            for name, ext in self._extractors.items()
        ]
```

### 2. Anonymization Engine

Built on LLM-Guard with consistent replacements and universal PII detection:

```python
class Anonymizer:
    """Handles PII detection and anonymization."""
    
    # Universal PII scanners - comprehensive defaults
    DEFAULT_SCANNERS = [
        "pii_email", "pii_phone", "pii_credit_card", 
        "pii_ssn", "pii_passport", "pii_driver_license",
        "pii_ip_address", "pii_person", "pii_location",
        "pii_organization", "pii_date", "pii_url",
        "pii_bank_account", "pii_crypto", "pii_medical_record"
    ]

    def __init__(self):
        self.scanner = self._create_scanner()
        self.faker = Faker()

    def anonymize_with_vault(
        self,
        text: str,
        existing_mappings: Dict[str, str] = None
    ) -> Tuple[str, Dict[str, int], Dict[str, str]]:
        """
        Anonymize text with consistent replacements.
        Returns: (anonymized_text, statistics, new_mappings)
        """
        # Detect PII with LLM-Guard using universal scanners
        # Replace with consistent fake data
        # Return results and mappings
        # Ensure no PII leaks to the LLM
```

### 3. Document Segmentation

Two distinct strategies for different use cases:

```python
class DocumentSegmenter:
    """Handles document splitting strategies."""

    def segment_large_document(
        self,
        content: str,
        min_tokens: int = 10000,
        max_tokens: int = 30000
    ) -> List[Segment]:
        """Split large documents for processing."""
        # Break at chapter/section boundaries
        # Maintain context across segments

    def split_into_prompts(
        self,
        content: str,
        split_level: str = "h2", # adaptable, usually h1 or h2
        template: Optional[str] = None
    ) -> List[Prompt]:
        """Split structured content into individual prompts."""
        # Break at specified heading level
        # Apply optional template
        # Include parent context and list of sibling-level headers
```

## FastMCP Server Implementation

### Server Initialization

```python
from fastmcp import FastMCP

# Create server instance
server = FastMCP("inkognito")

# Configure with metadata
server.meta(
    description="Privacy-preserving document processing",
    version="1.0.0"
)
```

## FastMCP Tools Implementation

### 1. anonymize_documents

```python
@server.tool()
async def anonymize_documents(
    output_dir: str,
    files: Optional[List[str]] = None,
    directory: Optional[str] = None,
    patterns: List[str] = ["*.pdf", "*.md", "*.txt"],
    recursive: bool = True
) -> ProcessingResult:
    """Anonymize documents with consistent PII replacement."""
    # Find files
    # Extract text (PDF → Markdown if needed)
    # Anonymize with universal PII detection
    # Save results and vault
    # Report progress via FastMCP streaming
```

### 2. extract_document

```python
@server.tool()
async def extract_document(
    file_path: str,
    ctx: Context,
    output_path: Optional[str] = None,
    extraction_method: str = "auto"
) -> ProcessingResult:
    """Convert PDF/DOCX to markdown."""
    # FastMCP injects context via type hints
    
    if extraction_method == "auto":
        # Smart selection with fallback
        methods = ["azure", "llamaindex", "mineru", "docling"]
        for method in methods:
            extractor = registry.get(method)
            if extractor and extractor.is_available():
                try:
                    # Report progress via FastMCP
                    ctx.report_progress(
                        f"Extracting with {extractor.name}...",
                        0.1
                    )

                    # Extract with streaming updates
                    result = await extractor.extract(
                        file_path,
                        progress_callback=lambda p: context.report_progress(
                            f"Processing page {p['current']}/{p['total']}",
                            p['percent']
                        )
                    )
                    return result
                except Exception:
                    continue  # Try next method
```

### 3. segment_document

```python
@server.tool()
async def segment_document(
    file_path: str,
    output_dir: str,
    max_tokens: int = 15000,
    min_tokens: int = 10000
) -> ProcessingResult:
    """Split large documents into LLM-sized chunks."""
    # Read markdown file
    # Apply intelligent segmentation
    # Save numbered segments
    # Create summary report
    # Use FastMCP streaming for progress
```

### 4. split_into_prompts

```python
@server.tool()
async def split_into_prompts(
    file_path: str,
    output_dir: str,
    split_level: str = "h2",
    include_parent_context: bool = True,
    prompt_template: Optional[str] = None
) -> ProcessingResult:
    """Split structured markdown into individual prompts."""
    # Parse markdown structure
    # Split by heading level
    # Apply template if provided
    # Save individual prompt files
```

### 5. restore_documents

```python
@server.tool()
async def restore_documents(
    output_dir: str,
    files: Optional[List[str]] = None,
    directory: Optional[str] = None,
    vault_path: Optional[str] = None
) -> ProcessingResult:
    """Restore original PII using vault."""
    # Load vault
    # Find anonymized files
    # Reverse replacements
    # Save restored files
```

## Configuration

### Environment Variables

Following FastMCP conventions, all configuration via environment variables:

```bash
# Optional API keys for cloud extractors
AZURE_DI_KEY=your-key-here
LLAMAPARSE_API_KEY=your-key-here
```

### Smart Defaults

- **Extraction**: Auto-selects fastest available method
- **Anonymization**: Universal PII detection enabled
- **Segmentation**: 10k-30k tokens for large docs
- **Prompts**: Split at H2 level with parent context

## Progress Reporting

FastMCP 2.11 provides built-in streaming and progress support:

```python
# FastMCP automatically injects context
async def process_with_progress(self):
    """Example of FastMCP progress reporting."""
    context = server.get_context()
    
    # Stream progress updates
    await context.report_progress("Scanning for documents...", 0.1)
    await context.report_progress("Extracting content...", 0.3)
    await context.report_progress("Anonymizing PII...", 0.7)
    await context.report_progress("Saving results...", 0.9)
    await context.report_progress("Complete!", 1.0)
```

Example progress messages:

- "Scanning for documents..." (10%)
- "Extracting document.pdf with Azure DI..." (20%)
- "Processing page 5 of 20..." (45%)
- "Anonymizing content..." (80%)
- "Saving results..." (95%)
- "Complete!" (100%)

## Timeout Management

Per-backend timeout policies:

```python
EXTRACTOR_TIMEOUTS = {
    "azure": {"default": 300, "per_page": 2},
    "llamaindex": {"default": 600, "per_page": 3},
    "docling": {"default": 900, "per_page": 10},
    "mineru": {"default": 1200, "per_page": 7}
}

async def extract_with_timeout(extractor, file_path, timeout=None):
    """Execute extraction with appropriate timeout."""
    if timeout is None:
        # Calculate based on page count and backend
        page_count = estimate_page_count(file_path)
        timeout_config = EXTRACTOR_TIMEOUTS.get(extractor.name)
        timeout = min(
            timeout_config["default"],
            page_count * timeout_config["per_page"]
        )

    return await asyncio.wait_for(
        extractor.extract(file_path),
        timeout=timeout
    )
```

## Error Handling

Simple, informative error messages:

```python
class InkognitoError(Exception):
    """Base exception with user-friendly messages."""
    pass

class ExtractionError(InkognitoError):
    """When document extraction fails."""
    pass

class AnonymizationError(InkognitoError):
    """When PII anonymization fails."""
    pass

# In practice:
try:
    result = await extract_document(file_path)
except ExtractionError as e:
    return ProcessingResult(
        success=False,
        message=f"Failed to extract document: {e}"
    )
```

## Package Structure

Following FastMCP conventions:

```
inkognito/
├── pyproject.toml          # Modern Python packaging
├── LICENSE                 # MIT license
├── README.md               # Project documentation
├── __init__.py
├── __main__.py             # Entry point for python -m
├── server.py               # FastMCP server setup
├── anonymizer.py           # Universal PII detection
├── vault.py                # Mapping storage
├── segmenter.py            # Document splitting
├── exceptions.py           # Custom exception classes
├── extractors/
│   ├── __init__.py
│   ├── base.py             # Base interface
│   ├── registry.py         # Auto-discovery
│   ├── azure_di.py         # Azure Document Intelligence
│   ├── llamaindex.py       # LlamaIndex/LlamaParse
│   ├── docling.py          # Docling (default)
│   └── mineru.py           # MinerU
└── tests/
```

## Installation

Multiple installation methods supported:

```bash
# Via pip
pip install inkognito

# Via uvx (no Python setup needed)
uvx inkognito

# Development
git clone https://github.com/yourusername/inkognito
cd inkognito
pip install -e .
```

## Performance Characteristics

### Extraction Speed

- **Azure DI**: 0.2-1 sec/page (requires API key)
- **LlamaIndex**: 1-2 sec/page (requires API key)
- **MinerU**: 3-7 sec/page (local, GPU accelerated)
- **Docling**: 5-10 sec/page (local, CPU or limited GPU acceration options)

### Anonymization Speed

- ~1000 words/second
- Minimal overhead for consistency checking
- Vault operations are O(1)

### Memory Usage

- Streaming where possible
- ~100MB base + document size
- No accumulation over time

## Security Considerations

1. **Local-First**: All operations can run entirely offline
2. **Path Names Only**: Makes every effort to pass only path names to the LLM, minimizing leakage of PII (but this cannot be guaranteed due to MCP limitations)
3. **No Persistence**: Nothing saved without explicit output paths
4. **Vault Security**: Mappings stored only where user specifies
5. **API Keys**: Never logged or transmitted

## Future Extensibility

### Adding a New Extractor

1. Create new file in `extractors/`
2. Implement `BaseExtractor` interface
3. Register in `__init__.py`
4. Add to auto-selection order if appropriate

## FastMCP Entry Point

The `__main__.py` provides the standard entry point:

```python
# __main__.py
import asyncio
from .server import create_server

def main():
    """Entry point for FastMCP server."""
    server = create_server()
    asyncio.run(server.run())

if __name__ == "__main__":
    main()
```

## Summary

Inkognito leverages FastMCP 2.11 to provide powerful document processing through a modern MCP interface. By focusing on:

- **FastMCP native** implementation with streaming and progress
- **Modular extractors** with smart selection
- **Universal anonymization** without domain-specific complexity
- **Intelligent segmentation** for different use cases
- **Zero configuration** with environment-based setup

It delivers privacy-preserving functionality in a lightweight, standards-compliant FastMCP package.
