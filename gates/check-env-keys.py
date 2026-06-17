#!/usr/bin/env python3
"""Verify all required environment keys are present and non-empty."""
import os
import sys
from pathlib import Path

REQUIRED_KEYS = {
    "deepseek": ["DEEPSEEK_API_KEY"],
}
OPTIONAL_KEYS = ["BOT_TOKEN", "BOT_ENABLED", "CORS_ORIGINS", "DB_PATH"]


def check_provider(provider, keys):
    missing = []
    for k in keys:
        val = os.getenv(k, "")
        if not val:
            missing.append(k)
    return missing


def main():
    env_path = Path("backend/.env")
    if not env_path.exists():
        print(f"FAIL: {env_path} not found")
        sys.exit(1)

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

    all_ok = True
    for provider, keys in REQUIRED_KEYS.items():
        missing = check_provider(provider, keys)
        if missing:
            print(f"FAIL: {provider} missing keys: {', '.join(missing)}")
            all_ok = False

    if all_ok:
        print("PASS: all required keys present")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
