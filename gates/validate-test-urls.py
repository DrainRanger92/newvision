#!/usr/bin/env python3
"""Validate that smoke-test URLs are reachable before build."""
import sys

import httpx

TEST_URLS = [
    "https://realpython.com/python-f-strings/",
    "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Functions",
]


def main():
    all_ok = True
    for url in TEST_URLS:
        try:
            r = httpx.get(
                url,
                follow_redirects=True,
                timeout=15,
                headers={"User-Agent": "CurtainReader/1.0 SmokeTest"},
            )
            if r.status_code == 200:
                print(f"PASS: {url} -> {r.status_code}")
            elif r.status_code == 403:
                print(f"FAIL: {url} -> 403 Forbidden (bot blocked)")
                all_ok = False
            else:
                print(f"WARN: {url} -> {r.status_code}")
        except Exception as e:
            print(f"FAIL: {url} -> {e}")
            all_ok = False
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
