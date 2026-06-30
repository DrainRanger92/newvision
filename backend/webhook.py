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
from backend.logutil import logerror, logexception, logsecure

logger = logging.getLogger(__name__)

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
        secret_present = secret_token is not None
        logsecure(
            logger, "webhook", "SECRET_MISMATCH",
            "Rejected webhook request with incorrect or missing secret token",
            secret_present=str(secret_present),
            remote_ip=request.client.host if request.client else "unknown",
        )
        return JSONResponse(status_code=403, content={"status": "error", "detail": "invalid secret token"})

    bot, dp = await _get_bot_and_dispatcher()

    try:
        payload = await request.json()
    except ValueError as e:
        logerror(
            logger, "webhook", "INVALID_JSON",
            "Received non-JSON payload on webhook endpoint",
            error=str(e),
            content_length=request.headers.get("content-length", "0"),
        )
        return JSONResponse(status_code=400, content={"status": "error", "detail": "invalid json"})

    try:
        update = Update.model_validate(payload, context={"bot": bot})
    except Exception as e:
        logexception(
            logger, "webhook", "UPDATE_VALIDATE_FAILED",
            "Failed to validate Telegram Update model",
            update_id=payload.get("update_id", "unknown"),
        )
        return JSONResponse(status_code=422, content={"status": "error", "detail": "invalid update"})

    try:
        await dp.feed_webhook_update(bot, update)
    except Exception as e:
        logexception(
            logger, "webhook", "UPDATE_PROCESS_FAILED",
            "aiogram dispatcher raised exception while processing update",
            update_id=update.update_id,
        )
        return JSONResponse(status_code=500, content={"status": "error", "detail": "processing failed"})

    logger.info("[Webhook] Processed update_id=%s", update.update_id)
    return JSONResponse(content={"status": "ok"})


async def shutdown_webhook_singletons() -> None:
    """Close the bot session and shut down the dispatcher."""
    global _bot, _dispatcher
    if _dispatcher is not None:
        try:
            await _dispatcher.shutdown()
        except Exception as e:
            logexception(
                logger, "webhook", "DISPATCHER_SHUTDOWN_FAILED",
                "Error shutting down aiogram dispatcher",
            )
    if _bot is not None:
        try:
            await _bot.session.close()
        except Exception as e:
            logexception(
                logger, "webhook", "BOT_SESSION_CLOSE_FAILED",
                "Error closing bot aiohttp session",
            )
    _bot = None
    _dispatcher = None
