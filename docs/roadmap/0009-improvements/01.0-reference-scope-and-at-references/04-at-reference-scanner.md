# Task 04 — `AtReference` recognition in the shared scanner

**Parent story:** [Story 01.0](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/README.md)  
**Role:** Python Expert  
**Depends on:** Task 02 (threat model), Task 03 (no code dependency, but serial edits).

## Inputs

- Story README "At-reference grammar" (normative, including the examples block and amendment A2).
- [Threat model](/docs/security/threat-model-0009-at-references-2026-11-14.md) (standing input):
  M8, M12, M13 and M19, and amendment A2.
- `/src/docsentinel/markdown_blocks.py`: `scan_markdown()`, `_mask_line()`, the inline-link and
  reference-use finders, `InlineCode`, `MarkdownSpan`, `MarkdownBlockIndex`.
- `/docs/dev/markdown_scanner.md` and `/docs/dev/markdown_dialect.md` for scanner conventions.

## Steps

1. Add the frozen dataclass `AtReference(target, raw, kind, in_code_span, span)` and the defaulted
   field `at_references: tuple[AtReference, ...] = ()` on `MarkdownBlockIndex`.
2. Prose form: walk each non-fenced line's masked text (code spans and comments already masked).
   Recognise an `@` only at line start or after whitespace or one of the four opening characters
   named in the grammar; reject after a backslash, letter, digit or `@`. Consume the token with a
   hand-written loop or a fixed, linear regex (no pattern built from input). A backslash followed
   by anything other than a space ends the token. Cap at 1,024 raw characters as written, each
   escaped space counting as two (an over-long run is not recognised, and scanning resumes after
   the end of that run, not at the next character). Strip trailing punctuation. Reject a token
   that starts or ends with an escaped space (checked after the strip). Skip tokens whose `@`
   falls inside an inline link or image span (text or destination), a reference-use label, or a
   raw HTML tag on that line.
3. Code-span form: for each `InlineCode` whose trimmed text is `@` plus one token that consumes
   the whole span, record a mention with `in_code_span=True` and the span's position.
4. Keep only tokens whose last component has an extension containing a letter. Decode escaped
   spaces in `target` by replacing exactly each two-character backslash-space sequence with one
   space, once, as a literal string operation (no `unicode_escape`, regex substitution or
   `html.unescape()`); keep `raw` exactly as written. Classify `kind` by the first character(s).
5. No logging inside the per-line loop (logging spec section 4); no filesystem access; no config
   access.
6. Docstrings in the module's style; mention that DS124 and DS116 are the consumers.

## Files

`/src/docsentinel/markdown_blocks.py` only.

## Verification

- test_at_reference_grammar.py in the unit tests folder covers every row of the examples block,
  each rejection rule, columns and lines, the cap, and that existing scanner fields are unchanged
  for documents without mentions (equality of the index minus the new field).
- A timing guard: a 1 MB line of repeated `@a` stays linear (op-count or time bound, matching the
  existing scanner timing tests).
- ruff and style check clean.

## Acceptance

- [ ] All grammar examples behave as specified.
- [ ] Scanner output for every existing fixture is unchanged except the new field.
- [ ] No new import outside the standard library.
