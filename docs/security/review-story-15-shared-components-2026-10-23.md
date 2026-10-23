# Threat Model - Story 15.0 Task 02 shared-component changes - 2026-10-23

Security and robustness review of the uncommitted Story 15.0 Task 02 shared-component
changes on branch `milestone/0005-deepening-test-case-stage-2`:

1. `reporting._neutralize_controls` and its use in the text and GitHub sinks
   (`src/docsentinel/reporting.py`), with
   `tests/unit/test_reporting_control_characters.py`,
   `tests/integration/test_reporter_hostile_filename.py`, and section 7 of
   `docs/security/review-github-actions-annotations-2026-10-10.md`.
2. The DS301 lazy `_triples`/spaCy import (`src/docsentinel/detectors/contradictions.py`),
   with `tests/integration/test_import_isolation.py` and
   `tests/integration/test_milestone_0005_final_audit.py`.
3. `tests/integration/test_adversarial_runtime_cases.py` and `scripts/bench_corpus.py`.
4. The performance-report claims
   (`docs/roadmap/0005-deepening-test-case-stage-2/performance-report.md`).

Scope limited to the above. Product code and other docs were not modified; the full
suite was not run. Findings were verified with ad-hoc probes against the working tree and
against `git show HEAD:src/docsentinel/reporting.py`.

## Assets & trust boundaries

- **Untrusted inputs:** scanned repository file **names** (`Finding.path`,
  `Document.path`) and detector-echoed source **excerpts** (`Finding.message`). File
  names on POSIX are arbitrary bytes; the OS/Git may present names an attacker chose.
- **Trust boundary crossed:** untrusted name/excerpt -> `ScanResult` -> `reporting.render`
  -> three sinks (terminal text, GitHub Actions workflow-command stream, JSON) -> human
  reader / CI runner / log viewer. A second boundary: untrusted name -> `OSError` message
  -> `cli.py` `Scan failed:` -> stderr.
- **Assets:** integrity/trustworthiness of the CI log and terminal display; availability
  of the CLI (no crash on hostile input); integrity of the GitHub workflow-command stream
  (`::error`/`::warning`/`::set-output`/`::add-mask` must not be forgeable).
- **No secrets** are handled by these components. No network, shell, SQL, or AI backend is
  reached. The deep (spaCy) path reads doc files already inside the scan root.

## What is correctly mitigated (verified)

- **GitHub workflow-command injection (the CRITICAL concern): closed.** In
  `_render_github` both the `file=` property (`_escape_property`) and the message
  (`_escape_data`) percent-encode `%`, CR and LF (property also `:` and `,`), with the
  `%`-first ordering preserved. CR/LF -> `%0D`/`%0A` means neither path nor message can
  emit a newline, so a hostile name **cannot forge a second `::error`/`::warning`/
  `::set-output`/`::add-mask` line**. `,` escaping blocks injecting a new `file=`/`line=`
  property; `line` is an `int`/`None`; severity is mapped to exactly `error`/`warning` by
  `_gha_level`. No `title=` field is emitted, so there is no title second-command vector.
  Verified on the hostile corpus: `::error file=...%0D%0A...::...` stays one line.
- **C0/C1/DEL/ESC/BEL/NUL/CSI/NEL/bidi/zero-width: neutralized** in both human sinks.
  `U+0085` (NEL) and `U+009B` (CSI) fall in the C1 range `0x80-0x9F` and are escaped;
  bidi overrides (`U+202A-202E`, `U+2066-2069`, `U+200E/200F`, `U+061C`) and zero-width
  formats (`U+200B-200D`, `U+FEFF`) are escaped. Verified by probe.
- **Byte-identical for normal input.** Rendering 200 generated findings (ASCII + ordinary
  Unicode: accented, CJK) through text/github/json was byte-for-byte identical to the
  committed `HEAD` reporter. No regression for benign content.
- **JSON sink** is lossless and ASCII-only (`ensure_ascii=True`); round-trips the raw
  strings. Baseline fingerprints hash raw `Finding` fields, unaffected by rendering.
- **Idempotence / performance.** Double-neutralization does not corrupt (`\` is not in the
  table). `str.translate` is C-level linear: a 10 MB message neutralized in ~0.01 s; a
  pathological 100k-escape string in ~1.8 s, linear in output size. No quadratic blow-up.
- **DS301 lazy import: registration/selection semantics unchanged vs HEAD.** `DS301` still
  registers eagerly (`register_rule` + `ANALYZERS["DS301"]=detect` at import);
  `rules_for_profile("deep")` returns `['DS301']`, `opt_in_option=''`, severity `warning`.
  The deep confirmation gate and advisory exit 0 are untouched (engine/CLI unchanged).
  A plain `import docsentinel` and a fast scan load **none** of
  spacy/textacy/sklearn/textstat/docsig (own subprocess probe confirmed `heavy loaded: []`
  and importing `contradictions` does not pull in `spacy` or `_triples`).
- **Deep missing-deps failure mode is graceful.** The engine's `deep_ready()` gate returns
  a bounded `ScanResult` with an explanatory notice ("Deep profile detection skipped
  because dependencies are unavailable.") and `findings=()` **before** the analyzer (and
  thus the lazy `_triples` import) runs - not a traceback and not a silent clean (the
  notice/pending state the skip). Because the lazy import is reached only after
  `deep_ready()` confirms spaCy is importable, it adds no new `ImportError` surface.
- **Lazy-import thread-safety/idempotence.** `importlib.import_module` is backed by the
  import system's per-module lock and `sys.modules` cache; repeated calls are idempotent.

## Findings

### [MEDIUM] Unicode line/paragraph separators U+2028/U+2029 are not neutralized
- Vector / evidence: `src/docsentinel/reporting.py:56-62` builds the neutralization set
  from C0, DEL, C1, the bidi controls and the zero-width formats but omits `U+2028` (LINE
  SEPARATOR) and `U+2029` (PARAGRAPH SEPARATOR). Probe: `_neutralize_controls(' ')`
  returns it unchanged, and `render(..., 'text'|'github')` emits `U+2028`/`U+2029` raw in
  both `path` and `message`.
- Impact: these are Unicode line terminators. They do **not** forge a GitHub
  workflow-command line (the .NET-based runner's line reader splits only on CR/LF/CRLF,
  not U+2028/U+2029/NEL, and the sink already percent-encodes CR/LF), so this is **not**
  command injection. But they render as line breaks in the GitHub web log viewer, many
  editors and some terminals, so a hostile file name can still visually break/forge a log
  line - the exact display-spoofing class this hardening set out to close (the module
  docstring names "a line feed forging a second log line"). CWE-117, CWE-150.
- Mitigation: add `{0x2028, 0x2029}` to the neutralized set in `_build_control_table`
  (and consider `U+000B`/`U+000C` vertical-tab/form-feed, already covered by the C0 range,
  and `U+0085` already covered). Hand to `python-expert`; add a regression case to
  `tests/unit/test_reporting_control_characters.py` via `testing-expert`.

### [MEDIUM] Lone surrogate in a path makes text/github output un-encodable -> unhandled traceback
- Vector / evidence: undecodable bytes in a POSIX file name are decoded by Python with
  `surrogateescape` into lone surrogates `U+DC80-U+DCFF`. These are not in the
  neutralization table (`reporting.py:56-62`), so `render` returns them raw. The text and
  GitHub renderings then **cannot be encoded to UTF-8**; probe:
  `UnicodeEncodeError: 'utf-8' codec can't encode character '\udcff' ... surrogates not
  allowed`. In `cli.py:232` the `print(render(result, args.format))` is **outside** the
  `try/except (ConfigError, ValueError, OSError)` block (which wraps only the scan,
  `cli.py:212-231`), so the resulting `UnicodeEncodeError` propagates as an unhandled
  traceback and the process exits 1.
- Impact: availability / the hardening's "no raw control reaches the reader, no traceback"
  contract fails on a hostile non-UTF-8 file name (reachable on Linux/ext4; **not** on
  macOS, whose filesystem enforces UTF-8 - which is why `test_reporter_hostile_filename`
  skips there and why the adversarial suite, using only UTF-8 names, misses it). The JSON
  sink is unaffected (`ensure_ascii` escapes surrogates). CWE-20, CWE-176, CWE-248.
- Mitigation: neutralize the lone-surrogate range `U+D800-U+DFFF` in the table (escaping
  them as `\uDCFF` etc. makes output ASCII-safe and inert), so all three sinks stay
  encodable. Hand to `python-expert`; add a Linux-gated regression (and/or a direct
  `_neutralize_controls('\udcff')` unit assertion) via `testing-expert`.

### [LOW] cli.py error sinks bypass the reporter and can emit raw control bytes to stderr
- Vector / evidence: `cli.py:208` (`Baseline generation failed: {exc}`) and `cli.py:230`
  (`Scan failed: {exc}`) print exception text to stderr with no `_neutralize_controls`.
  An `OSError` (e.g. `FileNotFoundError`/`PermissionError`) embeds the offending file path
  in its message, so a hostile file name carrying ESC/CR/LF reaches stderr verbatim on the
  exit-2 path. The `rules`/`doctor`/`init`/`baseline` success outputs also bypass the
  reporter, but they emit only rule metadata, config-author paths and static text, not
  scanned finding names.
- Impact: terminal/CI-log control-byte injection on the error path (narrow trigger: an
  `OSError` whose message embeds a control-laden scanned path; stderr only; exit 2). The
  `test_reporter_hostile_filename` test checks only `stdout`; the adversarial suite checks
  `stdout+stderr` but no case produces such an `OSError`, so neither guards this sink.
- Mitigation: route CLI error strings through `_neutralize_controls` (or render the path
  component with it) before printing. Low priority relative to the two MEDIUMs.

### [LOW] Adversarial suite does not assert expected findings for security-relevant cases
- Vector / evidence: `tests/integration/test_adversarial_runtime_cases.py` allows
  `frozenset({0, 1})` for `traversal_and_absolute_targets`, `windows_drive_unc_backslash`,
  `symlink_escapes` and others, asserting only documented-exit + no-traceback +
  no-control-bytes + under-ceiling + deterministic. It never asserts that the expected
  DS116 path-escape / symlink-out finding is actually produced.
- Impact: a crash-with-exit-1 is still caught (the `b"Traceback" not in stderr` assert and
  the fact that argparse/config errors exit 2 would fail a `{0,1}` case). But a
  **fail-open** regression - a detector silently ceasing to flag a traversal or an in-root
  symlink that escapes the root - yields exit 0 which is in `{0,1}` and passes here. This
  is a security-relevant blind spot for a robustness harness, though per-rule DS116
  integration tests cover the correctness.
- Mitigation: for the containment-relevant cases, assert at least one DS116 finding (or a
  minimal expected count) in addition to the safety invariants.

### [LOW] 120 s ceiling is too loose to detect a DoS/performance regression
- Vector / evidence: `_CEILING_SECONDS = 120.0` versus the performance report's ~13 s
  worst case at 2000 files and ~4 s for the adversarial cases.
- Impact: the ceiling trips only on a catastrophic hang/infinite loop; a 5-10x slowdown
  passes. This is a deliberate anti-flake choice, documented in the performance report
  ("asserts only a generous 120 s ceiling ... so it cannot flake"), and acceptable - but
  it means the suite provides no meaningful DoS-regression protection.
- Mitigation: none required; recorded so reviewers do not read the suite as a performance
  gate. A separate, machine-normalized benchmark assertion would be the right tool if one
  is wanted.

### [LOW] Pre-existing: a runtime spaCy-load failure raises RuntimeError the CLI does not catch
- Vector / evidence: if `deep_ready()` passes (libraries + model package present) but
  `spacy.load` fails at runtime, `deep_support.load_pipeline` raises `RuntimeError`
  (`deep_support.py:58-59`). `cli.py:229` catches only
  `(ConfigError, ValueError, OSError)`, so a `RuntimeError` would propagate as a traceback
  (exit 1).
- Impact: a non-graceful deep failure mode in a corner case. **Not introduced by this
  change** (the lazy import is reached only after `deep_ready()` and does not alter this),
  and the common missing-libs/missing-model cases are handled gracefully by the
  `deep_ready()` gate. Recorded for completeness.
- Mitigation: add `RuntimeError` to the CLI's caught set (returning exit 2 with the
  install-guidance message). Out of this task's scope.

## Verdict: PASS_WITH_FOLLOWUP

No CRITICAL finding: the primary attack - forging a GitHub workflow command from a hostile
file name, message, path or title - is correctly blocked, the byte-identity and
determinism invariants hold, and the DS301 lazy import preserves rule
registration/selection/gate semantics while provably keeping spaCy off the fast path. The
two MEDIUM findings (U+2028/U+2029 not neutralized; lone-surrogate paths crashing the
text/github sinks on non-UTF-8 filesystems) are completeness gaps in the same hardening,
not injection vectors, and should be fixed as follow-ups by `python-expert` with
regression tests from `testing-expert`. The LOW items are defense-in-depth and test-
strength observations. Nothing here blocks merge to `master`.
