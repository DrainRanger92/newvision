# M3 — Translation: LLM EN→RU, Lazy + Cache

**Milestone**: Translation — EN→RU through DeepSeek API, lazy loading with SQLite cache
**Status**: Planning
**Created**: 2026-06-17
**Depends on**: M1 (Skeleton) ✅, M2 (Parser) ✅

---

## 1. Library Decisions

| # | Purpose | Choice | Justification |
|---|---------|--------|---------------|
| 1 | DeepSeek API client | **openai** Python package (OpenAI-compatible mode) | Async-native (`AsyncOpenAI`), built-in retries with exponential backoff (2 retries by default), rate-limit handling, battle-tested — vs raw httpx: 3x less code, no retry boilerplate |
| 2 | Single vs batch translation | **Both**: `/api/translate` (1 block) for first-swipe + `/api/translate/batch` (N blocks) for preload | Single-block = minimal latency for first interaction (~0.8s). Batch = 1 LLM call for 3 blocks, 3x cheaper, ideal for scroll-ahead preload per TZ §51 |
| 3 | Translation prompt strategy | **System prompt** + numbered block markers in user message for batch | System prompt sets the translator role once; numbered `---BLOCK N---` separators let LLM return structured output. Technical term preservation via explicit instruction (see §2.2) |
| 4 | Inline `<code>` placeholder | **`__CC_{index}__`** (e.g. `__CC_0__`, `__CC_1__`) | Short, regex-friendly, contains no HTML entities or Unicode that LLM would mangle. Unlikely to appear in natural English text. Survives tokenization. Simple `re.sub` for extract/restore |
| 5 | Translation cache key | **(article_id, block_index)** with `text_hash` for invalidation | Matches API shape (frontend sends article_id + block_index). `text_hash` (SHA-256 of original plain text) detects content drift on re-parse — same index, different text → re-translate |
| 6 | Failure handling | **openai built-in retry (2 attempts, exponential backoff) + 5s total timeout** via `httpx.Timeout` on the underlying client. On exhaustion → return original English text + `error=True` flag | 5s fits the <1.5s TZ budget for single blocks. Returning original text keeps UX working (curtain shows English as fallback) rather than crashing |

**Why NOT these alternatives:**
- *httpx direct HTTP to DeepSeek*: would need manual retry logic, error parsing, streaming support — ~40 lines extra code vs 5 with openai package
- *Batch only*: first-swipe would wait for N blocks to translate together — violates laziness requirement from TZ §49
- *Google Translate / DeepL*: explicitly forbidden by AGENTS.md rule 9 — LLM only
- *hash(original_text) as sole cache key*: requires frontend to compute/send hash — unnecessary indirection when article_id + block_index is already canonical

---

## 2. Subtasks

### T1: Config + env — `backend/config.py` + `backend/.env.example`

**Scope**: Add DeepSeek API key and translation model to settings. Add `openai` to requirements.txt.

**Changes**:
- `backend/config.py`: add `deepseek_api_key: str = ""`, `translation_model: str = "deepseek-chat"`
- `backend/.env.example`: add `DEEPSEEK_API_KEY=` and `# TRANSLATION_MODEL=deepseek-chat` (commented, default in code)
- `backend/requirements.txt`: add `openai>=1.0.0`

**Acceptance**:
- `python -c "from backend.config import settings; assert hasattr(settings, 'deepseek_api_key')"` succeeds
- `python -c "from openai import AsyncOpenAI"` succeeds (after pip install)
- `pip install -r backend/requirements.txt` passes in clean venv

---

### T2: Pydantic models — extend `backend/models.py`

**Scope**: Add request/response models for the translate endpoints.

**New models**:

```python
class TranslateRequest(BaseModel):
    article_id: str
    block_index: int

class BatchTranslateRequest(BaseModel):
    article_id: str
    block_indices: list[int]       # 1–10 blocks for preload

class TranslateResponse(BaseModel):
    article_id: str
    block_index: int
    block_type: BlockType
    translated_text: str            # for list blocks: items joined with \n
    cached: bool                    # True = served from DB, False = fresh LLM call
    error: bool = False             # True = translation failed, original text returned

class BatchTranslateResponse(BaseModel):
    translations: list[TranslateResponse]
```

**Block-type gating (NOT in model, in endpoint logic)**:
- Translatable: `heading`, `paragraph`, `list`, `quote`
- Rejected (400): `code`, `image`

**Acceptance**:
- All models instantiate and serialize to valid JSON
- `python -c "from backend.models import TranslateRequest, TranslateResponse, BatchTranslateRequest, BatchTranslateResponse"` succeeds
- Discriminated union in existing models untouched (M2 regression check): `python -c "from backend.models import Article, Block, BlockType; print('OK')"`

---

### T3: Translation engine — `backend/translator.py` (NEW)

**Scope**: Core translation logic — code tag extraction/restoration, HTML stripping, DeepSeek API calls, batch assembly.

**Functions**:

1. **`_extract_code_tags(html: str) -> tuple[str, list[str]]`**
   - Regex: find all `<code[^>]*>.*?</code>` (dotall, non-greedy)
   - Replace each with `__CC_{i}__` where `i` = sequential index
   - Return `(text_with_placeholders, [code_1_html, code_2_html, ...])`

2. **`_restore_code_tags(text: str, codes: list[str]) -> str`**
   - Regex: find `__CC_{i}__` → replace with `codes[i]`
   - Undoes `_extract_code_tags`

3. **`_html_to_plain_text(html: str) -> str`**
   - `BeautifulSoup(html, "lxml").get_text(separator=" ")` — strip all HTML tags, join text nodes with space
   - Collapse multiple whitespace to single space
   - Strip leading/trailing whitespace

4. **`_get_translatable_text(block: Block) -> str`**
   - Switch on block type:
     - HeadingBlock / ParagraphBlock / QuoteBlock → `block.content` (inner HTML)
     - ListBlock → `"\n".join(block.items)` (join list items with newline)
   - Returns the raw HTML to be translated

5. **`_build_translation_prompt(text: str) -> list[dict]`**
   - Returns messages list for OpenAI chat completions API:
     ```python
     [
         {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
         {"role": "user", "content": text}
     ]
     ```
   - `TRANSLATION_SYSTEM_PROMPT` (module-level constant):
     ```
     You are a technical translator. Translate the following English text to Russian.
     Rules:
     1. Keep ALL markers like __CC_0__, __CC_1__ exactly as-is — never modify, translate, or remove them.
     2. Preserve technical terms: API names, function names, variable names, class names, library names — keep in English.
     3. Preserve URLs, numbers, and HTML entities exactly as-is.
     4. Preserve the original line breaks and paragraph structure.
     5. Return ONLY the translated text. No explanations, no notes, no markdown formatting.
     ```

6. **`_build_batch_prompt(texts: list[str]) -> list[dict]`**
   - Joins texts with `\n\n---BLOCK {i}---\n\n` separator
   - System prompt adds: "Each block is separated by '---BLOCK N---'. Preserve these separators in your response."
   - Returns messages list

7. **`async def translate_text(text: str, model: str = "deepseek-chat") -> str`**
   - Core LLM call: create `AsyncOpenAI(api_key=..., base_url="https://api.deepseek.com/v1")`, call `chat.completions.create()`
   - Temperature=0.1 (low temp for consistent translations)
   - Timeout: 5s via `httpx.Timeout(5.0, connect=3.0)` on the client
   - On any exception → log warning, re-raise as `TranslationError`
   - Returns `response.choices[0].message.content`

8. **`async def translate_block(article_id: str, block_index: int, block: Block, model: str) -> tuple[str, bool, bool]`**
   - Orchestrator for single block: extract code → strip HTML → check cache → call LLM → restore code → save cache
   - Returns `(translated_text, cached, error)`
   - Rejects non-translatable types with `ValueError`

9. **`async def translate_blocks_batch(article_id: str, blocks: list[tuple[int, Block]], model: str) -> list[tuple[int, str, bool, bool]]`**
   - Orchestrator for batch: for each block → extract code + strip HTML → check cache → if all cached → return; if some need translation → build batch prompt → call LLM once → parse response by separators → restore code for each → save all to cache
   - Returns `[(block_index, translated_text, cached, error), ...]`

**Constants** (module-level):
```python
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
CODE_PLACEHOLDER_RE = re.compile(r"__CC_(\d+)__")
CODE_TAG_RE = re.compile(r"<code[^>]*>.*?</code>", re.DOTALL)
BLOCK_SEPARATOR_RE = re.compile(r"---BLOCK\s+(\d+)---")
TRANSLATION_SYSTEM_PROMPT = "..."  # (as defined above)
```

**Error model**:
```python
class TranslationError(Exception):
    """Raised when translation fails (API error, timeout, empty response)."""
    pass
```

**Acceptance**:
- `_extract_code_tags('<p>Use <code>asyncio.run()</code> in Python</p>')` → `('<p>Use __CC_0__ in Python</p>', ['<code>asyncio.run()</code>'])`
- `_restore_code_tags('Use __CC_0__ in Python', ['<code>asyncio.run()</code>'])` → `'Use <code>asyncio.run()</code> in Python'`
- `_html_to_plain_text('<p>Hello <strong>world</strong></p>')` → `'Hello world'`
- `translate_text("Hello world")` returns non-empty Russian string (requires DEEPSEEK_API_KEY in .env)
- `translate_block(...)` rejects `CodeBlock` and `ImageBlock` with ValueError
- Translation of same text twice → second call uses cache (checked via translate_block)
- `python -c "from backend.translator import translate_text, translate_block, TranslationError"` succeeds

---

### T4: Database layer — extend `backend/db.py`

**Scope**: Add `translations` table and CRUD functions. Extend `init_db()` to create the new table.

**New schema** (add to `init_db()` after existing `articles` table):
```sql
CREATE TABLE IF NOT EXISTS translations (
    article_id TEXT NOT NULL,
    block_index INTEGER NOT NULL,
    text_hash TEXT NOT NULL,
    original_text TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    model TEXT NOT NULL,
    translated_at TEXT NOT NULL,
    PRIMARY KEY (article_id, block_index)
);
CREATE INDEX IF NOT EXISTS idx_translations_lookup ON translations(article_id, block_index);
```

**New functions**:

1. **`async def get_translation(article_id: str, block_index: int, text_hash: str | None = None) -> str | None`**
   - Lookup by (article_id, block_index)
   - If `text_hash` provided and stored hash ≠ provided hash → return `None` (stale cache, needs re-translate)
   - Otherwise return `translated_text`
   - Return `None` if no row found

2. **`async def save_translation(article_id: str, block_index: int, original_text: str, translated_text: str, model: str) -> None`**
   - Compute `text_hash = hashlib.sha256(original_text.encode()).hexdigest()[:16]` (16-char hex, sufficient for dedup)
   - `INSERT OR REPLACE INTO translations ...`
   - `translated_at` = `datetime.now(UTC).isoformat()`

3. **`async def get_translations_batch(article_id: str, block_indices: list[int]) -> dict[int, str]`**
   - `SELECT block_index, translated_text FROM translations WHERE article_id = ? AND block_index IN ({placeholders})`
   - Returns `{block_index: translated_text}` for cached blocks only

**Acceptance**:
- `python -c "from backend.db import get_translation, save_translation, get_translations_batch"` succeeds
- Save translation → get same translation back → matches
- Get non-existent translation → returns `None`
- `get_translation` with stale `text_hash` → returns `None` (text changed)
- `get_translations_batch` returns only cached blocks, not all requested
- Existing M2 functions (`get_article_by_url`, `save_article`) still work unchanged

---

### T5: API endpoints — extend `backend/main.py`

**Scope**: Add two POST endpoints under `/api/translate` and `/api/translate/batch`. No changes to existing endpoints.

**New endpoints**:

1. **`POST /api/translate`**
   - Request: `TranslateRequest` (article_id, block_index)
   - Logic:
     1. `get_article_by_id(article_id)` → 404 if not found
     2. Get `block = article.blocks[block_index]` → 400 if index out of range
     3. Check block type → 400 if `code` or `image` type
     4. Call `translate_block(article_id, block_index, block, settings.translation_model)`
     5. Return `TranslateResponse` with `translated_text`, `cached`, `error` flags
   - Error responses:
     - 404: article not found
     - 400: non-translatable block type (`{"detail": "Block type 'code' cannot be translated"}`)
     - 400: block_index out of range
     - 503: TranslationError (API unavailable)

2. **`POST /api/translate/batch`**
   - Request: `BatchTranslateRequest` (article_id, block_indices)
   - Logic:
     1. `get_article_by_id(article_id)` → 404
     2. Filter: skip code/image blocks (silently — log warning, don't fail)
     3. Valid indices: 400 if none valid after filtering
     4. Call `translate_blocks_batch(article_id, valid_blocks, model)`
     5. Return `BatchTranslateResponse` with array of `TranslateResponse`
   - Constraints: max 10 block_indices per request (400 if exceeded)
   - Error responses: same as single + 400 for too many indices

**Logging** (structured, semantic anchors):
- `[Translator] Cache hit for article={id} block={n}`
- `[Translator] Translating article={id} block={n} ({len} chars, type={type})`
- `[Translator] Batch: {n} blocks, {cached} cached, translating {to_translate}`
- `[Translator] Translation failed for article={id} block={n}: {error}`

**Acceptance**:
- `curl -X POST .../api/translate -d '{"article_id":"...","block_index":0}'` → returns `TranslateResponse` with RU text for a paragraph block
- Same request again → `cached: true`
- Code block request → 400 with message about non-translatable type
- `POST /api/translate/batch` with 3 paragraph indices → returns 3 `TranslateResponse` entries
- `/health` still returns `{"status": "ok"}`
- `/api/parse` still works (M2 not broken)

---

### T6: Smoke test (MANUAL — no test framework)

**Prerequisites**:
- `DEEPSEEK_API_KEY=sk-...` set in `backend/.env`
- Backend running on `localhost:8000`
- Python venv with `pip install -r backend/requirements.txt`

**Procedure** (exact commands):

```bash
# === SETUP ===
cd curtain-reader

# Ensure DEEPSEEK_API_KEY is set
grep DEEPSEEK_API_KEY backend/.env || echo "FAIL: DEEPSEEK_API_KEY not set in .env"

# Verify imports (M1+M2 not broken)
python -c "from backend.bot import router; print('PASS: bot import')"
python -c "from backend.models import Article, Block, BlockType,TranslateRequest,TranslateResponse; print('PASS: models import')"
python -c "from backend.db import init_db, get_article_by_url, get_translation, save_translation; print('PASS: db import')"
python -c "from backend.parser import parse_article; print('PASS: parser import')"
python -c "from backend.translator import translate_text, translate_block, TranslationError; print('PASS: translator import')"

# Start server
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
sleep 2

# === TEST 1: Health (M1 regression) ===
curl -sf http://localhost:8000/health | python -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='ok'; print('PASS: /health')"

# === TEST 2: Parse article (M2 regression) ===
curl -sf -X POST http://localhost:8000/api/parse \
  -H "Content-Type: application/json" \
  -d '{"url":"https://realpython.com/async-io-python/"}' \
  -o /tmp/m3_article.json

python -c "
import json
d = json.load(open('/tmp/m3_article.json'))
assert d['title'], 'FAIL: no title'
types = {b['type'] for b in d['blocks']}
assert 'paragraph' in types, 'FAIL: no paragraphs'
assert 'code' in types, 'FAIL: no code blocks'
print(f'PASS: parse ({len(d[\"blocks\"])} blocks)')
print(f'  article_id: {d[\"id\"]}')
"

# === TEST 3: Translate first text block (paragraph) ===
ARTICLE_ID=$(python -c "import json; print(json.load(open('/tmp/m3_article.json'))['id'])")

# Find first paragraph block index
BLOCK_IDX=$(python -c "
import json
blocks = json.load(open('/tmp/m3_article.json'))['blocks']
idx = next(i for i,b in enumerate(blocks) if b['type']=='paragraph')
print(idx)
")

echo "Translating block $BLOCK_IDX of article $ARTICLE_ID..."

curl -sf -X POST http://localhost:8000/api/translate \
  -H "Content-Type: application/json" \
  -d "{\"article_id\":\"$ARTICLE_ID\",\"block_index\":$BLOCK_IDX}" \
  -o /tmp/m3_translate.json

python -c "
import json, time
d = json.load(open('/tmp/m3_translate.json'))
assert d['block_type'] == 'paragraph', f'FAIL: wrong type {d[\"block_type\"]}'
assert d['cached'] == False, 'FAIL: should not be cached on first call'
assert d['error'] == False, 'FAIL: translation error'
assert len(d['translated_text']) > 10, f'FAIL: translation too short ({len(d[\"translated_text\"])} chars)'
# Basic RU check: should contain Cyrillic characters
assert any(0x0400 <= ord(c) <= 0x04FF for c in d['translated_text']), 'FAIL: no Cyrillic chars in translation'
print(f'PASS: translate block {d[\"block_index\"]}')
print(f'  Original: {d.get(\"original_text\", \"?\")[:80]}...')
print(f'  Translation: {d[\"translated_text\"][:80]}...')
"

# === TEST 4: Cache hit (same block, instant) ===
START=$(python -c "import time; print(time.time())")
curl -sf -X POST http://localhost:8000/api/translate \
  -H "Content-Type: application/json" \
  -d "{\"article_id\":\"$ARTICLE_ID\",\"block_index\":$BLOCK_IDX}" \
  -o /tmp/m3_translate2.json
ELAPSED=$(python -c "import time; print(f'{time.time() - $START:.3f}')")

python -c "
import json
d = json.load(open('/tmp/m3_translate2.json'))
assert d['cached'] == True, 'FAIL: should be cached'
assert d['error'] == False, 'FAIL: error on cached'
print(f'PASS: cache hit ({float($ELAPSED)*1000:.0f}ms)')
"

# Verify cache hit < 50ms
python -c "assert float($ELAPSED) < 0.050, f'FAIL: cache too slow ({float($ELAPSED)*1000:.0f}ms)'; print('PASS: cache < 50ms')"

# === TEST 5: Code block rejected ===
CODE_IDX=$(python -c "
import json
blocks = json.load(open('/tmp/m3_article.json'))['blocks']
idx = next(i for i,b in enumerate(blocks) if b['type']=='code')
print(idx)
")

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/translate \
  -H "Content-Type: application/json" \
  -d "{\"article_id\":\"$ARTICLE_ID\",\"block_index\":$CODE_IDX}")

python -c "assert '$HTTP_CODE' == '400', f'FAIL: expected 400 for code block, got $HTTP_CODE'; print('PASS: code block rejected (400)')"

# === TEST 6: Batch translate (3 text blocks for preload) ===
python -c "
import json
blocks = json.load(open('/tmp/m3_article.json'))['blocks']
text_indices = [i for i,b in enumerate(blocks) if b['type'] in ('paragraph','heading')][:3]
print(','.join(str(i) for i in text_indices))
" > /tmp/m3_batch_indices.txt

BATCH_INDICES=$(cat /tmp/m3_batch_indices.txt)

curl -sf -X POST http://localhost:8000/api/translate/batch \
  -H "Content-Type: application/json" \
  -d "{\"article_id\":\"$ARTICLE_ID\",\"block_indices\":[$BATCH_INDICES]}" \
  -o /tmp/m3_batch.json

python -c "
import json
d = json.load(open('/tmp/m3_batch.json'))
translations = d['translations']
assert len(translations) == 3, f'FAIL: expected 3 translations, got {len(translations)}'
for t in translations:
    assert t['error'] == False, f'FAIL: error on block {t[\"block_index\"]}'
    assert len(t['translated_text']) > 10, f'FAIL: short translation for block {t[\"block_index\"]}'
    assert any(0x0400 <= ord(c) <= 0x04FF for c in t['translated_text']), f'FAIL: no Cyrillic for block {t[\"block_index\"]}'
print(f'PASS: batch translate (3 blocks)')
for t in translations:
    print(f'  Block {t[\"block_index\"]} ({t[\"block_type\"]}): cached={t[\"cached\"]}, {len(t[\"translated_text\"])} chars')
"

# === TEST 7: Inline code preservation (visual check) ===
echo ""
echo "=== Inline code preservation (manual visual check) ==="
python -c "
import json
d = json.load(open('/tmp/m3_translate.json'))
text = d['translated_text']
# Should contain <code> tags if original had them
has_code = '<code>' in text
print(f'  Translation has <code> tags: {has_code}')
print(f'  Translation snippet: {text[:200]}')
"

# === TEST 8: Verify M2 endpoints still work ===
curl -sf "http://localhost:8000/api/articles/$ARTICLE_ID" | python -c "import sys,json; d=json.load(sys.stdin); assert d['id']=='$ARTICLE_ID'; print('PASS: GET /api/articles/{id} still works')"

# === CLEANUP ===
kill %1
rm -f data/curtain_reader.db  # fresh state for next run
```

**Expected results**: All 8 tests PASS. Translation contains Cyrillic text. Cache hit < 50ms. Code blocks rejected with 400. M1+M2 endpoints unaffected.

---

## 3. File Blueprint

```
backend/
├── models.py          # MODIFY — add TranslateRequest, BatchTranslateRequest, TranslateResponse, BatchTranslateResponse
├── db.py              # MODIFY — extend init_db() with translations table, add get_translation, save_translation, get_translations_batch
├── translator.py      # NEW — _extract_code_tags, _restore_code_tags, _html_to_plain_text, translate_text, translate_block, translate_blocks_batch, TranslationError, TRANSLATION_SYSTEM_PROMPT
├── main.py            # MODIFY — add POST /api/translate + POST /api/translate/batch endpoints
├── config.py          # MODIFY — add deepseek_api_key, translation_model
├── requirements.txt   # MODIFY — add openai>=1.0.0
├── bot.py             # UNCHANGED
├── parser.py          # UNCHANGED
├── .env.example       # MODIFY — add DEEPSEEK_API_KEY, TRANSLATION_MODEL
└── __init__.py        # UNCHANGED
```

**No new directories.** No new infrastructure.

**Key invariants preserved:**
- Global `_db: aiosqlite.Connection | None` pattern in `db.py` — extended, not replaced
- `init_db()` called once in FastAPI lifespan — extended to create translations table
- All existing endpoints (`/health`, `POST /api/parse`, `GET /api/articles/{id}`) unchanged
- All existing models (`Article`, `Block`, `ParseRequest`) unchanged
- `parse_article()` signature unchanged → `tuple[str, str, list[Block]]`

---

## 4. Smoke Test Procedure

Same as T6 above. Summary:

| Test | Command | Expected |
|------|---------|----------|
| 1. Health | `curl /health` | `{"status":"ok"}` |
| 2. Parse | `POST /api/parse` realpython.com | 200 + blocks array |
| 3. Translate single | `POST /api/translate` paragraph block | RU text, `cached:false`, `error:false` |
| 4. Cache hit | Same request again | `cached:true`, <50ms total |
| 5. Code block reject | Translate a code block | HTTP 400 |
| 6. Batch translate | `POST /api/translate/batch` 3 blocks | 3 translations with RU text |
| 7. Inline code | Manual check | `<code>` tags preserved in output |
| 8. M2 regression | `GET /api/articles/{id}` | Still returns article |

**PORT**: 8000 (matches existing config and Dockerfile)

---

## 5. Risks

| # | Risk | Impact | Mitigation |
|---|------|--------|------------|
| 1 | **DeepSeek API returns non-RU text** (hallucination, wrong language, English echoed back) | Curtain shows wrong translation, user confused | Low temperature (0.1) minimizes this. System prompt explicitly says "Translate to Russian". Smoke test verifies Cyrillic characters in output. If it happens: API returns `error=True`, frontend (M5) shows "Перевод недоступен" |
| 2 | **LLM mangles `__CC_N__` placeholders** (removes, renumbers, translates "CC" as "carbon copy") | Inline `<code>` content lost or corrupted in translation | Two-stage defense: (a) system prompt explicitly says "keep ALL __CC_N__ markers exactly as-is", (b) post-restoration validation — if any placeholder index is missing, return error. Also: markers like `__CC_7__` are unlikely tokens for LLM to "translate" |
| 3 | **Batch response parsing fails** (LLM returns blocks in wrong order, merges blocks, or omits `---BLOCK N---` separators) | Batch translation returns garbage or partial results | Three-stage defense: (a) numbered separators are unambiguous, (b) validate response has N blocks matching input, (c) on parse failure → fall back to sequential single-block translations for each uncached block. Log warning with raw LLM response for debugging |
| 4 | **DeepSeek API key missing or invalid** | All translate endpoints return 503 | Startup check: in lifespan, if `deepseek_api_key` is empty, log warning (don't crash). Translate endpoints return 503 with clear message. Frontend (M5) handles gracefully |
| 5 | **openai package incompatible with DeepSeek endpoint** (API drift, auth header format, response format) | Translation broken entirely | DeepSeek explicitly documents OpenAI-compatible API (`https://api.deepseek.com/v1`). openai Python package supports custom `base_url` via `AsyncOpenAI(base_url=...)`. Verified working pattern across community reports. Smoke test catches any issues immediately |

---

## 6. Open Questions

None blocking. Proceed with these defaults:

- **Translation model**: `deepseek-chat` — confirmed in AGENTS.md as runtime translation model. Configurable via `TRANSLATION_MODEL` env var for future model changes.
- **Batch separator format**: `\n\n---BLOCK N---\n\n` — double newlines ensure LLM treats blocks as separate sections. Index `N` is 0-based for code consistency.
- **text_hash algorithm**: SHA-256 first 16 hex chars — handles texts up to ~10KB without collision risk. 16 chars = 64 bits, birthday bound ~4B texts before collision — acceptable for a single-user cache.
- **List block translation**: items joined with `\n` for translation, returned as a single `translated_text` string with newlines. Frontend (M5) splits and renders. Simpler than per-item translation rows.
- **Max batch size**: 10 blocks — prevents oversized LLM prompts (10 blocks × ~500 chars = 5000 chars). Batch endpoint returns 400 for >10 indices.
- **Client lifecycle**: `AsyncOpenAI` instance created per-request (not global). FastAPI's async model means connections are pooled by httpx under the hood. For a single-user app, per-request creation is fine (<1ms overhead). Can optimize to module-level singleton later if needed.
- **No frontend changes in M3**: Translation endpoints are built and tested entirely via curl. Frontend integration (calling these APIs from CurtainBlock) is M5 scope.
- **TTL on translations**: None for MVP. Translations cached indefinitely (same as articles). `translated_at` field stored for future TTL logic.
