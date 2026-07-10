"""
Tests for backend/bot.py — handle_message with summarizer integration.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.bot import handle_message, handle_start
from backend.models import Article, ParagraphBlock


def _make_message(text: str) -> MagicMock:
    """Create a mock aiogram Message with answer() returning a placeholder."""
    placeholder = MagicMock()
    placeholder.message_id = 123
    placeholder.edit_text = AsyncMock()

    msg = MagicMock()
    msg.text = text
    msg.answer = AsyncMock(return_value=placeholder)

    return msg


def _make_article(article_id: str = "test-abc123") -> Article:
    """Create a sample Article for tests."""
    return Article(
        id=article_id,
        url="https://example.com/test-article",
        title="Test Article Title",
        blocks=[
            ParagraphBlock(content="First block."),
            ParagraphBlock(content="Second block."),
        ],
    )


def _mock_settings(**overrides: str) -> MagicMock:
    """Create a mock Settings object with the specified overrides."""
    s = MagicMock()
    s.deepseek_api_key = overrides.get("deepseek_api_key", "")
    s.translation_model = overrides.get("translation_model", "deepseek-chat")
    s.mini_app_url = overrides.get("mini_app_url", "http://localhost:5173")
    s.webhook_url = overrides.get("webhook_url", "")
    s.webhook_path = overrides.get("webhook_path", "/webhook/telegram")
    return s


class TestHandleStart:
    """Tests for /start command."""

    @pytest.mark.asyncio
    async def test_start_sends_welcome(self) -> None:
        msg = _make_message("/start")
        await handle_start(msg)

        msg.answer.assert_awaited_once()
        call_args = msg.answer.call_args[0]
        assert "Welcome to NewVision" in call_args[0]


class TestHandleMessage:
    """Tests for the URL handler with summarizer integration."""

    @pytest.mark.asyncio
    async def test_non_url_message_replies_prompt(self) -> None:
        msg = _make_message("hello world")
        await handle_message(msg)

        msg.answer.assert_awaited_once()
        assert "valid URL" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_empty_message_replies_prompt(self) -> None:
        msg = _make_message("")
        await handle_message(msg)

        msg.answer.assert_awaited_once()
        assert "valid URL" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_url_without_netloc_replies_prompt(self) -> None:
        msg = _make_message("not-a-url")
        await handle_message(msg)

        msg.answer.assert_awaited_once()
        assert "valid URL" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_new_article_full_flow(self) -> None:
        article = _make_article()
        msg = _make_message("https://example.com/test-article")
        placeholder = msg.answer.return_value

        with (
            patch("backend.bot.get_article_by_url", AsyncMock(return_value=None)),
            patch(
                "backend.bot.parse_article",
                AsyncMock(return_value=("<html>", article.title, article.blocks)),
            ),
            patch("backend.bot.save_article", AsyncMock()),
            patch(
                "backend.bot.settings", _mock_settings(deepseek_api_key="sk-test-key")
            ),
            patch(
                "backend.bot.summarize_article",
                AsyncMock(
                    return_value=("Краткое содержание статьи на русском.", False, False)
                ),
            ),
        ):
            await handle_message(msg)

        placeholder.edit_text.assert_awaited_once()
        call_args = placeholder.edit_text.call_args
        display_text = call_args[0][0]
        assert article.title in display_text
        assert "Краткое содержание статьи на русском." in display_text

        kwargs = call_args[1]
        assert kwargs["parse_mode"] == "HTML"
        assert kwargs["reply_markup"] is not None

    @pytest.mark.asyncio
    async def test_cache_hit_instant_response(self) -> None:
        """Repeated URL: article exists in DB, summary cached — no LLM call."""
        article = _make_article()
        msg = _make_message("https://example.com/test-article")
        placeholder = msg.answer.return_value

        with (
            patch("backend.bot.get_article_by_url", AsyncMock(return_value=article)),
            patch(
                "backend.bot.settings", _mock_settings(deepseek_api_key="sk-test-key")
            ),
            patch(
                "backend.bot.summarize_article",
                AsyncMock(return_value=("Кэшированное саммари.", True, False)),
            ),
        ):
            await handle_message(msg)

        placeholder.edit_text.assert_awaited_once()
        call_args = placeholder.edit_text.call_args
        display_text = call_args[0][0]
        assert article.title in display_text
        assert "Кэшированное саммари." in display_text

    @pytest.mark.asyncio
    async def test_deepseek_failure_fallback(self) -> None:
        """DeepSeek error: show title + button, no summary, bot doesn't crash."""
        article = _make_article()
        msg = _make_message("https://example.com/test-article")
        placeholder = msg.answer.return_value

        with (
            patch("backend.bot.get_article_by_url", AsyncMock(return_value=None)),
            patch(
                "backend.bot.parse_article",
                AsyncMock(return_value=("<html>", article.title, article.blocks)),
            ),
            patch("backend.bot.save_article", AsyncMock()),
            patch(
                "backend.bot.settings", _mock_settings(deepseek_api_key="sk-test-key")
            ),
            patch(
                "backend.bot.summarize_article",
                AsyncMock(return_value=("", False, True)),
            ),
        ):
            await handle_message(msg)

        placeholder.edit_text.assert_awaited_once()
        call_args = placeholder.edit_text.call_args
        display_text = call_args[0][0]
        assert article.title in display_text
        assert "\n\n" not in display_text

        kwargs = call_args[1]
        assert kwargs["reply_markup"] is not None

    @pytest.mark.asyncio
    async def test_no_api_key_skips_summarization(self) -> None:
        article = _make_article()
        msg = _make_message("https://example.com/test-article")
        placeholder = msg.answer.return_value

        with (
            patch("backend.bot.get_article_by_url", AsyncMock(return_value=article)),
            patch("backend.bot.settings", _mock_settings(deepseek_api_key="")),
        ):
            await handle_message(msg)

        placeholder.edit_text.assert_awaited_once()
        call_args = placeholder.edit_text.call_args
        display_text = call_args[0][0]
        assert article.title in display_text
        assert "\n\n" not in display_text

        kwargs = call_args[1]
        assert kwargs["reply_markup"] is not None

    @pytest.mark.asyncio
    async def test_parse_error_fallback(self) -> None:
        """Parse failure: edit placeholder with error, bot doesn't crash."""
        from backend.parser import ParseError

        msg = _make_message("https://example.com/broken")
        placeholder = msg.answer.return_value

        with (
            patch("backend.bot.get_article_by_url", AsyncMock(return_value=None)),
            patch(
                "backend.bot.parse_article",
                AsyncMock(side_effect=ParseError("timeout")),
            ),
        ):
            await handle_message(msg)

        placeholder.edit_text.assert_awaited_once()
        error_text = placeholder.edit_text.call_args[0][0]
        assert "Failed to parse article" in error_text

    @pytest.mark.asyncio
    async def test_button_has_correct_text_and_url(self) -> None:
        article = _make_article()
        msg = _make_message("https://example.com/test-article")
        placeholder = msg.answer.return_value

        with (
            patch("backend.bot.get_article_by_url", AsyncMock(return_value=article)),
            patch("backend.bot.settings", _mock_settings()),
        ):
            await handle_message(msg)

        kwargs = placeholder.edit_text.call_args[1]
        keyboard = kwargs["reply_markup"]
        button = keyboard.inline_keyboard[0][0]
        assert "Читать полностью" in button.text
        assert f"/#/reader/{article.id}" in button.web_app.url

    @pytest.mark.asyncio
    async def test_url_trailing_punctuation_stripped(self) -> None:
        article = _make_article()
        msg = _make_message("https://example.com/test-article.")
        placeholder = msg.answer.return_value

        with (
            patch("backend.bot.get_article_by_url", AsyncMock(return_value=article)),
            patch("backend.bot.settings", _mock_settings()),
        ):
            await handle_message(msg)

        placeholder.edit_text.assert_awaited_once()
