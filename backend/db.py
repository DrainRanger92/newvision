"""
# @module: db
"""

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from backend.models import Article

logger = logging.getLogger(__name__)

_db: aiosqlite.Connection | None = None


async def init_db(db_path: str) -> None:
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
    await _db.execute(
        """
        CREATE TABLE IF NOT EXISTS translations (
            article_id TEXT NOT NULL,
            block_index INTEGER NOT NULL,
            text_hash TEXT NOT NULL,
            original_text TEXT NOT NULL,
            translated_text TEXT NOT NULL,
            model TEXT NOT NULL,
            translated_at TEXT NOT NULL,
            PRIMARY KEY (article_id, block_index)
        )
        """
    )
    await _db.execute(
        "CREATE INDEX IF NOT EXISTS idx_translations_lookup ON translations(article_id, block_index)"
    )
    await _db.execute(
        """
        CREATE TABLE IF NOT EXISTS summaries (
            article_id TEXT PRIMARY KEY,
            summary TEXT NOT NULL,
            model TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
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


async def get_translation(article_id: str, block_index: int, text_hash: str | None = None) -> str | None:
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    cursor = await _db.execute(
        "SELECT text_hash, translated_text FROM translations WHERE article_id = ? AND block_index = ?",
        (article_id, block_index),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    if text_hash is not None and row["text_hash"] != text_hash:
        return None
    return row["translated_text"]


async def save_translation(article_id: str, block_index: int, original_text: str, translated_text: str, model: str) -> None:
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    text_hash = hashlib.sha256(original_text.encode()).hexdigest()[:16]
    translated_at = datetime.now(UTC).isoformat()
    await _db.execute(
        """
        INSERT OR REPLACE INTO translations (article_id, block_index, text_hash, original_text, translated_text, model, translated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (article_id, block_index, text_hash, original_text, translated_text, model, translated_at),
    )
    await _db.commit()
    logger.info("[DB] Saved translation for article=%s block=%d", article_id, block_index)


async def get_summary(article_id: str) -> str | None:
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    cursor = await _db.execute(
        "SELECT summary FROM summaries WHERE article_id = ?",
        (article_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return row["summary"]


async def save_summary(article_id: str, summary: str, model: str) -> None:
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    created_at = datetime.now(UTC).isoformat()
    await _db.execute(
        """
        INSERT OR REPLACE INTO summaries (article_id, summary, model, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (article_id, summary, model, created_at),
    )
    await _db.commit()
    logger.info("[DB] Saved summary for article=%s", article_id)


async def get_translations_batch(article_id: str, block_indices: list[int]) -> dict[int, str]:
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    if not block_indices:
        return {}
    placeholders = ",".join("?" for _ in block_indices)
    cursor = await _db.execute(
        f"SELECT block_index, translated_text FROM translations WHERE article_id = ? AND block_index IN ({placeholders})",
        (article_id, *block_indices),
    )
    rows = await cursor.fetchall()
    return {row["block_index"]: row["translated_text"] for row in rows}


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None
        logger.info("[DB] Connection closed")


def _row_to_article(row: aiosqlite.Row) -> Article:
    blocks_data = json.loads(row["blocks_json"])
    from pydantic import TypeAdapter
    from backend.models import Block

    adapter = TypeAdapter(list[Block])
    blocks = adapter.validate_python(blocks_data)
    return Article(
        id=row["id"],
        url=row["url"],
        title=row["title"],
        blocks=blocks,
        fetched_at=row["fetched_at"],
    )