---
# ====================================================================
# MODULE_MAP — NewVision Module Knowledge Graph
# Version: 2.1
# Updated: 2026-06-19 (M5: +curtain-block, use-curtain, use-translation, use-preload)
#
# This YAML frontmatter is consumed by AI agents (DeepSeek, Claude)
# for code navigation. The Markdown body below is for human readers.
#
# Convention: YAML Frontmatter (Google OKF-compatible)
# Schema: docs/grace/module-map.schema.json
# ====================================================================

version: "2.1"
project: newvision
updated: 2026-06-19

# ── Layers ──────────────────────────────────────────────────────────────────
layers:
  Presentation:
    description: "User-facing interfaces: API endpoints, bot commands, UI components"
  Application:
    description: "Core business logic: parsing, translation, caching, gesture handling"
  Domain:
    description: "Enterprise-wide business objects: models, types"
  Data:
    description: "Persistence and configuration: db, settings, API client"

# ── Modules ────────────────────────────────────────────────────────────────
modules:
  # Backend
  - name: main
    layer: Presentation
    file: backend/main.py
    depends_on: [config, db, models, parser, translator, bot]
    responsibility: "FastAPI application assembly and endpoint routing"
    contract: "All endpoints return valid JSON; /health always 200"

  - name: bot
    layer: Presentation
    file: backend/bot.py
    depends_on: [config, parser, db, models]
    responsibility: "Telegram bot: /start, URL → parse → WebApp button"
    contract: "URL messages return WebAppInfo button; non-URL messages return help text"

  - name: parser
    layer: Application
    file: backend/parser.py
    depends_on: [models, config]
    responsibility: "URL → blocks extraction (text, code, image)"
    contract: "Returns article with typed blocks; ParseError on failure"

  - name: translator
    layer: Application
    file: backend/translator.py
    depends_on: [models, db]
    responsibility: "LLM EN→RU block translation with caching"
    contract: "Writes to cache; returns (text, cached, error) tuple"

  - name: models
    layer: Domain
    file: backend/models.py
    depends_on: []
    responsibility: "Pydantic models: Article, Block, requests, responses"
    contract: "All models JSON-serializable; BlockType enum exhaustive"

  - name: config
    layer: Data
    file: backend/config.py
    depends_on: []
    responsibility: "Settings via pydantic-settings (.env)"
    contract: "All settings present with defaults; validates API keys"

  - name: db
    layer: Data
    file: backend/db.py
    depends_on: [models]
    responsibility: "SQLite: init, CRUD for articles + translation cache"
    contract: "Connection-safe; get/put operations atomic"

  # Frontend (M5)
  - name: curtain-block
    layer: Presentation
    file: frontend/src/components/CurtainBlock.tsx
    depends_on: [use-curtain, use-translation, api-client]
    responsibility: "Visual curtain component: original layer + translation layer with touch gesture"
    contract: "Renders translatable blocks with swipe-to-reveal; code/images pass through unchanged"

  - name: use-curtain
    layer: Presentation
    file: frontend/src/hooks/useCurtain.ts
    depends_on: []
    responsibility: "Touch gesture engine: swipe detection, 30% threshold, flick velocity, snap physics"
    contract: "Returns curtainProps + state machine (idle→dragging→loading→loaded→error)"

  - name: use-translation
    layer: Application
    file: frontend/src/hooks/useTranslation.tsx
    depends_on: [api-client]
    responsibility: "Shared translation cache via React Context: Map-based, inflight deduplication"
    contract: "getTranslation() returns cached or fetches; preloadTranslations() batch-loads"

  - name: use-preload
    layer: Application
    file: frontend/src/hooks/usePreload.ts
    depends_on: [use-translation]
    responsibility: "IntersectionObserver-based preloading: 300ms debounce, 3-block look-ahead"
    contract: "schedulePreload() fires batch translation for upcoming translatable blocks"

  - name: article-renderer
    layer: Presentation
    file: frontend/src/components/ArticleRenderer.tsx
    depends_on: [curtain-block, api-client]
    responsibility: "Routes article blocks: translatable → CurtainBlock, code/image → DirectBlockRenderer"
    contract: "All block types rendered; non-translatable blocks bypass curtain"

  - name: reader
    layer: Presentation
    file: frontend/src/pages/Reader.tsx
    depends_on: [article-renderer, use-translation, api-client]
    responsibility: "Article reader page: fetches by ID, wraps in TranslationProvider"
    contract: "Loading/error/empty states handled; article rendered via ArticleRenderer"

  - name: api-client
    layer: Data
    file: frontend/src/services/api.ts
    depends_on: []
    responsibility: "Frontend API client: types, fetchArticle, fetchBlockTranslation, fetchBlockTranslationBatch"
    contract: "All fetch calls use VITE_API_URL; responses typed; 404/error handled"

# ── Edges (Dependency Relationships) ───────────────────────────────────────
edges:
  # Backend
  - {from: main,    to: config,    type: configures-from}
  - {from: main,    to: db,        type: initialises}
  - {from: main,    to: bot,       type: starts-polling}
  - {from: main,    to: parser,    type: calls}
  - {from: main,    to: translator, type: calls}
  - {from: main,    to: models,    type: uses}
  - {from: bot,     to: config,    type: reads-settings}
  - {from: bot,     to: parser,    type: calls}
  - {from: bot,     to: db,        type: caches-through}
  - {from: bot,     to: models,    type: uses}
  - {from: parser,     to: models, type: produces}
  - {from: parser,     to: config, type: reads-settings}
  - {from: translator, to: models, type: type-gates}
  - {from: translator, to: db,    type: caches-through}
  - {from: db,      to: models,    type: serialises}

  # Frontend (M5)
  - {from: reader,            to: article-renderer, type: renders}
  - {from: reader,            to: use-translation,   type: provides-context}
  - {from: reader,            to: api-client,        type: fetches}
  - {from: article-renderer,  to: curtain-block,     type: delegates-to}
  - {from: article-renderer,  to: api-client,        type: type-gates}
  - {from: curtain-block,     to: use-curtain,       type: gesture-driven-by}
  - {from: curtain-block,     to: use-translation,   type: translates-via}
  - {from: curtain-block,     to: api-client,        type: type-gates}
  - {from: use-translation,   to: api-client,        type: calls}
  - {from: use-preload,       to: use-translation,   type: batch-loads}
---

# NewVision Module Map

## Module Dependency Graph

**Layers** (top → bottom):

- **Presentation**: `main`, `bot`, `curtain-block`, `article-renderer`, `reader`, `use-curtain` — expose functionality to users
- **Application**: `parser`, `translator`, `use-translation`, `use-preload` — core business logic
- **Domain**: `models` — shared business objects
- **Data**: `config`, `db`, `api-client` — configuration and persistence

**Dependency Direction**: arrows point from consumer → dependency.

```
  # Backend
  main ──┬──→ config  (configures-from)
          ├──→ db      (initialises)
          ├──→ bot     (starts-polling)
          ├──→ parser  (calls)
          ├──→ translator (calls)
          └──→ models  (uses)

  bot ──┬──→ config  (reads-settings)
        ├──→ parser  (calls)
        ├──→ db      (caches-through)
        └──→ models  (uses)
  parser ──→ models  (produces)
  parser ──→ config  (reads-settings)
  translator ──→ models  (type-gates)
  translator ──→ db  (caches-through)
  db ──→ models  (serialises)

  # Frontend (M5)
  reader ──→ article-renderer  (renders)
  reader ──→ use-translation   (provides-context)
  reader ──→ api-client        (fetches)
  article-renderer ──→ curtain-block   (delegates-to)
  article-renderer ──→ api-client      (type-gates)
  curtain-block ──→ use-curtain       (gesture-driven-by)
  curtain-block ──→ use-translation   (translates-via)
  curtain-block ──→ api-client        (type-gates)
  use-translation ──→ api-client      (calls)
  use-preload ──→ use-translation     (batch-loads)
```

> **AI Agents**: The YAML frontmatter above is the authoritative source for
> module navigation. Update the `modules` and `edges` lists when adding,
> removing, or modifying any module.

### Layer Rules

1. Presentation → Application → Domain → Data
2. No skipping layers
3. Domain modules have zero `depends_on` (business objects stand alone)
4. Data modules may depend on Domain (serialization)
5. Application modules depend on Domain + Data

### Quick Reference

| Module | Layer | File | Dependencies |
|--------|-------|------|-------------|
| main | Presentation | `backend/main.py` | config, db, models, parser, translator, bot |
| bot | Presentation | `backend/bot.py` | config, parser, db, models |
| parser | Application | `backend/parser.py` | models, config |
| translator | Application | `backend/translator.py` | models, db |
| models | Domain | `backend/models.py` | (none) |
| config | Data | `backend/config.py` | (none) |
| db | Data | `backend/db.py` | models |
| **curtain-block** | **Presentation** | `frontend/src/components/CurtainBlock.tsx` | **use-curtain, use-translation, api-client** |
| **use-curtain** | **Presentation** | `frontend/src/hooks/useCurtain.ts` | **(none)** |
| **use-translation** | **Application** | `frontend/src/hooks/useTranslation.tsx` | **api-client** |
| **use-preload** | **Application** | `frontend/src/hooks/usePreload.ts` | **use-translation** |
| **article-renderer** | **Presentation** | `frontend/src/components/ArticleRenderer.tsx` | **curtain-block, api-client** |
| **reader** | **Presentation** | `frontend/src/pages/Reader.tsx` | **article-renderer, use-translation, api-client** |
| **api-client** | **Data** | `frontend/src/services/api.ts` | **(none)** |
