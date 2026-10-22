# DocSentinel

DocSentinel is a deterministic-first documentation quality assurance and static analysis framework for Markdown repositories and Python docstrings. It validates document integrity, cross-references, text quality, and docstring synchronization without sending sensitive document content across networks.

All three initial milestones are complete, providing a fully working command-line tool and Python library:

* **`fast` default profile:** Sub-second structural and reference checks using only the Python standard library 
  * `DS101` dangling links/anchors
  * `DS102` stray HTML comments
  * `DS103` unresolvable path-like code spans 
  * `DS104` conflicting heading and explicit anchors
  * `DS105` heading hierarchy and section levels
  * `DS106` empty or contentless sections
  * `DS108` reference-style link definition integrity (undefined or duplicated reference labels)
  * `DS109` malformed or unclosed fenced code blocks
  * `DS110` missing language labels on code fences (opt-in; off unless `require_fence_languages` is enabled)
  * `DS113` missing local media and document assets: Markdown images, HTML `<img>`/`<source>` `src`/`srcset`, HTML `<a href>`, and used reference-definition targets whose local file does not exist as a regular file inside the scan root (error severity). Images are checked regardless of extension; `asset_extensions` gates link-shaped references, the `check_*` toggles enable each reference kind, and `missing_asset_policy` (off/warn/error) downgrades or silences it. External URLs, `data:` URIs, templates, and root escapes (DS116's concern) are skipped
  * `DS116` references that escape the documentation root, such as parent-directory traversal, percent-encoded escapes, and Windows drive, UNC, or backslash paths (error severity). Links, images, reference definitions, and HTML `href`/`src`/`srcset` are checked at full strictness; inline code spans are documentation, so there DS116 reports only genuine traversal (a root escape or an in-root symlink pointing outside), leaving drive, UNC, backslash, and regex or escape snippets to DS103
  * `DS117` malformed GFM pipe-table structure
* **`standard` profile:** Corpus-level statistics and docstring synchronization via `docsentinel[standard]` 
  * `DS201` prose readability complexity
  * `DS202` paragraph duplication
  * `DS203` low-information content
  * `DS204` Python docstring-to-code signature mismatch)
* **`deep` profile:** Semantic NLP contradiction candidate analysis via `docsentinel[deep]`. Gated by explicit opt-in confirmation with advisory-only exit codes.
  * `DS301` fact-contradiction candidates across documents 

## Requirements and Installation

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/) (or standard `pip`).

```sh
# Core installation (fast profile)
pip install docsentinel

# or with uv
uv add docsentinel

# Standard profile (corpus stats & docstrings)
pip install "docsentinel[standard]"

# or with uv
uv add --extra standard docsentinel

# Deep profile (semantic contradiction detection)
pip install "docsentinel[deep]"
python -m spacy download en_core_web_sm
```

## Command-Line Usage

```sh
# Initialize starter doc_sentinel.toml configuration
uv run docsentinel init

# Run deterministic fast-profile scan on the current repository
uv run docsentinel scan

# Scan specific directories or files
uv run docsentinel scan docs/
uv run docsentinel scan docs/README.md

# Scan with standard or deep profile
uv run docsentinel scan --profile standard
uv run docsentinel scan --profile deep --i-understand-deep-is-heuristic

# Output formats: text (default), json, or github annotations
uv run docsentinel scan --format json
uv run docsentinel scan --format github

# Strict mode: fail on warnings as well as errors
uv run docsentinel scan --strict

# Baseline legacy findings to prevent build regressions
uv run docsentinel baseline . --output .docsentinel-baseline.json
uv run docsentinel scan --baseline .docsentinel-baseline.json

# Inspect active detection rules and diagnostic environment readiness
uv run docsentinel rules
uv run docsentinel doctor
```

### Exit Codes Contract

- `0` — Scan completed with no blocking findings (or advisory-only deep candidates).
- `1` — Scan found blocking errors (or warnings when `--strict` is enabled).
- `2` — Configuration error, invalid arguments, or filesystem scan failure.

## Configuration

DocSentinel loads configuration from `doc_sentinel.toml` at the scan root, or from the `[tool.doc_sentinel]` table in `pyproject.toml`:

```toml
# doc_sentinel.toml: keys at the top level, no table header.
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

# Deep profile opt-in confirmation (optional)
deep_confirm = false
```

Patterns match relative paths; exclude patterns also match directory names. Symlinked files are skipped for safety. Output order and document inventory are stable and deterministic.

## Python Library

The CLI and Python API share the same engine and frozen data models:

```python
from pathlib import Path
from docsentinel import Config, load_config, scan

# Quick scan with default settings
result = scan(".")

print(f"Profile: {result.profile}")
print(f"Documents scanned: {len(result.documents)}")
print(f"Findings: {len(result.findings)}")

for finding in result.findings:
    print(f"[{finding.severity.upper()}] {finding.rule} in {finding.path}:{finding.line} - {finding.message}")

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

- `docsentinel-fast`: Runs fast structural checks on every commit (zero extra dependencies).
- `docsentinel-standard`: Manual on-demand hook for standard corpus and signature analysis.

## Documentation and Resources

- [User Tutorial](docs/user/tutorial/README.md) — Comprehensive guide for CLI and Python library consumers.
- [Statistical Checks Reference](docs/user/reference/statistical-checks.md) — Full reference for the six standard-profile threshold keys (DS201–DS203).
- [Architecture](docs/architecture/README.md) — Architectural design, profile boundaries, and data contracts.
- [Roadmap](docs/roadmap/README.md) — Detailed milestone, story, and task specifications.
- [Contributing](CONTRIBUTING.md) — Development guidelines and validation commands.
