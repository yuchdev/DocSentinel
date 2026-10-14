# Task 01 — Implement `DS208`: Near duplicate documents

**Story:** [Story 07.0](/docs/roadmap/0004-deepening-test-cases/07.0-near-duplicate-documents/README.md) · **Rule:** `DS208` · **Profile:** `standard`

## Deliverable and location

Implement `src/docsentinel/detectors/standard/documents.py` (new module unless a preexisting equivalent is found during implementation). Register `Rule(code="DS208", profile="standard", severity="warning", ...)` through the existing rule registry, and bind exactly one detector under `ANALYZERS["DS208"]`. Preserve lazy imports and existing rule identities.

## Inputs and well-defined outputs

**Input source:** Whole-doc normalized Markdown prose, document vectors.

**Success:** a deterministic tuple of `Finding` objects with `rule="DS208"`, normalized repo-relative paths, correct 1-based lines (where known), evidence-focused messages and severity `warning`.

**Not evaluated:** Missing mandatory config, unsupported source construct, or missing scan context must not silently turn into an assertion that the documentation was checked and found clean. Emit a clear pending/readiness or validation outcome using the milestone's shared per-rule execution status mechanism. **Do not** abuse `Finding(severity="error")` to mean 'could not analyze'.

## Algorithm contract

Algorithm: produce one normalized body per doc after excluding frontmatter, code-only blocks and configured boilerplate; require minimum token length; compute document cosine/Jaccard mix only on meaningful prose as documented and pinned; evaluate pairs in deterministic order; issue one later document finding per qualifying pair; skip excluded and generated paths. Do not confuse high overlap in headers with whole-body duplication.

## Detailed implementation obligations

1. Normalize whole-document visible prose with transparent boilerplate handling and minimum word count.
2. Expose document_similarity and word cutoff with strict validation.
3. Report stable pairs once with human-readable similarity score and paths.
4. Keep DS208 findings independent of DS202/DS207.

## Settings and parsing

**Proposed configuration fields:** document_similarity: float (0..1, default 0.90); min_document_words: int (default 120); duplicate_document_exclude: tuple[str,...].

Config work includes updating `Config`, `_CONFIG_OPTIONS`, both TOML loading paths, documented defaults, bad-config tests, and the existing example config. A rule that requires explicit mappings/dictionaries must be idle with an honest pending/readiness explanation until configured; it cannot implicitly reinterpret every README as an API contract. Existing configs continue loading untouched.

## Work with the current implementation

- `engine.scan` currently calls fast/deep analyzers with two arguments and standard ones with three. Follow Story 01.0's uniform optional-context contract before introducing a rule whose behavior depends on programmatic `Config` overrides.
- Use the already-implemented code paths where appropriate: `discovery.py`, `rules.py`, `code_discovery.py`, `detectors/standard/corpus.py`, `deep_support.py`, and `baseline.py`; do not silently duplicate a heavyweight index.
- No new runtime libraries in `fast`; standard only loads on demand; deep remains explicitly opt-in/advisory. Non-LLM by default in every rule.
- Favor explainable measurements and evidence. Any approximation is documented as a **candidate** rather than an authoritative contradiction.

## Security, negative scope and boundary checks

Two distinct manuals sharing navigation boilerplate must not be flagged solely for template similarity.

- Parse Markdown and Python source without executing it. Sanitize/normalize paths and reject scan-root escapes before I/O.
- Avoid reading generated fixture assets from the repository self-scan; fixture directories belong only to tests.
- No background agent, git invocation, secret file harvesting or remote request from a detector.

## Example Markdown test evidence


### Required fixture path examples

- Positive: `tests/assets/ds208/different_topic_documents/a.md` — Two substantial documents describe disjoint architecture topics.
- Negative: `tests/assets/ds208/identical_full_documents/a.md` — Two substantive docs have identical normalized prose.

The asset files are **required PR deliverables**. A rule implementation without those files and tests loading each case does not satisfy this story.


## Definition of done

- [ ] Rule registered exactly once, and selected/ignored predictably.
- [ ] Config options validated; default settings are conservative and backward compatible.
- [ ] Source line/provenance is preserved; reports are deterministic and privacy-conscious.
- [ ] Direct analyzer unit tests cover parser boundaries and specific error scenarios.
- [ ] Task 02 fixture tests prove no false positive on 3+ clean scenarios and detection on 3+ failing scenarios.
- [ ] README/architecture/rules output explains behavior and limitations.
