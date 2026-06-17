# Proposed Patches to `multi-agent-development-loop` Skill

This document specifies exact additions and modifications to the existing SKILL.md of the `multi-agent-development-loop` skill. Each patch references the section it modifies and provides the new text.

---

## Patch 1: New Section — "Hard Gates" (insert after "When NOT to Use")

**Insert after line 32** (after "When NOT to Use" section, before "Economy Mode"):

```markdown
## Hard Gates

Every cycle MUST pass automated quality gates. Gates are scripted — no human judgment.
See `gates/` directory for implementations.

| Gate | Phase | FAIL Action |
|------|-------|-------------|
| G1-env-file | Pre-flight | Block cycle |
| G2-key-presence | Pre-flight | Block cycle |
| G3-balance | Pre-flight | Block cycle |
| G4-port-free | Pre-flight | Block cycle |
| G5-imports | Build (per-agent) | Kill agent, escalate model |
| G6-frontend-build | Build (per-agent) | Kill agent, escalate model |
| G7-lint | Build (per-agent) | Kill agent, escalate model |
| G8-smoke-start | Build (per-agent) | Kill agent, escalate model |
| G9-smoke-parse | Build (per-agent) | Kill agent, escalate model |
| G10-smoke-translate | Build (per-agent) | Kill agent, escalate model |
| G11-system-prompt | Build (per-agent) | Kill agent, escalate model |
| G12-commit | Post-build | Fallback commit or FAIL |
| G13-diff-nonempty | Post-build | FAIL agent |
| G14-test-urls | Pre-flight | Block cycle |
| G15-typecheck | Build (per-agent) | Kill agent, escalate model |
| G16-env-path | Build (per-agent) | Kill agent |
| G17-context-guard | Post-build | FAIL agent |

Gates are run by the orchestrator automatically. Any FAIL triggers the specified action.
No build agent may commit before passing G5-G11 and G15-G16.
```

---

## Patch 2: New Section — "Cost Tracking" (insert after Hard Gates)

```markdown
## Cost Tracking

Every cycle writes an entry to `docs/budget.json`. The metric is:

```
CostPerAcceptedChange = (Σ token_cost + Σ compute_minutes × $0.50/min) / accepted_PRs
```

### Budget JSON format

```json
{
  "cycle_id": "M4-bot-integration",
  "provider": "deepseek-api",
  "mode": "economy",
  "started_at": "<ISO timestamp>",
  "completed_at": "<ISO timestamp>",
  "phases": {
    "architect": {"agents": [...], "total_token_cost": 0.15},
    "build": {"agents": [...], "total_token_cost": 0.18},
    "validate": {"agents": [...], "total_token_cost": 0.08}
  },
  "total_token_cost": 0.41,
  "total_compute_minutes": 15.7,
  "compute_cost": 7.85,
  "total_cost": 8.26,
  "accepted_prs": 1,
  "cost_per_accepted_change": 8.26,
  "gates": {"G1": "PASS", "G2": "PASS", ...}
}
```

Update `docs/budget.json` after every merge. Run `python gates/budget-calc.py` to recalculate totals.
```

---

## Patch 3: New Section — "Context Modules" (insert after Cost Tracking)

```markdown
## Context Modules

Prevent agents from reinventing the project. Each milestone defines a file allow-list in
`docs/context-modules.json`.

Format:
```json
{
  "M4-bot-integration": {
    "read_only": [
      "TZ.md", "AGENTS.md",
      "backend/parser.py", "backend/translator.py", "backend/db.py",
      "backend/models.py", "backend/config.py", "backend/requirements.txt",
      "docs/milestones/M1-skeleton.md", "docs/milestones/M2-parser.md",
      "docs/milestones/M3-translation.md", "docs/milestones/M4-bot-integration.md"
    ],
    "read_write": [
      "backend/bot.py",
      "backend/main.py",
      "frontend/src/"
    ],
    "context_summary": "Bot receives URL → calls /api/parse → returns Mini App button."
  }
}
```

Agents receive the `context_summary` in their prompt. They may ONLY modify `read_write` files.
Gate G17-context-guard enforces this at commit time.
```

---

## Patch 4: New Section — "Hard Stop Conditions" (insert after Context Modules)

```markdown
## Hard Stop Conditions

Before each cycle, define stop conditions in `docs/cycle-config.json`:

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

The orchestrator checks these conditions every 2 minutes during the cycle.
If any triggers → stop the ENTIRE cycle and report to user.
```

---

## Patch 5: New Section — "LogCraft Agent" (insert after Hard Stop Conditions)

```markdown
## LogCraft Agent

After every cycle, a LogCraft agent analyzes ALL logs from all phases. It runs BEFORE merge.

### Role
- Reads logs from: architects, plan-validator, builders, build-validator, gate scripts
- Classifies every failure using the LogCraft taxonomy (ENV-xxx, CODE-xxx, PLAN-xxx, LATENT-xxx)
- Produces a structured report at `docs/logcraft/{cycle-id}-report.json`
- Suggests new gates for failures that slipped through

### Failure Taxonomy (summary)

| Prefix | Category | Example |
|--------|----------|---------|
| ENV | Environment | Missing API key, port occupied, wrong env path |
| CODE | Code-level | Type error, missing system prompt, smoke skipped |
| PLAN | Planning | Test URL unreachable, port conflict, missing dep |
| LATENT | Latent bug | Prior-milestone bug surfaces, data format change |

Full taxonomy: see `docs/loopcraft/LOGCRAFT-SKILL.md` §3.

### Running LogCraft

```bash
opencode run "Read logs/cycle-{id}/ and write report per docs/loopcraft/LOGCRAFT-SKILL.md" \
  --model deepseek/deepseek-v4-pro \
  2>&1 | tee logs/cycle-{id}/logcraft.log
```
```

---

## Patch 6: Modify "Step 1: Pre-flight" (add gates + cost init)

**Replace the existing Step 1 text** with:

```markdown
### Step 1: Pre-flight (synchronous, 2 minutes)

- Read project's `TZ.md` and `AGENTS.md`
- Read `docs/cycle-config.json` for hard-stop conditions and budget limit
- **Run pre-flight gates**:
  ```bash
  python gates/check-env-keys.py || { echo "G2 FAIL: missing keys"; exit 1; }
  python gates/check-balance.py || { echo "G3 FAIL: insufficient balance"; exit 1; }
  python gates/check-port.py 8000 || { echo "G4 FAIL: port occupied"; exit 1; }
  python gates/validate-test-urls.py || { echo "G14 FAIL: unreachable test URLs"; exit 1; }
  test -f backend/.env || { echo "G1 FAIL: missing .env file"; exit 1; }
  ```
  Any gate FAIL → **report blocker immediately**, stop cycle. Do not silently switch providers.
- Initialize budget entry in `docs/budget.json`:
  ```json
  {"cycle_id": "M{n}-{name}", "started_at": "<now>", "status": "in_progress"}
  ```
- Verify model pool: `opencode models <provider>` (or check `auth list`)
- Check for blocking open questions — if any, **ask user BEFORE starting the cycle**
- **Pick provider tier**: DeepSeek API (cheapest) → Anthropic API (mid) → opencode (expensive)
- **Create log directories**:
  ```bash
  mkdir -p logs/cycle-{id}/{architects,builders,gates,validators}
  ```
```

---

## Patch 7: Modify "Step 4: Build Race" (add gates + context modules)

**Replace the existing Step 4 text** with:

```markdown
### Step 4: Build race (parallel, background — 10-20 minutes)

- Read context module from `docs/context-modules.json` for this milestone
- Include `context_summary` and `read_only` file list in each builder's prompt
- **Builder prompt MUST include**:
  - "You may ONLY modify these files: <read_write list>"
  - "Before committing, run: PORT=<assigned> bash gates/build-gate.sh"
  - "If build-gate.sh fails: fix the issue and retry. Do NOT commit broken code."
  - "After committing, run: bash gates/commit-gate.sh"
- Assign each agent a **unique port**: `PORT=8001`, `PORT=8002`, `PORT=8003`
- For each build-agent, create an isolated workdir:
  ```bash
  git clone <project> <project>-agent-<model>
  cd <project>-agent-<model>
  git checkout -b agent/<model-slug>/<task-id>
  cp -r ../<project>/gates/ gates/
  cp ../<project>/backend/.env backend/.env
  ```
- Start each agent as a background process with `notify_on_complete=true`:
  ```
  terminal(command="opencode run '...'", workdir="<project>-agent-<model>",
            background=true, notify_on_complete=true, timeout=900)
  ```
- The agent MUST run build-gate.sh before committing. The orchestrator verifies gate
  log presence. Missing gate log = agent skipped smoke test = CODE-005.
- Gate failures: escalate model (cheapest → mid → expensive). Max retries from
  `docs/cycle-config.json` (`max_agent_retries`). After max retries → FAIL that slot.
```

---

## Patch 8: Modify "Step 5: Monitor" (add hard-stop checks + gate monitoring)

**Insert after the existing Step 5 text**:

```markdown
### Step 5a: Hard-stop checks

Every 2 minutes, check hard-stop conditions from `docs/cycle-config.json`:

```python
def check_hard_stops(state, config):
    if state.elapsed_minutes > config["max_cycle_minutes"]:
        return True, "Max cycle time exceeded"
    if state.total_cost > config["max_cycle_cost"]:
        return True, "Max cycle cost exceeded"
    if state.agent_failures >= config["stop_on"]["consecutive_gate_failures"]:
        return True, "Too many consecutive gate failures"
    if not any_agent_alive(state) and config["stop_on"]["all_builders_fail"]:
        return True, "All builders failed"
    return False, None
```

If hard-stop triggers → kill all agents, write partial budget entry, report to user.

### Step 5b: Gate log monitoring

After each agent exits, check for gate log:
```bash
test -f logs/cycle-{id}/gates/G5-G16-{model}.log || echo "CODE-005: agent skipped smoke test"
```
```

---

## Patch 9: Modify "Step 6: Validate Build" (add context guard)

**Insert at the beginning of the existing Step 6 text**:

```markdown
### Step 6: Validate build (synchronous, 5-10 minutes)

**Before validation, run context guard (G17):**
```bash
bash gates/context-guard.sh <milestone-id>
```
If G17 fails → FAIL that branch immediately (agent modified files outside scope).

Then run the build-validator as before:
...
```

---

## Patch 10: Modify "Step 7: Merge" (add LogCraft + budget update)

**Replace the existing Step 7 text** with:

```markdown
### Step 7: Merge

- **Run LogCraft analysis**:
  ```bash
  opencode run "Read all logs in logs/cycle-{id}/ and write report per docs/loopcraft/LOGCRAFT-SKILL.md" \
    --model deepseek/deepseek-v4-pro
  ```
- If LogCraft reports failures > 0:
  - Review report
  - Apply suggested fixes if trivial
  - Re-run affected gates
  - If unfixable → report to user with LogCraft findings
- **If agents committed**: Best branch → squash merge to main with **business-meaningful** message
- **Fallback (no commits)**: Copy winning agent's files → `git add -A` → single commit
- Other branches → close without merge
- **Update budget**: fill in `completed_at`, gate results, token costs, compute minutes
- **Calculate cost**: `python gates/budget-calc.py`
- Write ADR if a non-obvious choice was made
- Update `AGENTS.md` model table if a model underperformed
```

---

## Patch 11: Modify "Step 8: Report to User" (add cost + gate data)

**Replace existing Step 8** with:

```markdown
### Step 8: Report to user

One short message with:
- Which plan won, which build won, key files changed
- Gate scorecard (PASS/FAIL per gate)
- Smoke test result
- Cost breakdown: token $X.XX + compute $X.XX = $X.XX total
- Cost per accepted change: $X.XX
- LogCraft findings (if any)
- What's next milestone
- Use a Markdown table for the gate scorecard
```

---

## Patch 12: New Pitfalls (append to existing "Pitfalls" section)

```markdown
21. **Provider balance is ALWAYS checked in pre-flight**. The M3 failure where all 3 architects failed within 2 seconds due to empty balance is now caught by G3-balance. Never skip this gate.
22. **Smoke test URLs are validated at pre-flight**. G14-test-urls prevents the "Parser 0 blocks (realpython 403)" failure. Test URLs that return 403 are rejected before any agent runs.
23. **Latent bugs from prior milestones** are the most expensive failures. The M3 cycle caught two latent M2 bugs (Annotated model_validate, classify_blocks unwrap). G5-imports and G10-smoke-translate catch these earlier. When a latent bug surfaces, add a gate that would have caught it.
24. **Gate logs are the ONLY evidence** that an agent ran smoke tests. If `gates/` log file is absent → agent skipped tests → CODE-005. Do not trust agent exit codes.
25. **env_file path is ALWAYS validated before agent starts**. G16-env-path catches the CWD-relative footgun in Pydantic Settings. Config import must succeed with non-empty values.
26. **System prompt presence is a hard gate**. G11-system-prompt checks for `TRANSLATION_SYSTEM_PROMPT` in `translator.py`. Critical constants must never be omitted.
27. **Port cleanup before uvicorn start**. G4-port-free + G8-smoke-start includes `lsof -ti:$PORT | xargs kill -9` before starting. Never assume ports are free.
28. **Context modules prevent scope creep**. Agents that modify files outside their `read_write` allow-list are FAILed by G17-context-guard. Define the allow-list in `docs/context-modules.json` before each cycle.
29. **Budget tracking is not optional**. Every cycle writes to `docs/budget.json`. Without tracking, you can't compute CostPerAcceptedChange, and you can't tell if the loop is economically viable.
30. **LogCraft runs every cycle, even clean ones**. A "0 failures" report is valuable — it confirms the gates are working. Skip LogCraft only if the cycle was aborted at pre-flight.
```

---

## Patch 13: Replace "Verification" section

```markdown
## Verification

Smoke-test the loop with a minimal cycle:
- TZ: 3-line goal
- Plan: 2 subtasks
- Build: 2 agents (one model is fine for smoke)
- Validate: same model
- LogCraft: run on logs
- Merge: best wins

Verification criteria:
1. All pre-flight gates (G1-G4, G14) pass
2. Build gates (G5-G11, G15-G16) pass in at least one agent
3. Commit gates (G12, G13, G17) pass
4. LogCraft produces a report at `docs/logcraft/{cycle-id}-report.json`
5. Budget entry written to `docs/budget.json`
6. CostPerAcceptedChange calculated

If that round-trip works, scale to the real cycle.
```

---

## Summary of All Patches

| # | Section | Action |
|---|---------|--------|
| 1 | New: "Hard Gates" | Insert table + explanation |
| 2 | New: "Cost Tracking" | Insert budget format + metric |
| 3 | New: "Context Modules" | Insert file allow-list spec |
| 4 | New: "Hard Stop Conditions" | Insert stop config format |
| 5 | New: "LogCraft Agent" | Insert LogCraft role + taxonomy |
| 6 | Step 1: Pre-flight | Add gates, budget init, log dirs |
| 7 | Step 4: Build race | Add context modules, gates, per-agent ports |
| 8 | Step 5: Monitor | Add hard-stop checks, gate log monitoring |
| 9 | Step 6: Validate build | Add G17 context guard before validator |
| 10 | Step 7: Merge | Add LogCraft analysis, budget update |
| 11 | Step 8: Report | Add cost + gate data to report |
| 12 | Pitfalls | Append pitfalls 21-30 |
| 13 | Verification | Replace with gate-aware smoke test |
