#!/bin/sh
# gates/setup-hooks.sh — Install git hooks for NewVision project
# Run once after clone or when hooks change.
# Usage: bash gates/setup-hooks.sh

set -e

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HOOKS_DIR="$ROOT_DIR/.git/hooks"

echo "🔧 Installing git hooks..."

# Pre-commit hook
cp "$ROOT_DIR/gates/pre-commit.sh" "$HOOKS_DIR/pre-commit"
chmod +x "$HOOKS_DIR/pre-commit"
echo "  ✅ pre-commit hook installed"

# Pre-push hook
cp "$ROOT_DIR/gates/pre-push.sh" "$HOOKS_DIR/pre-push"
chmod +x "$HOOKS_DIR/pre-push"
echo "  ✅ pre-push hook installed"

# Git agent wrapper
chmod +x "$ROOT_DIR/gates/git-agent.sh"
echo "  ✅ git-agent.sh wrapper ready (gates/git-agent.sh)"

echo ""
echo "📋 Git hooks installed successfully."
echo "   - pre-commit:  TypeScript typecheck + ruff lint (on staged files)"
echo "   - pre-push:    Full build + pytest (on all files)"
echo ""
echo "⚠️  Agents MUST use gates/git-agent.sh instead of bare git:"
echo "   $ gates/git-agent.sh commit -m \"message\""
echo "   $ gates/git-agent.sh push origin branch"
echo ""
echo "   Bare 'git commit --no-verify' is BLOCKED by the wrapper."
echo "   See AGENTS.md § Agent Rules #16 for details."