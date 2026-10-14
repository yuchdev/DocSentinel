# Task 01 — Implement `DS111`: Required document metadata

**Story:** [Story 03.0](/docs/roadmap/0004-deepening-test-cases/03.0-required-document-metadata/README.md) · **Rule:** `DS111` · **Profile:** `fast`

## Deliverable and location

Implement `src/docsentinel/detectors/metadata.py` (new module unless a preexisting equivalent is found during implementation). Register `Rule(code="DS111", profile="fast", severity="error", ...)` through the existing rule registry, and bind exactly one detector under `ANALYZERS["DS111"]`. Preserve lazy imports and existing rule identities.

## Inputs and well-defined outputs

**Input source:** Markdown frontmatter, path selectors, required keys.

**Success:** a deterministic tuple of `Finding` objects with `rule="DS111"`, normalized repo-relative paths, correct 1-based lines (where known), evidence-focused messages and severity `error`.

**Not evaluated:** Missing mandatory config, unsupported source construct, or missing scan context must not silently turn into an assertion that the documentation was checked and found clean. Emit a clear pending/readiness or validation outcome using the milestone's shared per-rule execution status mechanism. **Do not** abuse `Finding(severity="error")` to mean 'could not analyze'.

## Algorithm contract

Algorithm: inspect only selected Markdown paths; detect frontmatter only when first content delimiter is `---` (allow BOM on UTF-8); find matching terminator and parse a deliberately restricted top-level scalar `key: value` subset; collect keys + source offsets; validate required key presence, nonempty values, duplicate keys; mark unsupported structured YAML as unverifiable. Empty string is missing, numeric `0` and boolean `false` are present. Do not reuse `tomllib` as if it parsed YAML.

## Detailed implementation obligations

1. Introduce a narrowly documented frontmatter scalar reader with one-based source positions and explicit unsupported constructs.
2. Add glob-based applicability configured through Config and both supported TOML discovery forms.
3. Emit one finding per missing/empty/duplicate key with location; avoid multiple misleading reports for malformed input.
4. Guarantee no third-party YAML import on fast path.

## Settings and parsing

**Proposed configuration fields:** metadata_paths: tuple[str, ...] (default empty); required_metadata_fields: tuple[str, ...] (default title,status); metadata_format: str (default yaml_subset).

Config work includes updating `Config`, `_CONFIG_OPTIONS`, both TOML loading paths, documented defaults, bad-config tests, and the existing example config. A rule that requires explicit mappings/dictionaries must be idle with an honest pending/readiness explanation until configured; it cannot implicitly reinterpret every README as an API contract. Existing configs continue loading untouched.

## Work with the current implementation

- `engine.scan` currently calls fast/deep analyzers with two arguments and standard ones with three. Follow Story 01.0's uniform optional-context contract before introducing a rule whose behavior depends on programmatic `Config` overrides.
- Use the already-implemented code paths where appropriate: `discovery.py`, `rules.py`, `code_discovery.py`, `detectors/standard/corpus.py`, `deep_support.py`, and `baseline.py`; do not silently duplicate a heavyweight index.
- No new runtime libraries in `fast`; standard only loads on demand; deep remains explicitly opt-in/advisory. Non-LLM by default in every rule.
- Favor explainable measurements and evidence. Any approximation is documented as a **candidate** rather than an authoritative contradiction.

## Security, negative scope and boundary checks

Do not mistake `---` used as a thematic rule halfway through prose for a frontmatter block. Do not treat `0` or `false` as empty.

- Parse Markdown and Python source without executing it. Sanitize/normalize paths and reject scan-root escapes before I/O.
- Avoid reading generated fixture assets from the repository self-scan; fixture directories belong only to tests.
- No background agent, git invocation, secret file harvesting or remote request from a detector.

## Example Markdown test evidence


### Required fixture path examples

- Positive: `tests/assets/ds111/valid_required_fields/README.md` — Required title and status are present in opening frontmatter.
- Negative: `tests/assets/ds111/missing_title_field/README.md` — Selected document frontmatter lacks required title.

The asset files are **required PR deliverables**. A rule implementation without those files and tests loading each case does not satisfy this story.


## Definition of done

- [ ] Rule registered exactly once, and selected/ignored predictably.
- [ ] Config options validated; default settings are conservative and backward compatible.
- [ ] Source line/provenance is preserved; reports are deterministic and privacy-conscious.
- [ ] Direct analyzer unit tests cover parser boundaries and specific error scenarios.
- [ ] Task 02 fixture tests prove no false positive on 3+ clean scenarios and detection on 3+ failing scenarios.
- [ ] README/architecture/rules output explains behavior and limitations.
