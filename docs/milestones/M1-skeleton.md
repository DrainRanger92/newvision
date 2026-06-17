# M1 — Skeleton

**Milestone**: Skeleton — backend + bot + frontend запускаются, hello world
**Status**: Planning
**Created**: 2026-06-17

---

## 1. Stack Decisions

| Layer | Choice | Justification |
|---|---|---|
| Runtime | Python 3.11+ | Modern typing, match statements, tz-aware datetime |
| API | FastAPI + Uvicorn | Async-first, OpenAPI auto-docs, fast startup |
| Bot | aiogram 3.x | Native async, FSM built-in, Telegram Bot API v7 |
| Frontend | React 18 + TypeScript + Vite | HMR <100ms, strict TS, ecosystem depth |
| Telegram SDK | @twa-dev/sdk | Typed wrapper, tree-shakeable, maintained |
| Package mgr (FE) | npm | Simplest, no extra tooling for skeleton |
| Package mgr (BE) | pip + requirements.txt | Sufficient for MVP, no poetry overhead |

---

## 2. Subtasks

### T1: Backend FastAPI skeleton
**Scope**: `backend/main.py`, `backend/requirements.txt`, `backend/.env.example`
**Acceptance**:
- `uvicorn backend.main:app` starts on `:8000`
- `GET /health` returns `{"status": "ok"}` with 200
- `GET /docs` serves Swagger UI
- CORS middleware allows `localhost:5173` (Vite dev)

### T2: Bot stub (aiogram 3)
**Scope**: `backend/bot.py`
**Acceptance**:
- `python -c "from backend.bot import router"` succeeds (clean import)
- Router registered in `main.py` but bot polling disabled by default (env flag `BOT_ENABLED=false`)
- `/start` handler stub exists, sends placeholder text
- No runtime error when `BOT_ENABLED=false`

### T3: Frontend Vite + React + TS skeleton
**Scope**: `frontend/` directory — `package.json`, `vite.config.ts`, `index.html`, `src/main.tsx`, `src/App.tsx`, `tsconfig.json`
**Acceptance**:
- `npm install && npm run dev` starts on `:5173`
- Browser shows "Curtain Reader" heading
- `npm run build` exits 0

### T4: Telegram WebApp integration stub
**Scope**: `frontend/src/main.tsx`, `frontend/src/lib/telegram.ts`
**Acceptance**:
- `@twa-dev/sdk` listed in `package.json` dependencies
- On mount: `WebApp.ready()` and `WebApp.expand()` called
- No crash when opened outside Telegram (graceful fallback)

### T5: Docker Compose dev runner
**Scope**: `docker-compose.yml`, `scripts/dev.sh` (or `dev.ps1`)
**Acceptance**:
- `docker-compose up` starts backend on `:8000` and frontend on `:5173`
- Both services healthy (healthcheck on backend)
- `scripts/dev.sh` runs both without Docker (for quick local dev)

### T6: README + run instructions
**Scope**: `README.md`
**Acceptance**:
- "Quick Start" section with both Docker and local commands
- Prerequisites listed (Python 3.11+, Node 18+)
- Links to `/health` and frontend dev URL

---

## 3. File Blueprint

```
curtain-reader/
├── docker-compose.yml          # Dev orchestration: backend + frontend
├── scripts/
│   ├── dev.sh                  # Local dev without Docker (bash)
│   └── dev.ps1                 # Local dev without Docker (PowerShell)
├── backend/
│   ├── main.py                 # FastAPI app factory, CORS, health endpoint, lifespan
│   ├── bot.py                  # aiogram 3 router, /start stub, conditional startup
│   ├── config.py               # Pydantic Settings (env vars: BOT_TOKEN, BOT_ENABLED, CORS_ORIGINS)
│   ├── requirements.txt        # fastapi, uvicorn[standard], aiogram>=3.0, pydantic-settings
│   └── .env.example            # Template: BOT_TOKEN=, BOT_ENABLED=false, CORS_ORIGINS=["http://localhost:5173"]
├── frontend/
│   ├── index.html              # Minimal HTML with #root
│   ├── package.json            # react, react-dom, @twa-dev/sdk, vite, typescript, @types/react
│   ├── vite.config.ts          # Proxy /api → localhost:8000, HMR config
│   ├── tsconfig.json           # Strict TS, React JSX
│   ├── tsconfig.node.json      # Vite config TS context
│   └── src/
│       ├── main.tsx            # Entry: ReactDOM.createRoot, WebApp init
│       ├── App.tsx             # Root component: "Curtain Reader" heading
│       ├── lib/
│       │   └── telegram.ts     # WebApp.ready()/expand() with try-catch
│       └── styles/
│           └── global.css      # Reset + base typography
└── docs/
    └── milestones/
        └── M1-skeleton.md      # This file
```

---

## 4. Smoke Test Procedure

Run these commands in order. All must pass.

```bash
# --- Backend ---
cd backend
pip install -r requirements.txt
python -c "from backend.bot import router; print('bot import OK')"
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
sleep 2
curl -sf http://localhost:8000/health | grep '"ok"' && echo "PASS: health" || echo "FAIL: health"
curl -sf http://localhost:8000/docs | grep 'swagger' && echo "PASS: docs" || echo "FAIL: docs"
kill %1

# --- Frontend ---
cd frontend
npm install
npm run build && echo "PASS: build" || echo "FAIL: build"
npm run dev &
sleep 3
curl -sf http://localhost:5173 | grep 'Curtain Reader' && echo "PASS: frontend" || echo "FAIL: frontend"
kill %1

# --- Docker (optional) ---
docker-compose up -d
sleep 5
curl -sf http://localhost:8000/health && echo "PASS: docker backend" || echo "FAIL: docker backend"
docker-compose down
```

**Expected**: All PASS, zero errors in stderr.

---

## 5. Risks

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| 1 | aiogram 3 polling blocks FastAPI event loop | Backend hangs on startup | Use `BOT_ENABLED` flag; start bot in separate asyncio task only when enabled; lifespan hook |
| 2 | @twa-dev/sdk crashes outside Telegram context | Frontend white screen | Wrap `WebApp.ready()` in try-catch; check `WebApp.isExpanded` before calling |
| 3 | Windows path issues in docker-compose volume mounts | Dev environment broken on Windows | Use named volumes or WSL2 note in README; provide `scripts/dev.ps1` as Docker-free alternative |

---

## 6. Open Questions

None blocking. Proceed with defaults:
- `BOT_ENABLED=false` for M1 (no token needed until M4)
- CORS allows `localhost:5173` only in dev
- No auth, no DB yet (M2+)
