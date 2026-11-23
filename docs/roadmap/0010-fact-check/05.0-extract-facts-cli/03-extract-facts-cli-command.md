# Task 03 — `docsentinel extract-facts` subcommand

**Parent story:** [Story 05.0](/docs/roadmap/0010-fact-check/05.0-extract-facts-cli/README.md)  
**Role:** Python Expert  
**Depends on:** [Task 01](./01-shared-candidate-collection-and-public-api.md) and
[Task 02](./02-facts-template-context-and-packaged-templates.md).

## Goal

Add the CLI surface over `docsentinel.extract_facts()`. The command has one code path through the
engine and renders through a template. It is offline and never exits `1`.

## Inputs

- Story [decisions X4–X7, X9–X12](/docs/roadmap/0010-fact-check/05.0-extract-facts-cli/README.md#decisions).
- `/src/docsentinel/cli.py`: `_build_parser`, `_add_selector_options`, `_add_verbosity_options`,
  `NO_USER_SETTINGS_HELP`, the `scan` handler (config load with `--config`/`--no-user-settings`,
  template resolution before the run, `-o` writing, the `Scan failed:` path through
  `neutralize_text`, `scan started`/`scan finished` logging, `details in log file:`), and the
  `doctor` template lines.
- `/docs/specs/logging.md`, and the CLAUDE.md logging and exit-code sections.

## Steps

1. **Parser.** Add `commands.add_parser("extract-facts", help="List the verifiable facts DS302 would
   check (offline; no network)", parents=[verbosity])` with these arguments:
   - `root` (optional, default `.`): directory or file, as for `scan`.
   - `--config PATH` and `--no-user-settings`: same semantics as `scan`.
   - `--include`/`--exclude` through `_add_selector_options`.
   - `--format NAME`: default `facts-text`. The help lists `packaged_template_names(context="facts")`,
     and the value is validated against facts templates only (packaged, then `report_templates_dir`).
   - `--template PATH`: a trusted invoker path that wins over `--format`, as for `scan`.
   - `-o/--output PATH`: same file semantics as `scan -o` (UTF-8, overwrite, parents created).
   - `--min-salience FLOAT`, `--max-per-document INT`, `--max-total INT`: help text says "default:
     the effective fact_check_* configuration value".
   - `--weights N,E,D`: parsed into three floats; malformed text is an argparse error. `--dedup-threshold FLOAT`.
     The help text says: "exploration only: changes this command's output, never DS302; the output
     is then marked as not matching DS302".
   - `--all` (`dest="include_rejected"`): "also list claims that were not selected, with the reason".
   - Do **not** add `--profile`, `--select`, `--ignore`, `--baseline`, `--strict`,
     `--use-external-api`, `--i-understand-deep-is-heuristic`, `--link-root`, `--reference-scope`,
     `--extension` or `--allow-python-extensions`. Passing any of them is an argparse error (exit `2`).
2. **Handler** `_cmd_extract_facts(args)`, structured like the `scan` handler:
   1. Load the config with `load_config_with_sources(directory, args.config, user_settings=not
      args.no_user_settings)`. Log the same INFO `config: user settings …, project …` line as `scan`.
   2. Resolve the template before any extraction. A template error prints
      `Extraction failed: <neutralize_text(message)>` and exits `2`.
   3. If `deep_ready()` is false, print
      `Extraction failed: extract-facts needs the deep extras and the spaCy model - <DEEP_EXTRA_HINT>`
      and exit `2`. Use the same text as the library `RuntimeError`.
   4. Log INFO `extract-facts started` with counts and option *names* only, never values that
      came from a file, and never document text.
   5. Call `extract_facts(root, config=settings, include=…, exclude=…, min_salience=…,
      max_per_document=…, max_total=…, weights=…, dedup_threshold=…, include_rejected=…)`.
   6. Render with `render_facts(...)` and write it to stdout or `-o`. Log
      `report written to <path> (<format>, <N> lines)` as `scan` does.
      **Amended 2026-11-24 (threat model, E10).** `-o` keeps the `scan -o` semantics: render
      first, then write, so a render failure leaves no file. The facts file holds document text;
      Story 04.0 Task 04 docs warn against writing it under the scan root (the next scan would
      discover it) or committing it.
   7. Log INFO `extract-facts finished` with elapsed time, documents, unreadable, claims, selected,
      listed, `matches_ds302` and exit code.
   8. Return `0`.
3. **Errors.** `ConfigError`, `ValueError`, `OSError`, `RuntimeError` from the deep-readiness check,
   and `TemplateError` (via its chained `ValueError`) print one
   `Extraction failed: <neutralize_text(message)>` line, are logged once with `FILE_ONLY` as
   `scan` does, add `details in log file: <path>`, and exit `2`. No path returns `1`.
   **Amended 2026-11-24 (threat model, E7).** The extraction-error `RuntimeError` of Task 01 step
   4.9 prints exactly
   `Extraction failed: extract-facts: claim extraction failed (<TypeName>)` and is logged without
   `exc_info`, so no third-party exception text (which can carry document tokens) reaches stderr
   or the log file.
4. **Environment.** The handler reads none of `DOCSENTINEL_USE_EXTERNAL_API`,
   `DOCSENTINEL_FACTCHECK_*`, `DOCSENTINEL_DEEP_CONFIRM` or `DOCSENTINEL_ALLOW_PYTHON_EXTENSIONS`.
   The existing Story 01.0 Task 06 AST/grep test over `cli.py` must still pass. Extend it to assert
   that the `extract-facts` handler references no gate or backend helper.
5. **`doctor`.** The report-templates line becomes two lines:
   `report templates (packaged): …` (unchanged text, `report` context only) and
   `fact templates (packaged): facts-json, facts-text` (sorted; amended 2026-11-24). No other `doctor` change: the
   `fact-check gate:` line from Story 01.0 is unrelated to this command.
   **Amended 2026-11-24 (threat model, E2).** The `report_templates_dir` listing is **not** split:
   it stays one name-only line, `templates (report_templates_dir): <names> (context checked at
   load)`, which replaces today's `report templates (report_templates_dir): …` line (and its
   `unavailable:` form). No directory file is opened to build it.
6. **`rules`.** No change.
7. Report a `Docs impact:` line (trigger K) and a `Diagram impact:` line naming
   `component-overview.puml` (new CLI subcommand into `engine.extract_facts`, no network edge).

## Deliverables

- `/src/docsentinel/cli.py`

## Acceptance criteria

- [ ] `docsentinel extract-facts DIR` prints `facts-text` output and exits `0`, including when zero
      facts are selected.
- [ ] `--format facts-json -o out.json` writes valid JSON and logs the `report written to` line.
- [ ] `--format json` (a report template) exits `2` with the message from Task 02.
- [ ] Each override changes the matching `run.settings` value. An out-of-range value
      (`--max-total 0`, `--max-total 501`, `--min-salience 1.5`) exits `2` with the config
      validator's message.
- [ ] `--weights 0.5,0.5,0.5` (sum other than 1) and `--dedup-threshold 0` exit `2`.
      `--weights 0.2,0.2,0.6` exits `0` and the output says it does not match DS302.
- [ ] `--use-external-api`, `--profile deep` and `--i-understand-deep-is-heuristic` are argparse
      errors (exit `2`).
- [ ] An invoker `--include` that admits no document exits `2` with `EMPTY_SELECTION_MESSAGE`. A
      non-UTF-8 document is skipped with the shared WARNING and counted, and the exit code is `0`.
- [ ] With the deep extras unavailable (patched `deep_ready`), the command exits `2` before reading
      any document.
- [ ] stderr and the log file never contain a claim sentence (sentinel test). stdout is clean
      apart from the rendered output.
      **Amended 2026-11-24 (threat model, E13):** the sentinel test also runs with `-v` (DEBUG,
      including the `trace_salience` stage counts), covers the `config:` INFO line, and covers the
      E7 path (a patched `extract_claims` raising `ValueError(<sentinel sentence>)` exits `2` with
      the fixed text and no sentinel in stderr, the log file or any record).
- [ ] `doctor` shows both packaged template lines and the one name-only
      `templates (report_templates_dir):` line (E2, amended 2026-11-24). Every other `doctor`,
      `rules` and `scan` output is byte-identical.
- [ ] **Amended 2026-11-24 (threat model, E10).** `-o` after a forced render failure leaves no file.
      `--include ../x`, a `##[` selector value and `--exclude .` exit `2` exactly as for `scan`.

## Test expectations

Written in [Task 04](./04-fixtures-and-tests.md) (`tests/integration/test_extract_facts_cli_ds302.py`).

## Out of scope

- A pre-commit hook, a pytest fixture, or `--extension` for facts.
- A `baseline` for facts.
