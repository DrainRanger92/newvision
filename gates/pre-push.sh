#!/bin/sh
# .git/hooks/pre-push (installed by gates/setup-hooks.sh)
# Full validation on every push: build + tests
# Cannot be bypassed — see gates/git-agent.sh

set -e

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "🔍 Pre-push: running full validation..."

# --- Detect what branches are being pushed ---
REMOTE="$1"
URL="$2"
echo "  Pushing to: $REMOTE"

# --- Frontend build ---
if [ -d "$ROOT_DIR/frontend" ]; then
  echo "  Building frontend..."
  cd "$ROOT_DIR/frontend"

  # npm install if needed (cached by CI, fresh for agents)
  if [ ! -d node_modules ]; then
    echo "  Installing frontend dependencies..."
    npm ci --quiet 2>&1 || npm install --quiet 2>&1
  fi

  # TypeScript check
  echo "  tsc --noEmit..."
  npx tsc --noEmit 2>&1 || npx tsc -b 2>&1
  if [ $? -ne 0 ]; then
    echo "❌ PRE-PUSH FAILED: TypeScript typecheck errors."
    exit 1
  fi
  echo "  ✅ TypeScript OK"

  # Vite build
  echo "  npm run build..."
  npm run build 2>&1
  if [ $? -ne 0 ]; then
    echo "❌ PRE-PUSH FAILED: Frontend build failed."
    exit 1
  fi
  echo "  ✅ Frontend build OK"

  cd "$ROOT_DIR"
fi

# --- Python tests ---
if [ -d "$ROOT_DIR/backend/tests" ]; then
  echo "  Running Python tests..."
  cd "$ROOT_DIR"

  # Install deps if needed
  if [ ! -d backend/venv ] && [ ! -f backend/.venv/bin/activate ]; then
    echo "  (no venv found, using system python)"
  fi

  PYTHONPATH=backend python -m pytest backend/tests/ -v --tb=short 2>&1
  if [ $? -ne 0 ]; then
    echo "❌ PRE-PUSH FAILED: Python tests failed."
    echo "   Run: cd $ROOT_DIR && PYTHONPATH=backend python -m pytest backend/tests/ -v --tb=short"
    exit 1
  fi
  echo "  ✅ Python tests OK"
fi

echo "✅ All pre-push checks passed. Push permitted."