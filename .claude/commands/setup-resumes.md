---
description: Build (or rebuild) the resume system from the user's information — bullet database, baseline resumes, and resume mode
---

You are setting up the resume system for the job-search pipeline. The end state is:
1. `resume/resume-bullet-database.md` — every bullet the user can claim, tagged and organized
2. 3–6 compiled one-page **baseline resumes** in `resume/baselines/` (a `.tex` + `.pdf` per track)
3. `resume_mode` set in `config.json`

Work conversationally, one phase at a time. **Cardinal rule: never invent facts.** Every number, technology, date, and claim comes from the user or their documents. If a bullet is missing its measurable result (the Y in XYZ), ask the user for the real number — and if they don't have one, write the bullet without a number rather than estimating one.

## Phase 1 — Gather raw material

Ask the user for whatever they already have, in any combination:
- Existing resume files (PDF, .tex, .docx, Google Doc export) — ask for paths and read them
- A LinkedIn profile export, brag doc, or plain-text description of their experience

Then fill gaps by interviewing:
- **Header:** full name, phone, email, LinkedIn handle, GitHub handle, website (optional)
- **Education:** school, degree, grad date, GPA (optional), relevant coursework (optional)
- **Experiences:** for each job/internship/org — company, title, dates, location, and what they actually did. Push for specifics: scale ("how many users/queries/documents?"), measured outcomes ("what improved, by how much?"), and the method ("how, specifically?")
- **Projects** and **skills** (languages / tools / frameworks)

## Phase 2 — Choose the tracks (baselines)

Ask what kinds of roles they're applying to, then propose 3–6 tracks. Default suggestion: **GENERAL** (always include this one — the "if you could only send one" build) plus 2–5 role-type tracks such as INFRA, BACKEND, PRODUCT, AI, FRONTEND, DATA, EMBEDDED — whatever matches their targets. Confirm the final list and a filename prefix from their name (e.g. `JANE_DOE` → `JANE_DOE_GENERAL.tex`).

## Phase 3 — Draft the bullet database

Write `resume/resume-bullet-database.md`. If one already exists, confirm before overwriting (offer to back it up to `resume/resume-bullet-database.backup.md`). Follow this structure — it is what the `resume-tailor` agent parses, so keep all parts:

- **Header:** XYZ-format note; the tag legend (one tag per track, e.g. `[INFRA]`, plus `[LEAD]` if leadership bullets exist); explanation of the `↳` metadata line (`tech` · `shows` · `used on`); the page-capacity note (filled in after Phase 4 measures it).
- **"The baselines" section:** one line per track — what's on it and when to send it (the tailor agent scores JDs against these descriptions, so write them as fit guidance).
- **Per-experience sections:** a *Context for tailoring* line, then numbered bullets. Each bullet: tag, XYZ text with `**bold**` on key numbers/tech, then the `↳` line. Include useful variants (same work, different angle) even if no baseline uses them — mark `used on: —`.
- **Notes & flags:** the **same-work sets** (bullets describing the same work from different angles — list every set; two from one set must never appear on one resume); any per-role recipes.
- **Layout & length reference:** per-bullet rule (1 line, or 1.5–2 lines — never a few words orphaned on a second line), ~17–19 words/line and ~35-word drafting ceiling, and the verification workflow (compile, check 1 page, eyeball the PDF).

Draft bullets in XYZ format from the Phase 1 material, then **review them with the user in batches** — confirm every number is real, fix wording, drop anything they can't defend in an interview.

## Phase 4 — Build the baselines

For each track:
1. Copy `resume/template.tex` → `resume/baselines/<PREFIX>_<TRACK>.tex` and fill in header, education, skills, and the track's bullet selection (best bullets for that track's story; respect same-work sets; GENERAL gets the strongest spread with no two bullets showing the same skill).
2. Compile: `python3 scripts/compile_resume.py resume/baselines/<PREFIX>_<TRACK>.tex`
   - Over 1 page → trim bullets or sections and retry. Under-full → add bullets.
3. **Visual pass:** Read the PDF from `resume/build/` and check every bullet renders at 1 or 1.5–2 lines, no single-word orphan lines. Fix and recompile (2–3 passes is normal).
4. When it's right, copy the PDF into place: `cp resume/build/<PREFIX>_<TRACK>.pdf resume/baselines/`
5. Show the user the finished PDF path and get their sign-off before moving to the next track.

After all tracks: go back to the database and fill in the measured page capacity (how many bullets fit), the standard section allocation, and set every bullet's `used on` metadata to match what was actually built.

## Phase 5 — Resume mode

Explain the three modes and set `resume_mode` in `config.json`:
- **`baseline`** — every job gets the closest baseline PDF. Zero review burden.
- **`hybrid`** (recommended default) — closest baseline unless the JD clearly calls for a custom build; customs are flagged for review in the email.
- **`custom`** — a job-specific resume built for every job; every attachment needs a visual review before submitting.

## Phase 6 — Wrap up

Summarize: the tracks built, where everything lives, and how the pipeline uses it (the `resume-tailor` agent reads the database, picks/builds per job, and every email includes a fit assessment). Tell them future edits go in `resume/resume-bullet-database.md` and the baseline `.tex` files, with the rebuild workflow in `resume/README.md`.
