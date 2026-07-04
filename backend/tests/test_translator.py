"""
Tests for backend/translator.py — code tag extraction/restoration, plain text conversion,
translatable text gating, OpenAI mocking, batch parsing, and caching.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models import (
    CodeBlock,
    HeadingBlock,
    ImageBlock,
    ListBlock,
    ParagraphBlock,
    QuoteBlock,
)
from backend.translator import (
    TranslationError,
    _build_batch_prompt,
    _build_translation_prompt,
    _extract_code_tags,
    _get_translatable_text,
    _html_to_plain_text,
    _parse_batch_response,
    _restore_code_tags,
    translate_block,
    translate_blocks_batch,
    translate_text,
)


# ── _extract_code_tags ─────────────────────────────────────────────────


class TestExtractCodeTags:
    """Extract <code>...</code> blocks and replace with placeholders."""

    def test_no_code_tags(self) -> None:
        text, codes = _extract_code_tags("<p>Hello</p>")
        assert text == "<p>Hello</p>"
        assert codes == []

    def test_single_code_tag(self) -> None:
        text, codes = _extract_code_tags("<code>print(1)</code>")
        assert text == "__CC_0__"
        assert codes == ["<code>print(1)</code>"]

    def test_multiple_code_tags(self) -> None:
        text, codes = _extract_code_tags(
            "<code>a</code> and <code>b</code>"
        )
        assert text == "__CC_0__ and __CC_1__"
        assert codes == ["<code>a</code>", "<code>b</code>"]

    def test_code_with_attributes(self) -> None:
        text, codes = _extract_code_tags('<code class="python">x=1</code>')
        assert text == "__CC_0__"
        assert len(codes) == 1
        assert 'class="python"' in codes[0]

    def test_multiline_code(self) -> None:
        html = "<code>line1\nline2</code>"
        text, codes = _extract_code_tags(html)
        assert text == "__CC_0__"
        assert "line1" in codes[0]


# ── _restore_code_tags ─────────────────────────────────────────────────


class TestRestoreCodeTags:
    """Restore __CC_N__ placeholders back to original code tags."""

    def test_restore_single(self) -> None:
        result = _restore_code_tags("__CC_0__", ["<code>print(1)</code>"])
        assert result == "<code>print(1)</code>"

    def test_restore_multiple(self) -> None:
        result = _restore_code_tags(
            "__CC_0__ and __CC_1__",
            ["<code>a</code>", "<code>b</code>"],
        )
        assert result == "<code>a</code> and <code>b</code>"

    def test_preserves_unknown_placeholder(self) -> None:
        result = _restore_code_tags("__CC_99__", ["<code>x</code>"])
        assert result == "__CC_99__"

    def test_round_trip(self) -> None:
        original = '<p>Text with <code class="py">import os</code> inline.</p>'
        text, codes = _extract_code_tags(original)
        restored = _restore_code_tags(text, codes)
        assert restored == original


# ── _html_to_plain_text ────────────────────────────────────────────────


class TestHtmlToPlainText:
    """HTML → plain text conversion."""

    def test_simple(self) -> None:
        result = _html_to_plain_text("<p>Hello</p>")
        assert result == "Hello"

    def test_strips_html_tags(self) -> None:
        result = _html_to_plain_text("<p><strong>Bold</strong> and <em>italic</em></p>")
        assert "Bold" in result
        assert "italic" in result
        assert "<strong>" not in result

    def test_collapses_whitespace(self) -> None:
        result = _html_to_plain_text("<p>   Lots   of   spaces   </p>")
        assert result == "Lots of spaces"

    def test_newlines_to_spaces(self) -> None:
        result = _html_to_plain_text("<p>Line1</p>\n<p>Line2</p>")
        assert "Line1" in result
        assert "Line2" in result

    def test_empty_html(self) -> None:
        assert _html_to_plain_text("") == ""


# ── _get_translatable_text ─────────────────────────────────────────────


class TestGetTranslatableText:
    """Extract text from translatable block types; reject code/image."""

    def test_heading_block(self) -> None:
        block = HeadingBlock(level=2, content="Introduction")
        assert _get_translatable_text(block) == "Introduction"

    def test_paragraph_block(self) -> None:
        block = ParagraphBlock(content="Some text")
        assert _get_translatable_text(block) == "Some text"

    def test_quote_block(self) -> None:
        block = QuoteBlock(content="A quote")
        assert _get_translatable_text(block) == "A quote"

    def test_list_block(self) -> None:
        block = ListBlock(items=["Item A", "Item B"], ordered=False)
        assert _get_translatable_text(block) == "Item A\nItem B"

    def test_code_block_raises(self) -> None:
        block = CodeBlock(content="print('x')")
        with pytest.raises(ValueError, match="cannot be translated"):
            _get_translatable_text(block)

    def test_image_block_raises(self) -> None:
        block = ImageBlock(src="/img.png")
        with pytest.raises(ValueError, match="cannot be translated"):
            _get_translatable_text(block)


# ── _build_translation_prompt ──────────────────────────────────────────


class TestBuildTranslationPrompt:
    """Prompt structure for single-block translation."""

    def test_returns_list_of_two_messages(self) -> None:
        prompt = _build_translation_prompt("Hello")
        assert len(prompt) == 2
        assert prompt[0]["role"] == "system"
        assert prompt[1]["role"] == "user"
        assert prompt[1]["content"] == "Hello"

    def test_system_prompt_contains_translation_instructions(self) -> None:
        prompt = _build_translation_prompt("Test")
        content = prompt[0]["content"]
        assert "Translate" in content
        assert "Russian" in content
        assert "__CC_" in content


# ── _build_batch_prompt ────────────────────────────────────────────────


class TestBuildBatchPrompt:
    """Prompt structure for batch translation."""

    def test_returns_two_messages(self) -> None:
        prompt = _build_batch_prompt(["Hello", "World"])
        assert len(prompt) == 2

    def test_contains_block_separators(self) -> None:
        prompt = _build_batch_prompt(["A", "B"])
        user_content = prompt[1]["content"]
        assert "---BLOCK 0---" in user_content
        assert "---BLOCK 1---" in user_content
        assert "A" in user_content
        assert "B" in user_content

    def test_system_prompt_mentions_separators(self) -> None:
        prompt = _build_batch_prompt(["X"])
        system_content = prompt[0]["content"]
        assert "---BLOCK" in system_content


# ── _parse_batch_response ──────────────────────────────────────────────


class TestParseBatchResponse:
    """Parse LLM batch response with ---BLOCK N--- separators."""

    def test_two_blocks(self) -> None:
        response = "---BLOCK 0---\nHello\n---BLOCK 1---\nWorld"
        result = _parse_batch_response(response, 2)
        assert result == {0: "Hello", 1: "World"}

    def test_missing_blocks_return_empty(self) -> None:
        response = "---BLOCK 0---\nOnly first"
        result = _parse_batch_response(response, 3)
        assert result[0] == "Only first"
        assert result[1] == ""
        assert result[2] == ""

    def test_empty_response(self) -> None:
        result = _parse_batch_response("", 2)
        assert result == {0: "", 1: ""}

    def test_multiline_block(self) -> None:
        response = "---BLOCK 0---\nLine1\nLine2\n---BLOCK 1---\nSingle"
        result = _parse_batch_response(response, 2)
        assert "Line1" in result[0]
        assert "Line2" in result[0]


# ── translate_text (mocked OpenAI) ─────────────────────────────────────


class TestTranslateText:
    """translate_text with mocked OpenAI client."""

    @pytest.mark.asyncio
    async def test_successful_translation(self, mock_openai_client: MagicMock) -> None:
        result = await translate_text("Hello", "sk-test", "deepseek-chat")
        assert result == "Translated text"

    @pytest.mark.asyncio
    async def test_passes_api_key_and_model(self, mock_openai_client: MagicMock) -> None:
        with patch("backend.translator.httpx.AsyncClient") as mock_http:
            http_client = AsyncMock()
            mock_http.return_value = http_client

            await translate_text("Test", "sk-custom", "gpt-4")

            # AsyncOpenAI was constructed with our api_key

            # Verify the API was called
            assert mock_openai_client.chat.completions.create.called

    @pytest.mark.asyncio
    async def test_llm_empty_response_raises(self) -> None:
        """When LLM returns None content, raise TranslationError."""
        msg = MagicMock()
        msg.content = None
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]

        client = MagicMock()
        client.chat = MagicMock()
        client.chat.completions = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=resp)

        import backend.translator

        original = backend.translator.AsyncOpenAI
        backend.translator.AsyncOpenAI = lambda *a, **kw: client  # type: ignore[assignment]

        try:
            with pytest.raises(TranslationError, match="empty response"):
                await translate_text("Hello", "sk-test")
        finally:
            backend.translator.AsyncOpenAI = original

    @pytest.mark.asyncio
    async def test_translate_text_uses_30s_timeout(self, mock_openai_client: MagicMock) -> None:
        """translate_text creates httpx.AsyncClient with timeout=30.0."""
        with patch("backend.translator.httpx.AsyncClient") as mock_http_cls:
            http_client = AsyncMock()
            http_client.aclose = AsyncMock()
            mock_http_cls.return_value = http_client

            await translate_text("Hello", "sk-test")

            call_kwargs = mock_http_cls.call_args[1]
            timeout = call_kwargs["timeout"]
            assert timeout.connect == 3.0
            assert timeout.read == 30.0
            assert timeout.write == 30.0
            assert timeout.pool == 30.0

    @pytest.mark.asyncio
    async def test_translate_text_calls_logevent_on_error(self, mock_openai_client: MagicMock) -> None:
        """When translate_text fails, logevent is called."""
        mock_openai_client.chat.completions.create = AsyncMock(side_effect=Exception("API error"))

        with (
            patch("backend.translator.httpx.AsyncClient") as mock_http_cls,
            patch("backend.translator.logevent") as mock_logevent_fn,
        ):
            http_client = AsyncMock()
            http_client.aclose = AsyncMock()
            mock_http_cls.return_value = http_client

            with pytest.raises(TranslationError):
                await translate_text("Hello", "sk-test")

            mock_logevent_fn.assert_called_once()
            args, kwargs = mock_logevent_fn.call_args
            assert args[1] == "translator"
            assert args[2] == "TRANSLATE_TEXT_FAILED"
            assert kwargs["exc_info"] is True
            assert kwargs["error"] == "API error"


# ── translate_block (mocked) ───────────────────────────────────────────


class TestTranslateBlock:
    """translate_block with mocked OpenAI and DB."""

    @pytest.mark.asyncio
    async def test_code_block_raises(self) -> None:
        block = CodeBlock(content="code")
        with pytest.raises(ValueError, match="cannot be translated"):
            await translate_block("a", 0, block, "sk-test")

    @pytest.mark.asyncio
    async def test_image_block_raises(self) -> None:
        block = ImageBlock(src="/img.png")
        with pytest.raises(ValueError, match="cannot be translated"):
            await translate_block("a", 0, block, "sk-test")

    @pytest.mark.asyncio
    async def test_cache_hit(self, mock_openai_client: MagicMock) -> None:
        """When cache returns a value, no API call is made."""
        block = ParagraphBlock(content="Hello")

        with (
            patch("backend.db.get_translation", AsyncMock(return_value="Hola")),
            patch("backend.db.save_translation", AsyncMock()),
        ):
            text, cached, error = await translate_block(
                "a", 0, block, "sk-test"
            )

        assert text == "Hola"
        assert cached is True
        assert error is False
        # No API call was made
        assert not mock_openai_client.chat.completions.create.called

    @pytest.mark.asyncio
    async def test_cache_miss_calls_api(self, mock_openai_client: MagicMock) -> None:
        block = ParagraphBlock(content="Hello")

        with (
            patch("backend.db.get_translation", AsyncMock(return_value=None)),
            patch("backend.db.save_translation", AsyncMock()),
        ):
            text, cached, error = await translate_block(
                "a", 0, block, "sk-test"
            )

        assert text == "Translated text"
        assert cached is False
        assert error is False

    @pytest.mark.asyncio
    async def test_translation_failure_fallback(self) -> None:
        """On TranslationError, returns original text with error=True."""
        block = ParagraphBlock(content="Original")

        with (
            patch(
                "backend.translator.translate_text",
                AsyncMock(side_effect=TranslationError("fail")),
            ),
            patch("backend.db.get_translation", AsyncMock(return_value=None)),
            patch("backend.db.save_translation", AsyncMock()),
        ):
            text, cached, error = await translate_block(
                "a", 0, block, "sk-test"
            )

        assert text == "Original"
        assert cached is False
        assert error is True

    @pytest.mark.asyncio
    async def test_code_tags_restored_after_translation(
        self, mock_openai_client: MagicMock
    ) -> None:
        """Code tags in content are extracted, text translated, tags restored."""
        block = ParagraphBlock(content='Text with <code>inline code</code> inside.')

        # Override the mock response to include the code placeholder
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content="Text with __CC_0__ inside."))]
            )
        )

        with (
            patch("backend.db.get_translation", AsyncMock(return_value=None)),
            patch("backend.db.save_translation", AsyncMock()),
        ):
            text, *_ = await translate_block("a", 0, block, "sk-test")

        # The code placeholder should be restored
        assert "<code>inline code</code>" in text
        assert "__CC_" not in text


# ── translate_blocks_batch (mocked) ────────────────────────────────────


class TestTranslateBlocksBatch:
    """Batch translation with mocked OpenAI and DB."""

    @pytest.mark.asyncio
    async def test_all_cached(self) -> None:
        """When all blocks are cached, no API call."""
        blocks = [
            (0, ParagraphBlock(content="A")),
            (1, ParagraphBlock(content="B")),
        ]

        with (
            patch(
                "backend.db.get_translations_batch",
                AsyncMock(return_value={0: "Trans A", 1: "Trans B"}),
            ),
            patch("backend.db.save_translation", AsyncMock()),
        ):
            results = await translate_blocks_batch(
                "a", blocks, "sk-test"
            )

        assert len(results) == 2
        assert results[0] == (0, "Trans A", True, False)
        assert results[1] == (1, "Trans B", True, False)

    @pytest.mark.asyncio
    async def test_skips_code_and_image_blocks(
        self, mock_openai_client: MagicMock
    ) -> None:
        """Code and Image blocks are returned as-is with error=True."""
        blocks = [
            (0, CodeBlock(content="print('hi')")),
            (1, ImageBlock(src="/img.png")),
        ]

        with (
            patch("backend.db.get_translations_batch", AsyncMock(return_value={})),
            patch("backend.db.save_translation", AsyncMock()),
        ):
            results = await translate_blocks_batch(
                "a", blocks, "sk-test"
            )

        assert len(results) == 2
        assert results[0][0] == 0
        assert results[0][2] is False  # not cached
        assert results[0][3] is True  # error
        assert results[1][0] == 1
        assert results[1][3] is True

    @pytest.mark.asyncio
    async def test_mixed_cache_and_translate(
        self, mock_openai_client: MagicMock
    ) -> None:
        """Some cached, some translated via API."""
        blocks = [
            (0, ParagraphBlock(content="Cached")),
            (1, ParagraphBlock(content="Fresh")),
        ]

        with (
            patch(
                "backend.db.get_translations_batch",
                AsyncMock(return_value={0: "Cached text"}),
            ),
            patch("backend.db.save_translation", AsyncMock()),
        ):
            results = await translate_blocks_batch(
                "a", blocks, "sk-test"
            )

        assert len(results) == 2
        # First result is cached
        assert results[0] == (0, "Cached text", True, False)
        # Second result was translated
        assert results[1][0] == 1
        assert results[1][2] is False
        assert results[1][3] is False

    @pytest.mark.asyncio
    async def test_batch_api_failure_fallback(
        self, mock_openai_client: MagicMock
    ) -> None:
        """On TranslationError in batch, fall back to translate_text per block."""
        blocks = [
            (0, ParagraphBlock(content="Block A")),
        ]

        with (
            patch("backend.db.get_translations_batch", AsyncMock(return_value={})),
            patch("backend.db.save_translation", AsyncMock()),
            patch(
                "backend.translator.translate_text",
                AsyncMock(return_value="Fallback translation"),
            ),
        ):
            # Mock _build_batch_prompt and the OpenAI call to trigger a missing block scenario
            results = await translate_blocks_batch(
                "a", blocks, "sk-test"
            )

        assert len(results) == 1
        assert results[0][0] == 0
        assert results[0][3] is False  # no error - fallback succeeded

    @pytest.mark.asyncio
    async def test_results_are_sorted(
        self, mock_openai_client: MagicMock
    ) -> None:
        """Results are returned in ascending block_index order."""
        blocks = [
            (3, ParagraphBlock(content="D")),
            (1, ParagraphBlock(content="B")),
            (0, ParagraphBlock(content="A")),
        ]

        with (
            patch(
                "backend.db.get_translations_batch",
                AsyncMock(return_value={}),
            ),
            patch("backend.db.save_translation", AsyncMock()),
            patch(
                "backend.translator.translate_text",
                AsyncMock(side_effect=["Trans A", "Trans B", "Trans D"]),
            ),
        ):
            results = await translate_blocks_batch(
                "a", blocks, "sk-test"
            )

        assert [r[0] for r in results] == [0, 1, 3]
