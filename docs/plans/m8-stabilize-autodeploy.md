# План: Стабилизация авто-деплоя NewVision

created: 2026-07-04
milestone: M8 (Production Hardening)
issues: #69, #76 (частично), #84 (закрыто)
status: plan
branch: agent/flash/m8-fix-autodeploy

## Диагностика (аудит 2026-07-04)

### Что работает

| Компонент | Статус |
|---|---|
| Cloud Run сервис (health check) | ✅ HTTP 200 |
| Webhook зарегистрирован | ✅ URL корректный |
| Container port 8080 | ✅ (исправлен вручную через REST API) |
| WEBHOOK_SECRET в Cloud Run | ✅ (добавлен вручную) |
| Все обязательные env vars | ✅ |
| Dockerfile: EXPOSE 8080 + CMD --port 8080 | ✅ PR #87 |

### Что сломано

| # | Проблема | Влияние | Приоритет |
|---|---|---|---|
| 1 | `cloudbuild.yaml` line 26: `--port=8000` | Каждый деплой падает | 🔴 P0 |
| 2 | `cloudbuild.yaml` line 34: `--set-secrets` повреждён | Бот не запустится | 🔴 P0 |
| 3 | `cloudbuild.yaml`: нет `WEBHOOK_SECRET` | Webhook не зарегистрируется | 🔴 P0 |
| 4 | `validate-cloudbuild.py` не проверяет порты | Не поймал mismatch | 🟡 P1 |
| 5 | `webhook.py:shutdown` — `_bot` NameError | Краш при shutdown | 🟢 P2 |

## Исправления (4 файла)

| Файл | Изменение |
|---|---|
| `cloudbuild.yaml:26` | `--port=8000` → `--port=8080` |
| `cloudbuild.yaml:34` | `--set-secrets` восстановлен (3 секрета) |
| `backend/webhook.py` | shutdown: убран `_bot`, `dispatcher.shutdown()` без await |
| `.github/scripts/validate-cloudbuild.py` | Проверка консистентности портов |

## Критерии успеха

1. `cloudbuild.yaml`: `--port=8080`
2. `cloudbuild.yaml`: `--set-secrets` содержит DEEPSEEK_API_KEY, BOT_TOKEN, WEBHOOK_SECRET
3. `validate-cloudbuild.py`: проверяет порты
4. `webhook.py`: shutdown не падает
5. CI: все три workflow зелёные
