# AGENTS.md — NewVision

Telegram Mini App для чтения английских технических статей с inline-переводом.
Жест «шторка» — свайп вверх по абзацу reveals перевод.

## Repository

- **Repository**: `github.com/DrainRanger92/newvision`
- **ТЗ (source of truth)**: `TZ.md` — лишено техники, только цели/UX/перфоманс
- **Obsidian index**: `pet/curtain-reader/_index.md` (в vault)
- **Workflow**: feature branch → PR → review → merge. Все изменения кода проходят через Pull Request, даже single-commit фиксы. Pull Request — единственный способ изменить код в main.
- **Review**: перед мержем каждой ветки проводится ревью кода. Ревью выполняется Hermes Agent (скилл `requesting-code-review`). Ветка мержится только после APPROVE.
- **Cloud-first**: код живёт на GitHub, агенты клонируют/пушат через MCP

## Tech Stack (chosen by agent — TZ doesn't mandate)

Aгенты выбирают стек сами. Ожидаемые defaults (от skill `telegram-mini-app`):

| Layer | Default (если агент не предложит лучше) |
|---|---|
| Bot | Python 3.11+, aiogram 3.x |
| API | Python, FastAPI, Uvicorn |
| Frontend | React 18+, TypeScript, Vite |
| SDK | @twa-dev/sdk |
| DB | SQLite (cache) |
| Anim | Framer Motion |
| Translation | LLM через OpenCode Go (mimo/glm) — НЕ DeepL, НЕ OpenRouter |
- **LLM provider**: opencode-go/* (mimo-v2.5-pro, glm-5.1, kimi-k2.6)

## GRACE Semantic Markup Convention

This project uses **GRACE Framework** (Generative Robust AI Code Engineering) semantic markup,
adapted for Python from the Voice Book Writer (София) convention.

All `backend/*.py` files MUST contain a module docstring with:

### 1. MODULE_CONTRACT

```
"""
<MODULE_CONTRACT>
name: ModuleName
layer: Presentation | Application | Domain | Data
depends: [Dep1, Dep2]
responsibility: What this module does
contract: What guarantees this module provides
</MODULE_CONTRACT>

"""
```

### 2. LINKS (Knowledge Graph)

```
"""
<LINKS>
- TargetModule: relationship (e.g. "uses", "produces", "configures")
</LINKS>

"""
```

### 3. Semantic log anchors

Every `logger.info()` / `logger.warning()` call must include a `[ModuleName]` prefix
matching the `name` field in MODULE_CONTRACT.

```python
logger.info("[Parser] Fetching %s", url)
logger.info("[DB] Initialized at %s", db_path)
logger.info("[Translator] Cache hit for article=%s block=%d", article_id, block_index)
```

### 4. MODULE_MAP.xml

The file `docs/grace/MODULE_MAP.xml` contains the complete module knowledge graph
and must be updated synchronously with any module change.

### GRACE Compliance (Mandatory)

1. **Preserve GRACE markup** — When modifying a `.py` file, update its MODULE_CONTRACT, LINKS, and anchor-coordinated logs.
2. **Synchronous updates** — Changing a module's responsibility or dependencies MUST be reflected in `MODULE_MAP.xml`.
3. **Semantic anchors are stable coordinates** — Do NOT remove or rename anchors without updating all references.
4. **Docstrings required** — Every public function SHOULD have a docstring (PEP 257).
5. **Respect layer boundaries** — Presentation → Application → Domain → Data. No skipping layers.
6. **Contracts before code** — Define/update MODULE_CONTRACT before writing implementation code.

### Mandatory Checklist Before Any Change

Before modifying any `.py` file, verify:
- [ ] The file has `<MODULE_CONTRACT>` and `<LINKS>` docstring blocks
- [ ] Public functions have docstrings (PEP 257)
- [ ] Log statements use `[ModuleName]` semantic anchor prefix
- [ ] MODULE_CONTRACT layer matches the actual layer
- [ ] `depends` list matches actual import dependencies
- [ ] LINKS references match actual module relationships

### Mandatory Checklist After Any Change

After modifying any `.py` file, verify:
- [ ] If dependencies changed → update `MODULE_CONTRACT.depends` and `LINKS`
- [ ] If responsibility changed → update `MODULE_CONTRACT.responsibility` and `MODULE_CONTRACT.contract`
- [ ] If links changed → update `docs/grace/MODULE_MAP.xml`
- [ ] If public API changed → update docstrings
- [ ] If new logs added → use `[ModuleName]` anchor prefix

## Available Models (DeepSeek API — primary; Anthropic/OpenCode — escalation)

| Роль цикла | Primary | Escalation | Зачем |
|---|---|---|---|
| **Architect** | `deepseek/deepseek-v4-pro` | `anthropic/claude-sonnet-4-5` | План, декомпозиция, риски |
| **Builder** | `deepseek/deepseek-v4-flash` | `deepseek/deepseek-v4-pro` | Имплементация, smoke test |
| **Validator** | `deepseek/deepseek-v4-pro` | `anthropic/claude-sonnet-4-5` | Ревью кода, data integrity |
| **Translate (runtime)** | `deepseek/deepseek-chat` | — | EN→RU в проде |
| **LogCraft** | `deepseek/deepseek-v4-pro` | — | Post-cycle log analysis, failure classification |

> 🔑 DeepSeek API key ($0.30–0.50 за билд). Эскалация на Anthropic только при FAIL. OpenCode Go — deprecated (баланс пуст).
> Эконом-режим: 1 architect → 1 builder → smoke → 1 LogCraft. Full race (3×3) только для M5 Curtain UX.

### Builder Escalation Ladder

When a builder fails a gate, escalate model:

```
deepseek/deepseek-v4-flash (cheapest, ~$0.10/build)
  ├─ GATE FAIL → deepseek/deepseek-v4-pro (~$0.30/build)
  └─ GATE FAIL → anthropic/claude-sonnet-4-5 (~$2.00/build)
       └─ GATE FAIL → FAIL slot (replace with different model)
```

Max retries per build slot: 2 (from `docs/cycle-config.json`).

## Project Structure (target)

```
newvision/
├── AGENTS.md                         # This file
├── TZ.md                             # Source of truth (no tech details)
├── README.md                         # Human-friendly intro
├── .gitignore
├── backend/
│   ├── main.py                       # FastAPI app
│   ├── bot.py                        # aiogram bot
│   ├── parser.py                     # URL → blocks
│   ├── translator.py                 # LLM translate + cache
│   ├── db.py                         # SQLite (articles + translations)
│   ├── models.py                     # Pydantic
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── Router.tsx                 # HashRouter: "/" и "/reader/:id"
│   │   ├── pages/Reader.tsx           # Article reader page
│   │   ├── components/
│   │   │   ├── ArticleRenderer.tsx
│   │   │   ├── CurtainBlock.tsx      # core: touch swipe
│   │   │   ├── CodeBlock.tsx
│   │   │   └── Header.tsx
│   │   ├── hooks/
│   │   │   ├── useCurtain.ts
│   │   │   ├── useArticle.ts
│   │   │   └── useTranslation.ts
│   │   ├── services/
│   │   │   └── api.ts                # API client (fetchArticle)
│   │   └── styles/
│   │       └── global.css
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
├── gates/
│   ├── build-gate.sh                 # G5-G11, G15-G16: build validation
│   ├── commit-gate.sh                # G12-G13: commit checks
│   ├── context-guard.sh              # G17: file scope enforcement
│   ├── check-env-keys.py             # G2: API key presence
│   ├── check-balance.py              # G3: provider balance
│   ├── check-port.py                 # G4: port availability
│   ├── validate-test-urls.py         # G14: smoke URL validation
│   └── budget-calc.py                # CostPerAcceptedChange
└── docs/
    ├── decisions/                    # ADR-лог
    ├── milestones/                   # Milestone plans
    ├── grace/
    │   └── MODULE_MAP.xml            # GRACE knowledge graph
    ├── loopcraft/
    │   ├── LOOPCRAFT-SKILL.md        # Gate methodology
    │   ├── LOGCRAFT-SKILL.md         # Post-cycle log analysis
    │   ├── PATCHES-AGENTS.md         # AGENTS.md patches
    │   └── methodology.md            # Architect design docs
    ├── logcraft/                     # LogCraft reports
    │   └── *-report.json
    ├── budget.json                   # Cycle cost log
    ├── context-modules.json          # File allow-lists per milestone
    └── cycle-config.json             # Hard-stop conditions
```

## Agent Loop Protocol

### На каждый milestone:

1. **Architect-агенты (2-3 параллельно, race)**:
   - Каждый получает: TZ.md + текущее состояние репо + список пройденных milestones
   - Каждый создаёт независимый план: декомпозиция, выбор библиотек, smoke-test
   - Пишут планы в `docs/milestones/M{n}-{name}-{model}.md`

2. **Plan Validator** (deepseek-v4-pro):
   - Получает: TZ + все N планов
   - Отдаёт: лучший план (или merge лучших идей)
   - Коммитит победителя как `docs/milestones/M{n}-{name}.md`

3. **Build-агенты (3 параллельно, race)**:
   - Каждый получает одну и ту же задачу + winning plan
   - Каждый коммитит в свою ветку: `agent/<model>/<task-id>`
   - Должен запускать свой код и проверять что он работает (smoke test)

4. **Build Validator** (deepseek-v4-pro):
   - Получает: ТЗ + plan + дифф всех веток
   - Отдаёт: PASS/FAIL с конкретными пунктами + data integrity check
   - Критерии: соответствие ТЗ, работает ли код, чистота git истории, данные для будущих milestone сохранены

5. **Review + Merge**:
   - Лучшая ветка → создаётся Pull Request в main
   - PR проходит ревью кода (Hermes агент со скиллом `requesting-code-review`)
   - После APPROVE → squash merge в main
   - Остальные ветки → закрываются без merge
   - **Никаких push напрямую в main.** Все изменения — только через PR.

6. **LogCraft (synchronous, 2-5 minutes)**:
   - Run LogCraft agent on all cycle logs before merge
   - Agent produces `docs/logcraft/{cycle-id}-report.json`
   - If failures found: review, fix trivial ones, re-run gates
   - If unfixable failures: report to user before merge
   - Zero failures = proceed to merge

### Когда цикл останавливается:
- Validator = PASS по всем критериям milestone
- Milestone соответствует acceptance criteria из плана

## Milestones (порядок)

- [x] **M1** Skeleton: backend + bot + frontend запускаются, hello world ✅ (dbbb98d, QWEN winner)
- [x] **M2** Parser: URL → массив блоков, кэш статей ✅ (257ba4b, DSV4 winner)
- [x] **M3** Translation: LLM EN→RU, lazy + cache ✅ (8f7bcf2, DSV4Flash winner)
- [x] **M4** Bot integration: URL → Mini App кнопка, end-to-end ✅ (c17fd8a, DSV4Flash)
- **M5** Curtain UX: touch swipe, snap, 60fps
- **M6** Telegram theme + polish: light/dark, inline-code preserved
- **M7** Deploy: VPS + Vercel + HTTPS, smoke на реальном устройстве

## Gate Checklist Per Milestone

Every milestone cycle MUST pass these gates before merge. Failures trigger automatic actions.

### Pre-flight Gates (run once per cycle, before ANY agent)

| Gate | Command | PASS Criteria |
|------|---------|---------------|
| G1-env-file | `test -f backend/.env` | File exists |
| G2-key-presence | `python gates/check-env-keys.py` | Exit 0 |
| G3-balance | `python gates/check-balance.py` | Exit 0 |
| G4-port-free | `python gates/check-port.py 8000` | Exit 0 (8001-8003 also checked for build race) |
| G14-test-urls | `python gates/validate-test-urls.py` | All URLs return 200 |

### Build Gates (run per agent, before commit)

| Gate | Command | PASS Criteria |
|------|---------|---------------|
| G5-imports | `PYTHONPATH=. python -c "from backend.main import app; print('OK')"` | stdout="OK", exit 0 |
| G6-frontend-build | `cd frontend && npm run build` | exit 0 |
| G7-lint | `ruff check backend/` | exit 0 |
| G8-smoke-start | Start uvicorn, curl health | `{"status":"ok"}` |
| G9-smoke-parse | Parse known-good URL | `blocks` array length > 0 |
| G10-smoke-translate | Translate first translatable block | `translated_text` non-empty, `error` false |
| G11-system-prompt | `grep -q "TRANSLATION_SYSTEM_PROMPT" backend/translator.py` | Match found |
| G15-typecheck | `cd frontend && npx tsc --noEmit` | exit 0 |
| G16-env-path | `python -c "from backend.config import settings; assert settings.db_path"` | exit 0 |

### Post-build Gates (run per agent, after build gates pass)

| Gate | Command | PASS Criteria |
|------|---------|---------------|
| G12-commit | `git log --oneline -1` | Shows a commit |
| G13-diff-nonempty | `git diff main..$(git branch --show-current) --stat` | At least 1 file |
| G17-context-guard | `bash gates/context-guard.sh <milestone>` | exit 0 |

### Gate Failure Protocol

1. **Pre-flight gate fails** → BLOCK CYCLE. Report to user. Fix before retry.
2. **Build gate fails** → KILL AGENT. Escalate model. If retries exhausted → FAIL that slot.
3. **Post-build gate fails (G12)** → Fallback: `git add -A && git commit -m "auto"`
4. **Post-build gate fails (G13, G17)** → FAIL agent permanently.
5. **3+ consecutive gate failures across all agents** → HARD STOP. Report to user.

## Cost Tracking

Every cycle writes to `docs/budget.json`. Metric: `CostPerAcceptedChange`.

### Cycle cost log (`docs/budget.json`)

Each cycle appends an entry:

```json
{
  "cycle_id": "M4-bot-integration",
  "provider": "deepseek-api",
  "mode": "economy",
  "started_at": "<ISO timestamp>",
  "completed_at": "<ISO timestamp>",
  "total_token_cost": 0.41,
  "total_compute_minutes": 15.7,
  "compute_cost": 7.85,
  "total_cost": 8.26,
  "accepted_prs": 1,
  "cost_per_accepted_change": 8.26,
  "gates": {},
  "winner_branch": "agent/deepseek-v4-flash/M4-bot-integration",
  "winner_commit": "abc1234"
}
```

### Running total

```bash
python gates/budget-calc.py
```

### Per-milestone budget estimates

| Milestone | Mode | Est. cost | Notes |
|-----------|------|-----------|-------|
| M4 Bot Integration | Economy (1+1) | $1–3 | Bot logic, Mini App button, E2E wiring |
| M5 Curtain UX | Full race (2+3) | $5–15 | Core UX, touch gestures, animation |
| M6 Theme + Polish | Single builder | $0.30–1 | CSS variables, theme detection |
| M7 Deploy | Single builder | $0.30–1 | Docker, Vercel, smoke on device |

### Budget cap

Per `docs/cycle-config.json`, default `max_cycle_cost = $5.00`. M5 is the only milestone
expected to exceed this; raise the cap for M5 to $15.00 before starting the cycle.

## LogCraft Reports

After every cycle, LogCraft produces a report at `docs/logcraft/{cycle-id}-report.json`.

### Report schema

```json
{
  "cycle_id": "M4-bot-integration",
  "generated_at": "<ISO timestamp>",
  "summary": {
    "total_failures": 0,
    "by_category": {"ENV": 0, "CODE": 0, "PLAN": 0, "LATENT": 0}
  },
  "failures": [],
  "recommendations": {"new_gates": [], "process_changes": []}
}
```

### Failure taxonomy (quick reference)

| Code | Category | Example |
|------|----------|---------|
| `ENV-001` | Missing config | API key empty |
| `ENV-002` | Balance empty | HTTP 402 |
| `ENV-003` | Port occupied | `[Errno 10048]` |
| `ENV-006` | env_file path wrong | `.env` vs `backend/.env` |
| `CODE-001` | Type/import error | `AttributeError` |
| `CODE-004` | Missing critical code | No `TRANSLATION_SYSTEM_PROMPT` |
| `CODE-005` | Smoke test skipped | No gate log |
| `PLAN-001` | Test URL broken | URL returns 403 |
| `LATENT-001` | Prior milestone bug | M2 bug surfaces in M3 |

Full taxonomy: `docs/loopcraft/LOGCRAFT-SKILL.md` §3.

### M3 Failure Post-Mortem (archived findings)

The 10 failures from M3 are pre-classified in `docs/loopcraft/LOGCRAFT-SKILL.md` §4.
LogCraft cross-references new failures against this archive to detect recurring patterns.

## Agent Rules (Mandatory)

1. **ТЗ — source of truth**. Если возникает противоречие — спрашивать, не выдумывать.
2. **Smoke-test обязателен**. Каждый build-агент должен запустить свой код и убедиться, что он работает, до коммита.
3. **Один осмысленный коммит**. Никаких fixup-ов, wip-ов, «fix typo» в истории.
4. **Имена = бизнес-смысл**. `ShouldEnableCurtain`, не `ModeToIsEnabled`. `parse_article`, не `do_stuff`.
5. **Не трогать лишнего**. Изменения только в скоупе задачи.
6. **Документация = код**. Если меняешь API — обнови README. Если принял решение — пиши ADR.
7. **Только через Pull Request**. Все изменения кода — в feature-ветке → PR → review → merge. Никаких push в main. PR создаётся даже для одного коммита. Мерж — только после APPROVE ревью.
8. **Логи = structured + semantic anchor**. `[ModuleName] message with {Params}`.
9. **Никаких DeepL/OpenRouter** — только OpenCode Go модели.
10. **Блокирующие вопросы — спрашивать сразу**, не молча выбирать запасной путь.

## Open Questions (собираем здесь)

- [ ] Домен для Mini App — Mark даст перед M7
- [ ] VPS провайдер — Hetzner? (предложение в плане M7)
- [ ] Max budget per milestone: $5 for economy, $15 for full race. Acceptable? (Mark: confirm)
- [ ] Should LogCraft run even when all gates pass? (recommended: yes, for audit trail)
- [ ] Compute rate: $0.50/min (assumes VPS cost). Accurate? (Mark: confirm)

## Build & Test

- **M1**: Frontend `npm run build` ✅ (Vite + tsc), backend imports ✅ (FastAPI + aiogram)
- **M2**: Parser ✅ (DSV4 winner): POST /api/parse → 416 blocks, cache hit < 50ms, /health preserved
- **M3**: Translation ✅ (DSV4Flash winner): translate block returns RU text, code preserved, batch works
- **M4**: Bot integration ✅ (DSV4Flash): URL handler → parse → WebAppInfo button, Mini App reader page
- Backend Python env needs clean venv setup (hermes-agent PYTHONPATH interferes)

### Gate Commands

```bash
# Pre-flight (run once per cycle)
python gates/check-env-keys.py      # G2: verify API keys present
python gates/check-balance.py       # G3: verify provider balance
python gates/check-port.py 8000     # G4: verify port free
python gates/validate-test-urls.py  # G14: verify smoke test URLs

# Build (run in each agent's workdir)
PORT=8001 bash gates/build-gate.sh  # G5-G11, G15-G16: full build validation

# Post-build (run in each agent's workdir)
bash gates/commit-gate.sh           # G12-G13: verify commit exists and has changes
bash gates/context-guard.sh M4      # G17: verify no out-of-scope file modifications

# Budget
python gates/budget-calc.py         # Recalculate CostPerAcceptedChange
```
