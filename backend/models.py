"""
<MODULE_CONTRACT>
name: models
layer: Domain
depends: []
responsibility: Pydantic data models for articles, blocks, translation requests/responses
contract: All models are self-validating via Pydantic; Block discriminated union covers all content types; serialisation is round-trip safe
</MODULE_CONTRACT>

<LINKS>
- db: stores and retrieves Article objects via JSON serialisation
- parser: produces Block instances from parsed HTML
- main: API request/response models
</LINKS>
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, HttpUrl, field_validator


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


def _generate_uuid() -> str:
    return str(uuid.uuid4())


class Article(BaseModel):
    id: str = ""
    url: str
    title: str
    blocks: list[Block] = []
    fetched_at: datetime | None = None

    def model_post_init(self, __context) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())
        if self.fetched_at is None:
            self.fetched_at = datetime.now(UTC)


class ParseRequest(BaseModel):
    url: HttpUrl


class ArticleResponse(BaseModel):
    id: str
    url: str
    title: str
    blocks: list[Block] = []
    fetched_at: datetime