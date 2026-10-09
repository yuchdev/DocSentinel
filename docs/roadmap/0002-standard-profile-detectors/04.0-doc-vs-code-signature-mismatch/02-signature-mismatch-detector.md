# Task 02 - Signature-Mismatch Detector (`DS204`)

**Story:** [04.0 - Doc-vs-Code Signature Mismatch Detector](README.md)
**Depends on:** [01 - Python source discovery path](01-code-discovery.md); Milestone 0002 Story 01.0
(lives in the lazy `standard` subpackage, so it may import `docsig`)

## Purpose

Run `docsig` over the Python files from `discover_python` and turn each docstring-vs-signature
violation into one `DS204` `Finding`. This covers `CLAUDE.md`'s "doc-vs-code" concern at the
*mechanical* level - documented params that do not exist, real params left undocumented, spurious
`:returns:` - which is deterministic and belongs in `standard`, as distinct from the *behavioral*
doc-vs-code drift (does the prose describe what the code does?) that is semantic and reserved for
`deep` (Milestone 0003).

## The real `docsig` API (researched) and how we adapt

`docsig`'s public surface is intentionally small: `docsig(...)` (the runner), `main`, `messages`
(the `SIGxxx` code→text schema), and `__version__`. **There is no public structured report object.**
`docsig(...)` runs the checks and *prints* a human report, returning an `int` failure count. So this
detector:

1. Invokes `docsig` **in-process** (no subprocess) once per discovered file, passing the file path
   and `no_ansi=True` (stable, color-free output), and captures stdout with
   `contextlib.redirect_stdout(io.StringIO())`.
2. Parses the captured report into violations. The report's record shape is stable and documented:
   a location/function header line followed by one or more indented `SIGxxx: message` lines, e.g.
   ```
   <file>:<lineno> in <function>
       SIG202: includes parameters that do not exist (params-do-not-exist)
   ```
   The parser pairs each `SIGxxx` line with the most recent header line.
3. Validates each parsed `SIGxxx` code against `docsig.messages` (the public schema) so an
   unrecognized code (a `docsig` version drift) is caught rather than silently mis-attributed.

This stdout-parsing coupling is a **documented fragility**: it depends on `docsig`'s report format
staying stable across patch versions (hence the `>=0.96` floor and a pinned-tested version in CI,
Story 05.0). Record, in the module docstring, that if a future `docsig` exposes a structured result
object, the parser should be replaced by it - the `Finding`-mapping logic stays, only the extraction
changes. Do **not** shell out to the `docsig` CLI as a subprocess (slower, and couples to argv
parsing on top of output parsing).

## Decision this task implements

1. **One `Finding` per `(file, lineno, function, SIGxxx)` violation.** `severity="error"` -
   docstring/signature mismatch is unambiguous and mechanical (a documented parameter that does not
   exist is simply wrong), matching `DS101`'s "unambiguously wrong → error" reasoning. Message shape:
   `f"{function}: {sig_code} {sig_message}"`; `Finding.path` is the Python file's root-relative path;
   the line number is embedded in the message (`f"line {lineno}: ..."`) since `Finding` has no line
   field.
2. **`detect` ignores its `documents` argument.** The `Analyzer` signature passes the Markdown
   `documents` tuple; `DS204` does not use it - it calls `discover_python(root, load_config(root))`
   to get Python files instead. This is the one honest deviation from the "detectors consume
   `documents`" pattern (flagged in the story README); note it explicitly in the function docstring
   so the unused parameter is obviously intentional, not a bug. Keep the parameter (signature is
   frozen); do not rename it to `_documents` in the public alias.
3. **docsig configuration is left at its defaults for this milestone.** No per-project docstring-style
   selection (Sphinx vs NumPy vs Google), no `SIGxxx` enable/disable beyond DocSentinel's own
   `select`/`ignore` (which operate at the `DS204` granularity, not the `SIGxxx` sub-granularity).
   Sub-code filtering is explicit future work - note it; do not build a nested `[tool.doc_sentinel.
   docsig]` schema now (same "don't over-build config" discipline as `DS201`'s single threshold).
4. **A file `docsig` cannot parse (syntax error) is surfaced, not swallowed.** If `docsig` raises on a
   malformed file, let it propagate (consistent with `DS101`/`DS201` propagating read errors) - a
   source file that will not parse is itself worth surfacing.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/detectors/standard/signatures.py` | Create |
| `tests/test_detectors_signatures.py` | Create |

## Symbols / fields

`src/docsentinel/detectors/standard/signatures.py`:

| Symbol | Kind | Notes |
|--------|------|-------|
| `DS204` | module-level `Rule` via `register_rule(...)` | `Rule(code="DS204", profile="standard", title="Docstring/signature mismatch", description="A function docstring's documented parameters or returns do not match its signature.", severity="error")`. |
| `_Violation` | `@dataclass(frozen=True)` | `file: str`, `lineno: int`, `function: str`, `sig_code: str`, `sig_message: str` - one parsed docsig violation. |
| `_run_docsig(path: Path) -> str` | function | Invokes `docsig` in-process on `path` with `no_ansi=True`, captures and returns stdout. Isolated so the parser can be tested against canned output without invoking docsig. |
| `_parse_docsig_output(output: str, *, file: str) -> tuple[_Violation, ...]` | function | Parses the header/`SIGxxx` record format (above) into `_Violation`s; validates each `sig_code` against `docsig.messages`, raising `ValueError` on an unknown code (version-drift guard). Pure - the core of this task's testability. |
| `check_file(root: Path, path: Path) -> tuple[Finding, ...]` | function | `_run_docsig` → `_parse_docsig_output` → one `Finding(rule="DS204", path=<root-relative path>, ...)` per violation. |
| `detect(root: Path, documents: tuple[Document, ...]) -> tuple[Finding, ...]` | function, `ANALYZERS["DS204"]` | Ignores `documents` (Decision §2); `discover_python(root, load_config(root))`; `check_file` on each; concatenate. |

## Validators

- `_parse_docsig_output` raises `ValueError` on a `SIGxxx` code not present in `docsig.messages` (a
  docsig-version drift that changed codes) - better a loud failure (exit `2` via the CLI boundary)
  than silently emitting findings with codes we cannot explain.
- No `ConfigError` here beyond what `discover_python`/`load_config` already raise.

## Tests (`tests/test_detectors_signatures.py`)

Guard with `importorskip("docsig")`.

- `test_parse_docsig_output_single_violation` - feed `_parse_docsig_output` a canned two-line record;
  assert one `_Violation` with the right file/lineno/function/sig_code.
- `test_parse_docsig_output_multiple_violations_one_function` - a header with two indented `SIGxxx`
  lines → two `_Violation`s sharing location.
- `test_parse_docsig_output_unknown_sig_code_raises` - a `SIG999` not in `docsig.messages` →
  `ValueError` (version-drift guard).
- `test_parse_docsig_output_clean_is_empty` - empty/clean output → `()`.
- `test_check_file_flags_param_that_does_not_exist` - a real `tmp_path` `.py` file whose docstring
  documents a nonexistent parameter → one `DS204` finding (error severity), path attributed, lineno
  and SIG code in the message. (This exercises the real `docsig`, not canned output.)
- `test_check_file_flags_undocumented_param` - a function with an undocumented real parameter → a
  `DS204` finding.
- `test_well_documented_function_is_clean` - a correctly-documented function → zero findings.
- `test_detect_ignores_markdown_documents` - `detect(root, documents=(Document("a.md", 10),))` still
  discovers and checks Python files under `root/src`, confirming the `documents` argument is unused by
  design (plant a bad `.py` under `src/`, pass an unrelated markdown `Document`, assert the `.py`
  finding appears).
- `test_detect_respects_docsig_paths` - with `docsig_paths=("lib",)` in config, a bad `.py` under
  `lib/` is flagged and one under `src/` is not scanned.

## Success criteria

- [ ] `DS204` emits one `error`-severity finding per real docsig violation, with the file path,
      line number, function, and `SIGxxx` sub-code all present in the finding.
- [ ] `_parse_docsig_output` is pure and covered against canned output, including the unknown-code
      guard - the fragile stdout coupling is isolated behind one tested function.
- [ ] `detect` scans Python source (via `discover_python`), not the Markdown corpus, and does so even
      when handed an unrelated `documents` tuple.

## Constraints

- Full type annotations; no bare `except:`. `docsig` imported inside the functions (lazy-loader-reached
  module).
- In-process `docsig(...)` call with `redirect_stdout` - no subprocess, no CLI-argv dependency.
- Do not add a `SIGxxx`-level enable/disable config or a docstring-style selector this milestone
  (Decision §3) - `select`/`ignore` operate at `DS204` granularity only. Record both as future work.
- Record the stdout-parsing fragility and the "swap for a structured API if docsig adds one" note in
  the module docstring.
</content>
