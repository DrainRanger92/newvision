# M7 — Plan: Cloud Build Pipeline for Cloud Run Deploy

**Issue:** [#47] Создать cloudbuild.yaml для сборки и деплоя на Cloud Run
**Status:** Plan (not implemented)
**Date:** 2026-06-29

## Context

GCP проект `newvision-telegram` создан, Artifact Registry настроен (`europe-west1-docker.pkg.dev/newvision-telegram/newvision/`),
но **Cloud Build не знает, что собирать**.

Текущее состояние:
- `backend/Dockerfile` — есть (python:3.11-slim, uvicorn, EXPOSE 8000)
- `backend/requirements.txt` — есть
- `scripts/gcp-setup.sh` — инфраструктура развёрнута
- `cloudbuild.yaml` — ❌ **нужно создать**
- `.dockerignore` — ❌ **нужно создать**

## Что делаем

Создаём два файла в корне репозитория:

### 1. `.dockerignore`

Исключаем из контекста Docker-сборки всё лишнее, чтобы образ не раздувало:

```
.git/
.gitignore
.github/
__pycache__/
*.pyc
*.pyo
.pytest_cache/
*.egg-info/
.venv/
venv/
env/
node_modules/
frontend/
docs/
gates/
scripts/
.vscode/
.idea/
*.md
.env
.env.*
.DS_Store
Thumbs.db
```

### 2. `cloudbuild.yaml`

Три шага:

| Шаг | Название | Команда |
|-----|----------|---------|
| 1 | `build` | `docker build -t $AR_IMAGE:$SHORT_SHA -t $AR_IMAGE:latest .` |
| 2 | `push` | `docker push $AR_IMAGE --all-tags` |
| 3 | `deploy` | `gcloud run deploy newvision-backend ...` |

**Переменные подстановки Cloud Build:**

| Переменная | Значение | Откуда |
|------------|----------|--------|
| `$PROJECT_ID` | `newvision-telegram` | авто (gcloud config) |
| `$SHORT_SHA` | первые 7 символов хеша коммита | авто |
| `$LOCATION` | `europe-west1` | `--region` при запуске |
| `$AR_IMAGE` | `$LOCATION-docker.pkg.dev/$PROJECT_ID/newvision/backend` | вычисляется |

**Параметры Cloud Run:**

```
gcloud run deploy newvision-backend \
  --image=$LOCATION-docker.pkg.dev/$PROJECT_ID/newvision/backend:$SHORT_SHA \
  --region=$LOCATION \
  --platform=managed \
  --port=8000 \
  --timeout=300s \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=3 \
  --concurrency=80 \
  --set-env-vars=BOT_ENABLED=false \
  --allow-unauthenticated \
  --quiet
```

### Secrets

`DEEPSEEK_API_KEY` и `BOT_TOKEN` — через `--set-secrets` из Secret Manager.
Cloud Build SA уже имеет `roles/secretmanager.secretAccessor` (настроено в `gcp-setup.sh`).

Пока `BOT_ENABLED=false` — деплоим только API (без бота).

## Локальный запуск

```bash
gcloud builds submit --config=cloudbuild.yaml --region=europe-west1 .
```

Флаг `--region` обязателен (Cloud Build regional — используется регион Artifact Registry).

## Почему нет GitHub триггера

На этом этапе `cloudbuild.yaml` создаётся для **ручного запуска** из консоли.
GitHub → Cloud Build trigger будет настроен отдельно (см. issue #39 T12).

## CI не ломается

`cloudbuild.yaml` и `.dockerignore` — не `.py` и не `.ts/.tsx` — GitHub Actions
`validate-python` / `validate-frontend` не триггерятся на эти файлы.

## Acceptance Criteria

- [ ] `cloudbuild.yaml` в корне репозитория
- [ ] `.dockerignore` в корне репозитория
- [ ] `gcloud builds submit --config=cloudbuild.yaml --region=europe-west1 .` проходит успешно
- [ ] В Artifact Registry появляется образ
- [ ] Cloud Run сервис `newvision-backend` отвечает 200 на `/health`
- [ ] CI (validate-python, validate-frontend) не ломается от новых файлов
