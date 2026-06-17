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

## Available Models (OpenCode Go — subscription)

| Роль цикла | Модель | Зачем |
|---|---|---|
| **Plan** | `opencode-go/qwen3.7-max` (gpt-5.1-codex-max НЕ в Go-пуле) | Архитектура, декомпозиция |
| **Build #1** | `opencode-go/glm-5.1` | Coding (Python/TS), сильный baseline |
| **Build #2** | `opencode-go/qwen3.6-plus` | Альтернативный coding подход |
| **Build #3** | `opencode-go/mimo-v2.5-pro` | Быстрый, легковесный runner-up |
| **Validator** | `opencode-go/deepseek-v4-pro` | Глубокий ревью, длинный контекст |
| **Translate (runtime)** | `opencode-go/mimo-v2.5-pro` | EN→RU в проде |

> ⚠️ Только `opencode-go/*` модели. Никаких `openrouter/*`, `anthropic/*` напрямую, DeepL, Google Translate.

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

1. **Plan-agent** (gpt-5.1-codex-max):
   - Получает: TZ.md + текущее состояние репо + список пройденных milestones
   - Отдаёт: декомпозиция milestone на 3-7 атомарных задач, выбор стека (если M1)
   - Пишет план в `docs/decisions/NNN-milestone.md`

2. **Build-агенты (3 параллельно, race)**:
   - Каждый получает одну и ту же задачу
   - Каждый коммитит в свою ветку: `agent/<model>/<task-id>`
   - Контекст: TZ.md + plan-документ + смежные файлы
   - Должен запускать свой код и проверять что он работает (smoke test)

3. **Validator-agent** (deepseek-v4-pro):
   - Получает: ТЗ + plan + дифф всех 3 веток
   - Отдаёт: PASS/FAIL с конкретными пунктами
   - Критерии:
     - Соответствие ТЗ (поведение, а не реализация)
     - Работает ли код (build + run + smoke)
     - Производительность (если применимо)
     - Чистота git истории

4. **Merge**:
   - Лучшая ветка (по validator) → squash merge в main
   - Остальные 2 ветки → закрываются без merge
   - Коммит-msg: бизнес-имя (`feat: bot accepts URL and returns Mini App`, не `wip`)

### Когда цикл останавливается:
- Validator = PASS по всем критериям milestone
- Milestone соответствует acceptance criteria из плана

## Milestones (порядок)

- **M1** Skeleton: backend + bot + frontend запускаются, hello world
- **M2** Parser: URL → массив блоков, кэш статей
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

## Build & Test (после того как агенты выберут стек)

(заполняется агентами в M1)
