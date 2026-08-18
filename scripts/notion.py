#!/usr/bin/env python3
"""Notion mirror for the job pipeline.

jobs.db stays the source of truth for dedupe; Notion is the presentation layer.

Usage:
  notion.py inspect                  -> list everything shared with the integration, with schemas
  notion.py init --parent <page_id>  -> create the "Recommended" database, save its id to config.json
  notion.py sync [--dry-run]         -> push new high-fit jobs to Notion; digest body goes to
                                        stdout and logs/last-digest.txt

Credentials: set NOTION_TOKEN in the environment, or in ~/.config/jobs-pipeline/env
(KEY=value lines). Create an integration at https://www.notion.so/my-integrations,
then share the target page with it (page "..." menu -> Connections).
"""

import argparse
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "jobs.db"
CONFIG_PATH = ROOT / "config.json"
DIGEST_PATH = ROOT / "logs" / "last-digest.txt"
ENV_FILE = Path.home() / ".config" / "jobs-pipeline" / "env"
API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
BLOCK_LIMIT = 1900  # Notion caps a rich_text chunk at 2000 chars
DEFAULT_MIN_SCORE = 0  # fit score a job must hit to reach Notion; 0 = everything syncs (score is informational only)


def get_token() -> str:
    token = os.environ.get("NOTION_TOKEN")
    if not token and ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith("NOTION_TOKEN="):
                token = line.split("=", 1)[1].strip()
    if not token:
        sys.exit(
            "error: NOTION_TOKEN not set (env var or ~/.config/jobs-pipeline/env). "
            "Create an integration at https://www.notion.so/my-integrations"
        )
    return token


def api(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"{API}/{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {get_token()}",
            "Notion-Version": VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = json.loads(e.read() or b"{}").get("message", str(e))
        raise RuntimeError(f"Notion API {e.code} on {method} {path}: {detail}") from None


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def notion_config() -> dict:
    cfg = load_config().get("notion", {})
    if not cfg.get("database_id"):
        sys.exit('error: no notion.database_id in config.json — run "notion.py init --parent <page_id>" first')
    return cfg


def title_of(obj: dict) -> str:
    """Plain-text title of a page or database object."""
    rich = obj.get("title")
    if rich is None:
        for prop in obj.get("properties", {}).values():
            if prop.get("type") == "title":
                rich = prop.get("title", [])
                break
    return "".join(t.get("plain_text", "") for t in (rich or [])) or "(untitled)"


def cmd_inspect(args) -> None:
    results = api("POST", "search", {})["results"]
    if not results:
        sys.exit(
            "error: nothing is shared with this integration.\n"
            "In Notion, open the page -> '...' menu (top right) -> Connections -> add your integration."
        )
    for obj in results:
        print(f"\n{obj['object'].upper()}  {title_of(obj)}\n  id:  {obj['id']}\n  url: {obj.get('url', '')}")
        if obj["object"] == "database":
            print("  properties:")
            for name, prop in obj["properties"].items():
                kind = prop["type"]
                extra = ""
                if kind in ("select", "multi_select", "status"):
                    opts = [o["name"] for o in prop[kind].get("options", [])]
                    extra = f" [{', '.join(opts)}]" if opts else ""
                print(f"    - {name!r}: {kind}{extra}")


SCHEMA = {
    "Company": {"title": {}},
    "Position": {"rich_text": {}},
    "Link": {"url": {}},
    "Fit Score": {"number": {"format": "number"}},
    "Term": {"rich_text": {}},
    "Resume": {"rich_text": {}},
    "Found": {"date": {}},
    "Triage": {"select": {"options": [
        {"name": "New", "color": "blue"},
        {"name": "To apply", "color": "yellow"},
        {"name": "Dismissed", "color": "gray"},
    ]}},
}


def cmd_init(args) -> None:
    db = api("POST", "databases", {
        "parent": {"type": "page_id", "page_id": args.parent},
        "title": [{"type": "text", "text": {"content": args.name}}],
        "properties": SCHEMA,
    })
    cfg = load_config()
    cfg.setdefault("notion", {})["database_id"] = db["id"]
    cfg["notion"].setdefault("min_score", DEFAULT_MIN_SCORE)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n")
    print(f"Created database {args.name!r}\n  id:  {db['id']}\n  url: {db['url']}")
    print(f"Saved notion.database_id to config.json (min_score={cfg['notion']['min_score']})")


def rich(text: str) -> list:
    return [{"type": "text", "text": {"content": text[:BLOCK_LIMIT]}}]


def body_blocks(job: dict) -> list:
    """Page body: the fit assessment and JD summary, chunked to Notion's limit."""
    blocks = []
    for heading, text in (("Resume fit", job["resume_fit"]), ("Job description", job["jd_summary"])):
        if not text:
            continue
        blocks.append({"object": "block", "type": "heading_3",
                       "heading_3": {"rich_text": rich(heading)}})
        for i in range(0, len(text), BLOCK_LIMIT):
            blocks.append({"object": "block", "type": "paragraph",
                           "paragraph": {"rich_text": rich(text[i:i + BLOCK_LIMIT])}})
    return blocks


def create_row(database_id: str, job: dict) -> str:
    props = {
        "Company": {"title": rich(job["company"])},
        "Position": {"rich_text": rich(job["title"])},
        "Link": {"url": job["url"]},
        "Found": {"date": {"start": job["found_at"][:10]}},
        "Triage": {"select": {"name": "New"}},
    }
    if job["resume_score"] is not None:
        props["Fit Score"] = {"number": int(job["resume_score"])}
    if job["term"]:
        props["Term"] = {"rich_text": rich(job["term"])}
    if job["resume_path"]:
        props["Resume"] = {"rich_text": rich(Path(job["resume_path"]).name)}
    page = api("POST", "pages", {
        "parent": {"database_id": database_id},
        "properties": props,
        "children": body_blocks(job),
    })
    return page["id"]


COLUMNS = ["id", "company", "title", "url", "jd_summary", "term", "found_at",
           "resume_path", "resume_kind", "resume_fit", "resume_score"]


def cmd_sync(args) -> None:
    cfg = notion_config()
    min_score = cfg.get("min_score", DEFAULT_MIN_SCORE)
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        f"SELECT {', '.join(COLUMNS)} FROM jobs "
        "WHERE status = 'found' AND notion_page_id IS NULL ORDER BY id"
    ).fetchall()
    jobs = [dict(zip(COLUMNS, r)) for r in rows]

    # A job with no score yet hasn't been through the resume tailor — leave it for the next run.
    scored = [j for j in jobs if j["resume_score"] is not None]
    unscored = [j for j in jobs if j["resume_score"] is None]
    strong = [j for j in scored if int(j["resume_score"]) >= min_score]
    weak = [j for j in scored if int(j["resume_score"]) < min_score]

    if args.dry_run:
        print(f"would add {len(strong)}, filter {len(weak)} (<{min_score}/10), "
              f"skip {len(unscored)} unscored")
        for j in strong:
            print(f"  + [{j['resume_score']}/10] {j['company']} - {j['title']}")
        return

    added, failed = [], []
    for job in strong:
        try:
            page_id = create_row(cfg["database_id"], job)
        except RuntimeError as e:
            failed.append((job, str(e)))
            continue
        conn.execute("UPDATE jobs SET notion_page_id = ?, status = 'synced' WHERE id = ?",
                     (page_id, job["id"]))
        conn.commit()
        added.append(job)

    for job in weak:
        conn.execute("UPDATE jobs SET status = 'filtered' WHERE id = ?", (job["id"],))
    conn.commit()

    body = digest(added, weak, unscored, failed, min_score)
    DIGEST_PATH.parent.mkdir(exist_ok=True)
    DIGEST_PATH.write_text(body + "\n")
    print(body)
    print(f"\n(digest written to {DIGEST_PATH.relative_to(ROOT)})")
    if failed:
        sys.exit(1)


def digest(added, weak, unscored, failed, min_score) -> str:
    """Plain-text digest body, piped into send_email.py --summary."""
    lines = [f"{len(added)} new job{'s' if len(added) != 1 else ''} added to Notion.", ""]
    for job in sorted(added, key=lambda j: -int(j["resume_score"])):
        lines.append(f"  [{job['resume_score']}/10] {job['company']} — {job['title']}")
        lines.append(f"            {job['term'] or 'term TBD'} · {job['url']}")
    if weak:
        lines += ["", f"Filtered out {len(weak)} below the {min_score}/10 fit threshold."]
    if unscored:
        lines += ["", f"{len(unscored)} job(s) still awaiting a resume — will sync next run."]
    if failed:
        lines += ["", f"ERRORS — {len(failed)} job(s) failed to sync:"]
        lines += [f"  {j['company']} — {j['title']}: {err}" for j, err in failed]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("inspect", help="list shared pages/databases and their schemas").set_defaults(func=cmd_inspect)

    p_init = sub.add_parser("init", help="create the Recommended database")
    p_init.add_argument("--parent", required=True, help="id of the page to create it under")
    p_init.add_argument("--name", default="Recommended")
    p_init.set_defaults(func=cmd_init)

    p_sync = sub.add_parser("sync", help="push new high-fit jobs to Notion")
    p_sync.add_argument("--dry-run", action="store_true", help="show what would sync, change nothing")
    p_sync.set_defaults(func=cmd_sync)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
