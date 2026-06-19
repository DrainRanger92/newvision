# M4 Bot Integration — Behavioral Specification

**Milestone**: Bot Integration — Telegram bot accepts URLs, returns Mini App button; reader page renders parsed articles

**Status**: Planning
**Created**: 2026-06-19
**Depends on**: M1 (Skeleton) ✅, M2 (Parser) ✅, M3 (Translation) ✅

---

## Goal

A user can send any English technical article URL to the Telegram bot and open it as a clean reader inside Telegram Mini App with one tap, with cached articles opening instantly.

## User Story

As a user learning English technical materials,  
I want to paste a URL into the Telegram bot and tap a button to open the article as a clean reader inside Telegram,  
so that I can read the article without distractions and prepare for the translation curtain feature (M5).

## Behavioral Requirements (Acceptance Criteria)

### Bot Behavior

- [ ] **URL acceptance**: When the user sends a text message containing a valid HTTP(S) URL to the bot, the bot accepts it. Messages without a valid URL receive a helpful text response asking the user to send a proper article URL.
- [ ] **Parsing on demand**: When the bot receives a valid URL, it triggers parsing of that URL using the existing article parsing infrastructure. The user does not need to invoke any additional commands beyond sending the URL.
- [ ] **Cache-aware response**: If the article was previously parsed and cached, the bot responds immediately without re-parsing. The user sees no difference in behavior between a fresh parse and a cache hit — only the response speed differs.
- [ ] **Mini App button**: The bot responds to a valid article URL with a message containing a single inline keyboard button (WebApp button) labelled with the article title. Tapping this button opens the article inside the Telegram Mini App.
- [ ] **Error handling**: If parsing fails (invalid URL, unreachable site, non-article page), the bot responds with a clear error message explaining what went wrong. The bot does not crash or produce an unhandled exception.
- [ ] **Non-URL messages**: Text messages that are not valid URLs receive a friendly reminder that the bot expects article URLs. Commands (`/start`, `/help`) still work as before.

### Mini App — Reader Page

- [ ] **Article reader entry point**: When the user taps the Mini App button from the bot chat, the Mini App opens to a reader page that displays the parsed article. The reader page knows which article to load based on information passed through the Mini App (e.g., via `initData` or URL parameters).
- [ ] **Title display**: The article title is displayed prominently at the top of the reader page.
- [ ] **Block rendering**: All article blocks are rendered in reading order: headings (with appropriate visual hierarchy based on level), paragraphs as flowing text, code blocks with distinct visual treatment (monospace font + background), images (with src as image source and alt text as fallback), lists (bulleted or numbered based on type), and quotes (with distinct indentation or styling).
- [ ] **Code block visual distinction**: Code blocks are visually distinct from regular text — rendered in monospace font with a distinct background color. No translation curtain is applied to code blocks (this is an M5 concern, but the block type distinction must be present in the renderer).
- [ ] **Image display**: Images from the article are displayed inline within the reading flow at their original positions.
- [ ] **Telegram theme awareness**: The reader page respects the Telegram color scheme (light/dark mode) using the Telegram Mini App SDK theme parameters.
- [ ] **Empty state**: If the article contains no blocks, the page shows an appropriate message indicating the article has no content to display.

### API Behavior

- [ ] **Article retrieval endpoint still works**: The existing `GET /api/articles/{article_id}` endpoint continues to serve full article data to the frontend. No new API endpoints are required for M4 unless the bot needs a new server-side action.
- [ ] **Existing endpoints unchanged**: All existing endpoints (`/health`, `POST /api/parse`, `POST /api/translate`, `POST /api/translate/batch`) remain functional and unchanged in their contract.

### Data Integrity

- [ ] **Article ID matching**: The article ID used in the Mini App URL matches the ID stored in the database, so the frontend can reliably fetch the article via the existing `GET /api/articles/{id}` endpoint.
- [ ] **No duplicate parsing**: Sending the same URL twice results in exactly one database entry (the cached one is reused). No duplicate articles are created.
- [ ] **Existing test suite passes**: All existing pytest tests (183 tests) continue to pass after the M4 changes.

## Architecture Notes

### GRACE Modules Involved

The following modules from `docs/grace/MODULE_MAP.md` participate in this milestone:

| Module | Layer | Role in M4 |
|--------|-------|------------|
| `bot` | Presentation | Accept URL messages, invoke parsing, return Mini App button |
| `main` | Presentation | Serves article data API; starts bot polling |
| `parser` | Application | Parses URLs into article blocks (existing, called by bot) |
| `db` | Data | Article cache lookup and save (existing, called by bot) |
| `models` | Domain | Article, Block, URL validation models (existing) |
| `config` | Data | Bot token, API settings (existing) |

### Dependency Changes

The `bot` module currently lists `depends_on: [config]` only. For M4, it needs to expand its dependencies to include modules it interacts with at the Presentation → Application and Presentation → Data layer boundaries:

- `bot` must have access to article parsing logic (Application layer — `parser` module)
- `bot` must have access to article cache lookup/save (Data layer — `db` module)  
- `bot` must use article and block types (Domain layer — `models` module)

This means the `bot` module's `depends_on` in the GRACE module map must be updated from `[config]` to `[config, parser, db, models]`.

### Layer Boundaries to Respect

1. **Presentation → Application**: `bot` calls `parser` for URL → article transformation. The bot does not contain parsing logic — it delegates to the parser module.
2. **Presentation → Data**: `bot` reads from `db` for cache checks and article retrieval. The bot does not contain SQL or database access patterns — it uses existing db functions.
3. **Presentation → Domain**: `bot` uses `models` types for type safety in its handlers. The bot does not redefine article or block types.
4. **Frontend → API**: The frontend reader page fetches article data via the existing HTTP API (`GET /api/articles/{id}`). It does not access the database directly.

### Frontend Routing

The Mini App opens with a reader page that reads the article ID from the Mini App launch context. This is a new page within the existing React SPA — it should be reachable via the Mini App initialization data, not via a separate build or deployment.

## Risks

| # | Risk | Impact | Mitigation |
|---|------|--------|------------|
| 1 | **BOT_TOKEN not provided** — user may not have a Telegram bot token configured in `.env` | Bot cannot start, entire M4 feature is blocked | Bot polls gracefully when token is missing (existing pattern in `start_bot_polling`). The reader page can be tested in browser dev mode without the bot. |
| 2 | **Mini App URL configuration** — the bot needs to know the Mini App's URL (its web app origin) to construct the `WebAppInfo` button | Bot cannot construct valid Mini App button | The Mini App URL must be configurable (e.g., via env var or config). Without it, the bot degrades gracefully (returns a plain link instead of a WebApp button, or tells the user the Mini App is not yet configured). |
| 3 | **Frontend routing mismatch** — the way the article ID is passed from bot to Mini App (via URL params, initData, or startparam) must match what the frontend expects | Article fails to load in reader | The mechanism for passing the article ID must be clearly defined and consistent between bot and frontend. The Mini App SDK `WebApp.initDataUnsafe.start_param` is the canonical Telegram way. |
| 4 | **Platform-specific bot behavior** — aiogram bot may behave differently when polling on Windows (development) vs Linux (production) | Bot tests pass locally but fail in CI | Keep bot logic simple and well-tested. Use the existing `bot_enabled` toggle for local development without a token. |
| 5 | **Config coupling** — the bot module gaining dependencies on parser, db, and models creates tighter coupling and may make future changes harder | Future refactoring requires more coordination | This is expected and acceptable for MVP. The dependency direction is clear: Presentation → Application → Domain → Data. Module map must be kept in sync. |

## Success Gate

The milestone is complete when all of the following can be demonstrated:

1. **Bot accepts a URL**: Send a valid article URL (e.g., `https://realpython.com/async-io-python/`) to the bot → bot responds with a button showing the article title within 5 seconds.
2. **Cache works**: Send the same URL again → bot responds instantly (< 1 second) with the same button.
3. **Invalid URL handling**: Send a non-URL text → bot responds with a helpful message (not a crash).
4. **Reader renders article**: Tap the button → Mini App opens → reader page shows the article with title, paragraphs, code blocks with distinct styling, and images.
5. **Existing API intact**: `curl /health` returns `{"status":"ok"}`, `POST /api/parse` still works, `POST /api/translate` still works.
6. **Tests pass**: `python -m pytest` passes all existing tests.
7. **Frontend builds**: `cd frontend && npm run build` succeeds with no TypeScript errors.

### Smoke Test Sequence

```
User sends:  https://realpython.com/async-io-python/
Bot replies: [InlineKeyboard with WebApp button "Async IO in Python"]
 User taps the button
  → Mini App opens at reader page
  → Title: "Async IO in Python"
  → Content: headings, paragraphs, code blocks (monospace), images
  → Telegram theme applied (light/dark)
```
