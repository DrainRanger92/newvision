# M5 — Curtain UX (Winning Plan)

> Plan Validator: deepseek-v4-pro  
> Architects: deepseek-v4-pro (Framer Motion path), deepseek-v4-pro (zero-deps path)  
> Winner: **zero-dependency approach** (pure CSS transforms + native touch events)  
> Date: 2026-06-19

## Plan Validator Decision

| Criterion | Pro (Framer Motion) | Flash (Zero-deps) | Winner |
|---|---|---|---|
| Bundle size | +31.5KB gzip | +5KB gzip | **Flash** |
| New dependencies | framer-motion ^11 | 0 | **Flash** |
| iOS Safari perf | Known drag issues | GPU-composited CSS | **Flash** |
| Gesture engine | Black-box `drag="y"` | Explicit state machine | **Flash** |
| Design documentation | Risk-focused | 11 decisions with defaults | **Flash** |
| Edge cases | 18 | 16 (+ more detail) | **Flash** |

**Reasoning:** Zero dependencies, smaller bundle, predictable CSS GPU-composited animations, explicit gesture state machine, and full design decision traceability. Framer Motion's spring physics are nice but not worth 31.5KB when the same can be achieved with `requestAnimationFrame` + CSS transitions.

---

## Library Decisions

| Library | Decision | Rationale |
|---|---|---|
| Touch gestures | **Native touch events** (touchstart/move/end) | Zero deps, full control, 60fps achievable |
| Animation | **CSS `transform: translateY()` + `transition`** | GPU-composited, hardware-accelerated |
| Snap physics | **`requestAnimationFrame` + spring math** | Same quality as framer-motion, 0KB |
| Preloading | **`IntersectionObserver`** | Native browser API, no polyfill needed (iOS 12.2+, Android 5+) |
| State management | **React Context** (`TranslationProvider`) | Shared cache across components, no external library |
| HTML rendering | **Keep `dangerouslySetInnerHTML` + DOMPurify** | Already in codebase, no change needed |

---

## Architecture

### Component Tree

```
Reader
 └─ TranslationProvider          ← context: cache, fetchTranslation, preloadQueue
     └─ ArticleRenderer
          ├─ CurtainBlock[]       ← translatable: heading, paragraph, list, quote
          │    ├─ useCurtain       ← gesture engine (touchstart/move/end, threshold, snap)
          │    ├─ useTranslation   ← per-block cache lookup + fetch
          │    └─ visual layers:   original (top) + translation (bottom)
          ├─ CodeBlock[]           ← no curtain, plain render
          └─ ImageBlock[]          ← no curtain, plain img
```

### Data Flow

```
User swipe UP on paragraph
  → touchstart: capture Y0, blockHeight
  → touchmove: delta = Y0 - Ycurrent, clamped to [0, blockHeight]
               apply CSS transform translateY(-delta)
               if delta > 30% threshold → hint "will snap open"
  → touchend:
      if delta > 30% blockHeight OR flick velocity > 0.3px/ms:
        → SNAP OPEN:
            1. CSS transition to translateY(-blockHeight) [250ms ease-out]
            2. call fetchTranslation(articleId, blockIndex)
            3. show translation text (fade in)
      else:
        → SNAP CLOSE: CSS transition to translateY(0) [250ms ease-out]

User swipe DOWN on open curtain
  → reverse: delta from open position
  → if delta > 30% blockHeight → SNAP CLOSE → translateY(0)

Preloading:
  IntersectionObserver on last visible block
  → debounce 300ms
  → fetchTranslateBatch for next 3 untranslated translatable blocks
  → populate TranslationContext cache
```

### Per-Block State Machine

```
IDLE ──(swipe up, δ>30%)──▶ LOADING ──(API response)──▶ LOADED
  ▲                             │                          │
  │                             ▼                          │
  │                          ERROR ◀──(API fail)           │
  │                             │                          │
  └──(swipe down, δ>30%)───────┴──────────────────────────┘
```

---

## Subtasks

### T1 — Extend `api.ts` with translate client functions
**File:** `frontend/src/services/api.ts` (modify)  
**Add:**
- `translateBlock(articleId, blockIndex)` → `TranslateResponse`
- `translateBlockBatch(articleId, blockIndices)` → `TranslateResponse[]`
- Types: `TranslateResponse { article_id, block_index, block_type, translated_text, cached, error }`

**Acceptance criteria:**
- [ ] Functions compile (tsc --noEmit)
- [ ] Types match backend response shape

### T2 — `useTranslation.ts` — shared cache context
**File:** `frontend/src/hooks/useTranslation.ts` (new)  
**Exports:**
- `TranslationProvider` — wraps children with cache context
- `useTranslation()` — returns `{ translate(articleId, blockIndex): Promise<string>, preload(articleId, indices): Promise<void> }`
- Internal: `Map<string, TranslateResponse>` keyed by `${articleId}:${blockIndex}`
- Cache: if found → return immediately; if error → return `"[translation error]"`
- Memoized via `useCallback`

**Acceptance criteria:**
- [ ] Multiple CurtainBlocks share the same cache
- [ ] Second call for same block returns cached value (no network)
- [ ] Error response cached as error state (not retried)

### T3 — `useCurtain.ts` — touch gesture engine
**File:** `frontend/src/hooks/useCurtain.ts` (new)  
**Design decisions (from Flash plan):**

| Parameter | Default | Notes |
|---|---|---|
| Snap duration | 250ms | CSS transition |
| Open threshold | 30% | Of block height |
| Flick velocity | 0.3px/ms | Window: last 150ms of gesture |
| Dead zone | 10px | Ignore tiny movements |
| Max open | 400px | Cap for very long blocks |
| Horizontal gate | 30° | If horizontal > vertical*tan(30°) → ignore (scroll passthrough) |

**State:** `{ state: 'idle'|'dragging'|'loading'|'loaded'|'error', offset: number, velocity: number }`  
**Input:** `(blockHeight: number, onOpen: () => Promise<void>, onClose: () => void)`  
**Output:** `{ curtainProps: { onTouchStart, onTouchMove, onTouchEnd, style: { transform, transition } }, state, offset }`

**Implementation:**
- touchstart: capture `startY`, `startTime`, blockHeight
- touchmove: calculate delta, apply `requestAnimationFrame`-throttled transform
- touchend: evaluate threshold + velocity → snap open/close
- `e.preventDefault()` on vertical swipes to block page scroll
- Horizontal scroll passthrough (angle gate < 30°)

**Acceptance criteria:**
- [ ] Swipe up > 30% → snaps open
- [ ] Swipe < 30% → snaps back
- [ ] Fast flick → opens regardless of distance
- [ ] Horizontal swipe → page scrolls normally

### T4 — `CurtainBlock.tsx` — visual component
**File:** `frontend/src/components/CurtainBlock.tsx` (new)  
**Props:** `{ articleId: string, blockIndex: number, block: Block, article: Article }`  
**States:**
- **idle:** original text visible, no translation layer
- **dragging:** original text offset by touch delta, translation layer hidden
- **loading:** snapped open, spinner in translation area
- **loaded:** original text hidden (above viewport), translation visible with fade-in
- **error:** "Translation unavailable" in italics

**Structure:**
```html
<div className="curtain-container" style={{ height: auto, position: relative, overflow: hidden }}>
  <div className="curtain-original" style={{ transform: translateY(-offset), transition }}>
    <!-- original block content (dangerouslySetInnerHTML) -->
  </div>
  <div className="curtain-translation" style={{ opacity, transition: 'opacity 200ms' }}>
    <!-- translation text or spinner/error -->
  </div>
</div>
```

**Translatable block types:**
- `heading` (h2-h6, NOT h1 — title is already rendered separately)
- `paragraph`
- `list` (ordered + unordered)
- `quote`

**Not translatable:**
- `code` — rendered directly (no CurtainBlock wrapper)
- `image` — rendered directly

**Acceptance criteria:**
- [ ] Original text slides up smoothly on swipe
- [ ] Translation fades in after API response
- [ ] Spinner visible during loading
- [ ] Error state rendered gracefully
- [ ] Code blocks rendered as-is (no curtain)

### T5 — CSS curtain styles
**File:** `frontend/src/styles/global.css` (append)  
**Add (~60 lines):**
```css
.curtain-container {
  position: relative;
  overflow: hidden;
  touch-action: pan-y; /* allow vertical gestures, block horizontal on this element */
  user-select: none;
  -webkit-user-select: none;
  contain: layout style paint; /* paint isolation for 60fps */
}

.curtain-original {
  will-change: transform;
  backface-visibility: hidden;
}

.curtain-translation {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  opacity: 0;
  padding: inherit;
  font-size: inherit;
  line-height: inherit;
  color: var(--tg-hint-color, #666);
}

.curtain-translation.visible {
  opacity: 1;
}

.curtain-spinner {
  width: 1rem;
  height: 1rem;
  border: 2px solid var(--tg-secondary-bg-color);
  border-top-color: var(--tg-link-color);
  border-radius: 50%;
  animation: curtain-spin 0.6s linear infinite;
  margin: 0.5rem auto;
}

@keyframes curtain-spin {
  to { transform: rotate(360deg); }
}
```

**Acceptance criteria:**
- [ ] GPU-composited (will-change + transform)
- [ ] No layout thrashing (contain: layout style paint)
- [ ] Translation area matches original typography

### T6 — `usePreload.ts` — IntersectionObserver preloader
**File:** `frontend/src/hooks/usePreload.ts` (new)  
**Design:** Uses `IntersectionObserver` on the last rendered CurtainBlock. When it enters viewport → debounce 300ms → `fetchTranslateBatch` for next 3 untranslated blocks.  
**Parameters:**
- `articleId: string`
- `blocks: Block[]` (to calculate translatable indices)
- `currentIndex: number`
- `translateBatch: (indices: number[]) => Promise<void>`

**Acceptance criteria:**
- [ ] Scroll near bottom → next 3 blocks preloaded
- [ ] Already translated blocks skipped
- [ ] Debounced (no rapid-fire API calls)
- [ ] Code blocks excluded from preload count

### T7 — Integrate into `ArticleRenderer`
**File:** `frontend/src/components/ArticleRenderer.tsx` (modify)  
**Changes:**
- Wrap translatable blocks in `CurtainBlock` instead of direct render
- Code blocks → direct `CodeBlock` render (no CurtainBlock)
- Image blocks → direct `ImageBlock` render
- Title (h1) → rendered as-is (no curtain)
- Pass `articleId` and `blockIndex` to `CurtainBlock`

### T8 — Wrap Reader in TranslationProvider
**File:** `frontend/src/pages/Reader.tsx` (modify)  
**Change:** Wrap `<ArticleRenderer>` in `<TranslationProvider>`

---

## File Blueprint

| File | Action | Purpose |
|---|---|---|
| `frontend/src/hooks/useCurtain.ts` | **NEW** | Touch gesture engine |
| `frontend/src/hooks/useTranslation.ts` | **NEW** | Shared translation cache (context) |
| `frontend/src/hooks/usePreload.ts` | **NEW** | IntersectionObserver preloader |
| `frontend/src/components/CurtainBlock.tsx` | **NEW** | Visual curtain component |
| `frontend/src/components/ArticleRenderer.tsx` | MODIFY | Route blocks to CurtainBlock |
| `frontend/src/pages/Reader.tsx` | MODIFY | Wrap in TranslationProvider |
| `frontend/src/services/api.ts` | MODIFY | Add translate functions |
| `frontend/src/styles/global.css` | APPEND | Curtain styles |
| `docs/grace/MODULE_MAP.md` | MODIFY | Add new module entries |

**Total:** 4 new files, 5 modified, 0 new npm dependencies, backend unchanged.

---

## Edge Cases

1. **Very short paragraph (1-2 words):** curtain still works — block height is small, threshold proportionally small
2. **Very long paragraph (>400px):** offset capped at 400px (CSS max-height approach for translation layer)
3. **Fast flick:** velocity check (last 150ms, >0.3px/ms) → opens regardless of distance
4. **Interrupted gesture:** touchend at 15% → animate back to 0; next touch restarts from 0
5. **Double-tap:** ignored (dead zone 10px)
6. **Horizontal swipe:** angle gate < 30° → `e.preventDefault()` NOT called → browser scrolls
7. **Scroll while curtain open:** curtain stays open, page scrolls through closed blocks
8. **iOS Safari rubber-banding:** `touch-action: pan-y` on container + `preventDefault` on vertical drag
9. **Android pull-to-refresh:** `overscroll-behavior: contain` on body
10. **API failure during open:** show "translation unavailable" text, state = error
11. **API slow:** spinner visible indefinitely until response or timeout (10s)
12. **Concurrent swipes on different blocks:** independent state per CurtainBlock instance
13. **Preload race condition:** if user swipes while preload is in-flight → cancel preload for that block, fetch directly
14. **Browser without IntersectionObserver:** graceful degradation — no preloading, just lazy on-swipe
15. **Resize (orientation change):** block heights recalculated on resize via ResizeObserver
16. **Inline code within paragraph:** DOMPurify preserves `<code>` tags — rendered inside original layer as-is

---

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| iOS Safari scroll interference with touch events | HIGH | `touch-action: pan-y` + `preventDefault` only on vertical drag |
| Low-end Android jank (no GPU layer) | MEDIUM | `will-change: transform` + `contain: layout style paint` |
| IntersectionObserver on Android 5-7 | LOW | Graceful degradation — no preload, lazy on-swipe |
| Block height changes during animation | LOW | ResizeObserver recalculates on layout change |
| State race: preload + manual swipe same block | MEDIUM | cancel preload promise on swipe start |
| Telegram WebView resets scroll position | MEDIUM | Save+restore scroll position on visibility change |

---

## Smoke Test Plan

### Prerequisites
- Backend running on `localhost:8001`
- Frontend dev server on `localhost:5173`
- A known-good article URL (e.g., Real Python post)

### Test Cases

| # | Test | Expected |
|---|---|---|
| 1 | Open article in mobile viewport (375×812) | Article renders with paragraphs |
| 2 | Swipe UP on paragraph to ~40% height | Paragraph snaps open, spinner appears |
| 3 | Wait for translation | Spinner disappears, RU text fades in |
| 4 | Swipe DOWN on open paragraph | Translation closes, original returns |
| 5 | Swipe UP only ~15% and release | Snaps back to closed |
| 6 | Fast flick UP on paragraph | Opens immediately (velocity gate) |
| 7 | Scroll past paragraphs | Page scrolls normally |
| 8 | Tap code block, swipe on it | No reaction (no curtain) |
| 9 | Swipe UP on heading (h2) | Heading animates open |
| 10 | Open paragraph → scroll down → come back | Translation still visible (cached) |
| 11 | Open in dark theme (tgColorScheme=dark) | Styles adapt to dark variables |
| 12 | Switch orientation mid-open | Curtain stays open, layout adjusts |
| 13 | Preload: open first paragraph → scroll to bottom | Translation for bottom blocks already loaded |
| 14 | Backend unreachable (stop uvicorn) | Paragraph opens, shows error text |
| 15 | VERY long paragraph (400px+) | Offset capped at 400px, translation scrollable |
| 16 | Rapid open/close 3x on same paragraph | No flicker, smooth transitions |
| 17 | Two fingers simultaneously on different paragraphs | Each reacts independently |

### Smoke Test Script

```bash
#!/bin/bash
# smoke-test-m5.sh
set -e

echo "=== M5 Curtain UX Smoke Test ==="

# G8: Backend start
cd backend
python -c "from backend.main import app; print('OK')" || { echo "FAIL: G5-imports"; exit 1; }
cd ..

# G6: Frontend build
cd frontend
npx tsc --noEmit || { echo "FAIL: G15-typecheck"; exit 1; }
npm run build || { echo "FAIL: G6-frontend-build"; exit 1; }
cd ..

echo "=== All gates PASSED ==="
echo ""
echo "Manual tests required (see test cases 1-17 above)"
```

---

## GRACE Module Map Updates

Add to `docs/grace/MODULE_MAP.md`:

```yaml
curtain-block:
  layer: Presentation
  dependencies: [use-curtain, use-translation]
  responsibility: "Visual curtain component with touch gesture and translation display"
  
use-curtain:
  layer: Presentation
  dependencies: []
  responsibility: "Touch gesture engine: swipe detection, threshold, snap physics"
  
use-translation:
  layer: Application
  dependencies: [api]
  responsibility: "Shared translation cache via React Context, fetch orchestration"
  
use-preload:
  layer: Application
  dependencies: [use-translation]
  responsibility: "IntersectionObserver-based preloading of upcoming block translations"
```

---

## Success Criteria (Milestone Complete)

- [ ] All 17 smoke tests pass
- [ ] G5-G11, G15-G16 gates green
- [ ] 60fps on iOS Safari (no frame drops on swipe)
- [ ] 60fps on Android Chrome (no frame drops on swipe)
- [ ] Code blocks correctly excluded from curtain
- [ ] Translation caching works (second swipe = instant)
- [ ] Preloading populates cache before user reaches bottom
- [ ] Zero new npm dependencies added
- [ ] Bundle size increase < 10KB gzipped
- [ ] No regressions in M1-M4 functionality

---

## Budget

| Phase | Model | Est. cost |
|---|---|---|
| Architect x2 | deepseek-v4-pro | $0.60 |
| Plan Validator | deepseek-v4-pro | $0.30 |
| Builder x3 | deepseek-v4-flash | $0.90 |
| Build Validator | deepseek-v4-pro | $0.30 |
| LogCraft | deepseek-v4-pro | $0.30 |
| **Total** | | **~$2.40** |

> Mode: Economy (1 architect winner, 1 builder winner). Actual: full race with 2 architects, 3 builders. Budget cap raised to $15.00.
