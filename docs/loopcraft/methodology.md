# LoopCraft — Automated Quality Gate Methodology for Multi-Agent Development Cycles

**Author**: Architect Agent #2 (deepseek-v4-pro)
**Date**: 2026-06-17
**Status**: Draft — competing architect perspective

---

## 1. Core Metric

```
Efficiency = (token_cost + time × labor_rate) / accepted_PRs
```

| Variable | Source | Example |
|----------|--------|---------|
| `token_cost` | Sum of provider-reported token usage × pricing across ALL models in cycle | $0.30 DeepSeek flash + $0.50 DeepSeek pro = $0.80 |
| `time` | Wall-clock duration of cycle (hours) | 0.5h |
| `labor_rate` | User-defined hourly rate for overseeing the loop (default: $10/h — the value of operator attention) | 0.5h × $10 = $5 |
| `accepted_PRs` | Number of branches that PASS validation with zero blocking failures | 1 |

**Dashboard format** (printed at end of each cycle):

```
╔══════════════════════════════════════════════════════════════╗
║                    LOOPCRAFT CYCLE M4                       ║
╠══════════════════════════════════════════════════════════════╣
║ Metric          │ Value            │ Target                 ║
╠══════════════════════════════════════════════════════════════╣
║ Token cost      │ $1.42            │ < $3.00                ║
║ Wall-clock time │ 28 min           │ < 30 min               ║
║ Labor (est.)    │ $4.67            │ —                      ║
║ Efficiency      │ $6.09/PR         │ < $15/PR               ║
║ Accepted PRs    │ 1                │ ≥ 1                    ║
║ Gates passed    │ 5/5              │ 100%                   ║
║ Failures logged │ 2                │ —                      ║
╚══════════════════════════════════════════════════════════════╝
║ Top failure: Port 8000 conflict (stale uvicorn)             ║
║ Recommendation: Add pre-flight port-kill gate               ║
╚══════════════════════════════════════════════════════════════╝
```

---

## 2. Budget System

### 2.1 Per-cycle budget

Every cycle has a **hard budget cap** derived from the economy mode table in the multi-agent-development-loop skill:

| Mode | Budget cap | Token cap (est.) | Gate suite |
|------|-----------|-------------------|------------|
| Low (config/deploy) | $1.00 | ~50K tokens | gates: check-balance |
| Medium (new module) | $3.00 | ~150K tokens | gates: check-balance, check-deps, check-imports |
| High (core UX, race) | $15.00 | ~750K tokens | full gate suite |

Budget is **checked at 3 points**:
1. **Pre-flight** (before architects launch) — refuse to start if balance < budget cap
2. **Mid-architect** (after each architect finishes) — if 2 architects used $2 of $3 budget, third architect gets capped prompt (fewer tokens)
3. **Pre-build** (before builders launch) — re-check; if over budget already, collapse to economy mode

### 2.2 Mid-cycle DeepSeek API key expiry

**Critical vulnerability**: If the DeepSeek API key expires or is revoked mid-cycle, ALL running agents fail simultaneously with `401 Unauthorized`.

**Detection**: Gate `check-auth` runs before ANY agent launch. But mid-cycle expiry requires a different mechanism.

**Protocol**:
```
On 401 response from ANY agent:
  1. Kill all running agents immediately (kill -9 equivalent)
  2. Emit structured failure log: {"event":"cycle_aborted","reason":"api_key_expired","provider":"deepseek","timestamp":"..."}
  3. Do NOT escalate to Anthropic automatically — user MUST approve provider switch
  4. Preserve partial work: git stash each workdir before cleanup
  5. Report: "Cycle M4 aborted: DeepSeek API key expired. 
     Options: (1) renew key and re-run, (2) switch to Anthropic ($3-5/build)"
```

**Implementation**: Every agent prompt includes a pre-amble check:
```python
# Preamble check (first tool call of every agent):
# curl -s https://api.deepseek.com/v1/models -H "Authorization: Bearer $DEEPSEEK_API_KEY"
# If 401 → emit "LOOPCRAFT: auth check failed, aborting cycle" and exit 1
```

### 2.3 Multi-provider cost tracking

When a cycle uses multiple providers (e.g. DeepSeek architects + Anthropic escalation builders), costs MUST be tracked per-provider:

```json
{
  "cycle": "M4",
  "mode": "full_race",
  "providers": {
    "deepseek": {
      "models_used": ["deepseek-v4-pro", "deepseek-v4-flash", "deepseek-chat"],
      "total_tokens": {"input": 82000, "output": 34000, "cost": 0.87},
      "agents": 5
    },
    "anthropic": {
      "models_used": ["claude-sonnet-4-5"],
      "total_tokens": {"input": 12000, "output": 3000, "cost": 2.15},
      "agents": 1,
      "reason": "escalation: deepseek-v4-flash builder FAIL on hard gate 'check-imports'"
    }
  },
  "total_cost": 3.02,
  "budget_remaining": 11.98
}
```

**Enforcement**: The orchestrator refuses to launch an agent on a provider whose cumulative cost already exceeds its budget share. Budget share = total budget / number of providers expected to participate.

---

## 3. Escalation Protocol v2 (Hard-Gate-Aware)

The original escalation protocol (Skill § Economy Mode) is replaced by:

```
Builder (cheapest model)
  ├─ Hard gates PASS → soft-smoke PASS → commit ✅
  ├─ Hard gates PASS → soft-smoke FAIL → re-prompt same model (1 retry)
  ├─ Hard gate FAIL on 1 gate → LogCraft analysis → re-prompt with gate-specific fix instruction
  ├─ Hard gate FAIL on 2+ gates → kill → escalate to stronger model
  └─ 3rd model also FAIL → cycle abort with structured post-mortem
```

**Key difference from original**: Hard gates are **pre-commit barriers**. A builder CANNOT commit code that fails any hard gate. This eliminates the "agent committed broken code" pitfall (#14 from Skill — "exit code 0 ≠ committed").

### 3.1 Gate hierarchies by failure severity

| Tier | Gates | On FAIL | Recoverable? |
|------|-------|---------|--------------|
| Tier 0 (pre-agent) | check-balance, check-auth, check-env | Kill cycle immediately | No — user action required |
| Tier 1 (static) | check-imports, lint, type-check | Reject commit, re-prompt with error log | Yes — same model can fix |
| Tier 2 (runtime) | check-smoke, check-diff-scope, check-data-integrity | Reject commit, escalate model | Maybe — 1 retry, then escalate |
| Tier 3 (post-cycle) | LogCraft analysis | Log for future cycles | N/A — informational only |

---

## 4. Partial Failure During Race

### 4.1 Problem

In a 3-way build race:
- Agent A: all gates PASS, commits to branch `agent/dsv4-flash/m4-bot`
- Agent B: gate `check-smoke` FAIL, port conflict, stuck for 4 minutes
- Agent C: gate `check-imports` FAIL, missing dependency

**Question**: Does the orchestrator wait for B and C? Kill B? Let C retry?

### 4.2 Protocol

```
RaceState = {
    "healthy": [],   // agents that passed all gates, committed
    "stuck": [],     // agents in repeating error loop > 3 min
    "failed": [],    // agents killed (gate failure, timeout)
    "running": []    // agents still working
}

Every 3 minutes:
  poll all agents:
    - "healthy" agents: leave alone (they commit independently)
    - "stuck" agents: kill immediately, do NOT replace (race window closing)
    - "failed" agents: log failure reason, do NOT replace

Race ends when:
  - (healthy ≥ 1 AND running == 0 AND stuck == 0) 
    OR
  - (wall-clock > 20 min) → collect whatever we have, skip validator for missing agents
    OR
  - (healthy ≥ 2) → terminate race early, validate top 2
```

**Design rationale**: In a race, you need at least 1 winner. Waiting for all 3 when 1 has already succeeded is wasteful. The race MVP is "at least one valid implementation" — not "all 3 must finish."

### 4.3 Gate evasion prevention

**Risk**: A builder agent could skip the gate entirely (not run `npm run typecheck`, not check imports). The orchestrator can't see inside the agent's workdir during execution.

**Mitigation**: Gates are run by the **orchestrator**, NOT by the agent:

```
Agent flow:
  1. Agent writes code to workdir
  2. Agent runs its own smoke test (soft)
  3. Agent commits
  4. Agent signals "done"

Orchestrator flow (after agent "done"):
  1. Checkout agent's branch
  2. Run Tier 1 gates (check-imports, lint, type-check) — fast, ~5s
  3. Run Tier 2 gates (check-smoke, check-diff-scope) — slower, ~15s
  4. If ALL pass → mark agent "healthy"
  5. If any FAIL → mark agent "failed", log failure
```

**This is the single most important architectural decision in LoopCraft**: gates are orchestrator-side. Agent-side self-checks are advisory only. The orchestrator holds the keys to the merge button.

---

## 5. Gate Ordering & Parallelism

### 5.1 Dependency graph

```
check-auth ──┬── check-balance ──────────────────────────► (Build starts)
             │
             └── check-env (venv, deps, config)

After build:
  check-imports ──┬── lint ──┬── type-check ──► (Tier 1 complete)
                  │          │
                  └──────────┘  (PARALLEL — they touch different subsystems)

  check-diff-scope ── check-data-integrity ──► (Tier 2, sequential because 
                                                data-integrity reads diff-scope result)

  check-smoke (independent, can run parallel to Tier 1 + Tier 2)
```

### 5.2 Parallel execution plan

```bash
# === PRE-FLIGHT (sequential, fast) ===
check-auth        # 0.5s
check-balance     # 1.0s
check-env         # 2.0s

# === POST-BUILD (parallelize Tier 1) ===
# Run these in 3 concurrent processes:
check-imports &   # PID 1
lint &            # PID 2
type-check &      # PID 3
wait              # collect all exit codes
# If any non-zero → Tier 1 FAIL, mark agent

# === TIER 2 (data integrity needs diff-scope context) ===
check-diff-scope && check-data-integrity
check-smoke       # can run in parallel with Tier 2

# Total gate time: ~10s (vs 25s sequential)
```

---

## 6. LogCraft Agent — Post-Cycle Failure Classifier

### 6.1 Purpose

After every cycle (PASS or FAIL), a lightweight agent analyzes all failure logs and classifies them into categories. This turns raw failures into actionable improvements for the next cycle.

### 6.2 Input

- All agent stderr logs from the cycle
- All gate failure outputs
- Previous cycle's LogCraft report (for trend detection)

### 6.3 Output

```json
{
  "cycle": "M4",
  "timestamp": "2026-06-17T14:22:00Z",
  "outcome": "PASS",
  "failures": [
    {
      "id": "m4-f1",
      "category": "env_conflict",
      "subcategory": "port_already_bound",
      "agent": "deepseek-v4-flash",
      "phase": "build",
      "message": "Port 8000 already in use — stale uvicorn from previous smoke test",
      "recurring": true,
      "previous_cycles": ["M3"],
      "recommendation": "Add pre-flight port-kill gate: lsof -ti:8000 | xargs kill -9"
    },
    {
      "id": "m4-f2", 
      "category": "code_generation",
      "subcategory": "import_missing",
      "agent": "deepseek-v4-flash",
      "phase": "build",
      "message": "ImportError: cannot import 'TypeAdapter' from 'pydantic'",
      "recurring": true,
      "previous_cycles": ["M3"],
      "recommendation": "Add check-imports gate with known footgun list"
    }
  ],
  "trends": [
    {
      "category": "env_conflict",
      "direction": "worsening",
      "count_this_cycle": 3,
      "count_last_cycle": 1,
      "action": "Gate required before M5"
    }
  ],
  "gates_efficacy": {
    "check-imports": {"ran": 3, "caught": 2, "false_positive": 0},
    "check-smoke": {"ran": 3, "caught": 1, "false_positive": 0}
  }
}
```

### 6.4 Failure classification taxonomy

| Category | Examples from M3 |
|----------|-----------------|
| `env_conflict` | Port 8000 conflict (#5), wrong terminal mode (#6) |
| `missing_precondition` | Billing not checked (#1), test URLs not verified (#2) |
| `code_generation` | Block.model_validate AttributeError (#4), translate_text missing system prompt (#7) |
| `config_drift` | env_file path wrong (#9) |
| `process_failure` | API key write failures (#8) |
| `latent_bug` | <html>/<body> unwrap missing (#3) |
| `no_verification` | No smoke test (#10) |

### 6.5 Auto-gating from LogCraft

When a failure category appears in **2+ consecutive cycles**, LogCraft promotes it:

```
failure_category "env_conflict" hit threshold (2 cycles) →
  AUTO-ADD gate "check-port-available" to next cycle's Tier 1 gate suite
  Log: "[LogCraft] Promoted 'env_conflict' failures to hard gate after 2 cycles"
```

This makes the gate suite **self-improving** — gates accumulate from real failures, not theoretical risks.

---

## 7. Cycle Lifecycle State Machine

```
               ┌──────────────┐
               │  IDLE        │
               └──────┬───────┘
                      │ milestone triggered
                      ▼
               ┌──────────────┐
               │  PRE-FLIGHT  │──── Tier 0 gates (auth, balance, env)
               └──────┬───────┘
                      │ all PASS
                      ▼
               ┌──────────────┐
               │  PLAN        │──── N architects in parallel
               └──────┬───────┘
                      │ plan validator picks winner
                      ▼
               ┌──────────────┐
               │  BUILD       │──── N builders in parallel (race)
               └──────┬───────┘
                      │ agents exit
                      ▼
               ┌──────────────┐
               │  GATE        │──── Tier 1 + Tier 2 gates per branch
               └──────┬───────┘
                      │ at least 1 branch PASS
                      ▼
               ┌──────────────┐
               │  VALIDATE    │──── build validator (different model)
               └──────┬───────┘
                      │ PASS
                      ▼
               ┌──────────────┐
               │  MERGE       │──── squash merge winner → main
               └──────┬───────┘
                      │
                      ▼
               ┌──────────────┐
               │  LOGCRAFT    │──── post-cycle failure analysis
               └──────┬───────┘
                      │
                      ▼
               ┌──────────────┐
               │  REPORT      │──── dashboard + recommendations
               └──────────────┘
```

**Hard-stop conditions** (cycle aborts immediately):
- Tier 0 gate FAIL → cycle blocked, user notified
- All agents FAIL on Tier 1 gates → cycle fails, LogCraft runs immediately
- DeepSeek API key 401 mid-cycle → kill all, preserve work, report

---

## 8. Integration Checklist

For each existing milestone cycle to adopt LoopCraft:

| Component | M4 (Bot Integration) | M5 (Curtain UX) | M6 (Theme) | M7 (Deploy) |
|-----------|---------------------|-----------------|------------|-------------|
| Gate suite | Tier 0 + Tier 1 | Full suite | Tier 0 + Tier 1 | Full suite |
| LogCraft | Required | Required | Optional | Required |
| Budget cap | $3.00 (medium) | $15.00 (high) | $1.00 (low) | $3.00 (medium) |
| Economy/Race | 1 architect + 1 builder | Full race (3×3) | Single builder | 1 architect + 1 builder |

---

## 9. Risks This Methodology Introduces

| Risk | Impact | Mitigation |
|------|--------|------------|
| Gate false positives kill valid branch | Losing the best implementation because a gate is too strict | Gates have `severity: warning` mode for first run; promote to `error` after 1 cycle of calibration |
| LogCraft agent consumes significant tokens | $0.15-0.30 extra per cycle | LogCraft uses the cheapest model (dsv4-flash); only runs on cycles with >0 failures |
| Orchestrator-side gate running adds latency | ~10s per branch, ~30s total for 3-branch race | Acceptable: 30s vs 20min agent runtime. Gates can be parallelized (see §5.2) |
| Gate evasion via orchestrator bypass | Agent might not commit, leaving no branch to gate | Fallback: run gates on agent's workdir directly if no commit exists (same as current fallback pattern) |
| Budget exhaustion mid-build leaves no usable branch | Cycle must be re-run from scratch | Pre-build re-check prevents launching builders if budget is already too low |
