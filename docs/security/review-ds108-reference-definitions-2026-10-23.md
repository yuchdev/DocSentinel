# Security review findings - Story 05.0 DS108

- Date: 2026-10-23
- Reviewer: Security Auditor (DocSentinel)
- Target: `src/docsentinel/detectors/references.py` (DS108, uncommitted), relying on
  the shared scanner `src/docsentinel/markdown_blocks.py`.
- Tests reviewed: `tests/unit/test_detectors_references.py`,
  `tests/integration/test_detectors_reference_definition_integrity_ds108.py`.
- Method: differential comparison of DS108 recognition against a `markdown-it-py`
  4.2.0 CommonMark oracle; doubling-series DoS timing/memory; output-injection
  probes through all three report sinks; file-open/network auditing via a Python
  audit hook; fingerprint/baseline and DS101-interaction checks.

DS108 is a pure, deterministic reference-*identity* check at `warning` severity in
the `fast` profile. It performs no network, subprocess, or symlink I/O and never
resolves a reference target on disk. All issues below are **accuracy/honesty**
items (spurious or missing non-blocking warnings), not spoofing, tampering,
injection, disclosure, DoS, or privilege findings.

## Assets & trust boundaries

- Untrusted input: the UTF-8 **content** of Markdown documents handed to
  `detect()` (reference labels, definition targets, surrounding text).
- Trust boundary crossed: document bytes -> `check_text` recognition ->
  `Finding.message` -> text/json/github report sinks (and the SHA-256 baseline
  fingerprint).
- Trusted inputs (out of DS108's scope): the `documents` tuple and `root` come
  from the engine/discovery layer, not from document content.
- Key safety property verified: untrusted content never drives a filesystem
  access, a network call, or code execution. The echoed label is the only piece
  of untrusted data that reaches a report sink, and it is bounded and escaped.

## Findings

### [LOW] Spurious undefined-reference warnings inside indented (four-space) code blocks
- Vector / evidence: `references._masked_lines` masks only fenced code, inline
  code, and HTML comments (`references.py:162-167`); the shared scanner does not
  model indented code blocks. Oracle case `indented_code_use`
  (`    [text][missing]`): markdown-it renders literal code (0 links); DS108 emits
  `undefined reference label: missing` at the indented line.
- Impact: a reference-looking token inside a four-space code example is reported
  as a broken reference (false positive, `warning` severity, non-blocking).
- Mitigation: documented dialect gap (`docs/dev/markdown_dialect.md` lists
  "Indented (four-space) code blocks" as not recognized) and shared by every fast
  rule including the already-shipped DS101, so DS108 introduces no new class of
  surprise. Follow-up: consider masking indented code blocks in the shared
  scanner, or note the limitation in the DS108 message contract. Related: CWE-1287
  (improper input validation of structured content) in the honesty sense only.

### [LOW] Spurious undefined-reference warnings inside multi-line inline code spans
- Vector / evidence: `markdown_blocks.find_code_spans` operates per physical line,
  so a code span opened on one line and closed on another is not masked. Oracle
  case `multiline_code_span` (`` a `code\n[text][missing]\ncode` b ``): markdown-it
  treats the whole span as code (0 links); DS108 flags `missing` on the middle
  line.
- Impact: false-positive `warning` on reference-looking text that a CommonMark
  renderer treats as literal code.
- Mitigation: documented dialect gap (`docs/dev/markdown_dialect.md`: "Multi-line
  inline code spans ... are not recognized"), shared with DS101. No evasion in the
  other direction was found: an unclosed single-line backtick does not mask a
  later line, so a real broken reference cannot be hidden behind a stray backtick.

### [LOW] Multi-line reference definition is not recognized, so its uses look undefined
- Vector / evidence: `_REF_DEF_RE` (`references.py:94`) requires the destination on
  the same physical line (`\]:\s*\S`). Oracle case `multiline_def`
  (`[label]:\nx.md`): markdown-it defines `LABEL` and links the use; DS108 reports
  `undefined reference label: label` for `[use][label]`.
- Impact: false-positive `warning` when a definition places its destination on the
  following line (a valid but uncommon CommonMark form).
- Mitigation: rare in practice; matches the shared scanner's own line-oriented
  definition recognition. Follow-up only if multi-line definitions appear in the
  corpus.

### [LOW] Use-scanner vs definition-regex disagree on labels containing an escaped bracket
- Vector / evidence: `_scan_uses`/`_closing_bracket` honour `\]` inside a label
  (`references.py:171-248`), but `_REF_DEF_RE`'s `[^\]]+` label class
  (`references.py:94`, mirrored in `markdown_blocks._REF_DEF_RE:80`) cannot. Oracle
  case `label_with_escaped_bracket`: `[t][a\]b]` with `[a\]b]: x.md` is a resolved
  link in markdown-it, but DS108 recognizes the *use* and fails to recognize the
  *definition*, emitting `undefined reference label: a\\]b`.
- Impact: false-positive `warning`: a correctly defined label that contains an
  escaped `]` is reported as undefined. This is an internal inconsistency between
  DS108's two recognizers, not merely a dialect gap.
- Mitigation: hand the escaped-bracket label-parsing asymmetry to `python-expert`
  so the definition recognizer matches the use recognizer (or so both skip such
  labels), and add a regression fixture via `testing-expert`. Labels with escaped
  brackets are unusual, so severity is LOW, but this is the most defensible
  accuracy fix of the set.

### [LOW] Collapsed/full multi-line use is missed, yielding a false "unused" under the opt-in
- Vector / evidence: `_scan_uses` runs per line; a use split across a newline
  (`[text][la\nbel]`) is not recognized. Oracle case `multiline_label_use`:
  markdown-it links it against `[la bel]: x.md`; DS108, with
  `unused_reference_definitions=true`, reports `unused reference definition: la bel`.
- Impact: false-positive `unused` warning. Gated behind the opt-in
  `unused_reference_definitions` policy (off by default), so it cannot fire on a
  default scan.
- Mitigation: accept as a documented line-oriented limitation; the default-off
  gating keeps it out of the shipped default behavior.

### [INFO] DS108 is more lenient than CommonMark on label normalization (false negatives)
- Vector / evidence: `normalize_label` applies NFC + `casefold`
  (`markdown_blocks.py:386-398`) whereas markdown-it uses
  `trim/collapse + toLowerCase().toUpperCase()` with no NFC. Oracle cases
  `nfc_precomposed_vs_decomposed` and `html_block_def`: DS108 treats
  precomposed/decomposed labels as equal (so it does not flag a use markdown-it
  would leave unlinked), and DS108 honours a definition inside an HTML `<div>`
  block that CommonMark ignores. Greek sigma, eszett, Turkish dotted-I, NBSP, tab,
  and HTML-entity cases all agreed with the oracle.
- Impact: under-reporting (missed `undefined` warnings) in these edge cases - the
  conservative direction for a default-on warning rule; no safety impact.
- Mitigation: none required; NFC-folding is a reasonable, deterministic choice.

### [INFO] Baseline fingerprint is label-granular, not line-granular
- Vector / evidence: `baseline.fingerprint` is `rule:path:sha256(message)[:12]`
  with no line number (`baseline.py:13-16`). Verified: two undefined uses of the
  same label on different lines in one file produce one identical fingerprint, so
  baselining one suppresses the other.
- Impact: a newly introduced undefined use of an already-baselined label in the
  same file is silently suppressed. This is the framework-wide fingerprint design,
  not DS108-specific, and the message is the intended dedup key.
- Mitigation: none required for DS108; flagged for awareness. Determinism and
  round-trip stability were confirmed (repeated scans byte-identical).

### [INFO] Bounded echo can collapse distinct long labels to one message/fingerprint
- Vector / evidence: `_echo` truncates at `_MAX_ECHO = 80` characters then appends
  `...` (`references.py:98,106-119`). Verified: two labels sharing their first 80
  characters yield identical messages and therefore one baseline fingerprint
  (both still surface as separate findings in a live scan via distinct columns).
- Impact: two different broken labels can be indistinguishable in the report
  message and collapse under baseline.
- Mitigation: accepted - the bound is a deliberate and correct DoS mitigation
  (see DoS section). No change recommended.

## STRIDE-lite results (non-findings confirmed safe)

- Tampering / injection (CWE-150 control-char injection, ANSI/terminal escape
  injection, GitHub Actions workflow-command injection): SAFE. `_echo` passes the
  label through `str.encode("unicode_escape")`, so ESC (`\x1b`), C1 CSI (`\x9b`),
  NUL, backspace, DEL, tab, newline, and RTL/bidi overrides (`‪`-`‮`) all
  render as printable `\xNN`/`\uNNNN`. Across text/json/github sinks no message
  contained a raw control, C1, NUL, or newline byte. A `::warning file=evil::`
  payload inside a label stays mid-line in the github sink, and GitHub only parses
  workflow commands at the start of a line, so no `::`-command injection is
  possible. A `]`-bearing payload is truncated at the closing bracket before it
  can form.
- DoS (CWE-400 / CWE-1333): SAFE. Doubling-series slopes (log2 time ratio per
  doubling, target < 1.3) for open-bracket floods, `][` adjacency, full-reference
  floods, definition floods, a single huge label, backtick floods, deep `[`-nesting,
  CRLF, NUL, comment-per-line, unclosed-comment-then-references, and fenced-body
  masking all converged to ~1.0-1.2 (no shape stayed above 1.3 across a 5-point
  series up to 128k units). Peak memory scaled linearly (<=~41 MB at 32k findings).
  No quadratic rescan was observed; the single forward-pass use scanner and the
  bisect-indexed code-span/comment masks hold up on adversarial input.
- Information disclosure: SAFE. No secret handling; the only untrusted datum that
  reaches a sink is the bounded, escaped label echo. No PII/credential surfaces.
- Spoofing / tampering via I/O (CWE-22 path traversal, symlink following): SAFE.
  An audit-hook trace of `detect()` over a document that *defines*
  `[o]: ../../outside/secret.md` and `[secret]: ../secret.md`, with an in-root
  `escape` symlink to an out-of-root tree, opened only the one handed
  `docs/README.md`; the in-root `secret.md`, the out-of-root `outside/secret.md`,
  and the `escape` symlink were never opened. The only other open was the
  interpreter lazily loading the `unicode_escape` codec. Zero
  socket/connection/subprocess/`os.system` events. Untrusted labels and definition
  targets never drive a file open because DS108 resolves no targets.
- Invalid/unreadable input: `references._read_text` uses
  `open(encoding="utf-8")`, so invalid UTF-8 raises `UnicodeDecodeError` and an
  unreadable file raises `PermissionError` - surfacing rather than a silent clean,
  as the integration suite asserts. Symlinked Markdown files are excluded at the
  engine/discovery layer (DS108's `detect` trusts its document list by design;
  direct library misuse with a symlink path is out of scope).
- Repudiation / audit, Elevation: not applicable - DS108 takes no action on
  production data or external services and performs no automated remediation.

## DS101 interaction (no double-reporting)

Confirmed: DS101's matcher `_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")`
(`src/docsentinel/detectors/links.py:20`) requires inline `](target)` parentheses,
so a reference-style `[text][label]` never matches DS101. An undefined reference
label is therefore DS108's alone. The integration suite asserts this
(`test_undefined_reference_is_ds108_only_never_ds101`). DS108 resolves no targets,
so it also cannot collide with DS116 (path boundaries) or DS103 (unresolvable
paths).

## Verdict: PASS_WITH_FOLLOWUP

DS108 is **safe to ship default-on at `warning` severity.** No CRITICAL/HIGH
issue exists: there is no injection, path traversal, information disclosure,
privilege, or DoS exposure. Output is bounded and escaped across all sinks, the
analyzer touches only the documents it is handed, and adversarial input stays
linear in time and memory.

The follow-ups are accuracy/honesty items that produce spurious or missing
*non-blocking* warnings, all consistent with the project's documented Markdown
dialect and shared with existing fast rules:

1. (LOW, recommended) Fix the escaped-bracket label asymmetry between `_scan_uses`
   and `_REF_DEF_RE` so a validly defined `[a\]b]` label is not reported undefined
   - hand to `python-expert`; add a regression fixture via `testing-expert`.
2. (LOW, optional) Mask indented code blocks and multi-line code spans in the
   shared scanner, or note these gaps in the DS108 message contract.
3. (LOW, optional) Recognize multi-line reference definitions, or document the
   limitation.

Because the two highest-impact gaps are already documented dialect limitations
shared with the shipped DS101, and the remaining items are LOW/INFO, DS108 clears
the merge gate as PASS_WITH_FOLLOWUP.
