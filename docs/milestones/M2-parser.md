# M2 — Parser: URL → Structured Blocks + Cache

**Milestone**: Parser — URL → массив блоков, кэш статей
**Status**: Planning
**Created**: 2026-06-17
**Depends on**: M1 (Skeleton) ✅

---

## 1. Library Decisions

| Purpose | Choice | Justification |
|---|---|---|
| HTTP fetching | **httpx** | Async-native, same API surface as requests, HTTP/2 support, fits FastAPI async model |
| Content extraction (reader-mode) | **readability-lxml** | Mozilla's readability algorithm ported to Python — best-in-class main-content detection, strips nav/ads/sidebars |
| HTML parsing & block classification | **beautifulsoup4** (with **lxml** backend) | Ergonomic tree walking for tag classification; lxml C-parser for speed; already pulled in by readability-lxml |
| SQLite driver | **aiosqlite** | Async wrapper around sqlite3 — no event loop blocking, small dependency, fits async-first architecture |

**Why NOT these alternatives:**
- *trafilatura*: excellent text extraction but returns flat text/markdown — loses the block structure (headings, code, lists) we need to classify
- *newspaper3k*: sync-only, heavy, unreliable on modern JS-heavy sites, poor async support
- *selectolax*: 10-100x faster than bs4 but less ergonomic API; speed not needed for single-article parsing (<100ms either way)
- *sqlite3 (sync)*: would block event loop on queries; aiosqlite is a thin wrapper with zero trade-offs

---

## 2. Subtasks

### T1: Pydantic models — `backend/models.py`

**Scope**: Create `backend/models.py` with all data models for articles and blocks.

**Models**:
- `BlockType` — enum: `heading`, `paragraph`, `code`, `image`, `list`, `quote`
- Discriminated union `Block` with typed variants:
  - `HeadingBlock`: `type="heading"`, `level: int` (1-6), `content: str` (HTML, inline `<code>` preserved)
  - `ParagraphBlock`: `type="paragraph"`, `content: str` (HTML, inline `<code>` preserved)
  - `CodeBlock`: `type="code"`, `content: str` (plain text, original formatting), `language: str | None`
  - `ImageBlock`: `type="image"`, `src: str`, `alt: str`
  - `ListBlock`: `type="list"`, `items: list[str]` (each item is HTML string), `ordered: bool`
  - `QuoteBlock`: `type="quote"`, `content: str` (HTML)
- `Article`: `id: str` (uuid4), `url: str`, `title: str`, `blocks: list[Block]`, `fetched_at: datetime`
- `ParseRequest`: `url: str` (validated with HttpUrl)
- `ArticleResponse`: API response schema (excludes raw HTML)

**Acceptance**:
- `python -c "from backend.models import Article, Block, BlockType"` succeeds
- All models serialize to JSON cleanly (no datetime serialization errors)
- Discriminated union round-trips: `Article.model_validate_json(article.model_dump_json())` works

---

### T2: SQLite database layer — `backend/db.py`

**Scope**: Create `backend/db.py` with async SQLite operations for article caching.

**Schema**:
```sql
CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    html TEXT NOT NULL,
    blocks_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url);
```

**Functions**:
- `init_db()` — create tables on startup (called from FastAPI lifespan)
- `get_article_by_url(url: str) -> Article | None` — cache lookup
- `get_article_by_id(article_id: str) -> Article | None` — ID lookup
- `save_article(article: Article, raw_html: str) -> None` — insert parsed article
- `close_db()` — close connection on shutdown

**Config**: DB path from `settings.db_path` (default: `data/curtain_reader.db`). Create parent directory if not exists.

**Acceptance**:
- `init_db()` creates the `data/` directory and SQLite file
- Save an article → retrieve by URL → same data back
- Retrieve by URL when not cached → returns `None`
- Retrieve by ID works
- All operations are async (no event loop blocking)

---

### T3: Article parser — `backend/parser.py`

**Scope**: Create `backend/parser.py` with the full pipeline: fetch → extract → classify.

**Functions**:
- `fetch_html(url: str) -> str` — async HTTP GET with httpx
  - User-Agent: `"CurtainReader/1.0 (+https://github.com/curtain-reader)"`
  - Timeout: 10 seconds
  - Follow redirects
  - Raise `ParseError` on HTTP errors, timeouts, non-HTML content types
  - Max response size: 10MB (reject larger pages)

- `extract_content(html: str, url: str) -> tuple[str, str]` — readability extraction
  - Returns `(title, cleaned_html)` — the main content HTML with nav/ads/sidebars removed
  - If readability returns empty: fallback to `<body>` content with warning log
  - Title: from readability, fallback to `<title>` tag, fallback to URL

- `classify_blocks(cleaned_html: str) -> list[Block]` — walk HTML tree, produce typed blocks
  - Use bs4 to iterate over children of the content container
  - Classification rules:
    - `<h1>`–`<h6>` → `HeadingBlock` (level from tag name, content = inner HTML)
    - `<p>` → `ParagraphBlock` (content = inner HTML, preserves `<code>` spans)
    - `<pre>`, `<pre><code>` → `CodeBlock` (content = text only, language from class attr like `language-python`)
    - `<img>` (standalone, not inside `<p>`) → `ImageBlock` (src, alt)
    - `<ul>`, `<ol>` → `ListBlock` (items = list of `<li>` inner HTML, ordered from tag)
    - `<blockquote>` → `QuoteBlock` (content = inner HTML)
    - `<figure>` → inspect children: if contains `<img>` → ImageBlock; if `<pre>` → CodeBlock; else skip
    - `<div>`, `<section>`, `<article>` → recurse into children (unwrap containers)
    - Everything else → skip (hr, br, nav remnants, etc.)
  - Skip empty blocks (no text content after stripping whitespace)
  - Preserve order of appearance

- `parse_article(url: str) -> Article` — orchestrator
  - Calls fetch → extract → classify
  - Generates uuid4 for article ID
  - Returns complete `Article` object

**Error handling**:
- Custom `ParseError(Exception)` with message
- `fetch_html`: httpx.HTTPStatusError → ParseError, httpx.TimeoutException → ParseError
- `extract_content`: empty result → fallback + log warning
- `classify_blocks`: unknown tags → skip silently (log at DEBUG level)

**Acceptance**:
- `parse_article("https://realpython.com/async-io-python/")` returns Article with:
  - Non-empty title
  - Mix of HeadingBlock, ParagraphBlock, CodeBlock (at minimum)
  - CodeBlock.content preserves original formatting (indentation, newlines)
  - No navigation, ads, or sidebar content in blocks
- `parse_article("https://httpbin.org/status/404")` raises ParseError
- Inline `<code>` within `<p>` is preserved in ParagraphBlock.content as HTML

---

### T4: API endpoints — extend `backend/main.py`

**Scope**: Add two endpoints to the FastAPI app.

**Endpoints**:

1. `POST /api/parse`
   - Request body: `{"url": "https://..."}`
   - Logic:
     1. Normalize URL (strip trailing slash, lowercase scheme/host)
     2. Check DB cache: `get_article_by_url(normalized_url)`
     3. If cached → return immediately (log: `[Parser] Cache hit for {url}`)
     4. If not cached → `parse_article(url)` → save to DB → return (log: `[Parser] Parsed {url} in {elapsed:.2f}s`)
   - Response: `ArticleResponse` (id, url, title, blocks, fetched_at)
   - Errors: `ParseError` → 422 with detail message; invalid URL → 422

2. `GET /api/articles/{article_id}`
   - Logic: `get_article_by_id(article_id)`
   - If found → return `ArticleResponse`
   - If not found → 404

**Router setup**: Use `APIRouter(prefix="/api", tags=["articles"])` included in main app.

**Lifespan update**: Call `init_db()` on startup, `close_db()` on shutdown (add to existing lifespan context manager).

**Acceptance**:
- `curl -X POST http://localhost:8000/api/parse -H "Content-Type: application/json" -d '{"url":"https://realpython.com/async-io-python/"}'` returns JSON with blocks array
- Same request a second time returns instantly (cache hit, < 50ms)
- `GET /api/articles/{id}` returns the same article
- `GET /api/articles/nonexistent` returns 404
- `POST /api/parse` with invalid URL returns 422
- `/health` still works (M1 not broken)

---

### T5: Config + dependencies update

**Scope**: Update `backend/config.py` and `backend/requirements.txt`.

**config.py changes**:
- Add `db_path: str = "data/curtain_reader.db"`
- Add `fetch_timeout: float = 10.0`
- Add `fetch_max_bytes: int = 10_000_000` (10MB)

**requirements.txt additions**:
```
httpx>=0.27.0
readability-lxml>=0.8.1
beautifulsoup4>=4.12.0
lxml>=5.0.0
aiosqlite>=0.20.0
```

**Acceptance**:
- `pip install -r backend/requirements.txt` succeeds in a clean venv
- `from backend.config import settings` works, new fields have defaults
- No import errors from any new dependency

---

### T6: Smoke test procedure

**Scope**: Manual verification with real articles.

**Test URLs** (chosen for diversity of block types):
1. `https://realpython.com/async-io-python/` — headings, paragraphs, code blocks, images, lists
2. `https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Using_promises` — headings, paragraphs, code, lists, notes/quotes
3. `https://realpython.com/fastapi-python-web-sockets/` — code-heavy article

**Acceptance** (all must pass):
- All 3 URLs parse successfully (< 3 seconds each)
- Block types include at minimum: heading, paragraph, code for each article
- Code blocks preserve indentation and newlines
- No navigation/sidebar/ad content in any block
- Second request for same URL is a cache hit (< 50ms)
- `GET /health` still returns `{"status": "ok"}`
- `python -c "from backend.bot import router"` still succeeds (bot imports clean)

---

## 3. File Blueprint

```
backend/
├── models.py          # NEW — Pydantic models: BlockType, Block (discriminated union), Article, ParseRequest, ArticleResponse
├── db.py              # NEW — aiosqlite: init_db, get_article_by_url, get_article_by_id, save_article, close_db
├── parser.py          # NEW — fetch_html, extract_content, classify_blocks, parse_article, ParseError
├── main.py            # MODIFY — add APIRouter /api/parse + /api/articles/{id}, init_db in lifespan
├── config.py          # MODIFY — add db_path, fetch_timeout, fetch_max_bytes
├── requirements.txt   # MODIFY — add httpx, readability-lxml, beautifulsoup4, lxml, aiosqlite
├── bot.py             # UNCHANGED
├── .env.example       # MODIFY — add DB_PATH example
└── __init__.py        # UNCHANGED
```

**New directories**:
- `data/` — created at runtime by `init_db()` for SQLite file (add to `.gitignore`)

---

## 4. Smoke Test Procedure

```bash
# 1. Install dependencies
cd curtain-reader
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r backend/requirements.txt

# 2. Verify imports (M1 not broken)
python -c "from backend.bot import router; print('PASS: bot import')"
python -c "from backend.models import Article, Block, BlockType; print('PASS: models import')"
python -c "from backend.db import init_db, get_article_by_url; print('PASS: db import')"
python -c "from backend.parser import parse_article; print('PASS: parser import')"

# 3. Start server
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
sleep 2

# 4. Health check (M1 still works)
curl -sf http://localhost:8000/health | grep '"ok"' && echo "PASS: health" || echo "FAIL: health"

# 5. Parse article (first time — fresh parse)
curl -sf -X POST http://localhost:8000/api/parse \
  -H "Content-Type: application/json" \
  -d '{"url":"https://realpython.com/async-io-python/"}' \
  | python -m json.tool > /tmp/parse_result.json

# Verify: has title, has blocks, blocks include heading + paragraph + code
python -c "
import json
data = json.load(open('/tmp/parse_result.json'))
assert data['title'], 'FAIL: no title'
types = {b['type'] for b in data['blocks']}
assert 'heading' in types, 'FAIL: no headings'
assert 'paragraph' in types, 'FAIL: no paragraphs'
assert 'code' in types, 'FAIL: no code blocks'
print(f'PASS: parsed {len(data[\"blocks\"])} blocks, types={types}')
print(f'  title: {data[\"title\"][:60]}')
print(f'  article_id: {data[\"id\"]}')
"

# 6. Parse same article again (cache hit — should be instant)
time curl -sf -X POST http://localhost:8000/api/parse \
  -H "Content-Type: application/json" \
  -d '{"url":"https://realpython.com/async-io-python/"}' \
  > /dev/null && echo "PASS: cache hit" || echo "FAIL: cache miss"

# 7. Get article by ID
ARTICLE_ID=$(python -c "import json; print(json.load(open('/tmp/parse_result.json'))['id'])")
curl -sf "http://localhost:8000/api/articles/$ARTICLE_ID" | grep '"blocks"' && echo "PASS: get by id" || echo "FAIL: get by id"

# 8. 404 for nonexistent article
curl -sf "http://localhost:8000/api/articles/nonexistent" && echo "FAIL: should 404" || echo "PASS: 404 correct"

# 9. Invalid URL
curl -sf -X POST http://localhost:8000/api/parse \
  -H "Content-Type: application/json" \
  -d '{"url":"not-a-url"}' && echo "FAIL: should reject" || echo "PASS: invalid URL rejected"

# 10. Cleanup
kill %1
```

**Expected**: All PASS. Total parse time for first request < 3s. Cache hit < 50ms.

---

## 5. Risks

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| 1 | readability-lxml fails on some sites (returns empty or wrong content) | Article shows no content or garbage | Fallback: if readability returns empty, extract `<body>` content directly. Log warning. Can refine per-site heuristics later. |
| 2 | Code block detection misses some patterns (e.g., `<code>` without `<pre>`, custom site markup) | Code rendered as paragraph text | Primary rule: `<pre>` or `<pre><code>` → code block. Secondary: `<code>` that is a direct child of content root (not inside `<p>`) → code block. Inline `<code>` inside `<p>` → preserved as HTML within paragraph. |
| 3 | Some sites block httpx User-Agent or require JS rendering | Parse fails for those sites | Use a realistic User-Agent string. Document that JS-rendered sites (SPAs) are out of scope for MVP — TZ targets "Real Python, MDN, blogs" which all serve server-rendered HTML. |

---

## 6. Open Questions

None blocking. Proceed with these defaults:

- **DB path**: `data/curtain_reader.db` (relative to project root, created at runtime)
- **Cache TTL**: none for MVP (articles cached indefinitely). `fetched_at` stored for future TTL logic.
- **URL normalization**: strip trailing slash, lowercase scheme+host, preserve path+query. Sufficient for dedup.
- **Article ID**: uuid4 (random, not URL-derived). Dedup handled by URL unique constraint.
- **API prefix**: `/api/` — matches existing Vite proxy config (`/api` → `localhost:8000`)
- **Block content format**: HTML strings (inner HTML). Preserves `<code>` spans for inline code. Frontend will render with `dangerouslySetInnerHTML` in M5/M6. Translator (M3) will strip `<code>` tags before translating.
