# Task 02 - `--output` and Repeatable `--format`

**Story:** [01.0 - Multi-Format Output Plumbing](README.md)
**Depends on:** [Task 01](01-renderer-registry.md) (the registry)

## Purpose

Let one scan write several reports. Motivating case: reviewing a documentation tree needs the
`json` for tooling, the `text` for reading and the `github` stream for CI from the same scan.

## Decisions this task implements

1. **`--format` becomes repeatable** (`action="append"`); the default stays `text`. Passing it once
   behaves exactly as today.
2. **`--output PATH`** writes the report to a file instead of stdout. It is valid only with a single
   `--format`; combining it with more than one is a usage error (exit `2`).
3. **`--output-dir DIR`** writes one file per requested format, named `docsentinel-<profile>.<ext>`
   with extensions `txt`, `json`, `github.txt` (new formats declare theirs when registering). The
   directory is created if missing.
4. **Without either flag, nothing changes.** Reports go to stdout; with several `--format` values and
   no `--output-dir`, it is a usage error rather than concatenated output.
5. **One scan.** All renderings come from the same `ScanResult`.
6. **Exit code is unaffected by where output goes.** It is computed from the result exactly as today.
7. **No clobbering surprises.** Existing files are overwritten (reports are regenerable), but a path
   that is a directory, or that resolves outside the working tree via a symlink, is refused with a
   neutralized error and exit `2`.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/cli.py` | Modify - flags, validation, file writing |
| `src/docsentinel/reporting.py` | Modify - `register_format` accepts a default file extension |
| `tests/test_scan.py` | Modify/add CLI tests |

## Tests

- `test_single_format_to_stdout_unchanged`.
- `test_output_writes_file_and_leaves_stdout_empty`.
- `test_output_with_multiple_formats_is_usage_error`.
- `test_output_dir_writes_one_file_per_format_from_one_scan` - monkeypatch the scan to count calls.
- `test_multiple_formats_without_output_dir_is_usage_error`.
- `test_output_path_that_is_a_directory_is_refused`.
- `test_exit_code_independent_of_output_destination`.
