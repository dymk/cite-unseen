# Task: Pre-process 25 academic PDFs about the Persistent Naming Problem in CAD

## Context

This git repo contains 25 papers on the Topological/Persistent Naming Problem (TNP) in
parametric CAD. The repo is already organized with standardized filenames and an INDEX.md.
The goal is to extract high-quality text and build structured summaries so a future coding
agent can use these papers without re-processing PDFs at query time.

## Repo layout

```
<root>/
├── prompt.md                            # this file — orchestration instructions
├── .agents/
│   ├── extract.md                       # subagent prompt: Phase 1 extraction
│   ├── describe-figure.md               # subagent prompt: Phase 2 figure description
│   ├── qa.md                            # subagent prompt: Phase 3 QA + fix
│   └── summarize.md                     # subagent prompt: Phase 5 summarization
├── papers/
│   ├── INDEX.md                         # one-line-per-paper manifest (DO NOT MODIFY)
│   ├── 01-kripac-1997-naming.pdf
│   ├── ... (25 PDFs total) ...
│   └── 25-zheng-2004-persistent-naming.pdf
└── processed/                           # all outputs go here
    ├── text/                            # extracted markdown + figures
    ├── page-images/                     # rendered page PNGs for QA
    ├── figures/                         # per-figure markdown descriptions
    ├── qa/                              # per-paper QA verification reports
    ├── summaries/                       # per-paper structured summaries
    └── CONCEPTS.md                      # concept → paper routing table
```

## Prerequisites (Phase 0)

```bash
pip install marker-pdf
which pdftoppm || sudo apt-get install -y poppler-utils
source .venv/bin/activate.fish
mkdir -p processed/{text,page-images,figures,qa,summaries}
```

## Hardware

- 2× RTX 4080 GPUs (16 GB VRAM each)
- Marker uses **~9.6 GB VRAM peak** per worker with `--force_ocr` (measured)
- **Max 2 extraction workers at a time** (one per GPU)
- A 10-page paper takes ~45 seconds per worker on GPU
- QA and summarization phases are CPU-only — fully parallelizable

## Subagent architecture

Each phase that operates per-paper uses a **subagent** with a self-contained prompt file
in `.agents/`. The orchestrator (this file) reads the agent prompt, substitutes
`{{PAPER_NAME}}` with the paper's filename stem (e.g., `01-kripac-1997-naming`), and
invokes the subagent.

This design:
- Prevents main agent context overflow (each paper is isolated)
- Enables parallelism (independent subagents can run concurrently)
- Makes prompts independently iterable and reviewable

---

## Phase 1: Extraction + Page Image Export

**Agent prompt**: `.agents/extract.md`
**Parallelism**: max 2 at a time (GPU-bound)

For each of the 25 papers, invoke a subagent with `.agents/extract.md`, substituting
`{{PAPER_NAME}}`. Each subagent runs `marker_single` and `pdftoppm` for its paper.

Wait for all 25 to complete. Collect status reports.
If any report `"failed"`, stop and report to user.

**Git commit**: `processed/text/` and `processed/page-images/`

---

## Phase 2: Figure Descriptions

**Agent prompt**: `.agents/describe-figure.md`
**Parallelism**: fully parallel (CPU-only — one subagent per figure)

For each paper, list the image files in `processed/text/{{PAPER_NAME}}/` (excluding
`.md` and `.json`). For each figure:

1. Find where the figure is referenced in the extracted markdown (look for
   `![...](FILENAME)` or similar embed syntax).
2. Extract **~300–500 words** of surrounding markdown context (the section or paragraphs
   around the figure reference). If the figure has no reference in the markdown, set
   context to: `"This figure was extracted but not referenced in markdown."`
3. Invoke a subagent with `.agents/describe-figure.md`, substituting:
   - `{{PAPER_NAME}}` — paper filename stem
   - `{{FIGURE_FILENAME}}` — image filename (e.g., `image_0.jpeg`)
   - `{{FIGURE_STEM}}` — filename without extension (e.g., `image_0`)
   - `{{FIGURE_CONTEXT}}` — the surrounding text extracted above

Each subagent views one image, writes one description file to
`processed/figures/{{PAPER_NAME}}/{{FIGURE_STEM}}.md`, or reports `"skipped"` for
non-figure artifacts.

Collect results. Skipped figures are normal (header/footer artifacts). No failures
expected — if a subagent can't view the image, report to user.

**Git commit**: `processed/figures/`

---

## Phase 3: Quality Verification + Fix

**Agent prompt**: `.agents/qa.md`
**Parallelism**: fully parallel (CPU-only)

Phase 2 and Phase 3 are independent and **can run in parallel**.

For each paper, invoke a subagent with `.agents/qa.md`, substituting `{{PAPER_NAME}}`.
Each subagent views page images, compares against extracted markdown, fixes mechanical
issues, and writes a QA report. Figure verification is handled by Phase 2 — QA focuses
on math and text.

**Git commit**: `processed/qa/`

---

## Phase 4: Triage QA Results

**No subagent** — the orchestrator handles this directly.

Read all 25 QA reports from `processed/qa/`:

- If any paper is **FAIL**: stop and report to user with specific issues. User decides
  whether to re-extract or skip.
- If any paper is **WARN**: list all warnings. Ask user whether to proceed or re-extract.
- If all **PASS**: proceed to Phase 5.

---

## Phase 5: Per-Paper Structured Summaries

**Agent prompt**: `.agents/summarize.md`
**Parallelism**: fully parallel (CPU-only)

For each paper, invoke a subagent with `.agents/summarize.md`, substituting
`{{PAPER_NAME}}`. Each subagent reads the extracted text, figure descriptions, and writes
a structured summary.

**Git commit**: `processed/summaries/`

---

## Phase 6: Build CONCEPTS.md

**No subagent** — the orchestrator handles this directly (all 25 summaries fit in
context).

Read all 25 summaries and `papers/INDEX.md`, then generate `processed/CONCEPTS.md`.

Start with at least these seed categories, add more as the summaries reveal:

| Concept | Papers |
|---------|--------|
| persistent naming (original formulations) | 01, 02, 03 |
| face-based naming | 06 |
| feature-based naming | 07, 20, 23 |
| graph rewriting / Jerboa | 10, 24 |
| B-rep deformation / topology variance | 04, 15, 16 |
| parametric families | 14, 16 |
| dual representation consistency | 17 |
| CAD model exchange | 08, 21, 22 |
| entity matching | 19 |
| editability / E-Rep | 12, 13 |
| hierarchical naming | 18 |
| macro-parametrics | 09 |
| survey / literature review | 05, 09, 11 |
| OCCT / CAS.CADE lineage | 03 |

Every paper (01–25) must appear in **at least one** concept row.

**Git commit**: `processed/CONCEPTS.md`

---

## Important notes

- Do NOT modify `papers/INDEX.md` — it is already complete.
- Paper 24 (Cardot thesis) is in French. Extract fully, summarize in English.
- `--force_ocr` is **mandatory** — marker requires it to convert inline math to LaTeX.
- Do NOT use `--use_llm` unless you configure Ollama (see `.agents/extract.md`).
- Always activate the venv before running marker: `source .venv/bin/activate.fish`
- If `marker` fails on any PDF, the extraction subagent reports the error — do not skip.
- Phase 2 (figures) and Phase 3 (QA) are independent — run them in parallel.