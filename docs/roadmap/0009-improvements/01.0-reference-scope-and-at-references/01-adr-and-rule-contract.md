# Task 01 — ADR for reference scope and DS124; `Rule.opt_in_values` contract

**Parent story:** [Story 01.0](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/README.md)  
**Role:** Architect  
**Depends on:** nothing; first task of the milestone.

## Inputs

- Story README sections "Decisions", "At-reference grammar", "Resolution (DS124)", "DS124 rule
  contract" and plan contracts C2, C3, C4.
- `/src/docsentinel/rules.py` (`Rule`, `opt_in_satisfied()`), `/src/docsentinel/engine.py`
  (`evaluated_notice()`, the rule-plan warning), `/src/docsentinel/cli.py` (the opt-in suffix and
  the `doctor` counts), `/src/docsentinel/markdown_blocks.py` (`MarkdownBlockIndex`,
  `resolve_local_reference()`).
- Existing ADRs in `/docs/adr/` and the template `/docs/adr/template.md`.

## Steps

1. Take the next free ADR number (expected 0004) and write a MADR record titled "Reference scope
   and @-document references", status `Proposed`. Considered options at least: (a) DS103 off by
   default via `reference_scope` plus new DS124 (chosen); (b) keep DS103 on and tune its heuristics;
   (c) a boolean `check_code_span_paths`; (d) fold mentions into DS101. Give pros and cons for each.
2. Specify the `Rule.opt_in_values` contract exactly as plan C2, including the rendering rule
   (`option = "value"` with the single sorted enabling value; several values join with " or ") and
   the byte-identity requirement for the four existing opt-in rules.
3. Specify the `AtReference` record and the `MarkdownBlockIndex.at_references` field as additive,
   defaulted fields; name every consumer (DS124, DS116, DS103) and the migration path (none needed
   for library callers; baselines see Task 07).
4. Record the rule-code reservation DS124 and the fault class `dangling_reference`.
5. List the affected diagrams: check `/docs/diagrams/README.md` and every diagram source under
   `/docs/diagrams/`, plus Mermaid diagrams in `/docs/architecture/README.md`. Because the code is
   not built yet, record a follow-up for `diagram-creator` (new detector module, scanner record,
   DS116 input) instead of editing diagrams, and end the ADR hand-off with one
   `Diagram impact:` line.
6. Add follow-up rows for the Python Expert and Testing Expert tasks of this story to the ADR's
   rollout section, by link.

## Files

- New ADR under `/docs/adr/` (next free number, kebab-case title).
- `/docs/adr/README.md` index row.

## Verification

- `python scripts/check_doc_links.py docs/adr docs/roadmap` reports 0 problems.
- The ADR names every component touched by the contract change and the migration path.

## Acceptance

- [ ] ADR exists, status `Proposed`, MADR sections complete, options with honest trade-offs.
- [ ] `Rule.opt_in_values`, `opt_in_satisfied()` semantics and rendering are specified without
      ambiguity.
- [ ] Diagram follow-up recorded; no diagram source edited.
