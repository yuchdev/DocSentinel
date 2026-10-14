# Task 01 — Implement `DS217`: Configuration key synchronization

**Story:** [Story 09.0](/docs/roadmap/0004-deepening-test-cases/09.0-configuration-key-synchronization/README.md) · **Rule:** `DS217` · **Profile:** `standard`

## Deliverable and location

Implement `src/docsentinel/detectors/standard/config_sync.py` (new module unless a preexisting equivalent is found during implementation). Register `Rule(code="DS217", profile="standard", severity="error", ...)` through the existing rule registry, and bind exactly one detector under `ANALYZERS["DS217"]`. Preserve lazy imports and existing rule identities.

## Inputs and well-defined outputs

**Input source:** Markdown config tables/TOML fences, explicit schema mappings, parsed source literals.

**Success:** a deterministic tuple of `Finding` objects with `rule="DS217"`, normalized repo-relative paths, correct 1-based lines (where known), evidence-focused messages and severity `error`.

**Not evaluated:** Missing mandatory config, unsupported source construct, or missing scan context must not silently turn into an assertion that the documentation was checked and found clean. Emit a clear pending/readiness or validation outcome using the milestone's shared per-rule execution status mechanism. **Do not** abuse `Finding(severity="error")` to mean 'could not analyze'.

## Algorithm contract

Algorithm: load explicit doc-to-source mapping; validate source path stays in repo; parse declarative dataclass field literal defaults and mapped TOML reference values; extract documented key/value claims from mapped Markdown tables or explicitly tagged TOML snippets; compare typed values and required key sets within same scope/version; report missing/removed/changed keys with source evidence; mark expressions, factories and environment-derived defaults as unverifiable. No arbitrary prose number matching.

## Detailed implementation obligations

1. Specify a compact explicit config-schema mapping format; include source path, schema type, version and required keys.
2. Parse only safe static Python AST nodes and TOML literals, handling field defaults without evaluating expressions.
3. Extract config claims from recognizable Markdown tables and explicitly designated TOML fences.
4. Report source provenance and exact Markdown line with typed comparison; treat unknown source defaults as pending/unverifiable.

## Settings and parsing

**Proposed configuration fields:** config_sources: tuple[str,...] (default empty); config_document_paths: tuple[str,...] (default empty); config_mappings: path or TOML table explicitly defining doc key -> source key.

Config work includes updating `Config`, `_CONFIG_OPTIONS`, both TOML loading paths, documented defaults, bad-config tests, and the existing example config. A rule that requires explicit mappings/dictionaries must be idle with an honest pending/readiness explanation until configured; it cannot implicitly reinterpret every README as an API contract. Existing configs continue loading untouched.

## Work with the current implementation

- `engine.scan` currently calls fast/deep analyzers with two arguments and standard ones with three. Follow Story 01.0's uniform optional-context contract before introducing a rule whose behavior depends on programmatic `Config` overrides.
- Use the already-implemented code paths where appropriate: `discovery.py`, `rules.py`, `code_discovery.py`, `detectors/standard/corpus.py`, `deep_support.py`, and `baseline.py`; do not silently duplicate a heavyweight index.
- No new runtime libraries in `fast`; standard only loads on demand; deep remains explicitly opt-in/advisory. Non-LLM by default in every rule.
- Favor explainable measurements and evidence. Any approximation is documented as a **candidate** rather than an authoritative contradiction.

## Security, negative scope and boundary checks

A numeric value in free prose is never presumed to be a config default solely because it resembles a schema value.

- Parse Markdown and Python source without executing it. Sanitize/normalize paths and reject scan-root escapes before I/O.
- Avoid reading generated fixture assets from the repository self-scan; fixture directories belong only to tests.
- No background agent, git invocation, secret file harvesting or remote request from a detector.

## Example Markdown test evidence


### Required fixture path examples

- Positive: `tests/assets/ds217/documented_defaults_match/README.md` — Configured doc table key retry_count=3 matches supported dataclass literal default 3.
- Negative: `tests/assets/ds217/documented_default_mismatch/README.md` — Documentation declares retry_count=5 while mapped literal source default is 3.

The asset files are **required PR deliverables**. A rule implementation without those files and tests loading each case does not satisfy this story.


## Definition of done

- [ ] Rule registered exactly once, and selected/ignored predictably.
- [ ] Config options validated; default settings are conservative and backward compatible.
- [ ] Source line/provenance is preserved; reports are deterministic and privacy-conscious.
- [ ] Direct analyzer unit tests cover parser boundaries and specific error scenarios.
- [ ] Task 02 fixture tests prove no false positive on 3+ clean scenarios and detection on 3+ failing scenarios.
- [ ] README/architecture/rules output explains behavior and limitations.
