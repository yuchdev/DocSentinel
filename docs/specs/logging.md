# Logging — levels, placement and the per-run log file

**Status:** Accepted (2026-11-13).
**Scope:** every `logging` call in `src/docsentinel/`, the per-run log file, and what the CLI
prints to stderr. Agents that add log calls follow this document. Change it here first.

## 1. Goals

- A CLI run is never silent. Even with `--output FILE`, the user sees on stderr what started,
  what finished, and where the result went.
- Every run leaves a log file that answers "what did it do, and why did it fail?" without
  re-running.
- The library stays quiet. `import docsentinel` and `docsentinel.scan()` configure no handler;
  only the CLI does.
- Reports are unchanged. Logging never writes to stdout, which carries the report when no
  `--output` is given, so `docsentinel scan --format json | jq` keeps working.

## 2. The wrapper: `docsentinel.log`

| Item | Contract |
|---|---|
| Loggers | `logging.getLogger(__name__)` in every module: a hierarchy under `docsentinel`. Never the root logger, and never `print` for diagnostics. |
| Library default | The `docsentinel` logger gets a `NullHandler` at import and `propagate` stays on, so an embedding application decides. |
| `configure_cli_logging(...)` | Called once by `cli.main`. It attaches a stderr handler and a per-run file handler to the `docsentinel` logger, and returns the log file path (or `None` when the file could not be created). |
| Log directory | `~/.local/logs/docsentinel/`, overridable by `DOCSENTINEL_LOG_DIR`. Created with mode `0o700`. An existing directory must be a real directory (`lstat`, not a symlink), owned by the current user, with no group or other write bit; otherwise the file is disabled (see Failure). Never point `DOCSENTINEL_LOG_DIR` into a checked-out repository or a shared directory. |
| File name | `docsentinel-<YYYYmmdd-HHMMSS>-<pid>.log`, local time, one new file per run. It is created with `O_CREAT|O_EXCL|O_NOFOLLOW`, so an existing file, hard link or symlink is never opened; when the name is taken, `-1`, `-2` ... is appended. The new file must be a regular file owned by the current user with exactly one link. |
| Rotation | After the file is created, keep the newest `DOCSENTINEL_LOG_KEEP` files (default 20, minimum 1) whose name matches `^docsentinel-\d{8}-\d{6}-\d+(?:-\d+)?\.log$` in that directory and delete the rest. Only regular files owned by the current user are counted or deleted; symlinks and non-regular files are skipped, never followed. A file with a modification time in the future is ignored (neither counted nor deleted), and a file modified in the last 60 seconds is never deleted, so concurrent runs keep their live files. |
| File level | `DEBUG`. Format: `[{timestamp}][{severity}]: {message}` (`log.LOG_FORMAT`, timestamp `%Y-%m-%d %H:%M:%S`, `log.LOG_DATE_FORMAT`; no logger name). File mode `0o600`, UTF-8. Tracebacks are neutralised line by line, and an exception's `Type: message` text is one neutralised line, so it cannot forge a record. |
| Stderr level | `INFO` by default; `-v/--verbose` gives `DEBUG`, `-q/--quiet` gives `WARNING`. `DOCSENTINEL_LOG_LEVEL` (a level name) overrides both. Stderr format: the same `[{timestamp}][{severity}]: {message}` line as the file, at every level (the old `docsentinel: ` prefix and the unlabelled `INFO` form are gone; since 2026-11-26, owner ruling). |
| Failure | If the directory or file cannot be created (read-only home, full disk), the run continues with stderr only and logs one `WARNING` naming the reason. Logging must never change an exit code. |
| Tests | `tests/conftest.py` points `DOCSENTINEL_LOG_DIR` at a temporary directory for every test, so the suite never writes to the real home. |

The CLI prints the log file path once at `DEBUG` on startup and once at `INFO` on any failure
(exit 1 or 2), so a failing run says where its details are.

## 3. Choosing a level

| Level | Use for | Examples |
|---|---|---|
| `DEBUG` | Anything that happens **per item inside a loop** (per document, per rule on a document, per finding, per template node, per extension hook call), and intermediate decisions useful only when diagnosing. | `checking docs/a.md with DS101`; `skipped symlinked file x`; `link target ./x.md resolved to /abs/x.md`; `cache hit for corpus model` |
| `INFO` | The **start** of an operation and its **final totals**: what was asked and what came out, with numeric metrics. One line per stage, not per item. | `scan started: root=…, profile=fast, 16 rules (12 evaluated)`; `config: user settings loaded (profile, reference_scope), project docsentinel.toml`; `selection: include 1 pattern(s) (invoker), exclude 4 pattern(s) (3 configured, 1 invoker)` (counts only; one `DEBUG` line per pattern); `discovered 385 documents (2 skipped)`; `scan finished in 1.42s: 385 documents, 1203 findings (errors 40, warnings 1163); by rule DS101=12, DS103=1100, …`; `report written to …/out.txt (text, 1312 lines)`; `baseline loaded: 900 fingerprints, 880 matched` |
| `WARNING` | Something went wrong **because of the user's input or configuration**, and DocSentinel coped, by skipping, falling back or ignoring, so the result may be incomplete or not what they meant. | A document that is unreadable, not a regular file or not valid UTF-8 (no rule checks it; it stays in the inventory and gets a blocking DS100 error finding unless `DS100` is ignored or not selected; stderr names the first 20, then one `skipped N more unreadable documents (see log file)` line, and the rest go to the log file only); the deep profile confirmed but its dependencies or model are missing (skipped); a config key value that falls back to a default; an excluded path that does not exist (`exclude pattern <p> names nothing under the scan root`, for a multi-component literal `--exclude`); an invoker `--include` pattern that admitted no document; `--include`/`--exclude` given with a single-file scan target (ignored); a linked file too large for the anchor check (skipped); an opt-in rule selected but its option unset; the log file could not be created |
| `ERROR` | A failure that is **not the user's fault**: a system problem (I/O error, permission on our own files, out of memory), an external failure (an optional dependency that was present at start-up failing at run time, a spaCy model failure), or a likely **bug** (an internal invariant broken, an unexpected exception caught at a boundary). Use `logger.exception(...)` inside `except` so the traceback reaches the file. | An analyzer raised an unexpected exception; a template that passed validation failed to render; writing the report failed with `OSError`; the standard extra failed to import mid-run |

Do not log the same event at two levels, or twice on its way up. Log where it is decided:
the lowest frame that knows what to do about it logs it, and callers that only propagate don't.

**A user mistake that aborts the run** (`ConfigError`, a bad `--template`, exit code 2) is not
something DocSentinel "coped with". The CLI reports it on stderr as today, and the log records
it once at `WARNING` with the exception message, not at `ERROR`. The user's input was at fault,
not the system.

Findings are **not** log events. A dangling link is a result, not a problem in DocSentinel. Log
finding totals at `INFO`, and each finding at most at `DEBUG`.

## 4. What may be logged

Logs land in a file under the user's home and in CI logs, so the reporting rules apply:

- **Never document content.** No paragraph, line, snippet, comment text or frontmatter value.
  A count, a byte size, a line number, a rule code or a relative path is fine. One explicit
  exception (owner ruling of 2026-11-27): the `DS302` trace lines may quote the first ten words of
  a claim sentence, and the lenz client the first ten words of the backend's echo of it, through
  `docsentinel.log.quote_start(text)` (first words, then `...`, through `safe()`). These reach stderr and
  the log file at `INFO` by default. Nothing else of a document is quoted; `FactCheckError`
  messages, citations and API keys are never logged (the lenz client's own fixed rejection message
  is logged at `DEBUG`).
- **Paths and other untrusted strings** (link targets, config values, template names) go through
  `docsentinel.log.safe(value)`, which applies `neutralize_text` and caps the length (200
  characters). A crafted file name must not forge log lines, carry terminal control
  sequences, or form a GitHub Actions legacy command (`neutralize_text` rewrites `##[` as `##\[`).
- **No secrets.** No environment dumps or full config dumps; log the option names that matter.
  The settings layers are the model: the `INFO` line `config: user settings <state>[ (<names>)],
  project <file name or none>` (logged by `scan` and `baseline` after `scan started`) lists option
  names only, sorted, at most 20 and then `and N more`, never a value. The user settings path is
  shown in tilde form (`~/.local/share/docsentinel/settings.json`), never the absolute home path,
  and a failure message names the file in the same form. The `DEBUG` lines
  `user settings: disabled`, `user settings: missing`, `user settings: no home directory` and
  `user settings: permission check skipped (non-POSIX)` record the other states. A `ConfigSources`
  object is never logged as a whole: its paths are absolute.
- **Lazy formatting:** `logger.debug("checked %s: %d findings", safe(path), n)`, never an
  f-string. In per-line or per-character hot paths (the Markdown scanner, filters, the template
  engine inner loop), do not log at all; log per document or per call instead, so
  `MAX_STEPS`-style budgets and the timing tests are unaffected.

## 5. Placement checklist (per module)

1. `logger = logging.getLogger(__name__)` at module top. Import `safe` from `docsentinel.log`
   when you log untrusted strings.
2. Each public entry point (`scan`, `render`, `load_config`, `load_template`, `resolve_*`,
   detector `detect`): log `DEBUG` on entry with its key parameters. Log `INFO` only at the
   CLI/engine stage level.
3. Each `except` block: decide which section 3 class it is. A user-caused fallback is
   `WARNING`. An unexpected failure is `ERROR` via `logger.exception`. A re-raise with no
   decision logs nothing.
4. Each silent `continue`/skip on input: `DEBUG` when it is normal (an excluded file), `WARNING`
   when the user would be surprised (an unreadable file they asked to scan).
5. No `print` outside `cli.py` user output, and no logging to stdout.
