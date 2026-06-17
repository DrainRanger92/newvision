#!/usr/bin/env bash
# Context guard: verify agent only modified allowed files.
# Usage: bash gates/context-guard.sh M4-bot-integration
set -euo pipefail

MILESTONE="${1:-}"
if [ -z "$MILESTONE" ]; then
    echo "Usage: bash gates/context-guard.sh <milestone-id>"
    exit 1
fi

CONFIG_FILE="docs/context-modules.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "WARN: $CONFIG_FILE not found, skipping context guard"
    exit 0
fi

echo "=== G17: Context guard ($MILESTONE) ==="

python -c "
import json, sys, subprocess

with open('$CONFIG_FILE') as f:
    modules = json.load(f)

if '$MILESTONE' not in modules:
    print(f'WARN: milestone $MILESTONE not in context-modules.json, skipping guard')
    sys.exit(0)

allowed_raw = modules['$MILESTONE'].get('read_write', [])
# Normalize: strip trailing slashes for directory prefixes
allowed = [a.rstrip('/') for a in allowed_raw]

changed = subprocess.check_output(
    ['git', 'diff', '--name-only', 'main..HEAD'],
    text=True
).strip().split('\n')
changed = [f.strip() for f in changed if f.strip()]

violations = []
for f in changed:
    ok = False
    for prefix in allowed:
        if f == prefix or f.startswith(prefix + '/'):
            ok = True
            break
    if not ok:
        violations.append(f)

if violations:
    print('G17 FAIL: modified files outside scope:')
    for v in violations:
        print(f'  {v}')
    print(f'Allowed prefixes: {allowed}')
    sys.exit(1)

print('G17 PASS: all changes within allowed scope')
print(f'Changed files: {changed}')
sys.exit(0)
" || exit 1
