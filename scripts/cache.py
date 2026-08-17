#!/usr/bin/env python3
"""Decide which companies need a fresh web search vs. can use the cached careers page.

A company's cache (.companies/{slug}.md) is used only if it is younger than TTL_DAYS
AND survives a random refresh roll (REFRESH_PROB chance of a forced re-search).

Usage:
  cache.py check   -> prints SEARCH: and CACHED: lists
  cache.py slug "Company Name"  -> prints the cache filename slug for a company
"""

import random
import re
import sys
import time
from pathlib import Path

# Tuned for HOURLY pipeline runs: every company is re-searched at least once a
# day (TTL), plus ~one random early refresh per day (0.03/run x 24 runs).
TTL_DAYS = 1
REFRESH_PROB = 0.03

ROOT = Path(__file__).resolve().parent.parent
COMPANIES_FILE = ROOT / "companies.txt"
CACHE_DIR = ROOT / ".companies"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def cmd_check() -> None:
    companies = [
        line.strip()
        for line in COMPANIES_FILE.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    search, cached = [], []
    for company in companies:
        cache_file = CACHE_DIR / f"{slugify(company)}.md"
        fresh = (
            cache_file.exists()
            and (time.time() - cache_file.stat().st_mtime) < TTL_DAYS * 86400
        )
        if fresh and random.random() >= REFRESH_PROB:
            cached.append(company)
        else:
            search.append(company)

    print("SEARCH:")
    for c in search:
        print(f"  {c}")
    print("CACHED:")
    for c in cached:
        print(f"  {c}")


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "check":
        cmd_check()
    elif len(sys.argv) >= 3 and sys.argv[1] == "slug":
        print(slugify(sys.argv[2]))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
