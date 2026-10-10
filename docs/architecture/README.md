# Architecture and milestone boundaries

`config` validates local TOML input, `discovery` inventories files, `engine.scan`
orchestrates registered analyzers, and `reporting` presents the shared
`ScanResult` contract for the CLI and Python clients. Pytest support is opt-in
and calls the same engine.

Configuration discovery checks for a standalone `doc_sentinel.toml` at the scan
root first. Its keys are top-level. If that file is absent, DocSentinel reads
`[tool.doc_sentinel]` from a root-level `pyproject.toml`; otherwise it uses
defaults. An explicit configuration path bypasses discovery.

Rule codes use the `DS1xx` namespace for `fast`, `DS2xx` for `standard`, and
`DS3xx` for `deep`. Profiles are exact rather than cumulative. `select` accepts
exact codes or prefixes such as `DS1`; an empty list selects every rule in the
active profile. `ignore` uses the same matching and takes precedence over
`select`.

The registered [Story 02.0](../roadmap/0001-generic-implementation/02.0-fast-profile-structural-detectors/README.md)
`fast` rules are:

- `DS101` reports dangling Markdown links and anchors.
- `DS102` reports stray HTML comments.
- `DS103` reports unresolvable path-like inline code spans.

`standard` and `deep` remain unimplemented. The fast rules run locally; no
external service, network, or model is used.

## Schema versioning

`ScanResult` exposes a `schema_version` integer field (`1` in M0) as its first field, identifying the contract shape for JSON and text consumers.

Versioning policy: `schema_version` increments by exactly 1 whenever a field is removed, renamed, or has its *meaning* changed (not just added) in `ScanResult`'s JSON representation. Adding a new optional field with a sensible default does **not** require a bump - only breaking changes do. This mirrors semantic-versioning-for-data, not semantic-versioning-for-code.
