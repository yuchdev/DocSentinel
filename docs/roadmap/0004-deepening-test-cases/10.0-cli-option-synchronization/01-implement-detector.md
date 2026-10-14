# Task 01 — Implement `DS218`: CLI option synchronization

**Story:** [Story 10.0](/docs/roadmap/0004-deepening-test-cases/10.0-cli-option-synchronization/README.md) · **Rule:** `DS218` · **Profile:** `standard`

## Deliverable and location

Implement `src/docsentinel/detectors/standard/cli_sync.py` (new module unless a preexisting equivalent is found during implementation). Register `Rule(code="DS218", profile="standard", severity="error", ...)` through the existing rule registry, and bind exactly one detector under `ANALYZERS["DS218"]`. Preserve lazy imports and existing rule identities.

## Inputs and well-defined outputs

**Input source:** Python argparse AST, selected Markdown CLI reference sections, explicit command mapping.

**Success:** a deterministic tuple of `Finding` objects with `rule="DS218"`, normalized repo-relative paths, correct 1-based lines (where known), evidence-focused messages and severity `error`.

**Not evaluated:** Missing mandatory config, unsupported source construct, or missing scan context must not silently turn into an assertion that the documentation was checked and found clean. Emit a clear pending/readiness or validation outcome using the milestone's shared per-rule execution status mechanism. **Do not** abuse `Finding(severity="error")` to mean 'could not analyze'.

## Algorithm contract

Algorithm: load explicitly mapped argparse parser path and documentation reference section; AST-parse parser.add_argument calls with literal flags/defaults/actions; group aliases into canonical option actions and retain command/subparser scope; parse only designated Markdown reference table/options section; compare presence and asserted defaults; completeness errors only with opt-in. Dynamic builder patterns return unsupported evidence, never guess from executing CLI code.

## Detailed implementation obligations

1. Index argparse statements using AST and a deliberately documented supported grammar.
2. Define explicit mapping of source parser and Markdown CLI reference; do not infer from arbitrary flags.
3. Normalize long and short aliases, booleans and subcommand scope; compare only known literal defaults.
4. Emit actionable missing/removed/default mismatch findings with source location; dynamic parser expressions are unsupported.

## Settings and parsing

**Proposed configuration fields:** cli_entrypoints: tuple[str,...] (default empty); cli_document_paths: tuple[str,...] (default empty); cli_option_require_all: bool (default false).

Config work includes updating `Config`, `_CONFIG_OPTIONS`, both TOML loading paths, documented defaults, bad-config tests, and the existing example config. A rule that requires explicit mappings/dictionaries must be idle with an honest pending/readiness explanation until configured; it cannot implicitly reinterpret every README as an API contract. Existing configs continue loading untouched.

## Work with the current implementation

- `engine.scan` currently calls fast/deep analyzers with two arguments and standard ones with three. Follow Story 01.0's uniform optional-context contract before introducing a rule whose behavior depends on programmatic `Config` overrides.
- Use the already-implemented code paths where appropriate: `discovery.py`, `rules.py`, `code_discovery.py`, `detectors/standard/corpus.py`, `deep_support.py`, and `baseline.py`; do not silently duplicate a heavyweight index.
- No new runtime libraries in `fast`; standard only loads on demand; deep remains explicitly opt-in/advisory. Non-LLM by default in every rule.
- Favor explainable measurements and evidence. Any approximation is documented as a **candidate** rather than an authoritative contradiction.

## Security, negative scope and boundary checks

Only recognized argparse syntax is supported initially; Click/Typer adapters require separate work and tests.

- Parse Markdown and Python source without executing it. Sanitize/normalize paths and reject scan-root escapes before I/O.
- Avoid reading generated fixture assets from the repository self-scan; fixture directories belong only to tests.
- No background agent, git invocation, secret file harvesting or remote request from a detector.

## Example Markdown test evidence


### Required fixture path examples

- Positive: `tests/assets/ds218/matching_argument_flags/README.md` — Mapped docs list --timeout and --max-retries that exist with matching defaults.
- Negative: `tests/assets/ds218/removed_option_in_docs/README.md` — README documents --obsolete but argparse no longer defines it.

The asset files are **required PR deliverables**. A rule implementation without those files and tests loading each case does not satisfy this story.


## Definition of done

- [ ] Rule registered exactly once, and selected/ignored predictably.
- [ ] Config options validated; default settings are conservative and backward compatible.
- [ ] Source line/provenance is preserved; reports are deterministic and privacy-conscious.
- [ ] Direct analyzer unit tests cover parser boundaries and specific error scenarios.
- [ ] Task 02 fixture tests prove no false positive on 3+ clean scenarios and detection on 3+ failing scenarios.
- [ ] README/architecture/rules output explains behavior and limitations.
