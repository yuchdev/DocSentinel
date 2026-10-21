# Task 01 — shared stdlib Markdown block scanner and parser compatibility

**Do first:** verify whether M4's shared Markdown parsing/graph modules are already in master. Reuse them if present; only create `src/docsentinel/markdown_blocks.py` if not. Do not create two competing tokenizers.

1. Specify typed immutable heading/fence/comment/inline/reference/image/table tokens with **one-based original source line**. Preserve the current DS101 duplicate-anchor suffix behavior and DS102 fence/comment masking.
2. Build a scanner for the narrow supported GFM subset: ATX/setext headings, fenced blocks, inline backtick runs, HTML comments, reference definitions/uses, simple pipe tables, Markdown images plus basic HTML img/source tags. Avoid regex scans on rendered/untrusted HTML beyond the supported patterns.
3. Handle malformed fences conservatively so another rule does not parse swallowed body as active Markdown. Distinguish info-string and delimiter issues.
4. Provide isolated tests for CRLF, final newline absent, Unicode normalization, escaped delimiter, repeated headings, mixed backticks/tilde, long unmatched spans, HTML comments, and README subdirectory resolution.
5. All scanner APIs must use only stdlib imports. Add a test launching a subprocess in an environment without optional extras to prove `import docsentinel` and `scan fast` are unaffected.
6. Document supported Markdown dialect and intentional gaps, including inline HTML interpretation.

**Acceptance:** O(input length) normal scan, deterministic original source locations, compatibility to existing DS101/102/103 fixtures, no new heavyweight imports, no file I/O from tokenization itself.
