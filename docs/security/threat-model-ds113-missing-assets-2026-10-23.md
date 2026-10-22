# Threat Model - DS113 Missing local media and document assets - 2026-10-23

This is the standing, **pre-implementation** threat model for Story 10.0 (`DS113`,
`fast` profile, default severity `error`). It is normative input for every Task
01/02/03 briefing and every reviewer of Story 10.0 and must be linked from each.
No `DS113` code exists yet; the behavior attributed below to the shared scanner,
the resolver, `DS101`, and `DS116` was confirmed against the committed code
(`src/docsentinel/markdown_blocks.py`, `detectors/path_boundaries.py`,
`detectors/links.py`, `config.py`) and a scratch reproduction, not assumed.

`DS113` resolves Markdown image, HTML `<img src>`/`<source srcset>`, and
HTML `<a href>`/reference-style image targets to local paths and reports targets
that do not exist, are not regular files, or cannot be read as assets, **inside
the scan root only**. Because it performs filesystem existence and file-type
checks on author-controlled paths, it inherits the containment, oracle, TOCTOU,
and DoS concerns already established for `DS116`, plus new ones specific to
checking existence and file type. It maps to CWE-22 (path traversal), CWE-59
(link following), CWE-203 (observable discrepancy / existence oracle), CWE-367
(TOCTOU), CWE-117 (log injection), CWE-20 (improper input validation - the
srcset/data-URI split), CWE-178 (improper case-sensitivity handling), CWE-400
(resource exhaustion / asset floods and opening special files), CWE-693
(protection-mechanism failure / scanner evasion), and OWASP A01:2021 (Broken
Access Control) and A09:2021 (Security Logging).

## Scope and method

In scope: the proposed analyzer `src/docsentinel/detectors/assets.py`; its use of
the shared resolver `resolve_local_reference` and the shared scanner
`scan_markdown` in `markdown_blocks.py` (specifically `index.images`,
`index.local_references`, `index.reference_definitions`, `index.reference_uses`,
`_srcset_urls`); the existing containment helpers `is_ds116_owned` and
`escapes_via_symlink` in `detectors/path_boundaries.py`; the `DS101` image
handling in `detectors/links.py`; the `DS113` config options in `config.py`
(`asset_extensions`, `check_html_asset_tags`, `check_markdown_images`,
`check_srcset`); and the report sinks in `reporting.py`. The method is STRIDE-lite
over the trust boundary from untrusted Markdown content to the filesystem (now
including a *file-type* probe) and to the report sinks.

The DS116 standing requirements apply unchanged as a floor: filesystem
containment, no existence oracle outside the root, bounded repr-escaped echo, no
quadratic shapes, decode-once, scanner-evasion parity with CommonMark
(requirement 16). This document adds the DS113-specific controls and does not
relax any DS116 control.

## Assets and trust boundaries

| Asset | Trust level | Why it matters |
|-------|-------------|----------------|
| Untrusted Markdown content | Hostile | Authors and PR contributors control every image target, `srcset`, HTML `src`/`href`, reference definition, and alt text. |
| Scan-root subtree | Trusted boundary | The only region DS113 may `stat`; existence disclosure here is of the repo's own files and is not sensitive. |
| Filesystem outside the root | Off-limits | Must never be `stat`-ed, opened, `realpath`-ed, or symlink-followed by DS113; this is the DS116 boundary and DS113 inherits it. |
| Special files inside the root (FIFO, device, socket, huge file) | Hostile-adjacent | A committed FIFO/device at an asset path must never be `open()`-ed; opening blocks or reads unbounded data. |
| Report sinks (text/json/github) and CI logs | Semi-public | `finding.message` is rendered verbatim into CI logs and PR annotations; the author-controlled raw target lands here. |
| Pass/fail exit code | Integrity/availability signal | `error` severity makes DS113 blocking (exit 1); a false positive is a merge-gate denial of service, a false clean hides a broken doc. |

Threat actors: a contributor submitting a crafted Markdown tree that runs through
CI or pre-commit (to probe host paths, inject log bytes, stall the run, or wedge
the gate); a reader of public CI logs harvesting an out-of-root existence oracle.
Supply chain is out of scope (stdlib-only analyzer, no network, no execution of
document content).

## Threats (STRIDE findings)

Each finding lists the vector, impact, and the required control. "Matrix" marks a
case already covered by the 15 Task 02 fixtures; "extra" marks a test the
implementer must add beyond the matrix.

### [HIGH] Existence oracle and outside-root I/O (inherited from DS101/DS103)

- Vector / evidence: the resolver is lexical and returns `RESOLVED` for any path
  that does not lexically escape, but `RESOLVED` is *not* proof of containment -
  an in-root symlink can still point outside (`path_boundaries.escapes_via_symlink`
  exists precisely for this). A naive DS113 that calls `Path.exists()` /
  `os.stat()` / `is_file()` on a target classified `OUTSIDE_ROOT`, on an unsafe
  `UNSUPPORTED` category (`drive`/`unc`/`backslash`/`control`), or on an in-root
  symlink whose target escapes, re-creates the Story 11.0 oracle: it stats a path
  outside the root and leaks its existence/type through the finding-vs-no-finding
  signal (CWE-203, CWE-22, CWE-59).
- Impact: a PR author learns whether arbitrary absolute/relative-escape paths
  exist on the CI host, and DocSentinel touches the filesystem outside the boundary
  it promises to respect.
- Mitigation (required): before any filesystem call, DS113 must route the target
  through `resolve_local_reference` and act only on `RESOLVED`. It must skip
  `EXTERNAL` and the safe `UNSUPPORTED` reasons (`template`, `glob`), and it must
  **defer** every unsafe category to DS116 - call `is_ds116_owned(root, doc, target)`
  and, for the resolved in-root candidate, `escapes_via_symlink(root, candidate)` -
  and skip (no stat) when either is true. An escaped or symlink-out missing asset
  is DS116's finding, never DS113's; DS113 must not dereference it.
- Test case (extra, syscall recorder + runtime symlink): a document whose image
  target clamps to a real outside file via `../` flood, and one via an in-root
  symlink to outside, must yield zero DS113 findings and **zero** `os.stat`,
  `os.open`, `os.scandir`, `os.access`, `Path.exists`, or `Path.is_file` calls on
  any path resolving outside the canonical root (assert via a patched counter).
  Matrix: `asset_symlink_outside` (runtime-symlink-companion) is a DS116 finding,
  not a DS113 one.

### [HIGH] Special files (FIFO/device/socket) and huge files - never open content

- Vector / evidence: Task 01 requires a "regular-file status" check. If DS113
  implements it by opening the file (e.g. `open(path).read()` to sniff bytes, or a
  PIL/`imghdr`-style content probe), a committed FIFO at an asset path blocks the
  entire scan forever, a device node reads unbounded or privileged data, and a
  multi-gigabyte committed file exhausts memory (CWE-400, CWE-20). Opening is also
  pointless: existence and type are decidable without reading a byte.
- Impact: one crafted in-root path wedges every pre-commit and CI run (availability
  DoS) or forces an unbounded read.
- Mitigation (required): the regular-file check must use `os.lstat`/`os.stat` and
  `stat.S_ISREG` only - **never** `open`, `read`, `imghdr`, or any content sniff.
  `Path.exists()` and `Path.is_file()` are acceptable (they `stat`, they do not
  open), but a raw `os.stat` on the lexically-validated path is preferred so no
  higher-level call is tempted into opening. DS113 must never read asset content;
  it validates existence and `S_ISREG`, nothing more.
- Test case (extra): a runtime-created FIFO (`os.mkfifo`) at an in-root asset path
  must complete the scan promptly and must not block; assert no `open()` on the
  asset path via a syscall recorder; skip only with an explicit
  FIFO-unavailable reason.

### [HIGH] srcset / data-URI splitting corrupts a data URI into a spurious path probe

- Vector / evidence: `markdown_blocks._srcset_urls` splits a `srcset` value on
  `,` and takes the first whitespace token of each candidate. A `data:` URI
  contains a comma (`data:image/png;base64,<payload>`), so the split yields two
  candidates. Confirmed in a scratch run:

  ```text
  srcset="data:image/png;base64,iVBORw0KGgoAAAANSUhEUg== 1x, real.png 2x"
    -> ['data:image/png;base64', 'iVBORw0KGgoAAAANSUhEUg==', 'real.png']
  ```

  The first fragment classifies `EXTERNAL` (harmless), but the base64 fragment
  `iVBORw0KGgoAAAANSUhEUg==` has no scheme and no slash, so the resolver returns
  `RESOLVED` as an in-root relative path. DS113 would then `stat` that base64
  garbage and, finding it absent, emit a **false-positive** `error` that blocks
  the merge - and it has probed a filesystem path derived from attacker-chosen
  base64 (CWE-20, CWE-203). This is the exact "commas inside data URIs" hazard
  Task 01 calls out.
- Impact: any legitimate inline-data `srcset` (a common responsive-image pattern)
  wedges the gate with a nonsense missing-asset finding; a crafted payload steers
  the stat to an arbitrary in-root relative path.
- Mitigation (required): split `srcset` correctly - a candidate boundary is a
  comma that is **not** inside a `data:`/other URI. The implementer must either
  (a) skip any candidate whose decoded form classifies `EXTERNAL`, and recognise
  that a `data:` candidate must consume up to the next *descriptor-delimiting*
  comma (a comma followed by optional whitespace and a new URL token), or (b)
  detect a `data:` prefix on the whole attribute and treat the attribute as a
  single external candidate. Whichever is chosen, a `data:` URI in `srcset` must
  never produce a `RESOLVED` filesystem probe. Because `_srcset_urls` is shared
  with DS116, any fix there must be covered by a DS116 regression too (DS116 is
  saved only by the base64 fragment lacking an escape; do not rely on that).
- Test case (extra + matrix): `missing_srcset_candidate` asserts exactly one
  finding for the genuinely-absent high-DPI candidate and not a second for any
  data-URI fragment; add a `data_uri_srcset_candidate` CLEAN case with a real
  existing fallback and an inline `data:` candidate asserting **zero** findings.

### [MEDIUM] Information disclosure / log injection through the echoed target

- Vector / evidence: `reporting.py` renders `finding.message` verbatim; its
  `_escape_data` neutralises `%`, CR, LF for the github format but not NUL, ESC,
  or other C0/C1 bytes. DS113 will echo an author-controlled raw target (CWE-117),
  and if it echoes the *resolved* path it leaks host layout and re-creates the
  oracle through the message body (CWE-203).
- Impact: control/ESC bytes corrupt or spoof CI log lines; a resolved absolute
  path discloses the CI host filesystem layout.
- Mitigation (required): reuse the DS116 echo discipline (`path_boundaries._echo`:
  bound to a small maximum - e.g. 80 chars - then `unicode_escape` so control,
  ESC, RTL-override, and non-ASCII bytes become printable `\xNN`/`\uNNNN` before
  the sinks). Echo only the author's raw target (or the repo-relative document
  path), **never** the resolved absolute path, and never the file's existence of a
  neighbouring path or its type beyond "missing". Do not weaken the github
  newline/percent escaping.
- Test case (extra): a 10,000-char target yields a message under the bound; a
  target with embedded NUL/ESC/newline renders with no raw control byte and no
  second github command line; assert the resolved absolute root string never
  appears in any message.

### [MEDIUM] Algorithmic DoS - asset/srcset floods and per-reference I/O

- Vector / evidence: DS113 adds a `stat` per resolved asset reference. A document
  can carry thousands of images or a single `srcset` with thousands of candidates
  (each becomes an `Image` in `index.images`), and a per-reference `stat` is a
  syscall each (CWE-400). The scanner's link/bracket handling is already linear,
  but DS113's I/O must not multiply it.
- Impact: a crafted document issues one syscall per candidate, stalling pre-commit
  and CI; on a network filesystem this is severe.
- Mitigation (required): resolution and classification stay O(total bytes) and
  reuse the shared scanner (no new regex with catastrophic backtracking). Perform
  at most **one** `stat` per distinct resolved in-root path by memoising existence
  per `(resolved_path)` within a single document scan; collapse duplicate
  `(line, message)` findings as DS116 does. Lexical containment and the
  `is_ds116_owned`/`escapes_via_symlink` gate run *before* any `stat`, so escaped
  floods cost no I/O. Prove the bound with `tests/timing_helpers.assert_scales_linearly`
  over a doubling series for single-line srcset-candidate floods, many-image
  documents, and multi-line image floods, measured in CPU time, with a fixed
  expected finding count per size so the bound cannot pass vacuously.
- Test case (extra): doubling-series timing tests as above.

### [MEDIUM] Case-insensitive filesystem mismatch -> nondeterministic blocking gate

- Vector / evidence: `stat` on macOS (default APFS) and Windows is
  case-insensitive, so `![](Logo.PNG)` resolving to a committed `logo.png`
  succeeds there but fails on a case-sensitive Linux CI runner (CWE-178). At
  `error` severity this means the merge gate passes locally and blocks in CI (or
  vice-versa) for the same tree - a nondeterministic, platform-dependent verdict.
- Impact: inconsistent blocking findings across developer and CI platforms;
  erodes trust in the gate and can hide a real break on the serving platform.
- Mitigation (required, documented): DS113 must document that existence is decided
  by the host filesystem's case policy and is therefore platform-dependent for
  case-mismatched references; the supported-dialect note and the rule docstring
  must state this limitation honestly rather than claim portable detection. Adding
  a `scandir`-based exact-dirent case check is **not** required by default (it adds
  per-directory I/O and its own DoS surface); if offered it must be opt-in and
  itself bounded. Keep `asset_extensions` matching case-insensitive for the
  extension gate so the *scope* decision does not add a second case trap.
- Test case (extra): documented reason recorded in the test module if the
  case-mismatch behaviour is not asserted portably.

### [MEDIUM] Scanner-evasion parity (requirement 16) and the shared masking surface

- Vector / evidence: DS113 reads `index.images`, `index.local_references`, and
  `index.reference_definitions`, which already mask fenced code, inline code, and
  HTML comments (the `bad_asset_under_code` fixture relies on this). But the shared
  scanner has documented false negatives (multi-line destinations, nested-paren
  destinations `x(y)z.md`, multi-line `<a>` tags, unquoted HTML attributes) and the
  multi-line inline-code-span over-mask. A reference the renderer makes live but
  the scanner hides is a hidden broken asset (a false clean, CWE-693); DS113 must
  not *add* a new hiding hole.
- Impact: at most a false clean (a broken asset silently passes) or a false
  positive (an over-masked live reference). DS113 inherits these; it must not widen
  them with its own ad-hoc regex over raw text.
- Mitigation (required): DS113 extracts asset references **only** through the shared
  scanner tokens; it must not run its own image/HTML regex over unmasked source.
  Any construct DS113 masks must be masked only where CommonMark hides it. Inherit
  and document the scanner's known gaps in `docs/dev/markdown_dialect.md`; do not
  claim complete coverage.
- Test case (extra): a differential against a CommonMark oracle (the
  `markdown-it-py` scratch oracle used for DS116, never a runtime dependency) over
  image/srcset/href cases, asserting DS113 reports no asset the renderer would not
  make live and (best-effort) does not miss one it would, within the documented
  gaps.

### [LOW] Residual TOCTOU on the existence/type check

- Vector / evidence: like DS101/DS103, DS113 runs the non-following
  `escapes_via_symlink` lexical gate and then a `stat`/`is_file` that *does* follow
  symlinks. An attacker who wins a local race by swapping an in-root symlink to
  point outside between the gate and the `stat` could make the `stat` follow it out
  of root and leak a boolean existence (CWE-367).
- Impact: small window, requires a local race on the CI host, leaks only the
  existence/type of one path; not a blocker.
- Mitigation (optional, documented): decide existence/type with a non-following
  `os.lstat` on the already lexically-validated in-root path, resolving at most one
  in-root symlink hop through the same bounded walk `escapes_via_symlink` uses,
  rather than a following `Path.is_file()`. If not done, record the residual race
  in the docstring exactly as DS116/DS101 do. DS113 must never open content, so it
  has no exploitable *use* window of its own.

### [LOW] Confusables, tilde, env syntax, absolute POSIX paths (inherited literals)

- Vector / evidence: the resolver treats fullwidth dots, tilde, `$VAR`, and
  `/etc/passwd` as in-root literals or root-relative (DS116 evidence table). None
  escapes; each stays an in-root literal that DS113 will simply find missing (or
  present) inside the root.
- Impact: none exploitable. A `~/x.png` becomes an in-root `~` directory literal;
  a missing one is an ordinary (correct) DS113 finding.
- Mitigation: keep the resolver's behaviour; do not expand tilde or env vars, do
  not add Unicode normalization that would turn a confusable into a parent token.

## Required rulings (spec ambiguities to resolve before fixtures freeze)

These change the DS113 behaviour contract and must be ruled before Task 02 freezes
the 15 fixtures and their expected outcomes.

- **R1 - Reference-style image ownership.** The scanner's `reference_uses` carry a
  label only (no image flag, no target); `reference_definitions` carry the target
  but not whether a use is an image or an ordinary link. The CLEAN fixture
  `asset_reference_definition` requires DS113 not to false-positive on a
  reference-style image resolving to an existing asset. **Ruling needed:** DS113
  checks a reference *definition's* target for existence only when the decoded
  target's extension is in `asset_extensions` (so it does not step on DS101's
  link-definition territory and does not need the impossible use-is-image join),
  **and** only when that definition is actually used (join `reference_uses` label
  to `reference_definitions` label) to avoid flagging an unused definition (DS108's
  concern). Confirm this is the ownership line, or state that reference-style images
  are out of DS113 scope and document it.

- **R2 - DS116-owned and escaped references are never stat-ed.** Confirm that for
  any target where `is_ds116_owned` is true (`OUTSIDE_ROOT`, `drive`, `unc`,
  `backslash`, `control`) or where `escapes_via_symlink` is true on the resolved
  candidate, DS113 emits **nothing** and performs **no** filesystem call - the
  escape is solely DS116's finding. (This is the non-negotiable containment ruling;
  R1's extension gate must not bypass it.)

- **R3 - Meaning of "regular file" for in-root symlinks.** Ruling needed: an
  in-root symlink whose target is also in-root and is a regular file is a **valid**
  asset (no finding); DS113 therefore follows at most in-root symlink hops (via the
  bounded, containment-checked walk) and tests `S_ISREG` on the final in-root
  target. A symlink whose target escapes the root is DS116's (R2), not a DS113
  "missing" finding. A path that exists but is not a regular file after in-root
  resolution (directory, FIFO, device, socket) is reported as a non-asset finding
  **without opening it** - confirm this is a finding rather than a silent pass, so
  a FIFO cannot masquerade as a present asset.

- **R4 - Escaped image markup.** The scanner does not model backslash escapes
  outside table cells, so `\![alt](x.png)` (a literal `!` plus an ordinary link in
  CommonMark) is still seen as an image by `_find_inline_links`. Ruling needed:
  accept this as an over-detection (a possible false positive, never a hidden
  escape) and document it, rather than add escape handling that could diverge from
  the shared scanner. The same ruling covers escaped reference brackets, consistent
  with DS108's escape handling.

- **R5 - `asset_extensions` scope and the data path.** Ruling needed on exactly
  which references the extension gate filters. Proposed: Markdown `![]()` and HTML
  `<img>`/`<source>` images are checked **regardless** of extension (an image is an
  asset by syntax); `asset_extensions` gates only *link-shaped* asset references
  (HTML `<a href>` and reference definitions per R1) so DS113 does not probe every
  ordinary `.md` link (DS101's job) or every prose link. Keep the default list
  narrow and matching case-insensitively. A broad `asset_extensions` must not turn
  DS113 into a second existence-prober over all links (amplifies the stat surface
  and false positives).

## Verdict on error-severity default-on

From a pure confidentiality/integrity standpoint, `error` default-on is
**acceptable**: DS113 creates no vulnerability if the containment, no-open,
no-outside-root-stat, bounded-echo, and srcset/data-URI controls land - it only
reads existence/type of the repo's own in-root files, which is not sensitive.

The real risk of `error` default-on is **availability of the merge gate**: a
false positive is a blocking merge denial. DS113, unlike DS116, fires on ordinary
authoring patterns and has several environmental false-positive sources -
the data-URI `srcset` split (HIGH, must be fixed), case-insensitive-FS divergence
(MEDIUM), build-time/LFS/submodule-generated assets, and symlinked asset trees.
DS116 shipped default-on at `error` safely because it also carries a
`root_escape_policy` (off/warn/error) downgrade knob; **DS113 currently has no
equivalent severity knob** - only `check_html_asset_tags`/`check_markdown_images`/
`check_srcset` on-off toggles, plus `select`/`ignore` and baseline.

Recommended config / opt-outs (land before shipping default-on at `error`):

1. Add a `missing_asset_policy` option (`off`/`warn`/`error`, default `error`)
   mirroring `root_escape_policy`, so an operator can downgrade DS113 to advisory
   without losing it - the Rule metadata severity stays `error`, `check_text`
   maps the policy to the emitted severity, and `off` short-circuits with no I/O.
   If the milestone insists on no new policy knob, the three `check_*` toggles plus
   `select`/`ignore`/baseline are the documented opt-outs and the data-URI and
   case-sensitivity false-positive sources **must** be fixed/documented first.
2. Keep the default `asset_extensions` narrow (R5) and extension matching
   case-insensitive.
3. Honour `select`/`ignore`, baseline fingerprints, and all three report formats
   identically (parity with DS116/DS117).

## Verdict: PASS_WITH_FOLLOWUP

No CRITICAL exists because no DS113 code is written yet; this is the pre-code
standing model. The spec is sufficient to begin **provided** the standing
requirements below are met and rulings R1-R5 are recorded before the Task 02
fixtures freeze.

**DS113 must be documented as a best-effort structural guard, not a complete
containment or asset-integrity control** - it inherits every shared-scanner false
negative (multi-line/nested-paren destinations, multi-line HTML tags, unquoted
attributes) and the platform-dependent case-sensitivity behaviour.

Merge-gate BLOCK conditions for the human reviewer and the merge-blocking hook -
any one of these ships ⇒ BLOCK, keep out of `master`:

- DS113 `stat`s, opens, `realpath`s, `resolve`s, or symlink-follows any path that
  resolves **outside** the canonical root, or re-introduces the DS101/DS103
  outside-root existence oracle.
- DS113 **opens or reads** asset content (any FIFO/device/huge-file open), rather
  than using `lstat`/`stat` + `S_ISREG` only.
- DS113 echoes a resolved absolute path, a neighbouring path's existence, or a file
  type beyond "missing" into any report sink, or leaves control/ESC bytes
  un-escaped in the message.
- DS113 ships the `srcset`/data-URI split bug (a `data:` URI candidate produces a
  `RESOLVED` filesystem probe or a spurious missing-asset finding).

## Standing requirements checklist (apply to every Story 10.0 task and review)

1. No filesystem access outside the canonical root: route every target through
   `resolve_local_reference`; act only on `RESOLVED`; defer `OUTSIDE_ROOT` and
   unsafe `UNSUPPORTED` (`drive`/`unc`/`backslash`/`control`) to DS116 via
   `is_ds116_owned`; skip any resolved candidate for which `escapes_via_symlink`
   is true - all before any `stat` (R2).
2. Never open or read asset content; the regular-file check is `os.lstat`/`os.stat`
   + `stat.S_ISREG` only; a FIFO/device at an asset path never blocks or reads
   (HIGH special-files finding).
3. Reuse the shared scanner and resolver; stdlib-only import graph; no second path
   resolver, no third-party Markdown or image parser, no network, no execution of
   document content, no regex over unmasked source.
4. Fix the `srcset`/data-URI split so a `data:` URI never becomes a `RESOLVED`
   probe; cover the shared `_srcset_urls` change with a DS116 regression too.
5. Bound and repr-escape the echoed raw target (reuse the DS116 `_echo`
   discipline); never echo a resolved absolute path, neighbouring existence, or
   type beyond "missing"; preserve the github newline/percent escaping.
6. Linear, O(total bytes) handling with at most one `stat` per distinct resolved
   path and collapsed duplicate findings; `assert_scales_linearly` doubling-series
   tests for srcset-candidate floods, many-image documents, and multi-line image
   floods, in CPU time, with fixed expected counts.
7. Scanner-evasion parity (requirement 16): mask only what CommonMark hides;
   inherit and document the scanner's known false negatives in
   `docs/dev/markdown_dialect.md`; add a markdown-it differential test over
   image/srcset/href cases.
8. Record the case-insensitive-FS limitation honestly; extension matching is
   case-insensitive; no default per-directory `scandir` case check.
9. Record rulings R1-R5 in the rule docstring and the dialect doc before fixtures
   freeze; ownership overlap with DS101 (dangling image link) and DS116 (escape) is
   documented, with DS113-specific assertions in the finding fixtures.
10. Default severity `error`; register DS113 exactly once in `RULES` and
    `ANALYZERS`, selectable via `select`/`ignore`, honouring baseline; CLI `rules`,
    `doctor`, baseline, and all three report formats agree. Prefer adding a
    `missing_asset_policy` (off/warn/error) opt-out knob (verdict section).
11. All 15 Task 02 fixtures (8 CLEAN, 7 FINDING, 0 ERROR) loaded individually via
    `asset_case` into fresh `tmp_path`; expected outcomes from a checked manifest,
    not from whatever the analyzer emits; symlink/FIFO fixtures generated at runtime
    and skipped only with an explicit unavailable reason; keep intentionally broken
    fixtures byte-for-byte and excluded from self-scan and formatters.
12. Pass the fast-only import isolation test (no spacy/textacy/sklearn/docsig/network
    on the fast path); syscall-recorder test proving zero outside-root filesystem
    calls and zero `open()` on asset paths.

Fix handoff: implementation of the detector and the `_srcset_urls`/`srcset` split
fix go to `python-expert`; the syscall-recorder, FIFO, runtime-symlink,
markdown-it differential, and flood-slope regression tests go to `testing-expert`.

## Security review findings - Story 10.0 DS113 - 2026-10-23

Post-implementation adversarial review of the shipped, uncommitted DS113
(`src/docsentinel/detectors/assets.py`; the shared `markdown_blocks._srcset_urls`
rewrite, `Image.attribute`/`LocalReference.html` additions; `config.py`
`missing_asset_policy`). Attacked against the four merge-gate BLOCK conditions and
the twelve standing requirements above. Method: an `os.*`/`builtins.open` syscall
recorder plus a `sys.addaudithook` probe over a hostile corpus (runtime symlinks,
symlink chains/cycles, a runtime `os.mkfifo`, `../` floods, absolute paths, control
bytes, data-URI `srcset`), a CPU-time doubling series, and a `markdown-it-py` 4.2.0
CommonMark differential over image/`srcset`/`href`/reference constructs. Evidence
scripts live only in the session scratchpad; no product code or other docs were
modified.

### Verdict on the BLOCK conditions: all four PASS (no CRITICAL)

Confirmed empirically, with the recorder asserting zero outside-root
`stat`/`lstat`/`open`/`scandir`/`access`/`readlink` and zero non-document `open()`:

- **Outside-root I/O / existence oracle - PASS.** `../`-flood-to-`/etc/hosts`,
  absolute `/etc/passwd`, an in-root symlink to `/etc/hosts`, and a two-hop in-root
  symlink chain ending outside all produced **zero** findings and **zero**
  filesystem calls resolving outside the canonical root. `is_ds116_owned` (lexical,
  runs before any `stat`) and `escapes_via_symlink` (non-following, in-root `lstat`
  walk) correctly defer every escape to DS116
  (`detectors/assets.py:350`,`:361`). `/etc/passwd` is reinterpreted root-relative
  per ruling G3 and reported as an in-root miss - no outside probe.
- **Never open/read content (special files) - PASS.** A runtime `os.mkfifo` at an
  asset path yielded `asset is not a regular file` within a 10 s alarm guard and
  **no** `open()` on the FIFO; a directory symlink and a symlink 2-cycle likewise
  produced findings without opening or hanging. `_classify_path` uses `os.stat` +
  `stat.S_ISREG` only and swallows every `OSError` (incl. `ELOOP` from a cycle that
  overran the 64-hop lexical gate) as `missing` (`detectors/assets.py:252-260`).
- **Echo / log injection / path disclosure - PASS.** `_echo` bounds to 80 chars then
  `unicode_escape`; a 10,000-char target rendered at 98 chars, and targets carrying
  NUL/ESC/CR/LF never reach a message (they are DS116-owned control targets, skipped,
  or split across physical lines by the line-based scanner). Only the author's raw
  first-token target is echoed - never the resolved absolute path, neighbour
  existence, or a file-type beyond "missing"/"not a regular file"
  (`detectors/assets.py:132-146`,`:368`). The github sink's `_escape_data`
  (%/CR/LF) is untouched.
- **`srcset` / data-URI split - PASS (fixed).** `_srcset_urls`
  (`markdown_blocks.py:578-633`) now collects each candidate URL as a maximal
  non-whitespace run, so `data:image/png;base64,iVBOR== 1x, real.png 2x` keeps the
  whole `data:` URI as one `EXTERNAL` candidate and probes only `real.png`
  (confirmed clean). The former comma-split that manufactured a base64 in-root probe
  is gone.

`missing_asset_policy = "off"` performs **zero** DS113 I/O (short-circuits before the
`os.path.realpath(root)` canonicalisation, `detectors/assets.py:407-408`); `warn`
downgrades to `warning`; `error` (default) blocks. The knob the pre-code verdict
recommended shipped. DoS: the srcset-candidate flood scaled linearly in CPU time
(0.29/0.61/1.26/2.57 s at n=2k/4k/8k/16k with a fixed one-finding-per-candidate
count); a `"[" * N` one-line flood stayed sub-50 ms at N=20k. One `stat` per distinct
resolved path is memoised (`detectors/assets.py:249-251`).

### [MEDIUM] False-positive merge block on CommonMark indented code blocks

- Vector / evidence: the shared scanner models only *fenced* code, not four-space
  **indented** code blocks (documented as a scanner gap, `docs/dev/markdown_dialect.md:61`).
  A renderer treats `    ![a](indent4.png)` as literal code and makes no image live;
  DS113 extracts it from the raw line and reports `missing asset: indent4.png`.
  Differential confirmed: markdown-it renders no `<img>`, DS113 emits one `error`.
- Impact: a documentation author who shows an image/link example in an indented code
  block gets a blocking (exit 1) false positive. Unlike DS116 (fires only on
  escapes), DS113 fires on *ordinary* missing assets, so this inherited gap now has a
  realistic false-positive, availability-of-the-merge-gate direction (CWE-693 in the
  false-positive sense). The dialect doc frames inherited gaps only as *false
  negatives*; the false-*positive* direction of the indented-code and
  inline-code-vs-indent gaps is not called out for an `error` default-on rule.
- Mitigation (follow-up, not blocking): either mask indented code blocks in the
  shared scanner (benefits DS116/DS103 too) or explicitly document the indented-code
  false-positive direction for DS113 and lean on `missing_asset_policy`/baseline. Add
  a differential fixture pinning the behaviour. Hand the scanner change to
  `python-expert` and the fixture to `testing-expert`.

### [LOW] Truncated-destination false positives (nested parens, angle-bracket spaces)

- Vector / evidence: a destination ends at the first `)` and the first whitespace
  token, so `![a](x(y)z.png)` is probed as `x(y` and `![a](<ang le.png>)` as `ang`
  (differential: renderer makes `x(y)z.png` / `ang%20le.png` live). DS113 reports a
  finding for the truncated, nonexistent fragment - a false positive if the real
  untruncated file exists, plus a confusing truncated echo. The nested-paren
  truncation is documented (`docs/dev/markdown_dialect.md:66`); the
  angle-bracket-with-internal-space `_first_token` truncation is not.
- Impact: occasional blocking false positive and a misleading message; no containment
  or disclosure impact (the truncated fragment stays in-root).
- Mitigation (optional): document the angle-bracket-space case alongside the
  nested-paren gap; no code change required for containment.

### [LOW] Shortcut/collapsed reference images are not checked (evasion / false clean)

- Vector / evidence: the used-definition join (R1) keys on
  `index.reference_uses`, which the shared scanner only populates for the
  two-bracket `[text][label]` / `[label][]` forms; a **shortcut** `![ref]` or `[ref]`
  produces no `ReferenceUse` (documented scanner gap,
  `docs/dev/markdown_dialect.md:60`). Differential: `![ref]\n\n[ref]: refimg2.png`
  renders a live `<img src="refimg2.png">` but DS113 emits nothing even though the
  asset is missing.
- Impact: a broken shortcut-reference image/link silently passes (false clean,
  CWE-693) - the lower-risk direction (hides a broken doc; never blocks a good one).
  It makes R1's "checked only when the label is actually used" incomplete relative to
  what a renderer makes live.
- Mitigation (optional): recognise shortcut uses over masked text as DS108 already
  does, or document that shortcut-reference assets are out of DS113 scope. Not a
  containment or disclosure issue.

### [LOW] Environmental false positives: unreadable dirs and case-insensitive FS

- Vector / evidence: `_classify_path` maps every `os.stat` `OSError` to `missing`
  (`detectors/assets.py:254-257`), so an existing in-root asset inside a directory
  lacking traverse permission (`EACCES`) reports as missing. Separately, case
  divergence (`Logo.PNG` vs committed `logo.png`) is platform-dependent (CWE-178),
  already documented (`docs/dev/markdown_dialect.md:209-212`).
- Impact: environment-dependent blocking false positives at `error` severity; no
  confidentiality/integrity impact.
- Mitigation: accept and rely on `missing_asset_policy`/baseline; the case behaviour
  is honestly documented. No change required.

### [LOW] Data-URI with an unencoded internal space

- Vector / evidence: `_srcset_urls` splits `data:text/plain, hello world.png` into
  `data:text/plain` (EXTERNAL) and `hello` (probed in-root, reported missing). This
  actually matches the WHATWG srcset candidate-splitting a browser performs (`hello`
  is a genuine candidate URL there), so it is a correct parse rather than the
  data-URI corruption the HIGH finding described; noted only for completeness.
- Impact: none beyond an in-root miss that a renderer would also treat as a broken
  candidate.
- Mitigation: none required.

### Regression check for the shared `_srcset_urls` change (DS116 consumers)

The `srcset` rewrite is shared with DS116. The differential and the DS116 code-span
ruling confirm the new whitespace-run collection does not newly classify any
`data:`/`EXTERNAL` candidate as an in-root path for DS116, and still surfaces an
escaping `srcset` candidate. No regression observed; a DS116 `srcset` regression
fixture (per standing requirement 4) should remain in the suite.

### Overall verdict: PASS_WITH_FOLLOWUP

No CRITICAL and no BLOCK condition is met: containment, the no-open/no-outside-stat
guarantee, the bounded repr-escaped echo, and the `srcset`/data-URI fix are all
verified. **`error` default-on is acceptable** - DS113 only reads existence/type of
the repo's own in-root files and ships the recommended `missing_asset_policy`
(off/warn/error) downgrade knob with a verified zero-I/O `off` path. The residual
risk is purely merge-gate *availability* from false positives; the data-URI and
case sources are fixed/documented, and the one newly-identified false-positive source
worth tracking is the **indented-code-block** gap (MEDIUM, above). Recommended
follow-ups (non-blocking): mask indented code blocks (or document the false-positive
direction), and close or scope-document the shortcut-reference false clean. Fixes to
`python-expert`; differential/flood/FIFO/symlink regression fixtures to
`testing-expert`.
