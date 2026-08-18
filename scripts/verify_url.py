#!/usr/bin/env python3
"""Verify job-posting URLs against the ATS's structured job-board API.

Ashby, Greenhouse, and Lever posting pages are client-side rendered: a deleted
posting still returns HTTP 200 with the same empty HTML shell as a live one,
so fetching the page cannot tell live from dead. Each ATS's public board API
lists exactly the postings that are currently live — that is ground truth.

Usage:
  verify_url.py <url> [<url> ...]

Prints one line per URL (same order as the arguments):
  LIVE <url> -- <current title on the board>
  DEAD <url>                  board fetched OK; this posting is not on it
  UNSUPPORTED <url>           not a recognizable Ashby/Greenhouse/Lever URL
  ERROR <url> -- <reason>     board API unreachable; could not decide

For UNSUPPORTED/ERROR, fall back to fetching the posting page directly.
Exit code 0 if every URL is LIVE, 1 otherwise.
"""

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 30

# url pattern -> (ats, org, posting id) extractors
PATTERNS = [
    # https://jobs.ashbyhq.com/{org}/{uuid}[/application]
    ("ashby", re.compile(r"^jobs\.ashbyhq\.com/([^/]+)/([0-9a-f-]{36})")),
    # https://boards.greenhouse.io/{org}/jobs/{id} or job-boards.greenhouse.io
    ("greenhouse", re.compile(r"^(?:job-)?boards\.greenhouse\.io/([^/]+)/jobs/(\d+)")),
    # https://jobs.lever.co/{org}/{uuid}
    ("lever", re.compile(r"^jobs\.lever\.co/([^/]+)/([0-9a-f-]{36})")),
]

BOARD_APIS = {
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{org}",
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{org}/jobs",
    "lever": "https://api.lever.co/v0/postings/{org}?mode=json",
}


def parse(url: str):
    """Return (ats, org, posting_id) or None if the URL isn't a known ATS."""
    stripped = re.sub(r"^https?://", "", url.strip()).removeprefix("www.")
    for ats, pattern in PATTERNS:
        m = pattern.match(stripped)
        if m:
            return ats, m.group(1), m.group(2)
    return None


def fetch_board(ats: str, org: str) -> dict:
    """Fetch a board's live postings. Returns {posting_id: title}."""
    api_url = BOARD_APIS[ats].format(org=urllib.parse.quote(org))
    req = urllib.request.Request(api_url, headers={"User-Agent": "jobs-pipeline"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.load(resp)
    if ats == "ashby":
        return {j["id"]: j["title"].strip() for j in data.get("jobs", [])}
    if ats == "greenhouse":
        return {str(j["id"]): j["title"].strip() for j in data.get("jobs", [])}
    return {j["id"]: j["text"].strip() for j in data}  # lever: top-level list


def main() -> None:
    urls = sys.argv[1:]
    if not urls:
        sys.exit(__doc__)

    boards = {}  # (ats, org) -> {id: title} | Exception
    all_live = True
    for url in urls:
        parsed = parse(url)
        if not parsed:
            print(f"UNSUPPORTED {url}")
            all_live = False
            continue
        ats, org, posting_id = parsed
        key = (ats, org)
        if key not in boards:
            try:
                boards[key] = fetch_board(ats, org)
            except (urllib.error.URLError, json.JSONDecodeError, KeyError, TimeoutError) as e:
                boards[key] = e
        board = boards[key]
        if isinstance(board, Exception):
            print(f"ERROR {url} -- {board}")
            all_live = False
        elif posting_id in board:
            print(f"LIVE {url} -- {board[posting_id]}")
        else:
            print(f"DEAD {url}")
            all_live = False

    sys.exit(0 if all_live else 1)


if __name__ == "__main__":
    main()
