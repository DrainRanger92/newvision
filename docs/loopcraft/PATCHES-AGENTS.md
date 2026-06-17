# Proposed Patches to `AGENTS.md` (curtain-reader)

This document specifies exact additions and modifications to `AGENTS.md` for LoopCraft integration. Each patch references the section it modifies and provides the complete replacement text.

---

## Patch A: New Section — "Gate Checklist Per Milestone" (insert after Milestones list, before Agent Rules)

**Insert after line 121** (after the M7 milestone line):

```markdown

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
```

---

## Patch B: New Section — "Context Modules" (insert after Gate Checklist)

```markdown

## Context Modules

Each milestone defines a file allow-list to prevent agents from modifying code outside scope.

Location: `docs/context-modules.json`

### M4 Context Module (Bot Integration)

```json
{
  "M4-bot-integration": {
    "read_only": [
      "TZ.md",
      "AGENTS.md",
      "backend/models.py",
      "backend/parser.py",
      "backend/translator.py",
      "backend/db.py",
      "backend/config.py",
      "backend/requirements.txt",
      "docs/milestones/M1-skeleton.md",
      "docs/milestones/M2-parser.md",
      "docs/milestones/M3-translation.md",
      "docs/milestones/M4-bot-integration.md"
    ],
    "read_write": [
      "backend/bot.py",
      "backend/main.py",
      "frontend/src/"
    ],
    "context_summary": "Bot receives URL → validates → calls /api/parse → returns Mini App button with article URL. Frontend Reader page fetches article from API and renders it."
  }
}
```

### M5 Context Module (Curtain UX)

```json
{
  "M5-curtain-ux": {
    "read_only": [
      "TZ.md",
      "AGENTS.md",
      "backend/main.py",
      "backend/models.py",
      "backend/parser.py",
      "backend/translator.py",
      "backend/db.py",
      "backend/config.py",
      "backend/bot.py",
      "backend/requirements.txt",
      "docs/milestones/M1-M4-all.md"
    ],
    "read_write": [
      "frontend/src/components/CurtainBlock.tsx",
      "frontend/src/components/ArticleRenderer.tsx",
      "frontend/src/hooks/useCurtain.ts",
      "frontend/src/pages/Reader.tsx"
    ],
    "context_summary": "Touch swipe gesture on paragraph blocks. Swipe up by ~30% → block snaps to 'translated' state showing Russian text. Swipe down → snaps back to English. Code blocks are inert. 60fps animation."
  }
}
```

### M6 Context Module (Theme + Polish)

```json
{
  "M6-theme-polish": {
    "read_only": [
      "TZ.md", "AGENTS.md",
      "backend/", "frontend/src/components/CurtainBlock.tsx",
      "docs/milestones/"
    ],
    "read_write": [
      "frontend/src/styles/",
      "frontend/src/components/CodeBlock.tsx",
      "frontend/src/hooks/useTranslation.ts"
    ],
    "context_summary": "Auto-detect Telegram theme (light/dark) via @twa-dev/sdk. Apply CSS variables. Ensure inline-code inside paragraphs is preserved (not translated). Syntax highlight code blocks."
  }
}
```

### M7 Context Module (Deploy)

```json
{
  "M7-deploy": {
    "read_only": [
      "TZ.md", "AGENTS.md", "backend/", "frontend/src/",
      "docs/milestones/"
    ],
    "read_write": [
      "docker-compose.yml",
      "backend/Dockerfile",
      "frontend/Dockerfile",
      "docs/deploy/"
    ],
    "context_summary": "VPS deployment: backend on Hetzner VPS (Docker), frontend on Vercel (static). HTTPS via Caddy/Traefik. Smoke test on real device."
  }
}
```

Agents receive their milestone's `context_summary` + `read_only` file contents in the prompt.
They may ONLY modify `read_write` files. Gate G17 enforces this.
```

---

## Patch C: New Section — "Updated Model Table for LoopCraft Roles" (replace existing model table)

**Replace lines 28-35** (the "Available Models" table) with:

```markdown
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
```

---

## Patch D: New Section — "Cost Tracking" (insert after Updated Model Table)

```markdown

## Cost Tracking

Every cycle writes to `docs/budget.json`. Metric: `CostPerAcceptedChange`.

### Running total

```bash
python gates/budget-calc.py
```

### Cycle cost log (`docs/budget.json`)

Each cycle appends an entry. Example:

```json
{
  "cycle_id": "M4-bot-integration",
  "provider": "deepseek-api",
  "mode": "economy",
  "started_at": "2026-06-17T10:00:00Z",
  "completed_at": "2026-06-17T10:25:00Z",
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
```

---

## Patch E: New Section — "LogCraft Reports" (insert after Cost Tracking)

```markdown

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
```

---

## Patch F: Modify "Build & Test" section (add gate commands)

**Replace lines 142-146** with:

```markdown
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
```

---

## Patch G: Add `gates/` directory to Project Structure

**In the project structure diagram (lines 42-79)**, add:

```
├── gates/
│   ├── build-gate.sh
│   ├── commit-gate.sh
│   ├── context-guard.sh
│   ├── check-env-keys.py
│   ├── check-balance.py
│   ├── check-port.py
│   ├── validate-test-urls.py
│   └── budget-calc.py
├── docs/
│   ├── decisions/
│   ├── milestones/
│   ├── loopcraft/
│   │   ├── LOOPCRAFT-SKILL.md
│   │   ├── LOGCRAFT-SKILL.md
│   │   ├── PATCHES-multi-agent-loop.md
│   │   └── PATCHES-AGENTS.md
│   ├── logcraft/
│   │   └── M*-report.json
│   ├── budget.json
│   ├── context-modules.json
│   └── cycle-config.json
```

---

## Patch H: Add LogCraft to Agent Loop Protocol

**Insert after Step 6 (Validate build)** in the Agent Loop Protocol section, add a new step:

```markdown
6.5 **LogCraft (synchronous, 2-5 minutes)**:
    - Run LogCraft agent on all cycle logs
    - Agent produces `docs/logcraft/{cycle-id}-report.json`
    - If failures found: review, fix trivial ones, re-run gates
    - If unfixable failures: report to user before merge
    - Zero failures = proceed to merge
```

---

## Patch I: Add Open Question — "Budget thresholds"

**Append to Open Questions (line 139)**:

```markdown
- [ ] Max budget per milestone: $5 for economy, $15 for full race. Acceptable? (Mark: confirm)
- [ ] Should LogCraft run even when all gates pass? (recommended: yes, for audit trail)
- [ ] Compute rate: $0.50/min (assumes VPS cost). Accurate? (Mark: confirm)
```
```

---

## Summary of AGENTS.md Patches

| # | Section | Action | Lines affected |
|---|---------|--------|---------------|
| A | Gate Checklist | New section after milestones | +after L121 |
| B | Context Modules | New section | +after Patch A |
| C | Model Table | Replace existing (L28-35) | L28-35 |
| D | Cost Tracking | New section | +after Patch C |
| E | LogCraft Reports | New section | +after Patch D |
| F | Build & Test | Replace existing (L142-146) | L142-146 |
| G | Project Structure | Add `gates/` and `docs/loopcraft/` | L42-79 |
| H | Agent Loop Protocol | Add LogCraft step 6.5 | +after Step 6 |
| I | Open Questions | Append budget thresholds | +after L139 |
