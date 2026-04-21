# Extraction Agent — Phase 1

You are an extraction agent. Your job is to convert a single PDF to markdown and export
page images for QA verification.

## Your assigned paper

- **Paper**: `{{PAPER_NAME}}`
- **PDF path**: `{{PAPERS_DIR}}/{{PAPER_NAME}}.pdf`
- **Output dir**: `processed/{{PAPER_NAME}}/`

## Steps

### 1. Activate the venv

```bash
source .venv/bin/activate.fish   # skip if no .venv exists
```

### 2. Extract text with `marker`

```bash
marker_single {{PAPERS_DIR}}/{{PAPER_NAME}}.pdf \
  --output_dir processed/{{PAPER_NAME}}/_marker_out/ \
  --force_ocr \
  --paginate_output
```

**Required flags:**
- `--force_ocr` — **mandatory**: converts inline math to LaTeX. Without this, equations
  will be garbled or lost.
- `--paginate_output` — inserts page delimiters (`\n\n{PAGE_NUMBER}\n---...\n\n`) so QA
  agents can align extracted text to specific PDF pages.

**Expected output** (in `processed/{{PAPER_NAME}}/_marker_out/{{PAPER_NAME}}/`):
- `{{PAPER_NAME}}.md` — extracted markdown
- `*.jpeg` or `*.png` — any extracted figures/images
- `{{PAPER_NAME}}_meta.json` — metadata

### 3. Reorganize + render page images

Run the reorganize script. It moves `paper.md` into place, moves extracted images into
`images/`, rewrites `![](foo.jpeg)` references to `![](images/foo.jpeg)`, cleans up the
marker staging dir, and renders page PNGs at 150 DPI into `page-images/`:

```bash
python .github/skills/process-papers/scripts/reorganize_marker_output.py \
  {{PAPER_NAME}} --papers-dir {{PAPERS_DIR}}
```

The script prints a status line:
`ok: paper=... images=N image_refs_rewritten=N pages=N`

This is pure, deterministic plumbing — do **not** rewrite image references or move files
by hand.

### 4. Sanity checks

Before reporting back, verify:
- `processed/{{PAPER_NAME}}/paper.md` exists and is **non-empty**
- Word count is reasonable (flag if < 50 words per PDF page)
- No excessive garbled characters (flag if > 20% non-ASCII non-LaTeX characters)
- Page images were generated in `processed/{{PAPER_NAME}}/page-images/`
  (count should match PDF page count)

### 5. Report back

Return a structured report:
```
{paper: "{{PAPER_NAME}}", status: "ok"|"warning"|"failed", pages: N, words: N, warnings: [...]}
```

## Notes

- Scanned image-only PDFs: `--force_ocr` handles OCR automatically. Verify the output
  is readable text, not empty or garbage.
- Non-English PDFs: extract fully. The text in the original language is expected.
  Summarization (a later phase) will handle translation.
- Very large documents (100+ pages): extraction will take longer. This is normal.

## Constraints

- Do NOT modify any files outside your output directories.
- If `marker` fails, report the error message — do not silently skip.
- Do NOT use `--use_llm`.
