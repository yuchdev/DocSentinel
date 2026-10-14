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
    load_config,
    
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

### 2. Loading Configuration from Disk

`load_config` automatically searches for `doc_sentinel.toml` or `pyproject.toml` (under `[tool.doc_sentinel]`):

```python
from pathlib import Path
from docsentinel import load_config, scan

# Auto-detects config in project root
config = load_config(Path("."))

# Or load an explicit file
config = load_config(Path("."), explicit_file=Path("configs/custom-docsentinel.toml"))

result = scan(".", config=config)
```

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
