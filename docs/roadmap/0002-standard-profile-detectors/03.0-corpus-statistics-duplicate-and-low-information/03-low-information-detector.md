# Task 03 - Low-Information-Content Detector (`DS203`)

**Story:** [03.0 - Corpus Statistics](README.md)
**Depends on:** [01 - Shared corpus vectorizer & chunking](01-shared-corpus-module.md); independent
of [02 - Duplicate detector](02-duplicate-text-detector.md) (different rule, same `CorpusModel`)

## Purpose

Covers `CLAUDE.md`'s "low-information facts" requirement: flag a paragraph that carries little
information - lexically thin *and* non-distinctive. A paragraph that is all common connective words
("As mentioned above, this is of course important to note, generally speaking...") says almost
nothing; one whose top TF-IDF terms are all corpus-wide-common words is not pulling its weight. This
is the filler-paragraph detector.

## Decision this task implements

1. **Two signals, combined - both must be low.** A paragraph is low-information only when it is
   *both*:
   - **Lexically thin** - low type-token ratio (TTR = distinct words / total words), computed with
     `textstat` (or a direct count; see Symbols). Repetitive, padded text has low TTR.
   - **Non-distinctive** - its maximum TF-IDF weight (over the shared `CorpusModel.matrix` row) is
     low, meaning even its "most characteristic" term is corpus-common. A paragraph of boilerplate
     has no standout term.
   Requiring *both* avoids two large false-positive classes: a short list of distinct keywords
   (low TTR by length but high distinctiveness) and a flowing but genuinely informative paragraph
   (high TTR). This mirrors `DS201`'s "two formulas must agree" conservatism.
2. **Combined into one `information_score` in `[0, 1]`.** Define
   `information_score = sqrt(norm_ttr * norm_distinctiveness)` (the geometric mean of the two
   normalized signals), where `norm_ttr = min(ttr / _TTR_REF, 1.0)` and
   `norm_distinctiveness = min(max_tfidf / _TFIDF_REF, 1.0)`. The geometric mean is low if *either*
   factor is low and only high if *both* are - encoding "both must be low to flag." Flag a chunk when
   `information_score < min_information_score`. Reference constants `_TTR_REF = 0.5`,
   `_TFIDF_REF = 0.3` are fixed (not config) normalizers chosen so typical informative prose lands
   near `information_score` ≈ 0.6-1.0; only the final threshold is user-tunable.
3. **Default threshold: `min_information_score = 0.15`**, `warning` severity. Deliberately low -
   `DS203` should fire only on paragraphs that are *clearly* filler, not merely below-average, because
   "this paragraph is a bit thin" is a judgment call a tool should be humble about. Configurable for
   projects that want a stricter bar.
4. **Reuse Story 03 Task 01's fitted vectorizer - do not re-fit.** `DS203` reads
   `CorpusModel.matrix`/`vocabulary`/`idf` directly to get each chunk's max TF-IDF. This is the
   documented sharing decision (see the tradeoff note below); re-fitting a second independent
   vectorizer would double the cost and risk the two detectors disagreeing on vocabulary.
5. **Message names the chunk and the score.** `f"low-information paragraph (score {score:.2f} <
   {threshold:.2f}): '{chunk.preview}'"`, attributed to `chunk.path`.

## Tradeoff recorded: share the vectorizer, accept the coupling

`DS202` and `DS203` share `corpus.CorpusModel`. The alternative - each detector fits its own
vectorizer - would decouple them (either could change parameters without affecting the other) at the
cost of fitting TF-IDF twice over the whole corpus per scan and risking subtly different vocabularies
producing inconsistent similarity/distinctiveness numbers. **This milestone chooses sharing**: the
vectorizer parameters are fixed constants in `corpus.py` (not per-detector config), so the coupling
is static and visible in one place, and the performance win is real on every `standard` scan. The
cost - changing `corpus.py`'s vectorizer parameters affects both detectors at once - is acceptable
and must be called out in `corpus.py`'s docstring so the coupling is never a surprise. Record this
decision here and cross-reference it from `corpus.py`.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/detectors/standard/low_information.py` | Create |
| `src/docsentinel/config.py` | Modify - add `Config.min_information_score` + validation |
| `tests/test_detectors_low_information.py` | Create |
| `tests/test_config.py` | Modify - `min_information_score` validation tests |

## Symbols / fields

`src/docsentinel/detectors/standard/low_information.py`:

| Symbol | Kind | Notes |
|--------|------|-------|
| `DS203` | module-level `Rule` via `register_rule(...)` | `Rule(code="DS203", profile="standard", title="Low-information content", description="A paragraph is both lexically thin and non-distinctive.", severity="warning")`. |
| `_TTR_REF` / `_TFIDF_REF` | module-level `float` | `0.5` / `0.3` - fixed normalizers (Decision §2). |
| `type_token_ratio(text: str) -> float` | function | Distinct words / total words (lowercased, word-tokenized the same way the vectorizer tokenizes, for consistency). Returns `0.0` for empty text. |
| `information_score(ttr: float, max_tfidf: float) -> float` | function | The geometric-mean combiner (Decision §2). Pure, unit-testable in isolation. |
| `low_information_chunks(model: CorpusModel, threshold: float) -> tuple[tuple[int, float], ...]` | function | Returns `(chunk_index, score)` for every chunk scoring below `threshold`, sorted by chunk index. Reads each row's max TF-IDF from `model.matrix` and each chunk's TTR from `model.chunks[i].text`. Pure over `(model, threshold)`. |
| `detect(root: Path, documents: tuple[Document, ...]) -> tuple[Finding, ...]` | function, `ANALYZERS["DS203"]` | Reads `min_information_score` via `load_config(root)`; builds the `CorpusModel`; calls `low_information_chunks`; maps each to a `Finding(rule="DS203", path=..., ...)`. |

`src/docsentinel/config.py`:

| Symbol | Change |
|--------|--------|
| `Config.min_information_score: float = 0.15` | New field. |
| validation | Number in `[0.0, 1.0]`, not a `bool`; else `ConfigError("min_information_score must be a number between 0 and 1")`. |

## Validators (raise `ConfigError`)

- `min_information_score` outside `[0, 1]`, not a number, or a `bool` → `ConfigError`.

## Tests (`tests/test_detectors_low_information.py`)

Guard with `importorskip("sklearn")` / `importorskip("textstat")`.

- `test_filler_paragraph_is_flagged` - a paragraph of repetitive, common-word filler (low TTR, low
  max-TF-IDF) within a corpus of otherwise substantive paragraphs produces one `DS203` finding.
- `test_informative_paragraph_is_clean` - a dense, distinctive paragraph produces none.
- `test_keyword_list_not_flagged_despite_low_ttr` - a short list of distinct technical terms (low
  TTR by brevity but high distinctiveness) is NOT flagged - the "both must be low" guard.
- `test_information_score_is_geometric_mean` - `information_score(0.0, 0.9) == 0.0` and
  `information_score` is monotonic in each argument; a direct unit test of the combiner.
- `test_threshold_is_configurable` - a borderline paragraph flagged at `min_information_score=0.4`,
  clean at `0.01`.
- `test_reuses_corpus_model_without_refitting` - spy on `TfidfVectorizer.fit_transform`; a scan
  running **both** `DS202` and `DS203` (via the engine) fits at most... see note - each detector's
  `detect` calls `build_corpus_model` once, so two detectors currently fit twice per scan unless the
  model is cached. **Decision for this test:** assert `low_information_chunks` itself performs **zero**
  fits (it only reads a passed-in `CorpusModel`), proving the sharing boundary is correct at the
  function level; cross-scan model caching between the two detectors is explicitly a Story 03.0 Task
  04 concern (see that task), not this one's.
- `test_empty_and_single_chunk_corpus_produce_no_findings`.

`tests/test_config.py` additions:
- `test_min_information_score_default_is_0_15`.
- `test_min_information_score_out_of_range_raises`.
- `test_min_information_score_non_number_raises`.

## Success criteria

- [ ] `DS203` fires only when both signals are low - the keyword-list and informative-prose
      false-positive classes each have a covering negative test.
- [ ] `information_score` and `low_information_chunks` are pure functions, unit-tested without disk or
      config.
- [ ] `DS203` reads the shared `CorpusModel` and performs no TF-IDF fit of its own (the fit lives in
      `corpus.build_corpus_model`).

## Constraints

- Full type annotations; no bare `except:`. Heavy imports inside functions (lazy-loader-reached
  module).
- Do not introduce a second, independent vectorizer (Decision §4 / the tradeoff note) - share
  `corpus.CorpusModel`.
- Tokenize TTR consistently with the vectorizer's `token_pattern` so the two signals describe the
  same tokens; note this in the module docstring.
</content>
