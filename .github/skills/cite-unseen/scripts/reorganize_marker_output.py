#!/usr/bin/env python3
"""Reorganize marker_single output into the canonical per-paper layout.

Given a paper that has just been extracted with::

    marker_single PAPERS_DIR/PAPER_NAME.pdf \
      --output_dir processed/PAPER_NAME/_marker_out/ \
      --force_ocr --paginate_output

this script moves the produced files into the final layout and rewrites image
references in the markdown so they point at the ``images/`` subdirectory:

    processed/{paper_name}/
    ├── paper.md          # was _marker_out/{paper_name}/{paper_name}.md
    ├── images/           # was _marker_out/{paper_name}/*.{jpeg,png}
    └── page-images/      # produced here via pdftoppm

Finally, it renders the source PDF as 150 DPI page PNGs into ``page-images/``
using ``pdftoppm``.

Pure, deterministic plumbing — no LLM judgment involved.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

IMAGE_SUFFIXES = {".jpeg", ".jpg", ".png"}


def fail(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def rewrite_image_refs(md_text: str, image_filenames: set[str]) -> tuple[str, int]:
    """Rewrite ``![alt](foo.jpeg)`` to ``![alt](images/foo.jpeg)`` when the
    referenced file is one of the extracted images.

    Only rewrites references whose target is a bare filename present in
    ``image_filenames`` and not already prefixed with a directory. Leaves URLs,
    already-prefixed paths, and unknown references untouched.

    Returns the new text and a count of rewrites.
    """
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        alt, target = match.group(1), match.group(2)
        # Leave URLs and anything with a path separator alone.
        if "/" in target or target.startswith(("http://", "https://", "data:")):
            return match.group(0)
        if target in image_filenames:
            count += 1
            return f"![{alt}](images/{target})"
        return match.group(0)

    pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    return pattern.sub(repl, md_text), count


def reorganize(paper_name: str, papers_dir: Path, processed_dir: Path) -> None:
    out_dir = processed_dir / paper_name
    marker_staging = out_dir / "_marker_out" / paper_name
    if not marker_staging.is_dir():
        fail(f"marker staging dir not found: {marker_staging}")

    src_md = marker_staging / f"{paper_name}.md"
    if not src_md.is_file():
        fail(f"expected markdown not found: {src_md}")

    # Collect images before moving.
    image_files = [
        p for p in marker_staging.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES
    ]
    image_names = {p.name for p in image_files}

    # Move images.
    images_dir = out_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    for img in image_files:
        shutil.move(str(img), str(images_dir / img.name))

    # Rewrite and move markdown.
    md_text = src_md.read_text(encoding="utf-8")
    new_text, rewrites = rewrite_image_refs(md_text, image_names)
    dest_md = out_dir / "paper.md"
    dest_md.write_text(new_text, encoding="utf-8")
    src_md.unlink()

    # Clean up marker staging dir.
    shutil.rmtree(out_dir / "_marker_out", ignore_errors=True)

    # Render page images.
    pdf_path = papers_dir / f"{paper_name}.pdf"
    if not pdf_path.is_file():
        fail(f"source PDF not found: {pdf_path}")

    page_images_dir = out_dir / "page-images"
    page_images_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "pdftoppm",
            "-png",
            "-r",
            "150",
            str(pdf_path),
            str(page_images_dir / "page"),
        ],
        check=True,
    )
    page_count = sum(1 for _ in page_images_dir.glob("page-*.png"))

    print(
        f"ok: paper={paper_name} images={len(image_files)} "
        f"image_refs_rewritten={rewrites} pages={page_count}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paper_name", help="Filename stem (without .pdf)")
    ap.add_argument(
        "--papers-dir",
        default="papers",
        type=Path,
        help="Directory containing source PDFs (default: papers)",
    )
    ap.add_argument(
        "--processed-dir",
        default="processed",
        type=Path,
        help="Directory containing per-paper output dirs (default: processed)",
    )
    args = ap.parse_args()
    reorganize(args.paper_name, args.papers_dir, args.processed_dir)


if __name__ == "__main__":
    main()
