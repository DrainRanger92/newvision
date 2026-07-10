"""
# @module: summarizer
"""

import logging

import httpx
from openai import AsyncOpenAI

from backend.logutil import logevent

logger = logging.getLogger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

SUMMARY_SYSTEM_PROMPT = """Ты — ассистент для суммаризации технических статей.
Прочитай статью на английском и напиши краткое содержание на русском.
Правила:
1. 3-5 предложений, только главное.
2. Технические термины оставляй на английском.
3. Только саммари, без пояснений и форматирования.
4. Не выдумывай факты, которых нет в статье."""


class SummarizationError(Exception):
    pass


async def summarize_article(
    article_id: str, api_key: str, model: str = "deepseek-chat"
) -> tuple[str, bool, bool]:
    """(summary, cached, error) — зеркало translator.translate_block."""
    from backend.db import get_article_by_id, get_summary, save_summary
    from backend.article_text import build_summary_context

    cached_summary = await get_summary(article_id)
    if cached_summary is not None:
        logger.info("[Summarizer] Cache hit for article=%s", article_id)
        return cached_summary, True, False

    article = await get_article_by_id(article_id)
    if article is None:
        logevent(logger, "Summarizer", "ARTICLE_NOT_FOUND", "Article not found", article_id=article_id)
        return "", False, True

    context = build_summary_context(article.blocks)

    http_client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=3.0))
    try:
        client = AsyncOpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL, http_client=http_client)
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
            temperature=0.3,
        )
        content = response.choices[0].message.content
        if content is None:
            raise SummarizationError("LLM returned empty response")
    except Exception:
        logevent(logger, "Summarizer", "SUMMARIZE_FAILED", "Summarization failed", exc_info=True)
        return "", False, True
    finally:
        await http_client.aclose()

    await save_summary(article_id, content, model)
    return content, False, False
