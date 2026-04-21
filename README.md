# cite-unseen

An agent skill that distills a directory of academic PDFs into agent-friendly
extracted text, per-figure descriptions, structured summaries, and a concept
index — so downstream agents can use the papers without re-processing PDFs at
query time.

The skill itself lives at
[.github/skills/cite-unseen/SKILL.md](.github/skills/cite-unseen/SKILL.md) —
that file is the authoritative pipeline spec. This README only covers setup and
invocation.

## Repo layout

```
.
├── .github/skills/cite-unseen/   # the skill
├── papers/                       # input PDFs (gitignored)
└── processed/                    # generated artifacts (gitignored)
```

Drop PDFs into `papers/`; the skill populates `processed/`.

## Prerequisites

### `marker` (required)

Phase 1 extraction is driven by
[**marker**](https://github.com/datalab-to/marker) (`marker-pdf` on PyPI). The
pipeline calls `marker_single --force_ocr`; `--force_ocr` is **mandatory** so
inline math is emitted as LaTeX.

```bash
python -m venv .venv
.venv/bin/pip install marker-pdf
.venv/bin/marker_single --help   # sanity check
```

Marker downloads model weights on first run (cached under `~/.cache/`).

### Other dependencies

```bash
which pdftoppm || sudo apt-get install -y poppler-utils   # PDF → PNG page renders
```

```fish
source .venv/bin/activate.fish   # per-session, fish
```

- GPU with ~9.6 GB free VRAM recommended (CPU fallback works but is slow).
- `gemini-api-key` file at the repo root if subagents use Gemini. Gitignored.

## Usage

Invoke the skill from an agent that supports this repo's skills (Claude Code,
Copilot Chat with skills enabled, etc.). The skill accepts:

- **`papers_dir`** — defaults to `papers/`.
- **`papers`** — `all` (default), comma-separated filename stems, or a shell
  glob.

Examples:

```
Run the cite-unseen skill on all papers.

Run cite-unseen on papers matching 1?-*-2019-*.

Run cite-unseen on 01-kripac-1997-naming, 13-hoffmann-1993-erep.
```

Re-runs are idempotent — figures with an existing `.md` are skipped; delete the
`.md` to force regeneration.

## Consuming the output

1. `processed/INDEX.md` — concept routing + paper directory.
2. `processed/<paper>/summary.md` — decide relevance.
3. `processed/<paper>/paper.md` + `figures/` — full details.
4. `processed/<paper>/qa.md` — only if extraction quality is in doubt.

## License

[MIT](LICENSE). Covers the skill code in this repo only — it does not grant
any rights to the source PDFs in `papers/` or their extracted derivatives in
`processed/`
