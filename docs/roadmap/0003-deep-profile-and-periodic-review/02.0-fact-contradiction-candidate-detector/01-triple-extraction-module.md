# Task 01 - Triple-Extraction Module

**Story:** [02.0 - Fact-Contradiction Candidate Detector](README.md)
**Depends on:** Milestone 0003 Story 01.0 Task 02 (the `deep_support.load_pipeline` lazy loader and
the no-eager-import boundary this module lives behind)

## Purpose

`DS301` (Task 02) needs `(subject, predicate, object)` triples per paragraph to compare across the
corpus. This task isolates all spaCy/textacy contact into one module that turns a document's text
into a list of normalized claims, with the heavy libraries loaded lazily through Story 01.0's
`deep_support.load_pipeline`. Keeping extraction separate from the comparison logic (Task 02) means
the model-touching surface is small, independently testable, and the comparison can be unit-tested
against hand-built triples without a model.

## What a "claim" is

A `Claim` is one extracted triple plus where it came from and a normalized form for cross-document
matching. The normalization is what makes two phrasings of the same fact collide (so a
contradiction can be spotted) while keeping the raw text for the human-readable message.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/detectors/_triples.py` | Create |
| `tests/test_detectors_triples.py` | Create |

## Symbols / fields

`src/docsentinel/detectors/_triples.py`:

| Symbol | Kind | Signature / fields | Notes |
|--------|------|--------------------|-------|
| `Claim` | `@dataclass(frozen=True)` | `subject_key: str`, `predicate_key: str`, `raw_subject: str`, `raw_object: str`, `raw_sentence: str`, `object_numbers: tuple[str, ...]`, `object_entities: tuple[str, ...]`, `path: str`, `paragraph_index: int` | Frozen, like every model in this codebase. `*_key` fields are the normalized match keys; `raw_*` fields are verbatim for messages. `object_numbers`/`object_entities` are the comparable payload Task 02 diffs. |
| `_normalize_key(text: str) -> str` | function | - | Lowercase, strip surrounding punctuation/articles (`a`/`an`/`the`), collapse internal whitespace, lemmatize head tokens via the pipeline. Deterministic for a fixed model version. |
| `_object_numbers(span) -> tuple[str, ...]` | function | - | Extract numeric tokens from the object span (digits and `like_num` tokens), normalized (e.g. `"1,024"` → `"1024"`, spelled-out `"ten"` → `"10"` where spaCy tags `like_num`). |
| `_object_entities(span) -> tuple[str, ...]` | function | - | Named entities inside the object span, as `(label, normalized_text)` joined strings (e.g. `"ORG:acme"`), restricted to the entity types worth comparing (`ORG`, `PRODUCT`, `GPE`, `PERSON`, `CARDINAL`, `QUANTITY`, `PERCENT`, `DATE`) - documented as a closed list so the comparison surface is predictable. |
| `extract_claims(pipeline, text: str, path: str) -> tuple[Claim, ...]` | function | - | Split `text` into paragraphs (blank-line separated, matching the project's paragraph notion), run the pipeline per paragraph, pull SVO triples via `textacy.extract.subject_verb_object_triples`, build one `Claim` per triple with `paragraph_index` set. `pipeline` is the already-loaded spaCy `Language` passed in by Task 02 (this function never loads it - the caller does, once per scan, via `deep_support.load_pipeline`). |

## Decision

- **The pipeline is loaded once per scan and threaded in**, not loaded per document - model load is
  the expensive step. `extract_claims` takes an already-loaded `pipeline`; Task 02 calls
  `deep_support.load_pipeline()` exactly once and reuses it across every document.
- **Paragraph granularity**, not whole-document: a `paragraph_index` lets Task 02's message point a
  reviewer near the claim, and keeps subjects from colliding across unrelated sections as readily as
  a document-level bag would.
- **Determinism caveat is explicit:** extraction is deterministic *only for a pinned model version*.
  The module docstring must state that `en_core_web_sm`'s version is the hidden input, and that a
  model upgrade can change `Claim` output - this is the documented point where `deep` departs from
  the "explainable from inputs alone" rule every `fast`/`standard` detector obeys.

## Tests (`tests/test_detectors_triples.py`)

These require the `deep` extra + model, so mark them (see Constraints) - they are skipped when the
model is absent, exactly like Canonix Engine's `local_engine`-marked tests skip without Argos models.
- `test_extract_claims_simple_svo` - `"The cache holds 100 entries."` yields one `Claim` with
  `subject_key` normalizing "the cache" → "cache", and `object_numbers` containing `"100"`.
- `test_number_normalization` - `"1,024"` and `"ten"` (where tagged `like_num`) normalize to
  `"1024"` / `"10"`.
- `test_entity_extraction_closed_list` - an object naming an `ORG` populates `object_entities`; an
  object naming an out-of-list entity type does not.
- `test_subject_key_ignores_articles_and_case` - `"The Cache"` and `"a cache"` produce the same
  `subject_key`.
- `test_paragraph_index_assigned` - two paragraphs, a claim in each, carry `paragraph_index` 0 and 1.
- `test_no_triples_yields_empty` - prose with no extractable SVO triple yields `()`, no error.

## Success criteria

- [ ] `extract_claims` never loads the model itself - it operates on the passed-in `pipeline`, so a
      scan loads the model exactly once (asserted in Task 03's end-to-end test).
- [ ] `subject_key`/`predicate_key` normalization makes two trivially-different phrasings of the same
      subject collide, proven by `test_subject_key_ignores_articles_and_case`.
- [ ] The comparable payload (`object_numbers`, `object_entities`) is built from the documented
      closed entity-label list only - no open-ended "any entity" extraction that would make the
      comparison surface unpredictable.
- [ ] The module docstring states the pinned-model-version determinism caveat.

## Constraints

- Full type annotations; no bare `except:`. The spaCy `Language` parameter/return types use string
  forward-references (no top-level `import spacy`), consistent with Story 01.0 Task 02's boundary.
- Register a `deep` pytest marker (in `pyproject.toml` `[tool.pytest.ini_options] markers` and/or
  `conftest.py`) that skips model-dependent tests when `deep_support.deep_ready()` is `False`, so the
  default CI matrix (no `deep` extra) stays green. Mirror the existing skip-without-assets pattern
  rather than inventing a new one.
- This module has **no** `Finding` surface and does not import `models.Finding` - it is pure
  extraction; emitting findings is Task 02's job.
