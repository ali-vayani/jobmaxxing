# Resume Tailoring

For each new job the pipeline finds, the `resume-tailor` subagent (`.claude/agents/resume-tailor.md`) decides which resume to send, governed by `resume_mode` in `config.json`:

- **`baseline`** — always the closest of the five baselines (GENERAL, INFRA, BACKEND, PRODUCT, AI), scored against the JD using the fit descriptions in `resume-bullet-database.md`. Its original PDF is attached.
- **`hybrid`** (default) — closest baseline, unless no baseline clearly covers the JD's emphasis (or it stresses evidence living only in unused database bullets — Java, compliance, caching, leadership, etc.); only then is a custom resume built.
- **`custom`** — a job-specific resume is built for every job, starting from the closest baseline.

**Custom builds:** the agent copies the nearest baseline's `.tex`, swaps in better bullets from the database (respecting same-work sets and the 17-bullet page budget), compiles with `scripts/compile_resume.py`, visually verifies line rendering, and attaches the result — **flagged in the email for manual review before submitting.**

**Fit assessment:** whatever the mode, the agent writes a 3–5 sentence comparison of the chosen resume against the JD — which bullets hit the requirements, where the resume is weak, and any advice — stored on the job (`resume_fit`) and included in the email body.

## Files

| Path | What it is |
|---|---|
| `resume-bullet-database.md` | **Source of truth.** Every bullet, tags, same-work sets, baseline definitions, layout math. Built by `/setup-resumes`; edit it here. |
| `template.tex` | Blank Jake Gutierrez skeleton — `/setup-resumes` builds new baselines from it. |
| `baselines/<PREFIX>_*.pdf` | The five original baseline PDFs (what gets attached for baseline picks). |
| `baselines/<PREFIX>_*.tex` | Reconstructed LaTeX sources (Jake Gutierrez template, 10.5pt) — verified text-identical to the PDFs. Custom resumes start from these. Never compile output into this directory. |
| `custom/` | Generated per-job resumes (`job<id>-<company>.tex` + `.pdf`). |
| `build/` | pdflatex scratch output (gitignored). |
| `<PREFIX>_MASTER.pdf` | 2-page superset of all bullets — reference only, never submitted. |

## Editing bullets

After editing `resume-bullet-database.md` or any baseline `.tex`:

```sh
python3 scripts/compile_resume.py resume/baselines/<PREFIX>_<NAME>.tex
open resume/build/<PREFIX>_<NAME>.pdf   # visual pass: no orphan lines, nothing over 2 lines
```

Then replace the corresponding `baselines/<PREFIX>_<NAME>.pdf` with the new build once it looks right, and keep the database's "used on" metadata in sync.

To rebuild the whole system from scratch (or onboard a different person's resume data), run **`/setup-resumes`** in an interactive session.
