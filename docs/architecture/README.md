# Architecture and milestone boundaries

`config` validates local TOML input, `discovery` inventories files, `engine.scan`
orchestrates registered analyzers (forwarding the effective `Config` to any analyzer that declares a third `config` parameter, while the two-argument `detect(root, documents)` form remains supported), and `reporting` presents the shared
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

Milestone 0005 adds a block of typed, validated policy options to `Config`
(for example `heading_level_policy`, `first_heading_level`,
`allowed_fence_languages`, `navigation_indexes`, `root_escape_policy`,
`document_id_field`, `deprecated_references_file`, and `documentation_naming`).
They load from both the standalone `doc_sentinel.toml` and the
`[tool.doc_sentinel]` table, keep strict unknown-key rejection, validate enums,
positive/non-negative integers, nonempty string lists, and reject path options
that escape the scan root. These options are plumbing for the Milestone 0005
fast checks. So far only the fence options (`fence_dialect`,
`report_stray_closing_fence`), the fence-language policy options
(`require_fence_languages`, `allow_unlabelled_empty_fences`,
`allowed_fence_languages`), the heading options (`heading_level_policy`,
`first_heading_level`, `multiple_h1_policy`, `setext_heading_support`) and the
anchor options (`anchor_collision_policy`, `anchor_renderer`), the empty-section
options (`empty_section_policy`, `placeholder_content_policy`, `image_content_counts`,
`empty_section_min_text_chars`), the table options (`table_dialect`,
`table_strict_cells`, `table_enable`), the path-boundary options
(`root_escape_policy`, `decode_percent_paths`, `windows_path_policy`), the reference
options (`unused_reference_definitions`, `duplicate_reference_definitions`,
`reference_label_normalization`) and the asset options (`asset_extensions`,
`check_html_asset_tags`, `check_markdown_images`, `check_srcset`, `missing_asset_policy`)
are consumed, by
`DS109`, `DS110`, `DS105`, `DS104`, `DS106`, `DS117`, `DS116`, `DS108` and `DS113`; the remaining options are not yet consumed by
any registered rule. A `Config` injected by a library caller still wins over any discovered file.

The registered [Story 02.0](../roadmap/0001-generic-implementation/02.0-fast-profile-structural-detectors/README.md)
`fast` rules are:

- `DS101` reports dangling Markdown links and anchors.
- `DS102` reports stray HTML comments.
- `DS103` reports unresolvable path-like inline code spans.
- `DS104` reports conflicting heading and explicit anchors (an explicit HTML anchor repeating another or shadowing a generated heading anchor), via the shared `markdown_blocks.py` scanner.
- `DS105` reports heading-level skips and a first heading that violates `first_heading_level` (optionally multiple H1s), via the shared `markdown_blocks.py` scanner.
- `DS106` reports empty or contentless leaf sections (a heading whose body has no visible, publishable content), via the shared `markdown_blocks.py` scanner.
- `DS108` reports reference-style link definition integrity problems (warning severity), via the same scanner's fence, inline-code, and comment masks. It is an always-active fast rule that checks reference *identifiers* and *definitions*, never target existence (DS101's concern): it flags undefined full `[text][label]` and collapsed `[label][]` references, flags each duplicate definition after the first (gated by `duplicate_reference_definitions`, off/warn/error), and flags unused definitions only when `unused_reference_definitions` is enabled. Labels are normalized under the `commonmark` `reference_label_normalization` dialect; shortcut `[label]` uses, escaped brackets, footnotes, inline links, and masked regions are never reported.
- `DS109` reports unclosed or malformed fenced code blocks (error severity), via the same scanner.
- `DS110` reports meaningful fenced code blocks that omit the language label required by policy (warning severity), via the same scanner. It is an optional policy, off by default: it reuses DS109's fence tokens and emits nothing unless `require_fence_languages` is enabled, and additionally consumes `allow_unlabelled_empty_fences` and `allowed_fence_languages` (plus `fence_dialect`, which gates whether it emits at all).
- `DS113` reports local media and document assets that do not exist as a regular file inside the scan root, via the shared scanner and resolver in `markdown_blocks.py`. It is an always-active fast rule at `error` severity (blocking) and consumes `asset_extensions`, `check_html_asset_tags`, `check_markdown_images`, `check_srcset`, and `missing_asset_policy` (off/warn/error, default error). It validates Markdown images, HTML `<img>`/`<source>` `src`/`srcset`, HTML `<a href>`, and used reference-definition targets: images are checked regardless of extension, while `asset_extensions` (case-insensitive) gates only link-shaped references so it does not re-prove ordinary `.md` links (DS101's concern). It reuses `is_ds116_owned`/`escapes_via_symlink` to defer every DS116-owned or in-root symlink-out target to `DS116` (never stats an escape) and decides existence/type with `os.stat`+`S_ISREG` only, never opening content, so a committed FIFO, device, socket, or directory is a non-regular-file finding without being read. It echoes only a bounded, repr-escaped copy of the author's raw target, never a resolved path; see the standing [DS113 threat model](../security/threat-model-ds113-missing-assets-2026-10-23.md).
- `DS116` reports documentation references whose target escapes the configured scan root, via the shared resolver in `markdown_blocks.py`. It is an always-active fast rule at `error` severity (blocking) and consumes `root_escape_policy` (off/warn/error), `decode_percent_paths`, and `windows_path_policy`. Its scope differs by reference kind (Story 11.0 code-span ruling): links, image sources, reference definitions, and HTML `href`/`src`/`srcset` are checked at full strictness and `DS101` delegates all unsafe link targets to `DS116` via `is_ds116_owned` instead of resolving or stat-ing them; inline **code spans** are documentation, so there `DS116` reports only genuine traversal (a lexical root escape, its percent-encoded and residual-encoding forms, or an in-root symlink pointing outside) and leaves drive, UNC, backslash, control, and regex or escape snippets to `DS103`, which keeps its exact pre-Story-11 behaviour for them and skips only the root-escape and symlink-out code spans `DS116` owns. The shared `ResolvedReference.reason` field carries the typed sub-category (`drive`, `unc`, `backslash`, `control`, `template`, `glob`) that lets `DS116` separate unsafe targets from safe ones. The detector never reads a path outside the root and echoes only a bounded, repr-escaped copy of the author's raw target, never a resolved path; see the standing [DS116 threat model](../security/threat-model-ds116-path-boundaries-2026-10-22.md), including its "Rulings during implementation" section.
- `DS117` reports malformed GFM pipe-table structure (inconsistent cell counts or malformed alignment markers, warning severity), via the same scanner's fence mask. It is an always-active fast rule and consumes `table_dialect`, `table_strict_cells` and `table_enable` (it emits nothing when `table_enable` is false or `table_dialect` names an unsupported dialect).

## Opt-in policy rules

Some rules implement an *opt-in policy* that is inert until a project configures it (`DS110` today; `DS112`, `DS115`, `DS118` later). To keep diagnostic honesty, `rules.Rule` carries an optional `opt_in_option` field naming the `Config` option that switches the policy on (empty for ordinary always-active rules); `rules.opt_in_satisfied(rule, config)` returns whether that option is set to an enabling value (truthy and not the string `"off"`, covering boolean, tuple, and string option shapes). Opt-in status is reported, never hidden:

- `ScanResult.notice` counts only genuinely evaluated rules and names any active opt-in rule whose policy is off, e.g. `11 fast rule(s) evaluated; opt-in rule(s) not enabled: DS110 (set require_fence_languages).`. The `ScanResult` dataclass shape, JSON schema v1, exit codes, and `enabled_rules` semantics are unchanged (selection stays orthogonal to whether an opt-in policy fires).
- `docsentinel rules` marks such a rule `DS110: Missing language labels on code fences [opt-in: set require_fence_languages]`.
- `docsentinel doctor` counts them separately, e.g. `fast rules: 12 registered (1 opt-in, off unless configured: DS110)`.

The fast rules run locally; no external service, network, or model is used.

The registered [Milestone 0002 Story 02.0](../roadmap/0002-standard-profile-detectors/02.0-text-complexity-detector/README.md),
[Milestone 0002 Story 03.0](../roadmap/0002-standard-profile-detectors/03.0-corpus-statistics-duplicate-and-low-information/README.md),
and [Milestone 0002 Story 04.0](../roadmap/0002-standard-profile-detectors/04.0-doc-vs-code-signature-mismatch/README.md)
`standard` rules are:

- `DS201` reports high text complexity when prose readability exceeds the configured grade level threshold (`warning`, evaluated using `textstat`). A single global `max_grade_level` threshold is supported; per-category thresholds are noted for future work. Documents with fewer prose words than `min_document_words` (int >= 1, default 50) are skipped.
- `DS202` reports duplicated text or facts across paragraph chunks using cosine similarity on a shared TF-IDF corpus model (`warning`, evaluated using `scikit-learn`).
- `DS203` reports low-information content paragraphs that are both lexically thin and non-distinctive (`warning`, evaluated using `scikit-learn` and `textstat`).
- Standard-profile size limits: `DS202` and `DS203` draw from the shared paragraph corpus, which skips paragraphs below either `min_paragraph_words` (int >= 1, default 5) or `min_paragraph_chars` (int >= 0, default 30). The two floors are part of the `build_corpus_model` memoization key so distinct settings never reuse a stale corpus within a process. The TF-IDF vectoriser settings, the `DS203` normalisation references, and the `DS201` Flesch-Kincaid metric are fixed calibration internals and are not configurable. All defaults reproduce historical behaviour byte-for-byte.
- `DS204` reports docstring and function signature mismatches (`error`, evaluated using `docsig`). It is the sole `standard` detector that reads Python source (via `code_discovery.discover_python` / `Config.docsig_paths`) rather than Markdown documents.

The registered [Milestone 0003 Story 02.0](../roadmap/0003-deep-profile-and-periodic-review/02.0-fact-contradiction-candidate-detector/README.md)
`deep` rule is:

- `DS301` reports fact-contradiction candidates across Markdown documents where differing numeric or named-entity claims are made about the same subject (`warning`, evaluated using `spacy` and `textacy`).

## Standard profile and optional dependencies

The `standard` profile detectors reside behind the optional `docsentinel[standard]` dependency group (including packages such as `scikit-learn`, `textstat`, and `docsig`). To keep the fast scan lightweight and free of heavy startup costs, standard detectors are isolated behind a lazy-loading boundary (`ensure_standard_loaded()`).

- **Lazy loading boundary:** The standard detectors package is imported only when `profile="standard"` is requested or when inspecting available rules via `rules` and `doctor`. Running `scan --profile fast` never imports or touches standard dependencies.
- **Graceful CLI degradation:** If `profile="standard"` is requested during a scan without the extra installed, the CLI fails cleanly with an actionable install error message and exit code `2` (no traceback). Diagnostic commands such as `docsentinel rules` and `docsentinel doctor` degrade gracefully: `rules` prints an installation guidance note for standard rules and exits `0`, while `doctor` explicitly reports whether the standard profile is available or uninstalled.
- **Milestone scope:** With Milestone 0002 complete, `DS201`–`DS204` are registered as standard detectors. With Milestone 0003 complete, `DS301` is registered as the deep profile candidate detector.

## Deep profile, opt-in gating, and periodic review

The `deep` profile registers one detector, `DS301` (fact-contradiction candidates). Because semantic SVO extraction is heuristic and expected to report false positives, the deep profile operates under strict safety and advisory boundaries:

- **Explicit opt-in confirmation gate:** Deep checks require explicit confirmation via `deep_confirm = true` in configuration, `--i-understand-deep-is-heuristic` on the CLI, or the `DOCSENTINEL_DEEP_CONFIRM=1` environment variable. Unconfirmed scans run zero deep analyzers and report an explanatory pending notice.
- **Optional dependencies and lazy pipeline loading:** Deep dependencies (`spacy`, `textacy`, and the `en_core_web_sm` model) live in the `docsentinel[deep]` extra and are loaded lazily only when a confirmed deep scan runs.
- **Advisory-only exit codes:** Deep findings are candidate generators for review. An exit code of `0` is always returned on deep scans (even under `--strict` or when findings are present), accompanied by an advisory report banner. Promoting deep findings to build failures (e.g. via `--fail-on-deep`) is deferred to future work.
- **Periodic review loop:** Deep review runs asynchronously on a weekly or on-demand cadence via the `/loop deep-review` loop driving the `docs-reviewer` agent, triaging candidates and auditing doc-vs-code behavioral drift without blocking commits or CI builds.

## CI and pre-commit hook policy for standard profile

The `fast` profile runs on every commit via the default `docsentinel-fast` pre-commit hook (stdlib-only, fast inventory and structural checks).

In contrast, the `standard` profile is designed as CI-and-on-demand rather than an every-commit blocker:

- **Local opt-in hook:** A separate `docsentinel-standard` hook is provided in `.pre-commit-hooks.yaml` configured with `stages: [manual]` and `additional_dependencies: ["docsentinel[standard]"]`. It runs only on explicit on-demand invocation (e.g. `pre-commit run docsentinel-standard --hook-stage manual`), ensuring contributors are not blocked by heavy optional dependencies or longer scan runtimes during standard git commits.
- **Dedicated CI lane:** Continuous integration runs `docsentinel scan . --profile standard --baseline .docsentinel-standard-baseline.json` with the `standard` extra installed.
- **Separate baseline files:** Standard findings are baselined separately in `.docsentinel-standard-baseline.json` (distinct from `.docsentinel-baseline.json`). This ensures the two profiles maintain disjoint fingerprints and can be adopted or baselined independently.
- **Non-blocking advisory warnings:** CI enforces standard scans without failing on advisory warnings (`DS201`–`DS203`), failing only on errors (`DS204`) or when `--strict` is explicitly configured.

## Schema versioning

`ScanResult` exposes a `schema_version` integer field (`1` in M0) as its first field, identifying the contract shape for JSON and text consumers.

Versioning policy: `schema_version` increments by exactly 1 whenever a field is removed, renamed, or has its *meaning* changed (not just added) in `ScanResult`'s JSON representation. Adding a new optional field with a sensible default does **not** require a bump - only breaking changes do. This mirrors semantic-versioning-for-data, not semantic-versioning-for-code.
