---
name: docs-updater
description: Keep existing DocSentinel documentation synchronized with code and documentation changes. Use for updates, moves, splits, merges, and reference propagation, not net-new guides.
---

Update existing documentation to match actual behavior. First inspect the diff and identify every
user-, operator-, API-, and public-symbol surface affected. Preserve the existing tone, use readable
Markdown with language-tagged fences, relative links, and safe placeholders instead of secrets.

Treat documentation as a reference graph. Before changing a path, heading, or summarized section,
use `doc-xref` to find inbound references in docs, root Markdown, code docstrings, comments, and
tests. Update all affected references in the same change, including GitHub-style anchors and the
`docs/README.md` index. Refresh API/OpenAPI material when applicable and keep public docstrings in
the repository's required reStructuredText/Sphinx style.

Finish with the `link-check` skill or `python scripts/check_doc_links.py`. Report exactly which docs
changed, verify links and anchors resolve, and identify anything requiring subject-matter review.