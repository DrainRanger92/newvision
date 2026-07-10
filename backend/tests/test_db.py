"""
Tests for backend/db.py — SQLite persistence with mocked aiosqlite.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models import Article, ParagraphBlock


class TestInitDb:
    """Database initialisation."""

    @pytest.mark.asyncio
    async def test_creates_tables_and_indexes(self, mock_db: MagicMock) -> None:
        """init_db should execute CREATE TABLE and CREATE INDEX statements."""
        import backend.db

        # Mock the path.mkdir so we don't create real dirs
        with patch("backend.db.Path.mkdir"):
            await backend.db.init_db(":memory:")

        # Verify execute was called for tables + indexes (4 SQL statements)
        assert mock_db.execute.call_count >= 4
        # Verify commit was called
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_creates_data_directory(self, mock_db: MagicMock) -> None:
        """init_db should create parent directories."""
        import backend.db

        with patch("backend.db.Path.mkdir") as mock_mkdir:
            await backend.db.init_db("/tmp/test/db.sqlite")
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


class TestGetArticleByUrl:
    """Retrieve article by URL."""

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, mock_db: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchone = AsyncMock(return_value=None)
        mock_db.execute.return_value = cursor

        import backend.db

        result = await backend.db.get_article_by_url("https://example.com/a")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_article_when_found(self, mock_db: MagicMock) -> None:
        row = MagicMock()
        row.__getitem__.side_effect = lambda k: {
            "id": "abc-123",
            "url": "https://example.com/a",
            "title": "Test",
            "blocks_json": '[{"type":"paragraph","content":"Hello"}]',
            "fetched_at": "2025-01-01T00:00:00+00:00",
        }[k]

        cursor = MagicMock()
        cursor.fetchone = AsyncMock(return_value=row)
        mock_db.execute.return_value = cursor

        import backend.db

        result = await backend.db.get_article_by_url("https://example.com/a")
        assert result is not None
        assert result.id == "abc-123"
        assert result.url == "https://example.com/a"
        assert result.title == "Test"
        assert len(result.blocks) == 1


class TestGetArticleById:
    """Retrieve article by ID."""

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, mock_db: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchone = AsyncMock(return_value=None)
        mock_db.execute.return_value = cursor

        import backend.db

        result = await backend.db.get_article_by_id("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_executes_correct_query(self, mock_db: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchone = AsyncMock(return_value=None)
        mock_db.execute.return_value = cursor

        import backend.db

        await backend.db.get_article_by_id("abc-123")
        mock_db.execute.assert_called_with(
            "SELECT * FROM articles WHERE id = ?", ("abc-123",)
        )


class TestSaveArticle:
    """Persist article to database."""

    @pytest.mark.asyncio
    async def test_inserts_article(self, mock_db: MagicMock) -> None:
        article = Article(
            id="abc-123",
            url="https://example.com/a",
            title="Test",
            blocks=[ParagraphBlock(content="Hello")],
            fetched_at=datetime(2025, 1, 1, tzinfo=UTC),
        )

        import backend.db

        await backend.db.save_article(article, "<html></html>")

        # Verify execute was called with INSERT OR REPLACE
        assert mock_db.execute.called
        call_args = mock_db.execute.call_args[0][0]
        assert "INSERT OR REPLACE" in call_args
        assert "articles" in call_args
        mock_db.commit.assert_awaited_once()


class TestGetTranslation:
    """Retrieve cached translation."""

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, mock_db: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchone = AsyncMock(return_value=None)
        mock_db.execute.return_value = cursor

        import backend.db

        result = await backend.db.get_translation("a", 0)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_hash_mismatch(self, mock_db: MagicMock) -> None:
        row = MagicMock()
        row.__getitem__.side_effect = lambda k: {
            "text_hash": "oldhash123",
            "translated_text": "Old translation",
        }[k]

        cursor = MagicMock()
        cursor.fetchone = AsyncMock(return_value=row)
        mock_db.execute.return_value = cursor

        import backend.db

        result = await backend.db.get_translation("a", 0, "newhash999")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_translated_text(self, mock_db: MagicMock) -> None:
        row = MagicMock()
        row.__getitem__.side_effect = lambda k: {
            "text_hash": "abc123",
            "translated_text": "Hello",
        }[k]

        cursor = MagicMock()
        cursor.fetchone = AsyncMock(return_value=row)
        mock_db.execute.return_value = cursor

        import backend.db

        result = await backend.db.get_translation("a", 0, "abc123")
        assert result == "Hello"

    @pytest.mark.asyncio
    async def test_returns_translated_without_hash_check(self, mock_db: MagicMock) -> None:
        row = MagicMock()
        row.__getitem__.side_effect = lambda k: {
            "text_hash": "any",
            "translated_text": "Hi",
        }[k]

        cursor = MagicMock()
        cursor.fetchone = AsyncMock(return_value=row)
        mock_db.execute.return_value = cursor

        import backend.db

        result = await backend.db.get_translation("a", 0)
        assert result == "Hi"


class TestSaveTranslation:
    """Persist translation to database."""

    @pytest.mark.asyncio
    async def test_saves_translation(self, mock_db: MagicMock) -> None:
        import backend.db

        await backend.db.save_translation(
            "a", 0, "original", "translated", "deepseek-chat"
        )

        assert mock_db.execute.called
        call_args = mock_db.execute.call_args[0][0]
        assert "INSERT OR REPLACE" in call_args
        assert "translations" in call_args
        mock_db.commit.assert_awaited_once()


class TestGetSummary:
    """Retrieve cached summary."""

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, mock_db: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchone = AsyncMock(return_value=None)
        mock_db.execute.return_value = cursor

        import backend.db

        result = await backend.db.get_summary("article-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_summary_when_found(self, mock_db: MagicMock) -> None:
        row = MagicMock()
        row.__getitem__.side_effect = lambda k: {
            "summary": "This is a summary of the article.",
        }[k]

        cursor = MagicMock()
        cursor.fetchone = AsyncMock(return_value=row)
        mock_db.execute.return_value = cursor

        import backend.db

        result = await backend.db.get_summary("article-1")
        assert result == "This is a summary of the article."

    @pytest.mark.asyncio
    async def test_executes_correct_query(self, mock_db: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchone = AsyncMock(return_value=None)
        mock_db.execute.return_value = cursor

        import backend.db

        await backend.db.get_summary("article-1")
        mock_db.execute.assert_called_with(
            "SELECT summary FROM summaries WHERE article_id = ?",
            ("article-1",),
        )


class TestSaveSummary:
    """Persist summary to database."""

    @pytest.mark.asyncio
    async def test_saves_summary(self, mock_db: MagicMock) -> None:
        import backend.db

        await backend.db.save_summary("article-1", "Summary text", "deepseek-chat")

        assert mock_db.execute.called
        call_args = mock_db.execute.call_args[0][0]
        assert "INSERT OR REPLACE" in call_args
        assert "summaries" in call_args
        mock_db.commit.assert_awaited_once()


class TestGetTranslationsBatch:
    """Batch fetch translations."""

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_indices(self, mock_db: MagicMock) -> None:
        import backend.db

        result = await backend.db.get_translations_batch("a", [])
        assert result == {}
        # execute should not be called
        assert not mock_db.execute.called

    @pytest.mark.asyncio
    async def test_returns_mapping(self, mock_db: MagicMock) -> None:
        row_0 = MagicMock()
        row_0.__getitem__.side_effect = lambda k: {
            "block_index": 0,
            "translated_text": "T0",
        }[k]

        row_2 = MagicMock()
        row_2.__getitem__.side_effect = lambda k: {
            "block_index": 2,
            "translated_text": "T2",
        }[k]

        cursor = MagicMock()
        cursor.fetchall = AsyncMock(return_value=[row_0, row_2])
        mock_db.execute.return_value = cursor

        import backend.db

        result = await backend.db.get_translations_batch("a", [0, 1, 2])
        assert result == {0: "T0", 2: "T2"}


class TestCloseDb:
    """Graceful shutdown."""

    @pytest.mark.asyncio
    async def test_closes_connection(self, mock_db: MagicMock) -> None:
        import backend.db

        await backend.db.close_db()
        mock_db.close.assert_awaited_once()
        assert backend.db._db is None


class TestUninitializedDbErrors:
    """All operations raise RuntimeError when _db is None."""

    @pytest.mark.asyncio
    async def test_get_article_by_url_raises(self, mock_db_uninitialized: None) -> None:
        import backend.db

        with pytest.raises(RuntimeError, match="not initialized"):
            await backend.db.get_article_by_url("https://example.com/a")

    @pytest.mark.asyncio
    async def test_get_article_by_id_raises(self, mock_db_uninitialized: None) -> None:
        import backend.db

        with pytest.raises(RuntimeError, match="not initialized"):
            await backend.db.get_article_by_id("abc")

    @pytest.mark.asyncio
    async def test_save_article_raises(self, mock_db_uninitialized: None) -> None:
        import backend.db
        from backend.models import Article

        article = Article(url="https://example.com/a", title="T")
        with pytest.raises(RuntimeError, match="not initialized"):
            await backend.db.save_article(article, "<html></html>")

    @pytest.mark.asyncio
    async def test_get_translation_raises(self, mock_db_uninitialized: None) -> None:
        import backend.db

        with pytest.raises(RuntimeError, match="not initialized"):
            await backend.db.get_translation("a", 0)

    @pytest.mark.asyncio
    async def test_save_translation_raises(self, mock_db_uninitialized: None) -> None:
        import backend.db

        with pytest.raises(RuntimeError, match="not initialized"):
            await backend.db.save_translation("a", 0, "orig", "trans", "model")

    @pytest.mark.asyncio
    async def test_get_translations_batch_raises(self, mock_db_uninitialized: None) -> None:
        import backend.db

        with pytest.raises(RuntimeError, match="not initialized"):
            await backend.db.get_translations_batch("a", [0])

    @pytest.mark.asyncio
    async def test_get_summary_raises(self, mock_db_uninitialized: None) -> None:
        import backend.db

        with pytest.raises(RuntimeError, match="not initialized"):
            await backend.db.get_summary("article-1")

    @pytest.mark.asyncio
    async def test_save_summary_raises(self, mock_db_uninitialized: None) -> None:
        import backend.db

        with pytest.raises(RuntimeError, match="not initialized"):
            await backend.db.save_summary("article-1", "summary", "model")


class TestRowToArticle:
    """Internal _row_to_article helper."""

    def test_converts_row_to_article(self) -> None:
        """Verify that _row_to_article parses blocks_json and builds Article correctly."""
        from backend.db import _row_to_article

        row = MagicMock(spec=dict)
        row.__getitem__.side_effect = lambda k: {
            "id": "id-1",
            "url": "https://example.com",
            "title": "Title",
            "blocks_json": '[{"type":"paragraph","content":"Test"}]',
            "fetched_at": "2025-06-01T12:00:00+00:00",
        }[k]

        article = _row_to_article(row)
        assert article.id == "id-1"
        assert article.url == "https://example.com"
        assert article.title == "Title"
        assert len(article.blocks) == 1
        assert isinstance(article.blocks[0], ParagraphBlock)
        assert article.blocks[0].content == "Test"
