# Using DocSentinel as an Executable (CLI)

The `docsentinel` command-line tool provides fast, deterministic documentation linting and static analysis for local development and CI/CD pipelines.

---

## Command Overview

DocSentinel provides the following CLI subcommands:

| Command | Purpose |
|---------|---------|
| `docsentinel scan` | Analyze Markdown documents and report findings |
| `docsentinel baseline` | Capture current findings into a baseline file to suppress legacy issues |
| `docsentinel init` | Create a starter `doc_sentinel.toml` configuration file |
| `docsentinel rules` | List all available and active rules per profile |
| `docsentinel doctor` | Diagnose environment readiness and optional dependency installations |

---

## Scanning Documents (`docsentinel scan`)

The `scan` command is the primary entry point for documentation validation.

### Basic Invocations

```bash
# Scan the current repository with default settings
docsentinel scan

# Scan a specific directory
docsentinel scan docs/

# Scan a single Markdown file
docsentinel scan docs/README.md
```

### Analysis Profiles

DocSentinel supports three distinct profiles via `--profile`:

#### 1. Fast Profile (`--profile fast`) - Default

Runs structural and reference rules. All rules use only the Python standard
library. Sixteen rules are registered; twelve are evaluated by default (four are
opt-in policies that are silent until their option is set):

| Rule | Severity | Description | Opt-in option |
|------|----------|-------------|---------------|
| `DS101` | error | Dangling link or anchor (missing target file) | — |
| `DS102` | warning | Stray HTML comment | — |
| `DS103` | warning | Unresolvable path-like inline code span | — |
| `DS104` | warning | Conflicting heading and explicit anchors | — |
| `DS105` | warning | Heading-level skip or wrong first heading | — |
| `DS106` | warning | Empty or contentless leaf section | — |
| `DS108` | warning | Reference-style link definition integrity | — |
| `DS109` | error | Malformed or unclosed fenced code block | — |
| `DS110` | warning | Missing language label on a code fence | `require_fence_languages` |
| `DS112` | warning | Declared documentation navigation integrity | `navigation_indexes` |
| `DS113` | error | Missing local media or document asset | — |
| `DS114` | error | Duplicate stable document identifier | — |
| `DS115` | warning | Deprecated name or migrated reference | `deprecated_references_file` |
| `DS116` | error | Reference escaping the documentation root | — |
| `DS117` | warning | Malformed GFM pipe-table structure | — |
| `DS118` | warning | Documentation file or directory naming violation | `documentation_naming` |

```bash
docsentinel scan --profile fast
```

**Opt-in rules.** `DS110`, `DS112`, `DS115`, and `DS118` are inert until you set
their enabling option. The scan notice reports exactly which ones are off:

```
12 fast rule(s) evaluated; opt-in rule(s) not enabled: DS110 (set require_fence_languages), DS112 (set navigation_indexes), DS115 (set deprecated_references_file), DS118 (set documentation_naming).
```

To enable an opt-in rule, set its option in `doc_sentinel.toml` (see
[Configuration Reference](../reference/configuration.md)):

```toml
# Enable DS110: require a language label on every non-empty code fence.
require_fence_languages = true

# Enable DS118: enforce kebab-case file and directory names.
documentation_naming = "kebab"
```

#### 2. Standard Profile (`--profile standard`)
Runs statistical corpus detectors and docstring synchronization:
- `DS201`: Text readability complexity exceeds threshold
- `DS202`: Duplicate text across documents (cosine similarity check)
- `DS203`: Low information content (short/boilerplate files)
- `DS204`: Docstring parameter/return mismatch against Python code signatures

```bash
docsentinel scan --profile standard
```

#### 3. Deep Profile (`--profile deep`)
Runs deep heuristic NLP analysis (`DS301` fact-contradiction candidate detector). Deep checks are heuristic, compute-intensive, and require explicit confirmation:

```bash
docsentinel scan --profile deep --i-understand-deep-is-heuristic
# or via environment variable
DOCSENTINEL_DEEP_CONFIRM=1 docsentinel scan --profile deep
```

---

## Filtering Rules: `--select` and `--ignore`

You can restrict or exclude specific rules using comma-separated rule codes or prefixes:

```bash
# Only run rule DS101 and DS103
docsentinel scan --select DS101,DS103

# Run all DS2xx standard rules
docsentinel scan --profile standard --select DS2

# Exclude comment checks (DS102)
docsentinel scan --ignore DS102
```

---

## Output Formats: `--format`

DocSentinel supports three output renderers:

### 1. Human-Readable Text (`--format text`) - Default

Prints an inventory table, rule status notices, and a categorized list of findings:

```bash
docsentinel scan --format text
```

### 2. Structured JSON (`--format json`)

Outputs a JSON object adhering to Schema v1, ideal for programmatic consumers:

```bash
docsentinel scan --format json
```

Example JSON payload:
```json
{
  "schema_version": 1,
  "profile": "fast",
  "documents": [
    {"path": "docs/README.md", "bytes": 1420}
  ],
  "findings": [
    {
      "rule": "DS101",
      "path": "docs/README.md",
      "message": "broken relative link: missing-file.md",
      "severity": "error",
      "line": 42
    }
  ],
  "enabled_rules": [
    "DS101", "DS102", "DS103", "DS104", "DS105", "DS106",
    "DS108", "DS109", "DS110", "DS112", "DS113", "DS114",
    "DS115", "DS116", "DS117", "DS118"
  ],
  "pending": [],
  "notice": "12 fast rule(s) evaluated; opt-in rule(s) not enabled: DS110 (set require_fence_languages), DS112 (set navigation_indexes), DS115 (set deprecated_references_file), DS118 (set documentation_naming)."
}
```

`enabled_rules` lists every rule selected in the active profile (selection is
orthogonal to whether an opt-in policy fires). `notice` separately names the
opt-in rules that are selected but currently silent.

### 3. GitHub Actions Annotations (`--format github`)

Formats findings directly as GitHub Actions workflow commands (`::error` and `::warning`):

```bash
docsentinel scan --format github
```

---

## Strict Mode and Exit Codes

### Exit Code Rules

| Exit Code | Meaning |
|-----------|---------|
| `0` | Clean run (no error-level findings, or deep advisory findings) |
| `1` | One or more error-level findings detected (or any warnings when `--strict` is enabled) |
| `2` | Configuration error, invalid CLI flags, or filesystem scan failure |

### Strict Mode (`--strict`)

By default, warning-level findings do not fail the build (exit code `0`). Use `--strict` to elevate all findings to build-failing conditions (exit code `1`):

```bash
docsentinel scan --strict
```

*Note: Deep profile findings (`DS301`) are heuristic candidates and advisory-only; they always return exit code `0` to avoid blocking CI pipelines.*

---

## Baselines: Suppressing Existing Debt (`docsentinel baseline`)

When introducing DocSentinel to an existing project with legacy issues:

### 1. Generate the Baseline

```bash
# Capture fast profile findings
docsentinel baseline --output .docsentinel-baseline.json

# Capture standard profile findings
docsentinel baseline --profile standard --output .docsentinel-standard-baseline.json
```

### 2. Run Scans with Baseline Filtering

```bash
docsentinel scan --baseline .docsentinel-baseline.json
```

All existing issues recorded in `.docsentinel-baseline.json` are suppressed. The scan will only report and fail on new issues introduced in subsequent commits.

---

## Environment Diagnostics (`docsentinel doctor`)

Verify which profiles, dependencies, and language models are ready on your machine:

```bash
docsentinel doctor
```

Example output:
```text
Inventory: available
standard profile: available
deep profile: not ready
  ✓ deep libraries installed (spacy, textacy)
  ✗ deep model missing (en_core_web_sm): python -m spacy download en_core_web_sm
fast rules: 16 registered (4 opt-in, off unless configured: DS110, DS112, DS115, DS118)
standard rules: 4 registered
deep rules: 1 registered
```

The deep profile requires an additional model download even after
`pip install "docsentinel[deep]"`:

```bash
python -m spacy download en_core_web_sm
```

---

## Listing Rules (`docsentinel rules`)

Inspect all registered detection rules across profiles:

```bash
docsentinel rules
```

---

## Project Configuration (`docsentinel init`)

Generate a starter `doc_sentinel.toml` configuration:

```bash
docsentinel init
```

Created `doc_sentinel.toml`:
```toml
profile = "fast"
include = ["*.md", "**/*.md"]
exclude = [".git", ".venv", "node_modules"]
select = []
ignore = []

# Standard profile thresholds (profile = "standard"); defaults shown.
# max_grade_level = 14.0          # DS201: flag prose above this readability grade
# duplicate_similarity = 0.85     # DS202: flag paragraph pairs at/above this cosine similarity
# min_information_score = 0.15    # DS203: flag paragraphs scoring below this information score
# docsig_paths = ["src"]          # DS204: Python source roots checked against docstrings
#
# Statistical size limits (standard profile); defaults shown.
# min_document_words = 50         # DS201: skip documents with fewer prose words
# min_paragraph_words = 5         # DS202/DS203: skip paragraphs with fewer words
# min_paragraph_chars = 30        # DS202/DS203: skip paragraphs shorter than this
```

For a comprehensive example of fast-profile policy options (DS104–DS118) with
all defaults documented, see [examples/doc_sentinel.toml](/examples/doc_sentinel.toml).
