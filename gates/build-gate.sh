#!/usr/bin/env bash
# Per-agent build gate. Run in agent workdir.
# Usage: PORT=8001 bash gates/build-gate.sh
set -euo pipefail

PORT="${PORT:-8000}"
FAILURES=0

echo "=== G5: Backend imports ==="
PYTHONPATH=. python -c "from backend.main import app; print('OK')" || { echo "G5 FAIL"; FAILURES=$((FAILURES+1)); }

echo "=== G7: Lint ==="
ruff check backend/ 2>/dev/null || { echo "G7 FAIL (ruff not installed or lint errors)"; }
# ruff check failures are non-fatal if ruff isn't installed
if command -v ruff &>/dev/null; then
    ruff check backend/ || { echo "G7 FAIL"; FAILURES=$((FAILURES+1)); }
fi

echo "=== G6: Frontend build ==="
(cd frontend && npm run build) || { echo "G6 FAIL"; FAILURES=$((FAILURES+1)); }

echo "=== G15: Frontend typecheck ==="
(cd frontend && npx tsc --noEmit) || { echo "G15 FAIL"; FAILURES=$((FAILURES+1)); }

echo "=== G16: Config path check ==="
python -c "from backend.config import settings; assert settings.db_path, 'db_path empty'; assert settings.deepseek_api_key, 'api_key empty'" || { echo "G16 FAIL"; FAILURES=$((FAILURES+1)); }

echo "=== G11: System prompt check ==="
grep -q "TRANSLATION_SYSTEM_PROMPT" backend/translator.py || { echo "G11 FAIL: missing system prompt"; FAILURES=$((FAILURES+1)); }

# Kill any existing uvicorn on this port
echo "=== Cleaning port $PORT ==="
python -c "
import os, signal
port = int(os.environ.get('PORT', 8000))
try:
    import subprocess, sys
    if sys.platform == 'win32':
        subprocess.run(['cmd', '/c', f'for /f \"tokens=5\" %a in (\'netstat -ano ^| findstr :{port}\') do taskkill /F /PID %a'], capture_output=True, shell=True)
    else:
        subprocess.run(['bash', '-c', f'lsof -ti:{port} | xargs kill -9'], capture_output=True)
except Exception:
    pass
" || true
sleep 1

echo "=== G8: Smoke start (port $PORT) ==="
uvicorn backend.main:app --port "$PORT" &
UV_PID=$!
sleep 3

HEALTH_RESPONSE=$(curl -s "http://localhost:$PORT/health" 2>/dev/null || echo "")
if echo "$HEALTH_RESPONSE" | grep -q '"status":"ok"'; then
    echo "G8 PASS: $HEALTH_RESPONSE"
else
    echo "G8 FAIL: health check returned: $HEALTH_RESPONSE"
    kill $UV_PID 2>/dev/null || true
    FAILURES=$((FAILURES+1))
fi

if [ $FAILURES -gt 0 ]; then
    kill $UV_PID 2>/dev/null || true
    echo "=== RESULT: $FAILURES gate(s) failed ==="
    exit 1
fi

echo "=== RESULT: all gates passed ==="
kill $UV_PID 2>/dev/null || true
exit 0
