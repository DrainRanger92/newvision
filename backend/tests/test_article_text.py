"""
Tests for backend/article_text.py — build_full_text and build_summary_context.
"""

from backend.models import (
    CodeBlock,
    HeadingBlock,
    ImageBlock,
    ListBlock,
    ParagraphBlock,
    QuoteBlock,
)
from backend.article_text import build_full_text, build_summary_context


class TestBuildFullText:
    """build_full_text assembles blocks into a single text string."""

    def test_heading(self) -> None:
        blocks = [HeadingBlock(level=2, content="Introduction")]
        result = build_full_text(blocks)
        assert "## Introduction" in result

    def test_paragraph(self) -> None:
        blocks = [ParagraphBlock(content="Some text.")]
        result = build_full_text(blocks)
        assert "Some text." in result

    def test_code_block(self) -> None:
        blocks = [CodeBlock(content="print('hello')", language="python")]
        result = build_full_text(blocks)
        assert "```python" in result
        assert "print('hello')" in result
        assert "```" in result

    def test_code_block_no_language(self) -> None:
        blocks = [CodeBlock(content="x = 1")]
        result = build_full_text(blocks)
        assert "```" in result
        assert "x = 1" in result

    def test_list_block(self) -> None:
        blocks = [ListBlock(items=["First", "Second"], ordered=False)]
        result = build_full_text(blocks)
        assert "• First" in result
        assert "• Second" in result

    def test_quote_block(self) -> None:
        blocks = [QuoteBlock(content="To be or not to be")]
        result = build_full_text(blocks)
        assert "> To be or not to be" in result

    def test_heading_level(self) -> None:
        blocks = [HeadingBlock(level=3, content="Subsection")]
        result = build_full_text(blocks)
        assert "### Subsection" in result

    def test_image_skipped(self) -> None:
        blocks = [
            ImageBlock(src="/img.png", alt="pic"),
            ParagraphBlock(content="After image."),
        ]
        result = build_full_text(blocks)
        assert "After image." in result
        assert "/img.png" not in result

    def test_mixed_blocks(self) -> None:
        blocks = [
            HeadingBlock(level=1, content="Title"),
            ParagraphBlock(content="Intro."),
            CodeBlock(content="fn main() {}", language="rust"),
            ListBlock(items=["A", "B"], ordered=False),
            QuoteBlock(content="End quote."),
            ImageBlock(src="/x.png"),
        ]
        result = build_full_text(blocks)
        assert "# Title" in result
        assert "Intro." in result
        assert "```rust" in result
        assert "• A" in result
        assert "> End quote." in result
        assert "/x.png" not in result

    def test_empty_blocks(self) -> None:
        result = build_full_text([])
        assert result == "\n"


class TestBuildSummaryContext:
    """build_summary_context truncates text to max_chars at sentence boundary."""

    def test_short_text_no_truncation(self) -> None:
        blocks = [ParagraphBlock(content="Short text.")]
        result = build_summary_context(blocks, max_chars=48000)
        assert "Short text." in result
        assert len(result) < 100

    def test_truncates_at_sentence_boundary(self) -> None:
        sentence = "This is a complete sentence. "
        long_text = sentence * 2000
        blocks = [ParagraphBlock(content=long_text)]
        result = build_summary_context(blocks, max_chars=100)
        assert len(result) < len(long_text)
        assert result.strip().endswith(".")

    def test_text_equal_to_max_chars(self) -> None:
        blocks = [ParagraphBlock(content="Short text.")]
        result = build_summary_context(blocks, max_chars=20)
        assert result.strip().endswith(".")

    def test_no_sentence_boundary_in_window(self) -> None:
        blocks = [ParagraphBlock(content="word " * 50000)]
        result = build_summary_context(blocks, max_chars=100)
        assert len(result) <= 105
