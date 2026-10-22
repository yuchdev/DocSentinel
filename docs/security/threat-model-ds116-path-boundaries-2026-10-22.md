# Threat Model - DS116 Path Traversal Outside Documentation Root - 2026-10-22

This is the standing, pre-implementation threat model for Story 11.0 (DS116,
fast profile, default severity `error`). It is normative input for every task
briefing and every reviewer of Story 11.0 and must be linked from each. It was
produced before any detector code was written; the behavior it attributes to
DS101 and DS103 was confirmed empirically (see the evidence section), not assumed.

DS116 detects documentation references that escape the configured scan root:
lexical parent-directory escapes, percent-encoded escapes, absolute and
drive/UNC paths, and in-root symlinks that point outside. It maps to CWE-22,
CWE-23, CWE-36 (absolute path traversal), CWE-41 (path equivalence), CWE-59
(link following), CWE-172 and CWE-174 (encoding and double-decoding), and OWASP
A01:2021 Broken Access Control. The reporting and oracle concerns map to CWE-203
(observable discrepancy), CWE-117 (log injection), and CWE-400 with CWE-1333
(resource and regular-expression DoS).

## Scope and method

In scope: the proposed analyzer path_boundaries.py, the shared resolver
`resolve_local_reference` and token scanner in
`/src/docsentinel/markdown_blocks.py`, the existing readers in
`/src/docsentinel/detectors/links.py` (DS101) and
`/src/docsentinel/detectors/paths.py` (DS103) that DS116 must stop
short-circuiting, discovery symlink handling in
`/src/docsentinel/discovery.py`, the DS116 config options in
`/src/docsentinel/config.py`, and the report sinks in
`/src/docsentinel/reporting.py`. The method is STRIDE-lite over the trust
boundary from untrusted Markdown content to the filesystem and to report sinks.

## Assets and trust boundaries

| Asset | Trust level | Why it matters |
|-------|-------------|----------------|
| Untrusted Markdown content | Hostile | Authors and PR contributors control every link, image, reference definition, HTML attribute, and code-span target. |
| Scan root subtree | Trusted boundary | The only region DS116 may read; the containment boundary itself. |
| Filesystem outside the root | Off-limits | Must never be opened, stat-ed, or symlink-followed by DS116. |
| Report sinks (text, json, github) | Semi-public | Rendered into CI logs and PR annotations by reporting.py; attacker-influenced strings land here. |
| CI logs and annotations | Public-ish | Visible to anyone who can read the build; an existence oracle or injected control bytes leak here. |
| Pass/fail exit code | Integrity signal | The `error` severity makes DS116 blocking (exit 1); suppressing it silently defeats the gate. |

Threat actors: a contributor submitting a malicious Markdown tree in a PR that
runs through CI or pre-commit; a reader of public CI logs harvesting an existence
oracle; a supply-chain concern is out of scope here (stdlib-only analyzer).

## Empirical evidence (confirmed in a scratch temp dir, not assumed)

The current readers resolve and stat escaped targets outside the root:

- `/src/docsentinel/detectors/links.py` lines 85-89 and 134-135: DS101
  `_resolve` joins the target onto the source directory, calls `resolve()`, then
  `exists()`. `resolve()` follows symlinks; `exists()` stats the target.
- `/src/docsentinel/detectors/paths.py` lines 76-82 and 128: DS103 does the same
  for path-like code spans.

Observed with a document under a scratch root containing a link whose
parent-directory chain climbs past the filesystem root to a real file and a
sibling to a non-existent one:

```text
[real](many ../ segments; clamps to /etc/passwd)   -> NO DS101 finding (it exists)
[fake](many ../ segments; /etc/zzz_nope)            -> DS101 "dangling link" finding
```

The resolved path was /private/etc/passwd and `exists()` returned True after
`resolve()` followed the /private/etc symlink. The finding versus no-finding
signal therefore discloses whether an arbitrary path outside the root exists, and
the stat touched a path outside the root. This is the oracle DS116 must eliminate.

The shared lexical resolver classifies the adversarial corpus as follows (scratch
run against a root with document docs/README.md). Raw targets are shown as plain
text so this page does not itself trip DS103:

| Raw target | Current status | Note for DS116 |
|------------|----------------|----------------|
| ../../secrets.md | OUTSIDE_ROOT | Finding. Correct. |
| %2e%2e/%2e%2e/file.md | OUTSIDE_ROOT | Finding. Decode-once works. |
| ..%2f..%2fx.md | OUTSIDE_ROOT | Finding. Encoded separator decodes. |
| %252e%252e/x.md | RESOLVED (literal %2e%2e dir) | Decode-once correct; fixture expects FINDING. See gap G1. |
| C:\Windows\win.ini | UNSUPPORTED | Must be a finding under `windows_path_policy`. |
| c:/win and C%3A/win | UNSUPPORTED | Drive letter; must be a finding. |
| backslash-backslash server share | UNSUPPORTED | UNC; must be a finding. |
| //host/share | EXTERNAL | Protocol-relative URL; clean. |
| file scheme URL to /etc/passwd | EXTERNAL | URL scheme; clean. |
| ~/secret and $HOME/x | RESOLVED (literal) | No tilde or env expansion; stays in root; clean. |
| /etc/passwd | RESOLVED as root-relative | Reinterpreted under root; clean (see gap G3). |
| ..%5c..%5cx (encoded backslash) | UNSUPPORTED | Must be a finding. |
| x.md?../../y (query suffix) | UNSUPPORTED (glob char) | Must stay a non-finding. |
| ../x.md#a (fragment) | RESOLVED | Fragment stripped; in-root; clean. |
| fullwidth-dot pair then /x (U+FF0E) | RESOLVED (literal) | Confusable is not ASCII parent token; stays in root; clean. |
| a/../b | RESOLVED | Oscillation collapses; clean. |
| rooted backslash Windows sys | UNSUPPORTED | Must be a finding. |
| /docs/guide.md | RESOLVED | Root-relative; clean. |
| mailto and https URLs | EXTERNAL | Clean. |

The resolver already decodes exactly once (markdown_blocks.py line 1209) and
treats the remainder literally, so the double-encoded form stays in-root. That is
the security-correct behavior and must not be changed to double-decode.

## STRIDE findings

Each finding lists severity, required control, and a concrete adversarial test
case. "Matrix" marks cases already covered by the 15 Task 02 fixture scenarios;
"extra" marks tests the implementer must add beyond the matrix.

### [HIGH] Existence oracle and outside-root I/O in DS101 and DS103

- Vector and evidence: links.py lines 85-89 and 134-135, and paths.py lines 76-82
  and 128; demonstrated above. `resolve()` follows symlinks and `exists()` stats
  targets that lexically escape the root, and the finding signal leaks existence
  into CI logs (CWE-203, CWE-22, CWE-59).
- Impact: a PR author reads whether arbitrary absolute or relative-escape paths
  exist on the CI host, and DocSentinel performs filesystem access outside the
  scan boundary it promises to respect.
- Mitigation (required, must land with DS116): DS101 and DS103 must route every
  target through the shared lexical resolver and must not call `resolve()` or
  `exists()` on anything that is not classified RESOLVED inside the root. Replace
  `resolve()` with a non-following containment check. Targets classified
  OUTSIDE_ROOT, drive, UNC, backslash, or control become DS116's concern and must
  never be stat-ed by DS101 or DS103. Regression-test that DS101 and DS103 public
  behavior for in-root targets is unchanged.
- Test case (extra, runtime symlink and scratch): a link to a many-parent target
  that clamps to a real outside file must yield exactly one DS116 finding and zero
  DS101 findings, and a fault-injected `os.stat()` or `Path.resolve()` must never be
  called with a path outside root (assert via a patched stat counter).

### [HIGH] Symlink inside root pointing outside - the safe containment check

- Vector and evidence: the resolver docstring at markdown_blocks.py lines
  1183-1196 is lexical-only and explicitly does not detect symlink escapes;
  fixture `symlink_escape_is_rejected` requires detecting an in-root symlink whose
  target is outside (CWE-59, CWE-367).
- Impact: a committed in-root symlink (for example a docs link pointing two levels
  up to an outside file) is lexically in-root, so a purely lexical resolver misses
  it; naive fixes such as `Path.resolve(strict=False)` or realpath follow the
  symlink and stat the outside target, reintroducing the oracle and a
  time-of-check-to-time-of-use race.
- Mitigation (required): the "safe, non-following containment check" is defined as
  follows. First do lexical containment on the raw and decoded target and reject
  lexical escapes with no filesystem access at all. Only for a target that is
  lexically in-root may DS116 walk the normalized components with `os.lstat()` per
  segment and `os.readlink()` (never `stat`, `open`, realpath, or `resolve`),
  computing each symlink's target lexically. If any component is a symlink whose
  lexical target escapes the root, emit the finding. The `os.lstat()` and
  `os.readlink()` calls touch only the symlink object itself, which lives inside
  the root, so no path outside the root is ever stat-ed. DS116 must never open or
  read file content, so the time-of-check-to-time-of-use window has no exploitable
  use inside DS116; downstream openers (DS101, DS113) must rely on this lexical
  gate and must not follow symlinks out of root themselves.
- Test case (matrix `symlink_escape_is_rejected`, generated at runtime with
  `tmp_path`): create an in-root symlink whose target is two levels above the root,
  link to it, assert one DS116 finding. Add an in-root symlink to an in-root file
  and assert no finding. Symlink tests may be skipped only with an explicit
  symlink-unavailable reason recorded in the test.

### [HIGH] Overloaded UNSUPPORTED hides the finding versus non-finding decision

- Vector and evidence: the resolver returns UNSUPPORTED with no reason for drive
  letters, UNC, backslashes, control bytes, templates with braces, and glob or
  query characters alike (markdown_blocks.py lines 1211-1221). `ResolvedReference`
  has no reason field.
- Impact: DS116 cannot tell an unsafe Windows, drive, UNC, backslash, or control
  path (must be a finding) from a template or query string (must stay clean), so
  it will either false-positive on `template_link_literal_skipped` and the query
  case or false-negative on `windows_absolute_drive_path`,
  `absolute_rooted_backslash`, and `encoded_separator_escape`.
- Mitigation (required): add a typed reason or category to the resolver result (or
  a DS116-local classifier reusing the resolver's decode-once output) that
  distinguishes drive, unc, backslash, control, template, and glob. DS116 emits
  findings only for the unsafe subset selected by `windows_path_policy` and leaves
  templates and query or glob cases clean.
- Test cases (matrix): `windows_absolute_drive_path`, `windows_unc_network_path`,
  `absolute_rooted_backslash`, and `encoded_separator_escape` are findings;
  `template_link_literal_skipped` is clean. Extra: the query case asserted clean.

### [MEDIUM] Information disclosure through echoed resolved path, type, or existence

- Vector and evidence: reporting.py lines 79-82 and 29-35 render `finding.message`
  verbatim into text, json, and github; DS101 today echoes the raw target
  unbounded.
- Impact: echoing a resolved absolute path, or the target's existence or type,
  leaks host layout and reintroduces the oracle through the message body.
- Mitigation (required): the DS116 message echoes only the author's raw target,
  bounded to a safe maximum length (for example 120 characters with an ellipsis),
  with repr-style escaping of non-printable and non-ASCII bytes, and never the
  resolved absolute path, existence, or file type. Reference the raw author string
  only.
- Test case (extra): a target of 10,000 characters yields a message under the
  bound; a target with embedded bytes is escaped in the message (see next finding).

### [MEDIUM] Log and workflow-command injection via crafted target bytes

- Vector and evidence: reporting.py `_escape_data` (lines 14-16) escapes percent,
  carriage return, and newline but not NUL or other C0 and C1 control bytes; the
  message carries the author-controlled raw target (CWE-117). The resolver rejects
  control bytes as UNSUPPORTED only on the decoded path component, but DS116 may
  still echo the raw target.
- Impact: control bytes (NUL, ESC) survive into CI logs and terminals; newline is
  already escaped so the github format cannot gain a new command line, but ESC
  sequences can still corrupt or spoof log output.
- Mitigation (required): DS116 must repr-escape control bytes in the echoed target
  before it reaches reporting, since reporting will not. Keep the existing newline
  and percent escaping in `_render_github`; do not weaken it.
- Test case (extra): a target containing NUL, ESC, and newline produces a message
  whose rendered text and github forms contain no raw control byte and no second
  command at line start.

### [MEDIUM] Algorithmic DoS on traversal floods and symlink walks

- Vector and evidence: DS116 adds per-target decode, lexical normalization, and an
  optional per-component symlink walk (CWE-400). A single document can carry a
  parent-segment flood, an encoded-dot flood, an oscillation flood, one very long
  segment, or many components.
- Impact: super-linear handling would let one crafted document stall every
  pre-commit and CI run.
- Mitigation (required): decode exactly once (`unquote` is linear); normalize with
  the existing list push and pop in `_normalize_relative` (linear); perform lexical
  containment before any `os.lstat()` so the symlink walk runs only over the
  collapsed in-root component count, not the raw parent-segment count; bound path
  length and component count. Reuse no catastrophic regular expression. Prove
  bounds with the `/tests/timing_helpers.py` helper `assert_scales_linearly` over a
  doubling series, for both single-line floods (parent-segment, encoded-dot, and
  oscillation repeats, plus long single segments) and multi-line floods, using CPU
  time.
- Test case (extra): doubling-series timing tests as above with a fixed expected
  finding count per size so the bound cannot pass vacuously.

### [MEDIUM] Scan-root subtlety - subdir root, symlinked root, cwd, individual docs

- Vector and evidence: containment is relative to the configured scan root, which
  may be a repo subdirectory or itself a symlink; the resolver joins against the
  passed root (markdown_blocks.py lines 1223-1232); discovery requires that the
  root is a directory (discovery.py line 13).
- Impact: an inconsistent root canonicalization lets a parent reference that stays
  inside the repo but above the scan root read as clean, or a symlinked root breaks
  containment comparisons.
- Mitigation (required): canonicalize the trusted scan root exactly once at engine
  entry (the single allowed realpath, on the trusted root, never on untrusted
  targets) and compare all containment against it. A reference above the scan root
  but inside the repo is still a finding; the scan root, not the repo, is the
  boundary. The current working directory must never enter resolution; documents
  passed individually use root plus document path only.
- Test cases: matrix `nested_parent_within_root`, `root_relative_local_link`, and
  `safe_parent_link_subdir` are clean; extra: a subdir-root scan where a parent
  reference escapes the subdir is a finding, and a symlinked root resolves
  containment consistently.

### [LOW] Confusables, tilde, env syntax, absolute POSIX paths treated as literals

- Vector and evidence: fullwidth dots (U+FF0E), U+2025, tilde, env-var syntax, and
  /etc/passwd all classify as in-root literals or root-relative (evidence table).
  No Unicode normalization collapses a confusable into the ASCII parent token.
- Impact: none exploitable; each stays inside the root as a literal filename or
  root-relative path, so none can escape; they are documented so reviewers do not
  "fix" them into traversal.
- Mitigation: keep the ASCII-only parent token as the sole traversal token; do not
  expand tilde or env vars; keep root-relative reinterpretation of leading-slash
  paths. Document gap G3 for the absolute-POSIX reinterpretation.
- Test case (extra): fullwidth-dot and tilde targets assert clean.

## Standing requirements checklist (apply to every Story 11.0 task and review)

- No filesystem access outside the root: never `open`, `stat`, `resolve`, or
  realpath a target that is not lexically confirmed inside the root; use
  `os.lstat()` and `os.readlink()` only on in-root symlink objects.
- Reuse the shared `resolve_local_reference` and scanner; do not add a second path
  resolver or a third-party parser; keep a stdlib-only import graph.
- Decode percent-encoding exactly once, then treat the remainder literally; never
  double-decode (the double-encoded form stays in-root).
- Fix the DS101 and DS103 outside-root stat and existence oracle in the same
  change; keep their in-root behavior regression-tested and unchanged.
- Lexical containment before any symlink walk; bounded linear-time handling with
  `assert_scales_linearly` doubling-series tests for single-line floods
  (parent-segment, encoded-dot, and oscillation repeats, plus long single
  segments) and multi-line floods, measured in CPU time.
- Bound and repr-escape the echoed raw target; never echo the resolved absolute
  path, existence, or file type; preserve the github newline and percent escaping.
- Distinguish unsafe UNSUPPORTED subcategories (drive, UNC, backslash, control)
  from safe ones (template, glob or query); findings only for the unsafe subset per
  `windows_path_policy`.
- Canonicalize the trusted scan root once; the scan root, not the repo, is the
  boundary; the current working directory never enters resolution.
- Default severity `error` (blocking, exit 1); DS116 registered exactly once in
  `RULES` and `ANALYZERS`, selectable via `select` and `ignore`, honoring baseline.
- All 15 Task 02 fixtures (5 clean, 10 finding, 0 error) loaded individually via
  `asset_case` into fresh `tmp_path`; expected outcomes from a checked manifest,
  not from whatever the analyzer currently emits.
- Generate symlink fixtures at runtime with `tmp_path`; skip only with an explicit
  symlink-unavailable reason; no skip or xfail used to hide regressions.
- Register through the fixture-catalog and manifest gating used by earlier Stage 2
  stories; keep CLI `rules`, `doctor`, baseline, and all three report formats in
  agreement.
- Pass flake lint rules X004 and X005 and the fast-only import isolation test (no
  spacy, textacy, sklearn, docsig, or network client on the fast path).
- Never execute, fetch, or import documentation content; no network access.
- Keep intentionally malformed ds116 fixtures byte-for-byte; exclude them from
  self-scan and formatters.
- Additional standing requirement 16: every construct the shared scanner masks
  must be masked only where CommonMark also hides it. The scanner must never hide
  a reference that a CommonMark renderer would render as a live link, image, or
  reference definition; over-masking is a detector-evasion hole (CWE-693).

## Spec gaps and contradictions (proposed resolutions)

- G1 (needs user ruling - changes the product contract): the double-encoded fixture
  `encoded_double_decode_attack` expects a FINDING, but a correct decode-once
  resolver classifies the double-encoded dot path as an in-root literal (RESOLVED,
  clean), confirmed empirically. Proposed resolution: DS116 emits the finding when,
  after the single decode, a path component still contains a percent-encoded dot or
  separator octet (a defense-in-depth "suspicious residual encoding" signal); this
  satisfies the fixture without ever double-decoding. Ruling needed because it
  decides whether that case is clean or a finding.
- G2 (needs user ruling - changes the contract surface): the resolver UNSUPPORTED
  tag is overloaded and carries no reason, yet fixtures require Windows, drive, UNC,
  and backslash cases to be findings and templates or query cases to be clean.
  Proposed resolution: add a typed reason to `ResolvedReference` (or a DS116-local
  classifier). Ruling needed because it extends the shared resolver's public result
  shape that other Stage 2 rules consume.
- G3 (recommendation, no ruling needed): absolute POSIX paths are reinterpreted as
  root-relative and classified clean. This is safe (stays in root) and consistent
  with the root-relative allowance, so keep it; just document it so reviewers do
  not mistake it for a bypass.
- G4 (recommendation, no ruling needed): the story text says "reject symlink
  traversal using a safe, non-following containment check" without defining it;
  this threat model's HIGH symlink finding supplies the operational definition
  (lexical first, `os.lstat()` and `os.readlink()` only on in-root objects, never
  stat the outside target). Adopt it as the normative definition.
- G5 (recommendation, no ruling needed): an in-root symlink pointing outside is
  DS116's territory per fixture `symlink_escape_is_rejected`; it overlaps DS101
  (which must now not follow it) and any future DS113. Keep DS116 as the policy
  owner of the escape and document the intentional overlap, as contract section E
  already directs for DS101 and DS116.

## Verdict: PASS_WITH_FOLLOWUP

No CRITICAL exists because no DS116 code is written yet; this is the pre-code
standing model. The spec is sufficient to begin, provided the standing
requirements are met and gaps G1 and G2 receive a user ruling before the fixtures
are frozen. Merge-gate condition for the human reviewer and the merge-blocking
hook: if DS116 ships without removing the DS101 and DS103 outside-root `resolve()`
and `exists()` oracle, or if it ever stats or opens a path outside the root
(including via realpath or `resolve()` on an untrusted target), or echoes a
resolved absolute path or existence into a report, that change is a BLOCK and must
be kept out of `master`.

## Rulings during implementation

One ruling was recorded during Story 11.0 Task 02 after the first full-repo
self-scan, and it narrows the code-span scope only. It does not relax any control
above.

DS116 keeps full strictness for links, image sources, reference definitions, and
HTML href, src, and srcset attributes: every unsafe category there is a finding.
For inline code spans only, DS116 now reports just genuine traversal: a lexical
root escape (including its percent-encoded and residual single-decode forms) and
an in-root symlink whose target points outside. Drive-letter, UNC, rooted- and
embedded-backslash, and control-looking code spans are treated as documentation,
not references, and are left to DS103's existing structural check; regex and
escape snippets (for example a backslash-n or a dollar-anchored pattern) are not
path-like at all and are not even considered.

The rationale is empirical and spec-backed. The first self-scan with DS116 at full
strictness produced only code-span hits across this repository's own
specification, threat-model, and reference docs, and every one was a documented
example rather than a real reference; meanwhile every drive, UNC, and
rooted-backslash fixture in the matrix is a link target, and the only code-span
fixture is a parent-directory escape. The story text also exempts "external
literal examples". So the narrowed scope removes a large class of false positives
on documentation while preserving detection on the categories that are real
references, and keeps CI green with no configuration, baseline, or document
changes.

The mechanics stay within the existing controls: the code-span branch keeps the
shape gate, suppresses the drive, UNC, backslash, and control categories, and
never performs a second decode. DS103 resumes its exact pre-Story-11 behaviour for
the exempt categories and skips only the root-escape and symlink-out code spans
through the shared `escapes_via_symlink` check, which does lexical containment
first and touches only in-root objects. DS101 is unchanged and still delegates all
unsafe link categories to DS116 through `is_ds116_owned`. The oracle-parity guard
confirms that, over this repository's docs, the new DS101 and DS103 differ from
their frozen references by nothing at all.

### Comment-masking evasion (shared scanner)

A second ruling was recorded after the oracle-parity guard caught a
false-negative in the shared scanner's HTML-comment masking. The scanner treated
an unclosed comment opener anywhere on a line - including one inside an inline
code span, or one appearing as literal mid-line text - as a comment that ran to
the end of the document, so every later link, image, and reference definition was
masked out and became invisible to DS116 (and to DS101, DS104, DS105, DS106, and
the other scanner consumers). An attacker could hide an escaping reference behind
a stray opener, and the repository's own status notes were silently blinded after
a code span that mentioned the opener token many times. This maps to CWE-693
(protection-mechanism failure) and feeds the existing CWE-22/CWE-59 traversal
concern because a hidden reference is an unchecked reference.

The fix makes the scanner mask only what CommonMark hides (requirement 16):
inline code spans on the same line are blanked with the shared backtick matcher
before any opener is sought; an opener at line start (up to three spaces of
indentation) still begins an HTML-block comment that runs to the first closer or
end of file (the historical behaviour and its tests are preserved); a mid-line
opener outside a code span is a comment only when a closer appears within the same
paragraph (before the next blank line), otherwise the literal opener masks
nothing. Closer positions, opener positions, and paragraph boundaries are each
precomputed once and resolved with bisect so a paragraph of many unclosed openers
stays near-linear rather than quadratic (the exact trap behind five earlier
regressions), and doubling-series tests pin the bound.

Audit of the other masking constructs for the same hiding class: an unclosed
fence correctly runs to end of file (CommonMark hides it too); escaped backticks
and the empty-comment edge forms do not open a hiding hole. The remaining items
are listed for the security review rather than fixed here because the scanner does
not model them and they over-scan (a possible false positive) rather than hide:
raw HTML blocks (`<div>`, `<pre>`, `<script>`, `<style>`), `<![CDATA[`, processing
instructions, four-space indented code blocks, and multi-line code spans. The
multi-line-code-span case is the only residual hiding vector and is a pre-existing,
broader limitation (the scanner recognises single-line code spans only); it is
documented for the review and is unchanged by this fix.

## Security review findings - 2026-10-22 (post-implementation)

This section records the post-implementation adversarial review of the Story 11.0
code (DS116, the DS101/DS103 existence-oracle fix, and the rewritten shared
scanner). It is appended, not a rewrite; every control above still holds.

### Method and ground-truth oracle

All attack strings below were rendered with the `markdown-it-py` CommonMark
renderer in a scratch directory (used only as a ground-truth oracle, never added
as a dependency) and compared against the set of references DS116 reports. A
construct is an evasion when the renderer produces a live escaping link, image, or
reference definition that DS116 does not report. Filesystem, injection, and DoS
behaviour was exercised with a syscall recorder and a doubling series in the same
scratch directory. Escaping example targets appear only inside fenced blocks so
this page stays clean under DocSentinel's own rules.

### Confirmed-safe controls (no finding)

The core security controls were verified as solid:

- Filesystem containment. Over a hostile corpus (in-root file and directory
  symlinks pointing outside, relative, absolute, chained, looping, broken, and
  pointing above the root, plus a real outside secret) DS101, DS103, and DS116
  made no following `stat`, `open`, `access`, `scandir`, or `listdir` on any path
  resolving outside the canonical root. The only out-of-root `lstat` calls are the
  ancestors touched by the single permitted `realpath` of the trusted root; every
  other `lstat`/`readlink` lands on an in-root symlink object. The outside secret
  was never opened or statted.
- No existence oracle and no echoed resolved path. Messages echo only the bounded,
  repr-escaped raw target; control bytes, `ESC`, RTL overrides, and non-ASCII are
  neutralised before the report sinks, the github format gains no second command,
  and a 10,000-character target is truncated to the bound.
- Algorithmic cost. Fifteen single- and multi-line flood shapes (parent-segment,
  encoded-dot, oscillation, long segment, comment, fence, backtick, bracket,
  parenthesis, percent, entity, and multi-line link floods) were linear through
  the scanner and DS116 (fitted log-log slope 0.66 to 1.03, none above the 1.3
  ceiling); peak memory stayed bounded and findings never exceeded one per line.
- Config validation and `warn` semantics. Invalid `root_escape_policy`,
  `windows_path_policy`, and `decode_percent_paths` values are rejected with a
  clear error; `off` silences, `warn` downgrades to warning severity, `error`
  blocks; `decode_percent_paths = false` suppresses the single decode yet still
  catches raw parent-segment traversal.
- No secrets. No credential, key, or token literal appears in the new source.

### [HIGH] Raw HTML link and asset attributes are never checked

The shared scanner extracts image sources only from `img` and `source` tags and
anchor identities only from `id`/`name`; it never extracts an HTML link `href` or
an asset `srcset`. A raw HTML anchor whose destination escapes the root therefore
passes DS116, DS101, and DS103 with zero findings, although the renderer emits a
live escaping link. This contradicts the DS116 docstring and the standing
"full strictness for HTML href/src/srcset" wording.

Reproducer inputs (document at root `sub/doc.md`):

```text
<a href="../../../etc/passwd">x</a>
<img srcset="../../../secret.png 1x">
```

Vector/evidence: `markdown_blocks.scan_markdown` HTML extraction captures `src`
only (no `href`/`srcset` pattern exists) and `path_boundaries.check_text` enqueues
only `index.images` and Markdown references. Impact: a contributor commits an
escaping live reference that the containment gate reports as clean (CWE-693,
CWE-22). Mitigation: extract `a@href`, `srcset` candidates, and the other asset
`src`/`data`/`poster` attributes into the reference set, or correct the docstring
and standing requirement to state that raw HTML links are out of scope.

### [HIGH] Angle-bracket link and reference destinations bypass the parent token

CommonMark allows a destination wrapped in angle brackets. The scanner keeps the
brackets in the captured target, so the leading segment becomes a literal bracketed
segment rather than the parent token, and the resolver returns RESOLVED (in-root)
instead of OUTSIDE_ROOT. DS116 reports nothing for both inline links and reference
definitions; the renderer strips the brackets and produces a live escaping link.

Reproducer inputs:

```text
[a](<../../../etc/passwd>)
[a][r]

[r]: <../../../etc/passwd>
```

Vector/evidence: `markdown_blocks._find_inline_links` and `_REF_DEF_RE` capture the
bracketed text verbatim; `resolve_local_reference` normalises the bracketed segment
as an ordinary path part. Impact: standard CommonMark link syntax defeats the
containment classification (CWE-22, CWE-41). The inline case is incidentally caught
by DS101 as a dangling link only while no in-root path matches the literal; the
reference-definition case is caught by nothing. Mitigation: strip a single pair of
wrapping angle brackets from a destination before resolution.

### [HIGH] HTML entity and numeric character references in destinations

CommonMark decodes HTML entities inside link destinations, so an encoded parent
token becomes real traversal. DS116 does not decode entities, so the target stays a
literal in-root path (RESOLVED) and no finding is produced while the renderer
resolves the link outside the root.

Reproducer inputs:

```text
[a](&#46;&#46;/&#46;&#46;/&#46;&#46;/etc/passwd)
[a](&period;&period;/&period;&period;/&period;&period;/etc/passwd)
```

Vector/evidence: `resolve_local_reference` decodes percent-encoding once but never
HTML entities. Impact: entity-encoded traversal evades containment (CWE-172,
CWE-174). Only incidentally flagged by DS101 as dangling while no literal in-root
path matches. Mitigation: decode HTML named and numeric character references once,
alongside the existing single percent decode, before the parent-token check.

### [MEDIUM] Nested image-in-link-text hides the outer destination

The single-pass link scanner closes the link text on the first closing bracket, so
for an image used as link text the inner image destination is captured and the
outer link destination is never parsed. DS116 validates the inner source and misses
the outer escaping target.

Reproducer input:

```text
[![alt](inner.png)](../../../etc/passwd)
```

Vector/evidence: `markdown_blocks._find_inline_links` matches the first bracket and
parenthesis pair. Impact: the outer destination escapes the gate (CWE-22); DS101
flags only the inner image. Mitigation: balance nested brackets in the link-text
scan so the outer destination is the one resolved.

### [MEDIUM] Reference definitions are recognised only at the block margin

`_REF_DEF_RE` matches a definition only with up to three leading spaces, so a
definition inside a block quote or other container is missed, yet CommonMark
registers reference definitions regardless of container and resolves later uses to
the escaping target.

Reproducer input:

```text
> [r]: ../../../etc/passwd

[a][r]
```

Vector/evidence: `_REF_DEF_RE` anchored to the line margin. Impact: an escaping
definition in a container evades DS116, DS101, and DS103 entirely (CWE-693).
Mitigation: recognise reference definitions after a block-quote marker, or document
containers as an accepted scanner limitation.

### [LOW] Residual symlink-swap TOCTOU in the DS101 and DS103 existence check

DS116 never opens content, so its own check is race-free. DS101 and DS103 call the
non-following `escapes_via_symlink` gate and then `Path.exists()`, which does follow
symlinks. An attacker who wins a race by swapping an in-root symlink to point
outside between the gate and the `exists()` call could make `exists()` follow it
out of root and leak a boolean existence. The window is small, requires a local
race on the CI host, and leaks only existence of one path; it is noted, not a
blocker. Optional mitigation: test existence with a non-following `os.lstat` on the
already-validated lexical path instead of `Path.exists()`.

### Accepted limitations (not findings)

The following are safe or out of scope and are recorded so reviewers do not mistake
them for holes:

- Multi-line code spans. The scanner is single-line, so a link on a line inside a
  multi-line backtick span is over-reported (a false positive), not hidden; this is
  the documented residual and is safe in the hiding direction.
- The `decode_percent_paths = false` opt-out. Leaving an encoded dot unreported is
  the operator's explicit choice and is documented.
- Confusables, tilde, env syntax, and absolute POSIX paths. Unchanged from the LOW
  finding in the pre-code model; each stays an in-root literal.

### Verdict: PASS_WITH_FOLLOWUP (no CRITICAL)

No CRITICAL exists: none of the three merge-BLOCK conditions is met. DS116 performs
no filesystem access outside the canonical root, leaks no existence oracle, never
echoes a resolved absolute path or existence, is linear-time, and is
config-validated. DS116 is therefore safe to ship default-on at `error` severity as
a defense-in-depth gate.

It must not be presented as a complete containment control. The three HIGH
evasions (raw HTML `href`/`srcset`, angle-bracket destinations, and HTML-entity
destinations) let a determined author slip an escaping live reference past DS116;
the two MEDIUM gaps (nested-link outer destinations, container reference
definitions) do the same in narrower cases. These should be fixed in
`markdown_blocks.py` and `path_boundaries.py` with regression fixtures, or the
docstring and standing "full strictness for HTML href/src/srcset" wording must be
corrected to match the real coverage.

### Resolution of the close-gate findings (fixed)

All five evasions above were fixed in the shared scanner and resolver, verified
against the `markdown-it` oracle (`scripts/cases.py`), which now reports **0
evasions across its 58-case corpus**:

- **Raw HTML `href`/`srcset` (HIGH).** The scanner now extracts `href` from `<a>`
  tags and `srcset` from `<img>`/`<source>` tags (each comma-separated candidate's
  first token) and feeds them to DS116; `src` was already extracted.
- **Angle-bracket destinations (HIGH).** Inline links and reference definitions
  unwrap a CommonMark `<...>` destination in the scanner, and the shared resolver
  unwraps it too so `DS101`'s `is_ds116_owned` call is consistent.
- **HTML entity / numeric character references (HIGH).** The resolver decodes
  entities once with `html.unescape` *before* the fragment split (so the `#` in a
  numeric reference such as `&#46;` is not mistaken for a fragment), then decodes
  percent-encoding once; `&amp;` stays an in-root literal.
- **Nested image-in-link-text (MEDIUM).** `_find_inline_links` now matches
  balanced brackets with a linear stack, so the outer destination of
  `[![alt](inner)](dest)` is checked.
- **Block-quote reference definitions (MEDIUM).** `_REF_DEF_RE` accepts a leading
  block-quote prefix, so `> [r]: ...` is recognised.

Every fix keeps the linear-time bound (the DoS sweep in `scripts/dos.py` reports no
shape with slope > 1.3), and new single-line and multi-line flood tests pin each
new regex. The DS101/DS103 frozen-oracle parity over the repository's own docs is
unchanged (0 disappeared / 0 appeared).

**Remaining known false negatives** (pinned by tests, documented in the
`path_boundaries.py` docstring and `docs/dev/markdown_dialect.md`; DS116 stays a
best-effort structural guard, never a complete control): a link or reference
definition whose destination spans multiple physical lines (the scanner is
line-based) and a nested balanced-parenthesis destination such as `x(y)z.md` (the
destination ends at the first `)`).

### [LOW] Residual symlink-swap TOCTOU (acknowledged, not fixed)

The downstream existence checks in DS101 and DS103 run after DS116's lexical gate,
so a symlink swapped between the gate and the check is a theoretical
time-of-check/time-of-use race. DS116 itself never opens or reads target content,
so it has no exploitable use window of its own; there is no cheap, deterministic
fix short of a single atomic open, which DocSentinel deliberately avoids on
untrusted targets. The residual race is accepted and recorded here.
