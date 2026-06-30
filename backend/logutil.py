"""
# @module: logutil

Structured event logging with GCP Logs Explorer compatibility.

Usage:
    from backend.logutil import logevent

    logevent(logger, "bot", "PARSE_FAILED",
             "Failed to parse article URL from bot message",
             url=url, error=str(e))

    logevent(logger, "bot", "TOKEN_MISSING",
             "BOT_TOKEN is empty — bot cannot start",
             level=logging.WARNING, bot_enabled=str(settings.bot_enabled))

    logevent(logger, "webhook", "SECRET_MISMATCH",
             "Rejected webhook request with incorrect secret token",
             security=True, remote_ip=client_ip)
"""

import logging
from typing import Any


def logevent(
    logger: logging.Logger,
    module: str,
    event: str,
    message: str,
    *,
    level: int = logging.ERROR,
    exc_info: bool = False,
    security: bool = False,
    **extra: Any,
) -> None:
    """Log a structured event with semantic anchor and optional context.

    Args:
        logger: Logger instance (use module-level LOGGER).
        module: Module name for [ModuleName] semantic anchor — must match
                the @module annotation and MODULE_MAP.md.
        event: Machine-readable event name in SCREAMING_SNAKE_CASE
               (e.g. "UPDATE_PARSE_FAILED", "SECRET_MISMATCH").
        message: Human-readable description of what happened.
        level: Logging level (default ERROR). Use logging.WARNING for
               non-critical configuration or operational issues.
        exc_info: If True, includes full traceback (use inside except blocks).
        security: If True, logs at WARNING with "SECURITY: " prefix for
                  easy filtering of security-related events in GCP Logs Explorer.
        extra: Additional structured context fields (strings, ints, bools).
               Values are stringified for safe logging.
    """
    fields = " | ".join(f"{k}={v}" for k, v in extra.items())
    suffix = f" | {fields}" if fields else ""

    if security:
        logger.warning(
            "[%s] SECURITY: %s | event=%s%s",
            module,
            message,
            event,
            suffix,
        )
    else:
        logger.log(
            level,
            "[%s] %s | event=%s%s",
            module,
            message,
            event,
            suffix,
            exc_info=exc_info,
        )