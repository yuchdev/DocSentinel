# Task 01 — implement DS114: Duplicate stable document identifiers

**Parent story:** [Story 12.0](/docs/roadmap/0005-deepening-test-case-stage-2/12.0-document-identity-uniqueness/README.md)  
**Proposed source:** `src/docsentinel/detectors/document_ids.py`  
**Rule identity:** `Rule(code="DS114", profile="fast", title="Duplicate stable document identifiers", severity="error")`.

## Required behavior and algorithm

1. Read only explicitly configured frontmatter identifiers using DS111-compatible scalar frontmatter parser.
2. Normalize values for whitespace and Unicode NFC; case sensitivity follows explicit config.
3. Detect collisions across multiple documents and attribute to later sorted document path with reference to original.
4. Do not treat repeated prose titles or headings as stable document IDs without explicit opt-in.
5. Malformed or absent frontmatter must not be silently conflated with duplicate IDs; delegate malformed metadata to DS111.

## Configuration additions and defaults

- `document_id_field = "id" (default)`
- `document_id_scope = "corpus" (default)`
- `document_id_case_sensitive = true (default)`
- `document_id_required = false (default: lack of an ID is DS111 policy)`

Config is project-local and strict. Add typed defaults, `_CONFIG_OPTIONS` recognition, enum/range validation, standalone `doc_sentinel.toml`, `[tool.doc_sentinel]` and injected `Config` tests. Merge with M4's actual config changes; avoid overwriting them. Config-independent checks should not require new setup.

## Explicit exclusions (false-positive safeguards)

- Two documents with same H1 but no id are allowed by default.
- IDs in Markdown examples or code blocks are not metadata.
- Duplicate IDs within one frontmatter document are primarily DS111; avoid contradictory dual diagnostics.

## Relationship to previously shipped or planned rules

- DS111 validates required metadata and duplicate frontmatter keys; DS114 validates corpus-wide uniqueness.
- DS104 local HTML anchor identity is separate namespace.

## Data and reporting contract

- Read **only** Markdown docs in `documents` and supported local companions; never execute code or fetch URLs.
- Use shared scanner and resolver from Story 01.0; parse byte-exact input with real source one-based line positions.
- Return `tuple[Finding, ...]` with `DS114` code, configured default severity, POSIX relative `path`, smallest meaningful `message` and appropriate `line` where available; keep stable path/line ordering and no duplicates.
- Preserve optional `config` on direct detector invocation and the engine context. When disabled/not applicable, announce truthful execution state through the shared status API; never assume empty findings == checked.
- Do not touch other profile dependencies or global model readiness.

## Unit/mocking requirements

- Test pure normalization/recognition rules with focused inline unit samples only; larger documentation input resides in committed Markdown assets.
- Test config defaults, invalid values, line spans, cross-file path normalization, repeated scans and no false alarms.
- Include safe negative tests for unreadable files, symlink/root escape, invalid UTF-8 and adversarial input when relevant. Document precise reason for inapplicable generic safety cases.
- Target at least one test for each algorithm bullet, exclusion and interaction stated above.

## Acceptance

- [ ] `DS114` appears exactly once in `RULES` and `ANALYZERS`, assigned `fast` and documented severity.
- [ ] No change to `DS101`–`DS103` public behavior unless intentionally documented, isolated and regression-tested.
- [ ] Only stdlib in new analyzer import graph.
- [ ] All new config options are validated and selectable from library, standalone TOML, and pyproject TOML.
- [ ] All fixtures in Task 02 execute under Task 03 integration tests and produce expected results.
- [ ] Missing/unsupported input is handled explicitly rather than emitting a false clean signal.
