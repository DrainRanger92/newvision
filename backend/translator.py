"""
<MODULE_CONTRACT>
name: translator
layer: Application
depends: [models, db]
responsibility: LLM-based EN→RU translation with code-tag preservation, caching, and batch optimisation
contract: Code tags (<code>...</code>) are extracted before translation and restored after; translations are cached via db module keyed by (article_id, block_index, text_hash); single-block latency <1.5s; batch translates N blocks in one LLM call
</MODULE_CONTRACT>

<LINKS>
- models: uses Block discriminated union; BlockType.code and BlockType.image are rejected
- db: uses get_translation, save_translation, get_translations_batch for cache layer
- config: reads deepseek_api_key and translation_model from settings (via callers)
</LINKS>
"""

import hashlib
import logging
import re

import httpx
from bs4 import BeautifulSoup
from openai import AsyncOpenAI

from backend.models import Block, BlockType, CodeBlock, HeadingBlock, ImageBlock, ListBlock, ParagraphBlock, QuoteBlock

logger = logging.getLogger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
CODE_PLACEHOLDER_RE = re.compile(r"__CC_(\d+)__")
CODE_TAG_RE = re.compile(r"<code[^>]*>.*?</code>", re.DOTALL)
BLOCK_SEPARATOR_RE = re.compile(r"---BLOCK\s+(\d+)---")

TRANSLATION_SYSTEM_PROMPT = (
    "You are a technical translator. Translate the following English text to Russian.\n"
    "Rules:\n"
    "1. Keep ALL markers like __CC_0__, __CC_1__ exactly as-is — never modify, translate, or remove them.\n"
    "2. Preserve technical terms: API names, function names, variable names, class names, library names — keep in English.\n"
    "3. Preserve URLs, numbers, and HTML entities exactly as-is.\n"
    "4. Preserve the original line breaks and paragraph structure.\n"
    "5. Return ONLY the translated text. No explanations, no notes, no markdown formatting."
)


class TranslationError(Exception):
    pass


def _extract_code_tags(html: str) -> tuple[str, list[str]]:
    codes: list[str] = []
    def _replacer(m: re.Match) -> str:
        codes.append(m.group(0))
        return f"__CC_{len(codes) - 1}__"
    text = CODE_TAG_RE.sub(_replacer, html)
    return text, codes


def _restore_code_tags(text: str, codes: list[str]) -> str:
    def _restorer(m: re.Match) -> str:
        idx = int(m.group(1))
        if idx < len(codes):
            return codes[idx]
        return m.group(0)
    return CODE_PLACEHOLDER_RE.sub(_restorer, text)


def _html_to_plain_text(html: str) -> str:
    text = BeautifulSoup(html, "lxml").get_text(separator=" ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _get_translatable_text(block: Block) -> str:
    if isinstance(block, HeadingBlock):
        return block.content
    if isinstance(block, ParagraphBlock):
        return block.content
    if isinstance(block, QuoteBlock):
        return block.content
    if isinstance(block, ListBlock):
        return "\n".join(block.items)
    raise ValueError(f"Block type {block.type} cannot be translated")


def _build_translation_prompt(text: str) -> list[dict]:
    return [
        {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]


def _build_batch_prompt(texts: list[str]) -> list[dict]:
    parts = []
    for i, t in enumerate(texts):
        parts.append(f"---BLOCK {i}---\n\n{t}")
    joined = "\n\n".join(parts)
    system_prompt = (
        TRANSLATION_SYSTEM_PROMPT + "\n\n"
        "Each block is separated by '---BLOCK N---'. Preserve these separators in your response."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": joined},
    ]


async def translate_text(text: str, api_key: str, model: str = "deepseek-chat") -> str:
    http_client = httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0))
    try:
        client = AsyncOpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL, http_client=http_client)
        response = await client.chat.completions.create(
            model=model,
            messages=_build_translation_prompt(text),
            temperature=0.1,
        )
        content = response.choices[0].message.content
        if content is None:
            raise TranslationError("LLM returned empty response")
        return content
    except Exception as e:
        logger.warning("[Translator] translate_text failed: %s", e)
        raise TranslationError(str(e)) from e
    finally:
        await http_client.aclose()


async def translate_block(
    article_id: str,
    block_index: int,
    block: Block,
    api_key: str,
    model: str = "deepseek-chat",
) -> tuple[str, bool, bool]:
    from backend.db import get_translation, save_translation

    if isinstance(block, CodeBlock) or isinstance(block, ImageBlock):
        raise ValueError(f"Block type '{block.type}' cannot be translated")

    raw_html = _get_translatable_text(block)
    text_with_placeholders, codes = _extract_code_tags(raw_html)
    plain_text = _html_to_plain_text(text_with_placeholders)

    text_hash = hashlib.sha256(plain_text.encode()).hexdigest()[:16]

    cached_text = await get_translation(article_id, block_index, text_hash)
    if cached_text is not None:
        logger.info("[Translator] Cache hit for article=%s block=%d", article_id, block_index)
        restored = _restore_code_tags(cached_text, codes)
        return restored, True, False

    logger.info("[Translator] Translating article=%s block=%d (%d chars, type=%s)", article_id, block_index, len(plain_text), block.type.value)

    try:
        translated = await translate_text(plain_text, api_key, model)
    except TranslationError:
        logger.warning("[Translator] Translation failed for article=%s block=%d", article_id, block_index)
        restored = _restore_code_tags(text_with_placeholders, codes)
        return restored, False, True

    await save_translation(article_id, block_index, plain_text, translated, model)

    restored = _restore_code_tags(translated, codes)
    return restored, False, False


async def translate_blocks_batch(
    article_id: str,
    blocks: list[tuple[int, Block]],
    api_key: str,
    model: str = "deepseek-chat",
) -> list[tuple[int, str, bool, bool]]:
    from backend.db import get_translations_batch, save_translation

    indices = [b[0] for b in blocks]
    cached_map = await get_translations_batch(article_id, indices)

    results: list[tuple[int, str, bool, bool]] = []
    to_translate: list[tuple[int, Block, str, str, list[str]]] = []

    for idx, block in blocks:
        if isinstance(block, CodeBlock) or isinstance(block, ImageBlock):
            results.append((idx, _get_translatable_text(block), False, True))
            continue

        raw_html = _get_translatable_text(block)
        text_with_placeholders, codes = _extract_code_tags(raw_html)
        plain_text = _html_to_plain_text(text_with_placeholders)
        text_hash = hashlib.sha256(plain_text.encode()).hexdigest()[:16]

        if idx in cached_map:
            restored = _restore_code_tags(cached_map[idx], codes)
            results.append((idx, restored, True, False))
        else:
            to_translate.append((idx, block, plain_text, text_hash, codes))

    if not to_translate:
        return results

    logger.info("[Translator] Batch: %d blocks, %d cached, translating %d", len(blocks), len(results) - len(to_translate), len(to_translate))

    texts_to_send = [t[2] for t in to_translate]

    try:
        prompt = _build_batch_prompt(texts_to_send)
        http_client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=3.0))
        try:
            client = AsyncOpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL, http_client=http_client)
            response = await client.chat.completions.create(
                model=model,
                messages=prompt,
                temperature=0.1,
            )
            raw_response = response.choices[0].message.content or ""
        finally:
            await http_client.aclose()

        parsed = _parse_batch_response(raw_response, len(to_translate))

        for i, (idx, block, plain_text, text_hash, codes) in enumerate(to_translate):
            translated_text = parsed.get(i, "")
            if not translated_text:
                logger.warning("[Translator] Batch parse missing block %d, falling back", idx)
                try:
                    translated_text = await translate_text(plain_text, api_key, model)
                except TranslationError:
                    restored = _restore_code_tags(
                        _get_translatable_text(block).replace(str(codes[i]), codes[i]) if i < len(codes) else _get_translatable_text(block),
                        codes,
                    )
                    results.append((idx, restored, False, True))
                    continue

            await save_translation(article_id, idx, plain_text, translated_text, model)
            restored = _restore_code_tags(translated_text, codes)
            results.append((idx, restored, False, False))

    except TranslationError:
        for idx, block, _, _, codes in to_translate:
            raw = _get_translatable_text(block)
            text_wp, _ = _extract_code_tags(raw)
            restored = _restore_code_tags(text_wp, codes)
            results.append((idx, restored, False, True))

    results.sort(key=lambda x: x[0])
    return results


def _parse_batch_response(response: str, expected_count: int) -> dict[int, str]:
    result: dict[int, str] = {}
    parts = BLOCK_SEPARATOR_RE.split(response)
    parts = [p.strip() for p in parts if p.strip()]

    for i in range(expected_count):
        marker = f"---BLOCK {i}---"
        if marker in response:
            before, after = response.split(marker, 1)
            if i < expected_count - 1:
                next_marker = f"---BLOCK {i + 1}---"
                if next_marker in after:
                    block_text = after.split(next_marker, 1)[0].strip()
                else:
                    block_text = after.strip()
            else:
                block_text = after.strip()
            result[i] = block_text
        else:
            result[i] = ""

    return result
