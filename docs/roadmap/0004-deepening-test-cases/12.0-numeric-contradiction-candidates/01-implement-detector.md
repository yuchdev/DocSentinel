# Task 01 — Implement `DS302`: Numeric contradiction candidates

**Story:** [Story 12.0](/docs/roadmap/0004-deepening-test-cases/12.0-numeric-contradiction-candidates/README.md) · **Rule:** `DS302` · **Profile:** `deep`

## Deliverable and location

Implement `src/docsentinel/detectors/numeric_claims.py` (new module unless a preexisting equivalent is found during implementation). Register `Rule(code="DS302", profile="deep", severity="warning", ...)` through the existing rule registry, and bind exactly one detector under `ANALYZERS["DS302"]`. Preserve lazy imports and existing rule identities.

## Inputs and well-defined outputs

**Input source:** Visible Markdown sentences and tables containing comparable numeric assertions, optional scope annotation.

**Success:** a deterministic tuple of `Finding` objects with `rule="DS302"`, normalized repo-relative paths, correct 1-based lines (where known), evidence-focused messages and severity `warning`.

**Not evaluated:** Missing mandatory config, unsupported source construct, or missing scan context must not silently turn into an assertion that the documentation was checked and found clean. Emit a clear pending/readiness or validation outcome using the milestone's shared per-rule execution status mechanism. **Do not** abuse `Finding(severity="error")` to mean 'could not analyze'.

## Algorithm contract

Algorithm: extract prose numeric assertions anchored to subject/property and operator (equal, at least, at most, exclusive bounds, range), unit/dimension and scope (version/environment/default/max). Normalize recognized numbers and dimension-compatible units; compare constraints only when referent AND scope match. Determine disagreement by disjoint solution sets; a shared compatible interval is not a contradiction. Emit potential conflicting pairs with both document references and an explicit candidate label. Detecting phrases remains heuristic even when arithmetic is deterministic.

## Detailed implementation obligations

1. Create a normalized numeric claim model with subject, property, comparator, value/range, unit dimension, scope, provenance.
2. Use explicit comparison logic for equality, bounds and ranges, with known unit conversions only.
3. Preserve distinction between default, maximum, recommended and versioned scopes; avoid DS301 false positives.
4. Require deep confirmation but do not require spaCy model when only DS302 is active; deep findings remain warning/advisory.

## Settings and parsing

**Proposed configuration fields:** numeric_claim_min_tokens: int; numeric_scope_tags: tuple[str,...] optional; no external API config.

Config work includes updating `Config`, `_CONFIG_OPTIONS`, both TOML loading paths, documented defaults, bad-config tests, and the existing example config. A rule that requires explicit mappings/dictionaries must be idle with an honest pending/readiness explanation until configured; it cannot implicitly reinterpret every README as an API contract. Existing configs continue loading untouched.

## Work with the current implementation

- `engine.scan` currently calls fast/deep analyzers with two arguments and standard ones with three. Follow Story 01.0's uniform optional-context contract before introducing a rule whose behavior depends on programmatic `Config` overrides.
- Use the already-implemented code paths where appropriate: `discovery.py`, `rules.py`, `code_discovery.py`, `detectors/standard/corpus.py`, `deep_support.py`, and `baseline.py`; do not silently duplicate a heavyweight index.
- No new runtime libraries in `fast`; standard only loads on demand; deep remains explicitly opt-in/advisory. Non-LLM by default in every rule.
- Favor explainable measurements and evidence. Any approximation is documented as a **candidate** rather than an authoritative contradiction.

## Security, negative scope and boundary checks

Every result is a candidate, not a proven fact; exclude equations, examples, years and code when not tied to a clear subject/property.

- Parse Markdown and Python source without executing it. Sanitize/normalize paths and reject scan-root escapes before I/O.
- Avoid reading generated fixture assets from the repository self-scan; fixture directories belong only to tests.
- No background agent, git invocation, secret file harvesting or remote request from a detector.

## Example Markdown test evidence


### Required fixture path examples

- Positive: `tests/assets/ds302/consistent_worker_limits/a.md` — Two docs assert maximum workers=8 for same version/context.
- Negative: `tests/assets/ds302/conflicting_worker_maxima/a.md` — Two docs assert max concurrent workers=8 versus 16 for identical scope.

The asset files are **required PR deliverables**. A rule implementation without those files and tests loading each case does not satisfy this story.


## Definition of done

- [ ] Rule registered exactly once, and selected/ignored predictably.
- [ ] Config options validated; default settings are conservative and backward compatible.
- [ ] Source line/provenance is preserved; reports are deterministic and privacy-conscious.
- [ ] Direct analyzer unit tests cover parser boundaries and specific error scenarios.
- [ ] Task 02 fixture tests prove no false positive on 3+ clean scenarios and detection on 3+ failing scenarios.
- [ ] README/architecture/rules output explains behavior and limitations.
