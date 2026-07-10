"""
# @module: article_text
"""

import logging
import re

from backend.models import Block, CodeBlock, HeadingBlock, ImageBlock, ListBlock, ParagraphBlock, QuoteBlock

logger = logging.getLogger(__name__)

SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")


def build_full_text(blocks: list[Block]) -> str:
    """Собрать полный текст статьи из блоков."""
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, HeadingBlock):
            prefix = "#" * block.level
            parts.append(f"{prefix} {block.content}\n\n")
        elif isinstance(block, ParagraphBlock):
            parts.append(f"{block.content}\n\n")
        elif isinstance(block, CodeBlock):
            lang = block.language or ""
            parts.append(f"```{lang}\n{block.content}```\n\n")
        elif isinstance(block, ListBlock):
            for item in block.items:
                parts.append(f"• {item}\n")
            parts.append("\n")
        elif isinstance(block, QuoteBlock):
            parts.append(f"> {block.content}\n\n")
        elif isinstance(block, ImageBlock):
            pass
    return "".join(parts).rstrip() + "\n"


def build_summary_context(blocks: list[Block], max_chars: int = 48000) -> str:
    """Текст для summary с обрезкой до ~12K токенов."""
    full_text = build_full_text(blocks)
    if len(full_text) <= max_chars:
        return full_text

    truncated = full_text[:max_chars]
    matches = list(SENTENCE_BOUNDARY_RE.finditer(truncated))
    if matches:
        end = matches[-1].end()
        return truncated[:end].rstrip() + "\n"
    return truncated.rstrip() + "\n"
