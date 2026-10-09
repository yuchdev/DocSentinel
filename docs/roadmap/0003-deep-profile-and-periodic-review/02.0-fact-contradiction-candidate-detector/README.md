# Story 02.0 - Fact-Contradiction Candidate Detector (`DS301`)

The first and only `deep` detector this milestone ships. It is corpus-wide (like a `standard`
duplication check, it receives the whole `documents` tuple and needs all of it), model-backed
(spaCy `en_core_web_sm` + textacy SVO extraction), and - unlike every `fast`/`standard` rule -
explicitly a **candidate generator**, not a verdict. It pulls `(subject, predicate, object)`
triples from every paragraph across the corpus, groups them by subject across *different*
documents, and when the same subject carries differing numeric or named-entity claims it emits a
`warning`-severity `Finding` whose message says "candidate contradiction" and names both sides.

False positives are expected and acceptable here - the output's consumer is the `docs-reviewer`
agent (Story 03.0) and a human, not a build gate (Story 04.0 keeps `deep` advisory-only). This
story's job is to produce a *useful, honest shortlist*, with its tradeoffs written down, not to be
right every time.

## Tasks

| # | Task | Rule | Output |
|---|------|------|--------|
| 01 | [Triple-extraction module](01-triple-extraction-module.md) | - | `src/docsentinel/detectors/_triples.py`: lazy pipeline + SVO extraction + claim normalization |
| 02 | [Contradiction-candidate analyzer](02-contradiction-candidate-analyzer.md) | `DS301` | `src/docsentinel/detectors/contradictions.py`: cross-doc comparison, finding emission, known limitations |
| 03 | [Registration, gating & corpus end-to-end test](03-registration-gating-and-end-to-end-test.md) | - | detectors-package wiring, Story 01.0 gate integration, deep-marked end-to-end test, docs refresh |

01 is a pure helper with no `Finding` surface; 02 consumes it and owns `DS301`; 03 wires it into
the package and proves the whole confirmed-`deep` chain end-to-end. All three depend on Story 01.0
(the opt-in gate and lazy-import boundary) being in place.
