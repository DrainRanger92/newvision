# LoopCraft Skill

Automated quality gates, cost accounting, and hard-stop conditions for the multi-agent development loop.

---

## 1. Core Metric: CostPerAcceptedChange

```
CostPerAcceptedChange = (Σ token_cost + Σ compute_minutes × $0.50/min) / accepted_PRs
```

### Budget Log Format (`budget.json`)

Located at `docs/budget.json`. One JSON array, each entry is a cycle.

```json
[
  {
    "cycle_id": "M4-bot-integration",
    "provider": "deepseek-api",
    "mode": "economy",
    "started_at": "2026-06-17T10:00:00Z",
    "completed_at": "2026-06-17T10:25:00Z",
    "phases": {
      "architect": {
        "agents": [
          {"model": "deepseek/deepseek-v4-pro", "token_cost": 0.15, "compute_minutes": 3.2}
        ],
        "total_token_cost": 0.15
      },
      "build": {
        "agents": [
          {"model": "deepseek/deepseek-v4-flash", "token_cost": 0.18, "compute_minutes": 8.0}
        ],
        "total_token_cost": 0.18
      },
      "validate": {
        "agents": [
          {"model": "deepseek/deepseek-v4-pro", "token_cost": 0.08, "compute_minutes": 4.5}
        ],
        "total_token_cost": 0.08
      }
    },
    "total_token_cost": 0.41,
    "total_compute_minutes": 15.7,
    "compute_cost": 7.85,
    "total_cost": 8.26,
    "accepted_prs": 1,
    "cost_per_accepted_change": 8.26,
    "gates": {
      "env-check": "PASS",
      "build-typecheck": "PASS",
      "smoke-curl": "PASS",
      "key-presence": "PASS",
      "commit-check": "PASS"
    },
    "failures": [],
    "logcraft_report": "docs/logcraft/M4-report.json",
    "winner_branch": "agent/deepseek-v4-flash/M4-bot-integration",
    "winner_commit": "abc1234"
  }
]
```

### Budget calculation script (`gates/budget-calc.py`)

```python
#!/usr/bin/env python3
"""Calculate CostPerAcceptedChange from budget.json entries."""
import json
import sys

COMPUTE_RATE = 0.50  # $/min

def main(path="docs/budget.json"):
    with open(path) as f:
        cycles = json.load(f)
    for c in cycles:
        token = c["total_token_cost"]
        compute_cost = c["total_compute_minutes"] * COMPUTE_RATE
        total = token + compute_cost
        c["compute_cost"] = compute_cost
        c["total_cost"] = total
        prs = max(c["accepted_prs"], 1)
        c["cost_per_accepted_change"] = total / prs
    with open(path, "w") as f:
        json.dump(cycles, f, indent=2)
    total_across = sum(c["total_cost"] for c in cycles)
    print(f"Total cycles: {len(cycles)}")
    print(f"Total cost: ${total_across:.2f}")
    for c in cycles:
        print(f"  {c['cycle_id']}: ${c['cost_per_accepted_change']:.2f}/PR")

if __name__ == "__main__":
    main(*sys.argv[1:])
```

---

## 2. Hard Gates Table

Every gate is automatable — no human judgment. FAIL triggers automatic action.

| Gate ID | When | Command | PASS Criteria | FAIL Action |
|---------|------|---------|---------------|-------------|
| `G1-env-file` | Pre-flight | `test -f backend/.env` | File exists | Block cycle. Print: "MISSING: backend/.env — create from backend/.env.example" |
| `G2-key-presence` | Pre-flight | `python gates/check-env-keys.py` | All required keys non-empty | Block cycle. Print missing keys. |
| `G3-balance` | Pre-flight | `python gates/check-balance.py` | Balance > $0.10 on cheapest provider | Block cycle. Print: "INSUFFICIENT BALANCE on <provider>. Top up or switch provider." |
| `G4-port-free` | Pre-flight | `python gates/check-port.py 8000` | Port not in use | Block cycle. Print: "PORT 8000 occupied — kill the process or use different port." |
| `G5-imports` | Build (per-agent) | `PYTHONPATH=. python -c "from backend.main import app; print('OK')"` | stdout="OK", exit 0 | Kill agent. Escalate model. Log: `CODE-001` |
| `G6-frontend-build` | Build (per-agent) | `cd frontend && npm run build` | exit 0, no errors in stderr | Kill agent. Escalate model. Log: `CODE-001` |
| `G7-lint` | Build (per-agent) | `ruff check backend/` | exit 0 | Kill agent. Escalate model. Log: `CODE-001` |
| `G8-smoke-start` | Build (per-agent) | Start uvicorn, wait 2s, `curl -s http://localhost:$PORT/health` | `{"status":"ok"}` | Kill agent. Escalate model. Log: `ENV-003` if port conflict, else `CODE-005` |
| `G9-smoke-parse` | Build (per-agent) | `curl -s -X POST localhost:$PORT/api/parse -H 'Content-Type: application/json' -d '{"url":"<test-url>"}'` | Response has `blocks` array with length > 0 | Kill agent. Escalate model. Log: `PLAN-001` if test URL 403, else `CODE-003` |
| `G10-smoke-translate` | Build (per-agent) | Translate smoke: parse article → translate first translatable block → verify `translated_text` non-empty | `translated_text` not empty, `error` is false | Kill agent. Escalate model. Log: `LATENT-001` |
| `G11-system-prompt` | Build (per-agent) | `grep -q "TRANSLATION_SYSTEM_PROMPT" backend/translator.py` | Match found | Kill agent. Escalate model. Log: `CODE-004` |
| `G12-commit` | Post-build | `git log --oneline -1` (in agent workdir) | Shows a commit with non-empty message | Fallback: `git add -A && git commit -m "..."`. If still fails → FAIL agent. |
| `G13-diff-nonempty` | Post-build | `git diff main..agent/<branch> --stat` | At least 1 file changed | FAIL agent. Skip this agent's branch. |
| `G14-test-urls` | Pre-build | `python gates/validate-test-urls.py` | All smoke-test URLs return 200 | Block cycle. Print: "TEST URL <url> returned <status>. Replace in smoke-test config." |
| `G15-typecheck` | Build (per-agent) | `cd frontend && npx tsc --noEmit` | exit 0 | Kill agent. Escalate model. Log: `CODE-001` |
| `G16-env-path` | Build (per-agent) | `python -c "from backend.config import settings; assert settings.db_path, 'db_path empty'"` | exit 0, no assertion errors | Kill agent. Log: `ENV-006` |

---

## 3. Gate Automation Scripts

### `gates/check-env-keys.py`

```python
#!/usr/bin/env python3
"""Verify all required environment keys are present and non-empty."""
import os
import sys

REQUIRED_KEYS = {
    "deepseek": ["DEEPSEEK_API_KEY"],
    # "anthropic": ["ANTHROPIC_API_KEY"],  # only when escalated
}
OPTIONAL_KEYS = ["BOT_TOKEN", "BOT_ENABLED", "CORS_ORIGINS", "DB_PATH"]

def check_provider(provider, keys):
    missing = []
    for k in keys:
        val = os.getenv(k, "")
        if not val:
            missing.append(k)
    return missing

def main():
    from pathlib import Path
    env_path = Path("backend/.env")
    if not env_path.exists():
        print(f"FAIL: {env_path} not found")
        sys.exit(1)
    # Load .env
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

    all_ok = True
    for provider, keys in REQUIRED_KEYS.items():
        missing = check_provider(provider, keys)
        if missing:
            print(f"FAIL: {provider} missing keys: {', '.join(missing)}")
            all_ok = False
    if all_ok:
        print("PASS: all required keys present")
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### `gates/check-balance.py`

```python
#!/usr/bin/env python3
"""Check provider balance by making a trivial API call."""
import os
import sys
import httpx

PROVIDERS = [
    {
        "name": "deepseek",
        "url": "https://api.deepseek.com/v1/chat/completions",
        "api_key_env": "DEEPSEEK_API_KEY",
        "model": "deepseek-chat",
        "min_balance": 0.10,
    },
]

def check_provider(p):
    api_key = os.getenv(p["api_key_env"], "")
    if not api_key:
        print(f"SKIP {p['name']}: no API key")
        return True
    try:
        response = httpx.post(
            p["url"],
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": p["model"],
                "messages": [{"role": "user", "content": "OK"}],
                "max_tokens": 1,
            },
            timeout=10,
        )
        if response.status_code == 402:
            print(f"FAIL: {p['name']} — insufficient balance (HTTP 402)")
            return False
        if response.status_code == 200:
            print(f"PASS: {p['name']} — balance available")
            return True
        print(f"WARN: {p['name']} — HTTP {response.status_code}: {response.text[:200]}")
        return True  # Don't block on unknown errors
    except Exception as e:
        print(f"WARN: {p['name']} — check failed: {e}")
        return True  # Don't block on network errors

def main():
    # Load .env
    env_path = "backend/.env"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")
    all_ok = True
    for p in PROVIDERS:
        if not check_provider(p):
            all_ok = False
    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()
```

### `gates/check-port.py`

```python
#!/usr/bin/env python3
"""Check if a port is available."""
import socket
import sys

def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            s.close()
            print(f"PASS: port {port} free")
            return True
        except OSError:
            print(f"FAIL: port {port} occupied")
            return False

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    sys.exit(0 if check_port(port) else 1)
```

### `gates/validate-test-urls.py`

```python
#!/usr/bin/env python3
"""Validate that smoke-test URLs are reachable."""
import sys
import httpx

# URLs used in smoke tests — update per milestone
TEST_URLS = [
    "https://realpython.com/python-f-strings/",
    "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Functions",
]

def main():
    all_ok = True
    for url in TEST_URLS:
        try:
            r = httpx.get(url, follow_redirects=True, timeout=15, headers={
                "User-Agent": "CurtainReader/1.0 SmokeTest"
            })
            if r.status_code == 200:
                print(f"PASS: {url} → {r.status_code}")
            elif r.status_code == 403:
                print(f"FAIL: {url} → 403 Forbidden (bot blocked)")
                all_ok = False
            else:
                print(f"WARN: {url} → {r.status_code}")
        except Exception as e:
            print(f"FAIL: {url} → {e}")
            all_ok = False
    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()
```

### `gates/build-gate.sh`

```bash
#!/usr/bin/env bash
# Per-agent build gate. Run in agent workdir.
# Usage: PORT=8001 bash gates/build-gate.sh
set -euo pipefail

PORT="${PORT:-8000}"
FAILURES=0

echo "=== G5: Backend imports ==="
PYTHONPATH=. python -c "from backend.main import app; print('OK')" || { echo "G5 FAIL"; FAILURES=$((FAILURES+1)); }

echo "=== G7: Lint ==="
ruff check backend/ || { echo "G7 FAIL"; FAILURES=$((FAILURES+1)); }

echo "=== G6: Frontend build ==="
cd frontend && npm run build || { echo "G6 FAIL"; FAILURES=$((FAILURES+1)); cd ..; }
cd ..

echo "=== G15: Frontend typecheck ==="
cd frontend && npx tsc --noEmit || { echo "G15 FAIL"; FAILURES=$((FAILURES+1)); cd ..; }
cd ..

echo "=== G16: Config path check ==="
python -c "from backend.config import settings; assert settings.db_path, 'db_path empty'" || { echo "G16 FAIL"; FAILURES=$((FAILURES+1)); }

echo "=== G11: System prompt check ==="
grep -q "TRANSLATION_SYSTEM_PROMPT" backend/translator.py || { echo "G11 FAIL: missing system prompt"; FAILURES=$((FAILURES+1)); }

# Kill any existing uvicorn on this port
lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
sleep 1

echo "=== G8: Smoke start ==="
uvicorn backend.main:app --port $PORT &
UV_PID=$!
sleep 3
curl -s http://localhost:$PORT/health | grep -q '"status":"ok"' || { echo "G8 FAIL"; kill $UV_PID 2>/dev/null; FAILURES=$((FAILURES+1)); }

if [ $FAILURES -gt 0 ]; then
    kill $UV_PID 2>/dev/null || true
    echo "=== RESULT: $FAILURES gate(s) failed ==="
    exit 1
fi

echo "=== RESULT: all gates passed ==="
kill $UV_PID 2>/dev/null || true
exit 0
```

### `gates/commit-gate.sh`

```bash
#!/usr/bin/env bash
# Post-build commit gate. Run in agent workdir.
set -euo pipefail

echo "=== G12: Commit check ==="
COMMITS=$(git log --oneline -1 2>/dev/null || echo "")
if [ -z "$COMMITS" ]; then
    echo "G12 FAIL: no commits found. Attempting fallback commit..."
    git add -A
    git commit -m "$(whoami)-agent-build" || { echo "G12 FAIL: could not auto-commit"; exit 1; }
fi

echo "=== G13: Diff nonempty check ==="
BRANCH=$(git branch --show-current)
DIFF=$(git diff "main..$BRANCH" --stat 2>/dev/null || echo "")
if [ -z "$DIFF" ]; then
    echo "G13 FAIL: no changes on branch $BRANCH"
    exit 1
fi
echo "PASS: diff has changes"
exit 0
```

---

## 4. Hard Stop Conditions

User-defines these per cycle. If any triggers, the ENTIRE cycle stops.

```json
{
  "max_cycle_cost": 5.00,
  "max_cycle_minutes": 30,
  "max_agent_retries": 2,
  "required_gates": ["G1", "G2", "G3", "G4", "G8", "G9", "G12"],
  "stop_on": {
    "all_architects_fail": true,
    "all_builders_fail": true,
    "consecutive_gate_failures": 3,
    "provider_balance_empty": true
  }
}
```

Hard-stop enforcement pseudocode in orchestrator:

```python
def should_stop(state):
    if state.elapsed_minutes > stop_conditions["max_cycle_minutes"]:
        return True, "Max cycle time exceeded"
    if state.total_cost > stop_conditions["max_cycle_cost"]:
        return True, "Max cycle cost exceeded"
    if state.agent_retries > stop_conditions["max_agent_retries"]:
        return True, "Max agent retries exceeded"
    if state.consecutive_gate_failures >= stop_conditions["stop_on"]["consecutive_gate_failures"]:
        return True, "Too many consecutive gate failures"
    return False, None
```

---

## 5. Context Modules

Prevent agents from reinventing the project from scratch. Each milestone defines an explicit file allow-list.

### Context Module Specification (`context-modules.json`)

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
      "frontend/src/",
      "docs/milestones/M4-bot-integration.md"
    ],
    "context_summary": "Bot receives URL → calls /api/parse → returns Mini App button with article URL. Frontend shows Reader page with article data from API."
  }
}
```

Agents receive the `context_summary` in their prompt, plus the full `read_only` files. They may only modify `read_write` files. Gate scripts verify this at commit time.

### Context guard gate (`G17-context-guard`)

```bash
#!/usr/bin/env bash
# Check that agent only modified allowed files
MILESTONE="$1"
ALLOWED_FILE="docs/context-modules.json"
python -c "
import json, sys, subprocess
with open('$ALLOWED_FILE') as f:
    modules = json.load(f)
allowed = set(modules['$MILESTONE']['read_write'])
changed = subprocess.check_output(['git', 'diff', '--name-only', 'main..HEAD']).decode().split()
violations = [f for f in changed if not any(f.startswith(a) for a in allowed)]
if violations:
    print('CONTEXT VIOLATION: modified files outside scope:')
    for v in violations:
        print(f'  {v}')
    sys.exit(1)
print('PASS: all changes within allowed scope')
" || exit 1
```

---

## 6. Flow Diagram

```
                          ┌─────────────────────────┐
                          │  USER: define problem,   │
                          │  design gate, set budget, │
                          │  set hard-stop conditions  │
                          └────────────┬────────────┘
                                       │
                          ┌────────────▼────────────┐
                          │    PRE-FLIGHT (sync)     │
                          │  G1 env-file             │
                          │  G2 key-presence         │
                          │  G3 balance              │
                          │  G4 port-free            │
                          │  G14 test-urls           │
                          └─┬──────────┬────────────┘
                            │ ALL PASS │ ANY FAIL
                            ▼          ▼
               ┌────────────────┐  ┌──────────────────┐
               │ ARCHITECT RACE │  │ REPORT TO USER,   │
               │ (N parallel)   │  │ STOP CYCLE        │
               └───────┬────────┘  └──────────────────┘
                       │
               ┌───────▼────────┐
               │ PLAN VALIDATE  │
               │ (independent)  │
               └───────┬────────┘
                       │
         ┌─────────────▼─────────────┐
         │    BUILD RACE (N parallel)│
         │                           │
         │  PER AGENT LOOP:          │
         │  ┌──────────────────┐     │
         │  │ clone → branch   │     │
         │  │ ↓                │     │
         │  │ BUILD-GATES      │     │
         │  │ G5 imports       │     │
         │  │ G6 frontend-build│     │
         │  │ G7 lint          │     │
         │  │ G11 system-prompt│  ◄── FAIL → kill agent,
         │  │ G15 typecheck    │     │     escalate model,
         │  │ G16 env-path     │     │     retry (max N)
         │  │ G8 smoke-start   │     │
         │  │ G9 smoke-parse   │     │
         │  │ G10 smoke-xlate  │     │
         │  │ ↓ ALL PASS       │     │
         │  │ G12 commit       │     │
         │  │ G13 diff-nonempty│     │
         │  │ G17 context-guard│     │
         │  └──────────────────┘     │
         └─────────────┬─────────────┘
                       │
         ┌─────────────▼──────────────┐
         │    BUILD VALIDATE          │
         │    (independent model)     │
         │    Data integrity check    │
         └─────────────┬──────────────┘
                       │
         ┌─────────────▼──────────────┐
         │    LOGCRAFT ANALYZE        │
         │    Read all logs           │
         │    Classify failures       │
         │    Write taxonomy report   │
         └─────────────┬──────────────┘
                       │
         ┌─────────────▼──────────────┐
         │    MERGE + REPORT          │
         │    Squash best branch      │
         │    Update budget.json      │
         │    Write cycle report      │
         └────────────────────────────┘
```

---

## 7. Integration with Existing Multi-Agent Loop

LoopCraft **wraps** the existing multi-agent loop protocol. It does not replace it.

| Existing Step | LoopCraft Addition |
|---------------|-------------------|
| Step 1: Pre-flight | Add G1-G4 + G14 gates. Add budget initialization. |
| Step 2: Multi-plan | No change. Log craft captures architect logs. |
| Step 3: Plan validation | Log craft captures validator logs. |
| Step 4: Build race | **Before each agent runs**: apply context module (read-only file list). **During agent work**: run build-gate.sh after every file write batch. Gate failures → kill/escalate. |
| Step 5: Monitor | Log craft monitors in parallel. Hard-stop conditions checked every 2 min. |
| Step 6: Validate build | Add G17 context-guard before validator. |
| Step 7: Merge | Update budget.json. Trigger LogCraft analysis. |
| Step 8: Report | Include gate scores + cost breakdown. |

---

## 8. Gate Scorecard (per-cycle report)

```
┌──────────────────────────────────────────────┐
│           M4 BOT INTEGRATION REPORT           │
├──────────────────────────────────────────────┤
│ Cost: $1.43 (token: $0.48, compute: $0.95)   │
│ Time: 19 min                                  │
│ Cost/PR: $1.43                                │
├──────┬─────────────────────────┬──────────────┤
│ Gate │ Name                    │ Result       │
├──────┼─────────────────────────┼──────────────┤
│ G1   │ env-file                │ PASS         │
│ G2   │ key-presence            │ PASS         │
│ G3   │ balance                 │ PASS         │
│ G4   │ port-free               │ PASS         │
│ G5   │ imports                 │ PASS         │
│ G6   │ frontend-build          │ PASS         │
│ G7   │ lint                    │ PASS         │
│ G8   │ smoke-start             │ PASS         │
│ G9   │ smoke-parse             │ PASS         │
│ G10  │ smoke-translate         │ PASS         │
│ G11  │ system-prompt           │ PASS         │
│ G12  │ commit                  │ PASS         │
│ G13  │ diff-nonempty           │ PASS         │
│ G14  │ test-urls               │ PASS         │
│ G15  │ typecheck               │ PASS         │
│ G16  │ env-path                │ PASS         │
│ G17  │ context-guard           │ PASS         │
├──────┴─────────────────────────┼──────────────┤
│ LogCraft: 0 failures classified│              │
│ Winner: agent/dsv4-flash/M4    │              │
│ Commit: abc1234                │              │
└────────────────────────────────┴──────────────┘
```
