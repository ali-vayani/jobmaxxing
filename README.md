# Job Search Pipeline

An automated pipeline that watches a list of companies for new job postings, dedupes them against everything it's already seen, picks (or builds) the best-fitting resume for each, and emails each new job to me with the resume attached. Runs every 2 hours using headless Claude Code (`claude -p`) — no API key billing, just the existing Claude subscription.

## How it works

```
launchd (every 2 hours)
   └─> claude -p "Follow the instructions in PROMPT.md"
         ├─ 1. cache.py check       → which companies need a fresh search?
         ├─ 2. job-searcher agents  → one cheap Haiku subagent per company, in parallel
         │       ├─ finds the careers page + matching postings (web search)
         │       ├─ writes cache: .companies/{slug}.md
         │       └─ registers each posting: jobsdb.py add  → NEW or DUPLICATE
         ├─ 3. resume-tailor agents → one Sonnet subagent per NEW job,
         │       governed by resume_mode in config.json:
         │       ├─ baseline: always picks the closest of 5 baseline resumes
         │       ├─ hybrid (default): closest baseline, unless the JD clearly
         │       │    calls for a custom build
         │       └─ custom: builds a job-specific .tex from the bullet database
         │            for every job — compiles + 1-page check, and any custom
         │            build is flagged for manual review
         └─ 4. send_email.py        → one email per NEW job with the resume
                                      attached, then mark emailed
```

The split is deliberate: **Claude handles the fuzzy work** (finding careers pages, judging which roles match, summarizing JDs) while **plain Python handles everything deterministic** (cache freshness, dedup, email). The scripts are stdlib-only — nothing to install.

### Caching

Each company's cache in `.companies/{slug}.md` stores the **route** — the careers-page URL discovery landed on — plus the last results. The careers page itself is re-checked **every run**: cached companies get a lightweight "re-check mode" search that fetches the known URL directly instead of re-discovering it. Full discovery (web-searching for the careers page again, in case it moved) reruns when the cache is **older than 1 day** or on a **3% random refresh roll**. Both knobs live at the top of `scripts/cache.py`.

### Dedup

`jobs.db` (SQLite) is the source of truth for "have we seen this job." Every posting goes through `jobsdb.py add`, which normalizes the URL (drops `www.`, query params, trailing slashes) and does an `INSERT OR IGNORE` — so the same job found via slightly different links only ever produces one email. Jobs carry a status (`found` → `emailed`), so a crashed run just retries un-emailed jobs next time.

### Resume selection

Five baseline resumes (GENERAL, INFRA, BACKEND, PRODUCT, AI) live in `resume/baselines/` as original PDFs plus reconstructed LaTeX sources, all built from `resume/resume-bullet-database.md` — the bullet bank that also defines which bullets can't co-occur and the one-page layout budget. Custom builds swap database bullets into the nearest baseline's `.tex`, compile with a hard 1-page check, get visually verified, and arrive flagged **"REVIEW IT before submitting"** in the email. Details: `resume/README.md`.

**Resume mode** (`resume_mode` in `config.json`) controls how eagerly customs are built:

| Mode | Behavior |
|---|---|
| `baseline` | Always attach the closest baseline PDF. Zero review burden. |
| `hybrid` (default) | Closest baseline unless the JD clearly calls for a custom build. |
| `custom` | Build a job-specific resume for every job. Max tailoring, every attachment needs review. |

Whatever the mode, every email also includes a **fit assessment**: which resume bullets hit the JD's requirements, where the resume is weak against it, and (when useful) a talking-point suggestion.

## Layout

| Path | What it is |
|---|---|
| `PROMPT.md` | Orchestrator prompt for the headless run. **Target roles are defined at the top — edit them.** |
| `companies.txt` | Companies to monitor, one per line. |
| `config.json` | Pipeline settings — currently just `resume_mode` (`baseline` / `hybrid` / `custom`). |
| `.claude/commands/setup.md` | The `/setup` command: guided first-time configuration. |
| `.claude/commands/setup-resumes.md` | The `/setup-resumes` command: builds the whole resume system (bullet database + baselines) from your information. Run standalone or automatically via `/setup` when assets are missing. |
| `resume/template.tex` | Blank one-page resume template that `/setup-resumes` builds baselines from. |
| `.claude/agents/job-searcher.md` | The per-company search subagent (Haiku, web-search tools only). |
| `.claude/agents/resume-tailor.md` | The per-job resume subagent (Sonnet): baseline pick or custom build. |
| `.claude/settings.json` | Permission allowlist so headless runs never stall on prompts. |
| `.companies/` | Per-company search cache (gitignored). |
| `jobs.db` | SQLite job tracker (gitignored, created on first run). |
| `scripts/cache.py` | Fresh-vs-stale decision (TTL + random refresh). |
| `scripts/jobsdb.py` | DB CRUD: `add` (dedupe), `pending`, `mark`, `set-resume`, `list`. |
| `scripts/send_email.py` | Gmail SMTP sender; fills `email/TEMPLATE.md`, attaches the job's resume. |
| `scripts/compile_resume.py` | pdflatex wrapper with a hard 1-page check (outputs to `resume/build/`). |
| `email/TEMPLATE.md` | Email template (`Subject:` first line, body below, `{placeholders}`). |
| `launchd/*.plist` | Daily schedule definition (install manually, see below). |
| `resume/` | Bullet database (source of truth), baseline PDFs + `.tex` sources, generated custom resumes. See `resume/README.md`. |

## Setup

**Easiest way:** open an interactive Claude Code session in this repo and run **`/setup`** — it walks through everything below (credentials, companies, target roles, the resume system, a test run, and the schedule) conversationally. If no resume assets exist yet, it runs the full resume onboarding (`/setup-resumes`): you provide your experience/bullets/numbers, it builds the bullet database and the baseline resumes from `resume/template.tex`, and you pick the resume mode.

Manual version:

1. **Gmail App Password** (requires 2FA): create at <https://myaccount.google.com/apppasswords>, then:
   ```sh
   mkdir -p ~/.config/jobs-pipeline
   echo 'GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx' > ~/.config/jobs-pipeline/env
   chmod 600 ~/.config/jobs-pipeline/env
   ```
2. Create your personal copies of the gitignored config files, then fill them in:
   ```sh
   cp companies.txt.example companies.txt
   cp PROMPT.md.example PROMPT.md
   cp config.json.example config.json
   ```
   Edit `companies.txt` (your companies), the target-roles section of `PROMPT.md`, and `config.json` (your email + `resume_mode`).
3. **Manual test run** from this directory:
   ```sh
   mkdir -p logs && claude -p "Follow the instructions in PROMPT.md"
   ```
   Run it twice — the second run should report everything cached/duplicate and send no emails.
4. **Install the schedule** once manual runs look good:
   ```sh
   cp launchd/com.alivayani.jobsearch.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.alivayani.jobsearch.plist
   ```
   Runs every 2 hours (`StartInterval` in the plist). Logs land in `logs/run-YYYY-MM-DD.log`, one file per day. (launchd over cron because it catches up after the Mac wakes from sleep, and it won't start a second run while the previous one is still going.)

   **Note:** launchd only fires while the Mac is awake — it catches up once on wake, but hours spent asleep are skipped. For true around-the-clock checking, keep the machine awake (e.g. `caffeinate`, Amphetamine, or plugged in with sleep disabled); the missed-run catch-up plus the 1-day cache TTL means nothing is permanently missed either way.

## Useful commands

```sh
python3 scripts/jobsdb.py list                                        # everything ever found
python3 scripts/jobsdb.py pending                                     # found but not yet emailed
python3 scripts/cache.py check                                        # which companies would be searched right now
python3 scripts/compile_resume.py resume/baselines/<PREFIX>_AI.tex    # rebuild a baseline after edits
```
