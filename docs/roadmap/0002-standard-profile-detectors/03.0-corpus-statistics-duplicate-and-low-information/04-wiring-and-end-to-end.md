# Task 04 - Package Wiring, Corpus-Model Caching & End-to-End Test

**Story:** [03.0 - Corpus Statistics](README.md)
**Depends on:** [01 - Shared corpus module](01-shared-corpus-module.md),
[02 - Duplicate detector](02-duplicate-text-detector.md),
[03 - Low-information detector](03-low-information-detector.md)

## Purpose

Register `DS202` and `DS203` into the lazily-loaded `standard` subpackage, resolve the one
cross-detector efficiency problem their independence creates (each calls `build_corpus_model`, so a
scan running both fits TF-IDF twice), and prove the whole corpus-statistics chain end-to-end.

## Decision this task implements - per-scan corpus-model caching

`DS202.detect` and `DS203.detect` each call `build_corpus_model(root, documents)`. In a single
`standard` scan both run, so the (expensive) TF-IDF fit happens twice over the same corpus. Options:

- **A. Leave it.** Two fits per scan. Simple, but wasteful and worsens the O(n²) duplicate pass's
  constant factor.
- **B. Memoize `build_corpus_model` on `(root, documents)`** with a small cache keyed by the
  `documents` tuple identity/content. The `Document` tuple is already hashable (frozen dataclasses),
  so an `functools.lru_cache(maxsize=1)` keyed on `(root, documents)` would collapse the two calls in
  one scan into one fit, while a different corpus (next scan) evicts the single entry.
- **C. Thread a prebuilt model through the engine.** Have the engine build the model once and pass it
  to both detectors - but this needs a signature change to `Analyzer`, which Milestone 0001 froze.
  Rejected on those grounds.

**Chosen: B**, with `maxsize=1`. Rationale: it removes the double-fit with no `Analyzer` signature
change, `maxsize=1` bounds memory to the current corpus only (no leak across scans), and the cache
key is the already-hashable `documents` tuple plus `root`. Document the one caveat: `lru_cache`
caches across calls process-wide, so the model-isolation test fixture must clear it in teardown
(`build_corpus_model.cache_clear()`), the same global-state discipline used for `RULES`/`ANALYZERS`.
Keep the cache in `corpus.py` (decorate `build_corpus_model`); it is a corpus concern, not a detector
one.

> Note: this makes `build_corpus_model` cache on `documents` *identity/equality*. Because `Document`
> is a frozen dataclass of `(path, bytes)`, two scans of the same tree with unchanged files produce
> equal tuples and hit the cache; any file size change busts it. A content edit that leaves byte size
> identical (rare) would be a stale-cache risk **only within a single process that re-scans** - note
> this as an accepted, documented limitation (the CLI is one scan per process, so it never hits it).

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/detectors/standard/__init__.py` | Modify - add `duplication` and `low_information` imports |
| `src/docsentinel/detectors/standard/corpus.py` | Modify - memoize `build_corpus_model` (`lru_cache(maxsize=1)`) |
| `tests/test_standard_profile_end_to_end.py` | Modify - add DS202/DS203 corpus-wide cases |
| `tests/test_standard_corpus.py` | Modify - add cache behavior tests |
| `docs/architecture/README.md` | Modify - record DS202/DS203 |

## Symbols / fields

`src/docsentinel/detectors/standard/__init__.py` - after Story 02.0's line:

```python
from docsentinel.detectors.standard import complexity       # DS201 (Story 02.0)
from docsentinel.detectors.standard import duplication       # DS202 (Story 03.0)
from docsentinel.detectors.standard import low_information    # DS203 (Story 03.0)

__all__ = ["complexity", "duplication", "low_information"]
```

`corpus.py` - decorate `build_corpus_model` with `functools.lru_cache(maxsize=1)` (Decision above);
expose `build_corpus_model.cache_clear` implicitly (lru_cache provides it) for test teardown.

## Behavior change

- A `standard` scan with the extra installed now evaluates `DS201`, `DS202`, `DS203`; `enabled_rules`
  for a default `standard` scan becomes `("DS201", "DS202", "DS203")` (sorted), and `notice` reads
  "3 standard rule(s) evaluated".
- The TF-IDF corpus model is built once per scan even though two detectors consume it.

## Tests

`tests/test_standard_profile_end_to_end.py` additions (guard with `importorskip("sklearn")`):
- `test_standard_scan_reports_duplicate_and_low_info` - a `tmp_path` corpus containing (a) a
  paragraph duplicated across two files, (b) a filler paragraph, and (c) substantive distinct
  paragraphs → exactly one `DS202` and one `DS203` finding, each correctly attributed.
- `test_corpus_model_built_once_per_scan` - spy on `TfidfVectorizer.fit_transform`; a single
  `scan(..., profile="standard")` running both DS202 and DS203 triggers exactly **one** fit (proves
  the `lru_cache` collapses the two `build_corpus_model` calls). Clear the cache in setup so the spy
  count is meaningful.
- `test_standard_enabled_rules_are_all_three` - default `standard` scan reports
  `enabled_rules == ("DS201", "DS202", "DS203")` and the "3 ... evaluated" notice.
- `test_select_narrows_to_single_corpus_rule` - `Config(profile="standard", select=("DS202",))` runs
  only the duplicate detector; `DS201`/`DS203` do not appear in `enabled_rules`.

`tests/test_standard_corpus.py` additions:
- `test_build_corpus_model_is_cached_for_identical_inputs` - two calls with the same `(root,
  documents)` return the same cached object (identity) and fit once; clear the cache afterward.
- `test_cache_busts_on_changed_documents` - a different `documents` tuple (a file's `bytes` changed)
  produces a fresh fit.

## Docs updates

`docs/architecture/README.md`: add `DS202` (duplicated text/facts, `scikit-learn`, `warning`) and
`DS203` (low-information content, `scikit-learn`+`textstat`, `warning`) to the `standard`-profile
rule list, each one line. Note that these are the corpus-wide detectors (why `standard` exists) and
that `DS204` (code-reading) is still to come in Story 04.0.

## Success criteria

- [ ] A default `standard` scan evaluates all three of this-story-and-prior codes and builds the
      corpus model exactly once, proven by a fit-count test.
- [ ] `select`/`ignore` narrow the corpus detectors like any other rule (shared Milestone 0001
      resolver, no special-casing).
- [ ] The `lru_cache` is cleared in test teardown wherever a test asserts on fit counts or model
      identity - no cross-test cache leakage.

## Constraints

- Full type annotations; no bare `except:`.
- The cache is `maxsize=1` only (Decision) - do not grow it into an unbounded corpus cache that would
  leak memory across many scans in a long-lived process.
- Do not change the `Analyzer` signature to thread the model through the engine (rejected Option C) -
  the memoized `build_corpus_model` is the sanctioned sharing mechanism.
</content>
