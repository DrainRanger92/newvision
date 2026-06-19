"""
# @module: bot
"""

import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message

from backend.config import settings

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("start"))
async def handle_start(message: Message) -> None:
    await message.answer(
        "Welcome to Curtain Reader! Send me a URL to an English technical article."
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
