# Task 05 — Diagram follow-up for the as-built DS302 architecture

**Parent story:** [Story 04.0](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/README.md)  
**Role:** Python Expert. This role reports the `Diagram impact:` line only. `app-architect` or the
orchestrator then invokes `diagram-creator`.  
**Depends on:** the code from Stories 03.0 and 05.0 is merged (this is the as-built rule in the plan's
[Diagrams](/docs/roadmap/0010-fact-check/plan.md#diagrams) section), and ADR 0007's diagram
follow-up list from Story 01.0 Task 01.

## Goal

Hand `diagram-creator` an exact, as-built list of the diagram changes. That keeps `/docs/diagrams/`
accurate now that the package has a new detector, two new mining-layer modules, a `fact_check/`
backend package behind a Protocol boundary, and its first outbound network edge (amended
2026-11-21 for the mining-layer decision, plan contract C9). This task edits no diagram source.

## Inputs

- The plan's [Diagrams](/docs/roadmap/0010-fact-check/plan.md#diagrams) section and the diagram
  follow-up in ADR 0007.
- `/docs/diagrams/README.md`
- `/docs/diagrams/component/detectors/component-detectors.puml`
- `/docs/diagrams/component/overview/component-overview.puml`
- every other `.puml` under `/docs/diagrams/`
- any Mermaid block in `/docs/architecture/README.md`
- The merged source:
  - `src/docsentinel/detectors/fact_check.py` (`DS302`, `select_candidates`, `CandidateClaim`)
  - `src/docsentinel/mining/salience.py` and `src/docsentinel/mining/clustering.py` (mining layer)
  - `src/docsentinel/mining/claims.py`, `src/docsentinel/mining/nlp.py` and
    `src/docsentinel/mining/corpus.py` (the moved modules, as consumed by `DS302`)
  - `src/docsentinel/fact_check/protocol.py` and `src/docsentinel/fact_check/lenz.py` (backend
    package)
  - `engine.py` (forwarding of `use_external_api`, `pending`)
  - `rules.py` (`EXTERNAL_API_RULES`)
  - `cli.py` (flag, `doctor` line)

## Steps

1. Read each diagram source and confirm what it currently draws. Read the merged code. Do not
   describe the planned design from the plan.
2. List the affected diagrams:
   - `component-detectors.puml`: add `detectors/fact_check.py` to the deep detector group. Draw its
     dependency edges down into the mining layer: `mining/salience.py` and `mining/clustering.py`
     (new boxes, with `clustering` depending on `mining/corpus.py`'s vectorizer factory) and the
     `mining/claims.py`/`mining/nlp.py` reuse it shares with `DS301`. Draw the `FactCheckClient`
     Protocol boundary between `DS302` and the `fact_check/` package (`fact_check/protocol.py`,
     `fact_check/lenz.py`), outside both `detectors/` and `mining/`. No edge may point from
     `mining/` or `fact_check/` up into `detectors/`, `config` or `engine` (plan contract C9).
   - `component-overview.puml`: show the mining layer and the `fact_check/` package as components
     below the detectors, and add the first outbound network edge (`fact_check/lenz.py` to the
     external Lenz `/assess` service), labelled "opt-in: deep_confirm + --use-external-api + API key;
     advisory". Add the `use_external_api` invoker input that goes into `engine.scan`.
   - If the change that moved `corpus`/`claims`/`nlp` into `mining/` has not yet drawn the mining
     layer, say so in the line rather than folding that unrelated redraw into this one.
   - A possible new diagram, `sequence/ds302-fact-check-gate`, covering engine gate resolution, the
     `pending` entry, and the two fail-soft paths (closed gate, per-claim `FactCheckError`). Include it
     only if ADR 0007 asks for it, or if the reviewer judges that the component views cannot show the
     gate. ADR 0007 ("Diagram follow-up") asks for it; it also shows the Q1 evaluated-count
     adjustment and the Q3 time-budget and Q4 unrecognised-verdict fail-soft paths.
   - Story 05.0 (`extract-facts`, plan contract C11), from its merged code:
     - `component-overview.puml`: the `extract-facts` CLI subcommand calling
       `engine.extract_facts`, with no network edge.
     - `component-detectors.puml`: `trace_candidates`/`collect_candidates` as the one candidate
       source, called by `DS302` `detect()` and by `engine.extract_facts`.
     - `component-reporting.puml`: `telemetry/facts_model.py`, the `facts-text`/`facts-json`
       templates, the loader's `context` kind and `reporting.render_facts`.
     - `scan-selection.puml`: the inventory step is now shared by `scan()` and `extract_facts()`,
       so relabel it.
     - Possibly a new `sequence/extract-facts`, if the reviewer judges the component views
       insufficient.
   - Confirm `config-layered-load.puml` is not affected. The six keys do not change layering. If
     you find an effect, add it to the list.
3. Report exactly one line to the caller:
   `Diagram impact: <paths, or "new: sequence/ds302-fact-check-gate"> -> <what changes>`.
   Give the ADR path and the code paths listed above.

## Deliverables

- The `Diagram impact:` line in the task's final report, and nothing else. `diagram-creator`
  re-renders the `.svg`/`.png` files and updates `/docs/diagrams/README.md`.

## Acceptance criteria

- [ ] The line is reported only after the Story 03.0 code is merged, and it describes the as-built code.
- [ ] It names every affected diagram, or justifies why a diagram is unaffected.
- [ ] No diagram source is edited by this task.

## Test expectations

- After `diagram-creator` runs, its validation passes and
  `python scripts/check_doc_links.py docs/diagrams docs/architecture` reports 0 problems.

## Out of scope

- Drawing or rendering diagrams.
- Diagram changes for a second backend.
