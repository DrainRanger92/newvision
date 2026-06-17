#!/usr/bin/env bash
# Curtain Reader — Local Dev Runner (bash)
# Starts backend (uvicorn) and frontend (vite) concurrently.

set -e

echo "[Dev] Starting backend on :8000..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

sleep 2

echo "[Dev] Starting frontend on :5173..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo "[Dev] Both services running."
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo "  Health:   http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
