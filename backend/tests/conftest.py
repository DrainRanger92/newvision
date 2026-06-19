"""
Shared fixtures and configuration for NewVision backend unit tests.
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio


# ── pytest-asyncio config ──────────────────────────────────────────────


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Automatically mark all async tests with pytest.mark.asyncio."""
    for item in items:
        if item.get_closest_marker("asyncio") is None:
            item.add_marker(pytest.mark.asyncio)


# ── Shared fixture: sample block data ──────────────────────────────────


@pytest.fixture
def sample_heading_html() -> str:
    return "<h2>Introduction</h2>"


@pytest.fixture
def sample_paragraph_html() -> str:
    return "<p>This is a <strong>test</strong> paragraph.</p>"


@pytest.fixture
def sample_code_html() -> str:
    return '<pre><code class="language-python">print("hello")</code></pre>'


@pytest.fixture
def sample_image_html() -> str:
    return '<img src="https://example.com/img.png" alt="Example"/>'


@pytest.fixture
def sample_list_html() -> str:
    return "<ul><li>Item one</li><li>Item two</li></ul>"


@pytest.fixture
def sample_ordered_list_html() -> str:
    return "<ol><li>First</li><li>Second</li></ol>"


@pytest.fixture
def sample_quote_html() -> str:
    return "<blockquote>To be or not to be</blockquote>"


@pytest.fixture
def sample_figure_with_image_html() -> str:
    return '<figure><img src="https://example.com/fig.png" alt="Figure"/></figure>'


@pytest.fixture
def sample_figure_with_code_html() -> str:
    return '<figure><pre><code class="language-javascript">const x = 1;</code></pre></figure>'


@pytest.fixture
def sample_full_article_html() -> str:
    """A realistic article HTML with mixed content."""
    return """
<html>
<head><title>Test Article</title></head>
<body>
<h1>My Article</h1>
<p>First paragraph with <a href="#">link</a>.</p>
<pre><code class="language-python">def hello():\n    print("world")</code></pre>
<img src="https://example.com/photo.jpg" alt="Photo"/>
<blockquote>Important quote</blockquote>
<ul><li>A</li><li>B</li></ul>
</body>
</html>
""".strip()


# ── Mock aiosqlite connection ─────────────────────────────────────────


@pytest_asyncio.fixture
async def mock_db() -> AsyncGenerator[MagicMock, None]:
    """Create a mock aiosqlite connection, patching both _db and aiqlite.connect."""
    import backend.db

    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.commit = AsyncMock()
    conn.close = AsyncMock()
    conn.row_factory = None

    # Patch aiosqlite.connect so init_db() returns the mock connection
    # (init_db creates its own connection via await aiosqlite.connect())
    original_connect = backend.db.aiosqlite.connect
    backend.db.aiosqlite.connect = AsyncMock(return_value=conn)

    # Also patch the global _db for tests that use it directly
    original_db = backend.db._db
    backend.db._db = conn

    yield conn

    backend.db._db = original_db
    backend.db.aiosqlite.connect = original_connect


@pytest_asyncio.fixture
async def mock_db_uninitialized() -> AsyncGenerator[None, None]:
    """Ensure _db is None to test uninitialized DB errors."""
    import backend.db

    original = backend.db._db
    backend.db._db = None
    yield
    backend.db._db = original


# ── Mock httpx client for fetch_html ──────────────────────────────────


@pytest.fixture
def mock_httpx_response() -> MagicMock:
    """Return a successful HTTP response mock."""
    resp = MagicMock()
    resp.status_code = 200
    resp.text = "<html><body><p>Hello</p></body></html>"
    resp.headers = {"content-type": "text/html; charset=utf-8"}
    resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture
def mock_httpx_client(mock_httpx_response: MagicMock) -> MagicMock:
    """Mock httpx.AsyncClient context manager."""
    client = MagicMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    # Use AsyncMock for get() so that await client.get(url) works (MagicMock
    # does not support __await__ in Python 3.11)
    client.get = AsyncMock(return_value=mock_httpx_response)
    return client


# ── Mock OpenAI (AsyncOpenAI) client for translator ───────────────────


@pytest.fixture
def mock_openai_message() -> MagicMock:
    """Mock a single chat completion choice message."""
    msg = MagicMock()
    msg.content = "Translated text"
    return msg


@pytest.fixture
def mock_openai_choice(mock_openai_message: MagicMock) -> MagicMock:
    """Mock a single chat completion choice."""
    choice = MagicMock()
    choice.message = mock_openai_message
    return choice


@pytest.fixture
def mock_openai_response(mock_openai_choice: MagicMock) -> MagicMock:
    """Mock the full chat completion response."""
    resp = MagicMock()
    resp.choices = [mock_openai_choice]
    return resp


@pytest_asyncio.fixture
async def mock_openai_client(mock_openai_response: MagicMock) -> AsyncGenerator[MagicMock, None]:
    """Patch AsyncOpenAI so translate calls don't hit the real API."""
    import backend.translator

    original = backend.translator.AsyncOpenAI

    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=mock_openai_response)

    def _fake_init(*args: object, **kwargs: object) -> MagicMock:
        return client

    backend.translator.AsyncOpenAI = _fake_init  # type: ignore[misc]

    yield client

    backend.translator.AsyncOpenAI = original
