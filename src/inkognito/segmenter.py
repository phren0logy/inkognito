"""Document segmentation for different use cases."""

import re
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

try:
    import tiktoken
except ImportError:
    raise ImportError("tiktoken is required. Install with: pip install tiktoken")

import logging

logger = logging.getLogger(__name__)


@dataclass
class DocumentSegment:
    """A segment of document content."""
    content: str
    token_count: int
    start_line: int
    end_line: int
    heading_context: Dict[str, Optional[str]]
    segment_number: int
    total_segments: int


@dataclass
class DocumentPrompt:
    """A prompt extracted from structured content."""
    content: str
    heading: str
    parent_heading: Optional[str]
    level: int
    prompt_number: int
    total_prompts: int


class DocumentSegmenter:
    """Handles document splitting strategies."""
    
    def __init__(self):
        self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def segment_large_document(
        self,
        content: str,
        min_tokens: int = 10000,
        max_tokens: int = 30000,
        break_at_headings: List[str] = ["h1", "h2"]
    ) -> List[DocumentSegment]:
        """
        Split large documents into optimal chunks for LLM processing.
        
        Args:
            content: Markdown content to segment
            min_tokens: Minimum tokens per segment
            max_tokens: Maximum tokens per segment (soft limit)
            break_at_headings: Heading levels to prefer for breaks
            
        Returns:
            List of document segments
        """
        lines = content.split('\n')
        headings = self._parse_markdown_headings(lines)
        heading_lines = {h[0] for h in headings}
        
        # Convert break_at_headings to levels
        break_levels = []
        for h in break_at_headings:
            if h.startswith('h') and h[1:].isdigit():
                break_levels.append(int(h[1:]))
        
        # Track heading context
        heading_context = {f"h{i}": None for i in range(1, 7)}
        
        segments = []
        current_segment_lines = []
        current_token_count = 0
        segment_start_line = 0
        
        # Track if we're in special blocks
        in_code_block = False
        in_table = False
        
        for i, line in enumerate(lines):
            # Check for code block boundaries
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
            
            # Check for table
            if line.strip().startswith('|'):
                in_table = True
            elif not line.strip().startswith('|') and in_table:
                in_table = False
            
            # Calculate tokens for this line
            line_tokens = len(self.encoding.encode(line))
            
            # Update heading context if this is a heading
            if i in heading_lines:
                for h in headings:
                    if h[0] == i:
                        level = h[1]
                        heading_context[f"h{level}"] = h[2]
                        # Clear lower-level headings
                        for lower_level in range(level + 1, 7):
                            heading_context[f"h{lower_level}"] = None
                        break
            
            # Check if we should start a new segment
            should_split = False
            
            # Don't split in the middle of code blocks or tables
            if not in_code_block and not in_table:
                # Check if we've reached minimum tokens and hit a break heading
                if current_token_count >= min_tokens and i in heading_lines:
                    for h in headings:
                        if h[0] == i and h[1] in break_levels:
                            should_split = True
                            break
                
                # Force split if we exceed max tokens
                elif current_token_count + line_tokens > max_tokens and current_segment_lines:
                    should_split = True
            
            # Create segment if needed
            if should_split and current_segment_lines:
                segments.append(DocumentSegment(
                    content='\n'.join(current_segment_lines),
                    token_count=current_token_count,
                    start_line=segment_start_line + 1,
                    end_line=i,
                    heading_context=heading_context.copy(),
                    segment_number=len(segments) + 1,
                    total_segments=0  # Will be updated later
                ))
                
                # Start new segment
                current_segment_lines = []
                current_token_count = 0
                segment_start_line = i
            
            # Add line to current segment
            current_segment_lines.append(line)
            current_token_count += line_tokens
        
        # Add final segment if not empty
        if current_segment_lines:
            segments.append(DocumentSegment(
                content='\n'.join(current_segment_lines),
                token_count=current_token_count,
                start_line=segment_start_line + 1,
                end_line=len(lines),
                heading_context=heading_context.copy(),
                segment_number=len(segments) + 1,
                total_segments=0
            ))
        
        # Update total segments count
        total = len(segments)
        for segment in segments:
            segment.total_segments = total
        
        return segments
    
    def split_into_prompts(
        self,
        content: str,
        split_level: str = "h2",
        include_parent_context: bool = True,
        prompt_template: Optional[str] = None
    ) -> List[DocumentPrompt]:
        """
        Split structured markdown into individual prompts.
        
        Args:
            content: Markdown content with clear heading structure
            split_level: Heading level to split at (h1, h2, h3, etc.)
            include_parent_context: Include parent heading in context
            prompt_template: Template for prompts with {heading} and {content} placeholders
            
        Returns:
            List of document prompts
        """
        # Parse split level
        if not split_level.startswith('h') or not split_level[1:].isdigit():
            raise ValueError(f"Invalid split_level: {split_level}")
        
        target_level = int(split_level[1:])
        
        lines = content.split('\n')
        headings = self._parse_markdown_headings(lines)
        
        prompts = []
        current_prompt_lines = []
        current_heading = ""
        current_parent = None
        prompt_start_line = 0
        
        # Track parent headings
        parent_context = {i: None for i in range(1, 7)}
        
        for i, line in enumerate(lines):
            # Check if this is a heading
            is_target_heading = False
            for h in headings:
                if h[0] == i:
                    level = h[1]
                    text = h[2]
                    
                    # Update parent context
                    parent_context[level] = text
                    for lower in range(level + 1, 7):
                        parent_context[lower] = None
                    
                    # Check if this is our target level
                    if level == target_level:
                        # Save previous prompt if exists
                        if current_prompt_lines and current_heading:
                            prompts.append(self._create_prompt(
                                current_prompt_lines,
                                current_heading,
                                current_parent,
                                target_level,
                                len(prompts) + 1,
                                prompt_template
                            ))
                        
                        # Start new prompt
                        current_prompt_lines = [line]
                        current_heading = text
                        current_parent = parent_context.get(target_level - 1) if include_parent_context else None
                        is_target_heading = True
                    break
            
            # Add line to current prompt
            if not is_target_heading and current_heading:
                current_prompt_lines.append(line)
            elif not current_heading and not is_target_heading:
                # Before first target heading - could be frontmatter
                current_prompt_lines.append(line)
        
        # Add final prompt if exists
        if current_prompt_lines:
            if current_heading:
                prompts.append(self._create_prompt(
                    current_prompt_lines,
                    current_heading,
                    current_parent,
                    target_level,
                    len(prompts) + 1,
                    prompt_template
                ))
            elif any(line.strip() for line in current_prompt_lines):
                # Frontmatter without heading
                prompts.append(self._create_prompt(
                    current_prompt_lines,
                    "Introduction",
                    None,
                    0,
                    len(prompts) + 1,
                    prompt_template
                ))
        
        # Update total prompts count
        total = len(prompts)
        for prompt in prompts:
            prompt.total_prompts = total
        
        return prompts
    
    def _parse_markdown_headings(self, lines: List[str]) -> List[Tuple[int, int, str]]:
        """
        Parse markdown lines to find headings.
        
        Returns:
            List of (line_number, level, text) tuples
        """
        headings = []
        for i, line in enumerate(lines):
            match = re.match(r'^(#{1,6})\s+(.+)$', line.strip())
            if match:
                level = len(match.group(1))
                text = match.group(2).strip()
                headings.append((i, level, text))
        return headings
    
    def _create_prompt(
        self,
        lines: List[str],
        heading: str,
        parent_heading: Optional[str],
        level: int,
        prompt_number: int,
        template: Optional[str]
    ) -> DocumentPrompt:
        """Create a document prompt with optional template."""
        content = '\n'.join(lines).strip()
        
        # Apply template if provided
        if template:
            formatted_content = template.format(
                heading=heading,
                content=content,
                parent=parent_heading or "",
                level=level
            )
        else:
            formatted_content = content
        
        return DocumentPrompt(
            content=formatted_content,
            heading=heading,
            parent_heading=parent_heading,
            level=level,
            prompt_number=prompt_number,
            total_prompts=0  # Will be updated
        )