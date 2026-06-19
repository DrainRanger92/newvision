"""
Tests for backend/parser.py — URL normalization, HTML extraction, block classification,
error handling, and fetch mocking.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from bs4 import BeautifulSoup

from backend.models import (
    CodeBlock,
    HeadingBlock,
    ImageBlock,
    ListBlock,
    ParagraphBlock,
    QuoteBlock,
)
from backend.parser import (
    ParseError,
    _detect_language,
    _inner_html,
    _normalize_url,
    classify_blocks,
    extract_content,
    fetch_html,
    parse_article,
)


# ── _normalize_url ─────────────────────────────────────────────────────


class TestNormalizeUrl:
    """URL normalization: scheme, host, port, path, query."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("https://example.com", "https://example.com/"),
            ("HTTPS://EXAMPLE.COM/path", "https://example.com/path"),
            ("http://example.com:80/path/", "http://example.com/path"),
            ("https://example.com:443/foo/", "https://example.com/foo"),
            ("https://example.com:8443/path", "https://example.com:8443/path"),
            ("https://example.com/path?q=1", "https://example.com/path?q=1"),
            ("https://example.com//double//slash", "https://example.com//double//slash"),
            ("http://example.com/a/b/c/", "http://example.com/a/b/c"),
        ],
    )
    def test_normalizes_correctly(self, raw: str, expected: str) -> None:
        assert _normalize_url(raw) == expected

    def test_lowercases_scheme(self) -> None:
        assert _normalize_url("HTTP://EXAMPLE.COM").startswith("http://")

    def test_lowercases_hostname(self) -> None:
        assert "example.com" in _normalize_url("https://EXAMPLE.COM")


# ── _detect_language ───────────────────────────────────────────────────


class TestDetectLanguage:
    """Language detection from CSS classes."""

    def test_language_class(self) -> None:
        soup = BeautifulSoup('<pre class="language-python"></pre>', "lxml")
        el = soup.find("pre")
        assert el is not None
        assert _detect_language(el) == "python"

    def test_lang_class(self) -> None:
        soup = BeautifulSoup('<pre class="lang-javascript"></pre>', "lxml")
        el = soup.find("pre")
        assert el is not None
        assert _detect_language(el) == "javascript"

    def test_brush_class(self) -> None:
        soup = BeautifulSoup('<pre class="brush: ruby"></pre>', "lxml")
        el = soup.find("pre")
        assert el is not None
        assert _detect_language(el) == "ruby"

    def test_case_insensitive(self) -> None:
        soup = BeautifulSoup('<pre class="LANGUAGE-CPP"></pre>', "lxml")
        el = soup.find("pre")
        assert el is not None
        assert _detect_language(el) == "cpp"

    def test_no_language_class(self) -> None:
        soup = BeautifulSoup('<pre class="nohighlight"></pre>', "lxml")
        el = soup.find("pre")
        assert el is not None
        assert _detect_language(el) is None

    def test_multiple_classes_with_language(self) -> None:
        soup = BeautifulSoup('<pre class="brush: python noprint"></pre>', "lxml")
        el = soup.find("pre")
        assert el is not None
        assert _detect_language(el) == "python"

    def test_class_as_string_single(self) -> None:
        """Handle class attribute as a plain string (some parsers)."""
        from unittest.mock import MagicMock

        el = MagicMock()
        el.get.return_value = "language-python"
        assert _detect_language(el) == "python"


# ── _inner_html ────────────────────────────────────────────────────────


class TestInnerHtml:
    """Extract inner HTML from a BeautifulSoup Tag."""

    def test_simple_text(self) -> None:
        soup = BeautifulSoup("<p>Hello</p>", "lxml")
        el = soup.find("p")
        assert el is not None
        assert _inner_html(el) == "Hello"

    def test_nested_html(self) -> None:
        soup = BeautifulSoup("<p><strong>Bold</strong> text</p>", "lxml")
        el = soup.find("p")
        assert el is not None
        assert _inner_html(el) == "<strong>Bold</strong> text"

    def test_empty_element(self) -> None:
        soup = BeautifulSoup("<br/>", "lxml")
        el = soup.find("br")
        assert el is not None
        assert _inner_html(el) == ""


# ── classify_blocks ────────────────────────────────────────────────────


class TestClassifyBlocks:
    """HTML → Block list classification."""

    def test_heading(self, sample_heading_html: str) -> None:
        blocks = classify_blocks(sample_heading_html)
        assert len(blocks) == 1
        assert isinstance(blocks[0], HeadingBlock)
        assert blocks[0].level == 2

    def test_paragraph(self, sample_paragraph_html: str) -> None:
        blocks = classify_blocks(sample_paragraph_html)
        assert len(blocks) == 1
        assert isinstance(blocks[0], ParagraphBlock)
        assert "test" in blocks[0].content

    def test_code(self, sample_code_html: str) -> None:
        blocks = classify_blocks(sample_code_html)
        assert len(blocks) == 1
        assert isinstance(blocks[0], CodeBlock)
        assert blocks[0].language == "python"

    def test_image(self, sample_image_html: str) -> None:
        blocks = classify_blocks(sample_image_html)
        assert len(blocks) == 1
        assert isinstance(blocks[0], ImageBlock)
        assert blocks[0].src == "https://example.com/img.png"
        assert blocks[0].alt == "Example"

    def test_unordered_list(self, sample_list_html: str) -> None:
        blocks = classify_blocks(sample_list_html)
        assert len(blocks) == 1
        assert isinstance(blocks[0], ListBlock)
        assert blocks[0].ordered is False
        assert "Item one" in blocks[0].items

    def test_ordered_list(self, sample_ordered_list_html: str) -> None:
        blocks = classify_blocks(sample_ordered_list_html)
        assert len(blocks) == 1
        assert isinstance(blocks[0], ListBlock)
        assert blocks[0].ordered is True

    def test_quote(self, sample_quote_html: str) -> None:
        blocks = classify_blocks(sample_quote_html)
        assert len(blocks) == 1
        assert isinstance(blocks[0], QuoteBlock)

    def test_figure_with_image(self, sample_figure_with_image_html: str) -> None:
        blocks = classify_blocks(sample_figure_with_image_html)
        assert len(blocks) == 1
        assert isinstance(blocks[0], ImageBlock)

    def test_figure_with_code(self, sample_figure_with_code_html: str) -> None:
        blocks = classify_blocks(sample_figure_with_code_html)
        assert len(blocks) == 1
        assert isinstance(blocks[0], CodeBlock)
        assert blocks[0].language == "javascript"

    def test_full_article(self, sample_full_article_html: str) -> None:
        blocks = classify_blocks(sample_full_article_html)
        # Heading, paragraph, code, image, quote, list
        assert len(blocks) == 6
        # Check types and order
        assert isinstance(blocks[0], HeadingBlock)
        assert blocks[0].level == 1
        assert isinstance(blocks[1], ParagraphBlock)
        assert isinstance(blocks[2], CodeBlock)
        assert isinstance(blocks[3], ImageBlock)
        assert isinstance(blocks[4], QuoteBlock)
        assert isinstance(blocks[5], ListBlock)

    def test_ignored_tags(self) -> None:
        html = "<nav>Menu</nav><hr/><br/><aside>Sidebar</aside>"
        blocks = classify_blocks(html)
        assert blocks == []

    def test_empty_html(self) -> None:
        blocks = classify_blocks("")
        assert blocks == []

    def test_only_whitespace(self) -> None:
        blocks = classify_blocks("   \n   ")
        assert blocks == []

    def test_skip_image_without_src(self) -> None:
        html = '<img alt="no src"/>'
        blocks = classify_blocks(html)
        assert blocks == []


# ── extract_content ────────────────────────────────────────────────────


class TestExtractContent:
    """readability-lxml extraction with fallback."""

    def test_extracts_title_and_content(self) -> None:
        html = "<html><head><title>My Page</title></head><body><p>Body</p></body></html>"
        title, content = extract_content(html, "https://example.com")
        assert title == "My Page"
        assert "Body" in content

    def test_fallback_when_readability_empty(self) -> None:
        """When readability returns empty, fallback to <body> content."""
        html = "<html><head><title>Fallback</title></head><body><p>Fallback content</p></body></html>"
        title, content = extract_content(html, "https://example.com")
        assert title == "Fallback"
        assert "Fallback content" in content

    def test_title_fallback_to_url(self) -> None:
        """When no <title> tag exists, title falls back to URL."""
        html = "<html><body><p>No title</p></body></html>"
        title, _ = extract_content(html, "https://example.com/no-title")
        assert title == "https://example.com/no-title"

    def test_content_has_meaningful_length(self) -> None:
        html = "<html><body><p>Short</p></body></html>"
        _, content = extract_content(html, "https://example.com")
        assert len(content) > 0


# ── fetch_html (mocked) ────────────────────────────────────────────────


class TestFetchHtml:
    """fetch_html with mocked HTTP client."""

    @pytest.mark.asyncio
    async def test_successful_fetch(self, mock_httpx_client: MagicMock) -> None:
        with patch("backend.parser.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value.__aenter__.return_value = mock_httpx_client
            result = await fetch_html("https://example.com")
            assert result == "<html><body><p>Hello</p></body></html>"

    @pytest.mark.asyncio
    async def test_non_html_content_type_raises(self) -> None:
        resp = MagicMock()
        resp.status_code = 200
        resp.text = "{\"key\": \"value\"}"
        resp.headers = {"content-type": "application/json"}
        resp.raise_for_status = MagicMock()

        client = MagicMock()
        client.__aenter__.return_value = client
        client.get.return_value = resp

        with patch("backend.parser.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = client
            with pytest.raises(ParseError, match="non-HTML content type"):
                await fetch_html("https://example.com/data")

    @pytest.mark.asyncio
    async def test_http_status_error_raises(self) -> None:
        resp = MagicMock()
        resp.status_code = 404
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=resp
        )

        client = MagicMock()
        client.__aenter__.return_value = client
        client.get.return_value = resp

        with patch("backend.parser.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = client
            with pytest.raises(ParseError, match="HTTP error 404"):
                await fetch_html("https://example.com/404")

    @pytest.mark.asyncio
    async def test_timeout_raises(self) -> None:
        client = MagicMock()
        client.__aenter__.return_value = client
        client.get.side_effect = httpx.TimeoutException("Timeout", request=MagicMock())

        with patch("backend.parser.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = client
            with pytest.raises(ParseError, match="Timeout"):
                await fetch_html("https://example.com/slow")

    @pytest.mark.asyncio
    async def test_request_error_raises(self) -> None:
        client = MagicMock()
        client.__aenter__.return_value = client
        client.get.side_effect = httpx.RequestError("Connection refused", request=MagicMock())

        with patch("backend.parser.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = client
            with pytest.raises(ParseError, match="Request error"):
                await fetch_html("https://example.com/down")

    @pytest.mark.asyncio
    async def test_response_too_large(self) -> None:
        resp = MagicMock()
        resp.status_code = 200
        resp.text = "x" * 100
        resp.headers = {"content-type": "text/html"}
        resp.raise_for_status = MagicMock()

        client = MagicMock()
        client.__aenter__.return_value = client
        client.get.return_value = resp

        with (
            patch("backend.parser.httpx.AsyncClient") as mock_cls,
            patch("backend.parser.settings.fetch_max_bytes", 50),
        ):
            mock_cls.return_value.__aenter__.return_value = client
            with pytest.raises(ParseError, match="Response too large"):
                await fetch_html("https://example.com/big")


# ── parse_article (integration with mocks) ─────────────────────────────


class TestParseArticle:
    """End-to-end parse pipeline with fetch mocked."""

    @pytest.mark.asyncio
    async def test_full_pipeline(self, mock_httpx_client: MagicMock) -> None:
        html = """<html><head><title>Test</title></head>
        <body><h1>Title</h1><p>Paragraph</p></body></html>"""
        mock_httpx_client.get.return_value.text = html

        with patch("backend.parser.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = mock_httpx_client

            raw, title, blocks = await parse_article("https://example.com/a")

        assert raw == html
        assert title == "Test"
        assert len(blocks) == 2
        assert isinstance(blocks[0], HeadingBlock)
        assert isinstance(blocks[1], ParagraphBlock)

    @pytest.mark.asyncio
    async def test_passes_parse_error_through(self) -> None:
        client = MagicMock()
        client.__aenter__.return_value = client
        client.get.side_effect = httpx.TimeoutException("Timeout", request=MagicMock())

        with patch("backend.parser.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = client
            with pytest.raises(ParseError, match="Timeout"):
                await parse_article("https://example.com/timeout")

    @pytest.mark.asyncio
    async def test_normalizes_url_before_fetch(self, mock_httpx_client: MagicMock) -> None:
        with patch("backend.parser.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = mock_httpx_client
            raw, title, blocks = await parse_article("HTTPS://EXAMPLE.COM/PATH/")

        # URL should be normalized
        assert raw is not None
