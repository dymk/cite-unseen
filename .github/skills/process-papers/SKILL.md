---
name: process-papers
description: >
  Extract, QA-verify, and summarize a collection of academic PDFs. Use when asked to
  process papers, extract PDFs, run the paper pipeline, or build summaries/concepts
  from a paper collection.
allowed-tools:
  - shell
---

# Task: Pre-process a collection of academic PDFs

## Inputs

- **`{{papers_dir}}`** (default: `papers/`) — directory containing PDF files to process.
- **`{{papers}}`** (default: `all`) — which papers to process.

### Paper selection

Accepted formats for `{{papers}}`:
- `all` — process every PDF in the papers directory
- Filename stems, comma-separated: `kripac-1997-naming, capoyleas-1996-generic-naming`
- Shell glob: `*-2002-*` (matches filenames)

At startup, list all `*.pdf` files in `{{papers_dir}}`. If `{{papers}}` is not `all`,
filter to matching stems. The filename stem (PDF name without `.pdf`) becomes the
`{{PAPER_NAME}}` used throughout.

All phases below operate only on the selected papers.

## Context

The pipeline converts a directory of academic PDFs into high-quality extracted text,
per-figure descriptions, structured summaries, and a concept routing table — so a future
coding agent can use the papers without re-processing PDFs at query time.

## Repo layout

```
<root>/
├── .github/skills/process-papers/
│   ├── SKILL.md                         # this file — orchestration instructions
│   ├── extract.md                       # subagent prompt: Phase 1 extraction
│   ├── describe-figure.md               # subagent prompt: Phase 2 figure description
│   ├── qa.md                            # subagent prompt: Phase 3 QA + fix
│   ├── summarize.md                     # subagent prompt: Phase 5 summarization
│   └── scripts/                         # deterministic helpers (no LLM)
│       ├── reorganize_marker_output.py  # Phase 1 post-marker reorg
│       └── index_figures.py             # Phase 2 figure indexing
├── {{papers_dir}}/                      # input PDFs
│   ├── some-paper.pdf
│   └── another-paper.pdf
└── processed/                           # all outputs go here
    ├── {paper_name}/                    # one directory per paper
    │   ├── paper.md                     # full extracted markdown
    │   ├── summary.md                   # structured summary
    │   ├── qa.md                        # QA verification report
    │   ├── figures/                     # per-figure markdown descriptions
    │   ├── images/                      # extracted images from marker
    │   └── page-images/                 # rendered page PNGs (QA ground truth)
    └── INDEX.md                         # generated paper + concept index
```

## Prerequisites (Phase 0)

```bash
pip install marker-pdf
which pdftoppm || sudo apt-get install -y poppler-utils
source .venv/bin/activate.fish
```

Paper directories under `processed/` are created automatically by each subagent.
If a `.venv` directory exists at the repo root, activate it before running marker.

## Hardware

- Marker uses **~9.6 GB VRAM peak** per worker with `--force_ocr`
- **Max 2 extraction workers at a time** if using GPU
- A 10-page paper takes ~45 seconds per worker on GPU
- QA and summarization phases are CPU-only — fully parallelizable

## Subagent architecture

Each phase that operates per-paper uses a **subagent** with a self-contained prompt file
in this skill directory. The orchestrator (this file) reads the agent prompt, substitutes
`{{PAPER_NAME}}` with the paper's filename stem (e.g., `kripac-1997-naming`), and
invokes the subagent.

This design:
- Prevents main agent context overflow (each paper is isolated)
- Enables parallelism (independent subagents can run concurrently)
- Makes prompts independently iterable and reviewable

---

## Phase 1: Extraction + Page Image Export

**Agent prompt**: `extract.md` (in this skill directory)
**Parallelism**: max 2 at a time (GPU-bound)

For each selected paper, invoke a subagent with `extract.md`, substituting
`{{PAPER_NAME}}`. Each subagent runs `marker_single` and `pdftoppm` for its paper.

Wait for all to complete. Collect status reports.
If any report `"failed"`, stop and report to user.

**Git commit**: `processed/*/paper.md`, `processed/*/images/`, `processed/*/page-images/`

---

## Phase 2: Figure Descriptions

**Agent prompt**: `describe-figure.md` (in this skill directory)
**Parallelism**: fully parallel (CPU-only — one subagent per figure)

### 2a. Index figures (mechanical)

For each paper, run the figure indexing script. It scans `paper.md` for image references,
extracts ~2000 chars of surrounding context per figure, and writes a structured
`_index.json`:

```bash
python .github/skills/process-papers/scripts/index_figures.py {{PAPER_NAME}}
```

Output: `processed/{{PAPER_NAME}}/figures/_index.json` — a list of
`{filename, stem, context}` entries. Figures with no markdown reference get a
standard placeholder context.

Do **not** scan `paper.md` by hand — the script is deterministic and keeps main context
free of full paper text.

### 2b. Dispatch figure subagents

Read `processed/{{PAPER_NAME}}/figures/_index.json`. For each entry, invoke a subagent
with `describe-figure.md`, substituting:
- `{{PAPER_NAME}}` — paper filename stem
- `{{FIGURE_FILENAME}}` — `entry.filename`
- `{{FIGURE_STEM}}` — `entry.stem`
- `{{FIGURE_CONTEXT}}` — `entry.context`

Each subagent views one image, writes one description file to
`processed/{{PAPER_NAME}}/figures/{{FIGURE_STEM}}.md`, or reports `"skipped"` for
non-figure artifacts.

Collect results. Skipped figures are normal (header/footer artifacts). No failures
expected — if a subagent can't view the image, report to user.

**Git commit**: `processed/*/figures/`

---

## Phase 3: Quality Verification + Fix

**Agent prompt**: `qa.md` (in this skill directory)
**Parallelism**: fully parallel (CPU-only)

Phase 2 and Phase 3 are independent and **can run in parallel**.

For each paper, invoke a subagent with `qa.md`, substituting `{{PAPER_NAME}}`.
Each subagent views page images, compares against extracted markdown, fixes mechanical
issues, and writes a QA report. Figure verification is handled by Phase 2 — QA focuses
on math and text.

**Git commit**: `processed/*/qa.md`

---

## Phase 4: Triage QA Results

**No subagent** — the orchestrator handles this directly.

Read all QA reports (`processed/*/qa.md`) for the selected papers:

- If any paper is **FAIL**: stop and report to user with specific issues. User decides
  whether to re-extract or skip.
- If any paper is **WARN**: list all warnings. Ask user whether to proceed or re-extract.
- If all **PASS**: proceed to Phase 5.

---

## Phase 5: Per-Paper Structured Summaries

**Agent prompt**: `summarize.md` (in this skill directory)
**Parallelism**: fully parallel (CPU-only)

For each paper, invoke a subagent with `summarize.md`, substituting
`{{PAPER_NAME}}`. Each subagent reads the extracted text, figure descriptions, and writes
a structured summary.

**Git commit**: `processed/*/summary.md`

---

## Phase 6: Build INDEX.md

**No subagent** — the orchestrator handles this directly (all summaries fit in context).

Read all summaries from `processed/*/summary.md`.

Generate `processed/INDEX.md` with three sections:

### Section 1: How to Use This Collection

Introductory prose explaining the directory structure and file roles. Write this section
so that an agent encountering these files for the first time knows exactly where to look.
Include content equivalent to:

```markdown
# Paper Collection Index

## How to Use This Collection

Each paper in this collection has been extracted, verified, and summarized into a
standard directory structure under `processed/`. Every paper lives in its own directory
named by filename stem (e.g., `processed/kripac-1997-naming/`).

### Per-Paper Directory Layout

| File / Directory | What It Contains |
|------------------|------------------|
| `paper.md` | Full extracted markdown of the PDF — equations in LaTeX, section headings preserved. This is the primary source text. |
| `summary.md` | Structured summary: citation, key contribution, approach, algorithms, data structures, definitions, limitations, key figures, and relationships to other papers. **Start here** to decide if the paper is relevant. |
| `qa.md` | Quality verification report. Lists any known extraction issues (missing equations, garbled text, OCR artifacts). Check this if `paper.md` content looks suspicious. |
| `figures/` | One markdown file per extracted figure, containing a description of what the figure shows and how it relates to the paper's content. Filenames match the image filenames (e.g., `_page_2_Figure_9.md`). |
| `images/` | The actual image files extracted from the PDF by marker (JPEG/PNG). Referenced by `paper.md` inline. |
| `page-images/` | Full-page PNG renders of the original PDF at 150 DPI. Used as ground truth during QA — useful if you need to visually verify a specific page. |

### How to Find Information

- **Looking for a specific topic?** Check the Concept Index table below — it maps
  concepts to the papers that cover them.
- **Need a quick overview of a paper?** Read its `summary.md`.
- **Need the full details?** Read `paper.md`, consulting `figures/` for figure context.
- **Unsure about extraction quality?** Check `qa.md` for known issues.
```

Adapt the wording to fit the actual collection (e.g., adjust the example directory name
to a real paper from the batch), but keep the table and navigation guidance intact.

### Section 2: Paper Directory

A table with one row per paper, linking to its processed artifacts:

```markdown
## Papers

| Paper | Summary | Full Text | Figures | One-Line Description |
|-------|---------|-----------|---------|----------------------|
| some-paper | [summary](some-paper/summary.md) | [full text](some-paper/paper.md) | [figures](some-paper/figures/) | One sentence describing the paper's contribution |
```

Populate the one-line description from each paper's summary (Key Contribution, condensed
to one sentence). Sort by filename stem.

### Section 3: Concept Index

A concept → paper routing table:

```markdown
## Concepts

| Concept | Papers |
|---------|--------|
| some concept | [paper-a](paper-a/summary.md), [paper-b](paper-b/summary.md) |
```

Read all summaries and identify recurring themes, methods, and problem formulations.
Group papers by concept. Every paper must appear in at least one concept row. Use
filename stems as identifiers, linked to their summary files.

If processing a subset, **merge** with any existing INDEX.md rather than overwriting.

**Git commit**: `processed/INDEX.md`

---

## Important notes

- `--force_ocr` is **mandatory** — marker requires it to convert inline math to LaTeX.
- Do NOT use `--use_llm` unless you configure Ollama (see `extract.md`).
- If a `.venv` exists, activate it before running marker.
- If `marker` fails on any PDF, the extraction subagent reports the error — do not skip.
- Phase 2 (figures) and Phase 3 (QA) are independent — run them in parallel.
- Non-English papers: extract fully, summarize in English.