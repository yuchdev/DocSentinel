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

The fast rules run locally; no external service, network, or model is used.

The registered [Milestone 0002 Story 02.0](../roadmap/0002-standard-profile-detectors/02.0-text-complexity-detector/README.md),
[Milestone 0002 Story 03.0](../roadmap/0002-standard-profile-detectors/03.0-corpus-statistics-duplicate-and-low-information/README.md),
and [Milestone 0002 Story 04.0](../roadmap/0002-standard-profile-detectors/04.0-doc-vs-code-signature-mismatch/README.md)
`standard` rules are:

- `DS201` reports high text complexity when prose readability exceeds the configured grade level threshold (`warning`, evaluated using `textstat`). A single global `max_grade_level` threshold is supported; per-category thresholds are noted for future work.
- `DS202` reports duplicated text or facts across paragraph chunks using cosine similarity on a shared TF-IDF corpus model (`warning`, evaluated using `scikit-learn`).
- `DS203` reports low-information content paragraphs that are both lexically thin and non-distinctive (`warning`, evaluated using `scikit-learn` and `textstat`).
- `DS204` reports docstring and function signature mismatches (`error`, evaluated using `docsig`). It is the sole `standard` detector that reads Python source (via `code_discovery.discover_python` / `Config.docsig_paths`) rather than Markdown documents.

The registered [Milestone 0003 Story 02.0](../roadmap/0003-deep-profile-and-periodic-review/02.0-fact-contradiction-candidate-detector/README.md)
`deep` rule is:

- `DS301` reports fact-contradiction candidates across Markdown documents where differing numeric or named-entity claims are made about the same subject (`warning`, evaluated using `spacy` and `textacy`).

### Standard profile and optional dependencies

The `standard` profile detectors reside behind the optional `docsentinel[standard]` dependency group (including packages such as `scikit-learn`, `textstat`, and `docsig`). To keep the fast scan lightweight and free of heavy startup costs, standard detectors are isolated behind a lazy-loading boundary (`ensure_standard_loaded()`).

- **Lazy loading boundary:** The standard detectors package is imported only when `profile="standard"` is requested or when inspecting available rules via `rules` and `doctor`. Running `scan --profile fast` never imports or touches standard dependencies.
- **Graceful CLI degradation:** If `profile="standard"` is requested during a scan without the extra installed, the CLI fails cleanly with an actionable install error message and exit code `2` (no traceback). Diagnostic commands such as `docsentinel rules` and `docsentinel doctor` degrade gracefully: `rules` prints an installation guidance note for standard rules and exits `0`, while `doctor` explicitly reports whether the standard profile is available or uninstalled.
- **Milestone scope:** With Milestone 0002 complete, `DS201`–`DS204` are registered as standard detectors. With Milestone 0003 complete, `DS301` is registered as the deep profile candidate detector.

### Deep profile, opt-in gating, and periodic review

The `deep` profile registers one detector, `DS301` (fact-contradiction candidates). Because semantic SVO extraction is heuristic and expected to report false positives, the deep profile operates under strict safety and advisory boundaries:

- **Explicit opt-in confirmation gate:** Deep checks require explicit confirmation via `deep_confirm = true` in configuration, `--i-understand-deep-is-heuristic` on the CLI, or the `DOCSENTINEL_DEEP_CONFIRM=1` environment variable. Unconfirmed scans run zero deep analyzers and report an explanatory pending notice.
- **Optional dependencies and lazy pipeline loading:** Deep dependencies (`spacy`, `textacy`, and the `en_core_web_sm` model) live in the `docsentinel[deep]` extra and are loaded lazily only when a confirmed deep scan runs.
- **Advisory-only exit codes:** Deep findings are candidate generators for review. An exit code of `0` is always returned on deep scans (even under `--strict` or when findings are present), accompanied by an advisory report banner. Promoting deep findings to build failures (e.g. via `--fail-on-deep`) is deferred to future work.
- **Periodic review loop:** Deep review runs asynchronously on a weekly or on-demand cadence via the `/loop deep-review` loop driving the `docs-reviewer` agent, triaging candidates and auditing doc-vs-code behavioral drift without blocking commits or CI builds.

### CI and pre-commit hook policy for standard profile

The `fast` profile runs on every commit via the default `docsentinel-fast` pre-commit hook (stdlib-only, fast inventory and structural checks).

In contrast, the `standard` profile is designed as CI-and-on-demand rather than an every-commit blocker:

- **Local opt-in hook:** A separate `docsentinel-standard` hook is provided in `.pre-commit-hooks.yaml` configured with `stages: [manual]` and `additional_dependencies: ["docsentinel[standard]"]`. It runs only on explicit on-demand invocation (e.g. `pre-commit run docsentinel-standard --hook-stage manual`), ensuring contributors are not blocked by heavy optional dependencies or longer scan runtimes during standard git commits.
- **Dedicated CI lane:** Continuous integration runs `docsentinel scan . --profile standard --baseline .docsentinel-standard-baseline.json` with the `standard` extra installed.
- **Separate baseline files:** Standard findings are baselined separately in `.docsentinel-standard-baseline.json` (distinct from `.docsentinel-baseline.json`). This ensures the two profiles maintain disjoint fingerprints and can be adopted or baselined independently.
- **Non-blocking advisory warnings:** CI enforces standard scans without failing on advisory warnings (`DS201`–`DS203`), failing only on errors (`DS204`) or when `--strict` is explicitly configured.

## Schema versioning

`ScanResult` exposes a `schema_version` integer field (`1` in M0) as its first field, identifying the contract shape for JSON and text consumers.

Versioning policy: `schema_version` increments by exactly 1 whenever a field is removed, renamed, or has its *meaning* changed (not just added) in `ScanResult`'s JSON representation. Adding a new optional field with a sensible default does **not** require a bump - only breaking changes do. This mirrors semantic-versioning-for-data, not semantic-versioning-for-code.
