"""
Tests for backend/summarizer.py — summarize_article with mocked OpenAI and DB.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models import Article, ParagraphBlock
from backend.summarizer import summarize_article


@pytest.fixture
def mock_summarizer_openai() -> MagicMock:
    """Patch AsyncOpenAI in summarizer so calls don't hit the real API."""
    import backend.summarizer

    original = backend.summarizer.AsyncOpenAI

    msg = MagicMock()
    msg.content = "Mock summary in Russian."
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]

    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=resp)

    backend.summarizer.AsyncOpenAI = lambda *a, **kw: client  # type: ignore[assignment]

    yield client

    backend.summarizer.AsyncOpenAI = original


@pytest.fixture
def sample_article() -> Article:
    return Article(
        id="test-123",
        url="https://example.com/article",
        title="Test Article",
        blocks=[ParagraphBlock(content="First block."), ParagraphBlock(content="Second block.")],
    )


class TestSummarizeArticle:
    """summarize_article with mocked OpenAI and DB."""

    @pytest.mark.asyncio
    async def test_cache_hit(self, mock_summarizer_openai: MagicMock) -> None:
        with patch("backend.db.get_summary", AsyncMock(return_value="Cached summary.")):
            summary, cached, error = await summarize_article("test-123", "sk-test")

        assert summary == "Cached summary."
        assert cached is True
        assert error is False
        assert not mock_summarizer_openai.chat.completions.create.called

    @pytest.mark.asyncio
    async def test_cache_miss_calls_api(
        self, mock_summarizer_openai: MagicMock, sample_article: Article
    ) -> None:
        with (
            patch("backend.db.get_summary", AsyncMock(return_value=None)),
            patch("backend.db.get_article_by_id", AsyncMock(return_value=sample_article)),
            patch("backend.db.save_summary", AsyncMock()),
        ):
            summary, cached, error = await summarize_article("test-123", "sk-test")

        assert summary == "Mock summary in Russian."
        assert cached is False
        assert error is False

    @pytest.mark.asyncio
    async def test_deepseek_error_returns_error(
        self, mock_summarizer_openai: MagicMock, sample_article: Article
    ) -> None:
        mock_summarizer_openai.chat.completions.create = AsyncMock(
            side_effect=Exception("API error")
        )

        with (
            patch("backend.db.get_summary", AsyncMock(return_value=None)),
            patch("backend.db.get_article_by_id", AsyncMock(return_value=sample_article)),
            patch("backend.db.save_summary", AsyncMock()),
            patch("backend.summarizer.logevent") as mock_log,
        ):
            summary, cached, error = await summarize_article("test-123", "sk-test")

        assert summary == ""
        assert cached is False
        assert error is True
        mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_article_not_found(self, mock_summarizer_openai: MagicMock) -> None:
        with (
            patch("backend.db.get_summary", AsyncMock(return_value=None)),
            patch("backend.db.get_article_by_id", AsyncMock(return_value=None)),
        ):
            summary, cached, error = await summarize_article("nonexistent", "sk-test")

        assert summary == ""
        assert cached is False
        assert error is True

    @pytest.mark.asyncio
    async def test_cache_hit_no_api_call(self, mock_summarizer_openai: MagicMock) -> None:
        with patch("backend.db.get_summary", AsyncMock(return_value="Cached.")):
            summary, cached, error = await summarize_article("test-123", "sk-test")

        assert cached is True
        assert not mock_summarizer_openai.chat.completions.create.called
