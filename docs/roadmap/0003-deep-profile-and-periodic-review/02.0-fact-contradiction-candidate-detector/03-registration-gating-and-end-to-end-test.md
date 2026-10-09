# Task 03 - Registration, Gating Integration & Corpus End-to-End Test

**Story:** [02.0 - Fact-Contradiction Candidate Detector](README.md)
**Depends on:** [01 - Triple-extraction module](01-triple-extraction-module.md),
[02 - Contradiction-candidate analyzer](02-contradiction-candidate-analyzer.md), Milestone 0003
Story 01.0 (all three tasks - opt-in gate, lazy-import boundary, `doctor`)

## Purpose

`DS301` registering itself only matters if `docsentinel.engine` imports its module, and the opt-in
gate from Story 01.0 only matters if `DS301` is the thing it gates. This task wires the detector into
the detectors package (so `import docsentinel.engine` registers `DS301` cheaply, without importing
spaCy), proves the full confirmed-`deep` chain end-to-end, proves the **unconfirmed** chain runs
nothing, and retires the last `deep`-is-empty wording in the architecture doc that is no longer
strictly true.

## Decision this task implements

1. **`DS301` registers at engine-import time, lazily.** `detectors/__init__.py` imports the
   `contradictions` submodule for its registration side effect, exactly like the `fast` detectors
   (Milestone 0001 Story 02.0 Task 04). This stays cheap because `contradictions` has no top-level
   spaCy import (Task 02 Constraints) - so `import docsentinel.engine` registers `DS301` even on a
   machine with no `deep` extra installed; the model only loads if a confirmed `deep` scan runs it.
2. **`ANALYZERS["DS301"] = contradictions.detect`** is written at the `contradictions` module level,
   next to the `register_rule(DS301)` call - the same self-contained pattern the `fast` detectors
   use. `detectors/__init__.py` only ensures the import happens.
3. **Gate ordering is exercised, not just asserted.** The end-to-end test confirms the Story 01.0
   gate sits *in front of* `DS301`: an unconfirmed `profile="deep"` run reads no documents through the
   model and emits the opt-in `pending` message; a deps-missing confirmed run emits the deps `pending`
   message; a confirmed-and-ready run actually produces candidates.
4. **The model loads once per scan** even with multiple documents - asserted by spying on
   `deep_support.load_pipeline`.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/detectors/__init__.py` | Modify - add `contradictions` to the side-effect import list |
| `src/docsentinel/engine.py` | No change expected (it already imports the `detectors` package per Milestone 0001 Story 02.0 Task 04); confirm, do not duplicate |
| `tests/test_deep_profile_end_to_end.py` | Create |
| `docs/architecture/README.md` | Modify - narrow, honest `deep` sentence (coordinate with Story 04.0 Task 02 so the two edits do not conflict) |

## Symbols / fields

`src/docsentinel/detectors/__init__.py`: extend the existing re-export so it reads
`from docsentinel.detectors import comments, contradictions, links, paths` with `contradictions`
added to `__all__`. No new symbols - the import's side effect (registering `DS301` + `ANALYZERS`
entry) is the whole point, same as the `fast` modules.

> Coordination note: `docs/architecture/README.md` is edited by both this task and Story 04.0
> Task 02. This task adds only the single factual sentence "the `deep` profile registers one
> detector, `DS301` (fact-contradiction candidates), which is opt-in and advisory"; Story 04.0
> Task 02 owns the fuller advisory/reliability paragraph. Whichever lands second must integrate,
> not overwrite - keep both edits to the same `deep` paragraph.

## Tests (`tests/test_deep_profile_end_to_end.py`)

Model-free gating tests (default CI matrix):
- `test_import_engine_registers_ds301_without_spacy` - stub spaCy/textacy out of `sys.modules`,
  `import docsentinel.engine`, assert `"DS301" in ANALYZERS` and `"DS301" in RULES` and that spaCy
  was never imported.
- `test_unconfirmed_deep_does_not_load_model` - `profile="deep"`, no confirmation; monkeypatch
  `deep_support.load_pipeline` to raise if called → scan returns zero findings, opt-in `pending`
  message, and `load_pipeline` was never called.
- `test_confirmed_deep_deps_missing_does_not_load_model` - confirmed, `deep_support.deep_ready`
  stubbed `False` → deps `pending` message, `load_pipeline` never called, no traceback.

Model-backed `deep`-marked tests (skipped without the model):
- `test_confirmed_ready_deep_reports_candidates` - a tmp corpus with a planted cross-document number
  contradiction, `Config(profile="deep", deep_confirm=True)` → exactly one `DS301` finding,
  `enabled_rules == ("DS301",)`, `notice` says a deep rule was evaluated (advisory wording per Story
  04.0), not "not implemented."
- `test_model_loaded_once_for_multi_document_corpus` - spy on `deep_support.load_pipeline`; a
  three-document confirmed deep scan calls it exactly once.
- `test_consistent_corpus_zero_candidates_but_evaluated_notice` - a consistent tmp corpus → zero
  findings, but `notice` reflects that `DS301` ran (honest empty result, not "nothing implemented").

## Success criteria

- [ ] `import docsentinel.engine` alone registers `DS301` in both `RULES` and `ANALYZERS`, with no
      spaCy import triggered - proven by `test_import_engine_registers_ds301_without_spacy`.
- [ ] The Story 01.0 opt-in gate provably sits in front of `DS301`: the model is never loaded for an
      unconfirmed or deps-missing deep run.
- [ ] The model loads exactly once per confirmed scan regardless of document count.
- [ ] A confirmed, consistent corpus produces zero findings with an "evaluated" notice - never the
      "not implemented" wording, which is no longer true for a confirmed, ready `deep` run.
- [ ] `docs/architecture/README.md`'s `deep` sentence is updated to the narrow factual statement
      (one detector, opt-in, advisory) without overclaiming reliability, and without conflicting with
      Story 04.0 Task 02's edit to the same paragraph.

## Constraints

- Full type annotations; no bare `except:`.
- Do not add a plugin-discovery mechanism for `DS301` - one more hardcoded import line in
  `detectors/__init__.py` is the right amount of machinery, consistent with Milestone 0001 Story 02.0
  Task 04's explicit decision against entry-point discovery.
- The default CI matrix (no `deep` extra) must stay fully green: every model-backed test is
  `deep`-marked and skipped when `deep_support.deep_ready()` is `False`; the gating/registration
  guarantees are all covered by model-free tests.
