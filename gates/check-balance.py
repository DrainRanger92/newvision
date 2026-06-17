#!/usr/bin/env python3
"""Check provider balance by making a minimal API call."""
import os
import sys

import httpx

PROVIDERS = [
    {
        "name": "deepseek",
        "url": "https://api.deepseek.com/v1/chat/completions",
        "api_key_env": "DEEPSEEK_API_KEY",
        "model": "deepseek-chat",
        "min_balance": 0.10,
    },
]


def check_provider(p):
    api_key = os.getenv(p["api_key_env"], "")
    if not api_key:
        print(f"SKIP {p['name']}: no API key")
        return True
    try:
        response = httpx.post(
            p["url"],
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": p["model"],
                "messages": [{"role": "user", "content": "OK"}],
                "max_tokens": 1,
            },
            timeout=10,
        )
        if response.status_code == 402:
            print(f"FAIL: {p['name']} — insufficient balance (HTTP 402)")
            return False
        if response.status_code == 200:
            print(f"PASS: {p['name']} — balance available")
            return True
        print(f"WARN: {p['name']} — HTTP {response.status_code}: {response.text[:200]}")
        return True
    except Exception as e:
        print(f"WARN: {p['name']} — check failed: {e}")
        return True


def main():
    env_path = "backend/.env"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")

    all_ok = True
    for p in PROVIDERS:
        if not check_provider(p):
            all_ok = False
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
