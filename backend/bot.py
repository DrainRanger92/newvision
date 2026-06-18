"""
<MODULE_CONTRACT>
name: bot
layer: Presentation
depends: [config, parser, db, models]
responsibility: Telegram bot with aiogram 3 — /start handler, URL→parse→WebApp button flow, polling lifecycle
contract: Bot polling starts only when BOT_ENABLED=true and BOT_TOKEN is non-empty; URL messages trigger parse and reply with WebAppInfo button; router is import-safe (no side effects on import)
</MODULE_CONTRACT>

<LINKS>
- config: reads bot_token, bot_enabled, and mini_app_url from settings
- main: router included in FastAPI lifespan via start_bot_polling()
- parser: parse_article() for URL→blocks pipeline
- db: save_article() to persist parsed article
- models: Article model constructed after parse
</LINKS>
"""

import logging
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from backend.config import settings

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("start"))
async def handle_start(message: Message) -> None:
    await message.answer(
        "Welcome to NewVision! Send me a URL to an English technical article."
    )


@router.message()
async def handle_url(message: Message) -> None:
    if not message.text:
        return

    url = message.text.strip()
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        await message.answer("Please send a valid URL.")
        return

    if parsed.scheme not in ("http", "https"):
        await message.answer("Only http/https URLs are supported.")
        return

    await message.answer("⏳ Parsing article...")

    try:
        from backend.db import save_article
        from backend.models import Article
        from backend.parser import ParseError, parse_article

        raw_html, title, blocks = await parse_article(url)
        article = Article(url=url, title=title, blocks=blocks)
        await save_article(article, raw_html)
    except ParseError as e:
        logger.warning("[Bot] Parse failed for %s: %s", url, e)
        await message.answer(f"❌ Failed to parse: {e}")
        return

    web_app_url = f"{settings.mini_app_url}/#/reader/{article.id}"
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📖 Open in Reader",
                    web_app=WebAppInfo(url=web_app_url),
                )
            ],
        ],
    )

    await message.answer(
        f"✅ *{title}*\n\nParsed successfully. Open in Mini App to read.",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


def create_bot() -> Bot:
    return Bot(token=settings.bot_token)


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(router)
    return dp


async def start_bot_polling() -> None:
    if not settings.bot_enabled:
        logger.info("[Bot] Bot is disabled (BOT_ENABLED=false). Skipping polling.")
        return

    if not settings.bot_token:
        logger.warning("[Bot] BOT_TOKEN is empty. Bot will not start.")
        return

    logger.info("[Bot] Starting bot polling...")
    bot = create_bot()
    dp = create_dispatcher()
    await dp.start_polling(bot)
