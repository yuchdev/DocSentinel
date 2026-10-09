# Task 01 - Shared Corpus Vectorizer & Chunking (`corpus.py`)

**Story:** [03.0 - Corpus Statistics](README.md)
**Depends on:** Milestone 0002 Story 01.0 (lives in the lazily-loaded `standard` subpackage, so it
may import `sklearn` freely)

## Purpose

`DS202` and `DS203` both need the same two things: the corpus broken into paragraph-level chunks
with provenance (which document, where), and a single `TfidfVectorizer` fitted once over all those
chunks. This task builds that shared substrate so the two detectors agree on vocabulary and the
expensive fit happens once per scan. It emits no findings itself - it is the corpus-statistics
equivalent of Story 01.0's plumbing.

## Decision this task implements

1. **Chunk granularity = paragraph.** A chunk is a blank-line-delimited block of prose within one
   document. Paragraph granularity is the right unit for "duplicated text/facts" (a duplicated fact
   is usually a sentence or paragraph, not a whole file) and for "low information" (a filler
   paragraph). Fenced code blocks are excluded (they are not prose and would dominate TF-IDF with
   identifiers); inline code spans and link targets are stripped, link text kept - the same prose
   extraction `DS201` uses, re-implemented here against the chunk model (see Constraints on why this
   is not shared with `complexity.py`).
2. **Provenance per chunk.** Each `Chunk` records its source document path and its ordinal index
   within that document, so a `Finding` can point back to a specific paragraph (message references
   `path#chunk{index}` - a stable, human-readable locator, since the `Finding` model has no line
   field). Record the chunk's first ~60 characters as a preview for messages.
3. **One shared, deterministically-configured vectorizer.** `TfidfVectorizer(stop_words="english",
   sublinear_tf=True, min_df=1, lowercase=True, token_pattern=r"(?u)\b\w\w+\b")`. `stop_words` and
   `sublinear_tf` make cosine similarity reflect *distinctive* content rather than shared
   boilerplate function words; these parameters are fixed constants (not config) so results are
   reproducible and the two detectors share one vocabulary. The fitted matrix and vocabulary are
   returned together as a `CorpusModel`.
4. **Deterministic chunk ordering.** Chunks are produced in `(document path, chunk index)` sorted
   order, so the TF-IDF matrix rows, the vocabulary, and every downstream pair enumeration are
   reproducible run to run (`documents` already arrives sorted from `discovery.discover`, but sort
   defensively here too).
5. **Small-corpus / empty-corpus handling.** If there are zero chunks (empty corpus, or every
   document is all-code), `build_corpus_model` returns a `CorpusModel` with an empty matrix and both
   detectors must no-op cleanly (no exception). `TfidfVectorizer` raises on an empty vocabulary;
   guard that explicitly rather than letting it propagate.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/detectors/standard/corpus.py` | Create |
| `tests/test_standard_corpus.py` | Create |

## Symbols / fields

`src/docsentinel/detectors/standard/corpus.py`:

| Symbol | Kind | Fields / signature | Notes |
|--------|------|---------------------|-------|
| `Chunk` | `@dataclass(frozen=True)` | `path: str`, `index: int`, `text: str`, `preview: str` | One paragraph of prose with provenance. `preview` is `text[:60]` (single-lined) for messages. |
| `_MIN_CHUNK_WORDS` | module-level `int` | `20` | Chunks shorter than this are excluded from the model - too short to be a meaningful duplicate or a measurable "low-information" unit, and a magnet for false positives (a one-line heading is not a duplicated fact). |
| `_extract_prose_blocks(text: str) -> list[str]` | function | - | Strips fenced code blocks, inline code spans, link targets; splits on blank lines into paragraph blocks. |
| `iter_chunks(root: Path, documents: tuple[Document, ...]) -> tuple[Chunk, ...]` | function | - | Reads each `.md` document from disk (`root / document.path`), extracts prose blocks, drops blocks under `_MIN_CHUNK_WORDS` words, yields `Chunk`s in sorted `(path, index)` order. `index` is the ordinal among *retained* blocks within the document. |
| `CorpusModel` | `@dataclass(frozen=True)` | `chunks: tuple[Chunk, ...]`, `matrix: "scipy.sparse.csr_matrix"`, `vocabulary: dict[str, int]`, `idf: "numpy.ndarray"` | The fitted TF-IDF state both detectors share. `matrix` row `i` ↔ `chunks[i]`. `vocabulary` and `idf` let `DS203` compute per-chunk distinctiveness without re-fitting. |
| `build_corpus_model(root: Path, documents: tuple[Document, ...]) -> CorpusModel` | function | - | Calls `iter_chunks`, fits the fixed-parameter `TfidfVectorizer` on the chunk texts, returns the `CorpusModel`. On zero chunks, returns a `CorpusModel` with `chunks=()` and an empty matrix (Decision §5) - no fit attempted. |

- Type the `scipy`/`numpy` fields as string forward-refs or under `if TYPE_CHECKING:` so this
  module's annotations do not force a heavy import at annotation-eval time; the runtime import of
  `sklearn` (which pulls `scipy`/`numpy`) happens inside `build_corpus_model`, consistent with the
  module only ever being imported via the Story 01.0 lazy loader.

## Validators

- No `ConfigError` here - this module reads no config. The two thresholds (`duplicate_similarity`,
  `min_information_score`) belong to the detectors (Tasks 02/03), not the shared substrate.
- `build_corpus_model` must not raise on an empty corpus (Decision §5) - it returns an empty model.
- File-read errors (`OSError`/`UnicodeDecodeError`) propagate, consistent with `DS101`/`DS201`.

## Tests (`tests/test_standard_corpus.py`)

Guard with `importorskip("sklearn")` (and `textstat` if any helper here uses it).

- `test_iter_chunks_splits_on_blank_lines` - a two-paragraph document yields two chunks with
  `index` 0 and 1 and the right `path`.
- `test_iter_chunks_excludes_code_blocks` - a document whose only non-prose is a fenced code block
  yields chunks containing none of the code's tokens.
- `test_iter_chunks_drops_short_blocks` - a paragraph under `_MIN_CHUNK_WORDS` words is not emitted.
- `test_iter_chunks_is_deterministically_ordered` - across documents, chunks come back sorted by
  `(path, index)` regardless of input `documents` order.
- `test_chunk_preview_is_truncated_single_line` - a long multi-line paragraph's `preview` is ≤60
  chars and has no embedded newline.
- `test_build_corpus_model_fits_once` - the returned `matrix` has one row per chunk and
  `vocabulary`/`idf` are populated; monkeypatch/`spy` on `TfidfVectorizer.fit_transform` to assert
  it is called exactly once.
- `test_build_corpus_model_empty_corpus_returns_empty_model` - zero `.md` documents (or all-code
  documents) returns `CorpusModel(chunks=())` with an empty matrix and **no** exception (guards
  Decision §5).
- `test_build_corpus_model_single_chunk_does_not_crash` - one chunk only: model builds, matrix has
  one row (the degenerate corpus that would otherwise make pairwise logic in Task 02 trivial).

## Success criteria

- [ ] A corpus produces identical `chunks`, `vocabulary`, and `matrix` shape across repeated runs -
      determinism is exercised by a test comparing two `build_corpus_model` calls on the same input.
- [ ] The vectorizer is fitted exactly once per `build_corpus_model` call, and `DS202`/`DS203` (Tasks
      02/03) consume the result without re-fitting.
- [ ] Empty and single-chunk corpora are handled without exceptions.

## Constraints

- Full type annotations; no bare `except:`. Heavy imports (`sklearn`, `scipy`, `numpy`) occur inside
  functions or under `TYPE_CHECKING`, never at unconditional module top level that would run before
  the lazy loader intends (the module is only reached via the loader, but keep the import local to be
  robust against accidental eager import during development).
- **Why not reuse `complexity.py`'s `_extract_prose`?** `DS201` needs the whole document's prose as
  one string for a single readability score; this module needs it split into provenance-bearing
  paragraph chunks. The extraction *rules* are the same but the output shapes differ, and coupling
  them would force one to carry the other's concerns. Re-implementing the small strip-code helper
  here is cheaper than that coupling - the *expensive* shared artifact (the vectorizer) is what Task
  01 exists to centralize, not the cheap regex strip. Note this reasoning in the module docstring so
  a future contributor does not "DRY them up" and reintroduce the coupling.
</content>
