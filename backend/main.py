"""
<MODULE_CONTRACT>
name: main
layer: Presentation
depends: [config, db, models, parser, translator, bot]
responsibility: FastAPI application assembly — CORS, lifespan, endpoints (/health, /api/parse, /api/translate, /api/translate/batch, GET /api/articles/{id})
contract: All endpoints return valid JSON; health always responds 200; parse and translate endpoints delegate to application-layer modules; lifespan manages db init/close and bot polling lifecycle
</MODULE_CONTRACT>

<LINKS>
- config: uses settings for CORS origins, db_path, API keys
- db: init_db() in lifespan; get_article_by_id, get_article_by_url, save_article in endpoints
- models: ParseRequest, TranslateRequest, BatchTranslateRequest, TranslateResponse, BatchTranslateResponse, Article
- parser: parse_article() for POST /api/parse
- translator: translate_block(), translate_blocks_batch() for translate endpoints
- bot: start_bot_polling() in lifespan
</LINKS>
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.bot import start_bot_polling
from backend.config import settings
from backend.db import close_db, get_article_by_id, get_article_by_url, init_db, save_article
from backend.models import (
    Article,
    BatchTranslateRequest,
    BatchTranslateResponse,
    Block,
    BlockType,
    ParseRequest,
    TranslateRequest,
    TranslateResponse,
)
from backend.parser import ParseError, parse_article
from backend.translator import TranslationError, translate_block, translate_blocks_batch

logging.basicConfig(
    level=logging.INFO,
    format="[%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(settings.db_path)
    bot_task = asyncio.create_task(start_bot_polling())
    yield
    bot_task.cancel()
    try:
        await bot_task
    except asyncio.CancelledError:
        pass
    await close_db()


app = FastAPI(
    title="NewVision API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/parse")
async def api_parse(req: ParseRequest) -> Article:
    url = str(req.url)
    logger.info("[Parser] POST /api/parse url=%s", url)

    cached = await get_article_by_url(url)
    if cached is not None:
        logger.info("[Parser] Cache hit for %s", url)
        return cached

    start = time.time()
    try:
        raw_html, title, blocks = await parse_article(url)
    except ParseError as e:
        logger.warning("[Parser] Parse failed for %s: %s", url, e)
        raise HTTPException(status_code=422, detail=str(e))

    article = Article(url=url, title=title, blocks=blocks)
    await save_article(article, raw_html)
    elapsed = time.time() - start
    logger.info("[Parser] Parsed %s in %.2fs", url, elapsed)
    return article


@app.get("/api/articles/{article_id}")
async def api_get_article(article_id: str) -> Article:
    article = await get_article_by_id(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@app.post("/api/translate")
async def api_translate(req: TranslateRequest) -> TranslateResponse:
    article = await get_article_by_id(req.article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    if req.block_index < 0 or req.block_index >= len(article.blocks):
        raise HTTPException(status_code=400, detail="Block index out of range")

    block = article.blocks[req.block_index]
    if block.type in (BlockType.code, BlockType.image):
        raise HTTPException(status_code=400, detail=f"Block type '{block.type}' cannot be translated")

    logger.info("[Translator] POST /api/translate article=%s block=%d", req.article_id, req.block_index)

    try:
        translated_text, cached, error = await translate_block(
            req.article_id, req.block_index, block, settings.deepseek_api_key, settings.translation_model,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TranslationError:
        logger.warning("[Translator] Translation failed for article=%s block=%d", req.article_id, req.block_index)
        raise HTTPException(status_code=503, detail="Translation service unavailable")

    return TranslateResponse(
        article_id=req.article_id,
        block_index=req.block_index,
        block_type=block.type,
        translated_text=translated_text,
        cached=cached,
        error=error,
    )


@app.post("/api/translate/batch")
async def api_translate_batch(req: BatchTranslateRequest) -> BatchTranslateResponse:
    if len(req.block_indices) > 10:
        raise HTTPException(status_code=400, detail="Batch size exceeds maximum of 10 blocks")

    article = await get_article_by_id(req.article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    valid_blocks: list[tuple[int, Block]] = []
    for idx in req.block_indices:
        if idx < 0 or idx >= len(article.blocks):
            logger.warning("[Translator] Block index %d out of range, skipping", idx)
            continue
        block = article.blocks[idx]
        if block.type in (BlockType.code, BlockType.image):
            logger.warning("[Translator] Skipping block %d (type=%s)", idx, block.type)
            continue
        valid_blocks.append((idx, block))

    if not valid_blocks:
        raise HTTPException(status_code=400, detail="No valid translatable blocks in request")

    logger.info("[Translator] POST /api/translate/batch article=%s blocks=%s", req.article_id, valid_blocks)

    try:
        results = await translate_blocks_batch(
            req.article_id, valid_blocks, settings.deepseek_api_key, settings.translation_model,
        )
    except TranslationError:
        logger.warning("[Translator] Batch translation failed for article=%s", req.article_id)
        raise HTTPException(status_code=503, detail="Translation service unavailable")

    translations = [
        TranslateResponse(
            article_id=req.article_id,
            block_index=idx,
            block_type=article.blocks[idx].type,
            translated_text=text,
            cached=cached,
            error=error,
        )
        for idx, text, cached, error in results
    ]

    return BatchTranslateResponse(translations=translations)
