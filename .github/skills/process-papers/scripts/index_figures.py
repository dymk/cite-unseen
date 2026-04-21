#!/usr/bin/env python3
"""Index figures in a paper by scanning ``paper.md`` for image references and
extracting surrounding context for each.

For a given paper, this script:

1. Lists image files under ``processed/{paper_name}/images/``.
2. Scans ``processed/{paper_name}/paper.md`` for every ``![alt](images/FOO)``
   reference and records the character span where FOO appears.
3. For each image file, extracts a window of ~CONTEXT_CHARS characters of
   surrounding markdown (centered on the first reference). If the image is
   never referenced, context is set to a standard placeholder string.
4. Writes ``processed/{paper_name}/figures/_index.json`` — one entry per image.

The orchestrator reads this JSON to dispatch per-figure subagents without ever
needing to load ``paper.md`` into its own context.

Pure, deterministic — no LLM involved.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

IMAGE_SUFFIXES = {".jpeg", ".jpg", ".png"}
CONTEXT_CHARS = 2000  # ~300-500 words
UNREFERENCED = "This figure was extracted but not referenced in markdown."

REF_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")

# Caption detection. Matches "Figure 1", "**Figure 1**", "Fig. 1.", "Figure 2a:", etc.
# at the start of a line (optionally after whitespace), with any of the common
# separators (`.`, `:`, whitespace) or end-of-line following.
CAPTION_PATTERN = re.compile(
    r"^\s*(?:\*\*)?(Fig(?:ure|\.)?)\s+(\d+[a-z]?)(?:\*\*)?[\s.:]+(.*?)$",
    re.MULTILINE | re.IGNORECASE,
)


def find_caption(
    md_text: str,
    ref_end: int,
    next_ref_start: int | None,
) -> tuple[str | None, str | None]:
    """Look for a figure caption in the text immediately following an image ref.

    We search only up to ``next_ref_start`` (or ~400 chars if no further image
    follows). This prevents a caption from being attributed to an earlier image
    when a later image sits between the two.

    Returns ``(label, caption)`` or ``(None, None)`` if no caption was found
    within the window. ``label`` is normalized to "Figure N" (or "Figure Na").
    ``caption`` is the text following the label on the same line, stripped.
    """
    search_end = (
        next_ref_start if next_ref_start is not None else min(len(md_text), ref_end + 400)
    )
    # Stop at the next image ref even if within our window.
    if next_ref_start is not None:
        search_end = min(search_end, next_ref_start)
    window = md_text[ref_end:search_end]

    m = CAPTION_PATTERN.search(window)
    if not m:
        return None, None

    number = m.group(2)
    caption_text = m.group(3).strip().rstrip("*").strip()
    # Drop trailing pure-markdown noise like "**" from bold wrappers.
    label = f"Figure {number}"
    return label, caption_text or None


def extract_context(md_text: str, start: int, end: int, window: int) -> str:
    """Extract ~`window` chars of context around a match, snapped to paragraph
    boundaries when convenient."""
    half = window // 2
    ctx_start = max(0, start - half)
    ctx_end = min(len(md_text), end + half)

    # Snap ctx_start BACKWARD to the previous paragraph boundary (within slack).
    # Search for "\n\n" before ctx_start — not between ctx_start and the match —
    # so we extend the window outward, not collapse it inward.
    slack = 200
    blank_before = md_text.rfind("\n\n", max(0, ctx_start - slack), ctx_start)
    if blank_before != -1:
        ctx_start = blank_before + 2

    # Snap ctx_end FORWARD to the next paragraph boundary (within slack).
    blank_after = md_text.find("\n\n", ctx_end, min(len(md_text), ctx_end + slack))
    if blank_after != -1:
        ctx_end = blank_after

    return md_text[ctx_start:ctx_end].strip()


def index_figures(paper_name: str, processed_dir: Path) -> None:
    paper_dir = processed_dir / paper_name
    md_path = paper_dir / "paper.md"
    images_dir = paper_dir / "images"
    figures_dir = paper_dir / "figures"

    if not md_path.is_file():
        raise SystemExit(f"error: {md_path} not found")
    if not images_dir.is_dir():
        # No images — write an empty index and exit.
        figures_dir.mkdir(parents=True, exist_ok=True)
        (figures_dir / "_index.json").write_text("[]\n", encoding="utf-8")
        print(f"ok: paper={paper_name} figures=0 (no images dir)")
        return

    md_text = md_path.read_text(encoding="utf-8")

    # Build a map of image target (as it appears in the markdown) -> list of
    # (start, end) spans. Also collect all ref end positions in document order
    # so we can bound caption search.
    refs: dict[str, list[tuple[int, int]]] = {}
    all_ref_positions: list[int] = []  # start positions of each image ref
    for m in REF_PATTERN.finditer(md_text):
        target = m.group(1).strip()
        # Normalize to the bare filename (strip any leading directory like
        # ``images/``).
        bare = target.rsplit("/", 1)[-1]
        refs.setdefault(bare, []).append((m.start(), m.end()))
        all_ref_positions.append(m.start())
    all_ref_positions.sort()

    image_files = sorted(
        p for p in images_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES
    )

    entries: list[dict[str, str | None]] = []
    referenced_count = 0
    labelled_count = 0
    for img in image_files:
        spans = refs.get(img.name, [])
        if spans:
            start, end = spans[0]
            context = extract_context(md_text, start, end, CONTEXT_CHARS)
            # Find the next image ref (if any) to bound caption search.
            next_ref = next(
                (pos for pos in all_ref_positions if pos > end), None
            )
            label, caption = find_caption(md_text, end, next_ref)
            if label is not None:
                labelled_count += 1
            referenced_count += 1
        else:
            context = UNREFERENCED
            label, caption = None, None
        entries.append(
            {
                "filename": img.name,
                "stem": img.stem,
                "label": label,
                "caption": caption,
                "context": context,
            }
        )

    figures_dir.mkdir(parents=True, exist_ok=True)
    index_path = figures_dir / "_index.json"
    index_path.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"ok: paper={paper_name} figures={len(entries)} "
        f"referenced={referenced_count} labelled={labelled_count} "
        f"unreferenced={len(entries) - referenced_count}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paper_name", help="Filename stem (without .pdf)")
    ap.add_argument(
        "--processed-dir",
        default="processed",
        type=Path,
        help="Directory containing per-paper output dirs (default: processed)",
    )
    args = ap.parse_args()
    index_figures(args.paper_name, args.processed_dir)


if __name__ == "__main__":
    main()
