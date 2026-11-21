# Task 01 — ADR for invoker selection and directory selectors

**Parent story:** [Story 02.0](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/README.md)  
**Role:** Architect  
**Depends on:** Story 03.0 complete (its ADR fixes the precedence chain this ADR builds on).

## Inputs

- Story README "Decisions", "Selector grammar", "Precedence"; plan C1, C5, C8 and decisions D8
  to D10.
- `/src/docsentinel/discovery.py`, `/src/docsentinel/engine.py` (`scan()` signature and the
  `link_root` pass-through pattern), `/src/docsentinel/cli.py`.

## Steps

1. Take the next free ADR number (expected 0006) and write a MADR record "Invoker include/exclude
   and directory selectors", status `Proposed`. Considered options for the value base: scan root
   (chosen), current directory, mixed (paths CWD-relative, globs root-relative). Considered options
   for merging: replace both, append both, include replaces and exclude appends (chosen). Give
   honest pros and cons, including that a CWD-relative value typed from a subdirectory will not
   match and is reported instead.
2. Specify the `scan()` keyword contract (types, `None` versus empty sequence, effect on an injected
   `Config`) and the matching table as the authoritative contract. Name the affected components
   (discovery, engine, CLI, library users, pre-commit users) and the migration path (none for glob
   patterns; literal patterns gain meaning).
3. List affected diagrams (`/docs/diagrams/component/overview/component-overview.puml`,
   `/docs/diagrams/sequence/config-layered-load/config-layered-load.puml`, and a new
   `sequence/scan-selection` diagram; `/docs/architecture/README.md` has no Mermaid diagram, only
   prose) and record a `diagram-creator` follow-up after the code lands; end with one
   `Diagram impact:` line.

## Files

- New ADR under `/docs/adr/`; `/docs/adr/README.md` index row.

## Verification

- `python scripts/check_doc_links.py docs/adr docs/roadmap` reports 0 problems.

## Acceptance

- [ ] ADR `Proposed`, options and consequences complete, contract unambiguous.
- [ ] Diagram follow-up recorded, no diagram source edited.
