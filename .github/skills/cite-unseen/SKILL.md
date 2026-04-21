---
name: cite-unseen
description: >
  Extract, QA-verify, and summarize a collection of academic PDFs. Use when asked to
  process papers, extract PDFs, run the paper pipeline, or build summaries/concepts
  from a paper collection.
allowed-tools:
  - shell
---

# Task: Pre-process a collection of academic PDFs

> **READ THIS FIRST.** This pipeline is designed to run as an **orchestrator + subagents**.
> Every per-paper unit (extraction, figure description, QA, summarization) MUST be
> dispatched to a subagent — never inlined into the orchestrator, regardless of how
> simple the shell commands look or how many papers are in scope. Cost is not your
> concern: the user already accepted it by invoking this skill. See "Subagent
> architecture" below for the full rationale. If you catch yourself reasoning about
> "avoiding subagent overhead", stop and re-read that section.

## Inputs

- **`{{papers_dir}}`** (default: `papers/`) — directory containing PDF files to process.
- **`{{papers}}`** (default: `all`) — which papers to process.

### Paper selection

Accepted formats for `{{papers}}`:
- `all` — process every PDF in the papers directory
- Filename stems, comma-separated: `smith-2020-method, jones-2019-framework`
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
├── .github/skills/cite-unseen/
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

The install steps use bash syntax (run them in `bash -c` or a bash shell). Activation
of a fish-shell venv is a separate step:

```bash
# One-time setup (bash)
pip install marker-pdf
which pdftoppm || sudo apt-get install -y poppler-utils
```

```fish
# Per-session (fish)
source .venv/bin/activate.fish
```

If you're running the whole pipeline in bash, use `source .venv/bin/activate` instead.

Paper directories under `processed/` are created automatically by each subagent.

## Hardware

- Marker uses **~9.6 GB VRAM peak** per worker with `--force_ocr`
- **One worker per GPU** — two workers on the same 16 GB GPU will OOM or thrash
- With N GPUs: up to N concurrent extraction workers, each pinned via
  `CUDA_VISIBLE_DEVICES` (see Phase 1 "GPU assignment")
- A 10-page paper takes ~45 seconds per worker on GPU
- QA and summarization phases are CPU-only — fully parallelizable

## Subagent architecture

Each phase that operates per-paper uses a **subagent** with a self-contained prompt file
in this skill directory. The orchestrator (this file) reads the agent prompt, substitutes
`{{PAPER_NAME}}` with the paper's filename stem (e.g., `smith-2020-method`), and
invokes the subagent.

### MANDATORY: do not inline per-paper work

**You MUST spawn a subagent for every per-paper unit listed below. Do not inline this
work into the orchestrator, regardless of perceived cost or simplicity.**

Phases that require subagents (one invocation per item):

| Phase | Unit | Subagent prompt |
|-------|------|-----------------|
| 1 | one per paper | `extract.md` |
| 2b | one per figure | `describe-figure.md` |
| 3 | one per paper | `qa.md` |
| 5 | one per paper | `summarize.md` |

Phases 4 and 6 are orchestrator-only (triage + index assembly) and do not spawn subagents.

### Why this is non-negotiable

- **Context budget is the bottleneck, not token cost.** Inlining extract.md into the
  orchestrator pulls marker stdout, file listings, image counts, and per-paper sanity
  checks into main context. Across 25 papers that's tens of thousands of tokens of
  transient output crowding out the actual orchestration state.
- **You will underestimate "just shell commands".** Phase 1 looks like plain bash, but
  real runs produce multi-page stderr, OCR warnings, and failure diagnostics. A subagent
  absorbs all of that and returns a one-line status. The orchestrator stays clean.
- **Subagents are not a "premium" path.** They are the default. The question is never
  "is this worth spawning a subagent?" — it's "do I have a reason NOT to?" For the units
  in the table above, the answer is always no.
- **Cost reasoning is out of scope.** Do not budget subagent invocations. Do not batch
  papers to "save" subagents. Do not inline to "avoid overhead". The user already
  accepted the cost by invoking this skill.

### What you CAN do

- Run extraction subagents in **waves of up to 2** (GPU constraint). Spawn 2, wait, spawn
  the next 2. This is parallelism scheduling, not an inlining license.
- Run Phase 2b, 3, 5 subagents **fully in parallel** (all CPU-only). Spawn as many as
  the runtime will accept simultaneously.
- Orchestrator-level work (reading `_index.json`, aggregating QA verdicts, assembling
  `INDEX.md`) stays in the orchestrator.

### If no subagent runtime is available

Only if the runtime truly cannot spawn subagents (not "would prefer not to"): stop and
tell the user. Do not silently fall back to inlining. If the user confirms they want
an inline fallback, **run Phase 3 (QA) before Phase 2 (figures)** — QA may edit
`paper.md` to fix mechanical issues, and Phase 2 figure descriptions quote paper text.

---

## Phase 1: Extraction + Page Image Export

**Agent prompt**: `extract.md` (in this skill directory)
**Parallelism**: max 2 at a time (GPU-bound)
**Subagent required**: YES — one per paper. Do NOT inline `marker_single` calls into
the orchestrator, even though they are "just shell commands". See the "MANDATORY"
subsection above.

### GPU assignment

Before dispatching, detect available GPUs:

```bash
nvidia-smi --query-gpu=index --format=csv,noheader 2>/dev/null | wc -l
```

Assign a GPU index to each concurrent worker via the `{{GPU_INDEX}}` template variable:

- **2+ GPUs**: spawn workers in waves of 2, assigning `GPU_INDEX=0` to one and
  `GPU_INDEX=1` to the other. Each worker sets `CUDA_VISIBLE_DEVICES` to its assigned
  index before running marker.
- **1 GPU**: spawn 1 worker at a time with `GPU_INDEX=0`.
- **0 GPUs / CPU-only**: pass an empty string for `{{GPU_INDEX}}`; the worker will skip
  the export and marker will fall back to CPU (much slower).

Without this, both marker workers default to GPU 0 and one OOMs or both fight for the
same device while the second GPU sits idle.

### Dispatch

For each selected paper, invoke a subagent with `extract.md`, substituting
`{{PAPER_NAME}}`, `{{PAPERS_DIR}}`, and `{{GPU_INDEX}}`. Each subagent runs
`marker_single` and `pdftoppm` for its paper on its assigned GPU.

Wait for all to complete. Collect status reports.
If any report `"failed"`, stop and report to user.

**Git commit**: `processed/*/paper.md`, `processed/*/images/`, `processed/*/page-images/`

---

## Phase 2: Figure Descriptions

**Agent prompt**: `describe-figure.md` (in this skill directory)
**Parallelism**: fully parallel (CPU-only — one subagent per figure)
**Subagent required**: YES — one per figure (not per paper). Do NOT describe figures
inline.

### 2a. Index figures (mechanical)

For each paper, run the figure indexing script. It scans `paper.md` for image references,
extracts ~2000 chars of surrounding context per figure, and writes a structured
`_index.json`:

```bash
python .github/skills/cite-unseen/scripts/index_figures.py {{PAPER_NAME}}
```

Output: `processed/{{PAPER_NAME}}/figures/_index.json` — a list of
`{filename, stem, context}` entries. Figures with no markdown reference get a
standard placeholder context.

Do **not** scan `paper.md` by hand — the script is deterministic and keeps main context
free of full paper text.

### 2b. Dispatch figure subagents

Read `processed/{{PAPER_NAME}}/figures/_index.json`. Each entry has fields
`{filename, stem, label, caption, context}`. `label` and `caption` are populated when the
script detects a caption in the paper (e.g., `"Figure 3"`, `"A slot feature."`); they are
`null` for artifacts like logos and headshots.

For each entry, invoke a subagent with `describe-figure.md`, substituting:
- `{{PAPER_NAME}}` — paper filename stem
- `{{FIGURE_FILENAME}}` — `entry.filename`
- `{{FIGURE_STEM}}` — `entry.stem`
- `{{FIGURE_LABEL}}` — `entry.label` or empty string
- `{{FIGURE_CAPTION}}` — `entry.caption` or empty string
- `{{FIGURE_CONTEXT}}` — `entry.context`

**Idempotency:** Before dispatching, check if
`processed/{{PAPER_NAME}}/figures/{{stem}}.md` already exists. If it does, skip that
entry — it was either described or skipped in a prior run. Re-runs should be cheap.
To force regeneration, delete the `.md` file first.

Each subagent views one image, writes one description file (or a skip stub) to
`processed/{{PAPER_NAME}}/figures/{{FIGURE_STEM}}.md`.

Collect results. Skipped figures are normal (header/footer/logo artifacts). No failures
expected — if a subagent can't view the image, report to user.

**Git commit**: `processed/*/figures/`

---

## Phase 3: Quality Verification + Fix

**Agent prompt**: `qa.md` (in this skill directory)
**Parallelism**: fully parallel (CPU-only)
**Subagent required**: YES — one per paper. Do NOT view page images inline.

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
**Subagent required**: YES — one per paper. Do NOT read `paper.md` files in the
orchestrator to write summaries inline.

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
named by filename stem (e.g., `processed/smith-2020-method/`).

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
Group papers by concept. Use filename stems as identifiers, linked to their summary files.

**Concept budget** — this table is for *discovery*, not for tagging every nuance:

- Target **8–20 concepts total** across the whole collection, regardless of collection
  size. More than 20 becomes hard to scan.
- Every paper should appear in **2–5 concepts** — not 1 (too isolated) and not 7+
  (concepts too fine-grained).
- **Merge near-synonyms** aggressively (e.g., two phrasings of the same underlying idea
  should collapse to one row).
- If a candidate concept has only 1 paper, either (a) generalize it until another paper
  fits, or (b) fold it into a broader concept. Single-paper concepts add noise without
  aiding discovery.
- Sort concepts by paper count descending (most-cited first), then alphabetically.

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