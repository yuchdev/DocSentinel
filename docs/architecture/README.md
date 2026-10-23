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
`reference_label_normalization`), the asset options (`asset_extensions`,
`check_html_asset_tags`, `check_markdown_images`, `check_srcset`, `missing_asset_policy`)
the navigation options (`navigation_indexes`, `navigation_required`,
`navigation_unique_targets`, `navigation_check_missing`) and the
document-identity options (`document_id_field`, `document_id_scope`,
`document_id_case_sensitive`, `document_id_required`), the
deprecated-reference options (`deprecated_references_file`, `deprecated_check_prose`,
`deprecated_check_links`, `deprecated_case_sensitive`) and the documentation-naming
options (`documentation_naming`, `documentation_naming_allow`,
`documentation_naming_directories`, `documentation_naming_prefix_patterns`)
are consumed, by
`DS109`, `DS110`, `DS105`, `DS104`, `DS106`, `DS117`, `DS116`, `DS108`, `DS113`, `DS112`, `DS114`, `DS115` and `DS118`; with `DS118` registered, every Milestone 0005 typed policy option is now consumed by a registered rule. A `Config` injected by a library caller still wins over any discovered file.

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
- `DS112` reports declared documentation navigation integrity problems (warning severity), via the shared scanner and resolver in `markdown_blocks.py`. It is an optional policy, off by default: it emits nothing unless `navigation_indexes` names one or more index documents, and additionally consumes `navigation_required`, `navigation_unique_targets` (default on) and `navigation_check_missing` (default on). For each configured index it scopes navigation to links on list items derived over the scanner's masked text (R1), reports a navigation target linked more than once (`navigation_unique_targets`), a navigation link whose local destination does not exist (`navigation_check_missing`, `os.stat` only), and a target that escapes the scan root (reported lexically with zero filesystem access, an intentional overlap with DS116). Across indexes it reports a `navigation_required` document that no navigation link points at. The README's "appear exactly once" contract is realised as the union of the presence check (`navigation_required`) and the uniqueness check (`navigation_unique_targets`, default on), not a single coupled rule. A missing, unreadable, non-regular, out-of-root, or non-discovered configured index is a fail-closed `ConfigError` (readiness error, CLI exit 2), never a finding and never a silent clean result. It echoes only a bounded, repr-escaped copy of the author's raw target or configured path, never a resolved path; see the standing [DS112 threat model](../security/threat-model-ds112-navigation-integrity-2026-10-23.md).
- `DS113` reports local media and document assets that do not exist as a regular file inside the scan root, via the shared scanner and resolver in `markdown_blocks.py`. It is an always-active fast rule at `error` severity (blocking) and consumes `asset_extensions`, `check_html_asset_tags`, `check_markdown_images`, `check_srcset`, and `missing_asset_policy` (off/warn/error, default error). It validates Markdown images, HTML `<img>`/`<source>` `src`/`srcset`, HTML `<a href>`, and used reference-definition targets: images are checked regardless of extension, while `asset_extensions` (case-insensitive) gates only link-shaped references so it does not re-prove ordinary `.md` links (DS101's concern). It reuses `is_ds116_owned`/`escapes_via_symlink` to defer every DS116-owned or in-root symlink-out target to `DS116` (never stats an escape) and decides existence/type with `os.stat`+`S_ISREG` only, never opening content, so a committed FIFO, device, socket, or directory is a non-regular-file finding without being read. It echoes only a bounded, repr-escaped copy of the author's raw target, never a resolved path; see the standing [DS113 threat model](../security/threat-model-ds113-missing-assets-2026-10-23.md).
- `DS114` reports duplicate stable document identifiers (error severity, blocking). It is an always-active fast rule that, unlike the other Milestone 0005 fast rules, carries its own minimal, bounded, standard-library-only frontmatter reader rather than the shared `markdown_blocks.py` scanner (Milestone 0004's `DS111` metadata rule is not in this tree). It reads only the configured `document_id_field` (default `id`) from each document's opening YAML frontmatter, normalizes values to Unicode NFC with whitespace collapsed, case-folds when `document_id_case_sensitive` is false, enforces uniqueness within `document_id_scope` (`corpus`/`directory`), and flags each document lacking an identity when `document_id_required` is set. It stays completely silent for `DS111`-owned malformed metadata (an unterminated or over-long opening block, or a duplicate id key) but, when the configured field is present once in a well-formed block with an unsupported value shape (flow collection, anchor/alias/tag, block scalar, nested mapping/sequence, or unterminated quoted scalar), emits one explicit finding at the field's line and excludes that document from collision detection — a finding, never a `ConfigError`, so one odd document never aborts the whole scan with exit 2. It reads only the bounded head of each in-root document, never follows a reference, and echoes only a bounded, repr-escaped identity, original path, or field name, never a raw value or resolved path.
- `DS115` reports in-scope textual occurrences of explicitly deprecated names and migrated references (warning severity), via the shared scanner's masked views in `markdown_blocks.py` plus `tomllib`. It is an optional policy, off by default: it emits nothing unless `deprecated_references_file` names a root-contained TOML mapping of `[[replacement]]` entries (`old`, `new`, `kind` from the closed enum `prose`/`link`/`identifier`, optional `scope` globs including `!`-prefixed excludes for the historical-archive exemption). When set it matches each mapped `old` token literally with whole-token boundaries (never compiled as a user regex, so `APIv1` never matches inside `APIv10`) over the substrate the `kind` selects: `prose` over the masked physical lines, `identifier` over inline-code span text, and `link` over local link and reference-definition targets — matched lexically with **zero** filesystem probing of the target, since existence is DS101's concern and root escape DS116's. `deprecated_check_prose` gates prose/identifier, `deprecated_check_links` gates links, and `deprecated_case_sensitive` governs the single case policy (NFC normalization on both sides, no NFKC/confusable folding; DS115 reports literal occurrences and never chases a replacement chain, so cycles are inert). A missing, unreadable, non-regular, out-of-root, oversized, unparseable, or schema-invalid mapping — including a cross-entry duplicate/conflicting `old` — is a fail-closed `ConfigError` (readiness error, CLI exit 2), never a finding and never a silent clean result; the configured mapping path is re-validated defensively (DS116 containment + `S_ISREG` + size cap) before any open because an injected `Config` bypasses `load_config`. It reuses the shared resolver only for string identity and echoes only a bounded, repr-escaped copy of the configured path, matched token, and suggested replacement, never a resolved path or the raw `tomllib` text; see the standing [DS115 threat model](../security/threat-model-ds115-deprecated-references-2026-10-23.md).
- `DS116` reports documentation references whose target escapes the configured scan root, via the shared resolver in `markdown_blocks.py`. It is an always-active fast rule at `error` severity (blocking) and consumes `root_escape_policy` (off/warn/error), `decode_percent_paths`, and `windows_path_policy`. Its scope differs by reference kind (Story 11.0 code-span ruling): links, image sources, reference definitions, and HTML `href`/`src`/`srcset` are checked at full strictness and `DS101` delegates all unsafe link targets to `DS116` via `is_ds116_owned` instead of resolving or stat-ing them; inline **code spans** are documentation, so there `DS116` reports only genuine traversal (a lexical root escape, its percent-encoded and residual-encoding forms, or an in-root symlink pointing outside) and leaves drive, UNC, backslash, control, and regex or escape snippets to `DS103`, which keeps its exact pre-Story-11 behaviour for them and skips only the root-escape and symlink-out code spans `DS116` owns. The shared `ResolvedReference.reason` field carries the typed sub-category (`drive`, `unc`, `backslash`, `control`, `template`, `glob`) that lets `DS116` separate unsafe targets from safe ones. The detector never reads a path outside the root and echoes only a bounded, repr-escaped copy of the author's raw target, never a resolved path; see the standing [DS116 threat model](../security/threat-model-ds116-path-boundaries-2026-10-22.md), including its "Rulings during implementation" section.
- `DS117` reports malformed GFM pipe-table structure (inconsistent cell counts or malformed alignment markers, warning severity), via the same scanner's fence mask. It is an always-active fast rule and consumes `table_dialect`, `table_strict_cells` and `table_enable` (it emits nothing when `table_enable` is false or `table_dialect` names an unsupported dialect).
- `DS118` reports documentation file and directory naming-policy violations (warning severity). Unlike every other fast rule it is a **pure path-string policy**: it reads neither the shared `markdown_blocks.py` scanner nor the filesystem (no `open`/`stat`/`realpath`) and never reads document content, deciding entirely from each discovered document's relative POSIX path. It is an optional policy, off by default: it emits nothing unless `documentation_naming` selects a style (`kebab` = lowercase ASCII words joined by single hyphens, `snake` = by single underscores), and additionally consumes `documentation_naming_allow` (exact filename or whole-path exemptions, default `README.md`/`index.md`), `documentation_naming_prefix_patterns` (a restricted, bounded literal/`?`/`*` glob subset, never a user regex, for numeric ADR prefixes and similar) and `documentation_naming_directories` (whether directory components are checked). Each offending component is reported once (directories outermost-first, then the file) with a deterministic, ASCII, policy-conformant suggested rename; it never renames a file, so DS101 remains responsible for any link a later user rename breaks. The offending name is echoed bounded and `unicode_escape`-ed, and an injected `Config` with an unrecognised style or out-of-bounds prefix patterns fails closed with a `ConfigError`.

## Opt-in policy rules

Some rules implement an *opt-in policy* that is inert until a project configures it (`DS110`, `DS112`, `DS115`, and `DS118`). To keep diagnostic honesty, `rules.Rule` carries an optional `opt_in_option` field naming the `Config` option that switches the policy on (empty for ordinary always-active rules); `rules.opt_in_satisfied(rule, config)` returns whether that option is set to an enabling value (truthy and not the string `"off"`, covering boolean, tuple, and string option shapes). Opt-in status is reported, never hidden:

- `ScanResult.notice` counts only genuinely evaluated rules and names any active opt-in rule whose policy is off, e.g. `12 fast rule(s) evaluated; opt-in rule(s) not enabled: DS110 (set require_fence_languages), DS112 (set navigation_indexes), DS115 (set deprecated_references_file), DS118 (set documentation_naming).`. The `ScanResult` dataclass shape, JSON schema v1, exit codes, and `enabled_rules` semantics are unchanged (selection stays orthogonal to whether an opt-in policy fires).
- `docsentinel rules` marks such a rule `DS110: Missing language labels on code fences [opt-in: set require_fence_languages]`, `DS112: Declared documentation navigation integrity [opt-in: set navigation_indexes]` `DS115: Deprecated names and migrated references [opt-in: set deprecated_references_file]` and `DS118: Documentation file and directory naming policy [opt-in: set documentation_naming]`.
- `docsentinel doctor` counts them separately, e.g. `fast rules: 16 registered (4 opt-in, off unless configured: DS110, DS112, DS115, DS118)`.

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
