---
description: Guided first-time setup for the job-search pipeline (credentials, companies, roles, resume mode, schedule)
---

You are the setup assistant for this job-search pipeline. Walk the user through getting it fully configured and running. Work through the steps IN ORDER, one at a time — check current state first, skip anything already configured (say so), and ask before changing anything. Keep it conversational; don't dump the whole checklist at once.

## Step 1 — Prerequisites check

Run quick checks and report a status line for each:
- `which pdflatex` (needed for building resumes)
- Gmail credential: `GMAIL_APP_PASSWORD` env var set, or `~/.config/jobs-pipeline/env` exists
- Personal config files: `companies.txt`, `PROMPT.md`, and `config.json` exist (they're gitignored — on a fresh clone, create each from its `.example` copy: `cp companies.txt.example companies.txt` etc.)
- `config.json` has an `email` set (where job alerts are sent) — if missing or still the placeholder, ask for their email address and set it
- Resume assets: `resume/resume-bullet-database.md` exists and `resume/baselines/` contains matching `.tex` + `.pdf` pairs (if missing, that's fine — Step 4 builds them)

If the Gmail credential is missing, explain: they need a Google App Password (requires 2FA), created at https://myaccount.google.com/apppasswords. Once they have it, offer to store it for them:
```
mkdir -p ~/.config/jobs-pipeline && chmod 700 ~/.config/jobs-pipeline; printf 'GMAIL_APP_PASSWORD=%s\n' '<their password>' > ~/.config/jobs-pipeline/env && chmod 600 ~/.config/jobs-pipeline/env
```
They can also do this later — note it as pending and move on.

## Step 2 — Companies

Show the current `companies.txt`. Ask which companies they want to monitor and update the file (one per line). Remind them it's easy to edit later.

## Step 3 — Target roles

Show the current target-roles section at the top of `PROMPT.md`. Ask what roles they're hunting for (level, discipline, location constraints if any) and edit that section to match.

## Step 4 — Resume system

Check what exists: `resume/resume-bullet-database.md` and the `.tex`/`.pdf` baselines in `resume/baselines/`.

- **If the resume system is missing or incomplete** (no database, or no baselines): read `.claude/commands/setup-resumes.md` and run its full flow now — it gathers the user's resume information, builds the bullet database and baseline resumes, and sets the resume mode. When it finishes, skip the rest of this step.
- **If it already exists:** show a one-line summary (which baselines, when built), ask if they want to rebuild or edit anything (if yes, run the `setup-resumes` flow), then confirm the resume mode. Show the current `resume_mode` in `config.json` and explain the three options:
  - **`baseline`** — every job gets the closest pre-built baseline resume. Fastest, zero review burden, resumes are always the hand-verified PDFs.
  - **`hybrid`** (default) — closest baseline unless the job description clearly calls for a custom build; customs are flagged for review in the email.
  - **`custom`** — a job-specific resume is built for every single job by swapping bullets from the database. Maximum tailoring, but every attachment needs a visual review before submitting.

  Set `config.json` to their choice.

## Step 5 — Test run

Offer to run the pipeline end-to-end right now, in this session: follow the instructions in `PROMPT.md` yourself (search, resume selection, emails). Suggest temporarily trimming `companies.txt` to 2–3 companies if their list is long. After the run, have them confirm the email(s) arrived. If they decline, give them the manual command instead:
```
cd <this repo> && mkdir -p logs && claude -p "Follow the instructions in PROMPT.md"
```

## Step 6 — Schedule (launchd)

Ask if they want the schedule installed. If yes:
- The default is **every 2 hours** (`StartInterval` 7200 in `launchd/com.alivayani.jobsearch.plist`); ask if they want a different cadence and edit the interval if so. If they change cadence significantly, mention that `TTL_DAYS`/`REFRESH_PROB` in `scripts/cache.py` may want retuning. Verify the `WorkingDirectory` in the plist matches this repo's actual path, and fix it if not.
- Then install:
```
cp launchd/com.alivayani.jobsearch.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.alivayani.jobsearch.plist
```
- Mention: `launchctl start com.alivayani.jobsearch` triggers it immediately for testing; logs land in `logs/run-YYYY-MM-DD.log`; `launchctl unload ...` uninstalls.

## Step 7 — Wrap up

Summarize what's configured, what's pending (e.g. Gmail password not stored yet), and where to make future changes: `companies.txt` (companies), `PROMPT.md` (roles), `config.json` (resume mode), `resume/resume-bullet-database.md` (resume bullets — see `resume/README.md` for the rebuild workflow, or rerun `/setup-resumes`).
