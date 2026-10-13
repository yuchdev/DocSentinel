---
description: Audit the documentation corpus or propagate references after one document changes, iterating until links converge or human review is required.
allowPromptArgument: true
---

# Update documentation references

Optional target or mode: `$prompt`

With no target or `--scan`, audit Markdown in documentation, root files, and `.junie/`: inventory
existing files, find references to missing Markdown targets, and classify replacement candidates.
Apply only high-confidence link-target corrections through `docs-updater`, without changing link text
or prose. Write unresolved candidates to a review report under `docs/reviews/`, including source,
line, missing target, candidates, and required human decision. Recheck until clean or no automatic
progress remains.

With a target path, inspect its diff for removed and added headings. Build old-to-new heading and
anchor mappings, then use `doc-xref` to find stale inbound links, prose, docstrings, and comments.
Use `docs-updater` for Markdown and `python-expert` for reference-only code docstring/comment edits;
run those in parallel only when file scopes do not overlap. Also run `link-check` for outbound links.
Repeat the focused checks until no stale reference remains or the same unresolved findings recur.

Never guess between plausible targets or rewrite surrounding logic/prose beyond the listed stale
references. Report files touched, references fixed, specialist agents used, and human-review items.
Junie performs convergence in the current command run; it does not emulate Claude's delayed
`ScheduleWakeup` lifecycle.