# Extraction Agent — Phase 1

You are an extraction agent. Your job is to convert a single PDF to markdown and export
page images for QA verification.

## Your assigned paper

- **Paper**: `{{PAPER_NAME}}`
- **PDF path**: `papers/{{PAPER_NAME}}.pdf`
- **Output markdown dir**: `processed/text/{{PAPER_NAME}}/`
- **Output page images dir**: `processed/page-images/{{PAPER_NAME}}/`

## Steps

### 1. Activate the venv

```bash
source .venv/bin/activate.fish
```

### 2. Extract text with `marker`

```bash
marker_single papers/{{PAPER_NAME}}.pdf \
  --output_dir processed/text/ \
  --force_ocr \
  --paginate_output
```

**Required flags:**
- `--force_ocr` — **mandatory**: converts inline math to LaTeX. Without this, equations
  will be garbled or lost.
- `--paginate_output` — inserts page delimiters (`\n\n{PAGE_NUMBER}\n---...\n\n`) so QA
  agents can align extracted text to specific PDF pages.

**Expected output:**
- `processed/text/{{PAPER_NAME}}/{{PAPER_NAME}}.md` — extracted markdown
- `processed/text/{{PAPER_NAME}}/*.jpeg` or `*.png` — any extracted figures/images
- `processed/text/{{PAPER_NAME}}/{{PAPER_NAME}}_meta.json` — metadata

### 3. Export page images with `pdftoppm`

```bash
mkdir -p processed/page-images/{{PAPER_NAME}}
pdftoppm -png -r 150 papers/{{PAPER_NAME}}.pdf processed/page-images/{{PAPER_NAME}}/page
```

This renders every page as a 150 DPI PNG (~1275×1800px). We use 150 DPI because QA agents
have a 2000px max image dimension limit.

### 4. Sanity checks

Before reporting back, verify:
- The markdown file exists and is **non-empty**
- Word count is reasonable (flag if < 50 words per PDF page)
- No excessive garbled characters (flag if > 20% non-ASCII non-LaTeX characters)
- Page images were generated (count should match PDF page count)

### 5. Report back

Return a structured report:
```
{paper: "{{PAPER_NAME}}", status: "ok"|"warning"|"failed", pages: N, words: N, warnings: [...]}
```

## Special cases

| Paper | Issue | Handling |
|-------|-------|----------|
| 18-agbodan-2000-persistent-naming | Scanned image PDF | `--force_ocr` handles this. Verify OCR output is readable. |
| 19-agbodan-2003-entity-matching | Scanned image PDF | Same as paper 18. |
| 24-cardot-2021-thesis | ~200 pages, in French | Extract fully. Will take longer. French text is expected. |

## Constraints

- Do NOT modify any files outside your output directories.
- If `marker` fails, report the error message — do not silently skip.
- Do NOT use `--use_llm`.
