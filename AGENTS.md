# AGENTS.md — Curtain Reader

Telegram Mini App для чтения английских технических статей с inline-переводом.
Жест «шторка» — свайп вверх по абзацу reveals перевод.

## Repository

- **Project root**: this directory (`~/Documents/curtain-reader/`)
- **ТЗ (source of truth)**: `TZ.md` — лишено техники, только цели/UX/перфоманс
- **Obsidian index**: `~/Documents/Obsidian Vault/pet/curtain-reader/_index.md`
- **Workflow**: agentic loop — plan → build (3 модели race) → validator → repeat

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
| LLM provider | opencode-go/* (mimo-v2.5-pro, glm-5.1, kimi-k2.6) |

## Available Models (DeepSeek API — primary; Anthropic/OpenCode — escalation)

| Роль цикла | Primary | Escalation | Зачем |
|---|---|---|---|
| **Architect** | `deepseek/deepseek-v4-pro` | `anthropic/claude-sonnet-4-5` | План, декомпозиция, риски |
| **Builder** | `deepseek/deepseek-v4-flash` | `deepseek/deepseek-v4-pro` | Имплементация, smoke test |
| **Validator** | `deepseek/deepseek-v4-pro` | `anthropic/claude-sonnet-4-5` | Ревью кода, data integrity |
| **Translate (runtime)** | `deepseek/deepseek-chat` | — | EN→RU в проде |

> 🔑 DeepSeek API key ($0.30–0.50 за билд). Эскалация на Anthropic только при FAIL. OpenCode Go — deprecated (баланс пуст).
> Эконом-режим: 1 architect → 1 builder → smoke. Full race (3×3) только для M5 Curtain UX.

## Project Structure (target)

```
curtain-reader/
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
└── docs/
    └── decisions/                    # ADR-лог
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

### Когда цикл останавливается:
- Validator = PASS по всем критериям milestone
- Milestone соответствует acceptance criteria из плана

## Milestones (порядок)

- [x] **M1** Skeleton: backend + bot + frontend запускаются, hello world ✅ (dbbb98d, QWEN winner)
- [x] **M2** Parser: URL → массив блоков, кэш статей ✅ (257ba4b, DSV4 winner)
- **M3** Translation: LLM EN→RU, lazy + cache
- **M4** Bot integration: URL → Mini App кнопка, end-to-end
- **M5** Curtain UX: touch swipe, snap, 60fps
- **M6** Telegram theme + polish: light/dark, inline-code preserved
- **M7** Deploy: VPS + Vercel + HTTPS, smoke на реальном устройстве

## Agent Rules (Mandatory)

1. **ТЗ — source of truth**. Если возникает противоречие — спрашивать, не выдумывать.
2. **Smoke-test обязателен**. Каждый build-агент должен запустить свой код и убедиться, что он работает, до коммита.
3. **Один осмысленный коммит**. Никаких fixup-ов, wip-ов, «fix typo» в истории.
4. **Имена = бизнес-смысл**. `ShouldEnableCurtain`, не `ModeToIsEnabled`. `parse_article`, не `do_stuff`.
5. **Не трогать лишнего**. Изменения только в скоупе задачи.
6. **Документация = код**. Если меняешь API — обнови README. Если принял решение — пиши ADR.
7. **Git ветка = агент**. `agent/<model>/<task>`. Не пушить в main напрямую.
8. **Логи = structured + semantic anchor**. `[ModuleName] message with {Params}`.
9. **Никаких DeepL/OpenRouter** — только OpenCode Go модели.
10. **Блокирующие вопросы — спрашивать сразу**, не молча выбирать запасной путь.

## Open Questions (собираем здесь)

- [ ] Telegram bot token — Mark даст перед M4
- [ ] Домен для Mini App — Mark даст перед M7
- [ ] VPS провайдер — Hetzner? (предложение в плане M7)

## Build & Test

- **M1**: Frontend `npm run build` ✅ (Vite + tsc), backend imports ✅ (FastAPI + aiogram)
- **M2**: Parser ✅ (DSV4 winner): POST /api/parse → 416 blocks, cache hit < 50ms, /health preserved
- Backend Python env needs clean venv setup (hermes-agent PYTHONPATH interferes)
