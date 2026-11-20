# Using DocSentinel as a Python Library

DocSentinel provides a clean, frozen, and deterministic Python API. You can embed DocSentinel directly into custom build tools, release validation scripts, data pipelines, and test suites.

---

## Public API Imports

The top-level `docsentinel` package exports all primary functions and data models:

```python
from docsentinel import (
    # Core Scan API
    scan,
    
    # Configuration
    Config,
    ConfigError,
    ConfigSources,
    load_config,
    load_config_with_sources,
    
    # Data Models
    ScanResult,
    Document,
    Finding,
    
    # Baseline Management
    load_baseline,
    save_baseline,
    filter_baselined,
    fingerprint,
)
```

---

## Basic Scanning

The core function is `docsentinel.scan(root=".", *, config=None)`.

```python
from pathlib import Path
from docsentinel import scan

# Scan the current repository
result = scan()

print(f"Profile: {result.profile}")
print(f"Documents analyzed: {len(result.documents)}")
print(f"Total findings: {len(result.findings)}")

for finding in result.findings:
    print(f"[{finding.severity.upper()}] {finding.rule} in {finding.path}:{finding.line} -> {finding.message}")
```

---

## Configuring Scans Programmatically

You can construct a `Config` dataclass instance or load one from a file:

### 1. Constructing `Config` Directly

```python
from docsentinel import Config, scan

config = Config(
    profile="fast",
    include=("*.md", "docs/**/*.md"),
    exclude=(".venv", "node_modules", "dist"),
    select=("DS101", "DS103"),  # Only run link and anchor checks
    ignore=("DS102",),          # Ignore stray HTML comment checks
)

result = scan("docs", config=config)
```

### Selecting documents: `include` and `exclude`

`scan()` takes two keyword-only arguments that behave like `docsentinel scan --include` and
`--exclude`, because the CLI passes them straight through:

```python
from docsentinel import scan

# Only the user guides, and nothing under docs/archive (on top of the configured excludes)
result = scan(".", include=["docs/user"], exclude=["docs/archive"])
```

- `include` **replaces** the effective `include`; `exclude` is **appended** to the effective
  `exclude`, duplicates kept once. Exclude wins over include. Both also apply on top of an
  injected `Config`, which is never mutated.
- `None` (the default) means not given. A bare string, an empty sequence, more than 256 values or a
  value over 1,024 characters raises `ConfigError`, as does any refused value (`..`, an absolute
  path outside the scan root, a missing include). Pass a list or tuple, never a single string.
- Values are relative to the scan root and follow the literal and glob rules of the
  [configuration reference](../reference/configuration.md#selection-options-include-and-exclude).
- When the selection admits no document, `scan()` raises `ConfigError`
  (`the selection admitted no document; values are relative to the scan root`). A scan whose empty
  selection comes only from the configuration still returns an empty result.
- When `root` is a single file, both keywords are ignored with a `WARNING` after their shape is
  checked.
- The keywords have the same power as the `include` and `exclude` keys of the repository's own
  configuration. Do not pass on strings from an untrusted source without your own check.

### 2. Loading Configuration from Disk

`load_config` automatically searches for `docsentinel.toml` (or its alias `doc_sentinel.toml`) or `pyproject.toml` (under `[tool.doc_sentinel]`), and layers your [user settings](#3-user-settings-and-load_config_with_sources) beneath it:

```python
from pathlib import Path
from docsentinel import load_config, scan

# Auto-detects config in project root
config = load_config(Path("."))

# Or load an explicit file; a .json suffix selects the JSON reader
config = load_config(Path("."), path=Path("configs/custom-docsentinel.toml"))
config = load_config(Path("."), path=Path("configs/docsentinel.json"))

result = scan(".", config=config)
```

### 3. User settings and `load_config_with_sources`

`load_config` (and so `scan(root)` without a `config=`, and the `docsentinel_scan` pytest
fixture) layers the **user settings** file beneath the project configuration: the defaults, then
the user file, then the project file. The file is `~/.local/share/docsentinel/settings.json`
(under `XDG_DATA_HOME` when set, or the absolute path in `DOCSENTINEL_SETTINGS`); it cannot set
repository-relative options, and it must pass a permission check. A refused or unreadable file
raises `ConfigError`. See
[How to set options](../reference/configuration.md#how-to-set-options) for the rules.

A `Config` you pass to `scan(config=...)` is used as given: no file is read and no user settings
apply. Pass `config=load_config(root)` when you want the layered result.

Turn the user layer off for a call, or for the whole process:

```python
from pathlib import Path
from docsentinel import load_config

config = load_config(Path("."), user_settings=False)   # this call only
```

```bash
export DOCSENTINEL_SETTINGS=off    # every call in this process and its children
```

To see where the effective configuration came from, use `load_config_with_sources`. It returns the
`Config` and a `ConfigSources` that holds option **names** only, never values:

```python
from pathlib import Path
from docsentinel import load_config_with_sources

config, sources = load_config_with_sources(Path("."))
print(sources.user_state)       # "loaded", "missing", "off" or "no-home"
print(sources.user_options)     # names the user file set, sorted
print(sources.project_kind)     # "toml", "pyproject", "json" or "none"
```

`sources.user` and `sources.project` hold file paths; do not put a `ConfigSources` object in a
log line or report, because the user path is absolute.

**In CI, library and pytest runs included, set `DOCSENTINEL_SETTINGS=off` at job level.** A
persistent self-hosted runner home can carry a settings file from one job to the next, and the
library reads it unless you pass `user_settings=False` or an injected `Config`. Do the same for a
pytest run that uses the `docsentinel_scan` fixture on a runner you do not fully control.

---

## Data Models and Contracts

All core data structures in DocSentinel are immutable (frozen dataclasses).

### `ScanResult`

```python
@dataclass(frozen=True, kw_only=True)
class ScanResult:
    schema_version: int = 1
    profile: str
    documents: tuple[Document, ...]
    findings: tuple[Finding, ...]
    enabled_rules: tuple[str, ...]
    pending: tuple[str, ...]
    notice: str
```

### `Document`

```python
@dataclass(frozen=True)
class Document:
    path: str
    bytes: int
```

### `Finding`

```python
@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    message: str
    severity: str = "warning"
    line: Optional[int] = None
```

---

## Baseline Management in Code

You can manage baseline snapshots and filter findings programmatically:

```python
from pathlib import Path
from docsentinel import scan, load_baseline, save_baseline, filter_baselined

baseline_path = Path(".docsentinel-baseline.json")

# 1. Run raw scan without baseline
raw_result = scan(".")

# 2. To capture/save a new baseline:
# save_baseline(baseline_path, raw_result.findings)

# 3. Filter findings against an existing baseline:
if baseline_path.exists():
    known_fingerprints = load_baseline(baseline_path)
    new_findings = filter_baselined(raw_result.findings, known_fingerprints)
else:
    new_findings = raw_result.findings

print(f"New actionable findings: {len(new_findings)}")
```

---

## Pytest Integration

DocSentinel includes a built-in Pytest plugin (`docsentinel.pytest_plugin`).

### Running via pytest CLI

```bash
pytest -p docsentinel.pytest_plugin --docsentinel
```

### Using the `docsentinel_scan` Fixture in Tests

```python
from docsentinel import ScanResult

def test_documentation_integrity(docsentinel_scan: ScanResult) -> None:
    """Ensure documentation has zero error-level findings."""
    error_findings = [f for f in docsentinel_scan.findings if f.severity == "error"]
    assert not error_findings, f"Documentation errors detected: {error_findings}"
```

---

## Complete Example: Custom Pre-Release Gate

```python
#!/usr/bin/env python3
"""Custom pre-release documentation quality gate."""

import sys
from pathlib import Path
from docsentinel import scan, Config, load_baseline, filter_baselined

def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    
    # Configure standard profile checks
    config = Config(
        profile="standard",
        max_grade_level=16.0,
        duplicate_similarity=0.85,
        docsig_paths=("src",),
    )
    
    print(f"Scanning documentation in {repo_root}...")
    result = scan(repo_root, config=config)
    
    # Filter against committed baseline
    baseline_path = repo_root / ".docsentinel-standard-baseline.json"
    if baseline_path.exists():
        baseline = load_baseline(baseline_path)
        actionable_findings = filter_baselined(result.findings, baseline)
    else:
        actionable_findings = result.findings
        
    if actionable_findings:
        print(f"\n❌ Pre-release gate failed with {len(actionable_findings)} finding(s):", file=sys.stderr)
        for finding in actionable_findings:
            print(f"  - [{finding.rule}] {finding.path}:{finding.line or 1} {finding.message}", file=sys.stderr)
        return 1
        
    print(f"\n✅ All {len(result.documents)} documents passed validation ({result.notice})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

---

## Fast-profile policy options in the Python API

Milestone 0005 added typed policy options to `Config` for all fast-profile
rules DS104–DS118. These can be set directly when constructing a `Config`.

```python
from docsentinel import Config, scan

config = Config(
    profile="fast",
    # DS104 — anchor collisions
    anchor_collision_policy="explicit",

    # DS105 — heading hierarchy
    heading_level_policy="no-skips",
    first_heading_level=1,
    multiple_h1_policy="warn",

    # DS106 — contentless sections
    empty_section_policy="leaf",

    # DS108 — reference integrity
    unused_reference_definitions=True,
    duplicate_reference_definitions="error",

    # DS110 — fence language labels (opt-in)
    require_fence_languages=True,
    allowed_fence_languages=("python", "bash", "yaml", "toml"),

    # DS112 — navigation integrity (opt-in)
    navigation_indexes=("docs/README.md",),
    navigation_required=("docs/architecture/README.md",),

    # DS113 — missing assets
    missing_asset_policy="warn",

    # DS115 — deprecated references (opt-in)
    deprecated_references_file=".deprecated-names.toml",

    # DS116 — path boundaries
    root_escape_policy="warn",  # use "warn" in polyrepo docs

    # DS117 — pipe tables
    table_enable=True,

    # DS118 — naming policy (opt-in)
    documentation_naming="kebab",
    documentation_naming_allow=("README.md", "index.md", "CHANGELOG.md"),
)

result = scan(".", config=config)
```

**Important:** constructing `Config(...)` directly bypasses `load_config`
validation. The caller is responsible for passing valid values. Options that
require path containment (such as `navigation_indexes` or
`deprecated_references_file`) are validated by `load_config` when read from a
config file, but a directly constructed `Config` is trusted as given.

For the full list of options, valid values, and defaults, see the
[Configuration Reference](../reference/configuration.md).
