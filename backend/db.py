import json
import logging
from pathlib import Path

import aiosqlite

from backend.models import Article

logger = logging.getLogger(__name__)

_db: aiosqlite.Connection | None = None


async def init_db(db_path: str = "data/curtain_reader.db") -> None:
    global _db
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    _db = await aiosqlite.connect(db_path)
    _db.row_factory = aiosqlite.Row
    await _db.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id TEXT PRIMARY KEY,
            url TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            html TEXT NOT NULL,
            blocks_json TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        )
        """
    )
    await _db.execute(
        "CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url)"
    )
    await _db.commit()
    logger.info("[DB] Initialized at %s", db_path)


async def get_article_by_url(url: str) -> Article | None:
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    cursor = await _db.execute("SELECT * FROM articles WHERE url = ?", (url,))
    row = await cursor.fetchone()
    if row is None:
        return None
    return _row_to_article(row)


async def get_article_by_id(article_id: str) -> Article | None:
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    cursor = await _db.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
    row = await cursor.fetchone()
    if row is None:
        return None
    return _row_to_article(row)


async def save_article(article: Article, raw_html: str) -> None:
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    blocks_json = article.model_dump_json(include={"blocks"})
    blocks_data = json.loads(blocks_json)["blocks"]
    blocks_only_json = json.dumps(blocks_data)
    await _db.execute(
        """
        INSERT OR REPLACE INTO articles (id, url, title, html, blocks_json, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            article.id,
            article.url,
            article.title,
            raw_html,
            blocks_only_json,
            article.fetched_at.isoformat(),
        ),
    )
    await _db.commit()
    logger.info("[DB] Saved article %s (url=%s)", article.id, article.url)


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None
        logger.info("[DB] Connection closed")


def _row_to_article(row: aiosqlite.Row) -> Article:
    blocks_data = json.loads(row["blocks_json"])
    from backend.models import Block

    blocks = [Block.model_validate(b) for b in blocks_data]
    return Article(
        id=row["id"],
        url=row["url"],
        title=row["title"],
        blocks=blocks,
        fetched_at=row["fetched_at"],
    )