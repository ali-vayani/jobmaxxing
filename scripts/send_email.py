#!/usr/bin/env python3
"""Send a job-alert email via Gmail SMTP for a job in jobs.db.

Usage:
  send_email.py --job-id N [--attach path/to/resume.pdf]

Credentials: set GMAIL_APP_PASSWORD in the environment (a Google App Password,
not your account password — requires 2FA; create one at
https://myaccount.google.com/apppasswords). If the env var is unset, this script
also tries ~/.config/jobs-pipeline/env (KEY=value lines).
"""

import argparse
import json
import os
import smtplib
import sqlite3
import sys
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "jobs.db"
TEMPLATE_PATH = ROOT / "email" / "TEMPLATE.md"
CONFIG_PATH = ROOT / "config.json"
ENV_FILE = Path.home() / ".config" / "jobs-pipeline" / "env"

EMAIL_ADDRESS = json.loads(CONFIG_PATH.read_text()).get("email", "")
if not EMAIL_ADDRESS:
    sys.exit('error: no "email" set in config.json')


def get_app_password() -> str:
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not password and ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith("GMAIL_APP_PASSWORD="):
                password = line.split("=", 1)[1].strip()
    if not password:
        sys.exit(
            "error: GMAIL_APP_PASSWORD not set (env var or ~/.config/jobs-pipeline/env). "
            "Create a Google App Password at https://myaccount.google.com/apppasswords"
        )
    return password


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", type=int, required=True)
    parser.add_argument("--attach", help="Optional file to attach (e.g. tailored resume PDF)")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT company, title, url, jd_summary, resume_path, resume_kind, resume_fit "
        "FROM jobs WHERE id = ?", (args.job_id,)
    ).fetchone()
    if row is None:
        sys.exit(f"error: no job with id {args.job_id}")
    company, title, url, jd_summary, resume_path, resume_kind, resume_fit = row

    attach_path = args.attach or resume_path

    template = TEMPLATE_PATH.read_text()
    subject_line, _, body = template.partition("\n")
    fields = {
        "company": company,
        "title": title,
        "url": url,
        "jd_summary": jd_summary or "(no summary)",
    }
    subject = subject_line.removeprefix("Subject:").strip().format(**fields)

    body_text = body.strip().format(**fields)
    if attach_path:
        if resume_kind == "custom":
            body_text += (
                "\n\nAttached resume: CUSTOM-BUILT for this posting "
                f"({Path(attach_path).name}). REVIEW IT before submitting — check for "
                "orphaned lines, bullets over 2 lines, and page overflow."
            )
        else:
            body_text += f"\n\nAttached resume: {Path(attach_path).name} (baseline)."
        if resume_fit:
            body_text += f"\n\nResume fit vs. this JD:\n{resume_fit}"

    msg = EmailMessage()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_ADDRESS
    msg["Subject"] = subject
    msg.set_content(body_text)

    if attach_path:
        pdf = Path(attach_path)
        if not pdf.exists():
            sys.exit(f"error: resume attachment not found: {pdf}")
        msg.add_attachment(
            pdf.read_bytes(),
            maintype="application",
            subtype="pdf",
            filename=pdf.name,
        )

    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(EMAIL_ADDRESS, get_app_password())
        smtp.send_message(msg)
    print(f"SENT job {args.job_id}: {company} - {title}")


if __name__ == "__main__":
    main()
