# Task 01 — Implement `DS107`: Orphan documentation

**Story:** [Story 02.0](/docs/roadmap/0004-deepening-test-cases/02.0-orphan-documentation/README.md) · **Rule:** `DS107` · **Profile:** `fast`

## Deliverable and location

Implement `src/docsentinel/detectors/orphans.py` (new module unless a preexisting equivalent is found during implementation). Register `Rule(code="DS107", profile="fast", severity="warning", ...)` through the existing rule registry, and bind exactly one detector under `ANALYZERS["DS107"]`. Preserve lazy imports and existing rule identities.

## Inputs and well-defined outputs

**Input source:** Markdown inventory, configured entrypoint paths, local Markdown link graph.

**Success:** a deterministic tuple of `Finding` objects with `rule="DS107"`, normalized repo-relative paths, correct 1-based lines (where known), evidence-focused messages and severity `warning`.

**Not evaluated:** Missing mandatory config, unsupported source construct, or missing scan context must not silently turn into an assertion that the documentation was checked and found clean. Emit a clear pending/readiness or validation outcome using the milestone's shared per-rule execution status mechanism. **Do not** abuse `Finding(severity="error")` to mean 'could not analyze'.

## Algorithm contract

Algorithm: (1) select inventoried Markdown and configured entrypoints; (2) parse only navigational local links, with DS101-compatible scan-root resolution; (3) resolve target to inventory nodes; (4) breadth-first traverse from roots, marking visited; (5) emit one orphan warning for each unvisited eligible node. A cycle can never create reachability without a path from an entrypoint. Missing all entrypoints is a readiness failure, not a finding per node. Optional graph helper returns node/edge provenance for DS316. Complexity target O(documents + links); build once per scan.

## Detailed implementation obligations

1. Implement a navigation graph keyed by canonical repository-relative paths; stable traversal, cycle detection and visited set.
2. Use shared link parsing for supported Markdown syntaxes, preserving DS101 behavior; add reference definitions only where supported with tests.
3. Warn only on inventoried Markdown files that are demonstrably unreachable; evidence identifies entrypoint set and target path.
4. Document that the default discovery of entrypoints is conservative and configurable.

## Settings and parsing

**Proposed configuration fields:** doc_entrypoints: tuple[str, ...] (default: README.md, docs/README.md if present; documented discovery); orphan_exclude: tuple[str, ...] (default empty).

Config work includes updating `Config`, `_CONFIG_OPTIONS`, both TOML loading paths, documented defaults, bad-config tests, and the existing example config. A rule that requires explicit mappings/dictionaries must be idle with an honest pending/readiness explanation until configured; it cannot implicitly reinterpret every README as an API contract. Existing configs continue loading untouched.

## Work with the current implementation

- `engine.scan` currently calls fast/deep analyzers with two arguments and standard ones with three. Follow Story 01.0's uniform optional-context contract before introducing a rule whose behavior depends on programmatic `Config` overrides.
- Use the already-implemented code paths where appropriate: `discovery.py`, `rules.py`, `code_discovery.py`, `detectors/standard/corpus.py`, `deep_support.py`, and `baseline.py`; do not silently duplicate a heavyweight index.
- No new runtime libraries in `fast`; standard only loads on demand; deep remains explicitly opt-in/advisory. Non-LLM by default in every rule.
- Favor explainable measurements and evidence. Any approximation is documented as a **candidate** rather than an authoritative contradiction.

## Security, negative scope and boundary checks

Do not mistake an unlinked source-code file for an orphan document. Missing entrypoints are not an excuse to mark all files orphaned.

- Parse Markdown and Python source without executing it. Sanitize/normalize paths and reject scan-root escapes before I/O.
- Avoid reading generated fixture assets from the repository self-scan; fixture directories belong only to tests.
- No background agent, git invocation, secret file harvesting or remote request from a detector.

## Example Markdown test evidence


### Required fixture path examples

- Positive: `tests/assets/ds107/reachable_from_index/README.md` — README links to docs/index.md, which links to docs/guide.md; all three reachable.
- Negative: `tests/assets/ds107/unlinked_guide_document/README.md` — README exists but docs/guide.md has no inbound reachable links: one finding at docs/guide.md.

The asset files are **required PR deliverables**. A rule implementation without those files and tests loading each case does not satisfy this story.


## Definition of done

- [ ] Rule registered exactly once, and selected/ignored predictably.
- [ ] Config options validated; default settings are conservative and backward compatible.
- [ ] Source line/provenance is preserved; reports are deterministic and privacy-conscious.
- [ ] Direct analyzer unit tests cover parser boundaries and specific error scenarios.
- [ ] Task 02 fixture tests prove no false positive on 3+ clean scenarios and detection on 3+ failing scenarios.
- [ ] README/architecture/rules output explains behavior and limitations.
