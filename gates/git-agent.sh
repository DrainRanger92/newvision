#!/bin/sh
# gates/git-agent.sh — Git wrapper for AI agents
# Blocks --no-verify bypass. Always runs validation.
# Usage: gates/git-agent.sh commit -m "message"
#        gates/git-agent.sh push origin branch
#
# Agent rule: NEVER use bare `git commit` or `git push`.
# Always: gates/git-agent.sh commit ...

set -e

# Detect bypass attempt
for arg in "$@"; do
  case "$arg" in
    --no-verify|-n)
      echo "❌ BLOCKED: --no-verify is not allowed. Validation hooks are mandatory."
      exit 1
      ;;
  esac
done

# Execute real git
exec git "$@"