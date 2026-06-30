"""
# @module: logutil

Structured error logging with GCP Logs Explorer compatibility.

Usage:
    from backend.logutil import logerror, logexception

    try:
        result = await risky_operation()
    except Exception as e:
        logexception(LOGGER, "webhook", "UPDATE_PROCESS_FAILED",
                     "Failed to process Telegram update",
                     update_id=update_id, bot_token_present=bool(bot_token))
        raise

    if not valid:
        logerror(LOGGER, "webhook", "INVALID_SECRET",
                 "Rejected request with invalid secret token",
                 remote_ip=client_ip, path=request.url.path)
"""

import logging
import sys
import traceback
from typing import Any


def logerror(
    logger: logging.Logger,
    module: str,
    event: str,
    message: str,
    **extra: Any,
) -> None:
    """Log a structured error event (ERROR level).

    Args:
        logger: Logger instance (use module-level LOGGER).
        module: Module name for [ModuleName] semantic anchor — must match
                the @module annotation and MODULE_MAP.md.
        event: Machine-readable event name in SCREAMING_SNAKE_CASE
               (e.g. "UPDATE_PARSE_FAILED", "SECRET_MISMATCH").
        message: Human-readable description of what happened.
        extra: Additional structured context fields (strings, ints, bools).
               Values are stringified for safe logging.
    """
    fields = " | ".join(f"{k}={v}" for k, v in extra.items())
    logger.error(
        "[%s] %s | event=%s%s",
        module,
        message,
        event,
        f" | {fields}" if fields else "",
    )


def logexception(
    logger: logging.Logger,
    module: str,
    event: str,
    message: str,
    exc_info: bool = True,
    **extra: Any,
) -> None:
    """Log an exception with full traceback (ERROR level).

    Use this inside except blocks where you want to log the traceback.

    Args:
        logger: Logger instance.
        module: Module name for [ModuleName] semantic anchor.
        event: Machine-readable event name in SCREAMING_SNAKE_CASE.
        message: Human-readable description.
        exc_info: If True (default), includes full traceback.
        extra: Additional structured context fields.
    """
    fields = " | ".join(f"{k}={v}" for k, v in extra.items())
    logger.error(
        "[%s] %s | event=%s%s",
        module,
        message,
        event,
        f" | {fields}" if fields else "",
        exc_info=exc_info,
    )


def logsecure(
    logger: logging.Logger,
    module: str,
    event: str,
    message: str,
    **extra: Any,
) -> None:
    """Log a security-related event (WARNING level, but with SECURITY prefix).

    Security events (auth failures, token mismatches, rate limiting) are
    logged at WARNING level to avoid alert fatigue, but include the SECURITY
    prefix for easy filtering in GCP Logs Explorer.

    Args:
        logger: Logger instance.
        module: Module name for [ModuleName] semantic anchor.
        event: Machine-readable event name in SCREAMING_SNAKE_CASE.
        message: Human-readable description.
        extra: Additional structured context fields.
    """
    fields = " | ".join(f"{k}={v}" for k, v in extra.items())
    logger.warning(
        "[%s] SECURITY: %s | event=%s%s",
        module,
        message,
        event,
        f" | {fields}" if fields else "",
    )
