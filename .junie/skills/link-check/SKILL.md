---
name: link-check
description: Validate relative documentation links and Markdown heading anchors after documentation edits, moves, splits, merges, or renames.
---

# Link check

Use supplied paths or, when omitted, repository documentation, root Markdown, and `.junie/`
Markdown. This is the outbound check; run `doc-xref` for inbound references after a rename.

For every Markdown link outside fenced code:

1. Ignore external HTTP(S) and mail links.
2. Resolve relative file targets from the source file and report missing targets at `file:line`.
3. For Markdown fragments, compute target headings by lowercasing, removing punctuation other than
   word characters and hyphens, and replacing each whitespace character with `-`. Preserve repeated
   hyphens and suffix duplicate headings `-1`, `-2`, etc. Include explicit HTML anchors.
4. Fix only high-confidence typos or moved targets. If several candidates are plausible, request a
   human decision; if the correct file exists elsewhere, fix the link rather than renaming the file.
5. Repeat until the scoped check is clean.

Report fixes and a clean/non-clean result. Identify intentionally unresolved planned links explicitly;
never present them as a clean pass.