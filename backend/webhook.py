"""
# @module: webhook
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from aiogram import Bot, Dispatcher
from aiogram.types import Update

from backend.bot import create_dispatcher, get_webhook_bot
from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Bot is created by register_webhook() in bot.py — singletons shared via get_webhook_bot()
_dispatcher: Dispatcher | None = None


async def _get_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    """Lazily initialise dispatcher singleton; bot comes from bot.py's register_webhook()."""
    global _dispatcher
    bot = get_webhook_bot()
    if bot is None:
        raise RuntimeError("Webhook bot not initialized — register_webhook() must be called first")
    if _dispatcher is None:
        _dispatcher = create_dispatcher()
    return bot, _dispatcher


@router.post("/webhook/telegram")
async def telegram_webhook(request: Request) -> JSONResponse:
    """Receive a Telegram Update and feed it into the aiogram dispatcher."""
    # Verify secret token (Telegram sends X-Telegram-Bot-Api-Secret-Token)
    secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret_token != settings.webhook_secret:
        logger.warning("[Webhook] Invalid or missing secret token")
        return JSONResponse(status_code=403, content={"status": "error", "detail": "invalid secret token"})

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
