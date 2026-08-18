#!/usr/bin/env python3
"""Job tracking database. Dedupes jobs by normalized URL.

Usage:
  jobsdb.py add --company X --title Y --url Z [--jd "summary"] [--term "Summer 27"]   -> prints NEW or DUPLICATE
  jobsdb.py pending                                              -> JSON list of jobs not yet emailed
  jobsdb.py mark --id N --status emailed|synced|filtered
  jobsdb.py set-resume --id N --path P --kind baseline|custom [--fit "assessment"] [--score N]
  jobsdb.py list                                                 -> JSON list of all jobs
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

DB_PATH = Path(__file__).resolve().parent.parent / "jobs.db"


def normalize_url(url: str) -> str:
    p = urlparse(url.strip())
    host = p.netloc.lower().removeprefix("www.")
    path = p.path.rstrip("/")
    return f"{host}{path}"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            title TEXT NOT NULL,
            url_normalized TEXT NOT NULL UNIQUE,
            url TEXT NOT NULL,
            jd_summary TEXT,
            found_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'found'
        )"""
    )
    # Migrations for DBs created before the resume/term/score features
    for column in ("resume_path", "resume_kind", "resume_fit", "term", "resume_score",
                   "notion_page_id"):
        try:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {column} TEXT")
        except sqlite3.OperationalError:
            pass
    return conn


def cmd_add(args) -> None:
    conn = connect()
    cur = conn.execute(
        "INSERT OR IGNORE INTO jobs (company, title, url_normalized, url, jd_summary, term, found_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            args.company,
            args.title,
            normalize_url(args.url),
            args.url,
            args.jd,
            args.term,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    print("NEW" if cur.rowcount else "DUPLICATE")


def rows_to_json(rows) -> str:
    cols = ["id", "company", "title", "url", "jd_summary", "term", "found_at", "status",
            "resume_path", "resume_kind", "resume_fit", "resume_score", "notion_page_id"]
    return json.dumps([dict(zip(cols, r)) for r in rows], indent=2)


SELECT = ("SELECT id, company, title, url, jd_summary, term, found_at, status, "
          "resume_path, resume_kind, resume_fit, resume_score, notion_page_id FROM jobs")


def cmd_pending(args) -> None:
    conn = connect()
    print(rows_to_json(conn.execute(SELECT + " WHERE status = 'found' ORDER BY id").fetchall()))


def cmd_list(args) -> None:
    conn = connect()
    print(rows_to_json(conn.execute(SELECT + " ORDER BY id").fetchall()))


def cmd_set_resume(args) -> None:
    conn = connect()
    cur = conn.execute(
        "UPDATE jobs SET resume_path = ?, resume_kind = ?, resume_fit = ?, resume_score = ? WHERE id = ?",
        (args.path, args.kind, args.fit, args.score, args.id),
    )
    conn.commit()
    if cur.rowcount == 0:
        sys.exit(f"error: no job with id {args.id}")
    print("OK")


def cmd_mark(args) -> None:
    conn = connect()
    cur = conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (args.status, args.id))
    conn.commit()
    if cur.rowcount == 0:
        sys.exit(f"error: no job with id {args.id}")
    print("OK")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add")
    p_add.add_argument("--company", required=True)
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--url", required=True)
    p_add.add_argument("--jd", default="")
    p_add.add_argument("--term", default="", help='Internship term, e.g. "Summer 27"')
    p_add.set_defaults(func=cmd_add)

    sub.add_parser("pending").set_defaults(func=cmd_pending)
    sub.add_parser("list").set_defaults(func=cmd_list)

    p_resume = sub.add_parser("set-resume")
    p_resume.add_argument("--id", type=int, required=True)
    p_resume.add_argument("--path", required=True)
    p_resume.add_argument("--kind", required=True, choices=["baseline", "custom"])
    p_resume.add_argument("--fit", default=None, help="Fit assessment vs. the JD, included in the email")
    p_resume.add_argument("--score", type=int, default=None, choices=range(0, 11),
                          help="Rubric-based fit score 0-10, included in the email")
    p_resume.set_defaults(func=cmd_set_resume)

    p_mark = sub.add_parser("mark")
    p_mark.add_argument("--id", type=int, required=True)
    p_mark.add_argument("--status", required=True,
                        choices=["found", "emailed", "synced", "filtered"])
    p_mark.set_defaults(func=cmd_mark)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
