"""
# @module: bot
"""

import logging
import re
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from backend.config import settings
from backend.db import get_article_by_url, save_article
from backend.models import Article
from backend.parser import ParseError, parse_article

logger = logging.getLogger(__name__)

router = Router()

_URL_REGEX = re.compile(r"^(https?://[^\s]+)", re.IGNORECASE)


@router.message(Command("start"))
async def handle_start(message: Message) -> None:
    await message.answer(
        "Welcome to NewVision! Send me a URL to an English technical article."
    )


@router.message()
async def handle_message(message: Message) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Please send a valid URL to an English technical article.")
        return

    match = _URL_REGEX.match(text)
    if not match:
        await message.answer("Please send a valid URL to an English technical article.")
        return

    url = match.group(1).rstrip(".,!?;:")
    parsed = urlparse(url)
    if not parsed.netloc:
        await message.answer("Please send a valid URL.")
        return

    article = await get_article_by_url(url)
    if article is None:
        await message.answer("Parsing article, please wait...")
        try:
            raw_html, title, blocks = await parse_article(url)
        except ParseError as e:
            logger.warning("[Bot] Parse failed for %s: %s", url, e)
            await message.answer(f"Failed to parse article: {e}")
            return

        article = Article(url=url, title=title, blocks=blocks)
        await save_article(article, raw_html)
        logger.info("[Bot] Parsed and saved article %s: %s", article.id, url)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Open in NewVision",
                    web_app=WebAppInfo(url=f"{settings.mini_app_url}/#/reader/{article.id}"),
                )
            ]
        ]
    )

    await message.answer(
        f"<b>{article.title}</b>\n\nChoose how to read:",
        reply_markup=keyboard,
        parse_mode="HTML",
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
