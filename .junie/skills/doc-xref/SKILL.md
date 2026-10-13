---
name: doc-xref
description: Find and update inbound references to a documentation path, heading, anchor, or public symbol before a rename, move, split, deletion, or rewording.
---

# Documentation cross-reference sweep

Treat the supplied target as an old path, heading/anchor, or symbol. This skill handles inbound
references; use `link-check` afterward for outbound validity.

1. Derive exact variants worth searching: full path, basename, heading text, GitHub-style anchor,
   and symbol name. Do not rewrite unrelated bare mentions merely to make them searchable.
2. Search `docs/**`, root Markdown, `.junie/**`, `src/**`, and `tests/**`. Include Markdown links,
   prose, docstrings, and comments.
3. For a move or rename, update every unambiguous hit to the new relative path/anchor. Preserve file
   history when the task explicitly requires moving a tracked file. For a deleted section with no
   replacement, flag ambiguous references rather than guessing.
4. Update `docs/README.md` when indexed documents change.
5. Run `link-check` over changed documentation.

Return every updated `file:line` with old and new forms, and list references requiring human review.
Heading anchors are lowercase, punctuation removed, each whitespace replaced by `-`, with duplicate
headings suffixed `-1`, `-2`, and so on; do not incorrectly collapse meaningful double hyphens.