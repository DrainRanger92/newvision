"""
# @module: webhook
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from aiogram import Bot, Dispatcher
from aiogram.types import Update

from backend.bot import create_bot, create_dispatcher

logger = logging.getLogger(__name__)

router = APIRouter()

_bot: Bot | None = None
_dispatcher: Dispatcher | None = None


async def _get_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    """Lazily initialise bot + dispatcher singletons for webhook handling."""
    global _bot, _dispatcher
    if _bot is None:
        _bot = create_bot()
    if _dispatcher is None:
        _dispatcher = create_dispatcher()
    return _bot, _dispatcher


@router.post("/webhook/telegram")
async def telegram_webhook(request: Request) -> JSONResponse:
    """Receive a Telegram Update and feed it into the aiogram dispatcher."""
    bot, dp = await _get_bot_and_dispatcher()
    try:
        payload = await request.json()
    except ValueError:
        logger.warning("[Webhook] Invalid JSON payload received")
        return JSONResponse(status_code=400, content={"status": "error", "detail": "invalid json"})

    update = Update.model_validate(payload, context={"bot": bot})
    await dp.feed_webhook_update(bot, update)
    logger.info("[Webhook] Processed update_id=%s", update.update_id)
    return JSONResponse(content={"status": "ok"})


async def shutdown_webhook_singletons() -> None:
    """Close the bot session and shut down the dispatcher."""
    global _bot, _dispatcher
    if _dispatcher is not None:
        await _dispatcher.shutdown()
    if _bot is not None:
        await _bot.session.close()
    _bot = None
    _dispatcher = None
