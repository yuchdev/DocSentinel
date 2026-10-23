# Security review - DS118 Documentation file and directory naming policy - 2026-10-23

Post-implementation adversarial review of the **shipped, uncommitted** `DS118`
(branch `milestone/0005-deepening-test-case-stage-2`): the detector
`src/docsentinel/detectors/naming.py`, its `documentation_naming*` config options
in `config.py`, the unit/mock/integration tests
(`tests/unit/test_detectors_documentation_naming.py`,
`tests/mock/test_detectors_documentation_naming_oracle.py`,
`tests/integration/test_detectors_documentation_path_naming_policy_ds118.py`),
the `tests/assets/ds118/*` fixtures, and the registration wiring in
`src/docsentinel/detectors/__init__.py`.

`DS118` is an **opt-in** (`documentation_naming`, off by default), `warning`-severity,
`fast`-profile rule. It is a **pure path-string policy** over each discovered
document's relative POSIX path: it performs no filesystem access of any kind and
never reads document content. Inputs it treats as untrusted: the document path
strings (from discovery or an injected `Document`) and the author-influenced
config (`documentation_naming_allow`, `documentation_naming_prefix_patterns`,
`documentation_naming_directories`), which an API consumer may inject directly,
bypassing `load_config`'s gates.

The DS114/DS115/DS116/DS113/DS112 standing floor is applied: zero outside-root
I/O and no existence oracle, no quadratic/shared-prefix blow-up, a bounded
repr-escaped echo of author-influenced text, user text never compiled as a regular
expression, fail-closed validation of an injected `Config`, and an honest opt-in
surface. Relevant identifiers: CWE-117 (log/output injection), CWE-150 (improper
neutralization of escape sequences), CWE-20 (improper input validation), CWE-1333 /
CWE-400 (ReDoS / resource exhaustion), CWE-22 (path traversal - assessed for the
suggested-rename output), CWE-179/CWE-176 (improper Unicode/normalization
handling), CWE-693 (protection-mechanism failure), OWASP A09:2021 and A03:2021.

Evidence scripts live only in the session scratchpad; no product code or other
docs were modified. Dynamic checks ran under the project `uv` environment with a
`sys.addaudithook` syscall recorder.

## Assets & trust boundaries

- **Assets:** terminal/CI-log integrity of the rendered report; scan availability
  (no DoS); correctness of the opt-in gate (an off policy must be inert); the
  invariant that a suggested rename is always a safe, ASCII, separator-free,
  traversal-free token.
- **Boundary 1 - document path strings -> DS118 -> `Finding.path`/`Finding.message`
  -> reporting sinks.** Discovery yields in-root, forward-slash relative paths, but
  an individual path *component* can legally carry any byte except `/` and `NUL`
  on POSIX (ESC, newline, C1, RTL override, `::error::`). An injected `Document`
  (Python API) can additionally carry absolute/`..`/duplicate-slash/backslash
  shapes and arbitrarily long components.
- **Boundary 2 - injected `Config` -> `_Policy`.** `documentation_naming`,
  `documentation_naming_allow`, and `documentation_naming_prefix_patterns` are
  author text. A direct `Config(...)` construction bypasses `load_config`, so the
  detector must re-validate the style enum and the pattern count/length bounds
  itself (fail-closed).
- **Boundary 3 - suggested-rename generator -> report.** NFKD-folded,
  transliterated author text that must never emit a path separator, `..`, a
  control byte, or a non-ASCII byte.

## Findings

### [MEDIUM] Reporting text sink prints `Finding.path`/`Document.path` raw - not DS118's to fix, but it is DS118's inputs that surface it

- Vector / evidence (`src/docsentinel/reporting.py:79`, `:81`): the text renderer
  emits `f"  {document.path} ({document.bytes} bytes)"` and
  `f"{finding.severity}: {finding.path}: {finding.message}"` with `path`
  interpolated **raw**. A file legally named `docs/evil\x1b[31m\n::error::spoofed.md`
  on a POSIX disk reaches the terminal/log with the literal `ESC` and newline
  intact (reproduced: `ESC present in text output: True`, raw newline present).
  The GitHub sink is safer: `_escape_property` (`reporting.py:9`) neutralizes
  `% \r \n : ,`, so the dangerous `\n::error::` injection into the `file=` field is
  defused (reproduced: `raw newline in github file= field: False`) - but it does
  **not** strip `ESC`, so `\x1b` survives into the annotation body (reproduced:
  `ESC present in github output: True`).
- Impact: terminal-escape manipulation and, in the text sink, a spoofed extra
  report line (CWE-117, CWE-150). Severity MEDIUM, not higher, because the
  CI-annotation-forging bytes (`\n`, `::`) are already escaped on the GitHub sink.
- Mitigation / ruling: **This is a pre-existing, rule-agnostic weakness in
  `reporting.py`, not introduced or worsened by DS118.** Every rule's `Finding.path`
  comes from the same discovery paths and has always flowed raw to the text sink;
  DS118 adds no new path value. DS118's own author-influenced content - the
  offending component - is correctly bounded and escaped through `_echo`
  (`naming.py:192`), and its deterministic suggestion is ASCII by construction, so
  the DS118 **message** is clean on both sinks (verified). **It must NOT block the
  DS118 merge.** Hand off as a separate follow-up against `reporting.py`: escape or
  repr-bound `path` in the text sink (lines 79, 81) and add `ESC`/C0 stripping to
  `_escape_property`/`_escape_data`. This extends the existing
  `review-github-actions-annotations-2026-10-10.md` scope.

### [LOW] Suggested-rename length is unbounded (only the offending echo is bounded)

- Vector / evidence (`naming.py:490-492`, `_suggest_component` `:299`): the finding
  message bounds the offending component to 80 chars via `_echo`, but the
  `suggestion` is embedded at full length. A 10,000-char injected component yields a
  10,000-char suggestion (reproduced: `in_len=10000 out_len=10000`); a 160k injected
  component yields a 160k-char message.
- Impact: unbounded report-string growth for a hostile corpus delivered through the
  Python API (CWE-400). Content is safe (ASCII, conformant), so this is size-only.
- Mitigation: real filesystem components are bounded by `NAME_MAX` (255 bytes), so
  discovery can never trigger this; it is reachable only via an injected `Document`,
  the same lower-trust in-memory surface noted for DS114/DS115. Recommend bounding
  the suggestion the way `_echo` bounds the offending text. Follow-up, not a blocker.

### [LOW] Glob/suggestion cost scales with injected component length (no per-component cap)

- Vector / evidence (`_glob_matches` `:210`, `_Policy._name_is_exempt` `:396`): the
  per-component exemption check runs each (count-bounded, length-bounded) prefix
  pattern against the component with a two-pointer walk. Cost is
  `O(pattern_count x pattern_len x component_len)`. Measured worst case
  `*a*a...*b` (242-char pattern) against a 160k-char component: ~46 ms per call -
  polynomial, **not** exponential (a classic catastrophic-backtracking shape stays
  linear in text here because the single-star pointer never re-expands).
- Impact: with 256 patterns x a 160k injected component this is ~12 s for one
  component - a bounded DoS reachable only through injected `Document`s (CWE-400).
- Mitigation: real FS components are `NAME_MAX`-bounded (242 x 255 ~ 0.12 ms, i.e.
  negligible), and `_Policy` memoises per distinct component so a flooded
  shared-name corpus is evaluated once. Acceptable at this severity; a per-component
  length guard would fully close the injected case. Follow-up, not a blocker.

### [LOW/INFO] Malformed injected paths yield empty / ".." component findings

- Vector / evidence (`check_path` `:447`): `/abs/Bad.md`, `../escape/Bad.md`,
  `a//b/Bad.md`, and a trailing slash split into empty or `..` components and are
  reported as `directory name ""` / `directory name ".."` findings. All handled as
  pure string operations - no raise, no filesystem touch (reproduced).
- Impact: cosmetic only; the suggestion for `..` is the safe literal `document`, and
  no traversal is performed because DS118 never touches disk.
- Mitigation: discovery never emits absolute, `..`, duplicate-slash, or
  trailing-slash relative paths, so this is unreachable in the real pipeline. No
  action required; noted for completeness.

## BLOCK-condition verification (all PASS - no CRITICAL)

- **Zero filesystem access (proven).** A `sys.addaudithook` recorder over
  `detect()` across 1,001 hostile documents captured **no** `open`/`stat`/`lstat`/
  `scandir`/`listdir`/`readlink` on any document path. The single observed `open`
  was the one-time CPython load of the `unicode_escape` codec `.pyc` (runtime
  import, not document I/O). The committed mock test independently arms every FS
  entry point to raise and the detector still produces findings. PASS.
- **Patterns are not regex/fnmatch and carry no ReDoS.** `[abc]`, `a.b`, `a+` are
  all matched as literals (verified: no character classes, no `.`/`+` metacharacters,
  no anchors); `*`/`?` behave as a restricted glob. User text is never passed to
  `re`. The matcher is polynomial, not exponential. PASS (CWE-1333).
- **Config bounds enforced for the injected path.** Injected
  `documentation_naming_prefix_patterns` of 257 entries, or a 257-char entry, both
  raise `ConfigError` via `_validated_patterns` (`naming.py:250`); 256/256 are
  accepted at the bound. Note: `load_config` validates these only as nonempty
  strings (`_require_str_list`), so `_validated_patterns` is the **sole** enforcement
  point for the 256/256 caps - and it runs on every path (TOML and injected) because
  it is called from `_Policy.__init__`. PASS.
- **Fail-closed on an invalid style.** An injected `documentation_naming="PascalCase"`
  raises `ConfigError` rather than silently degrading (`naming.py:384`). PASS.
- **Suggestion is always safe.** Across traversal-shaped inputs (`../../etc/passwd`,
  `a/b/c`, `a\b`, `..`, `::error::x`, fraction-slash `U+2044`, NUL/C0, Arabic
  ligature `U+FDFA`), no suggestion ever contained `/`, `\`, `..`, a control byte,
  or a non-ASCII byte (0 unsafe over the matrix). NFKD non-ASCII expansions are
  dropped, so `U+FDFA`-style 18x compatibility blow-ups contribute nothing and an
  all-non-Latin name falls back to the literal `document`. No path-traversal-looking
  suggestion can be produced. PASS (CWE-22, CWE-179).
- **Bounded, escaped echo.** `_echo` caps at 80 chars and `unicode_escape`s ESC,
  newline, NUL, and RTL override to printable `\xNN`/`\uNNNN` forms (verified clean).
  PASS.
- **Opt-in honesty.** `DS118` registers `opt_in_option="documentation_naming"`;
  `opt_in_satisfied` is `False` for `off` and `True` for `kebab`; `detect()` with
  the default config returns `()` with zero work. PASS.
- **Scaling is linear.** Doubling the corpus (2k -> 32k documents, deep shared
  directory prefix, 16 patterns) scales ~2.0x per doubling (linear O(N)); `_Policy`'s
  per-component memoisation keeps a shared-prefix corpus from going quadratic. PASS.

## Test-gate integrity

- The committed mock oracle proves the zero-filesystem contract with no skip/xfail.
  The unit and integration suites parametrize the violation matrix (case,
  uppercase, separator, camelCase, non-ASCII, directory, exemptions) and both TOML
  and `pyproject.toml` config sources.
- The only catalog change (`FINDING_SATISFIES_ERROR` in
  `test_milestone_0005_fixture_catalog.py`) is a **DS114** ruling (a single
  explicitly-pinned `("DS114", "invalid_nested_metadata")` pair allowed to satisfy
  an error-outcome scenario via an own finding). It is a narrow, documented
  allowlist of exactly one entry; every other error-outcome scenario still must
  raise `ConfigError` or be pending. It does **not** touch or weaken any DS118
  scenario gate. The `config.py` diff is a DS114 `document_id_field` tightening, not
  a DS118 change. No gate is weakened.

## Verdict: PASS_WITH_FOLLOWUP

No CRITICAL and no HIGH. DS118 is a correctly fail-closed, zero-I/O, ReDoS-free,
honestly-opt-in pure path policy whose own report content is bounded and escaped.
Two LOW hardening items (bound the suggestion length; optionally cap per-component
glob input) and one MEDIUM cross-cutting item (the `reporting.py` text sink prints
`Finding.path`/`Document.path` raw, and `_escape_property`/`_escape_data` do not
strip `ESC`) are follow-ups and do **not** block the DS118 merge: the reporting
weakness is pre-existing, rule-agnostic, and not worsened by DS118, and its fix
belongs in `reporting.py`, not `naming.py`. Hand the suggestion/glob bounds to
`python-expert` with regression tests from `testing-expert`; raise the reporting
hardening as a separate `reporting.py` issue extending
`review-github-actions-annotations-2026-10-10.md`.
