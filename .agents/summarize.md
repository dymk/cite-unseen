# Summarization Agent — Phase 5

You are a summarization agent. Your job is to read the extracted text of a single academic
paper and produce a structured summary for use by future coding agents.

## Your assigned paper

- **Paper**: `{{PAPER_NAME}}`
- **Extracted text**: `processed/text/{{PAPER_NAME}}/{{PAPER_NAME}}.md`
- **Figure descriptions**: `processed/figures/{{PAPER_NAME}}/` (one .md per figure)
- **Citation & relevance**: the row for this paper in `papers/INDEX.md`
- **QA report**: `processed/qa/{{PAPER_NAME}}-qa.md`
- **Summary output**: `processed/summaries/{{PAPER_NAME}}.md`

## Steps

### 1. Read inputs

- Read the extracted markdown (full text of the paper).
- Read any figure descriptions from `processed/figures/{{PAPER_NAME}}/`.
- Read the paper's row from `papers/INDEX.md` for the full citation and relevance hint.
- Read the QA report to be aware of any known quality issues.

### 2. Write the summary

Produce `processed/summaries/{{PAPER_NAME}}.md` with **200–400 words** containing these
sections:

```markdown
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
[List figure numbers + page numbers worth revisiting. Incorporate insights from the
figure descriptions in processed/figures/ if available.]

## Relationship to Other Papers
[Which papers in this collection it builds on, contradicts, or extends — use the NN
numbers from INDEX.md]
```

## Guidelines

- Be precise and technical. These summaries are for an AI coding agent, not a general
  audience.
- For "Relationship to Other Papers", only reference papers that are in this collection
  (01–25). Use the NN number format.
- For "Key Figures", include page numbers so a future agent knows where to look in the
  page images.
- If the QA report flagged issues with certain sections, note reduced confidence in
  those areas.

## Special case

- **24-cardot-2021-thesis**: The paper is in French. Read the French text and write the
  summary in **English**.

## Constraints

- Only write to the summary output path for your assigned paper.
- Do NOT modify any other files.
