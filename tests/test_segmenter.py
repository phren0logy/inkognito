"""Tests for document segmentation functionality."""

import pytest
from unittest.mock import Mock, patch
import re

from segmenter import DocumentSegmenter, DocumentSegment, DocumentPrompt


class TestDocumentSegmenter:
    """Test the DocumentSegmenter class."""
    
    @pytest.fixture
    def segmenter(self):
        """Create a DocumentSegmenter instance."""
        return DocumentSegmenter()
    
    @pytest.fixture
    def mock_encoder(self):
        """Create a mock tiktoken encoder."""
        encoder = Mock()
        # Simple token counting: ~4 chars per token
        encoder.encode.side_effect = lambda text: ["tok"] * (len(text) // 4)
        return encoder
    
    def test_init(self, segmenter):
        """Test DocumentSegmenter initialization."""
        assert segmenter.encoder is not None
    
    def test_count_tokens(self, segmenter, mock_encoder):
        """Test token counting functionality."""
        segmenter.encoder = mock_encoder
        
        # Test various text lengths
        assert segmenter._count_tokens("") == 0
        assert segmenter._count_tokens("test") == 1  # 4 chars = 1 token
        assert segmenter._count_tokens("hello world!") == 3  # 12 chars = 3 tokens
        assert segmenter._count_tokens("a" * 100) == 25  # 100 chars = 25 tokens
    
    def test_extract_heading_info(self, segmenter):
        """Test heading extraction from markdown lines."""
        # Test h1
        heading, level = segmenter._extract_heading_info("# Main Title")
        assert heading == "Main Title"
        assert level == 1
        
        # Test h2
        heading, level = segmenter._extract_heading_info("## Section Title")
        assert heading == "Section Title"
        assert level == 2
        
        # Test h3
        heading, level = segmenter._extract_heading_info("### Subsection")
        assert heading == "Subsection"
        assert level == 3
        
        # Test h6
        heading, level = segmenter._extract_heading_info("###### Deep Heading")
        assert heading == "Deep Heading"
        assert level == 6
        
        # Test non-heading
        heading, level = segmenter._extract_heading_info("Regular text")
        assert heading is None
        assert level is None
        
        # Test malformed heading
        heading, level = segmenter._extract_heading_info("#No space")
        assert heading is None
        assert level is None
    
    def test_segment_large_document_simple(self, segmenter, mock_encoder):
        """Test basic document segmentation."""
        segmenter.encoder = mock_encoder
        
        # Create a document with clear boundaries
        document = """# Chapter 1
        
Content for chapter 1. """ + "Lorem ipsum " * 100 + """

# Chapter 2

Content for chapter 2. """ + "Dolor sit amet " * 100 + """

# Chapter 3

Content for chapter 3. """ + "Consectetur " * 100
        
        segments = segmenter.segment_large_document(
            document,
            min_tokens=200,
            max_tokens=400,
            break_at_headings=["h1"]
        )
        
        assert len(segments) >= 2
        assert all(isinstance(s, DocumentSegment) for s in segments)
        assert segments[0].heading_context.get("h1") == "Chapter 1"
        
        # Check segment numbering
        for i, segment in enumerate(segments):
            assert segment.segment_number == i + 1
            assert segment.total_segments == len(segments)
    
    def test_segment_respects_max_tokens(self, segmenter, mock_encoder):
        """Test that segments don't exceed max tokens."""
        segmenter.encoder = mock_encoder
        
        # Create very long content
        long_content = "word " * 2000  # ~2500 tokens
        
        segments = segmenter.segment_large_document(
            long_content,
            min_tokens=100,
            max_tokens=500
        )
        
        # Should create multiple segments
        assert len(segments) >= 5
        
        # Each segment should be under max tokens
        for segment in segments:
            assert segment.token_count <= 500
    
    def test_segment_heading_context_preservation(self, segmenter, mock_encoder):
        """Test that heading context is preserved across segments."""
        segmenter.encoder = mock_encoder
        
        document = """# Main Title

## Section A

### Subsection A.1

Content here.

### Subsection A.2

More content.

## Section B

Different content."""
        
        segments = segmenter.segment_large_document(
            document,
            min_tokens=10,
            max_tokens=50,
            break_at_headings=["h3"]
        )
        
        # Check that heading context is maintained
        for segment in segments:
            if "Subsection A.1" in segment.content:
                assert segment.heading_context.get("h1") == "Main Title"
                assert segment.heading_context.get("h2") == "Section A"
                assert segment.heading_context.get("h3") == "Subsection A.1"
            elif "Section B" in segment.content:
                assert segment.heading_context.get("h1") == "Main Title"
                assert segment.heading_context.get("h2") == "Section B"
    
    def test_segment_code_block_preservation(self, segmenter, mock_encoder):
        """Test that code blocks are not split."""
        segmenter.encoder = mock_encoder
        
        document = """# Title

Some text before code.

```python
def long_function():
    # This is a long code block
    # It should not be split
    for i in range(100):
        print(f"Line {i}")
    return "Done"
```

Text after code."""
        
        segments = segmenter.segment_large_document(
            document,
            min_tokens=10,
            max_tokens=50
        )
        
        # Code block should be intact in one segment
        code_block_found = False
        for segment in segments:
            if "```python" in segment.content:
                assert "def long_function():" in segment.content
                assert "return \"Done\"" in segment.content
                assert "```" in segment.content
                code_block_found = True
        
        assert code_block_found
    
    def test_segment_table_preservation(self, segmenter, mock_encoder):
        """Test that tables are not split."""
        segmenter.encoder = mock_encoder
        
        document = """# Title

Text before table.

| Header 1 | Header 2 | Header 3 |
|----------|----------|----------|
| Cell 1   | Cell 2   | Cell 3   |
| Cell 4   | Cell 5   | Cell 6   |
| Cell 7   | Cell 8   | Cell 9   |

Text after table."""
        
        segments = segmenter.segment_large_document(
            document,
            min_tokens=5,
            max_tokens=30
        )
        
        # Table should be intact in one segment
        table_found = False
        for segment in segments:
            if "| Header 1" in segment.content:
                assert "| Cell 9" in segment.content
                table_found = True
        
        assert table_found
    
    def test_segment_min_tokens_respected(self, segmenter, mock_encoder):
        """Test that segments meet minimum token requirements."""
        segmenter.encoder = mock_encoder
        
        document = """# Chapter 1

Short content.

# Chapter 2

Also short.

# Chapter 3

More short content."""
        
        segments = segmenter.segment_large_document(
            document,
            min_tokens=50,
            max_tokens=200,
            break_at_headings=["h1"]
        )
        
        # Should combine short sections to meet min tokens
        assert len(segments) < 3
        for segment in segments:
            assert segment.token_count >= 50 or segment == segments[-1]
    
    def test_split_into_prompts_by_h2(self, segmenter):
        """Test splitting document into prompts by h2 headings."""
        document = """# Main Document

## First Section

Content for first section.

## Second Section

Content for second section.

### Subsection 2.1

Details here.

## Third Section

Final content."""
        
        prompts = segmenter.split_into_prompts(
            document,
            split_level="h2"
        )
        
        assert len(prompts) == 3
        assert all(isinstance(p, DocumentPrompt) for p in prompts)
        
        # Check prompt details
        assert prompts[0].heading == "First Section"
        assert prompts[0].level == 2
        assert prompts[0].parent_heading == "Main Document"
        assert "Content for first section" in prompts[0].content
        
        assert prompts[1].heading == "Second Section"
        assert "Subsection 2.1" in prompts[1].content
        
        assert prompts[2].heading == "Third Section"
    
    def test_split_into_prompts_by_h3(self, segmenter):
        """Test splitting by h3 headings."""
        document = """# Title

## Section

### Part A

Content A.

### Part B

Content B."""
        
        prompts = segmenter.split_into_prompts(
            document,
            split_level="h3",
            include_parent_context=True
        )
        
        assert len(prompts) == 2
        assert prompts[0].heading == "Part A"
        assert prompts[0].parent_heading == "Section"
        assert prompts[1].heading == "Part B"
    
    def test_split_into_prompts_no_parent_context(self, segmenter):
        """Test splitting without parent context."""
        document = """# Title

## Section A

Content.

## Section B

More content."""
        
        prompts = segmenter.split_into_prompts(
            document,
            split_level="h2",
            include_parent_context=False
        )
        
        assert len(prompts) == 2
        for prompt in prompts:
            assert prompt.parent_heading is None
    
    def test_split_into_prompts_with_template(self, segmenter):
        """Test splitting with custom prompt template."""
        document = """# Doc

## Task 1

Do this.

## Task 2

Do that."""
        
        template = "Task: {heading}\nContext: {parent}\n\nInstructions:\n{content}"
        
        prompts = segmenter.split_into_prompts(
            document,
            split_level="h2",
            prompt_template=template
        )
        
        assert len(prompts) == 2
        assert prompts[0].content.startswith("Task: Task 1")
        assert "Context: Doc" in prompts[0].content
        assert "Instructions:" in prompts[0].content
        assert "Do this." in prompts[0].content
    
    def test_split_into_prompts_no_headings(self, segmenter):
        """Test handling documents without target headings."""
        document = """# Only H1

Just content without h2 headings."""
        
        prompts = segmenter.split_into_prompts(
            document,
            split_level="h2"
        )
        
        assert len(prompts) == 0
    
    def test_split_into_prompts_numbering(self, segmenter):
        """Test that prompts are correctly numbered."""
        document = """# Doc

## A

Text.

## B

Text.

## C

Text."""
        
        prompts = segmenter.split_into_prompts(document, split_level="h2")
        
        assert len(prompts) == 3
        for i, prompt in enumerate(prompts):
            assert prompt.prompt_number == i + 1
            assert prompt.total_prompts == 3
    
    def test_edge_case_empty_document(self, segmenter, mock_encoder):
        """Test segmenting empty document."""
        segmenter.encoder = mock_encoder
        
        segments = segmenter.segment_large_document("")
        assert len(segments) == 1
        assert segments[0].content == ""
        assert segments[0].token_count == 0
    
    def test_edge_case_only_headings(self, segmenter, mock_encoder):
        """Test document with only headings."""
        segmenter.encoder = mock_encoder
        
        document = """# Heading 1

## Heading 2

### Heading 3"""
        
        segments = segmenter.segment_large_document(
            document,
            min_tokens=5,
            max_tokens=20
        )
        
        assert len(segments) >= 1
        assert all(s.content.strip() for s in segments)
    
    def test_large_document_performance(self, segmenter, mock_encoder):
        """Test segmentation performance with large document."""
        segmenter.encoder = mock_encoder
        
        # Create a very large document
        sections = []
        for i in range(50):
            sections.append(f"# Chapter {i}\n\n" + "Content " * 200)
        
        large_doc = "\n\n".join(sections)
        
        segments = segmenter.segment_large_document(
            large_doc,
            min_tokens=500,
            max_tokens=1000
        )
        
        # Should handle large documents efficiently
        assert len(segments) > 20
        assert all(s.token_count <= 1000 for s in segments)