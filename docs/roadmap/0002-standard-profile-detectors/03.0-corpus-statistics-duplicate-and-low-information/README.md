# Story 03.0 - Corpus Statistics: Duplicate & Low-Information Detectors (`DS202`, `DS203`)

The two genuinely **corpus-wide** detectors - the reason `standard` is a separate profile from
`fast` at all. Both vectorize every paragraph of every scanned document together with
`scikit-learn`'s `TfidfVectorizer`:

- `DS202` - **duplicated text / facts**: paragraph pairs whose TF-IDF cosine similarity exceeds a
  threshold (near-duplicate boilerplate, copy-pasted facts).
- `DS203` - **low-information content**: paragraphs that are both lexically thin (low type-token
  ratio, via `textstat`) and non-distinctive (their top TF-IDF terms are all corpus-common words).

They share a single fitted vectorizer (Task 01) - fitting TF-IDF twice over the whole corpus would
be wasteful and would risk the two detectors disagreeing on vocabulary. This shared module is a
**deliberate, documented exception** to Milestone 0001's "no shared helpers across detectors"
convention: that convention was about tiny stdlib regex helpers in `fast`, where duplication is
cheaper than coupling; here the shared artifact is an expensive, parameter-sensitive model whose
single source of truth is the whole point.

## How a corpus-wide detector fits the `Analyzer` signature

The signature is unchanged: `Analyzer = Callable[[Path, tuple[Document, ...]], tuple[Finding, ...]]`.
A `fast` detector *also* receives the full `documents` tuple but processes it one file at a time;
`DS202`/`DS203` receive the same tuple and actually use all of it at once. No signature change is
needed or permitted - the design point is simply that the tuple is already the whole corpus. Both
detectors read document *content* from disk (the `Document` model carries only `path` + `bytes`, not
text), via the shared corpus helper.

## Tasks

| # | Task | Rule | Output |
|---|------|------|--------|
| 01 | [Shared corpus vectorizer & chunking](01-shared-corpus-module.md) | - | `src/docsentinel/detectors/standard/corpus.py`: `Chunk`, `iter_chunks`, `CorpusModel`, `build_corpus_model` |
| 02 | [Duplicate-text detector](02-duplicate-text-detector.md) | `DS202` | `src/docsentinel/detectors/standard/duplication.py`, `Config.duplicate_similarity` |
| 03 | [Low-information-content detector](03-low-information-detector.md) | `DS203` | `src/docsentinel/detectors/standard/low_information.py`, `Config.min_information_score` |
| 04 | [Package wiring & end-to-end test](04-wiring-and-end-to-end.md) | - | `detectors/standard/__init__.py` import lines, end-to-end tests |

01 must land first (02 and 03 both consume `CorpusModel`). 02 and 03 are independent of each other.
04 wires both and proves the chain.
</content>
