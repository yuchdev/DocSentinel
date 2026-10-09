# Task 02 - Duplicate-Text Detector (`DS202`)

**Story:** [03.0 - Corpus Statistics](README.md)
**Depends on:** [01 - Shared corpus vectorizer & chunking](01-shared-corpus-module.md)

## Purpose

Covers `CLAUDE.md`'s "duplicated text and facts" requirement: find paragraph pairs across the whole
corpus whose TF-IDF cosine similarity is high enough to be a near-duplicate - copy-pasted boilerplate,
a fact restated verbatim in two docs, a section cloned and lightly edited. Exact-duplicate detection
is trivial (hash the text); the value here is catching *near*-duplicates, which is why TF-IDF cosine,
not string equality, is the mechanism.

## Decision this task implements

1. **Corpus-wide pairwise cosine on the shared `CorpusModel`.** Use
   `sklearn.metrics.pairwise.cosine_similarity` on `CorpusModel.matrix` (or the equivalent sparse
   dot product, since TF-IDF rows are L2-normalized). This is the detector the `Analyzer`
   full-`documents`-tuple signature exists for: it needs every chunk at once.
2. **Similarity threshold: default `0.85` (cosine), configurable via `Config.duplicate_similarity`.**
   Justification: with English stop-words removed and `sublinear_tf=True` (Task 01's fixed
   vectorizer), two genuinely distinct technical paragraphs rarely exceed ~0.7 cosine, while
   near-identical boilerplate and copy-pasted facts sit at 0.9+. `0.85` is the knee that catches
   real duplication while leaving normal topical overlap (two paragraphs both about "the scan
   engine") below the line. It is `warning` severity precisely because this is a tuned heuristic:
   `0.85` will occasionally over- or under-fire, so it must not break a build by default, and it is
   configurable for projects whose corpus runs hotter or colder.
3. **Report each duplicate *pair* once.** Enumerate only `i < j` pairs above threshold. Attribute
   the finding to the **later** chunk (`chunks[j]`, the "copy"), with a message naming the earlier
   chunk (`chunks[i]`, the "original") and the similarity score. This avoids two symmetric findings
   for one duplication and gives a stable "fix the newer copy" framing. Message shape:
   `f"near-duplicate of {chunks[i].path}#chunk{chunks[i].index} (cosine {sim:.2f}): '{chunks[j].preview}'"`.
4. **Within-document duplication counts.** Two near-identical paragraphs in the *same* file are still
   a `DS202` finding (an accidental copy-paste within one doc is as real as one across docs). Do not
   special-case same-path pairs.
5. **Short chunks already excluded.** The `_MIN_CHUNK_WORDS` floor lives in Task 01's `iter_chunks`,
   so `DS202` never considers trivially-short chunks and needs no second guard.
6. **Complexity bound is acceptable.** Pairwise similarity is O(n²) in chunk count. For this
   milestone's corpus sizes (hundreds-to-low-thousands of chunks) a single `cosine_similarity` call
   on a sparse matrix is fine. Note the quadratic bound as a documented scaling limitation (a future
   milestone could switch to approximate nearest neighbors if a corpus ever makes it a problem);
   do **not** pre-optimize it now.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/detectors/standard/duplication.py` | Create |
| `src/docsentinel/config.py` | Modify - add `Config.duplicate_similarity` + validation |
| `tests/test_detectors_duplication.py` | Create |
| `tests/test_config.py` | Modify - `duplicate_similarity` validation tests |

## Symbols / fields

`src/docsentinel/detectors/standard/duplication.py`:

| Symbol | Kind | Notes |
|--------|------|-------|
| `DS202` | module-level `Rule` via `register_rule(...)` | `Rule(code="DS202", profile="standard", title="Duplicated text or facts", description="A paragraph is a near-duplicate of another paragraph in the corpus.", severity="warning")`. |
| `duplicate_pairs(model: CorpusModel, threshold: float) -> tuple[tuple[int, int, float], ...]` | function | Returns `(i, j, similarity)` for every `i < j` with cosine ≥ `threshold`, sorted by `(i, j)`. Pure over the model + threshold - unit-testable without disk or config. Returns `()` for an empty/single-chunk model. |
| `detect(root: Path, documents: tuple[Document, ...]) -> tuple[Finding, ...]` | function, `ANALYZERS["DS202"]` | Reads `duplicate_similarity` via `load_config(root)` (same config-access note as `DS201` Task 01); calls `build_corpus_model(root, documents)`; calls `duplicate_pairs`; maps each pair to a `Finding(rule="DS202", path=chunks[j].path, ...)`. |

`src/docsentinel/config.py`:

| Symbol | Change |
|--------|--------|
| `Config.duplicate_similarity: float = 0.85` | New field. |
| validation | Must be a number in the closed interval `[0.0, 1.0]` (cosine of L2-normalized non-negative TF-IDF vectors is in `[0, 1]`); not a `bool`; else `ConfigError("duplicate_similarity must be a number between 0 and 1")`. |

## Validators (raise `ConfigError`)

- `duplicate_similarity` outside `[0, 1]`, or not a number, or a `bool` → `ConfigError`.

## Tests (`tests/test_detectors_duplication.py`)

Guard with `importorskip("sklearn")`.

- `test_identical_paragraphs_in_two_docs_are_flagged` - the same paragraph in `a.md` and `b.md`
  produces exactly one `DS202` finding (not two), attributed to the later path, naming the earlier.
- `test_near_duplicate_above_threshold_is_flagged` - a paragraph and a lightly-edited copy (cosine
  between 0.85 and 1.0) is flagged.
- `test_distinct_paragraphs_below_threshold_are_clean` - two topically-related but genuinely
  different paragraphs (cosine < 0.85) produce no finding.
- `test_within_document_duplication_is_flagged` - two near-identical paragraphs in one file produce a
  finding (Decision §4).
- `test_threshold_is_configurable` - a borderline pair is flagged at `duplicate_similarity=0.5` and
  clean at `0.99`.
- `test_pair_reported_once_not_twice` - three mutually near-identical paragraphs produce the expected
  number of `i<j` pair findings (3), never the symmetric doubling (6).
- `test_empty_and_single_chunk_corpus_produce_no_findings` - guards Task 01's empty-model path end
  to end through `detect`.
- `test_duplicate_pairs_is_pure` - `duplicate_pairs` on a hand-built tiny `CorpusModel` returns the
  expected tuples without reading disk or config.

`tests/test_config.py` additions:
- `test_duplicate_similarity_default_is_0_85`.
- `test_duplicate_similarity_out_of_range_raises` - `1.5` and `-0.1` → `ConfigError`.
- `test_duplicate_similarity_non_number_raises` - `"high"` → `ConfigError`.

## Success criteria

- [ ] An identical paragraph duplicated across two documents yields exactly one `DS202` finding,
      attributed to the later document and naming the earlier - the canonical "copy-pasted fact"
      case.
- [ ] The threshold is honored and configurable, with the default documented and justified (0.85).
- [ ] `duplicate_pairs` is a pure function over `(CorpusModel, threshold)`, independently testable.
- [ ] Empty/single-chunk corpora produce zero findings and no exception.

## Constraints

- Full type annotations; no bare `except:`. `sklearn` imported inside `detect`/`duplicate_pairs`
  (module reached only via the lazy loader).
- Do not attempt cross-paragraph "fact extraction" (NLP-level claim matching) - that is semantic and
  belongs to `deep` (Milestone 0003). `DS202` is strictly TF-IDF-cosine near-duplicate text; the
  "facts" it catches are facts that happen to be restated in near-identical wording, and the
  description/docs must not over-claim beyond that.
- Do not pre-optimize the O(n²) pass (Decision §6) - document the bound, leave the approximate-NN
  path to a future milestone.
</content>
