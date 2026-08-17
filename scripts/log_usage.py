#!/usr/bin/env python3
"""Record per-run Claude Code usage for the pipeline.

Pipe mode (default): reads `claude -p --output-format json` output from stdin,
appends one JSONL row to logs/usage.jsonl (timestamp, duration, turns, cost,
tokens), and prints the run's result text so the daily log stays readable.
Non-JSON input (e.g. an error message) is passed through untouched.

Report mode: `log_usage.py --report` prints the last runs and running totals.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USAGE_LOG = ROOT / "logs" / "usage.jsonl"


def record() -> None:
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        sys.stdout.write(raw)
        return

    usage = data.get("usage", {})
    entry = {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "duration_min": round(data.get("duration_ms", 0) / 60000, 1),
        "num_turns": data.get("num_turns"),
        "total_cost_usd": data.get("total_cost_usd"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cache_read_tokens": usage.get("cache_read_input_tokens"),
        "cache_creation_tokens": usage.get("cache_creation_input_tokens"),
    }
    USAGE_LOG.parent.mkdir(exist_ok=True)
    with USAGE_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")

    print(data.get("result", ""))


def report() -> None:
    if not USAGE_LOG.exists():
        print("no usage recorded yet")
        return
    rows = [json.loads(line) for line in USAGE_LOG.read_text().splitlines() if line.strip()]
    print(f"{'timestamp':25} {'min':>6} {'turns':>6} {'out-tok':>9} {'cost $':>8}")
    for r in rows[-20:]:
        cost = r.get("total_cost_usd")
        print(
            f"{r['ts']:25} {r.get('duration_min') or 0:>6} {r.get('num_turns') or 0:>6} "
            f"{r.get('output_tokens') or 0:>9} {f'{cost:.2f}' if cost is not None else '-':>8}"
        )
    total_cost = sum(r.get("total_cost_usd") or 0 for r in rows)
    total_out = sum(r.get("output_tokens") or 0 for r in rows)
    print(f"\n{len(rows)} runs total · {total_out:,} output tokens · ~${total_cost:.2f} API-equivalent")


if __name__ == "__main__":
    report() if "--report" in sys.argv else record()
