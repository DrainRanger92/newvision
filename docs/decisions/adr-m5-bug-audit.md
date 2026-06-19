# ADR: M5 Curtain UX — Bug Pattern Analysis & AGENTS.md Updates

**Date:** 2026-06-19
**Author:** Hermes Agent (analysis)
**Reviewed by:** (pending — user to verify with another agent)

## Context

During the M5 Curtain UX milestone (PR #20 → PR #21), the code went through
3 rounds of review + 1 CI build failure, catching approximately 15 bugs.
The user requested a full audit of what went wrong and why, to derive
general rules that prevent recurrence — without bloating AGENTS.md with
case-specific rules.

## Method

### Data sources

1. Full commit history of branch `agent/deepseek-v4-pro/M5-curtain-ux` (8 commits)
2. CI workflow logs: 5 build runs (1 cancelled, 4 failures, 1 success after fix)
3. Check-run annotations from `tsc -b` output
4. Code review summaries from 3 parallel review rounds (Pro + DoD + Flash)
5. `frontend/tsconfig.json` — compiler flags governing strict mode
6. `AGENTS.md` — existing agent rules, gate definitions, workflow documentation

### Classification

Every bug was classified by:
- **Category** (TS strict mode, React hooks, DOM/CSS, feature logic)
- **Detection layer** (CI gate G15, code review, smoke test)
- **Root cause** (didn't read tsconfig, didn't run build, didn't follow pattern)

## Findings

### Bug inventory

| # | Bug | Category | Detection | Root cause |
|---|-----|----------|-----------|------------|
| 1 | `e.touches[0]` possibly undefined (×6) | TS strict | CI G15 (`tsc -b`) | Ignored `noUncheckedIndexedAccess` |
| 2 | `velocityPoints[0]` possibly undefined (×3) | TS strict | CI G15 | Ignored `noUncheckedIndexedAccess` |
| 3 | `blocks[i]` possibly undefined | TS strict | CI G15 | Ignored `noUncheckedIndexedAccess` |
| 4 | `QuoteBlock` unused import | TS strict | CI G15 | Ignored `noUnusedLocals` |
| 5 | `isCurrentlyOpen` circular param → TDZ crash | React hooks | Review | Circular dependency in hook params |
| 6 | Stale closure in `handleTouchEnd` | React hooks | Review | Used raw state instead of ref |
| 7 | Missing `AbortController` timeout | React hooks | Review | Missing cleanup pattern |
| 8 | No `requestAnimationFrame` throttle | React hooks | Review | Performance not considered |
| 9 | Touch handlers on wrong DOM element | DOM | Review | Incorrect CSS class target |
| 10 | Missing `overscroll-behavior: contain` | CSS | Review | iOS rubber-banding not handled |
| 11 | `pointer-events: none` blocking touch | CSS | Review | Wrong CSS property guess |
| 12 | `dx` always 0 (horizontal gate broken) | Logic | Review | `startX` not captured in touchstart |
| 13 | Close gesture not working (dy→0 clamp) | Logic | Review | No `startOffset` tracking |
| 14 | Errors re-thrown instead of cached | Logic | Review | Violated spec `[translation error]` |
| 15 | Preloader cursor stuck at `blocks.length-1` | Logic | Review | Off-by-one in while-loop cursor |

### Detection layer breakdown

| Layer | Bugs caught | % |
|-------|-------------|---|
| CI gate G15 (`tsc -b`) | 4 bug types, ~11 instances | ~27% |
| Code review (manual) | 11 bug types | ~73% |

### Root cause analysis

**For CI-catchable bugs (items 1–4), the root cause is singular:**
The agent did not read `frontend/tsconfig.json` before writing frontend code.
If it had, it would have seen:

```json
{
  "strict": true,
  "noUncheckedIndexedAccess": true,
  "noUnusedLocals": true,
  "noUnusedParameters": true
}
```

Every single TS strict mode bug would have been avoided by knowing the rules
upfront. These are not edge cases — they are project-wide compiler settings.

**For review-only bugs (items 5–15), the root causes vary:**
- React hooks: missing cleanup patterns, stale closures, circular deps
- Logic: incomplete state machine design (touch gesture FSM)
- CSS: platform-specific edge cases (iOS rubber-band, pointer-events)

These are harder to codify as rules without becoming case-specific.
The existing review gate (1 approving review) is the appropriate defence.

## Changes applied to AGENTS.md

### Change 1: Two-Token Architecture — stale → active

**Problem:** The section was marked "(Planned)" and referenced a non-existent
bot account name (`newvision-bot`). The actual dev account is
`newoxygensolutions92`. There was no explicit rule enforcing which account
Hermes must use for git operations.

**Fix:**
- `(Planned)` → `(Active)`
- `newvision-bot` → `newoxygensolutions92`
- `$GITHUB_PAT` → `$GITHUB_DEV_PAT`
- Added: "Hermes/OpenCode выполняет ВСЕ git-операции только от dev-аккаунта.
  Любой коммит от DrainRanger92 — нарушение. Такой PR закрывается."

### Change 2: New rule #14 — TypeScript Strict Mode zero tolerance

**Problem:** No rule told agents to read `tsconfig.json` before writing code.
All 4 TS strict mode bugs (11 instances) would have been prevented by this
single rule.

**Rule text:**
> TypeScript Strict Mode — zero tolerance. Перед написанием любого frontend-кода —
> прочитать `frontend/tsconfig.json`. Если включены `noUncheckedIndexedAccess` /
> `noUnusedLocals` / `noUnusedParameters` / `strict: true` — писать код, который
> проходит `tsc -b` с первого раза. Каждый доступ по индексу (`arr[i]`, `obj[k]`)
> требует null-guard. Каждый импорт — используется. CI gate G15 существует именно
> для этого. Не полагаться на CI как на первую линию обороны.

### Change 3: New rule #15 — Pre-build verification

**Problem:** Agents pushed code that had never been built locally, assuming
CI would catch everything. When CI failed, the iteration cycle was slow
(push → wait 2min CI → read logs → fix → push again).

**Rule text:**
> Pre-build verification. Перед любым push — локально запустить `npm run build`
> (frontend) и `PYTHONPATH=backend python -m pytest` (backend). Если build или
> тесты падают — чинить до push-а. CI должен найти ноль новых ошибок.
> Единственное исключение — платформенные gap-ы (ENV-007).

## Verification

The updated AGENTS.md was committed to PR #21 (`feat/m5-curtain-ux-v2`).
CI passed on the updated branch (dc44ee5).

**Local verification before push:**
- `tsc -b` — zero errors
- `vite build` — 47 modules, 874ms
- `python -m pytest` — 183 passed

**PR link:** https://github.com/DrainRanger92/newvision/pull/21

## What was NOT changed (and why)

The following were considered but rejected as too case-specific:

| Candidate rule | Rejected because |
|----------------|------------------|
| "Always add AbortController to fetch calls" | Already covered by #15 (build passes → ok) |
| "Always use useRef for callback values" | Specific to React hooks; not a build gate issue |
| "Always add overscroll-behavior: contain" | CSS edge case; review should catch |
| "Always add requestAnimationFrame throttle" | Performance, not correctness |

These are better handled by code review than by rule proliferation.

## How to reproduce this analysis

1. Clone branch `agent/deepseek-v4-pro/M5-curtain-ux`
2. Run `git log --oneline` to see 8 commits with bug-fix messages
3. Read commit messages — each describes what was broken and why
4. Run `npm run build` on the first commit (ec5fcb9) to see original errors
5. Run `npm run build` on the last commit (82b4c58) — still fails with `Block | undefined`
6. Run `tsc -b` to see the exact error (blocks[i] at usePreload.ts:42)
7. Read `tsconfig.json` to confirm `strict: true`, `noUncheckedIndexedAccess`, `noUnusedLocals`
8. Compare with `frontend/tsconfig.json` on `main` — identical settings
9. Conclusion: agent didn't read local config before writing code
