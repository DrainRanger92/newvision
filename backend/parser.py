import logging
import re
from urllib.parse import urlparse

import httpx
import lxml.html
from bs4 import BeautifulSoup, Tag
from readability import Document

from backend.config import settings
from backend.models import (
    Block,
    CodeBlock,
    HeadingBlock,
    ImageBlock,
    ListBlock,
    ParagraphBlock,
    QuoteBlock,
)

logger = logging.getLogger(__name__)

_USER_AGENT = "CurtainReader/1.0 (+https://github.com/curtain-reader)"


class ParseError(Exception):
    pass


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower() if parsed.hostname else ""
    port = f":{parsed.port}" if parsed.port and not (
        (scheme == "https" and parsed.port == 443) or
        (scheme == "http" and parsed.port == 80)
    ) else ""
    path = parsed.path.rstrip("/") if parsed.path else "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{scheme}://{host}{port}{path}{query}"


async def fetch_html(url: str) -> str:
    logger.info("[Parser] Fetching %s", url)
    try:
        async with httpx.AsyncClient(
            timeout=settings.fetch_timeout,
            follow_redirects=True,
        ) as client:
            response = await client.get(
                url,
                headers={"User-Agent": _USER_AGENT},
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                raise ParseError(
                    f"URL returned non-HTML content type: {content_type}"
                )
            content = response.text
            if len(content.encode("utf-8")) > settings.fetch_max_bytes:
                raise ParseError(
                    f"Response too large: {len(content)} bytes "
                    f"(max {settings.fetch_max_bytes})"
                )
            logger.info("[Parser] Fetched %d bytes from %s", len(content), url)
            return content
    except httpx.HTTPStatusError as e:
        raise ParseError(f"HTTP error {e.response.status_code} for {url}") from e
    except httpx.TimeoutException as e:
        raise ParseError(f"Timeout fetching {url}") from e
    except httpx.RequestError as e:
        raise ParseError(f"Request error for {url}: {e}") from e


def extract_content(html: str, url: str) -> tuple[str, str]:
    doc = Document(html)
    title = doc.title()
    cleaned = doc.summary()
    if not cleaned or not BeautifulSoup(cleaned, "lxml").get_text(strip=True):
        logger.warning(
            "[Parser] Readability returned empty/short content for %s, falling back to <body>", url
        )
        soup = BeautifulSoup(html, "lxml")
        body = soup.find("body")
        cleaned = str(body) if body else html
        if not title:
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else url
    if not title:
        title = url
    logger.info("[Parser] Extracted title=%s content_len=%d", title, len(cleaned))
    return title, cleaned


def _get_text_content(el: Tag) -> str:
    return el.get_text(strip=True)


def classify_blocks(cleaned_html: str) -> list[Block]:
    soup = BeautifulSoup(cleaned_html, "lxml")
    blocks: list[Block] = []

    for child in list(soup.children):
        blocks.extend(_classify_element(child))

    return blocks


def _classify_element(el: Tag) -> list[Block]:
    blocks: list[Block] = []
    if not isinstance(el, Tag):
        return blocks

    tag = el.name.lower() if el.name else ""

    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = int(tag[1])
        content = _inner_html(el)
        if content.strip():
            blocks.append(HeadingBlock(level=level, content=content.strip()))

    elif tag == "p":
        content = _inner_html(el)
        if content.strip():
            blocks.append(ParagraphBlock(content=content.strip()))

    elif tag == "pre":
        code_el = el.find("code") if el.find("code") else el
        content = code_el.get_text()
        lang = _detect_language(el)
        if content.strip():
            blocks.append(CodeBlock(content=content, language=lang))

    elif tag == "img":
        src = el.get("src", "")
        alt = el.get("alt", "")
        if src:
            blocks.append(ImageBlock(src=src, alt=alt))

    elif tag in ("ul", "ol"):
        items = []
        for li in el.find_all("li"):
            items.append(_inner_html(li))
        items = [i for i in items if i.strip()]
        if items:
            blocks.append(ListBlock(items=items, ordered=(tag == "ol")))

    elif tag == "blockquote":
        content = _inner_html(el)
        if content.strip():
            blocks.append(QuoteBlock(content=content.strip()))

    elif tag == "figure":
        img = el.find("img")
        pre = el.find("pre")
        if img:
            src = img.get("src", "")
            alt = img.get("alt", "")
            if src:
                blocks.append(ImageBlock(src=src, alt=alt))
        elif pre:
            code_el = pre.find("code") if pre.find("code") else pre
            content = code_el.get_text()
            lang = _detect_language(pre)
            if content.strip():
                blocks.append(CodeBlock(content=content, language=lang))

    elif tag in ("div", "section", "article", "html", "body"):
        for child in list(el.children):
            blocks.extend(_classify_element(child))

    elif tag in ("hr", "br", "nav", "aside", "footer", "header", "script", "style", "form", "button", "input"):
        pass

    else:
        logger.debug("[Parser] Skipping unknown tag: <%s>", tag)

    return blocks


def _inner_html(el: Tag) -> str:
    return "".join(str(c) for c in el.children)


def _detect_language(el: Tag) -> str | None:
    classes = el.get("class", [])
    if isinstance(classes, str):
        classes = classes.split()
    for cls in classes:
        match = re.match(r"(?:language|lang|brush)[-:]\s*(\w+)", cls, re.IGNORECASE)
        if match:
            return match.group(1).lower()
    return None


async def parse_article(url: str) -> tuple[str, str, list[Block]]:
    url = _normalize_url(url)
    raw_html = await fetch_html(url)
    title, cleaned_html = extract_content(raw_html, url)
    blocks = classify_blocks(cleaned_html)
    logger.info("[Parser] Parsed %s: %d blocks", url, len(blocks))
    return raw_html, title, blocks
