---
# ====================================================================
# MODULE_MAP — NewVision Module Knowledge Graph
# Version: 2.0
# Updated: 2026-06-19
#
# This YAML frontmatter is consumed by AI agents (DeepSeek, Claude)
# for code navigation. The Markdown body below is for human readers.
#
# Convention: YAML Frontmatter (Google OKF-compatible)
# Schema: docs/grace/module-map.schema.json
#
# Replace the old MODULE_MAP.xml with this format.
# Per-file GRACE docstrings are being deprecated.
# Use `@module:` single-line annotation instead.
# ====================================================================

version: "2.0"
project: newvision
updated: 2026-06-19

# ── Layers ──────────────────────────────────────────────────────────────────
layers:
  Presentation:
    description: "User-facing interfaces: API endpoints, bot commands"
  Application:
    description: "Core business logic: parsing, translation"
  Domain:
    description: "Enterprise-wide business objects: models, types"
  Data:
    description: "Persistence and configuration: db, settings"

# ── Modules ────────────────────────────────────────────────────────────────
modules:
  - name: main
    layer: Presentation
    file: backend/main.py
    depends_on: [config, db, models, parser, translator, bot, webhook]
    responsibility: "FastAPI application assembly and endpoint routing; lifespan routes bot between polling and webhook modes"
    contract: "All endpoints return valid JSON; /health always 200"

  - name: bot
    layer: Presentation
    file: backend/bot.py
    depends_on: [config, parser, db, models]
    responsibility: "Telegram bot: /start, URL → parse → WebApp button, polling + webhook lifecycle helpers"
    contract: "URL messages return WebAppInfo button; non-URL messages return help text; register_webhook/delete_webhook manage Cloud Run mode"

  - name: webhook
    layer: Presentation
    file: backend/webhook.py
    depends_on: [bot]
    responsibility: "FastAPI router receiving Telegram Updates and feeding them to the aiogram dispatcher"
    contract: "POST /webhook/telegram returns {status: ok} after feeding update to dispatcher"

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

# ── Edges (Dependency Relationships) ──────────────────────────────────────────────
edges:
  # Presentation
  - {from: main,    to: config,    type: configures-from}
  - {from: main,    to: db,        type: initialises}
  - {from: main,    to: bot,       type: starts-polling}
  - {from: main,    to: webhook,   type: mounts-router}
  - {from: main,    to: parser,    type: calls}
  - {from: main,    to: translator, type: calls}
  - {from: main,    to: models,    type: uses}
  - {from: webhook, to: bot,       type: feeds-update}
  - {from: bot,     to: config,    type: reads-settings}
  - {from: bot,     to: parser,    type: calls}
  - {from: bot,     to: db,        type: caches-through}
  - {from: bot,     to: models,    type: uses}

  # Application → Domain/Data
  - {from: parser,     to: models, type: produces}
  - {from: parser,     to: config, type: reads-settings}
  - {from: translator, to: models, type: type-gates}
  - {from: translator, to: db,    type: caches-through}

  # Data → Domain
  - {from: db,      to: models,    type: serialises}
---

# NewVision Module Map

## Module Dependency Graph

**Layers** (top → bottom):

- **Presentation**: `main`, `bot` — expose functionality to users
- **Application**: `parser`, `translator` — core business logic
- **Domain**: `models` — shared business objects
- **Data**: `config`, `db` — configuration and persistence

**Dependency Direction**: arrows point from consumer → dependency.

```
  main ──┬──→ config  (configures-from)
          ├──→ db      (initialises)
          ├──→ bot     (starts-polling)
          ├──→ webhook (mounts-router)
          ├──→ parser  (calls)
          ├──→ translator (calls)
          └──→ models  (uses)

  webhook ──→ bot     (feeds-update)
  bot ──┬──→ config  (reads-settings)
        ├──→ parser  (calls)
        ├──→ db      (caches-through)
        └──→ models  (uses)
  parser ──→ models  (produces)
  parser ──→ config  (reads-settings)
  translator ──→ models  (type-gates)
  translator ──→ db  (caches-through)
  db ──→ models  (serialises)
```

> **AI Agents**: The YAML frontmatter above is the authoritative source for
> module navigation. Update the `modules` and `edges` lists when adding,
> removing, or modifying any backend module.

### Layer Rules

1. Presentation → Application → Domain → Data
2. No skipping layers
3. Domain modules have zero `depends_on` (business objects stand alone)
4. Data modules may depend on Domain (serialization)
5. Application modules depend on Domain + Data

### Quick Reference

| Module | Layer | File | Dependencies |
|--------|-------|------|-------------|
| main | Presentation | `backend/main.py` | config, db, models, parser, translator, bot, webhook |
  | bot | Presentation | `backend/bot.py` | config, parser, db, models |
  | webhook | Presentation | `backend/webhook.py` | bot |
| parser | Application | `backend/parser.py` | models, config |
| translator | Application | `backend/translator.py` | models, db |
| models | Domain | `backend/models.py` | (none) |
| config | Data | `backend/config.py` | (none) |
| db | Data | `backend/db.py` | models |
