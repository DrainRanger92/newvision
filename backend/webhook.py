"""
# @module: webhook
"""

import logging

from fastapi import APIRouter, Request
from aiogram import Bot
from aiogram.types import Update

from backend.bot import create_bot, create_dispatcher

logger = logging.getLogger(__name__)

router = APIRouter()

_bot: Bot | None = None
_dispatcher = None


async def _get_bot_and_dispatcher() -> tuple[Bot, object]:
    """Lazily initialise bot + dispatcher singletons for webhook handling."""
    global _bot, _dispatcher
    if _bot is None:
        _bot = create_bot()
    if _dispatcher is None:
        _dispatcher = create_dispatcher()
    return _bot, _dispatcher


@router.post("/webhook/telegram")
async def telegram_webhook(request: Request) -> dict[str, str]:
    """Receive a Telegram Update and feed it into the aiogram dispatcher."""
    payload = await request.json()
    update = Update.model_validate(payload, context={"bot": _bot})
    bot, dp = await _get_bot_and_dispatcher()
    await dp.feed_webhook_update(bot, update)
    logger.info("[Webhook] Processed update_id=%s", update.update_id)
    return {"status": "ok"}


async def shutdown_webhook_singletons() -> None:
    """Close the bot session created for webhook handling."""
    global _bot, _dispatcher
    if _bot is not None:
        await _bot.session.close()
        _bot = None
    _dispatcher = None