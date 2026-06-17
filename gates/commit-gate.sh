#!/usr/bin/env bash
# Post-build commit gate. Run in agent workdir.
set -euo pipefail

echo "=== G12: Commit check ==="
COMMITS=$(git log --oneline -1 2>/dev/null || echo "")
if [ -z "$COMMITS" ]; then
    echo "G12 FAIL: no commits found. Attempting fallback commit..."
    git add -A
    git commit -m "$(whoami)-agent-build" || { echo "G12 FAIL: could not auto-commit"; exit 1; }
fi
echo "G12 PASS: commit exists"

echo "=== G13: Diff nonempty check ==="
BRANCH=$(git branch --show-current)
DIFF_LINES=$(git diff "main..$BRANCH" --stat 2>/dev/null | tail -1 || echo "")
if [ -z "$DIFF_LINES" ]; then
    echo "G13 FAIL: no changes on branch $BRANCH"
    exit 1
fi
echo "G13 PASS: $DIFF_LINES"
exit 0
