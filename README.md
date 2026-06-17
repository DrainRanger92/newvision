# Curtain Reader

Telegram Mini App для чтения английских технических статей с inline-переводом.
Жест «шторка» — свайп вверх по абзацу reveals перевод.

## Что это

Кидаешь ссылку на статью (Real Python, MDN, блоги) боту → бот парсит статью и открывает её прямо в Telegram в Mini App → читаешь оригинал → непонятный абзац → свайп вверх → видишь перевод → отпускаешь → снова оригинал. Код не переводится.

Полное ТЗ — в [`TZ.md`](./TZ.md). Технические детали намеренно опущены — выбираются в процессе разработки.

## Workflow разработки

Проект строится **agentic loop**-ом: Plan → 3 Build-агента (race) → Validator → merge лучшего → следующий milestone.

Детали и конвенции для агентов — в [`AGENTS.md`](./AGENTS.md).

## Milestones

- [ ] M1 — Skeleton (backend + bot + frontend запускаются)
- [ ] M2 — Parser (URL → блоки)
- [ ] M3 — Translation (lazy + cache)
- [ ] M4 — Bot integration (URL → Mini App)
- [ ] M5 — Curtain UX (touch swipe)
- [ ] M6 — Telegram theme + polish
- [ ] M7 — Deploy (VPS + Vercel + HTTPS)

## Запуск

_(заполнится в M1 после выбора стека)_
