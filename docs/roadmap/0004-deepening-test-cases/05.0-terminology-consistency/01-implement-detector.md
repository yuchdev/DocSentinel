# Task 01 — Implement `DS205`: Terminology consistency

**Story:** [Story 05.0](/docs/roadmap/0004-deepening-test-cases/05.0-terminology-consistency/README.md) · **Rule:** `DS205` · **Profile:** `standard`

## Deliverable and location

Implement `src/docsentinel/detectors/standard/terminology.py` (new module unless a preexisting equivalent is found during implementation). Register `Rule(code="DS205", profile="standard", severity="warning", ...)` through the existing rule registry, and bind exactly one detector under `ANALYZERS["DS205"]`. Preserve lazy imports and existing rule identities.

## Inputs and well-defined outputs

**Input source:** Markdown visible prose, configured terminology file containing canonical term and aliases.

**Success:** a deterministic tuple of `Finding` objects with `rule="DS205"`, normalized repo-relative paths, correct 1-based lines (where known), evidence-focused messages and severity `warning`.

**Not evaluated:** Missing mandatory config, unsupported source construct, or missing scan context must not silently turn into an assertion that the documentation was checked and found clean. Emit a clear pending/readiness or validation outcome using the milestone's shared per-rule execution status mechanism. **Do not** abuse `Finding(severity="error")` to mean 'could not analyze'.

## Algorithm contract

Algorithm: parse dictionary as TOML with explicit `canonical -> aliases` mapping and documented case policy; reject ambiguous alias-to-canonical mappings; compile safe phrase-level boundary patterns; tokenize/mask Markdown visible prose; emit alias occurrence and suggested canonical term with a one-based line; do not lemmatize or guess synonyms. Preserve distinction between visible link labels and destinations; do not flag examples in code fences.

## Detailed implementation obligations

1. Parse canonical-to-alias TOML dictionary with input validation and no automatic guessing.
2. Match visible Markdown prose with Unicode-safe boundaries and case policy.
3. Keep canonical spelling in messages and source line; configurable scope/exemptions.
4. Use standard lazy import boundary even if implementation itself uses only stdlib.

## Settings and parsing

**Proposed configuration fields:** terminology_file: str|None (default None); terminology_case_policy: str (preserve|fold); terminology_ignore_paths: tuple[str,...].

Config work includes updating `Config`, `_CONFIG_OPTIONS`, both TOML loading paths, documented defaults, bad-config tests, and the existing example config. A rule that requires explicit mappings/dictionaries must be idle with an honest pending/readiness explanation until configured; it cannot implicitly reinterpret every README as an API contract. Existing configs continue loading untouched.

## Work with the current implementation

- `engine.scan` currently calls fast/deep analyzers with two arguments and standard ones with three. Follow Story 01.0's uniform optional-context contract before introducing a rule whose behavior depends on programmatic `Config` overrides.
- Use the already-implemented code paths where appropriate: `discovery.py`, `rules.py`, `code_discovery.py`, `detectors/standard/corpus.py`, `deep_support.py`, and `baseline.py`; do not silently duplicate a heavyweight index.
- No new runtime libraries in `fast`; standard only loads on demand; deep remains explicitly opt-in/advisory. Non-LLM by default in every rule.
- Favor explainable measurements and evidence. Any approximation is documented as a **candidate** rather than an authoritative contradiction.

## Security, negative scope and boundary checks

“translation chain” and “translation pipeline” are interchangeable only when the project has explicitly declared them so.

- Parse Markdown and Python source without executing it. Sanitize/normalize paths and reject scan-root escapes before I/O.
- Avoid reading generated fixture assets from the repository self-scan; fixture directories belong only to tests.
- No background agent, git invocation, secret file harvesting or remote request from a detector.

## Example Markdown test evidence


### Required fixture path examples

- Positive: `tests/assets/ds205/canonical_terms_only/README.md` — Docs use CanonixEngine and translation pipeline exclusively.
- Negative: `tests/assets/ds205/deprecated_term_in_prose/README.md` — Configured alias translation chain occurs as visible prose and maps to translation pipeline.

The asset files are **required PR deliverables**. A rule implementation without those files and tests loading each case does not satisfy this story.


## Definition of done

- [ ] Rule registered exactly once, and selected/ignored predictably.
- [ ] Config options validated; default settings are conservative and backward compatible.
- [ ] Source line/provenance is preserved; reports are deterministic and privacy-conscious.
- [ ] Direct analyzer unit tests cover parser boundaries and specific error scenarios.
- [ ] Task 02 fixture tests prove no false positive on 3+ clean scenarios and detection on 3+ failing scenarios.
- [ ] README/architecture/rules output explains behavior and limitations.
