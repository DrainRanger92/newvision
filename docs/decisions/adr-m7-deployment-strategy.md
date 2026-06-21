# ADR: M7 Deployment Strategy — NewVision on Google Cloud Run

**Date:** 2026-06-21
**Author:** Mark Panchenko / Hermes Agent
**Status:** Proposed

## Context

NewVision (Telegram Mini App для чтения английских статей с inline-переводом) достиг M6 (Telegram theme + polish).
Для использования на реальных устройствах через Telegram Mini App необходим production-деплой с HTTPS, webhook-режимом бота и CI/CD.

Текущая архитектура (dev):
- FastAPI + aiogram 3 (polling mode)
- SQLite (local file)
- React + Vite dev server (HMR)
- docker-compose для локального запуска

**Проблема:** polling требует постоянно работающего процесса (~$3/мес), нет HTTPS, нет CI/CD.

## Решения

### Решение 1: Единый Cloud Run сервис (FastAPI → API + статика + webhook)

**Выбрано.** Единый Docker-образ содержит backend (FastAPI) + pre-built frontend (React) + bot webhook.
Один Cloud Run сервис обрабатывает все запросы.

**Почему, а не:**

| Альтернатива | Отклонено потому что |
|-------------|---------------------|
| Cloud Run API + Cloud Storage CDN для фронтенда | Сложнее инфраструктура, два deployment target. На MVP не нужно — трафик будет <100 запросов/день |
| Cloud Run API + отдельный nginx на Compute Engine | Дороже ($5+/мес), нужно управлять VM |
| Firebase Hosting + Cloud Functions | Lock-in, нет контроля над средой выполнения Python |

**Последствия:**
- Один `Dockerfile` (multi-stage) вместо двух
- В production `SERVE_STATIC=true`, фронтенд раздаётся через `StaticFiles` mount
- Все роуты API (`/api/*`) и webhook (`/webhook/telegram`) монтируются до статики
- React HashRouter (`/#/`) не конфликтует с API роутами

### Решение 2: Bot webhook (не polling)

**Выбрано.** При старте Cloud Run сервис регистрирует webhook URL в Telegram Bot API.
При shutdown — удаляет webhook.

**Почему, а не:**

| Альтернатива | Отклонено потому что |
|-------------|---------------------|
| Polling (как сейчас) | Cloud Run scale-to-zero несовместим с polling — нужен постоянно работающий инстанс (~$3/мес) |
| Cloud Run min-instances=1 | Отменяет преимущество scale-to-zero, платим за idle |

**Последствия:**
- `BOT_MODE=webhook` в production, `BOT_MODE=polling` для локальной разработки
- `backend/webhook.py` — новый модуль для обработки Telegram updates через FastAPI
- Webhook URL регистрируется в lifespan через `bot.set_webhook()`
- Телеграм доставляет update → Cloud Run просыпается (холодный старт ~2-5 сек) → обрабатывает → засыпает
- Это приемлемо: пользователь одной ссылкой открывает статью, cold start незаметен за загрузкой

### Решение 3: SQLite на Cloud Storage FUSE (gen2 volume)

**Выбрано.** Cloud Run gen2 execution environment поддерживает монтирование GCS bucket как FUSE-тома.
SQLite БД хранится в bucket.

**Почему, а не:**

| Альтернатива | Отклонено потому что |
|-------------|---------------------|
| Cloud SQL (PostgreSQL) | $10+/мес, нужна миграция с SQLite, оверкилл для <100 запросов/день |
| Firestore | Другая модель данных, нужно переписывать слой доступа |
| SQLite в /tmp | Эфемерный диск — данные теряются при каждом деплое/холодном старте |

**Последствия:**
- `--add-volume=name=sqlite-data,type=cloud-storage,bucket=newvision-data`
- `--add-volume-mount=volume=sqlite-data,mount-path=/app/data`
- `DB_PATH=data/curtain_reader.db`
- Cloud Storage FUSE latency выше, чем локальный диск, но для MVP (один пользователь, чтение > запись) — приемлемо
- GCS bucket `newvision-data` в `europe-west1` (та же region, что и Cloud Run)
- **Риск:** при конкурентных запросах от нескольких инстансов — SQLite corruption. На MVP один инстанс (~0 запросов/день) — не проблема. Если понадобится масштабирование — миграция на Cloud SQL.

### Решение 4: GCP Secret Manager для секретов

**Выбрано.** `BOT_TOKEN` и `DEEPSEEK_API_KEY` хранятся в GCP Secret Manager, монтируются в Cloud Run как env vars.

**Почему, а не:**

| Альтернатива | Отклонено потому что |
|-------------|---------------------|
| GitHub Secrets + env в cloudbuild.yaml | Секреты видны в логах Cloud Build, нет rotation audit |
| .env в репозитории | Нарушение безопасности, секреты в git — красная линия |
| HashiCorp Vault | Оверкилл для одного сервиса |

**Последствия:**
- Два секрета: `bot-token`, `deepseek-api-key`
- Cloud Build SA получает `roles/secretmanager.secretAccessor`
- В `cloudbuild.yaml` используется `--set-secrets`
- Secrets создаются один раз через `gcloud secrets create` (скрипт `scripts/gcp-secrets.sh`)

### Решение 5: Cloud Build для CD, GitHub Actions для PR validation

**Выбрано.** Разделение ответственности:
- **PR validation** (typecheck, lint, test) — GitHub Actions (`pr-build-gate.yml`)
- **Deploy** (build → push → deploy) — Cloud Build при merge в `main`

**Почему, а не:**

| Альтернатива | Отклонено потому что |
|-------------|---------------------|
| Только GitHub Actions | Нужно настраивать GCP auth в Actions (WIF), больше зависимостей |
| Только Cloud Build | Cloud Build не умеет PR статус checks как GitHub Actions |

**Последствия:**
- Cloud Build SA нужны роли: `roles/run.admin`, `roles/iam.serviceAccountUser`, `roles/secretmanager.secretAccessor`
- GitHub Actions workflow не меняется (только PR validation)
- Опционально: T12 добавит Workload Identity Federation для автоматизации из GitHub

### Решение 6: Region europe-west1

**Выбрано.** Все GCP ресурсы в `europe-west1` (Belgium).

**Почему:**
- Ближайший GCP регион к пользователю (Чехия / Центральная Европа)
- Telegram Bot API не имеет привязки к региону
- Совместимость с София проектом (us-central1 — но NewVision не зависит от Софии)
- Artifact Registry, Cloud Run, GCS — все в одном регионе (минимальная задержка, бесплатный inter-service трафик)

### Решение 7: Artifact Registry (не Docker Hub / GHCR)

**Выбрано.** Docker-образы хранятся в Artifact Registry (`europe-west1-docker.pkg.dev/$PROJECT_ID/newvision/`).

**Почему:**
- Бесплатный intra-region трафик между Artifact Registry и Cloud Run
- Не нужно настраивать registry credentials (Cloud Build имеет доступ по умолчанию)
- Docker Hub имеет rate limit (200 pulls/6h для anonymous)

## Бюджет

| Ресурс | Free Tier | Наш расход | Цена/мес |
|--------|-----------|-----------|----------|
| Cloud Run | 2M requests, 360K GB-seconds, 180K vCPU-seconds | << лимитов | $0 |
| GCS (SQLite) | 5GB, 20K ops/month | ~50MB, << 20K ops | $0 |
| Secret Manager | 6 active secrets free | 2 secrets | $0 |
| Artifact Registry | 0.5GB storage | ~200MB/image | $0 |
| Cloud Build | 120 min/day free | << 120 min | $0 |
| **Total** | | | **~$0.60** (egress only if traffic >1GB/mo) |

## Security considerations

- **No secrets in git.** `.env.example` содержит заглушки, реальные значения — только в GCP Secret Manager
- **CORS.** В production разрешён только Telegram origin (`https://*.t.me`). localhost:5173 только для dev
- **Bot token.** Никогда не логируется, не экспозится в API ответах
- **Docker image.** Не содержит секретов — они монтируются runtime через Secret Manager
- **IAM.** Cloud Build SA имеет только необходимые роли (run.admin, iam.serviceAccountUser, secretmanager.secretAccessor)

## T1 Infrastructure Checklist

Выполняется один раз (gcloud CLI от Mark'а):

1. `gcloud projects create newvision-telegram --set-as-default`
2. `gcloud config set run/region europe-west1`
3. `gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com storage.googleapis.com`
4. `gcloud artifacts repositories create newvision --repository-format=docker --location=europe-west1`
5. `gsutil mb -l europe-west1 gs://newvision-data`
6. Grant Cloud Build SA: `run.admin`, `iam.serviceAccountUser`, `secretmanager.secretAccessor`

→ Автоматизировано в `scripts/gcp-setup.sh`

## Что дальше

| Порядок | Зависимость |
|---------|------------|
| T2: Secret Manager Setup | T1 выполнен + токены от Mark |
| T3: Bot Webhook Refactor | Независим от T1 |
| T4: Backend Serves Static | T3 (основной файл main.py) |
| T5: Multi-stage Dockerfile | T4 (статический mount) |
| T6: Cloud Build Config | T1+T2+T5 |
| T7: CORS & Config | T3+T4 |
| T8: Webhook Registration | T3 |
| T10: Smoke Test | T6+T8 |

## References

- Issue #27: M7 Epic
- Issue #28: T1 — GCP Infrastructure Setup
- AGENTS.md: gates, two-token arch, orchestration
- newvision-dev-workflow skill: development pipeline
