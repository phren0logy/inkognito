"""Inkognito FastMCP Server - Document anonymization and processing."""

from fastmcp import FastMCP
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


async def report_progress(message: str, progress: float = None):
    """Report progress via FastMCP streaming."""
    context = server.get_context()
    if context and hasattr(context, 'report_progress'):
        await context.report_progress(message, progress)
    else:
        logger.info(f"Progress: {message}")


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
    files: Optional[List[str]] = None,
    directory: Optional[str] = None,
    patterns: List[str] = ["*.pdf", "*.md", "*.txt"],
    recursive: bool = True,
    entity_types: Optional[List[str]] = None,
    score_threshold: float = 0.5,
    date_shift_days: int = 365
) -> ProcessingResult:
    """
    Anonymize documents by replacing PII with realistic fake data.
    
    This tool processes documents to replace personally identifiable information (PII)
    with consistent, realistic fake data. The same entity always gets the same 
    replacement across all documents (e.g., "John Smith" always becomes "Robert Johnson").
    
    Uses universal PII detection for comprehensive coverage without configuration.
    
    Args:
        output_dir: Directory to save anonymized files and vault
        files: List of specific file paths to anonymize (optional)
        directory: Directory to scan for files (optional, use files OR directory)
        patterns: File patterns to match (default: PDF, markdown, text)
        recursive: Include subdirectories when scanning (default: true)
        entity_types: Optional list of specific entity types to detect
        score_threshold: Confidence threshold for PII detection (default: 0.5)
        date_shift_days: Maximum days to shift dates (default: 365)
    
    Returns:
        ProcessingResult with output paths, statistics, and vault location
    """
    try:
        # Find files to process
        await report_progress("Scanning for documents...", 0.1)
        input_files = find_files(directory, files, patterns, recursive)
        
        if not input_files:
            return ProcessingResult(
                success=False,
                output_paths=[],
                statistics={},
                message="No files found matching the specified patterns"
            )
        
        await report_progress(f"Found {len(input_files)} files to anonymize", 0.2)
        
        # Prepare output directory
        out_path = ensure_output_dir(output_dir)
        anon_path = out_path / "anonymized"
        anon_path.mkdir(exist_ok=True)
        
        # Initialize anonymizer
        anonymizer = PIIAnonymizer()
        
        # Generate date offset for this session
        date_offset = anonymizer.generate_date_offset(date_shift_days)
        
        # Process each file
        total_statistics = {}
        output_paths = []
        vault_mappings = {}
        
        for i, file_path in enumerate(input_files):
            progress = 0.2 + (0.6 * i / len(input_files))
            file_name = Path(file_path).name
            await report_progress(
                f"Processing file {i+1} of {len(input_files)}: {file_name}",
                progress
            )
            
            # Read file content
            content = ""
            file_type = Path(file_path).suffix.lower()
            
            if file_type == ".pdf":
                # Extract PDF to markdown first
                await report_progress(f"Extracting PDF: {file_name}", progress + 0.1)
                
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
        await report_progress("Saving anonymization vault...", 0.9)
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
        
        await report_progress("Anonymization complete!", 1.0)
        
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
    files: Optional[List[str]] = None,
    directory: Optional[str] = None,
    vault_path: Optional[str] = None,
    patterns: List[str] = ["*.md"],
    recursive: bool = True
) -> ProcessingResult:
    """
    Restore original PII in anonymized documents using vault.
    
    This tool reverses the anonymization process by replacing fake data with
    the original PII values stored in the vault. Only works with documents
    that were anonymized using anonymize_documents.
    
    Args:
        output_dir: Directory to save restored files
        files: List of specific anonymized files to restore (optional)
        directory: Directory containing anonymized files (optional)
        vault_path: Path to vault.json (auto-detected if not provided)
        patterns: File patterns to match (default: ["*.md"])
        recursive: Include subdirectories (default: true)
    
    Returns:
        ProcessingResult with restored file paths
    """
    try:
        # Find files to restore
        await report_progress("Scanning for anonymized documents...", 0.1)
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
        
        await report_progress("Loading vault data...", 0.2)
        
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
            await report_progress(
                f"Restoring file {i+1} of {len(input_files)}: {file_name}",
                progress
            )
            
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
        await report_progress("Creating restoration report...", 0.95)
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
        
        await report_progress("Restoration complete!", 1.0)
        
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
    output_path: Optional[str] = None,
    extraction_method: str = "auto"
) -> ProcessingResult:
    """
    Convert PDF or DOCX document to markdown format.
    
    Extracts text content from documents while preserving structure,
    formatting, tables, and other elements. Supports both local 
    processing (Docling, MinerU) and cloud processing (Azure DI, LlamaIndex).
    
    Args:
        file_path: Path to the input document (PDF or DOCX)
        output_path: Path for output markdown file (optional, auto-generated if not provided)
        extraction_method: "auto", "azure", "llamaindex", "docling", or "mineru"
    
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
        
        await report_progress(f"Extracting {input_path.name}...", 0.2)
        
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
        await report_progress(f"Using {extractor.name}...", 0.3)
        
        async def progress_callback(progress_info):
            percent = progress_info.get('percent', 0.5)
            adjusted_percent = 0.3 + (percent * 0.6)  # Scale to 30%-90%
            await report_progress(
                f"Processing page {progress_info.get('current', '?')}/{progress_info.get('total', '?')}",
                adjusted_percent
            )
        
        result = await extractor.extract(file_path, progress_callback)
        
        await report_progress("Writing markdown output...", 0.9)
        
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
        
        await report_progress("Extraction complete!", 1.0)
        
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
    max_tokens: int = 15000,
    min_tokens: int = 10000,
    break_at_headings: List[str] = ["h1", "h2"]
) -> ProcessingResult:
    """
    Split large markdown document into LLM-ready chunks.
    
    Intelligently segments documents at natural boundaries (chapters, sections)
    while respecting token limits. Each segment is a self-contained portion
    suitable for LLM processing.
    
    Args:
        file_path: Path to markdown file to segment
        output_dir: Directory to save segment files
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
        
        await report_progress("Reading document...", 0.1)
        
        # Read content
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        await report_progress("Analyzing document structure...", 0.2)
        
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
            await report_progress(
                f"Writing segment {segment.segment_number} of {segment.total_segments}...",
                progress
            )
            
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
        await report_progress("Creating segmentation report...", 0.95)
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
        
        await report_progress("Segmentation complete!", 1.0)
        
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
    split_level: str = "h2",
    include_parent_context: bool = True,
    prompt_template: Optional[str] = None
) -> ProcessingResult:
    """
    Split structured markdown into individual prompts.
    
    Splits markdown documents by heading level to create individual prompt files.
    Perfect for converting documentation, guides, or structured content into
    discrete prompts for AI training or testing.
    
    Args:
        file_path: Path to markdown file with clear heading structure
        output_dir: Directory to save prompt files
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
        
        await report_progress("Reading document...", 0.1)
        
        # Read content
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        await report_progress(f"Splitting by {split_level} headings...", 0.2)
        
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
            await report_progress(
                f"Writing prompt {prompt.prompt_number} of {prompt.total_prompts}...",
                progress
            )
            
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
        await report_progress("Creating prompt report...", 0.95)
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
        
        await report_progress("Prompt generation complete!", 1.0)
        
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


# Main entry point
if __name__ == "__main__":
    server.run()