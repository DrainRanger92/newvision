"""
# @module: bot
"""

import logging
import re
from urllib.parse import urljoin, urlparse

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from backend.config import settings
from backend.db import get_article_by_url, save_article
from backend.logutil import logevent
from backend.models import Article
from backend.parser import ParseError, parse_article
from backend.summarizer import summarize_article

logger = logging.getLogger(__name__)

router = Router()

_URL_REGEX = re.compile(r"^(https?://[^\s]+)", re.IGNORECASE)

# Webhook Bot singleton — shared between register_webhook() and webhook.py
_webhook_bot: Bot | None = None


def get_webhook_bot() -> Bot | None:
    """Return the Bot instance created by register_webhook(), if any."""
    return _webhook_bot


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

    placeholder = await message.answer("Reading the article...")

    article = await get_article_by_url(url)
    if article is None:
        try:
            raw_html, title, blocks = await parse_article(url)
        except ParseError as e:
            logevent(
                logger,
                "bot",
                "PARSE_FAILED",
                "Failed to parse article URL from bot message",
                url=url,
                error=str(e),
            )
            await placeholder.edit_text(f"Failed to parse article: {e}")
            return

        article = Article(url=url, title=title, blocks=blocks)
        await save_article(article, raw_html)
        logger.info("[Bot] Parsed and saved article %s: %s", article.id, url)

    summary_text = ""
    if settings.deepseek_api_key:
        summary, _cached, error = await summarize_article(
            article.id,
            settings.deepseek_api_key,
            settings.translation_model,
        )
        if not error:
            summary_text = summary

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="\U0001f4d6 Читать полностью",
                    web_app=WebAppInfo(
                        url=f"{settings.mini_app_url}/#/reader/{article.id}"
                    ),
                )
            ]
        ]
    )

    display_text = f"<b>{article.title}</b>"
    if summary_text:
        display_text += f"\n\n{summary_text}"

    await placeholder.edit_text(display_text, reply_markup=keyboard, parse_mode="HTML")


def create_bot() -> Bot:
    return Bot(token=settings.bot_token)


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(router)
    return dp


async def start_bot_polling() -> None:
    """Start the bot in long-polling mode (local development)."""
    if not settings.bot_enabled:
        logger.info("[Bot] Bot is disabled (BOT_ENABLED=false). Skipping polling.")
        return

    if not settings.bot_token:
        logevent(
            logger,
            "bot",
            "TOKEN_MISSING",
            "BOT_TOKEN is empty — bot cannot start in polling mode",
            level=logging.WARNING,
            bot_enabled=str(settings.bot_enabled),
        )
        return

    logger.info("[Bot] Starting bot polling...")
    bot = create_bot()
    dp = create_dispatcher()
    await dp.start_polling(bot)


async def register_webhook() -> Bot | None:
    """Register a Telegram webhook for Cloud Run / serverless deployments.

    Stores the created Bot as a module-level singleton (accessible via
    get_webhook_bot()) so webhook.py does not create a second instance.
    Returns the Bot, or None if the bot is disabled or misconfigured.
    """
    global _webhook_bot

    if not settings.bot_enabled:
        logger.info(
            "[Bot] Bot is disabled (BOT_ENABLED=false). Skipping webhook registration."
        )
        return None

    if not settings.bot_token:
        logevent(
            logger,
            "bot",
            "TOKEN_MISSING",
            "BOT_TOKEN is empty — webhook cannot be registered",
            level=logging.WARNING,
            bot_enabled=str(settings.bot_enabled),
        )
        return None

    if not settings.webhook_secret:
        logevent(
            logger,
            "bot",
            "WEBHOOK_SECRET_MISSING",
            "WEBHOOK_SECRET is empty — webhook cannot be registered",
            level=logging.WARNING,
            webhook_url=settings.effective_webhook_url,
            webhook_path=settings.webhook_path,
        )
        return None

    if not settings.effective_webhook_url:
        logevent(
            logger,
            "bot",
            "WEBHOOK_URL_MISSING",
            "WEBHOOK_URL is empty — webhook cannot be registered",
            level=logging.WARNING,
            webhook_secret_present=str(bool(settings.webhook_secret)),
        )
        return None

    full_url = urljoin(
        settings.effective_webhook_url.rstrip("/") + "/",
        settings.webhook_path.lstrip("/"),
    )
    _webhook_bot = create_bot()
    try:
        await _webhook_bot.set_webhook(
            full_url,
            secret_token=settings.webhook_secret,
            drop_pending_updates=False,
        )
    except Exception as e:
        logevent(
            logger,
            "bot",
            "WEBHOOK_SET_FAILED",
            "Telegram API rejected webhook registration",
            exc_info=True,
            full_url=full_url,
            error=str(e),
        )
        _webhook_bot = None
        return None

    logger.info("[Bot] Webhook registered: %s", full_url)
    return _webhook_bot


async def delete_webhook(bot: Bot | None) -> None:
    """Delete a previously registered Telegram webhook and close the session."""
    global _webhook_bot
    if bot is None:
        return
    try:
        await bot.delete_webhook()
        logger.info("[Bot] Webhook deleted.")
    except Exception as e:
        logevent(
            logger,
            "bot",
            "WEBHOOK_DELETE_FAILED",
            "Failed to delete Telegram webhook during shutdown",
            exc_info=True,
            error=str(e),
        )
    finally:
        await bot.session.close()
    _webhook_bot = None
