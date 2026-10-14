# Task 01 — Implement `DS216`: Stale source symbol references

**Story:** [Story 08.0](/docs/roadmap/0004-deepening-test-cases/08.0-stale-source-symbol-references/README.md) · **Rule:** `DS216` · **Profile:** `standard`

## Deliverable and location

Implement `src/docsentinel/detectors/standard/symbols.py` (new module unless a preexisting equivalent is found during implementation). Register `Rule(code="DS216", profile="standard", severity="error", ...)` through the existing rule registry, and bind exactly one detector under `ANALYZERS["DS216"]`. Preserve lazy imports and existing rule identities.

## Inputs and well-defined outputs

**Input source:** Markdown qualified symbol mentions and source index from configured Python roots.

**Success:** a deterministic tuple of `Finding` objects with `rule="DS216"`, normalized repo-relative paths, correct 1-based lines (where known), evidence-focused messages and severity `error`.

**Not evaluated:** Missing mandatory config, unsupported source construct, or missing scan context must not silently turn into an assertion that the documentation was checked and found clean. Emit a clear pending/readiness or validation outcome using the milestone's shared per-rule execution status mechanism. **Do not** abuse `Finding(severity="error")` to mean 'could not analyze'.

## Algorithm contract

Algorithm: construct a deterministic Python AST source index from configured local code roots. Populate fully qualified module/class/function/member names, tracking static aliases when safe. Extract Markdown qualified references only from supported contexts (explicit local imports, configured prefixes or local module references). Confirm module belongs to repository before reporting absent member. Treat unqualified, external or dynamic references as unverified/ignored by scope, not errors. Parse but never import source.

## Detailed implementation obligations

1. Create source symbol index from ast.parse and deterministic file discovery; do not import candidate modules.
2. Define an evidence model that distinguishes explicitly local qualified refs from unresolved/ambiguous names.
3. Emit errors only for provably local missing symbols; optionally mention nearest correct symbol as suggestion, not proof.
4. Handle import aliases where statically resolvable, and lazy loading under standard.

## Settings and parsing

**Proposed configuration fields:** code_paths: tuple[str,...] (default fallback to docsig_paths); local_module_prefixes: tuple[str,...] (default empty).

Config work includes updating `Config`, `_CONFIG_OPTIONS`, both TOML loading paths, documented defaults, bad-config tests, and the existing example config. A rule that requires explicit mappings/dictionaries must be idle with an honest pending/readiness explanation until configured; it cannot implicitly reinterpret every README as an API contract. Existing configs continue loading untouched.

## Work with the current implementation

- `engine.scan` currently calls fast/deep analyzers with two arguments and standard ones with three. Follow Story 01.0's uniform optional-context contract before introducing a rule whose behavior depends on programmatic `Config` overrides.
- Use the already-implemented code paths where appropriate: `discovery.py`, `rules.py`, `code_discovery.py`, `detectors/standard/corpus.py`, `deep_support.py`, and `baseline.py`; do not silently duplicate a heavyweight index.
- No new runtime libraries in `fast`; standard only loads on demand; deep remains explicitly opt-in/advisory. Non-LLM by default in every rule.
- Favor explainable measurements and evidence. Any approximation is documented as a **candidate** rather than an authoritative contradiction.

## Security, negative scope and boundary checks

Do not flag random `Foo.bar` as absent without proving it refers to in-repo Python code.

- Parse Markdown and Python source without executing it. Sanitize/normalize paths and reject scan-root escapes before I/O.
- Avoid reading generated fixture assets from the repository self-scan; fixture directories belong only to tests.
- No background agent, git invocation, secret file harvesting or remote request from a detector.

## Example Markdown test evidence


### Required fixture path examples

- Positive: `tests/assets/ds216/existing_public_function/README.md` — README refers to local package.module.process(), which exists.
- Negative: `tests/assets/ds216/removed_function_reference/README.md` — README refers to qualified local pkg.module.old_api(), absent from the symbol index.

The asset files are **required PR deliverables**. A rule implementation without those files and tests loading each case does not satisfy this story.


## Definition of done

- [ ] Rule registered exactly once, and selected/ignored predictably.
- [ ] Config options validated; default settings are conservative and backward compatible.
- [ ] Source line/provenance is preserved; reports are deterministic and privacy-conscious.
- [ ] Direct analyzer unit tests cover parser boundaries and specific error scenarios.
- [ ] Task 02 fixture tests prove no false positive on 3+ clean scenarios and detection on 3+ failing scenarios.
- [ ] README/architecture/rules output explains behavior and limitations.
