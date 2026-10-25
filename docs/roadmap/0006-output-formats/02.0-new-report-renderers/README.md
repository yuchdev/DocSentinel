# Story 02.0 - New Report Renderers

Adds two renderers on top of the registry from
[Story 01.0](/docs/roadmap/0006-output-formats/01.0-multi-format-output-plumbing/README.md):
a **Markdown** report people can read and commit, and **SARIF** so scan results can feed
code-scanning tools. Both are pure functions of `ScanResult`.

## Tasks

| # | Task | Output |
|---|------|--------|
| 01 | [Markdown report renderer](01-markdown-report-renderer.md) | `--format markdown`: summary table by rule and severity, a verdict, and findings grouped by document |
| 02 | [SARIF 2.1.0 renderer](02-sarif-renderer.md) | `--format sarif`: a valid SARIF 2.1.0 log, one `run`, rules from the registry, results with locations |

The two are independent once Story 01.0 lands and can ship in either order.
