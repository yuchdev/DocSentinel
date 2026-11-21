# Task 08 — Documentation and release-notes proposal for reference scope and DS124

**Parent story:** [Story 01.0](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/README.md)  
**Role:** Docs Writer  
**Depends on:** Tasks 03 to 07 (code final, tests green).

## Inputs

- The `Docs impact:` lines from Tasks 03 and 05; story README "Docs to update" and "Migration and
  release".
- `/docs/dev/documentation_sync.md` (triggers R, C, K, A).

## Steps

1. `/docs/user/reference/configuration.md`: new section "Reference scope options (DS103, DS124)"
   with `reference_scope` and `at_reference_extensions` in the page's per-option format (type,
   default, values, effect, example), plus summary-table rows.
2. `/docs/user/tutorial/cli.md`: fast-profile section notes DS103 is opt-in; document
   `--reference-scope`; a short "@-document mentions" subsection with the grammar summary, the two
   resolution steps and the escape hatches (backslash, fenced block); migration note.
3. `/docs/user/reference/rules.md`: verify the DS103 and DS124 rows and the profile summary match
   the code (the Python Expert wrote them; do not fork them).
4. `/docs/specs/finding-types.md` and `/docs/specs/fault-classes.md`: verify the DS124 rows; add a
   changelog line to finding-types.
5. `/docs/dev/markdown_scanner.md`: the `AtReference` record and which rule owns what (DS124
   missing, DS116 escape, DS103 skips `@`).
6. `/README.md`: rule list and configuration example; `/CLAUDE.md`: config, rules and detectors
   entries, the opt-in policy rules convention (DS103 via `reference_scope = "strict"`).
7. `/docs/architecture/README.md`: the new detector module and the scanner record; hand the
   `Diagram impact:` line from Task 01 to `diagram-creator` through the caller.
8. Propose a `/RELEASE_NOTES.json` entry for 1.3.0 (do not bump the version): behaviour change
   (DS103 opt-in), new DS124, new keys and flag, migration lines.
9. Run `python scripts/check_doc_links.py docs/` and fix anything it reports.

## Files

The documents named above. No source files.

## Verification

- Link check 0 problems; the rules-table drift test still passes.
- `uv run docsentinel scan . --format json` adds no finding in the edited documents.

## Acceptance

- [ ] Every document in the story's "Docs to update" list is current.
- [ ] Release-notes entry proposed, owner decision left open.
