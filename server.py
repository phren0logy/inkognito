"""Inkognito FastMCP Server - Document anonymization and processing."""

from fastmcp import FastMCP, Context
from typing import List, Optional, Dict, Any
import os
import glob as glob_module
from pathlib import Path
from datetime import datetime
import logging
from dataclasses import dataclass

# Import our modules
from extractors import registry
from anonymizer import PIIAnonymizer
from vault import VaultManager
from segmenter import DocumentSegmenter
from exceptions import InkognitoError, ExtractionError, AnonymizationError, VaultError, SegmentationError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
server = FastMCP("inkognito")


@dataclass
class ProcessingResult:
    """Result from document processing operations."""
    success: bool
    output_paths: List[str]
    statistics: Dict[str, Any]
    message: str
    vault_path: Optional[str] = None




def find_files(
    directory: Optional[str] = None,
    files: Optional[List[str]] = None,
    patterns: List[str] = ["*.pdf", "*.md", "*.txt"],
    recursive: bool = True
) -> List[str]:
    """Find files matching patterns in directory or from explicit file list."""
    if files:
        # Validate all files exist
        found_files = []
        for f in files:
            path = Path(f)
            if path.exists():
                found_files.append(str(path.absolute()))
            else:
                raise FileNotFoundError(f"File not found: {f}")
        return found_files
    
    if directory:
        dir_path = Path(directory)
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        found_files = []
        for pattern in patterns:
            if recursive:
                glob_pattern = str(dir_path / "**" / pattern)
                found_files.extend(glob_module.glob(glob_pattern, recursive=True))
            else:
                glob_pattern = str(dir_path / pattern)
                found_files.extend(glob_module.glob(glob_pattern))
        
        return sorted(list(set(found_files)))
    
    raise ValueError("Either 'files' or 'directory' must be provided")


def ensure_output_dir(output_dir: str) -> Path:
    """Ensure output directory exists and return Path object."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    return out_path


@server.tool()
async def anonymize_documents(
    output_dir: str,
    ctx: Context,
    files: Optional[List[str]] = None,
    directory: Optional[str] = None,
    patterns: List[str] = ["*.pdf", "*.md", "*.txt"],
    recursive: bool = True
) -> ProcessingResult:
    """
    Extract and anonymize documents by replacing PII with realistic fake data.
    
    IMPORTANT FOR LLMs:
    - Always ask user permission before reading any file contents
    - Always ask where to save output files if output_dir not explicitly provided
    - Explain what the anonymization process will do before starting
    - Mention that a vault file will be created for reversibility
    - Note that PDFs will be converted to markdown before anonymization
    
    Example interaction:
    User: "Anonymize my contracts folder"
    LLM: "I can help anonymize your contracts by replacing personal information like names, dates, and addresses with realistic fake data. PDFs will be converted to markdown format. May I read the files to identify what needs to be anonymized?"
    User: "Yes"
    LLM: "Where would you like me to save the anonymized versions? (I'll also create a vault file for future restoration)"
    User: "./private/anonymized"
    LLM: "I'll anonymize the documents and save them to ./private/anonymized..."
    
    This tool processes documents in two steps:
    1. Extracts text from PDFs (converts to markdown) or reads markdown/text files directly
    2. Replaces personally identifiable information (PII) with consistent, realistic fake data
    
    The same entity always gets the same replacement across all documents 
    (e.g., "John Smith" always becomes "Robert Johnson" in every file).
    
    Supported input formats: PDF, Markdown (.md), Text (.txt)
    Output format: Always Markdown (.md) regardless of input
    
    Args:
        output_dir: Directory to save anonymized files and vault (ALWAYS ASK if not provided)
        files: List of specific file paths to anonymize (REQUEST PERMISSION before reading)
        directory: Directory to scan for files (optional, use files OR directory)
        patterns: File patterns to match (default: ["*.pdf", "*.md", "*.txt"])
        recursive: Include subdirectories when scanning (default: true)
    
    Returns:
        ProcessingResult with output paths, statistics, and vault location
    """
    try:
        # Find files to process
        await ctx.info("Scanning for documents...")
        input_files = find_files(directory, files, patterns, recursive)
        
        if not input_files:
            return ProcessingResult(
                success=False,
                output_paths=[],
                statistics={},
                message="No files found matching the specified patterns"
            )
        
        await ctx.info(f"Found {len(input_files)} files to anonymize")
        
        # Prepare output directory
        out_path = ensure_output_dir(output_dir)
        anon_path = out_path / "anonymized"
        anon_path.mkdir(exist_ok=True)
        
        # Initialize anonymizer
        anonymizer = PIIAnonymizer()
        
        # Generate date offset for this session (default 365 days)
        date_offset = anonymizer.generate_date_offset(365)
        
        # Process each file
        total_statistics = {}
        output_paths = []
        vault_mappings = {}
        
        for i, file_path in enumerate(input_files):
            progress = 0.2 + (0.6 * i / len(input_files))
            file_name = Path(file_path).name
            ctx.report_progress(i+1, len(input_files), f"Processing {file_name}")
            
            # Read file content
            content = ""
            file_type = Path(file_path).suffix.lower()
            
            if file_type == ".pdf":
                # Extract PDF to markdown first
                await ctx.info(f"Extracting PDF: {file_name}")
                
                # Use auto-selection to get best available extractor
                extractor = registry.auto_select(file_path)
                if not extractor:
                    logger.warning(f"No extractor available for {file_path}, skipping")
                    continue
                
                result = await extractor.extract(file_path)
                content = result.markdown_content
            else:
                # Read text/markdown files directly
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            
            # Anonymize content
            anonymized_text, statistics, new_mappings = anonymizer.anonymize_with_vault(
                content,
                vault_mappings
            )
            
            # Update vault mappings
            vault_mappings.update(new_mappings)
            
            # Aggregate statistics
            for entity_type, count in statistics.items():
                total_statistics[entity_type] = total_statistics.get(entity_type, 0) + count
            
            # Save anonymized file as markdown
            output_name = Path(file_path).stem + ".md"
            output_file = anon_path / output_name
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(anonymized_text)
            
            output_paths.append(str(output_file))
        
        # Save vault
        await ctx.info("Saving anonymization vault...")
        vault_path = out_path / "vault.json"
        VaultManager.save_vault(vault_path, vault_mappings, date_offset, len(input_files))
        
        # Create summary report
        report_path = out_path / "REPORT.md"
        report = f"""# Anonymization Report

Generated: {datetime.now().isoformat()}

## Summary
- Files processed: {len(input_files)}
- Output directory: {output_dir}
- Vault location: vault.json

## Statistics
"""
        for entity_type, count in sorted(total_statistics.items()):
            report += f"- {entity_type}: {count}\n"
        
        report += f"\n## Consistency\n"
        report += "All occurrences of the same entity received the same replacement across all documents.\n"
        report += "To restore original values, use the restore_documents tool with the vault.json file.\n"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        await ctx.info("Anonymization complete!")
        
        return ProcessingResult(
            success=True,
            output_paths=output_paths,
            statistics=total_statistics,
            message=f"Successfully anonymized {len(input_files)} files",
            vault_path=str(vault_path)
        )
        
    except Exception as e:
        logger.error(f"Anonymization failed: {e}")
        return ProcessingResult(
            success=False,
            output_paths=[],
            statistics={},
            message=f"Anonymization failed: {str(e)}"
        )


@server.tool()
async def restore_documents(
    output_dir: str,
    ctx: Context,
    files: Optional[List[str]] = None,
    directory: Optional[str] = None,
    vault_path: Optional[str] = None,
    patterns: List[str] = ["*.md"],
    recursive: bool = True
) -> ProcessingResult:
    """
    Restore original PII in anonymized documents using vault.
    
    IMPORTANT FOR LLMs:
    - Always ask where to save restored files if output_dir not provided
    - Explain that this will restore the original personal information
    - Mention that a vault file is required for restoration
    - Explain vault auto-detection if user doesn't provide vault_path
    
    Example interaction:
    User: "Restore the anonymized documents"
    LLM: "I can restore the original personal information in the anonymized documents using the vault file. Where would you like me to save the restored versions?"
    User: "./restored"
    LLM: "I'll look for the vault file and restore the documents to ./restored..."
    
    This tool reverses the anonymization process by replacing fake data with
    the original PII values stored in the vault. Only works with documents
    that were anonymized using the anonymize_documents tool.
    
    Vault auto-detection: If vault_path is not provided, the tool searches:
    1. Parent directory of the anonymized files (most common location)
    2. Same directory as the anonymized files
    
    Args:
        output_dir: Directory to save restored files (ALWAYS ASK if not provided)
        files: List of specific anonymized files to restore (optional)
        directory: Directory containing anonymized files (optional)
        vault_path: Path to vault.json (if not provided, searches parent directory first, then current)
        patterns: File patterns to match (default: ["*.md"])
        recursive: Include subdirectories (default: true)
    
    Returns:
        ProcessingResult with restored file paths
    """
    try:
        # Find files to restore
        await ctx.info("Scanning for anonymized documents...")
        input_files = find_files(directory, files, patterns, recursive)
        
        if not input_files:
            return ProcessingResult(
                success=False,
                output_paths=[],
                statistics={},
                message="No anonymized files found"
            )
        
        # Find vault file
        if not vault_path:
            # Auto-detect vault in parent directory
            if directory:
                parent_dir = Path(directory).parent
                possible_vault = parent_dir / "vault.json"
                if possible_vault.exists():
                    vault_path = str(possible_vault)
                else:
                    # Check current directory
                    current_vault = Path(directory) / "vault.json"
                    if current_vault.exists():
                        vault_path = str(current_vault)
        
        if not vault_path or not Path(vault_path).exists():
            return ProcessingResult(
                success=False,
                output_paths=[],
                statistics={},
                message="Vault file not found. Cannot restore without vault.json"
            )
        
        await ctx.info("Loading vault data...")
        
        # Load vault
        date_offset, mappings = VaultManager.load_vault(Path(vault_path))
        
        # Create reverse mappings
        reverse_mappings = VaultManager.create_reverse_mappings(mappings)
        
        # Prepare output directory
        out_path = ensure_output_dir(output_dir)
        restored_path = out_path / "restored"
        restored_path.mkdir(exist_ok=True)
        
        # Process each file
        output_paths = []
        total_replacements = 0
        
        for i, file_path in enumerate(input_files):
            progress = 0.2 + (0.7 * i / len(input_files))
            file_name = Path(file_path).name
            ctx.report_progress(i+1, len(input_files), f"Restoring {file_name}")
            
            # Read anonymized content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Restore original values
            restored_content = content
            replacements_in_file = 0
            
            for faker_value, original_value in reverse_mappings.items():
                if faker_value in restored_content:
                    restored_content = restored_content.replace(faker_value, original_value)
                    replacements_in_file += restored_content.count(original_value)
            
            total_replacements += replacements_in_file
            
            # Save restored file
            output_file = restored_path / file_name
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(restored_content)
            
            output_paths.append(str(output_file))
        
        # Create restoration report
        await ctx.info("Creating restoration report...")
        report_path = out_path / "RESTORATION_REPORT.md"
        report = f"""# Restoration Report

Generated: {datetime.now().isoformat()}

## Summary
- Files restored: {len(input_files)}
- Total replacements: {total_replacements}
- Vault used: {vault_path}
- Output directory: {output_dir}

## Details
All fake values have been replaced with their original PII values.
The restored documents are identical to the pre-anonymization versions.
"""
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        await ctx.info("Restoration complete!")
        
        return ProcessingResult(
            success=True,
            output_paths=output_paths,
            statistics={"files_restored": len(input_files), "total_replacements": total_replacements},
            message=f"Successfully restored {len(input_files)} files"
        )
        
    except Exception as e:
        logger.error(f"Restoration failed: {e}")
        return ProcessingResult(
            success=False,
            output_paths=[],
            statistics={},
            message=f"Restoration failed: {str(e)}"
        )


@server.tool()
async def extract_document(
    file_path: str,
    ctx: Context,
    output_path: Optional[str] = None,
    extraction_method: str = "auto"
) -> ProcessingResult:
    """
    Convert PDF or DOCX document to markdown format.
    
    IMPORTANT FOR LLMs:
    - Always ask permission before processing the document
    - Ask where to save the output if output_path not provided
    - Explain what the extraction process will do
    - Currently only Docling extractor is implemented
    
    Example interaction:
    User: "Extract the PDF to markdown"
    LLM: "I can convert your PDF to markdown format, preserving the structure and formatting. May I process the document?"
    User: "Yes"
    LLM: "Where would you like me to save the markdown file? (default: same location with .md extension)"
    User: "Use the default"
    LLM: "I'll extract the PDF and save it as markdown..."
    
    Extracts text content from documents while preserving structure,
    formatting, tables, and other elements. Uses Docling for local processing
    with OCR support (OCRMac on macOS, EasyOCR on other platforms).
    
    Supported file types: PDF, DOCX
    
    Args:
        file_path: Path to the input document (REQUEST PERMISSION before processing)
        output_path: Path for output markdown file (ASK if not provided, default: same name with .md)
        extraction_method: "auto" (uses Docling) or "docling" (default: "auto")
    
    Returns:
        ProcessingResult with extracted markdown file path
    """
    try:
        # Validate input file
        input_path = Path(file_path)
        if not input_path.exists():
            return ProcessingResult(
                success=False,
                output_paths=[],
                statistics={},
                message=f"Input file not found: {file_path}"
            )
        
        # Determine output path
        if not output_path:
            output_path = str(input_path.with_suffix(".md"))
        
        await ctx.info(f"Extracting {input_path.name}...")
        
        # Select extractor
        if extraction_method == "auto":
            extractor = registry.auto_select(file_path)
            if not extractor:
                return ProcessingResult(
                    success=False,
                    output_paths=[],
                    statistics={},
                    message="No suitable extractor available. Please install dependencies or provide API keys."
                )
        else:
            extractor = registry.get(extraction_method)
            if not extractor:
                return ProcessingResult(
                    success=False,
                    output_paths=[],
                    statistics={},
                    message=f"Unknown extraction method: {extraction_method}"
                )
            
            if not extractor.is_available():
                return ProcessingResult(
                    success=False,
                    output_paths=[],
                    statistics={},
                    message=f"{extractor.name} is not available. Check configuration or dependencies."
                )
        
        # Extract with progress reporting
        await ctx.info(f"Using {extractor.name}...")
        
        async def progress_callback(progress_info):
            percent = progress_info.get('percent', 0.5)
            adjusted_percent = 0.3 + (percent * 0.6)  # Scale to 30%-90%
            current = progress_info.get('current', 0)
            total = progress_info.get('total', 100)
            ctx.report_progress(current, total, f"Processing page {current}/{total}")
        
        result = await extractor.extract(file_path, progress_callback)
        
        await ctx.info("Writing markdown output...")
        
        # Save markdown content
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result.markdown_content)
        
        # Prepare statistics
        statistics = {
            "extraction_method": result.extraction_method,
            "extractor_name": extractor.name,
            "pages": result.page_count,
            "processing_time": f"{result.processing_time:.1f} seconds",
            "output_size": f"{len(result.markdown_content)} characters"
        }
        statistics.update(result.metadata)
        
        await ctx.info("Extraction complete!")
        
        return ProcessingResult(
            success=True,
            output_paths=[output_path],
            statistics=statistics,
            message=f"Successfully extracted {input_path.name} to markdown"
        )
        
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return ProcessingResult(
            success=False,
            output_paths=[],
            statistics={},
            message=f"Extraction failed: {str(e)}"
        )


@server.tool()
async def segment_document(
    file_path: str,
    output_dir: str,
    ctx: Context,
    max_tokens: int = 15000,
    min_tokens: int = 10000,
    break_at_headings: List[str] = ["h1", "h2"]
) -> ProcessingResult:
    """
    Split large markdown document into LLM-ready chunks.
    
    IMPORTANT FOR LLMs:
    - Always ask permission before processing the document
    - Always ask where to save the segments if output_dir not provided
    - Explain that this will split the document into smaller parts
    - Mention this is for documents that exceed LLM context limits
    
    Example interaction:
    User: "Split this large document into chunks"
    LLM: "I can split your document into smaller, manageable chunks suitable for LLM processing. This is useful when documents exceed context limits. May I analyze the document structure?"
    User: "Yes"
    LLM: "Where would you like me to save the segmented files?"
    User: "./chunks"
    LLM: "I'll segment the document and save the chunks to ./chunks..."
    
    Use this tool when documents exceed LLM context limits or need batch processing.
    Unlike split_into_prompts, this creates evenly-sized chunks optimized for token 
    limits while preserving context across segments.
    
    Intelligently segments at natural boundaries (chapters, sections) and maintains
    heading context so each segment knows its place in the document structure.
    
    Args:
        file_path: Path to markdown file to segment (REQUEST PERMISSION before processing)
        output_dir: Directory to save segment files (ALWAYS ASK if not provided)
        max_tokens: Maximum tokens per segment (default: 15000)
        min_tokens: Minimum tokens per segment (default: 10000)
        break_at_headings: Heading levels to prefer for breaks (default: ["h1", "h2"])
    
    Returns:
        ProcessingResult with list of segment file paths
    """
    try:
        # Validate input
        input_path = Path(file_path)
        if not input_path.exists():
            return ProcessingResult(
                success=False,
                output_paths=[],
                statistics={},
                message=f"Input file not found: {file_path}"
            )
        
        if input_path.suffix.lower() not in [".md", ".markdown", ".txt"]:
            return ProcessingResult(
                success=False,
                output_paths=[],
                statistics={},
                message="Only markdown or text files can be segmented"
            )
        
        await ctx.info("Reading document...")
        
        # Read content
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        await ctx.info("Analyzing document structure...")
        
        # Segment the document
        segmenter = DocumentSegmenter()
        segments = segmenter.segment_large_document(
            content,
            min_tokens=min_tokens,
            max_tokens=max_tokens,
            break_at_headings=break_at_headings
        )
        
        # Prepare output directory
        out_path = ensure_output_dir(output_dir)
        segments_path = out_path / "segments"
        segments_path.mkdir(exist_ok=True)
        
        # Save segments
        output_paths = []
        base_name = input_path.stem
        
        for i, segment in enumerate(segments):
            progress = 0.3 + (0.6 * i / len(segments))
            ctx.report_progress(segment.segment_number, segment.total_segments, f"Writing segment {segment.segment_number}")
            
            # Create segment filename
            segment_name = f"{base_name}_{segment.segment_number:03d}_of_{segment.total_segments:03d}.md"
            segment_path = segments_path / segment_name
            
            # Add segment header
            segment_content = f"""<!-- Segment {segment.segment_number} of {segment.total_segments} -->
<!-- Original file: {input_path.name} -->
<!-- Tokens: ~{segment.token_count} -->
<!-- Lines: {segment.start_line}-{segment.end_line} -->

{segment.content}
"""
            
            with open(segment_path, 'w', encoding='utf-8') as f:
                f.write(segment_content)
            
            output_paths.append(str(segment_path))
        
        # Create segmentation report
        await ctx.info("Creating segmentation report...")
        report_path = out_path / "SEGMENTATION_REPORT.md"
        report = f"""# Segmentation Report

Generated: {datetime.now().isoformat()}

## Summary
- Source file: {input_path.name}
- Total segments: {len(segments)}
- Token range: {min_tokens} - {max_tokens}
- Break preferences: {', '.join(break_at_headings)}
- Output directory: {output_dir}

## Segments Created
"""
        
        for segment in segments:
            report += f"\n### Segment {segment.segment_number}\n"
            report += f"- Tokens: ~{segment.token_count}\n"
            report += f"- Lines: {segment.start_line}-{segment.end_line}\n"
            # Show current heading context
            for level in range(1, 7):
                heading = segment.heading_context.get(f"h{level}")
                if heading:
                    report += f"- H{level}: {heading}\n"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        await ctx.info("Segmentation complete!")
        
        # Statistics
        statistics = {
            "total_segments": len(segments),
            "average_tokens": sum(s.token_count for s in segments) // len(segments),
            "min_tokens": min(s.token_count for s in segments),
            "max_tokens": max(s.token_count for s in segments)
        }
        
        return ProcessingResult(
            success=True,
            output_paths=output_paths,
            statistics=statistics,
            message=f"Successfully segmented into {len(segments)} files"
        )
        
    except Exception as e:
        logger.error(f"Segmentation failed: {e}")
        return ProcessingResult(
            success=False,
            output_paths=[],
            statistics={},
            message=f"Segmentation failed: {str(e)}"
        )


@server.tool()
async def split_into_prompts(
    file_path: str,
    output_dir: str,
    ctx: Context,
    split_level: str = "h2",
    include_parent_context: bool = True,
    prompt_template: Optional[str] = None
) -> ProcessingResult:
    """
    Split structured markdown into individual prompts by heading.
    
    IMPORTANT FOR LLMs:
    - Always ask permission before processing the document
    - Always ask where to save the prompts if output_dir not provided
    - Explain this creates one file per heading section
    - Mention this is ideal for structured content that needs individual processing
    
    Example interaction:
    User: "Split this procedures manual into individual prompts"
    LLM: "I can split your procedures manual into individual files, one for each section heading. This is perfect for creating training data or processing each procedure separately. May I analyze the document structure?"
    User: "Yes"
    LLM: "Where would you like me to save the individual prompt files?"
    User: "./procedures"
    LLM: "I'll split the manual by headings and save each procedure to ./procedures..."
    
    Creates one file per heading - ideal for report templates, instruction sets,
    or documentation that needs individual processing. Unlike segment_document,
    this splits strictly by heading structure regardless of size.
    
    Use cases:
    - Converting a report template into individual section templates
    - Splitting a procedures manual into individual procedures
    - Breaking documentation into discrete topics for training
    
    Args:
        file_path: Path to markdown file with clear heading structure
        output_dir: Directory to save prompt files (ALWAYS ASK if not provided)
        split_level: Heading level to split at ("h1", "h2", "h3", etc.)
        include_parent_context: Include parent heading in context (default: true)
        prompt_template: Template with {heading}, {content}, {parent}, {level} placeholders
    
    Returns:
        ProcessingResult with list of prompt file paths
    """
    try:
        # Validate input
        input_path = Path(file_path)
        if not input_path.exists():
            return ProcessingResult(
                success=False,
                output_paths=[],
                statistics={},
                message=f"Input file not found: {file_path}"
            )
        
        if input_path.suffix.lower() not in [".md", ".markdown", ".txt"]:
            return ProcessingResult(
                success=False,
                output_paths=[],
                statistics={},
                message="Only markdown or text files can be split into prompts"
            )
        
        await ctx.info("Reading document...")
        
        # Read content
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        await ctx.info(f"Splitting by {split_level} headings...")
        
        # Split into prompts
        segmenter = DocumentSegmenter()
        prompts = segmenter.split_into_prompts(
            content,
            split_level=split_level,
            include_parent_context=include_parent_context,
            prompt_template=prompt_template
        )
        
        if not prompts:
            return ProcessingResult(
                success=False,
                output_paths=[],
                statistics={},
                message=f"No {split_level} headings found in document"
            )
        
        # Prepare output directory
        out_path = ensure_output_dir(output_dir)
        prompts_path = out_path / "prompts"
        prompts_path.mkdir(exist_ok=True)
        
        # Save prompts
        output_paths = []
        base_name = input_path.stem
        
        for i, prompt in enumerate(prompts):
            progress = 0.3 + (0.6 * i / len(prompts))
            ctx.report_progress(prompt.prompt_number, prompt.total_prompts, f"Writing prompt {prompt.prompt_number}")
            
            # Create prompt filename (sanitize heading for filename)
            safe_heading = "".join(c for c in prompt.heading if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_heading = safe_heading.replace(' ', '_')[:50]  # Limit length
            prompt_name = f"{base_name}_{prompt.prompt_number:03d}_{safe_heading}.md"
            prompt_path = prompts_path / prompt_name
            
            # Add prompt metadata header
            prompt_content = f"""<!-- Prompt {prompt.prompt_number} of {prompt.total_prompts} -->
<!-- Original file: {input_path.name} -->
<!-- Heading: {prompt.heading} -->
<!-- Level: H{prompt.level} -->
"""
            if prompt.parent_heading:
                prompt_content += f"<!-- Parent: {prompt.parent_heading} -->\n"
            
            prompt_content += f"\n{prompt.content}\n"
            
            with open(prompt_path, 'w', encoding='utf-8') as f:
                f.write(prompt_content)
            
            output_paths.append(str(prompt_path))
        
        # Create prompt report
        await ctx.info("Creating prompt report...")
        report_path = out_path / "PROMPT_REPORT.md"
        report = f"""# Prompt Generation Report

Generated: {datetime.now().isoformat()}

## Summary
- Source file: {input_path.name}
- Total prompts: {len(prompts)}
- Split level: {split_level}
- Parent context: {'Included' if include_parent_context else 'Not included'}
- Template used: {'Yes' if prompt_template else 'No'}
- Output directory: {output_dir}

## Prompts Created
"""
        
        for prompt in prompts:
            report += f"\n### Prompt {prompt.prompt_number}: {prompt.heading}\n"
            if prompt.parent_heading:
                report += f"- Parent: {prompt.parent_heading}\n"
            report += f"- Level: H{prompt.level}\n"
            report += f"- Content length: {len(prompt.content)} characters\n"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        await ctx.info("Prompt generation complete!")
        
        # Statistics
        statistics = {
            "total_prompts": len(prompts),
            "split_level": split_level,
            "average_length": sum(len(p.content) for p in prompts) // len(prompts),
            "parent_context": include_parent_context,
            "template_used": bool(prompt_template)
        }
        
        return ProcessingResult(
            success=True,
            output_paths=output_paths,
            statistics=statistics,
            message=f"Successfully created {len(prompts)} prompt files"
        )
        
    except Exception as e:
        logger.error(f"Prompt generation failed: {e}")
        return ProcessingResult(
            success=False,
            output_paths=[],
            statistics={},
            message=f"Prompt generation failed: {str(e)}"
        )


def main():
    """Main entry point for the inkognito FastMCP server."""
    server.run()


# Main entry point
if __name__ == "__main__":
    main()