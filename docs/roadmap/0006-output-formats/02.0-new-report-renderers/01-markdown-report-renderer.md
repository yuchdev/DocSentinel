# Task 01 - Markdown Report Renderer

**Story:** [02.0 - New Report Renderers](README.md)
**Depends on:** [Story 01.0 Task 01](/docs/roadmap/0006-output-formats/01.0-multi-format-output-plumbing/01-renderer-registry.md)

## Purpose

Today a committed, human-readable review has to be written by hand from the `json` output. A
built-in Markdown renderer produces that report directly: counts first, then detail.

## Report structure

1. `# DocSentinel report` and a one-line header: profile, document count, schema version.
2. The `notice` and any `pending` message, verbatim. A `deep` run adds its advisory banner.
3. **Summary table** - one row per rule that produced findings: rule, severity, count, title.
   Sorted by severity (errors first), then count, then rule id.
4. **Verdict** - the exit code this run would produce, with the reason (for example "2 errors") and
   the `--strict` and deep-advisory rules applied exactly as `_exit_code` does.
5. **Findings by document** - one `##` section per document in discovery order, each finding as a
   bullet: rule, severity, line when known, neutralized message. A document with no findings is
   omitted.
6. A run with zero findings states how many rules were evaluated; it never prints a bare "clean".

## Decisions

- The renderer imports `_exit_code`'s logic through a shared helper rather than re-deriving it, so
  the verdict cannot drift from the real exit code.
- Messages are neutralized and then Markdown-escaped, so a path or message cannot inject headings,
  links or HTML into the report.
- Very large reports are not truncated, but a `--max-findings-per-document N` is out of scope here.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/reporting.py` | Modify - `render_markdown`; register `markdown` (extension `md`) |
| `src/docsentinel/cli.py` | Modify - factor the exit-code reason into a shared helper |
| `tests/test_reporting.py` | Modify/add |

## Tests

- `test_markdown_summary_table_sorted_by_severity_count_rule`.
- `test_markdown_verdict_matches_exit_code` - parametrized over profile and `--strict`.
- `test_markdown_deep_run_has_advisory_banner_and_exit_zero`.
- `test_markdown_pending_run_never_reads_as_clean`.
- `test_markdown_escapes_injected_markup_and_controls` - a message with `#`, `[x](y)`, `<script>` and
  a bidi override.
- `test_markdown_output_is_deterministic`.
