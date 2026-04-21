# Task: Pre-process a collection of 25 academic PDFs about the Persistent Naming Problem in CAD

## Context

I have a git repo of 25 papers on the Topological/Persistent Naming Problem (TNP) in
parametric CAD. The repo is already organized with standardized filenames and an INDEX.md.
Your job is to extract high-quality text and build structured summaries so a future coding
agent can use these papers without re-processing PDFs at query time.

## Current repo layout

```
cadscade-papers/
├── papers/
│   ├── INDEX.md                         # one-line-per-paper manifest, listing filename, citation, and brief relevance as to why it was include
│   ├── 01-kripac-1997-naming.pdf
│   ├── ... more papers ...
│   └── 25-zheng-2004-persistent-naming.pdf
```

## What to do — three steps

### Step 1: Extract full text using `marker`

Use `marker` (https://github.com/VikParuchuri/marker) to convert each PDF to markdown.
Output to `processed/text/NN-name.md` matching the PDF name, e.g.:

    processed/text/01-kripac-1997-naming.md

`marker` handles OCR internally, which matters because **papers 18 and 19 are scanned
image PDFs** — `pdftotext` returns empty output for them. Paper 24 is a ~200-page French
PhD thesis; extract it fully but note it's in French.

If `marker` produces extracted images/figures, place them in a directory `processed/text/01-kripac-1997-naming/` (e.g. `processed/text/01-kripac-1997-naming/fig1.png`).

### Step 2: Generate per-paper structured summaries

Read each extracted text and produce `processed/summaries/NN-name.md`. Each summary should
be 200–400 words and contain these sections:

```
# [Paper number] — [Short title]

## Citation
[Full citation from INDEX.md]

## Key Contribution
[1-2 sentences: what is new in this paper]

## Approach / Algorithm
[3-5 sentences: how it works]

## Key Definitions Introduced
[Bullet list of terms this paper defines or coins, if any]

## Limitations / Critique
[2-3 sentences: what it doesn't solve, known weaknesses]

## Key Figures
[List of figure numbers + page numbers worth revisiting for diagrams]

## Relationship to Other Papers
[Which papers in this collection it builds on, contradicts, or extends — use the NN numbers]
```

### Step 3: Build CONCEPTS.md (topic → paper routing table)

After completing summaries, generate `processed/CONCEPTS.md` mapping concepts to paper
numbers. Start with at least these categories, add more as you find them:

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

## Important notes

- Do NOT modify INDEX.md — it is already complete.
- Paper 24 (Cardot thesis) is in French. Summarize it in English.
- Commit each step separately: text extraction, then summaries, then CONCEPTS.md.
- If `marker` fails on any PDF, stop and tell me so I can debug