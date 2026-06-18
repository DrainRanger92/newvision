# NewVision

Telegram Mini App для чтения английских технических статей с inline-переводом.
Жест «шторка» — свайп вверх по абзацу reveals перевод.

## Что это

Кидаешь ссылку на статью (Real Python, MDN, блоги) боту → бот парсит статью и открывает её прямо в Telegram в Mini App → читаешь оригинал → непонятный абзац → свайп вверх → видишь перевод → отпускаешь → снова оригинал. Код не переводится.

Полное ТЗ — в [`TZ.md`](./TZ.md). Технические детали намеренно опущены — выбираются в процессе разработки.

## Workflow разработки

Проект строится **agentic loop**-ом: Plan → 3 Build-агента (race) → Validator → merge лучшего → следующий milestone.

Детали и конвенции для агентов — в [`AGENTS.md`](./AGENTS.md).

## Milestones

- [x] M1 — Skeleton (backend + bot + frontend запускаются)
- [x] M2 — Parser (URL → блоки)
- [x] M3 — Translation (lazy + cache)
- [x] M4 — Bot integration (URL → Mini App)
- [ ] M5 — Curtain UX (touch swipe)
- [ ] M6 — Telegram theme + polish
- [ ] M7 — Deploy (VPS + Vercel + HTTPS)

## Запуск

### Prerequisites

- Python 3.11+
- Node 18+ (npm)
- Docker + Docker Compose (optional)

### Local (без Docker)

```bash
# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env
# Настрой MINI_APP_URL=http://localhost:5173 в .env
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Frontend (в другом терминале)
cd frontend
npm install
npm run dev
```

Или одной командой:

```bash
# PowerShell
.\scripts\dev.ps1

# Bash
bash scripts/dev.sh
```

### Docker Compose

```bash
docker-compose up --build
```

### Проверка

- Backend health: http://localhost:8000/health
- API docs: http://localhost:8000/docs
- Frontend dev: http://localhost:5173

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MINI_APP_URL` | `http://localhost:5173` | Web App URL used by the bot for WebAppInfo buttons |
| `BOT_TOKEN` | — | Telegram bot token (from @BotFather) |
| `DEEPSEEK_API_KEY` | — | DeepSeek API key for translation |
