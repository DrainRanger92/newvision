# LogCraft Agent Skill

Post-cycle log analysis agent. Runs after every cycle. Reads ALL logs from all phases, classifies failures using a taxonomy, proposes concrete fixes.

---

## 1. Role

LogCraft is a **separate agent** that runs after the build validator and before merge. It:

1. Collects logs from: architects, plan-validator, builders, build-validator, gate scripts
2. Classifies every failure using the taxonomy below
3. Produces a structured report: what failed, why, how to fix, which gate would have caught it
4. Suggests new gates for failures that slipped through

## 2. Input Sources

| Source | Location | Content |
|--------|----------|---------|
| Architect agent logs | `logs/cycle-{id}/architects/{model}.log` | Full agent session output |
| Plan validator log | `logs/cycle-{id}/plan-validator.log` | Validator reasoning + verdict |
| Builder agent logs | `logs/cycle-{id}/builders/{model}.log` | Full agent session output |
| Gate script output | `logs/cycle-{id}/gates/{gate-id}.log` | PASS/FAIL + stdout/stderr |
| Build validator log | `logs/cycle-{id}/build-validator.log` | Scorecard + reasoning |
| Budget log | `docs/budget.json` | Cost tracking |
| Git diff | `git diff main..agent/<branch>` (cached) | Actual code changes |

## 3. Failure Classification Taxonomy

### ENV — Environment failures (agent couldn't run)

| Code | Pattern | Symptoms | Root Cause |
|------|---------|----------|------------|
| `ENV-001` | Missing API key / config | `DEEPSEEK_API_KEY` empty, 401 from API | .env not copied, wrong env path, key not set |
| `ENV-002` | Insufficient balance | HTTP 402, "Insufficient balance" in response | Provider balance exhausted |
| `ENV-003` | Port occupied | `[Errno 10048]`, "address already in use" | Previous uvicorn not killed |
| `ENV-004` | Wrong Python env | `ModuleNotFoundError`, conflicting package versions | Agent uses parent venv instead of own |
| `ENV-005` | Wrong terminal mode | `&` rejected, syntax error in bash | Shell mode mismatch (foreground vs background) |
| `ENV-006` | env_file path wrong | Config values are empty strings despite .env existing | `SettingsConfigDict(env_file=".env")` is CWD-relative |
| `ENV-007` | Git clone failed | `fatal: destination path already exists` | Stale workdir not cleaned |
| `ENV-008` | Dependency sub-package missing | `ImportError: cannot import name 'clean' from 'lxml.html'` | Library split (e.g. lxml 5.x → `lxml_html_clean`) |

### CODE — Code-level failures (agent produced broken code)

| Code | Pattern | Symptoms | Root Cause |
|------|---------|----------|------------|
| `CODE-001` | Type/import error | `AttributeError`, `ImportError`, `TypeError` at runtime | Agent used wrong API, wrong import |
| `CODE-002` | API contract violation | Endpoint returns 500, validator rejects | Agent deviated from plan without justification |
| `CODE-003` | Logic bug (latent) | 0 blocks, empty response, silent failure | Agent didn't test edge case (e.g. `<html>` wrapper) |
| `CODE-004` | Missing critical code | Key function/constant missing (e.g. no `TRANSLATION_SYSTEM_PROMPT`) | Agent omitted a required piece |
| `CODE-005` | Smoke test skipped | Agent exited 0 but no curl/test output in logs | Agent bypassed smoke test requirement |
| `CODE-006` | Test URL broken | Smoke test uses URL that returns 403/404 | URL not validated before use |

### PLAN — Planning failures (plan was wrong)

| Code | Pattern | Symptoms | Root Cause |
|------|---------|----------|------------|
| `PLAN-001` | Test URL unreachable | Smoke-parse returns 0 blocks because URL blocked | Plan didn't validate test URLs |
| `PLAN-002` | Missing pre-condition | Agent fails because Docker/node/Python version missing | Plan assumed unavailable tool |
| `PLAN-003` | Port conflict in plan | Multiple agents race on same port | Plan didn't assign per-agent ports |
| `PLAN-004` | Scope creep | Agent modifies files outside milestone scope | Plan didn't define file allow-list |
| `PLAN-005` | Missing dependency declaration | `ImportError: No module named 'X'` | Plan didn't list all required packages |

### LATENT — Latent bugs (prior milestone bug surfaces now)

| Code | Pattern | Symptoms | Root Cause |
|------|---------|----------|------------|
| `LATENT-001` | Prior milestone bug | Function from M2 breaks in M3 | Bug existed but wasn't caught by M2 smoke test |
| `LATENT-002` | Data format incompatible | Old data in DB fails new schema validation | Schema changed without migration |
| `LATENT-003` | API response shape changed | Frontend expects field that backend removed | Contract drift between milestones |

---

## 4. Auto-Diagnosis Patterns for M3 Failures

Each M3 failure → taxonomy code + detection pattern + fix.

### M3-001: 3 architects failed 'Insufficient balance'

```
TAXONOMY: ENV-002
DETECTION: grep "Insufficient balance\|HTTP 402\|402 Payment" in architect logs
           All architects failed within 30 seconds
ROOT CAUSE: No pre-flight balance check
FIX: Add G3-balance gate to pre-flight step
GATE: G3-balance (python gates/check-balance.py)
PREVENTION: Run check-balance.py before launching any agents
```

### M3-002: Parser 0 blocks (realpython 403)

```
TAXONOMY: PLAN-001
DETECTION: grep "blocks=0" in builder log, cross-ref with test URL
           curl test URL → HTTP 403
ROOT CAUSE: Smoke-test URLs not validated before build
FIX: Add G14-test-urls gate
GATE: G14-test-urls (python gates/validate-test-urls.py)
PREVENTION: Run validate-test-urls.py at pre-flight
```

### M3-003: Parser 0 blocks (all URLs) — latent M2 bug

```
TAXONOMY: LATENT-001
DETECTION: blocks=0 for ALL URLs (not just realpython)
           Inspect classify_blocks() in backend/parser.py — no unwrap of <html>/<body>
ROOT CAUSE: classify_blocks doesn't handle top-level <html>/<body> wrappers from readability
FIX: In classify_blocks, iterate soup.children and recurse for <html>/<body> tags
CODE PATCH:
  def classify_blocks(cleaned_html):
      soup = BeautifulSoup(cleaned_html, "lxml")
      blocks = []
      for child in list(soup.children):
          blocks.extend(_classify_element(child))
      return blocks
  # _classify_element already handles div/section/article/html/body recursion
PREVENTION: G9-smoke-parse with a known-good URL catches 0-block returns
```

### M3-004: 500 on translate — Annotated[Union[...]] has no model_validate

```
TAXONOMY: LATENT-001
DETECTION: grep "AttributeError.*Annotated.*model_validate" in builder log
           Error in _row_to_article() in backend/db.py
ROOT CAUSE: Pydantic v2: Annotated[Union[...]] is not a BaseModel subclass
FIX: Use TypeAdapter(list[Block]).validate_python(data) instead of Block.model_validate()
PREVENTION: G5-imports gate catches this (backend imports fail)
             G10-smoke-translate gate catches this (translate endpoint fails)
```

### M3-005: Port 8000 occupied

```
TAXONOMY: ENV-003
DETECTION: grep "[Errno 10048]\|address already in use" in builder log
ROOT CAUSE: Previous uvicorn process not killed before starting new one
FIX: Add `lsof -ti:8000 | xargs kill -9 2>/dev/null || true` before uvicorn start
GATE: G4-port-free catches this at pre-flight; G8-smoke-start catch at build-time
PREVENTION: build-gate.sh includes kill-before-start logic
```

### M3-006: '&' in foreground rejected

```
TAXONOMY: ENV-005
DETECTION: grep "syntax error\|not allowed in foreground" near uvicorn start commands
ROOT CAUSE: Agent used `&` for backgrounding in a shell that disallows it
FIX: Use `&&` chaining or semicolons instead of background `&`
      Or: wrap in script that starts uvicorn as subprocess
PREVENTION: Agent prompt should specify: "Do not use & for backgrounding. Use && or ;"
```

### M3-007: translate_text without system prompt

```
TAXONOMY: CODE-004
DETECTION: grep "TRANSLATION_SYSTEM_PROMPT" backend/translator.py → no match
           OR: inspect _build_translation_prompt — missing system role
ROOT CAUSE: Builder deviated from plan; omitted the system prompt constant
FIX: Add system prompt back; verify with grep
GATE: G11-system-prompt catches this at build time
PREVENTION: Build gate checks for presence of critical constants
```

### M3-008: API key 5× failed to write to .env

```
TAXONOMY: ENV-001
DETECTION: Count of "DEEPSEEK_API_KEY" + "empty" or "not found" in builder log > 1
           Agent retried writing .env many times
ROOT CAUSE: .env write failed but no pre-check verified the key was present
FIX: Add G2-key-presence gate before agent starts
GATE: G2-key-presence (python gates/check-env-keys.py)
PREVENTION: Key presence check in pre-flight catches missing keys before agents waste time
```

### M3-009: config.py env_file path wrong

```
TAXONOMY: ENV-006
DETECTION: grep "db_path empty\|deepseek_api_key.*empty" in builder log
           SettingsConfigDict(env_file=".env") but .env is in backend/
ROOT CAUSE: Pydantic Settings `env_file` is resolved relative to CWD, not file location
FIX: Set env_file="backend/.env" in SettingsConfigDict
GATE: G16-env-path catches this at build time
PREVENTION: Config import check verifies all settings have non-empty values
```

### M3-010: Builder didn't run smoke test

```
TAXONOMY: CODE-005
DETECTION: No "curl" or "health" or "POST /api/parse" in builder log between
           "uvicorn started" and "git commit"
           Agent exited 0 but G8-G10 would have failed
ROOT CAUSE: Builder skipped smoke test step from plan
FIX: Make smoke test a HARD GATE that must pass before commit. Gate script records
     its own log. Absence of gate log = automatic fail.
GATE: G8-smoke-start + G9-smoke-parse + G10-smoke-translate (in build-gate.sh)
PREVENTION: build-gate.sh runs before commit; exit code > 0 = agent killed
```

---

## 5. LogCraft Report Format

Written to `docs/logcraft/{cycle-id}-report.json`:

```json
{
  "cycle_id": "M4-bot-integration",
  "generated_at": "2026-06-17T10:25:00Z",
  "summary": {
    "total_failures": 0,
    "by_category": {"ENV": 0, "CODE": 0, "PLAN": 0, "LATENT": 0},
    "gates_failed": [],
    "new_gates_recommended": []
  },
  "failures": [
    {
      "failure_id": "M4-001",
      "source_phase": "build",
      "agent_model": "deepseek-v4-flash",
      "category": "CODE-001",
      "detection_pattern": "TypeError: expected str, got NoneType",
      "log_excerpt": "File 'backend/bot.py', line 42, in handle_url...",
      "root_cause": "Agent didn't handle None case for message.text",
      "suggested_fix": "Add `if not message.text: return` guard",
      "gate_to_add": null,
      "existing_gate_that_would_catch": "G5-imports",
      "code_patch": {
        "file": "backend/bot.py",
        "old": "url = message.text",
        "new": "if not message.text:\n    return\nurl = message.text"
      }
    }
  ],
  "recommendations": {
    "new_gates": [],
    "updated_context_modules": [],
    "process_changes": []
  }
}
```

---

## 6. LogCraft Agent Prompt Template

```
You are LogCraft, a post-cycle log analyzer. Read ALL logs from the cycle directory
at logs/cycle-{cycle_id}/ and produce a structured failure report.

INPUT:
- Directory: logs/cycle-{cycle_id}/
- Budget log: docs/budget.json
- Context modules: docs/context-modules.json
- TZ: TZ.md
- AGENTS.md

TASKS:
1. Read every log file in the cycle directory
2. For each error/warning/failure, classify using the taxonomy:
   - ENV-001 through ENV-008
   - CODE-001 through CODE-006
   - PLAN-001 through PLAN-005
   - LATENT-001 through LATENT-003
3. For each failure:
   - extract the exact log line(s) that evidence it
   - determine root cause
   - suggest a concrete fix (actual code patch if applicable)
   - identify which existing gate would have caught it
   - if no existing gate covers it, propose a new gate
4. Write the report to docs/logcraft/{cycle_id}-report.json
5. If zero failures: write a clean report with summary only

TAXONOMY REFERENCE:
<include the full taxonomy table from above>

M3 FAILURE PATTERNS (for cross-reference with latent bugs):
<include the 10 M3 failure patterns>

OUTPUT:
A single JSON report file. No markdown summary — the orchestrator will format it.
```

---

## 7. Log Collection Infrastructure

Before each cycle, create the log directory:

```bash
mkdir -p logs/cycle-{id}/{architects,builders,gates,validators}
```

Each agent redirects its output:

```bash
# Architect
opencode run "..." 2>&1 | tee logs/cycle-M4/architects/{model}.log

# Builder
opencode run "..." 2>&1 | tee logs/cycle-M4/builders/{model}.log

# Gates (per-agent)
bash gates/build-gate.sh 2>&1 | tee logs/cycle-M4/gates/G5-G16-{model}.log

# Validator
opencode run "..." 2>&1 | tee logs/cycle-M4/validators/build-validator.log
```

---

## 8. LogCraft in the Flow

```
PRE-FLIGHT → ARCHITECT → PLAN VAL → BUILD RACE → BUILD VAL → LOGCRAFT → MERGE
                                                              │
                                                              ▼
                                              ┌──────────────────────────┐
                                              │ LogCraft reads all logs   │
                                              │ Classifies failures       │
                                              │ Writes report             │
                                              │ Suggests new gates        │
                                              └──────────┬───────────────┘
                                                         │
                                              ┌──────────▼───────────────┐
                                              │ If failures > 0:          │
                                              │   Review report           │
                                              │   Apply suggested fixes   │
                                              │   Re-run affected gates   │
                                              │ If failures = 0:          │
                                              │   Proceed to merge        │
                                              └──────────────────────────┘
```
