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
from backend.models import Article, ParseRequest
from backend.parser import ParseError, parse_article

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
    title="Curtain Reader API",
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
