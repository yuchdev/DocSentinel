# Task 02 - Contradiction-Candidate Analyzer (`DS301`)

**Story:** [02.0 - Fact-Contradiction Candidate Detector](README.md)
**Depends on:** [01 - Triple-extraction module](01-triple-extraction-module.md) (consumes `Claim`),
Milestone 0003 Story 01.0 (gating + `deep_support.load_pipeline`), Milestone 0001 Story 01.0
(`register_rule`, `ANALYZERS` keyed by code)

## Purpose

Turn the per-document `Claim` stream from Task 01 into cross-corpus contradiction *candidates*. When
the same subject has differing numeric or named-entity objects in **different** documents - "the
cache holds 100 entries" in one doc, "256 entries" in another - emit a single `warning` finding that
names both sides and explicitly frames it as a candidate for human review, never as a confirmed
contradiction.

## Decision this task implements (record precisely - do not improvise at implementation time)

1. **`DS301` is `warning`, never `error`.** A heuristic SVO extractor produces real false positives;
   a build-breaking `error` severity is forbidden for any `deep` rule (plan cross-cutting guideline).
   `Rule(code="DS301", profile="deep", title="Fact-contradiction candidate", description="Two
   documents make differing numeric or named-entity claims about the same subject.",
   severity="warning")`.
2. **Message is candidate-framed, not assertive.** The word "candidate" appears; the message states
   the disagreement as *possible*, names both documents and both raw claims, and never says "X is
   wrong" or "these contradict." Exact shape:
   `"candidate contradiction: subject '{raw_subject}' claimed as '{claim_a_object}' in {path_a} but '{claim_b_object}' in {path_b} - review to confirm"`.
3. **Comparison rule - when do two claims disagree?** Group claims by `(subject_key, predicate_key)`
   across documents. Within a group, two claims from **different** `path`s *disagree* when **either**:
   - their `object_numbers` are both non-empty and share **no** common value (a genuine numeric
     mismatch - `("100",)` vs `("256",)`), **or**
   - their `object_entities` are both non-empty and share no common value (`("ORG:acme",)` vs
     `("ORG:globex",)`).
   Claims where one side has no comparable payload (no numbers and no entities) are **not** compared -
   absence is not disagreement. Same-document pairs are never compared (intra-document phrasing
   variation is out of scope; this is a *cross-document* consistency check).
4. **One finding per disagreeing pair, deterministically attached.** To keep output stable and
   baseline fingerprints (Milestone 0001 Story 04.0 Task 02) reproducible, sort the two paths
   lexicographically and attach the single `Finding` to the **greater** path, with both paths named
   in the message. Do **not** emit two mirror-image findings for one disagreement - that would double
   every candidate and destabilize baselines.
5. **Deduplicate and order deterministically.** If the same `(subject_key, predicate_key, path_a,
   path_b, object_a, object_b)` disagreement is extracted more than once, emit it once. The returned
   tuple is sorted by `(path, subject_key, predicate_key)` so two runs on the same corpus and model
   version produce byte-identical findings.
6. **The pipeline loads exactly once per `detect` call.** `detect` calls
   `deep_support.load_pipeline()` once, threads it into every `extract_claims` call. It reads each
   `.md` document's content from disk via `root / document.path` (the same way `fast` detectors read
   content - `Document` carries only path/size), skipping non-`.md` documents.

## Known limitations (must appear verbatim-in-spirit in the module docstring)

This section is the `deep` analogue of Milestone 0001's path-detector exclusion-rule writeup - the
tradeoffs are documented, not hidden:
- **False positives** are expected: SVO extraction mis-parses; the same subject *string* can name
  two different real things in two docs; numbers in different units (`"500 ms"` vs `"0.5 s"`) read as
  a mismatch; intentionally version-specific or context-specific statements (two docs correctly
  describing two releases) look contradictory. `DS301` is a *candidate generator* feeding Story 03.0's
  `docs-reviewer` triage - it is not ground truth and must never be treated as such.
- **False negatives** are expected: paraphrase that defeats key normalization, pronoun or
  cross-sentence subjects (no coreference resolution), claims expressed without an extractable SVO
  triple, and disagreements in free prose rather than numbers/entities all slip through silently.
- **Not deterministic across model versions.** Output is stable only for the pinned `en_core_web_sm`
  version; an upgrade can add, drop, or change candidates. This is the documented departure from the
  deterministic-first premise, scoped to `deep`.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/detectors/contradictions.py` | Create |
| `tests/test_detectors_contradictions.py` | Create |

## Symbols / fields

`src/docsentinel/detectors/contradictions.py`:

| Symbol | Kind | Notes |
|--------|------|-------|
| `DS301` | module-level `Rule`, via `register_rule(Rule(...))` | Per Decision §1. Registered at import time (cheap - no spaCy import here). |
| `_disagree(a: Claim, b: Claim) -> bool` | function | The Decision §3 comparison rule. **Pure** - takes two `Claim`s, no model, no I/O - so the whole comparison matrix is unit-testable against hand-built `Claim`s with no model installed. |
| `_candidate_findings(claims: tuple[Claim, ...]) -> tuple[Finding, ...]` | function | Groups by `(subject_key, predicate_key)`, cross-document pairwise-compares via `_disagree`, builds deduplicated, deterministically-ordered `Finding`s per Decision §4-5. Pure (no model/I/O) - operates on already-extracted claims. |
| `detect(root: Path, documents: tuple[Document, ...]) -> tuple[Finding, ...]` | function, the `Analyzer` | Loads the pipeline once (`deep_support.load_pipeline()`), reads + extracts claims for each `.md` document (Task 01's `extract_claims`), concatenates, delegates to `_candidate_findings`. Registered into `ANALYZERS["DS301"]` in Task 03. |

## Tests (`tests/test_detectors_contradictions.py`)

Split into **model-free** tests (the bulk - exercise `_disagree`/`_candidate_findings` against
hand-built `Claim` objects, run in the default CI matrix) and **model-backed** `deep`-marked tests
(skipped without the model, per Task 01's marker):

Model-free (no model needed):
- `test_disagree_on_number_mismatch` - two `Claim`s, same subject/predicate, `object_numbers`
  `("100",)` vs `("256",)` → `_disagree` True.
- `test_no_disagree_on_shared_number` - overlapping numbers → False.
- `test_disagree_on_entity_mismatch` - `("ORG:acme",)` vs `("ORG:globex",)` → True.
- `test_no_disagree_when_one_side_has_no_payload` - one claim has neither numbers nor entities →
  never flagged.
- `test_same_document_pair_not_compared` - two disagreeing claims with the **same** `path` → no
  finding.
- `test_single_finding_attached_to_greater_path` - a disagreeing cross-doc pair yields exactly one
  `Finding`, on the lexicographically-greater path, message naming both.
- `test_findings_are_deduplicated_and_sorted` - duplicate disagreements collapse; output order is
  stable and sorted by `(path, subject_key, predicate_key)`.
- `test_message_is_candidate_framed` - message contains "candidate", both paths, both raw objects,
  and asserts nothing as fact.
- `test_ds301_registered_as_warning_deep` - `RULES["DS301"].profile == "deep"` and `.severity ==
  "warning"`.

Model-backed (`deep`-marked):
- `test_detect_end_to_end_number_contradiction` - two tmp `.md` files, one saying a cache holds 100
  entries, the other 256 → exactly one `DS301` finding.
- `test_detect_no_finding_when_consistent` - two docs with the same number → zero findings.
- `test_detect_skips_non_markdown` - a `.txt` document is not read.

## Success criteria

- [ ] `DS301` is `warning`; no code path can emit it at `error` - guarded by
      `test_ds301_registered_as_warning_deep`.
- [ ] Every emitted message contains the literal substring "candidate" and names both documents.
- [ ] `_disagree` and `_candidate_findings` are pure and fully covered by model-free tests, so the
      comparison logic is verified in the default CI matrix without the `deep` extra installed.
- [ ] A disagreeing cross-document pair yields exactly **one** finding (on the greater path), never
      two mirror-image findings - baseline fingerprints stay stable.
- [ ] The Known-limitations section is present in the module docstring, naming the false-positive,
      false-negative, and cross-model-version caveats.

## Constraints

- Full type annotations; no bare `except:`. Reading document content reuses the `OSError`/
  `UnicodeDecodeError` handling convention the `fast` detectors established (propagate, do not
  swallow); the model-load `RuntimeError` from `deep_support.load_pipeline` is allowed to propagate -
  a confirmed deep run that reached `detect` has already passed the Story 01.0 readiness gate, so a
  load failure here is a genuine error worth surfacing.
- No top-level `import spacy`/`import textacy` in this module - the only model contact is via
  `deep_support.load_pipeline` and Task 01's `extract_claims`, both called inside `detect`.
- Do not special-case any repo-specific subject, number, or filename - `DS301` is a generic OSS
  detector and cannot allowlist anyone's corpus (same rule as Milestone 0001's `DS103`).
