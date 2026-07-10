"""
# @module: models
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, HttpUrl, field_validator


class BlockType(StrEnum):
    heading = "heading"
    paragraph = "paragraph"
    code = "code"
    image = "image"
    list = "list"
    quote = "quote"


class HeadingBlock(BaseModel):
    type: Literal[BlockType.heading] = BlockType.heading
    level: int
    content: str

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: int) -> int:
        if not 1 <= v <= 6:
            raise ValueError(f"Heading level must be 1-6, got {v}")
        return v


class ParagraphBlock(BaseModel):
    type: Literal[BlockType.paragraph] = BlockType.paragraph
    content: str


class CodeBlock(BaseModel):
    type: Literal[BlockType.code] = BlockType.code
    content: str
    language: str | None = None


class ImageBlock(BaseModel):
    type: Literal[BlockType.image] = BlockType.image
    src: str
    alt: str = ""


class ListBlock(BaseModel):
    type: Literal[BlockType.list] = BlockType.list
    items: list[str]
    ordered: bool


class QuoteBlock(BaseModel):
    type: Literal[BlockType.quote] = BlockType.quote
    content: str


Block = Annotated[
    Union[HeadingBlock, ParagraphBlock, CodeBlock, ImageBlock, ListBlock, QuoteBlock],
    ...,
]


class Article(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    url: str
    title: str
    blocks: list[Block] = []
    fetched_at: datetime | None = Field(default_factory=lambda: datetime.now(UTC))


class ParseRequest(BaseModel):
    url: HttpUrl


class ArticleResponse(BaseModel):
    id: str
    url: str
    title: str
    blocks: list[Block] = []
    fetched_at: datetime


class TranslateRequest(BaseModel):
    article_id: str
    block_index: int


class BatchTranslateRequest(BaseModel):
    article_id: str
    block_indices: list[int]


class TranslateResponse(BaseModel):
    article_id: str
    block_index: int
    block_type: BlockType
    translated_text: str
    cached: bool
    error: bool = False


class BatchTranslateResponse(BaseModel):
    translations: list[TranslateResponse]


class SummarizeRequest(BaseModel):
    article_id: str


class SummarizeResponse(BaseModel):
    article_id: str
    summary: str | None = None
    cached: bool = False
    error: bool = False
