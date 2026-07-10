"""
Tests for backend/main.py — FastAPI endpoints: /health, /api/summarize.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import Article


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def mock_article() -> Mock:
    return Mock(spec=Article, id="test-123")


class TestHealth:
    def test_health_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestSummarize:
    ENDPOINT = "/api/summarize"

    def test_summarize_cached(
        self, client: TestClient, mock_article: Mock,
    ) -> None:
        with (
            patch("backend.main.get_article_by_id", AsyncMock(return_value=mock_article)),
            patch(
                "backend.main.summarize_article",
                AsyncMock(return_value=("Cached summary.", True, False)),
            ),
        ):
            resp = client.post(self.ENDPOINT, json={"article_id": "test-123"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["article_id"] == "test-123"
        assert data["summary"] == "Cached summary."
        assert data["cached"] is True
        assert data["error"] is False

    def test_summarize_fresh(
        self, client: TestClient, mock_article: Mock,
    ) -> None:
        with (
            patch("backend.main.get_article_by_id", AsyncMock(return_value=mock_article)),
            patch(
                "backend.main.summarize_article",
                AsyncMock(return_value=("Fresh summary.", False, False)),
            ),
        ):
            resp = client.post(self.ENDPOINT, json={"article_id": "test-456"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["article_id"] == "test-456"
        assert data["summary"] == "Fresh summary."
        assert data["cached"] is False
        assert data["error"] is False

    def test_summarize_not_found(
        self, client: TestClient,
    ) -> None:
        with patch("backend.main.get_article_by_id", AsyncMock(return_value=None)):
            resp = client.post(self.ENDPOINT, json={"article_id": "nonexistent"})

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Article not found"

    def test_summarize_service_unavailable(
        self, client: TestClient, mock_article: Mock,
    ) -> None:
        with (
            patch("backend.main.get_article_by_id", AsyncMock(return_value=mock_article)),
            patch(
                "backend.main.summarize_article",
                AsyncMock(return_value=("", False, True)),
            ),
        ):
            resp = client.post(self.ENDPOINT, json={"article_id": "test-789"})

        assert resp.status_code == 503
        assert resp.json()["detail"] == "Summarization service unavailable"
