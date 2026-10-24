"""Deterministic Markdown corpus generator for DocSentinel performance benchmarking.

Generates a reproducible tree of Markdown documents mixing headings, inline and
reference-style links, images, reference definitions, fenced code blocks and GFM
tables, so fast-profile scan timings are comparable across repeated runs and across
DocSentinel versions. The generator is standard-library only and fully deterministic:
the same ``--count`` always produces byte-identical files, so a benchmark can be
reproduced exactly. It writes documents only; it never scans or imports DocSentinel.

Example::

    python scripts/bench_corpus.py /tmp/corpus_500 --count 500
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional


def _document(index: int, count: int) -> str:
    """Return the deterministic Markdown body for one document.

    :param index: Zero-based document index.
    :param count: Total document count, used to keep cross-links in range.
    :returns: Markdown text mixing headings, links, an image, a reference definition,
        a fenced code block and a GFM table.
    """
    nxt = (index + 1) % count
    prv = (index - 1) % count
    return (
        f"# Document {index}\n\n"
        f"Intro paragraph for document {index} linking to [next]({nxt:05d}.md) and "
        f"[prev]({prv:05d}.md).\n\n"
        "## Section\n\n"
        f"See the [spec][ref-{index}] and the diagram ![diagram](img/diagram_{index % 10}.png).\n\n"
        f"[ref-{index}]: ./notes/note_{index % 7}.md\n\n"
        "### Code\n\n"
        "```python\n"
        f"value = {index}\n"
        "print(value)\n"
        "```\n\n"
        "### Table\n\n"
        "| name | value |\n"
        "| --- | --- |\n"
        f"| item{index} | {index} |\n"
        f"| other | {nxt} |\n"
    )


def generate(root: Path, count: int) -> int:
    """Write ``count`` deterministic Markdown documents under ``root``.

    :param root: Destination directory, created if missing.
    :param count: Number of documents to generate.
    :returns: The number of documents written.
    """
    root.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        (root / f"{index:05d}.md").write_text(_document(index, count), encoding="utf-8")
    return count


def main(argv: Optional[list[str]] = None) -> int:
    """Run the corpus generator command line.

    :param argv: Argument list; defaults to ``sys.argv[1:]`` when omitted.
    :returns: Process exit code (always 0 on success).
    """
    parser = argparse.ArgumentParser(description="Generate a deterministic Markdown corpus.")
    parser.add_argument("root", type=Path, help="Destination directory")
    parser.add_argument("--count", type=int, default=500, help="Number of documents to generate")
    args = parser.parse_args(argv)
    written = generate(args.root, args.count)
    print(f"wrote {written} documents to {args.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
