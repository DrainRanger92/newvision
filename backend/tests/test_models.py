"""
Tests for backend/models.py — Pydantic domain models, Block discriminated union, validation.
"""

import re
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.models import (
    Article,
    BatchTranslateRequest,
    BatchTranslateResponse,
    Block,
    BlockType,
    CodeBlock,
    HeadingBlock,
    ImageBlock,
    ListBlock,
    ParagraphBlock,
    ParseRequest,
    QuoteBlock,
    TranslateRequest,
    TranslateResponse,
    _generate_uuid,
)


# ── BlockType enum ─────────────────────────────────────────────────────


class TestBlockType:
    """BlockType StrEnum values."""

    def test_values_are_correct_strings(self) -> None:
        assert BlockType.heading == "heading"
        assert BlockType.paragraph == "paragraph"
        assert BlockType.code == "code"
        assert BlockType.image == "image"
        assert BlockType.list == "list"
        assert BlockType.quote == "quote"

    def test_all_members_accounted(self) -> None:
        expected = {"heading", "paragraph", "code", "image", "list", "quote"}
        assert {m.value for m in BlockType} == expected


# ── HeadingBlock ───────────────────────────────────────────────────────


class TestHeadingBlock:
    """HeadingBlock: level validation (1-6)."""

    @pytest.mark.parametrize("valid_level", [1, 2, 3, 4, 5, 6])
    def test_valid_level_accepted(self, valid_level: int) -> None:
        block = HeadingBlock(level=valid_level, content="Title")
        assert block.level == valid_level
        assert block.content == "Title"
        assert block.type is BlockType.heading

    @pytest.mark.parametrize("invalid_level", [0, -1, 7, 100])
    def test_invalid_level_raises(self, invalid_level: int) -> None:
        with pytest.raises(ValidationError):
            HeadingBlock(level=invalid_level, content="Bad")

    def test_default_type_is_heading(self) -> None:
        block = HeadingBlock(level=1, content="X")
        assert block.type == BlockType.heading
        assert block.type.value == "heading"

    def test_content_can_contain_html(self) -> None:
        block = HeadingBlock(level=2, content="<em>Hello</em>")
        assert block.content == "<em>Hello</em>"


# ── ParagraphBlock ─────────────────────────────────────────────────────


class TestParagraphBlock:
    """ParagraphBlock: content only."""

    def test_basic_paragraph(self) -> None:
        block = ParagraphBlock(content="Hello world")
        assert block.content == "Hello world"
        assert block.type is BlockType.paragraph

    def test_empty_content_allowed(self) -> None:
        # Pydantic allows empty strings unless constrained
        block = ParagraphBlock(content="")
        assert block.content == ""


# ── CodeBlock ──────────────────────────────────────────────────────────


class TestCodeBlock:
    """CodeBlock: content + optional language."""

    def test_with_language(self) -> None:
        block = CodeBlock(content="print('hi')", language="python")
        assert block.content == "print('hi')"
        assert block.language == "python"
        assert block.type is BlockType.code

    def test_without_language(self) -> None:
        block = CodeBlock(content="some code")
        assert block.language is None


# ── ImageBlock ─────────────────────────────────────────────────────────


class TestImageBlock:
    """ImageBlock: src + optional alt."""

    def test_with_src_only(self) -> None:
        block = ImageBlock(src="https://example.com/img.png")
        assert block.src == "https://example.com/img.png"
        assert block.alt == ""

    def test_with_src_and_alt(self) -> None:
        block = ImageBlock(src="/photo.jpg", alt="Sunset")
        assert block.src == "/photo.jpg"
        assert block.alt == "Sunset"


# ── ListBlock ──────────────────────────────────────────────────────────


class TestListBlock:
    """ListBlock: items + ordered flag."""

    def test_unordered_list(self) -> None:
        block = ListBlock(items=["A", "B"], ordered=False)
        assert block.items == ["A", "B"]
        assert block.ordered is False

    def test_ordered_list(self) -> None:
        block = ListBlock(items=["1", "2"], ordered=True)
        assert block.ordered is True

    def test_empty_items_allowed(self) -> None:
        block = ListBlock(items=[], ordered=False)
        assert block.items == []


# ── QuoteBlock ─────────────────────────────────────────────────────────


class TestQuoteBlock:
    """QuoteBlock: content string."""

    def test_quote(self) -> None:
        block = QuoteBlock(content="A wise saying")
        assert block.content == "A wise saying"
        assert block.type is BlockType.quote


# ── Block discriminated union ─────────────────────────────────────────-


class TestBlockDiscriminatedUnion:
    """The Block type alias correctly resolves to the right concrete type."""

    @pytest.mark.parametrize(
        ("data", "expected_type"),
        [
            ({"type": "heading", "level": 1, "content": "H"}, HeadingBlock),
            ({"type": "paragraph", "content": "P"}, ParagraphBlock),
            ({"type": "code", "content": "c"}, CodeBlock),
            ({"type": "image", "src": "s"}, ImageBlock),
            ({"type": "list", "items": ["a"], "ordered": False}, ListBlock),
            ({"type": "quote", "content": "q"}, QuoteBlock),
        ],
    )
    def test_construct_via_type_field(
        self, data: dict, expected_type: type[Block]
    ) -> None:
        block = expected_type(**data)
        assert isinstance(block, expected_type)
        assert block.type.value == data["type"]


# ── _generate_uuid helper ──────────────────────────────────────────────


class TestGenerateUUID:
    """_generate_uuid returns valid UUIDs."""

    def test_returns_string(self) -> None:
        uid = _generate_uuid()
        assert isinstance(uid, str)

    def test_valid_uuid_format(self) -> None:
        uid = _generate_uuid()
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", uid
        )

    def test_unique(self) -> None:
        ids = {_generate_uuid() for _ in range(100)}
        assert len(ids) == 100


# ── Article ────────────────────────────────────────────────────────────


class TestArticle:
    """Article model: auto-ID, auto-timestamp, block storage."""

    def test_generates_id_on_post_init(self) -> None:
        article = Article(url="https://example.com/a", title="A")
        assert article.id != ""
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            article.id,
        )

    def test_preserves_explicit_id(self) -> None:
        article = Article(id="my-id", url="https://example.com/a", title="A")
        assert article.id == "my-id"

    def test_sets_fetched_at_on_post_init(self) -> None:
        before = datetime.now(UTC)
        article = Article(url="https://example.com/a", title="A")
        after = datetime.now(UTC)
        assert article.fetched_at is not None
        assert before <= article.fetched_at <= after

    def test_preserves_explicit_fetched_at(self) -> None:
        dt = datetime(2025, 1, 1, tzinfo=UTC)
        article = Article(url="https://example.com/a", title="A", fetched_at=dt)
        assert article.fetched_at == dt

    def test_default_blocks_empty(self) -> None:
        article = Article(url="https://example.com/a", title="A")
        assert article.blocks == []

    def test_accepts_blocks(self) -> None:
        blocks = [ParagraphBlock(content="P1"), HeadingBlock(level=2, content="H2")]
        article = Article(url="https://example.com/a", title="A", blocks=blocks)
        assert len(article.blocks) == 2
        assert isinstance(article.blocks[0], ParagraphBlock)
        assert isinstance(article.blocks[1], HeadingBlock)

    def test_url_required(self) -> None:
        with pytest.raises(ValidationError):
            Article(title="No URL")  # type: ignore[call-arg]

    def test_title_required(self) -> None:
        with pytest.raises(ValidationError):
            Article(url="https://example.com/a")  # type: ignore[call-arg]


# ── Request/Response models ────────────────────────────────────────────


class TestParseRequest:
    """ParseRequest: URL must be valid HTTP URL."""

    def test_valid_url(self) -> None:
        req = ParseRequest(url="https://example.com/article")
        assert str(req.url) == "https://example.com/article/"

    def test_invalid_url_raises(self) -> None:
        with pytest.raises(ValidationError):
            ParseRequest(url="not-a-url")


class TestArticleResponse:
    """ArticleResponse: mirrors Article but requires fetched_at."""

    def test_basic(self) -> None:
        resp = ArticleResponse(
            id="abc",
            url="https://example.com/a",
            title="Test",
            fetched_at=datetime.now(UTC),
        )
        assert resp.id == "abc"
        assert resp.blocks == []


class TestTranslateRequest:
    def test_valid(self) -> None:
        req = TranslateRequest(article_id="abc", block_index=0)
        assert req.article_id == "abc"
        assert req.block_index == 0


class TestBatchTranslateRequest:
    def test_valid(self) -> None:
        req = BatchTranslateRequest(article_id="abc", block_indices=[0, 1, 2])
        assert req.block_indices == [0, 1, 2]


class TestTranslateResponse:
    def test_default_no_error(self) -> None:
        resp = TranslateResponse(
            article_id="a",
            block_index=0,
            block_type=BlockType.paragraph,
            translated_text="Hello",
            cached=False,
        )
        assert resp.error is False

    def test_explicit_error(self) -> None:
        resp = TranslateResponse(
            article_id="a",
            block_index=0,
            block_type=BlockType.paragraph,
            translated_text="",
            cached=False,
            error=True,
        )
        assert resp.error is True


class TestBatchTranslateResponse:
    def test_translations_list(self) -> None:
        t1 = TranslateResponse(
            article_id="a", block_index=0, block_type=BlockType.paragraph,
            translated_text="T1", cached=False,
        )
        t2 = TranslateResponse(
            article_id="a", block_index=1, block_type=BlockType.heading,
            translated_text="T2", cached=True,
        )
        resp = BatchTranslateResponse(translations=[t1, t2])
        assert len(resp.translations) == 2
        assert resp.translations[0].translated_text == "T1"
        assert resp.translations[1].cached is True

    def test_empty_list(self) -> None:
        resp = BatchTranslateResponse(translations=[])
        assert resp.translations == []


# ── Serialisation round-trip ───────────────────────────────────────────


class TestSerializationRoundTrip:
    """Verify that Block subclasses survive JSON serialisation/deserialisation."""

    @pytest.mark.parametrize(
        "block",
        [
            HeadingBlock(level=3, content="Section"),
            ParagraphBlock(content="Text"),
            CodeBlock(content="code", language="go"),
            ImageBlock(src="/img.png", alt="img"),
            ListBlock(items=["x", "y"], ordered=True),
            QuoteBlock(content="Quote"),
        ],
    )
    def test_model_dump_and_validate(self, block: Block) -> None:
        """model_dump_json → json.loads → TypeAdapter validates."""
        import json
        from pydantic import TypeAdapter

        adapter = TypeAdapter(list[Block])
        raw = json.loads(block.model_dump_json())
        restored = adapter.validate_python([raw])
        assert len(restored) == 1
        assert type(restored[0]) is type(block)
        assert restored[0].model_dump() == block.model_dump()
