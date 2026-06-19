# AGENTS.md — NewVision

Telegram Mini App для чтения английских технических статей с inline-переводом.
Жест «шторка» — свайп вверх по абзацу reveals перевод.

## Repository

- **Repository**: `github.com/DrainRanger92/newvision`
- **ТЗ (source of truth)**: `TZ.md` — лишено техники, только цели/UX/перфоманс
- **Obsidian index**: `pet/curtain-reader/_index.md` (в vault)
- **Workflow**: agentic loop — plan → build (3 модели race) → validator → repeat
- **Cloud-first**: код живёт на GitHub, агенты клонируют/пушат через MCP

## Branch Protection (main)

GitHub branch protection — **единственный жёсткий gate** перед мержем в main. Все настройки применены через REST API и действуют на всех, включая админа.

| Правило | Статус | Что даёт |
|---------|--------|----------|
| Require pull request | ✅ | Никаких прямых пушей в main |
| Require 1 approving review | ✅ | Merge только после approve (от другого аккаунта) |
| **Require approval of most recent push** | ✅ **NEW** | После любого пуша approve сбрасывается — нужно переаппрувить |
| Dismiss stale approvals | ✅ | Новый коммит сбрасывает старый approve |
| Require conversation resolution | ✅ **NEW** | Все PR-комментарии должны быть resolved |
| Require status checks (validate-python, validate-frontend) | ✅ | CI должен быть зелёным |
| Enforce for admins | ✅ | Админ тоже не может обойти |
| Block force pushes | ✅ | Нет `--force` в main |
| Block deletions | ✅ | Ветку main нельзя удалить |

### Two-Token Architecture (Active)

Обязательное требование: Hermes/OpenCode выполняет ВСЕ git-операции (commit, push, создание PR)
только от dev-аккаунта **newoxygensolutions92**. Mark (DrainRanger92) — только approve и merge.
Любой коммит от DrainRanger92 в feature-ветке — нарушение. Такой PR закрывается
и пересоздаётся от dev-аккаунта.

| Роль | Аккаунт | PAT | Что делает |
|------|---------|-----|-----------|
| 👑 Admin | `DrainRanger92` | Mark's personal PAT | Approve, merge, настройки репо, CI |
| 🤖 Dev | `newoxygensolutions92` | `$GITHUB_DEV_PAT` (ghp_..., classic 40-char) | Hermes/OpenCode: создаёт ветки, коммитит, открывает PR |

**Принцип работы:**
- Hermes/OpenCode использует `$GITHUB_DEV_PAT` от `newoxygensolutions92` → PR создаётся от dev-аккаунта
- Mark аппрувит своим админ-токеном → GitHub видит двух разных людей ✅
- Branch protection гарантирует: 1 approve + 2 CI checks → только тогда merge

> **Важно:** Public repo не даёт случайным людям права аппрува. Approve засчитывается **только от пользователей с Write доступом**.
> `GITHUB_TOKEN` (встроенный токен GitHub Actions) НЕ засчитывается в merge requirements — его approve проходит мимо gates.

---

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

NewVision uses the **GRACE Framework** (Generative Robust AI Code Engineering) for
AI agent code navigation. As of v2.0, GRACE metadata is **centralized** in a single file —
no more per-file docstring boilerplate.

### 1. MODULE_MAP.md (Source of Truth)

The file `docs/grace/MODULE_MAP.md` contains the complete module knowledge graph
(YAML Frontmatter + Markdown). This is the **single source of truth** for all
module metadata: name, layer, dependencies, responsibility, contract, and edges.

Update this file synchronously with any module change.

### 2. `# @module:` Annotation

Every `backend/*.py` file MUST have a single-line `# @module: <name>` annotation
in its module-level docstring (no more MODULE_CONTRACT/LINKS blocks):

```python
"""
# @module: main
"""
```

The `<name>` must match the `name` field in `docs/grace/MODULE_MAP.md`.

### 3. Semantic Log Anchors

Every `logger.info()` / `logger.warning()` call must include a `[ModuleName]` prefix
matching the `name` field in MODULE_MAP.md.

```python
logger.info("[Parser] Fetching %s", url)
logger.info("[DB] Initialized at %s", db_path)
logger.info("[Translator] Cache hit for article=%s block=%d", article_id, block_index)
```

### 4. Function-Level Docstrings

PEP 257 docstrings on public functions are **still required** — they document
the function API, not the module contract. The module contract lives in
MODULE_MAP.md.

### GRACE Compliance (Mandatory)

1. **`@module:` is the only per-file markup** — No MODULE_CONTRACT or LINKS blocks in .py files.
2. **MODULE_MAP.md is SSOT** — Changing a module's responsibility or dependencies MUST be reflected there.
3. **Semantic anchors are stable coordinates** — Do NOT remove or rename `[ModuleName]` log anchors without updating all references.
4. **Docstrings required** — Every public function SHOULD have a docstring (PEP 257).
5. **Respect layer boundaries** — Presentation → Application → Domain → Data. No skipping layers.

### Mandatory Checklist Before Any Change

Before modifying any `.py` file, verify:
- [ ] The file has a `# @module: <name>` annotation in its docstring
- [ ] Public functions have docstrings (PEP 257)
- [ ] Log statements use `[ModuleName]` semantic anchor prefix
- [ ] Module exists in `docs/grace/MODULE_MAP.md` with correct layer and dependencies

### Mandatory Checklist After Any Change

After modifying any `.py` file, verify:
- [ ] If dependencies changed → update `docs/grace/MODULE_MAP.md`
- [ ] If responsibility changed → update `docs/grace/MODULE_MAP.md`
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
│   │   ├── pages/Reader.tsx
│   │   ├── components/
│   │   │   ├── ArticleRenderer.tsx
│   │   │   ├── CurtainBlock.tsx      # core: touch swipe
│   │   │   ├── CodeBlock.tsx
│   │   │   └── Header.tsx
│   │   ├── hooks/
│   │   │   ├── useCurtain.ts
│   │   │   ├── useArticle.ts
│   │   │   └── useTranslation.ts
│   │   ├── services/api.ts
│   │   └── styles/
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
    │   └── MODULE_MAP.md            # GRACE knowledge graph
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

5. **Merge**:
   - Лучшая ветка → squash merge в main
   - Остальные ветки → закрываются без merge

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
- [x] **M4** Bot integration: URL → Mini App кнопка, end-to-end ✅
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

### Infrastructure Gates (автоматические — срабатывают без действий агента)

Эти gates проверяются git-hooks и CI. Агент не запускает их вручную. При ошибке — читать exit code и фиксить код.

| Gate | Триггер | Что проверяет |
|------|---------|---------------|
| G6-frontend-build | `gates/git-agent.sh push` (pre-push hook) | `npm run build` — полная сборка frontend |
| G7-lint | `gates/git-agent.sh commit` (pre-commit hook) | `ruff check backend/` — Python линтинг |
| G15-typecheck | `gates/git-agent.sh commit` (pre-commit hook) | `npx tsc --noEmit` — TypeScript typecheck |
| CI (validate-python) | Pull Request creation / push | GitHub Actions: imports + ruff + pytest |
| CI (validate-frontend) | Pull Request creation / push | GitHub Actions: `npm ci && npm run build` |

> **Агент не вызывает эти gates.** Если хук вернул exit code != 0 — прочитать вывод, исправить код, повторить коммит.

### Contextual Gates (ручной запуск агентом)

Эти gates требуют осмысленного участия агента — выбора URL, интерпретации результата.

| Gate | Command | PASS Criteria |
|------|---------|---------------|
| G5-imports | `PYTHONPATH=. python -c "from backend.main import app; print('OK')"` | stdout="OK", exit 0 |
| G8-smoke-start | Start uvicorn, curl health | `{"status":"ok"}` |
| G9-smoke-parse | Parse known-good URL | `blocks` array length > 0 |
| G10-smoke-translate | Translate first translatable block | `translated_text` non-empty, `error` false |
| G11-system-prompt | `grep -q "TRANSLATION_SYSTEM_PROMPT" backend/translator.py` | Match found |
| G16-env-path | `python -c "from backend.config import settings; assert settings.db_path"` | exit 0 |
| G18-smoke-script | `bash gates/smoke-test.sh [port]` (см. Правило 2) | exit 0 |

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

### Budget cap — HARD STOP

Протокол оркестратора:

1. **Перед каждым spawn-ом агента** (новый builder, validator, LogCraft) —
   выполнить `python gates/budget-calc.py`
2. Если `CostPerAcceptedChange > max_cycle_cost` (из `docs/cycle-config.json`) —
   скрипт возвращает **exit 1**
3. **exit 1 → оркестратор физически блокирует spawn**. Никаких новых задач.
   Единственное действие: сообщить пользователю «Бюджет цикла исчерпан.
   CostPerAcceptedChange: $X. Максимум: $Y. Дождитесь решения администратора.»
4. Игнорирование exit 1 = нарушение протокола оркестратора.

> **M5 — единственный milestone**, для которого `max_cycle_cost` превышает $5.00.
> Значение устанавливается в `docs/cycle-config.json` перед стартом цикла и НЕ может
> быть изменено агентом. Изменение конфига без явного указания пользователя = нарушение.

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
| **`ENV-007`** | **Platform gap** | **Test passes on Linux CI, fails on Windows (dev env). See § Platform Environment.** |
| `CODE-001` | Type/import error | `AttributeError` |
| `CODE-004` | Missing critical code | No `TRANSLATION_SYSTEM_PROMPT` |
| `CODE-005` | Smoke test skipped | No gate log |
| `PLAN-001` | Test URL broken | URL returns 403 |
| `LATENT-001` | Prior milestone bug | M2 bug surfaces in M3 |

Full taxonomy: `docs/loopcraft/LOGCRAFT-SKILL.md` §3.

### M3 Failure Post-Mortem

См. `docs/loopcraft/LOGCRAFT-SKILL.md` §4 — исторические паттерны отказов M3.
LogCraft сверяет новые ошибки с этим архивом для выявления повторяющихся паттернов.

## Platform Environment Awareness (Windows Dev → Linux CI)

**Critical gap**: code is written and tested by agents on Hermes (Windows), but CI/CD runs on GitHub Actions (Ubuntu Linux). Tests that pass on Linux may fail on Windows and vice versa.

### Known platform-specific pitfalls for Python tests

| # | Pitfall | Example | Fix |
|---|---------|---------|-----|
| 1 | `from x import y` creates a local reference. Patching `x.y` after import won't affect the importing module's `y`. | `from openai import AsyncOpenAI` in `translator.py` → patching `openai.AsyncOpenAI` has no effect | Patch `backend.translator.AsyncOpenAI` (the importer), not `openai.AsyncOpenAI` |
| 2 | Lazy imports inside functions (`from backend.db import fn`) create local names, not module attributes. | `patch("backend.translator.get_translation")` fails because `get_translation` is a local variable, not `backend.translator.get_translation` | Patch the source: `patch("backend.db.get_translation")` |
| 3 | `MagicMock` does NOT support `__await__` in Python 3.11. Use `AsyncMock` for anything that will be `await`-ed. | `client.get.return_value = resp` → `await resp` raises `TypeError: object MagicMock can't be used in 'await' expression` | `client.get = AsyncMock(return_value=resp)` |
| 4 | Hardcoded `/tmp/` paths fail on Windows. | `init_db("/tmp/test/db.sqlite")` → `OperationalError: unable to open database file` | Use `tempfile.gettempdir()` or mock the filesystem call / `aiosqlite.connect` |

### Gate validation protocol

Before declaring a gate "passing":

1. **Run EVERY check command locally** — not just "should pass on Linux"
2. If a test fails locally but is expected to pass on Linux CI → **investigate the root cause**. Do not assume. A "should pass" is a bug report waiting to happen.
3. If the root cause is a platform gap (pitfalls above) → mark as `ENV-007` in LogCraft
4. If the root cause is a real code bug → fix it before merge

### CI-only checks (cannot run on Windows)

These checks are safe to skip locally — they only matter in CI:
- Docker builds
- OS-specific path resolution
- Network-dependent smoke tests (need BOT_TOKEN)

## Agent Rules (Mandatory)

1. **ТЗ — source of truth**. Если возникает противоречие — спрашивать, не выдумывать.
2. **Smoke-test — формализован**. Каждый build-агент обязан выполнить `bash gates/smoke-test.sh [port]`
   перед коммитом. Скрипт физически поднимает процесс, пингует порт, проверяет HTTP 200 и парсит тестовый URL.
   Если smoke-test.sh не существует — выполнить эквивалентную команду вручную:
   `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health`.
   Exit code != 0 = задача не принята.
3. **Один осмысленный коммит**. Никаких fixup-ов, wip-ов, «fix typo» в истории.
4. **Имена = бизнес-смысл**. `ShouldEnableCurtain`, не `ModeToIsEnabled`. `parse_article`, не `do_stuff`.
5. **Не трогать лишнего**. Изменения только в скоупе задачи.
6. **Документация = код**. Если меняешь API — обнови README. Если принял решение — пиши ADR.
7. **Git ветка = агент**. `agent/<model>/<task>`. Не пушить в main напрямую.
8. **Логи = structured + semantic anchor**. `[ModuleName] message with {Params}`.
9. **Никаких DeepL/OpenRouter** — только OpenCode Go модели.
10. **Блокирующие вопросы — спрашивать сразу**, не молча выбирать запасной путь.
11. **Любой PR → ревью перед мержем**. Даже «очевидные» изменения (YAML, README). Merge только после явного OK.
12. **Тесты != «должны пройти»**. Каждый тест проверяется локально. Если тест падает — разобраться:
    реальный баг или платформенный gap (ENV-007). Не списывать на «на линуксе пройдёт» без доказательств.
13. **Никаких хардкодных адресов инфраструктуры**. Адреса внешних сервисов (API URL, Mini App URL,
    DB path) — только через конфигурацию: `pydantic-settings` для Python backend, `VITE_` env vars
    для Vite frontend. Никаких зашитых строк `/api`, `localhost:8000` в коде. Default-значения
    допустимы только как fallback при отсутствии переменной.
14. **TypeScript Strict Mode — zero tolerance**. Перед написанием любого frontend-кода — прочитать
    `frontend/tsconfig.json`. Если включены `noUncheckedIndexedAccess` / `noUnusedLocals` /
    `noUnusedParameters` / `strict: true` — писать код, который проходит `tsc -b` **с первого раза**.
    Каждый доступ по индексу (`arr[i]`, `obj[k]`) требует null-guard. Каждый импорт — используется.
    Нарушение = блокировка pre-commit hook (G15). Не полагаться на CI как на первую линию обороны.

15. **Git hooks — hard constraint**. Настроены `gates/git-agent.sh` + `pre-commit`/`pre-push` хуки.
    - **pre-commit**: TypeScript typecheck (`tsc --noEmit`) на изменённых файлах
    - **pre-push**: полная сборка (`npm run build`) + Python тесты (`pytest`)
    - Коммиты с ошибками типов или упавшими тестами **физически блокируются**.
    - При ошибке хука — прочитать вывод, исправить код, повторить коммит.
    - Единственное исключение — известный платформенный gap (ENV-007), задокументированный в LogCraft.

16. **`gates/git-agent.sh` — обязателен для агентов**. Никогда не использовать bare `git commit` или `git push`.
    Всегда: `gates/git-agent.sh commit -m "..."` и `gates/git-agent.sh push origin branch`.
    Флаг `--no-verify` физически заблокирован в обёртке.

### Инitialization Checklist (для кодеров)

Перед написанием любого кода — выполнить (если оркестратор не предоставил конфиги явно):

- [ ] Прочитать `frontend/tsconfig.json` — запомнить `strict`, `noUncheckedIndexedAccess`, `noUnusedLocals`
- [ ] Прочитать `frontend/package.json` → `scripts.build` / `scripts.typecheck`
- [ ] Прочитать `backend/pyproject.toml` или `.ruff.toml` — правила линтинга
- [ ] Убедиться, что `gates/setup-hooks.sh` выполнен (хуки установлены)
- [ ] Проверить, что `gates/git-agent.sh` в `$PATH` или доступен по относительному пути

Если какой-то конфиг не найден — запросить у оркестратора. Не гадать значение.

## Open Questions (собираем здесь)

- [x] Telegram bot token — Mark даст перед M4
- [ ] Домен для Mini App — Mark даст перед M7
- [ ] VPS провайдер — Hetzner? (предложение в плане M7)
- [ ] Max budget per milestone: $5 for economy, $15 for full race. Acceptable? (Mark: confirm)
- [ ] Should LogCraft run even when all gates pass? (recommended: yes, for audit trail)
- [ ] Compute rate: $0.50/min (assumes VPS cost). Accurate? (Mark: confirm)

## Build & Test

- **M1**: Frontend `npm run build` ✅ (Vite + tsc), backend imports ✅ (FastAPI + aiogram)
- **M2**: Parser ✅ (DSV4 winner): POST /api/parse → 416 blocks, cache hit < 50ms, /health preserved
- **M3**: Translation ✅ (DSV4Flash winner): translate block returns RU text, code preserved, batch works
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
