# Task 01 — Implement `DS207`: Repeated document sections

**Story:** [Story 06.0](/docs/roadmap/0004-deepening-test-cases/06.0-repeated-document-sections/README.md) · **Rule:** `DS207` · **Profile:** `standard`

## Deliverable and location

Implement `src/docsentinel/detectors/standard/sections.py` (new module unless a preexisting equivalent is found during implementation). Register `Rule(code="DS207", profile="standard", severity="warning", ...)` through the existing rule registry, and bind exactly one detector under `ANALYZERS["DS207"]`. Preserve lazy imports and existing rule identities.

## Inputs and well-defined outputs

**Input source:** Heading-delimited sections from Markdown documents, document corpus statistics.

**Success:** a deterministic tuple of `Finding` objects with `rule="DS207"`, normalized repo-relative paths, correct 1-based lines (where known), evidence-focused messages and severity `warning`.

**Not evaluated:** Missing mandatory config, unsupported source construct, or missing scan context must not silently turn into an assertion that the documentation was checked and found clean. Emit a clear pending/readiness or validation outcome using the milestone's shared per-rule execution status mechanism. **Do not** abuse `Finding(severity="error")` to mean 'could not analyze'.

## Algorithm contract

Algorithm: parse headings into section spans including ancestor heading context; obtain all visible paragraphs, removing code-only blocks; keep substantial multi-paragraph sections beyond configured minimum; vectorize normalized section bodies or compute robust lexical similarity; compare cross-document pairs in stable file/section order; emit later-section warning once per qualifying pair with earlier document/heading evidence. A shared title alone contributes zero content evidence.

## Detailed implementation obligations

1. Extract Markdown heading hierarchy while preserving nested section boundaries, offsets and line numbers.
2. Define word threshold before similarity scoring; do not permit headings alone to drive results.
3. Avoid recomputing expensive corpus representations unnecessarily; no duplicate mirrored pairs.
4. Document overlap with DS202 without changing DS202 findings.

## Settings and parsing

**Proposed configuration fields:** section_similarity: float (0..1, default 0.88); min_section_words: int (default 80).

Config work includes updating `Config`, `_CONFIG_OPTIONS`, both TOML loading paths, documented defaults, bad-config tests, and the existing example config. A rule that requires explicit mappings/dictionaries must be idle with an honest pending/readiness explanation until configured; it cannot implicitly reinterpret every README as an API contract. Existing configs continue loading untouched.

## Work with the current implementation

- `engine.scan` currently calls fast/deep analyzers with two arguments and standard ones with three. Follow Story 01.0's uniform optional-context contract before introducing a rule whose behavior depends on programmatic `Config` overrides.
- Use the already-implemented code paths where appropriate: `discovery.py`, `rules.py`, `code_discovery.py`, `detectors/standard/corpus.py`, `deep_support.py`, and `baseline.py`; do not silently duplicate a heavyweight index.
- No new runtime libraries in `fast`; standard only loads on demand; deep remains explicitly opt-in/advisory. Non-LLM by default in every rule.
- Favor explainable measurements and evidence. Any approximation is documented as a **candidate** rather than an authoritative contradiction.

## Security, negative scope and boundary checks

Two short identical headings with different substantive bodies are not duplicate sections.

- Parse Markdown and Python source without executing it. Sanitize/normalize paths and reject scan-root escapes before I/O.
- Avoid reading generated fixture assets from the repository self-scan; fixture directories belong only to tests.
- No background agent, git invocation, secret file harvesting or remote request from a detector.

## Example Markdown test evidence


### Required fixture path examples

- Positive: `tests/assets/ds207/distinct_section_explanations/a.md` — Two same-title sections contain clearly different substantive material.
- Negative: `tests/assets/ds207/identical_multisection_text/a.md` — Two substantial sections share the same multi-paragraph text; report second one.

The asset files are **required PR deliverables**. A rule implementation without those files and tests loading each case does not satisfy this story.


## Definition of done

- [ ] Rule registered exactly once, and selected/ignored predictably.
- [ ] Config options validated; default settings are conservative and backward compatible.
- [ ] Source line/provenance is preserved; reports are deterministic and privacy-conscious.
- [ ] Direct analyzer unit tests cover parser boundaries and specific error scenarios.
- [ ] Task 02 fixture tests prove no false positive on 3+ clean scenarios and detection on 3+ failing scenarios.
- [ ] README/architecture/rules output explains behavior and limitations.
