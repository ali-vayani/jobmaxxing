# Job Search Pipeline

Automated pipeline: search company career pages for matching jobs → dedupe against `jobs.db` → pick/build a tailored resume → email each new job (resume attached) to the configured address. Runs headless via `claude -p` on an hourly launchd schedule.

## How it works

- `PROMPT.md` — the orchestrator prompt the headless run follows. Target roles are defined at the top (edit them there).
- `companies.txt` — companies to monitor, one per line.
- `.claude/agents/job-searcher.md` — Haiku subagent, one spawned per company needing a search.
- `.companies/{slug}.md` — per-company search cache. Fresh = younger than `TTL_DAYS` (1) and survives a `REFRESH_PROB` (3% per run — tuned for hourly cadence) random refresh roll; both knobs are in `scripts/cache.py`.
- `jobs.db` — SQLite. Jobs dedupe on normalized URL; `status` is `found` → `emailed`; `resume_path`/`resume_kind`/`resume_fit` record what's attached and how it fits the JD.
- `config.json` — `resume_mode`: `baseline` (always closest baseline), `hybrid` (default; baseline unless a custom clearly helps), or `custom` (build per-job every time).
- `.claude/agents/resume-tailor.md` — Sonnet subagent, one per new job: applies the resume mode, writes a JD fit assessment (strengths/gaps, goes in the email), registers via `jobsdb.py set-resume`. Custom builds are flagged for review in the email. See `resume/README.md`.
- `.claude/commands/setup.md` — `/setup`: guided first-time configuration (credentials, companies, roles, mode, test run, schedule).
- `resume/` — bullet database (source of truth: `resume/resume-bullet-database.md`), baseline PDFs + reconstructed `.tex` sources, generated custom resumes.
- `scripts/` — deterministic helpers (cache decision, DB CRUD, Gmail SMTP, pdflatex + 1-page check). Stdlib only, no dependencies.

## Setup (one-time)

Run **`/setup`** in an interactive session for the guided version of all of this. Manually:

1. **Gmail App Password** (needed before emails work): requires 2FA on the Google account. Create one at https://myaccount.google.com/apppasswords, then either:
   - `mkdir -p ~/.config/jobs-pipeline && echo 'GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx' > ~/.config/jobs-pipeline/env && chmod 600 ~/.config/jobs-pipeline/env`
   - or export `GMAIL_APP_PASSWORD` in the environment.
2. `companies.txt`, `PROMPT.md`, and `config.json` are gitignored personal files — create each from its `.example` copy (`cp companies.txt.example companies.txt` etc.), then fill in companies, the target-roles section, and `config.json` (email + `resume_mode`).
3. **Manual test run** from this directory: `mkdir -p logs && claude -p "Follow the instructions in PROMPT.md"`.
4. **Install the schedule** once manual runs look good:
   ```sh
   cp launchd/com.alivayani.jobsearch.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.alivayani.jobsearch.plist
   # to trigger immediately for testing:
   launchctl start com.alivayani.jobsearch
   # to uninstall:
   launchctl unload ~/Library/LaunchAgents/com.alivayani.jobsearch.plist
   ```
   Logs land in `logs/run-YYYY-MM-DD.log`.

## Conventions

- Deterministic logic (dedupe, cache TTL, email, LaTeX compile checks) lives in `scripts/` — don't reimplement it in prompts.
- Scripts are stdlib-only Python; keep them that way.
- `jobsdb.py add` is the single source of truth for "have we seen this job" — always route findings through it.
- Never email a job the DB reported as DUPLICATE.
- Resume rules (same-work sets, 17-bullet budget, line rendering) live in `resume/resume-bullet-database.md` — the tailor agent must follow it, not improvise.
- Never compile LaTeX output into `resume/baselines/` — the original PDFs there are ground truth (`compile_resume.py` defaults to `resume/build/` for this reason).

## Useful commands

```sh
python3 scripts/jobsdb.py list                # all tracked jobs
python3 scripts/jobsdb.py pending             # found but not yet emailed
python3 scripts/cache.py check                # which companies would be searched right now
```
