# Inkognito

Privacy-first document processing FastMCP server. Extract, anonymize, and segment documents through FastMCP's modern tool interface.

Please note: As an MCP, privacy of file contents cannot be absolutely guaranteed, but it is a central design consideration. While file _contents_ should be low risk (but non-zero) risk for leakage, file _names_ will, unavoidably and by design, be read and written by the MCP. Plan accordingly. Consider using a local model.

## Quick Start

### Installation

```bash
# Install via pip
pip install inkognito

# Or via uvx (no Python setup needed)
uvx inkognito

# Or run directly with FastMCP
fastmcp run inkognito
```

### Configure Claude Desktop

If not already present, you need to make sure you add a filesystem MCP.

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "inkognito": {
      "command": "uvx",
      "args": ["inkognito"],
      "env": {
        // Optional: Add keys when extractors are implemented
        // "AZURE_DI_KEY": "your-key-here",
        // "LLAMAPARSE_API_KEY": "your-key-here"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/Users/you/input-files-or-whatever",
        "/Users/you/output-folder-if-you-want-one"
      ],
      "env": {},
      "transport": "stdio",
      "type": null,
      "cwd": null,
      "timeout": null,
      "description": null,
      "icon": null,
      "authentication": null
    }
  }
}
```

### Basic Usage

In Claude Desktop:

```
"Extract this PDF to markdown"
"Anonymize all documents in my contracts folder"
"Split this large document into chunks for processing"
"Create individual prompts from this documentation"
```

## Features

### 🔒 Privacy-First Anonymization

- Universal PII detection (50+ types)
- Consistent replacements across all documents
- Reversible with secure vault file
- No configuration needed - smart defaults

### 📄 Multiple Extraction Options

- **Available Now**: Docling (default, with OCR support)
- **Planned**: Azure DI, LlamaIndex, MinerU (placeholders only)
- Auto-selects best available option
- Falls back to Docling if no cloud options

### ✂️ Intelligent Segmentation

- **Large documents**: 10k-30k token chunks
- **Prompt generation**: Split by headings
- Preserves context and structure
- Markdown-native processing

## FastMCP Tools

All tools are exposed through FastMCP's modern interface with automatic progress reporting and error handling.

### anonymize_documents

Replace PII with consistent fake data across multiple files.

```python
anonymize_documents(
    directory="/path/to/docs",
    output_dir="/secure/output"
)
```

### extract_document

Convert PDF/DOCX to markdown.

```python
extract_document(
    file_path="/path/to/document.pdf",
    extraction_method="auto"  # auto, docling (others coming soon)
)
```

### segment_document

Split large documents for LLM processing.

```python
segment_document(
    file_path="/path/to/large.md",
    output_dir="/output/segments",
    max_tokens=20000
)
```

### split_into_prompts

Create individual prompts from structured content.

```python
split_into_prompts(
    file_path="/path/to/guide.md",
    output_dir="/output/prompts",
    split_level="h2", #configurable, LLM should be able to read the contents of these files safely
)
```

### restore_documents

Restore original PII using vault.

```python
restore_documents(
    directory="/anonymized/docs",
    output_dir="/restored",
    vault_path="/secure/vault.json"
)
```

## Extractor Status

| Extractor      | Status               | Notes                                                                            |
| -------------- | -------------------- | -------------------------------------------------------------------------------- |
| **Docling**    | ✅ Fully Implemented | Default extractor with OCR support (OCRMac on macOS, EasyOCR on other platforms) |
| **Azure DI**   | ⚠️ Placeholder       | Requires `AZURE_DI_KEY` environment variable when implemented                    |
| **LlamaIndex** | ⚠️ Placeholder       | Requires `LLAMAPARSE_API_KEY` environment variable when implemented              |
| **MinerU**     | ⚠️ Placeholder       | Will require magic-pdf library when implemented                                  |

## Configuration

Following FastMCP conventions, all configuration is via environment variables:

```bash
# Optional API keys for cloud extractors (when implemented)
export AZURE_DI_KEY="your-key-here"
export LLAMAPARSE_API_KEY="your-key-here"

# Optional OCR languages (comma-separated, default: all available)
export INKOGNITO_OCR_LANGUAGES="en,fr,de"
```

## Examples

### Legal Document Processing

```
You: "Anonymize all contracts in the merger folder for review"

Claude: "I'll anonymize those contracts for you...

[Processing 23 files...]

✓ Anonymized 23 contracts
✓ Replaced: 145 company names, 89 person names, 67 case numbers
✓ Vault saved to: /output/vault.json
```

### Research Paper Extraction

```
You: "Extract this 300-page research PDF"

Claude: "I'll extract that PDF to markdown...

[Using Docling for extraction...]

✓ Extracted 300 pages
✓ Preserved: tables, figures, citations
✓ Output size: 487,000 tokens
✓ Saved to: research_paper.md
```

### Documentation to Prompts

```
You: "Split this API documentation into individual prompts"

Claude: "I'll split the documentation by endpoints...

[Splitting by H2 headings...]

✓ Created 47 prompt files
✓ Each prompt includes endpoint context
✓ Ready for training or testing
```

## Performance

| Extractor  | Speed          | Requirements | Status       |
| ---------- | -------------- | ------------ | ------------ |
| Azure DI   | 0.2-1 sec/page | API key      | Planned      |
| LlamaIndex | 1-2 sec/page   | API key      | Planned      |
| MinerU     | 3-7 sec/page   | Local, GPU   | Planned      |
| Docling    | 5-10 sec/page  | Local, CPU   | ✅ Available |

## Privacy & Security

- **Local processing**: No cloud services required
- **No persistence**: Nothing saved without explicit paths
- **Secure vaults**: Encrypted mapping storage
- **API key safety**: Never logged or transmitted

## Development

### Running Locally

```bash
# Clone the repository
git clone https://github.com/phren0logy/inkognito
cd inkognito

# Run with FastMCP CLI
fastmcp dev

# Or run directly in development
uv run python server.py
```

### Testing with FastMCP

```bash
# Install the server configuration
fastmcp install inkognito

# Test a specific tool
fastmcp test inkognito extract_document
```

## Project Structure

```
inkognito/
├── pyproject.toml          # FastMCP-compatible packaging
├── LICENSE                 # MIT license
├── README.md               # This file
├── server.py               # FastMCP server and entry point
├── anonymizer.py           # PII detection and anonymization
├── vault.py                # Vault management for reversibility
├── segmenter.py            # Document segmentation
├── exceptions.py           # Custom exceptions
├── extractors/             # PDF extraction backends
│   ├── __init__.py
│   ├── base.py
│   ├── registry.py
│   ├── docling.py          # ✅ Implemented
│   ├── azure_di.py         # Placeholder
│   ├── llamaindex.py       # Placeholder
│   └── mineru.py           # Placeholder
└── tests/
```

## License

MIT License - see LICENSE file for details.
