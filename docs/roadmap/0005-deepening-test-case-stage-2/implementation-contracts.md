# Milestone 0005 — implementation contracts (normative)

## A. Audited master baseline and dependency gate

- Audited public repository `yuchdev/DocSentinel`, master tree/commit **`48ddf303b6f9b87c901833b29e8d75ffa3543950`**, authored 2026-10-14. This is a *planning snapshot*, not a statement that 0004 features have shipped.
- Latest master contains the **specification** `docs/roadmap/0004-deepening-test-cases/`, but its code tree still has implementations of DS101–103, DS201–204, DS301 only. **Do not assume DS107/DS111/DS119 or the 0004 shared scanner/context exist yet.**
- Before implementing Story 01.0, re-read the then-current `master`; if Milestone 0004 has since landed, reuse its `Analyzer` signature, fixture catalog, scanner and status capability; if not, either implement 0004 shared preconditions first or isolate new work behind a minimal compatibility adapter. Never build a competing analyzer dispatch graph.
- Python **3.12+**, uv, Hatchling; package/CLI `docsentinel`, standalone config `doc_sentinel.toml`, pyproject namespace `[tool.doc_sentinel]`. Do not switch to `.docsentinel.toml`.
- Exact (not cumulative) `fast`, `standard`, `deep` profiles; `select`/`ignore` prefixes, `ScanResult` schema versioning, baselines, no implicit heavy dependencies. Fast-profile runtime imports **standard library only**, regardless of extras installed. Existing package base dependencies do not justify adding a new runtime dependency for these rules.
- Existing `tests/assets/` convention and the `asset_case(rule, scenario)` pytest fixture remain authoritative. Self-scan excludes intentionally broken test assets.

## B. Test assets are mandatory source artifacts

**For every DS104/105/106/108/109/110/112/113/114/115/116/117/118 case named in `fixture-matrix.*`:**

1. Commit a directory `tests/assets/dsNNN/{two_to_four_word_snake_slug}/` containing at least one nonempty Markdown document. For one-file cases use `README.md`; multiple-file cases use descriptive `a.md`, `b.md`, `docs/index.md`, or `docs/guide.md`. The slug must have **2–4 real English words**. Do not rename the specified paths without updating all matrix formats and tests atomically.
2. The fixtures are text *input*, not screenshots or tests written only inside Python code. Include supporting `.toml`, `.py`, and small **real** `.svg` when needed for reference scenarios. Binary-file presence may be created via tiny deterministic runtime bytes; file content for tested Markdown remains committed.
3. The `markdown_assets` matrix column is exact. **Do not use a dummy README that accidentally triggers the detector.** Edge cases marked `runtime-symlink-companion` must commit a Markdown owner file; create only the filesystem symlink in the test via `tmp_path` (Git symlink behavior differs across Windows/OS).
4. Every clean scenario asserts **zero findings of its own rule**. Every finding scenario asserts code, path, severity, useful message substring and one-based line when a source span is available; no silent pass for an unregistered/disabled rule. `error` scenarios must assert the expected exception or scan `pending`/failure status rather than treating no findings as success.
5. Add test references for *every* case via `asset_case("dsNNN", "slug")`; parameterization is encouraged but expected behavior must be explicit in a checked manifest. Test file suffix `_dsNNN`; preserve `tests/unit`, `tests/mock`, `tests/integration` taxonomy and `pytest -p docsentinel.pytest_plugin` compatibility.
6. When tests need config, supply `Config` or a `doc_sentinel.toml` after asset copy; assert effective config reaches analyzer. Tests may vary thresholds, but the primary Markdown payload always comes from committed assets. A fixture's `setup` column describes required overrides/companions.
7. Preserve deliberately malformed Markdown byte-for-byte. Do not run markdown-formatting auto-fixers over `tests/assets/`.
8. Test each fixture *in isolation* in a clean temp directory to avoid shared indexes and overwriting `README.md` when composing different asset cases.

## C. Shared, stdlib-only Markdown block analysis

A **minimal Markdown block index** is justified here because seven new fast checks otherwise reimplement incompatible fence/heading/inline masking. Build a shared internal module such as `src/docsentinel/markdown_blocks.py` or extend the equivalent 0004 module **without introducing a third-party Markdown parser in fast imports**.

Supported baseline: ATX headings, setext headings, fenced code markers, HTML comments, inline code runs, reference-style link definitions, GFM-style pipe tables, Markdown images/links and supported basic HTML anchor/image tags. Preserve original text offsets, normalized POSIX relative paths and **one-based line numbers**, including CRLF and no-final-newline inputs.

The shared scanner must:
- Run in time proportional to source size for ordinary input; avoid catastrophic regular expressions and quadratic span masking. Consider a per-document token cache keyed by root+content or stat+mtime+size with safe invalidation; never cache only by basename.
- Expose structured `Heading`, `Fence`, `ReferenceDefinition`, `ReferenceUse`, `TableRow`, `LocalReference` tokens with source range and a parser-capability reason when a construct cannot be validated.
- Treat unmatched fences conservatively: DS109 reports the malformed fence; unrelated rules must not scan the swallowed content as active Markdown.
- Never execute embedded code, import Markdown-linked source, fetch URLs, or follow symlinks outside root.
- Unit-test Unicode, long lines, CRLF, delimiter escapes, deeply nested blocks, and adversarial unmatched markers.
- Publish a concise supported-Markdown-dialect document; **do not claim full CommonMark or complete GFM conformance** without a conformance suite.

## D. Config and scanning semantics

- Add validated typed config options to existing `Config` and known option allowlist; honor both standalone `doc_sentinel.toml` and `[tool.doc_sentinel]`; reject unknown/invalid types, out-of-root mapping paths and ambiguous configurations.
- Existing M4 preferred analyzer contract is `detect(root, documents, config: Config|None=None)` with engine always passing effective config, while preserving `detect(root, documents)` compatibility. Inspect M4 implementation before selecting final dispatch; do not overwrite M4 work.
- Optional policy-dependent rules **DS110, DS112, DS115, DS118** must be disabled or explicitly *not applicable* with clear execution status if no user config exists. They must **not** silently imply an audit of rules that were never evaluated. If per-rule execution metadata from M4 is unavailable, add it in compatibility layer with a stable schema migration policy.
- Paths from Markdown must be treated as untrusted: normalize under resolved scan root; avoid direct I/O on a path before validating containment and symlinks. Do not import scripts from the current repo into distributed runtime.
- Never modify `.docsentinel-baseline.json` or `.docsentinel-standard-baseline.json` merely to make tests green. If new fast checks produce legitimate findings on self-scan, propose a reviewed minimal baseline change with justification.
- Keep rule codes permanent and registered exactly once; registry `rules`, CLI `scan`, `rules`, `doctor`, baseline, text/json/github formats, pytest plugin and pre-commit must all agree.

## E. Cross-rule ownership and false positives

- **DS101** resolves ordinary local links/anchors; **DS104** diagnoses explicit anchor identity collisions; **DS108** diagnoses reference-definition identity; **DS112** checks designated navigation policy; **DS113** checks image/media assets; **DS116** detects unsafe root escapes. Preserve DS101's current behavior and document intentional overlap until a vetted dedup adapter is implemented.
- **DS105** heading hierarchy; **DS106** contentless leaf sections; **DS109** malformed fences; **DS110** missing fence language; **DS117** tables. Shared token rules must not cascade multiple findings from one malformed fence.
- **DS111 (M4)** metadata keys; **DS114** corpus-unique declared document identity. **DS119 (M4)** visible TODO markers; **DS115** explicitly mapped deprecated names; **DS118** path naming only. Avoid conflating quality/policy checks.
- Exclude `tests/assets` from self-scan and style lints as master currently does. Do not suppress actual detector failures by broadening arbitrary ignore patterns.

## F. CI, security, and performance acceptance

- Python unit/mock/integration tests; CLI E2E and library tests; exact-profile and selection/ignore tests; stable JSON schema and line/path outputs.
- Run isolated fast installation import test with optional `standard`/`deep` dependencies absent; `docsentinel scan --profile fast` must not import `spacy`, `textacy`, `sklearn`, `docsig` or network clients.
- Adversarial inputs: nested `../` and percent encoding, Windows UNC/drives, symlinks, unreadable files, invalid UTF-8, oversized fenced regions, tables with many escaped delimiters, repeated references, Unicode normalization and case sensitivity.
- Measure the existing DS101–103 scan baseline before/after; do not advertise sub-second for arbitrarily large corpora. Demonstrate O(total bytes) scanner and bounded overhead on a representative corpus, publishing environment and measurements.
- Do not persist raw private document content in reports; show only smallest snippets required for diagnostics and use existing redaction rules.
- No incomplete/TODO test implementations, no `.skip`/`.xfail` to hide regressions; dependency-specific skips only for existing DS301 model tests.
- Update `docs/roadmap/README.md` and milestone `status.md` honestly after merges; add docs to `docs/architecture/README.md`, `docs/user/tutorial/`, `README.md`, config example and development/test coverage docs.
