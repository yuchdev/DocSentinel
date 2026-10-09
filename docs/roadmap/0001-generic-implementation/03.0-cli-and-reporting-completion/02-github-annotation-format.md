# Task 02 - GitHub Actions Annotation Format

**Story:** [03.0 - CLI & Reporting Completion](README.md)
**Depends on:** Milestone 0001 Story 02.0 (real findings to render); independent of Task 01

## Purpose

CI today just captures DocSentinel's text/JSON output as a log blob (`docs/architecture/README.md`
/ `CLAUDE.md`'s own CI description: `uv run --locked docsentinel scan . --format json`). GitHub
Actions renders `::error file=...,line=...::message` workflow commands as inline PR annotations
on the exact changed line - a small addition that makes every future `DS1xx`/`DS2xx`/`DS3xx`
finding show up where a reviewer is already looking, instead of only in a log tab nobody opens.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/reporting.py` | Modify |
| `src/docsentinel/cli.py` | Modify - add `"github"` to the `--format` choices |
| `tests/test_reporting.py` | Create (reporting has had no dedicated test file; `render`'s
  existing coverage lives inline in `test_scan.py` - this task's tests can stay there too if the
  file does not yet exist by the time this task starts; create `test_reporting.py` only if it
  does not already exist, to avoid a redundant near-empty file) |

## Symbols / fields

`src/docsentinel/reporting.py`:

| Symbol | Change |
|--------|--------|
| `render(result: ScanResult, format: str = "text") -> str` | Add a third branch: `if format == "github": return _render_github(result)`. |
| `_render_github(result: ScanResult) -> str` | New. One line per `Finding`: `` f"::{_gha_level(f.severity)} file={f.path}::{f.rule}: {f.message}" `` (no line/column - `models.Finding` has no line number field today; omit those workflow-command parameters rather than fabricate `line=1`). Findings only - no profile/enabled-rules/pending/notice preamble (GitHub's annotation UI has no use for that framing; keep this format purely machine-consumed). |
| `_gha_level(severity: str) -> str` | New. `"error"` → `"error"`; anything else → `"warning"` - GitHub's workflow-command vocabulary only has `error`/`warning`/`notice`; map unknown/future severities to `"warning"` rather than erroring, so a new severity string introduced later doesn't crash report rendering. |

`src/docsentinel/cli.py`: `scan_parser.add_argument("--format", choices=("text", "json", "github"), default="text")` (add the one new choice to the existing line).

## Note for a future task

`DS101`'s `Finding.message` already contains line-relevant information in prose
(`"dangling link -> ..."`) but `Finding` has no structured `line` field, so this format cannot
emit `line=N` yet. Adding a `line: int | None = None` field to `Finding` is explicitly **out of
scope** for this task (it would ripple into every detector written in Story 02.0 and the JSON
schema versioning in Task 03) - note it here as a candidate for a later milestone once enough
detectors exist to justify the model change, rather than doing it piecemeal now.

## Tests

- `test_github_format_renders_error_and_warning_levels` - one `error` and one `warning` finding
  render as `::error ...` and `::warning ...` respectively.
- `test_github_format_omits_line_column_params` - the rendered string contains no `,line=` or
  `,col=` segment (documents the current `Finding` limitation rather than faking a value).
- `test_github_format_with_no_findings_is_empty_string` - a clean `ScanResult` renders to `""`
  (no preamble noise in a format meant purely for CI annotation consumption).
- `test_unknown_severity_maps_to_warning_level` - a `Finding` with an invented severity string
  still renders as `::warning ...`, not a `KeyError`/crash.
- `test_cli_accepts_github_format_choice` - `--format github` is accepted by argparse (does not
  raise `SystemExit` for an invalid choice).

## Success criteria

- [ ] `render(result, "github")` never raises for any `Finding.severity` value, including ones
      not currently produced by any shipped detector.
- [ ] CI's own workflow (`.github/workflows/ci.yml`) is **not** changed by this task - wiring
      `--format github` into an actual CI step is Milestone 0001 Story 04.0's job (pre-commit/CI
      wiring), not this one. This task only makes the format available.

## Constraints

- Full type annotations; no new dependency (GitHub's workflow-command syntax is a plain string
  format, no SDK needed).
- Keep `_render_github` resilient to a `Finding.message` containing a literal newline (GitHub
  workflow commands are single-line) - replace `\n` with the literal two characters `%0A` per
  GitHub's documented escaping for workflow command values (also escape `%`→`%25` and `\r`→`%0D`
  first, in that order, to avoid double-escaping).
