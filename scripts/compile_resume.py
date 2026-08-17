#!/usr/bin/env python3
"""Compile a resume .tex to PDF and enforce the 1-page rule.

Usage:
  compile_resume.py <file.tex> [--out DIR]

Compiles with pdflatex into resume/build/, checks the log reports exactly 1 page,
and leaves the PDF in resume/build/ (or --out DIR). The default deliberately does
NOT write next to the .tex — the original baseline PDFs live there and must never
be overwritten. Exits non-zero (with the log tail) on compile errors or page
overflow. The visual pass (orphan lines, dead-zone bullets) is still on the
caller — this only catches hard failures.
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "resume" / "build"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("texfile")
    parser.add_argument("--out", help="Directory for the final PDF (default: resume/build/)")
    args = parser.parse_args()

    tex = Path(args.texfile).resolve()
    if not tex.exists():
        sys.exit(f"error: {tex} not found")
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
         f"-output-directory={BUILD_DIR}", str(tex)],
        capture_output=True, text=True, cwd=tex.parent,
    )
    log = result.stdout
    if result.returncode != 0:
        print(log[-2500:])
        sys.exit("error: pdflatex failed (log tail above)")

    # pdflatex hard-wraps log lines at 79 chars (possibly mid-phrase) — flatten first
    match = re.search(r"Output written on.*?\((\d+) pages?", log.replace("\n", ""))
    pages = int(match.group(1)) if match else 0
    if pages != 1:
        sys.exit(f"error: PDF is {pages} pages, must be exactly 1 — trim bullets or structure")

    built = BUILD_DIR / (tex.stem + ".pdf")
    out_dir = Path(args.out).resolve() if args.out else BUILD_DIR
    final = out_dir / built.name
    if final != built:
        shutil.copy(built, final)
    print(f"OK 1 page: {final}")


if __name__ == "__main__":
    main()
