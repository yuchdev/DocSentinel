# DocSentinel

DocSentinel is a deterministic-first documentation quality assurance and static analysis framework for Markdown repositories and Python docstrings. It validates document integrity, cross-references, text quality, and docstring synchronization without sending sensitive document content across networks.

All three initial milestones are complete, providing a fully working command-line tool and Python library:

* **`fast` default profile:** Sub-second structural and reference checks; all 18 rules use only the Python standard library at scan time. Note: `pyproject.toml` lists `spacy` as a core runtime dependency (so every installation includes spaCy), but `import docsentinel` no longer imports spaCy at a module load and fast and standard profile scans never call any spaCy API. Whether to remove spaCy from the core dependencies is an open product decision; it does not affect scan correctness or the fast-profile runtime guarantee.
  * `DS100` unreadable document: a discovered document that cannot be read, is not a regular file or is not valid UTF-8 is skipped by every other rule, logged once as a warning and reported as one error finding (engine rule, emitted in every profile; `ignore = ["DS100"]` keeps only the warning)
  * `DS101` dangling links/anchors. A site-root-absolute target (one starting with `/`) resolves against the link root (`link_root`, default `auto`: the enclosing repository), not the filesystem root; the anchors of a linked file are checked only up to 1,000,000 characters (a larger or non-UTF-8 file skips the anchor check)
  * `DS102` stray HTML comments
  * `DS103` unresolvable path-like code spans (opt-in since 1.3.0; off unless `reference_scope = "strict"` or `--reference-scope strict`, and the scan notice says so; a `/`-rooted span resolves against the link root, as in DS101; spans starting with `@` are DS124's and DS116's)
  * `DS104` conflicting heading and explicit anchors
  * `DS105` heading hierarchy and section levels
  * `DS106` empty or contentless sections
  * `DS108` reference-style link definition integrity (undefined or duplicated reference labels)
  * `DS109` malformed or unclosed fenced code blocks
  * `DS110` missing language labels on code fences (opt-in; off unless `require_fence_languages` is enabled)
  * `DS112` declared documentation navigation integrity: within the Markdown indexes named by `navigation_indexes`, a navigation target linked more than once (`navigation_unique_targets`), a navigation link whose local destination does not exist (`navigation_check_missing`), a target that escapes the scan root, and a `navigation_required` document that no navigation link points at (warning severity; opt-in, off unless `navigation_indexes` is set). `/`-rooted targets resolve against the link root. A missing or unreadable configured index is a fail-closed readiness error (exit 2)
  * `DS113` missing local media and document assets: Markdown images, HTML `<img>`/`<source>` `src`/`srcset`, HTML `<a href>`, and used reference-definition targets whose local file does not exist as a regular file inside the scan root, or inside the link root for a `/`-rooted target (error severity). Images are checked regardless of extension; `asset_extensions` gates link-shaped references, the `check_*` toggles enable each reference kind, and `missing_asset_policy` (off/warn/error) downgrades or silences it. External URLs, `data:` URIs, templates, and root escapes (DS116's concern) are skipped
  * `DS114` duplicate stable document identifiers: two documents that declare the same stable frontmatter identity within `document_id_scope` (`corpus`/`directory`), reading only the configured `document_id_field` (default `id`); values are normalized to Unicode NFC with whitespace collapsed, and case-folded when `document_id_case_sensitive` is false, while `document_id_required` additionally flags each document lacking an identity (error severity). Malformed metadata (an unterminated block or duplicate id key) is left to metadata validation and stays silent, but an unsupported value shape of the configured field yields one explicit finding
  * `DS115` deprecated names and migrated references: in-scope textual occurrences of names explicitly mapped as deprecated in the TOML mapping named by `deprecated_references_file`, with the suggested replacement and the mapping provenance (warning severity; opt-in, off unless `deprecated_references_file` is set). `prose` and `identifier` matches (over prose and inline code) are gated by `deprecated_check_prose`, `link` matches (over local link targets, lexical only — existence stays DS101's concern) by `deprecated_check_links`, and `deprecated_case_sensitive` governs the case; fenced code and an explicit `scope` exemption keep historical examples clean. A missing, out-of-root, or schema-invalid mapping (including a conflicting duplicate entry) is a fail-closed readiness error (exit 2)
  * `DS116` references that escape the documentation root, such as parent-directory traversal, percent-encoded escapes, and Windows drive, UNC, or backslash paths (error severity). Links, images, reference definitions, and HTML `href`/`src`/`srcset` are checked at full strictness; inline code spans are documentation, so there DS116 reports only genuine traversal (a root escape or an in-root symlink pointing outside), leaving drive, UNC, backslash, and regex or escape snippets to DS103 (opt-in, strict scope only). A `/`-rooted target inside the link root is not an escape, even when it lies outside the scan root; one whose `..` climbs above the link root is
  * `DS117` malformed GFM pipe-table structure
  * `DS118` documentation file and directory naming policy: discovered document paths whose components do not match the portable-ASCII style named by `documentation_naming` (`kebab`/`snake`), with a deterministic suggested rename (warning severity; opt-in, off unless `documentation_naming` selects a style). `documentation_naming_allow` (default `README.md`/`index.md`) and `documentation_naming_prefix_patterns` (numeric ADR prefixes and similar) exempt conventional names, and `documentation_naming_directories` scopes whether directory components are checked. It is a pure path-string policy: it reads no document content, touches no filesystem, and never renames a file
  * `DS124` dangling `@`-document mentions, the way agent prompts name files (`@docs/README.md` in prose, or a whole inline code span): a mention whose extension is in `at_reference_extensions` and that resolves neither against the scan root nor, as a fallback, the link root is reported (warning severity, always active). `@~/...` and `@/...` mentions are never resolved; a mention that escapes the scan root is a `DS116` error; a target is never opened
* **`standard` profile:** Corpus-level statistics and docstring synchronization via `docsentinel[standard]` 
  * `DS201` prose readability complexity
  * `DS202` paragraph duplication
  * `DS203` low-information content
  * `DS204` Python docstring-to-code signature mismatch
* **`deep` profile:** Semantic NLP contradiction candidate analysis via `docsentinel[deep]`. Heuristic, with advisory-only exit codes.
  * `DS301` fact-contradiction candidates across documents 
  * `DS302` external fact-check disagreement: a high-salience claim sentence that a third-party fact-checking service rates false or mixed (warning severity, advisory only). **It sends claim sentences from your documents to a third party** and is off until you give both `--use-external-api` (or `DOCSENTINEL_USE_EXTERNAL_API=1`) and the backend's API key variable (`DOCSENTINEL_FACTCHECK_LENZ_API_KEY` for `lenz`, falling back to `LENZ_API_KEY`); neither is a configuration key. Verdicts are third-party heuristic output, not ground truth. Preview what would be sent, offline, with `docsentinel extract-facts`. Never use the flag in pre-commit `args:` or a `pull_request_target` workflow, or export the key for a whole CI job

## Requirements and Installation

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/) (or standard `pip`).

```sh
# Everything: fast, standard and deep profiles
pip install docsentinel

# or with uv
uv add docsentinel

# The deep profile also needs its spaCy model (one-time download)
python -m spacy download en_core_web_sm
```

The profile extras `docsentinel[fast]`, `docsentinel[standard]` and `docsentinel[deep]` select a
profile by name (for example `pip install "docsentinel[fast]"`). They are aliases: pip extras can
only add dependencies, so they do **not** make the installation lighter - every profile's dependencies
are already part of a plain `pip install docsentinel`.

pip cannot run code after an installation, so the starter configuration is a separate, explicit step:

```sh
docsentinel init                  # create docsentinel.toml in the current directory
docsentinel init path/to/dir      # ... or in a specific directory
docsentinel init --project-root   # ... or next to the nearest uv.lock / pyproject.toml
```

In a terminal, `init` asks for confirmation first; pass `--yes` to skip the prompt. It never
overwrites an existing file.

`docsentinel init --user` creates your personal settings file instead (see
[User settings](#user-settings)).

## Command-Line Usage

```sh
# Initialize starter docsentinel.toml configuration
uv run docsentinel init
uv run docsentinel init --user     # ... or your user settings file (~/.local/share/docsentinel/settings.json)

# Run deterministic fast-profile scan on the current repository
uv run docsentinel scan

# Scan specific directories or files
uv run docsentinel scan docs/
uv run docsentinel scan docs/README.md

# Scan with standard or deep profile
uv run docsentinel scan --profile standard
uv run docsentinel scan --profile deep

# Preview, offline, the claims DS302 would send to a fact-check service (no network, no key)
uv run docsentinel extract-facts docs
# DS302 itself needs --use-external-api AND a key in the environment; see docs/user/tutorial/cli.md

# Output formats: text (default), json (schema 2), json-v1 (old schema 1), json-documents, github annotations
uv run docsentinel scan --format json
uv run docsentinel scan --format json-v1   # the schema-1 bytes that --format json produced before 1.2.0
uv run docsentinel scan --format github    # use this one in GitHub Actions
uv run docsentinel scan --template my-report.json   # your own template, wins over --format
# Writing a template or an extension: docs/user/tutorial/custom-reports.md
uv run docsentinel scan --format json -o reports/scan.json   # write the report to a file

# Base for site-root-absolute (/) links; trusted, wins over the link_root config key
uv run docsentinel scan docs --link-root .

# Select documents: --include replaces the configured include, --exclude is appended (relative to the scan root)
uv run docsentinel scan . --include docs/user --exclude docs/archive

# Also check path-like inline code spans (DS103, opt-in); overrides reference_scope
uv run docsentinel scan --reference-scope strict

# Strict mode: fail on warnings as well as errors
uv run docsentinel scan --strict

# Baseline legacy findings to prevent build regressions
uv run docsentinel baseline . --output .docsentinel-baseline.json
uv run docsentinel scan --baseline .docsentinel-baseline.json

# More or less progress output on stderr (the report on stdout is unchanged)
uv run docsentinel -v scan docs/     # DEBUG detail
uv run docsentinel scan docs/ -q     # warnings and errors only

# Inspect active detection rules and diagnostic environment readiness
uv run docsentinel rules
uv run docsentinel doctor

# Ignore the user settings file for one run (scan, baseline and doctor accept it)
uv run docsentinel scan --no-user-settings
uv run docsentinel scan --config ci/docsentinel.json   # explicit JSON project configuration
```

### Exit Codes Contract

- `0` — Scan completed with no blocking findings (or advisory-only deep candidates).
- `1` — Scan found blocking errors (or warnings when `--strict` is enabled). An unreadable or non-UTF-8 document is a blocking `DS100` error.
- `2` — Configuration error, invalid arguments, or filesystem scan failure.

Every CLI run writes a per-run log file (default ~/.local/logs/docsentinel/, set `DOCSENTINEL_LOG_DIR`
to change it) and, on exit `1` or `2`, the last stderr line names it. See
[the CLI tutorial](docs/user/tutorial/cli.md#logging--v--q-and-the-per-run-log-file) and the
[logging spec](docs/specs/logging.md).

## Configuration

Settings come from four layers, lowest first: the built-in defaults, your [user settings](#user-settings) file, the project configuration, and command-line flags. The project configuration is `docsentinel.toml` (or the equivalent alias `doc_sentinel.toml`) at the scan root, or the `[tool.doc_sentinel]` table in `pyproject.toml`, or a JSON file named with `--config FILE.json` (JSON is never discovered):

```toml
# docsentinel.toml: keys at the top level, no table header.
# In pyproject.toml put the same keys under a [tool.doc_sentinel] table instead.
profile = "fast"
include = ["*.md", "**/*.md"]
exclude = [".git", ".venv", "node_modules", "dist"]
select = []
ignore = []
baseline = ".docsentinel-baseline.json"

# Standard profile thresholds (optional)
max_grade_level = 14.0          # DS201: flag prose above this readability grade
duplicate_similarity = 0.85     # DS202: flag paragraph pairs at/above this cosine similarity
min_information_score = 0.15    # DS203: flag paragraphs scoring below this information score
docsig_paths = ["src"]          # DS204: Python source roots checked against docstrings

# Standard profile statistical size limits (optional)
min_document_words = 50         # DS201: skip documents with fewer prose words
min_paragraph_words = 5         # DS202/DS203: skip paragraphs with fewer words
min_paragraph_chars = 30        # DS202/DS203: skip paragraphs shorter than this

# DS302 external fact-check (deep profile; sends claim sentences to a third party). Defaults shown.
# These only tune it: it also needs --use-external-api and an API key in the environment,
# which are never configuration keys. See the configuration reference.
# fact_check_backend = "lenz"
# fact_check_min_salience = 0.5
# fact_check_min_confidence = 0.6
# fact_check_max_claims_per_document = 3
# fact_check_max_claims_total = 25
# fact_check_time_budget_seconds = 300
# fact_check_combination = "each"   # or "all", or ranges such as "1-6,7-8,9-16"

# Base for /-rooted links (DS101, DS103, DS112, DS113, DS116, DS124). "auto" = the nearest
# .git ancestor, else the scan root; use "." for untrusted content nested in another checkout
link_root = "auto"

# Which references are checked: "links" (links and @-mentions, default) or "strict"
# (also path-like code spans, DS103). See the reference-scope section of the configuration reference.
reference_scope = "links"
at_reference_extensions = ["md", "markdown", "mdx", "txt", "rst", "toml", "json", "yaml", "yml", "py"]   # DS124
```

### User settings

A personal JSON file sets defaults for every repository you scan, for example `{"profile": "fast", "reference_scope": "strict"}`. It lives at `~/.local/share/docsentinel/settings.json` (under `$XDG_DATA_HOME` when set), or at the absolute path in `DOCSENTINEL_SETTINGS`; `docsentinel init --user` creates it, and `--no-user-settings` or `DOCSENTINEL_SETTINGS=off` ignores it. Options that name repository files or choose what a repository scans (`baseline`, `include`, `exclude`, `docsig_paths`, `navigation_indexes`, `navigation_required`, `deprecated_references_file`, `report_templates_dir`, `link_root`, `telemetry_domains`) are refused there. On POSIX the file and its directories must be owned by you or root and not writable by group or others, or the run exits `2` (fix with `chmod go-w`). **In CI, set `DOCSENTINEL_SETTINGS=off` at job level**, especially on self-hosted runners. Details: [How to set options](docs/user/reference/configuration.md#how-to-set-options).

Patterns match relative paths; exclude patterns also match directory names. A value without `*`, `?` or `[` is a literal that names a file or a directory and everything below it (a directory include admits only `.md` files); `scan --include` and `--exclude` (and `scan(include=, exclude=)`) take the same values, `--include` replacing and `--exclude` appending to the configured lists. See [Selection options](docs/user/reference/configuration.md#selection-options-include-and-exclude) and the [`link_root` reference](docs/user/reference/configuration.md#link_root) for the bounds on a configured ancestor. Symlinked files are skipped for safety. Output order and document inventory are stable and deterministic.

## Python Library

The CLI and Python API share the same engine and frozen data models:

```python
from pathlib import Path
from docsentinel import Config, load_config, load_config_with_sources, scan

# Quick scan with default settings
result = scan(".")

print(f"Profile: {result.profile}")
print(f"Documents scanned: {len(result.documents)}")
print(f"Findings: {len(result.findings)}")

for finding in result.findings:
    print(f"[{finding.severity.upper()}] {finding.rule} in {finding.path}:{finding.line} - {finding.message}")

# Layered configuration: defaults, then your user settings, then the project file
config = load_config(Path("."))                      # load_config(Path("."), user_settings=False) skips the user file
config, sources = load_config_with_sources(Path(".")) # sources: where each layer came from (option names only)

# Programmatic scan with explicit configuration
config = Config(
    profile="standard",
    select=("DS201", "DS204"),
    docsig_paths=("src",),
)
result = scan(".", config=config)
```

## Pytest Integration

DocSentinel includes an opt-in pytest plugin exposing the `docsentinel_scan` fixture:

```sh
uv run pytest -p docsentinel.pytest_plugin
```

```python
def test_documentation_integrity(docsentinel_scan):
    result = docsentinel_scan(".")
    assert not [f for f in result.findings if f.severity == "error"]
```

## Pre-commit Integration

DocSentinel provides pre-commit hooks in `.pre-commit-hooks.yaml`:

- `docsentinel-fast`: Runs fast structural checks on every commit (fast rules use stdlib only at run time; `pyproject.toml` lists `spacy` as a core dependency but spaCy is not imported during fast or standard scans — see the [dependency note](docs/user/tutorial/README.md#dependency-note) in the tutorial).
- `docsentinel-standard`: Manual on-demand hook for standard corpus and signature analysis.

## Documentation and Resources

- [User Tutorial](docs/user/tutorial/README.md) — Comprehensive guide for CLI and Python library consumers.
- [Statistical Checks Reference](docs/user/reference/statistical-checks.md) — Full reference for the six standard-profile threshold keys (DS201–DS203).
- [Rules](docs/user/reference/rules.md) — The single table of all 21 checks: profile, severity, activation, fault class and config keys (drift-tested against the code).
- [Configuration Reference](docs/user/reference/configuration.md) — All fast-profile policy options for DS104–DS118, with defaults and valid values.
- [Architecture](docs/architecture/README.md) — Architectural design, profile boundaries, and data contracts.
- [Markdown Scanner Guide](docs/dev/markdown_scanner.md) — Developer guide for adding rules, resolver ownership, and the security checklist.
- [Roadmap](docs/roadmap/README.md) — Detailed milestone, story, and task specifications.
- [Contributing](CONTRIBUTING.md) — Development guidelines and validation commands.
