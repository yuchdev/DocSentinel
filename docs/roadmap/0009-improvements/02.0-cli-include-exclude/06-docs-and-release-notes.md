# Task 06 — Documentation and release-notes proposal for CLI selection

**Parent story:** [Story 02.0](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/README.md)  
**Role:** Docs Writer  
**Depends on:** Tasks 03 to 05 (code final, tests green).

## Inputs

- `Docs impact:` lines from Tasks 03 and 04; story README "Docs to update".
- `/docs/dev/documentation_sync.md` (triggers C, K, P, A).

## Steps

1. `/docs/user/tutorial/cli.md`: section "Selecting files: --include and --exclude" with examples
   in a fenced block, the base (scan root), merge rules, the refused inputs and the warnings.
2. `/docs/user/reference/configuration.md`: a section for `include` and `exclude`: defaults,
   glob versus literal semantics, directory behaviour, exclude-wins; note the behaviour change for
   literal values (they now match directories).
3. `/docs/user/tutorial/library.md`: the `include` and `exclude` keywords of `scan()`.
4. `/README.md` CLI usage; `/CLAUDE.md` discovery and engine entries.
5. `/docs/architecture/README.md`: discovery paragraph; hand the Task 01 `Diagram impact:` line to
   `diagram-creator` through the caller.
6. Propose a `/RELEASE_NOTES.json` line (new flags and keywords; literal patterns now match
   directories).
7. Run `python scripts/check_doc_links.py docs/`.

## Files

The documents named above; no source files.

## Verification

- Link check 0 problems; self-scan adds no finding in the edited documents.

## Acceptance

- [ ] All listed documents current; release-notes line proposed.

## Amendment (ADR 0006, 2026-11-18)

- **Literal-pattern behaviour change.** The configuration reference and the release-notes line
  say that a literal `include`/`exclude` value (no `*`, `?` or `[`) now means "this file, or this
  directory and everything below it" (a directory include admits only `.md` files). Glob values
  are unchanged and give byte-identical results (owner ruling on O1); do not write a glob
  behaviour-change note.
- **Escaping `[`.** Document that a file name containing `*`, `?` or `[` cannot be selected as a
  literal and needs a glob that matches it, for example `notes[[]1].md`.
- The contract source is
  [ADR 0006](/docs/adr/0006-invoker-include-exclude-and-directory-selectors.md).
