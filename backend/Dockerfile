# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts
COPY frontend/ ./
RUN npm run build
# Output: frontend/dist/

# Stage 2: Python runtime
FROM python:3.11-slim
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist/

EXPOSE 8000

ENV SERVE_STATIC=true
ENV STATIC_DIR=frontend/dist

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
