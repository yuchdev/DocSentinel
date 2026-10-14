# Task 01 — Implement `DS316`: Documentation change impact

**Story:** [Story 13.0](/docs/roadmap/0004-deepening-test-cases/13.0-documentation-change-impact/README.md) · **Rule:** `DS316` · **Profile:** `deep`

## Deliverable and location

Implement `src/docsentinel/detectors/impact.py` (new module unless a preexisting equivalent is found during implementation). Register `Rule(code="DS316", profile="deep", severity="warning", ...)` through the existing rule registry, and bind exactly one detector under `ANALYZERS["DS316"]`. Preserve lazy imports and existing rule identities.

## Inputs and well-defined outputs

**Input source:** Explicit changed-files list from CLI/API, document-to-source reference graph, optional mapping.

**Success:** a deterministic tuple of `Finding` objects with `rule="DS316"`, normalized repo-relative paths, correct 1-based lines (where known), evidence-focused messages and severity `warning`.

**Not evaluated:** Missing mandatory config, unsupported source construct, or missing scan context must not silently turn into an assertion that the documentation was checked and found clean. Emit a clear pending/readiness or validation outcome using the milestone's shared per-rule execution status mechanism. **Do not** abuse `Finding(severity="error")` to mean 'could not analyze'.

## Algorithm contract

Algorithm: receive explicit `changed_paths` at scan-time or `--changed-file` on CLI; normalize names to scan-root POSIX paths, disallow escapes, keep deleted paths as identifiers. Build doc-to-code reference graph from explicit local Markdown links, symbol index and curated mappings. Find touched source nodes and bounded reverse-reachable document nodes; emit unique affected-document recommendations including the matching path(s) and evidence kind. If changed set omitted, do not evaluate the rule. Do not run git or infer semantic code behavior.

## Detailed implementation obligations

1. Extend the public scan interface with immutable normalized changed_paths and repeatable CLI `--changed-file` without altering callers that omit it.
2. Build evidence graph for Markdown local source links, documented symbol references and optional explicit dependency mapping.
3. Emit one document-level candidate per source/impact path with provenance; de-duplicate edges and cycles.
4. Keep DS316 advisory and independent of spaCy when selected alone, preserving explicit deep opt-in.

## Settings and parsing

**Proposed configuration fields:** Runtime scan(changed_paths=...) keyword and CLI --changed-file PATH repeatable; optional impact_mapping_file for curated edges.

Config work includes updating `Config`, `_CONFIG_OPTIONS`, both TOML loading paths, documented defaults, bad-config tests, and the existing example config. A rule that requires explicit mappings/dictionaries must be idle with an honest pending/readiness explanation until configured; it cannot implicitly reinterpret every README as an API contract. Existing configs continue loading untouched.

## Work with the current implementation

- `engine.scan` currently calls fast/deep analyzers with two arguments and standard ones with three. Follow Story 01.0's uniform optional-context contract before introducing a rule whose behavior depends on programmatic `Config` overrides.
- Use the already-implemented code paths where appropriate: `discovery.py`, `rules.py`, `code_discovery.py`, `detectors/standard/corpus.py`, `deep_support.py`, and `baseline.py`; do not silently duplicate a heavyweight index.
- No new runtime libraries in `fast`; standard only loads on demand; deep remains explicitly opt-in/advisory. Non-LLM by default in every rule.
- Favor explainable measurements and evidence. Any approximation is documented as a **candidate** rather than an authoritative contradiction.

## Security, negative scope and boundary checks

Do not flag a document as stale; report “review recommended because X changed”, with explicit evidence.

- Parse Markdown and Python source without executing it. Sanitize/normalize paths and reject scan-root escapes before I/O.
- Avoid reading generated fixture assets from the repository self-scan; fixture directories belong only to tests.
- No background agent, git invocation, secret file harvesting or remote request from a detector.

## Example Markdown test evidence


### Required fixture path examples

- Positive: `tests/assets/ds316/unrelated_source_change/README.md` — Changed unrelated module has no mapped documentation references.
- Negative: `tests/assets/ds316/changed_linked_source_file/README.md` — README links to src/tool.py and it is in changed set: one advisory finding.

The asset files are **required PR deliverables**. A rule implementation without those files and tests loading each case does not satisfy this story.


## Definition of done

- [ ] Rule registered exactly once, and selected/ignored predictably.
- [ ] Config options validated; default settings are conservative and backward compatible.
- [ ] Source line/provenance is preserved; reports are deterministic and privacy-conscious.
- [ ] Direct analyzer unit tests cover parser boundaries and specific error scenarios.
- [ ] Task 02 fixture tests prove no false positive on 3+ clean scenarios and detection on 3+ failing scenarios.
- [ ] README/architecture/rules output explains behavior and limitations.
