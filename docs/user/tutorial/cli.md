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
Runs zero-dependency structural rules:
- `DS101`: Dangling link target (missing target file)
- `DS102`: Stray HTML comment (unwanted TODOs or raw HTML comments)
- `DS103`: Unresolvable relative link anchor (missing `#section-heading`)

```bash
docsentinel scan --profile fast
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
  "enabled_rules": ["DS101", "DS102", "DS103"],
  "pending": [],
  "notice": "3 fast rule(s) evaluated."
}
```

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
deep profile: ready
  ✓ deep libraries installed (spacy, textacy)
  ✓ deep model installed (en_core_web_sm)
fast rules: 3 registered
standard rules: 4 registered
deep rules: 1 registered
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
```
