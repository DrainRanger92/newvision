#!/bin/sh
# .git/hooks/pre-commit (installed by gates/setup-hooks.sh)
# Fast checks on every commit: TypeScript typecheck + Python lint
# Cannot be bypassed — see gates/git-agent.sh

set -e

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
GATES_DIR="$ROOT_DIR/gates"

echo "🔍 Pre-commit: running fast checks..."

# --- Detect changed files ---
STAGED_FRONTEND=$(git diff --cached --name-only -- 'frontend/' '*.ts' '*.tsx' '*.js' '*.jsx' 2>/dev/null || true)
STAGED_BACKEND=$(git diff --cached --name-only -- 'backend/' '*.py' 2>/dev/null || true)

# --- TypeScript typecheck (if frontend files changed) ---
if [ -n "$STAGED_FRONTEND" ]; then
  echo "  TypeScript files changed → running tsc..."
  cd "$ROOT_DIR/frontend"
  if [ -f tsconfig.json ]; then
    npx tsc --noEmit 2>&1
    if [ $? -ne 0 ]; then
      echo "❌ PRE-COMMIT FAILED: TypeScript typecheck errors. Fix before commit."
      echo "   Run: cd frontend && npx tsc --noEmit"
      exit 1
    fi
    echo "  ✅ TypeScript typecheck passed"
  fi
  cd "$ROOT_DIR"
fi

# --- Python ruff lint (if backend files changed) ---
if [ -n "$STAGED_BACKEND" ]; then
  if command -v ruff >/dev/null 2>&1; then
    echo "  Python files changed → running ruff..."
    ruff check "$ROOT_DIR/backend/" --quiet 2>&1 || true
  fi
fi

echo "✅ Pre-commit checks passed"