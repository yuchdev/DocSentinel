# Story 03.0 - CLI & Reporting Completion

Story 01.0 already gave the CLI `--select`/`--ignore` and a real `rules`/`doctor`. This story
finishes the reporting layer now that findings are real (Story 02.0): severity has to actually
mean something at the exit-code level, CI needs a machine-friendly annotation format, and the
JSON report needs a schema version before anyone builds tooling against it.

## Tasks

| # | Task | Output |
|---|------|--------|
| 01 | [Severity-aware exit codes](01-severity-aware-exit-codes.md) | `cli.py` exit code honors `Finding.severity`; `--strict` flag |
| 02 | [GitHub Actions annotation format](02-github-annotation-format.md) | `reporting.render(..., format="github")` |
| 03 | [JSON report schema versioning](03-json-schema-versioning.md) | `ScanResult.schema_version`, documented |

Sequential: 02 and 03 both touch `reporting.py` and are easiest to land after 01 settles what
"severity" means for the CLI; 02 and 03 themselves do not depend on each other.
