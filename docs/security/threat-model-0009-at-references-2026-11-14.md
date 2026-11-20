# Threat Model - Milestone 0009 Story 01.0 At-References (DS124) - 2026-11-14

Pre-implementation threat model for
[Story 01.0](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/README.md)
([Task 02](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/02-threat-model-at-references.md)):
recognition of `@`-document mentions in the shared scanner (`AtReference`, plan contract C3),
their two-step resolution by the new fast rule DS124, their DS116 escape coverage, and the DS103
`@` skip. No code for this story exists yet. This model is a standing input for Tasks 03, 04, 05
and 06, and each of their briefings must link it. The design under review is the story README
and [ADR 0004](/docs/adr/0004-reference-scope-and-at-document-references.md) (status
Proposed); decisions D1 to D16 are those adopted in
[status.md](/docs/roadmap/0009-improvements/status.md).

It stays consistent with, and reuses the controls of,
[threat-model-ds116-path-boundaries-2026-10-22.md](/docs/security/threat-model-ds116-path-boundaries-2026-10-22.md)
(cited as "DS116-TM"). In particular, DS116-TM ruling G4 (lexical containment first, then
`os.lstat()` and `os.readlink()` only on in-boundary objects) and its standing requirement 16
(mask only what the renderer hides) apply unchanged. Mitigation numbers M1, M2, ... are local to
this file.

Relevant weaknesses: CWE-22/23 (path traversal), CWE-59 (link following), CWE-203 (observable
discrepancy, the existence oracle), CWE-367 (TOCTOU), CWE-117 (log injection), CWE-400 and
CWE-1333 (resource and regular-expression DoS), CWE-248 (uncaught exception), CWE-693
(protection-mechanism failure); OWASP A01:2021 Broken Access Control and A03:2021 Injection.

Adversarial examples are written only inside fenced blocks or as plain prose, so this page
creates no live mention, code-span path or link for the self-scan.

## Assets & trust boundaries

Assets:

- **Filesystem outside the scan root (step 1) and outside the link root (step 2).** Must never
  be stat-ed, lstat-ed, opened or symlink-followed because of document text.
- **The invoker's home directory.** Must never be probed because of a home mention.
- **Files inside the link root.** DS124 may learn whether they exist (by design). It must never
  learn or publish their content, size, type or resolved location.
- **Report sinks and CI logs** (text, github annotations, json, the per-run log file).
  Attacker-influenced strings land here.
- **The gate signal.** The exit codes 0, 1 and 2, DS116's error-severity guarantee, and the
  "never a silent clean result" principle.
- **CI availability.** One document must not stall or abort every pre-commit and CI run.

Threat actors:

- **A1, document author (untrusted).** Controls the text, names and symlinks of every document
  in the scanned tree, and the repository config (`at_reference_extensions` and
  `reference_scope` included, C8 tier "untrusted").
- **A2, invoker (trusted).** Controls argv (`--reference-scope`, `--link-root`), the
  environment and, from Story 03.0, user settings. A2 can widen the link root.
- **A3, CI runner observer.** Reads public CI logs and PR annotations, and so reads any oracle
  bit a finding encodes.

Trust boundaries:

1. Untrusted document text to the scanner's `AtReference` records (recognition cost, decoding).
2. `AtReference.target` to `resolve_local_reference()` to `contained_path()` to `os.stat()`
   (containment, oracle, TOCTOU).
3. DS124 and DS116 ownership split (one owner per mention, no silent gap).
4. the `raw` field of `AtReference` to the `value` and `message` fields of `Finding`, to templates, reports and the log
   (injection, disclosure).
5. Repository config (`at_reference_extensions`, `reference_scope`) and the link root (A1/A2)
   to DS124 behaviour.

## Evidence (confirmed in a scratch directory, not assumed)

Run against the current tree with the shared helpers that DS124 is specified to reuse:

```text
contained_path(root, root/docs/<300 x "a">.md)  -> raises OSError errno 63 (ENAMETOOLONG)
contained_path(root, root/locked/x.md), locked mode 000 -> raises PermissionError
scan() of one document holding a link to a 300-character file name
                                                -> scan aborts with OSError (DS101 today)
docs/loop -> loop (in-root symlink cycle):
    contained_path(...)      -> None (refused)
    escapes_via_symlink(...) -> False (not an escape, so DS116 reports nothing)
70 chained in-root symlinks (beyond the 64-hop bound):
    contained_path(...)      -> None ; escapes_via_symlink(...) -> False
resolve_local_reference(root, "docs/a.md", " ../x.md") -> RESOLVED root/x.md
resolve_local_reference(root, "docs/a.md", "x.md ")    -> RESOLVED root/docs/x.md
    (the resolver strips leading and trailing whitespace from the decoded target)
```

Reading the current code also shows:

- `_looks_path_like()` in `/src/docsentinel/detectors/path_boundaries.py` treats any code span
  containing a slash as path-like, so today DS116 checks a code span that is an `@` followed by an
  extensionless parent-directory chain.
- The `message` field of `Finding` is part of finding identity and of the baseline fingerprint
  (`/src/docsentinel/models.py`), but its `value` field is not.
- Claude Code (the main harness that follows these mentions) resolves relative imports against
  the importing file, imports home and absolute paths, imports extensionless paths, skips code
  spans and fences, strips block-level HTML comments, and asks for approval before an import that
  leaves the working directory
  ([Claude Code memory docs](https://code.claude.com/docs/en/memory)). That approval dialog, not
  DocSentinel, is the security control on the agent side. DS124 is a hygiene check, and DS116 is
  the repository-side traversal guard.

## Findings

Ratings describe the impact if the mitigation is missing or wrong. Every mitigation is written as
an acceptance criterion. Test names follow the repository layout: tests/unit (inline strings),
tests/mock (patched OS calls), tests/integration with rule suffixes, and assets under
tests/assets/ds124/(case) (or ds116/(case) for DS116 behaviour). Symlink, chmod and FIFO fixtures
are built in the test body under the tmp_path fixture, never committed. They may be skipped only
with an explicit "symlinks/permissions unavailable" reason.

### [HIGH] T1 Existence oracle outside the scan root (step 1) or the link root (step 2)

- Vector / evidence: the mention target is A1-controlled. The DS101 precedent (DS116-TM, first
  HIGH) showed that a following `resolve()` plus `exists()` turns finding versus no-finding into a
  host-wide existence oracle that A3 reads from CI logs (CWE-203, CWE-22). The design already
  routes both steps through `resolve_local_reference()` and `contained_path()` (README
  "Resolution (DS124)"). The remaining risk lies in implementation pitfalls:
  - stat-ing the resolver's `path` field without containment;
  - calling `contained_path()` with `path=None` on an `OUTSIDE_ROOT` result;
  - using the scan root as the step-2 boundary, or the link root as the step-1 boundary;
  - falling through to step 2 after a DS116-owned step 1.
- Impact: A1 learns whether arbitrary host paths exist, and DocSentinel breaks the boundary it
  promises.
- Mitigation:
  - **M1.** Step 1 runs in this fixed order: a `kind == "relative"` check, an extension filter,
    `resolve_local_reference(root, document, target)`, a stop on `OUTSIDE_ROOT`, then
    `contained_path(root, <resolved path>)`. Then a single `os.stat()` + `S_ISREG` on the path
    `contained_path()` returned, never on the path the resolver itself returned. A step 1 that DS116 owns (M5) ends
    processing for that mention and never reaches step 2.
  - **M2.** Step 2 resolves `"/" + target` with `link_root=` the engine-validated link root.
    `OUTSIDE_ROOT` counts as refused and is never passed on. Containment uses
    `contained_path(<boundary>, <resolved path>)`, where the boundary is the link root,
    and the only stat is on the returned path. A refusal produces no finding and one DEBUG record
    (M14).
  - **M3.** Every filesystem call DS124 makes (`os.stat()`, `os.lstat()`, `os.readlink()`,
    `Path.stat()`, `Path.exists()`, `Path.is_file()`, `os.path.realpath()`) takes a path inside the
    scan root during step 1 and inside the link root during step 2. When DS124 is called without
    `link_root=`, every call stays inside the scan root. This holds even when DS116 is ignored,
    deselected or set to `root_escape_policy = "off"`. The one exception is the single
    `os.path.realpath()` of the trusted scan root or link root itself (and so of its ancestors),
    which `canonical_root()` resolves once; no document-derived path is ever `realpath`-ed
    (amended 2026-11-16, security review L1).
- Tests (Task 06):
  - In tests/mock/test_at_reference_no_probe.py:
    - test_step1_never_probes_outside_scan_root
    - test_step2_never_probes_outside_link_root
    - test_outside_root_step1_does_not_fall_through_to_step2
    - test_escaping_mention_no_probe_when_ds116_ignored

    Each records every patched call and asserts its containment.
  - In tests/integration/test_at_references_ds124.py: test_project_root_fallback_resolves
    (asset ds124/project_root_fallback_resolves) and test_parent_chain_above_link_root_no_finding
    (asset ds124/fallback_climbs_above_link_root).

### [HIGH] T2 Symlink-out on step 2, and mentions owned by neither DS116 nor DS124

- Vector / evidence:
  - (a) Step 2: a link-root component that is a symlink leaving the link root. `contained_path()`
    refuses it before any `os.lstat()` outside the boundary. This is safe as long as nothing
    stats first.
  - (b) Ownership gap, confirmed above. README step 1 says that when `contained_path()` refuses,
    "DS124 stops: DS116 owns it". But `contained_path()` also refuses symlink cycles and chains
    beyond 64 hops, and for those `escapes_via_symlink()`, which is the DS116 predicate, returns
    False. So such a mention gets no DS116 finding and no DS124 finding: a silent clean result
    for a mention that cannot resolve (CWE-693).
- Impact:
  - (a) If the walk is done with `realpath()` or a following stat, it becomes an
    outside-link-root oracle (CWE-59).
  - (b) A1 can hide a broken mention from both rules with a committed symlink loop.
- Mitigation:
  - **M4.** Step 2 symlink containment is only `contained_path()`, which runs `os.lstat()` and
    `os.readlink()` on in-link-root objects only (DS116-TM G4). DS124 never calls `realpath()`,
    `Path.resolve()` or a following stat before `contained_path()` succeeds.
  - **M5.** One ownership predicate. Path_boundaries.py exposes a single helper, the same one that
    DS116 itself uses to classify mentions (escape, symlink). DS124 defers on step 1 only when
    that helper reports a DS116 category. Any other `contained_path()` refusal (cycle, hop
    overflow) or `OSError` (T5) means "does not resolve at this step", and DS124 goes on to step
    2 and, failing that, reports. Every recognised relative mention ends in exactly one of three
    states: it resolves, it gets a DS116 finding, or it gets a DS124 finding. The only exception
    is the step-2 refusal under M6.
  - **M6.** A step-2 refusal (symlink-out of the link root, or `..` above it) gives no finding,
    as designed. This is the single documented exception to M5, and Task 08 records it in the
    DS124 docs. Owner ruling R1 below asks whether it should be reported instead.
- Tests (Task 06):
  - In tests/integration/test_at_references_ds116_ds124.py:
    - test_symlink_out_step1_is_ds116_only
    - test_symlink_cycle_mention_is_one_ds124_finding (zero DS116, exactly one DS124)
    - test_symlink_chain_over_hop_limit_is_one_ds124_finding
  - In tests/mock/test_at_reference_no_probe.py: test_step2_symlink_out_no_outside_lstat_no_finding
    (records lstat/readlink/stat paths; no path outside the link root; no finding).
  - In tests/integration/test_at_references_ds116_ds124.py:
    test_every_relative_mention_has_exactly_one_outcome, a table-driven sweep over all of the
    above.

### [MEDIUM] T3 Home and absolute mentions probing the invoker's home directory

- Vector / evidence: Claude Code does import home and absolute paths, so A1 can write a home
  mention to a credential file or an absolute mention to a system path:

  ```text
  @~/.ssh/id_ed25519.pub     @~/.aws/credentials.json     @/etc/hosts.txt     @//server/x.md
  ```

  The design never resolves them. The pitfalls are:
  - an `os.path.expanduser()` or `Path.home()` call;
  - passing an absolute mention to the resolver, which would join it onto the link root (that
    stays contained, but breaks the "no filesystem call" guarantee);
  - treating a tilde-user token (tilde followed by a name, not a slash) as home.
- Impact: on a developer machine (pre-commit) or a self-hosted runner, finding versus no-finding
  would reveal files in the invoker's home directory (CWE-203).
- Mitigation:
  - **M7.** DS124 and DS116 branch on the `kind` field of `AtReference` before any resolver or filesystem call.
    `home` and `absolute` mentions cause zero calls to `os.stat()`, `os.lstat()`,
    `os.readlink()`, `os.path.expanduser()`, `os.path.expandvars()`, `Path.home()` or
    `Path.expanduser()`, and produce no finding. The new mentions module never references
    `expanduser`, `expandvars` or `home` (AST tripwire). A tilde-user token, or a tilde inside a
    path, is a `relative` literal that resolves under the scan root with no expansion.
- Tests (Task 06):
  - In tests/mock/test_at_reference_no_probe.py:
    test_home_and_absolute_mentions_cause_no_filesystem_call (asset
    ds124/home_and_absolute_skipped).
  - In tests/unit/test_mentions_no_home_expansion.py: test_module_never_references_expanduser
    (AST walk of the mentions module).
  - In tests/integration/test_at_references_ds124.py: test_tilde_user_is_literal_relative (asset
    ds124/tilde_user_literal; a directory literally named with a leading tilde resolves).

### [MEDIUM] T4 Recognition and resolution cost (pathological lines, long tokens, many `@`)

- Vector / evidence: the new scanner pass is on the hot path of every fast scan (ADR 0004
  "Consequences"). A1 can write:
  - a line of a million `@` characters;
  - one `@` followed by a megabyte of token characters (the 1,024 cap is a recognition rule, but
    a naive scanner that restarts at each position goes quadratic);
  - floods of escaped spaces;
  - floods of the four opening characters;
  - dense short mentions;
  - deep, many-component tokens (up to about 512 components), each costing one `os.lstat()` per
    component in `contained_path()`, times two steps, times every occurrence.
- Impact: one document stalls every pre-commit and CI run (CWE-400, CWE-1333).
- Mitigation:
  - **M8.** Recognition is one left-to-right pass per line. Each character is examined a bounded
    number of times. When a run of token characters exceeds 1,024 raw characters, the scanner
    skips the whole run and resumes after its end, not at the next character. No regular
    expression is built from input, and any regular expression used over a token has no nested
    or overlapping quantifier. The 1,024 cap counts raw characters as written, each escaped
    space counting as two (amendment A2).
  - **M9.** Resolution is memoised. Within one DS124 run, each `(document directory, target)`
    pair is resolved once, and each contained candidate path is stat-ed at most once per scan.
    The filesystem call count is bounded by distinct targets times (components + 64 hops), not
    by occurrences.
- Tests (Task 06):
  - In tests/unit/test_at_reference_grammar_timing.py, using `assert_scales_linearly` from
    `/tests/timing_helpers.py` over doubling sizes, measured in CPU time, each with a fixed
    `expected_count`:
    - test_many_at_signs_linear
    - test_dense_mentions_linear
    - test_overlong_token_linear (count 0 above 1,024)
    - test_escaped_space_flood_linear
    - test_open_punctuation_flood_linear
    - test_code_span_form_flood_linear
    - test_multi_line_mention_flood_linear
  - In tests/mock/test_at_reference_no_probe.py: test_repeated_mention_probes_once (1,000
    identical mentions make the same lstat/stat count as one).
  - In tests/integration/test_at_references_ds124.py: test_detect_scales_linearly_with_mentions.

### [MEDIUM] T5 One hostile mention aborts the whole scan (uncaught `OSError`)

- Vector / evidence: confirmed above. `contained_path()` catches only `FileNotFoundError` and
  `NotADirectoryError`, so ENAMETOOLONG (a component over 255 bytes, or a total over PATH_MAX,
  which is 1,024 on macOS and so reachable with a 1,024-character token under any root),
  EACCES, ELOOP and EIO propagate. DS101 already aborts a scan this way today. DS124 makes it
  easier, because a bare prose mention is enough. A3 sees an exit-2 failure and no report, so
  every other finding is hidden (CWE-248, CWE-400).
- Impact: availability of the gate. A CI that treats exit 2 as "tool problem, continue" turns
  this into a bypass of every blocking finding in the run.
- Mitigation:
  - **M10.** In DS124, an `OSError` from `contained_path()` or `os.stat()` means "does not
    resolve at this step" and is never propagated. ENAMETOOLONG and every other errno behave the
    same, are logged at DEBUG with a fixed reason (M14), and the scan continues. The DS116
    mention path keeps `escapes_via_symlink()`, which already catches `OSError`.
- Tests (Task 06):
  - In tests/integration/test_at_references_ds124.py:
    - test_overlong_component_reported_not_crash (asset ds124/overlong_component; exactly one
      DS124 finding, exit 1 only under `--strict`)
    - test_path_max_token_reported_not_crash
    - test_unsearchable_directory_does_not_abort (chmod built in the test body; skipped when
      running as root)
- Follow-up F1 (outside this story, python-expert): the same crash exists today in DS101
  (`contained_path()` and `Path.exists()`). Fix it in the shared helper or in DS101, with a
  regression test, in a separate change.

### [MEDIUM] T6 DS116 loses coverage of `@`-prefixed code spans that are not mentions

- Vector / evidence: README "DS116 and DS103 changes" says DS116's code-span list "drops spans
  that start with `@`". The scanner records only tokens whose last component has a letter-bearing
  extension. So a code span made of `@` plus an extensionless parent-directory chain is no
  longer a DS116 candidate (dropped by prefix) and is not a mention either (no extension). Today
  `_looks_path_like()` accepts it because it contains a slash, and DS116 reports it as an
  escape. The same goes for a span like `@` plus a chain plus a digit-only extension, or `@`
  plus a token plus another `@`.

  ```text
  `@../../../../etc/passwd`      `@../../v1.2`
  ```

- Impact: a silent regression of an error-severity guard. A1 can hide a traversal-looking
  reference from DS116 by prefixing `@` (CWE-693).
- Mitigation:
  - **M11.** DS116 drops a code span from its own candidate list only when the scanner recorded
    that exact span (by `MarkdownSpan` identity) as an `AtReference` with `in_code_span=True`.
    It never drops a span by prefix. DS103's `@`-prefix skip (S7) is acceptable as written
    (strict-only, warning severity, and escapes are DS116's in any case). Amendment A1.
- Tests (Task 06): in tests/integration/test_at_references_ds116_ds124.py,
  test_extensionless_at_code_span_escape_still_ds116 (asset
  ds124/at_code_span_extensionless_escape: exactly one DS116 escape finding, zero DS124).
- Follow-up F2 (product decision, LOW): a prose mention with no extension that escapes the root
  is checked by neither rule, although Claude Code would import it (behind its approval dialog).
  Consider having the scanner also record extensionless relative tokens that contain a
  parent-directory component, for DS116 only.

### [LOW] T7 Backslash-space decoding producing separators, controls or a different name

- Vector / evidence: the token admits a backslash-escaped space, decoded to a space. A generic
  unescape (`unicode_escape`, a backslash-any-character regex substitution, `html.unescape()`)
  would turn backslash sequences into control characters or separators. The grammar alphabet
  (ASCII letters and digits, dot, underscore, tilde, plus, hyphen, slash) contains no backslash
  other than in that pair, no percent and no hash, so the resolver's HTML and percent decodes are
  no-ops. But the resolver strips leading and trailing whitespace (evidence above), so a
  mention whose token begins or ends with an escaped space is resolved under a different name
  than the one written. A leading escaped space followed by a parent-directory chain still
  classifies as an escape, so DS116 owns it and nothing leaks.
- Impact: integrity only. A wrong resolved/missing outcome, no boundary crossing. A generic
  unescape would be MEDIUM (controls into paths and sinks).
- Mitigation:
  - **M12.** Decoding replaces exactly the two-character backslash-space sequence with one space,
    once, after recognition, as a literal string operation. A backslash followed by any other
    character ends the token and is never decoded. The decoded `target` contains only alphabet
    characters plus U+0020.
  - **M13.** A token whose first or last raw character pair is an escaped space is not recognised
    (amendment A2), so the resolver's strip can never change the name.
- Tests (Task 06): in tests/unit/test_at_reference_grammar.py:
  - test_escaped_space_decodes_to_space_only
  - test_backslash_other_character_ends_token
  - test_leading_or_trailing_escaped_space_not_recognised
  - test_decoded_target_charset (an exhaustive sweep over the alphabet plus each ASCII and C1
    code point after a backslash)

  Plus the existing asset ds124/escaped_space_path.

### [LOW] T8 Finding value, message and log injection

- Vector / evidence:
  - `raw` is the token as written. By the grammar it is ASCII and contains no control, bidi,
    zero-width, percent, hash, bracket or colon character, so `##[` and `::` cannot appear in it.
    A bidi or zero-width character ends or prevents recognition.
  - The rest is still a risk. A later grammar change could widen the alphabet. The document path
    is A1-controlled. The README bounds `value` to 200 characters but builds `message` from the
    unbounded `raw` (up to about 2,050 characters with escapes), and `message` is part of finding
    identity and the baseline fingerprint (CWE-117).
- Impact: log or terminal spoofing if the alphabet ever widens. Inconsistent or oversized
  baseline fingerprints.
- Mitigation:
  - **M14.** DS124 logs at DEBUG only, never the mention text. A record carries
    `safe(document.path)`, the line number and a fixed reason string (`step-2 boundary refusal`,
    `containment error`, ...) through `%`-style arguments, never an f-string. Document content is
    never logged.
  - **M15.** `value` and the echo inside `message` use the same bounded `raw`, cut to 200
    characters with no truncation marker inside the token (amendment A3). Both reach text and
    github sinks only through the existing `neutralize`/`gha_*` filters. JSON keeps
    `ensure_ascii`. No new sink or template is added.
- Tests (Task 06):
  - In tests/unit/test_at_reference_grammar.py: test_bidi_and_zero_width_never_enter_raw (U+202E,
    U+2066, U+200B, U+FEFF, U+2028, NUL and ESC placed before, inside and after a token).
  - In tests/integration/test_at_references_ds124.py:
    - test_value_and_message_bounded_to_200 (asset ds124/long_mention_bounded, a 1,000-character
      token)
    - test_text_and_github_reports_neutral (no control or bidi code point, no `##[`, exactly one
      annotation line per finding)
  - In tests/integration/test_at_references_logging_ds124.py:
    test_debug_log_never_contains_mention_text (caplog at DEBUG with a unique marker in the token;
    a document path holding a bidi character appears escaped).

### [LOW] T9 TOCTOU between containment and `os.stat()` (parity with DS101 and DS113)

- Vector / evidence: `contained_path()` checks the components with `os.lstat()`, then DS124 calls a
  following `os.stat()`. A process that swaps an in-boundary directory for a symlink in between
  would make the stat follow it out (CWE-367). This needs concurrent write access to the checkout
  during the scan, which already implies code execution on the runner. DS101 (`contained_path()`
  then `exists()`) and DS113 (`escapes_via_symlink()` then `os.stat()`) have the same window.
- Impact: at most one existence bit about one outside path. Nothing is ever opened, so there is
  no read or write primitive.
- Mitigation:
  - **M16.** DS124 never opens, reads, `scandir()`s or `listdir()`s a target. Its only target
    calls are `os.lstat()`/`os.readlink()` inside `contained_path()` and one stat with `S_ISREG`.
    The module docstring records the accepted TOCTOU residual and its parity with DS101 and
    DS113. Recommended hardening, not required: stat the returned path with
    `os.stat(path, follow_symlinks=False)`. Because `contained_path()` has already expanded
    every symlink, the outcome is identical, and the window narrows to intermediate components.
- Tests (Task 06): in tests/mock/test_at_reference_no_probe.py, test_target_never_opened (patch
  `open()`, `io.open()`, `os.open()`, `Path.open()`, `Path.read_text()`,
  `Path.read_bytes()`, `os.scandir()` and `os.listdir()`; zero calls with any non-document path).

### [LOW] T10 Fallback resolves to a sensitive in-repository or link-root file

- Vector / evidence:
  - Step 2 reveals whether a file exists anywhere under the link root. With `link_root = "auto"`
    that is the enclosing repository, possibly above the scan root. With A2's `--link-root` it can
    be a higher ancestor. The `.git`-at-or-above-home guard in `/src/docsentinel/link_root.py`
    stops "auto" from becoming the home directory.
  - Examples: ignored local files, or credential JSON that CI auth actions write into the
    workspace. A1 can widen `at_reference_extensions` within its bounds.
  - Only an existence bit is used, and DS101's site-root links already give A1 the same
    capability, so this adds no new capability.
- Impact: nil content disclosure. Existence disclosure is limited to the link root, which is the
  attacker's own tree in the normal case.
- Mitigation:
  - **M17.** DS124 never reveals the resolved path, the step that resolved, the file type or
    size, or why a target failed. The message is the same for a missing file, a directory, a
    FIFO or a socket. Nothing is read.
  - **M18.** Task 08 documents that DS124 uses the link root, that `link_root = "."` keeps
    untrusted nested content inside the scan root, and that the existing `--link-root` warnings
    (never in pre-commit `args:` or `pull_request_target`) cover DS124.
- Tests (Task 06): in tests/integration/test_at_references_ds124.py:
  - test_message_identical_for_missing_directory_and_fifo (FIFO built in the test body)
  - test_finding_never_contains_resolved_path
  - test_link_root_dot_keeps_fallback_inside_scan_root

### [LOW] T11 Recognition exclusions as an evasion channel (masking divergence)

- Vector / evidence: the grammar does not recognise mentions in fences, HTML comments, raw HTML
  tags, link text, destinations and labels, or after a backslash, letter, digit or `@`. If the
  scanner over-masks (for example by treating an unclosed mid-line comment opener as running to
  the end of the document, the DS116-TM "comment-masking evasion" ruling), A1 can hide later
  mentions. The divergence from Claude Code (D6 code spans, quoted paths, extensionless imports)
  is functional, not a security boundary, because the harness's own approval dialog governs
  external imports.
- Impact: missed dangling or escaping mentions after a crafted construct.
- Mitigation:
  - **M19.** Mention recognition reuses the scanner's existing CommonMark-accurate masks (fences,
    comments, code spans, link and HTML spans) and adds no mask of its own beyond the README
    exclusions (DS116-TM standing requirement 16). Whitespace before `@` means ASCII whitespace
    only (space, tab), so recognition never depends on `str.isspace()` Unicode tables.
- Tests (Task 06): in tests/unit/test_at_reference_grammar.py:
  - test_mention_after_unclosed_midline_comment_opener_recognised
  - test_mention_after_code_span_containing_comment_opener_recognised
  - test_unicode_space_before_at_not_a_boundary

  Plus the existing assets ds124/fenced_and_comment_ignored and ds124/link_label_mention_ignored.

### [LOW] T12 Config surface: `at_reference_extensions`, `reference_scope`, injected `Config`

- Vector / evidence: both keys come from untrusted repository config (C8). A hand-built `Config`
  bypasses `load_config()`.
- Impact: unbounded lists or patterns cost time. An unknown scope must not turn into a silently
  clean result.
- Mitigation:
  - **M20.** `load_config()` enforces the README bounds (1 to 64 entries, each 1 to 16 ASCII
    letters or digits, no duplicates after lowercasing, empty list rejected with the `ignore`
    hint). DS124 re-validates an injected `Config` and fails closed with `ConfigError`. The
    extension test is ASCII lowercasing plus set membership. No entry is ever compiled into a
    regular expression or a glob. An unknown injected `reference_scope` leaves DS103 inert and
    named in the notice (ADR Contract 1).
- Tests (Task 06):
  - In tests/unit/test_reference_scope_config.py: test_extensions_bounds_duplicates_and_empty.
  - In tests/unit/test_mentions_config.py:
    - test_injected_config_invalid_extensions_raise_config_error
    - test_extension_match_is_ascii_lowercase_membership
  - In tests/unit/test_rule_opt_in_values.py: test_unknown_injected_scope_keeps_ds103_inert.

### [LOW] T13 Link-root wiring

- Vector / evidence: the engine validates the link root only when a rule in `LINK_ROOT_RULES` is
  active (`/src/docsentinel/engine.py`). If DS124 is missing from that set, a run that selects
  only DS124 gets no validated link root. That is fail-safe today, because DS124 falls back to
  the lexical `link_root_for()`, but the fallback would silently differ from DS101. A direct call
  with an unvalidated ancestor would widen step 2.
- Impact: inconsistency, or an unvalidated boundary if a future caller passes a raw path.
- Mitigation:
  - **M21.** DS124 is in `LINK_ROOT_RULES`. With `select = ["DS124"]` an invalid configured
    `link_root` is a `ConfigError` (exit 2). Called without `link_root=`, DS124 uses
    `link_root_for()`, which refuses any explicit ancestor, so step 2 never leaves the scan root.
    DS124 never derives a link root itself.
- Tests (Task 06):
  - In tests/integration/test_reference_scope_cli_ds103_ds124.py:
    test_select_only_ds124_validates_link_root.
  - In tests/integration/test_at_references_ds124.py:
    test_direct_detect_without_link_root_stays_in_scan_root (a target present only above the
    scan root is reported, and no probe goes above the scan root).

### Not applicable / no finding

- **Spoofing, authentication:** none. A local read-only analyzer.
- **Repudiation:** the existing `scan started`/`scan finished` records, plus DS124's DEBUG
  records in the per-run log file, are enough. DS124 changes no state.
- **Elevation:** DS124 is read-only, runs no remediation, and fetches, imports and executes
  nothing. `DOC_SENTINEL_PROD_CONFIRMED` does not apply. No new dependency is added; fast scans
  stay stdlib-only (README acceptance criterion).
- **Pre-existing, unchanged residual (LOW):** the resolver collapses a symlink followed by a
  parent-directory segment lexically before containment, so the resolved name can differ from
  what the kernel would open. It never crosses the boundary (the collapsed path is contained),
  and DS101 and DS116 links share it. No change is required here.

## Required spec amendments (before the named task starts)

| ID | Severity | Amend | Change |
|---|---|---|---|
| A1 | MEDIUM | README "DS116 and DS103 changes", bullet 1; ADR 0004 Contract 2, consumers table, DS116 row | DS116 drops a code span only when the scanner recorded it as an `in_code_span` mention (span identity), never by `@` prefix (M11). Before Task 05. |
| A2 | LOW | README "At-reference grammar", path-token paragraph | The 1,024 cap counts raw characters. A backslash not followed by a space ends the token. A token may not start or end with an escaped space (M8, M12, M13). Before Task 04. |
| A3 | LOW | README "DS124 rule contract" (Finding comment); ADR 0004 Contract 3, Finding bullet | `message` echoes the same 200-character bounded `raw` as `value` (M15). Before Task 05. |
| A4 | MEDIUM | README "Resolution (DS124)", step 1; ADR 0004 Contract 2, consumers table, DS124 row | Replace "or `contained_path()` refuses it ... DS116 owns it" with "DS116's mention classifier reports it" (one shared predicate). Any other refusal or `OSError` is "does not resolve at this step" (M5, M10). Before Task 05. |

## Owner ruling requested

- **R1 (LOW).** A step-2 refusal (a link-root symlink-out, or a climb above the link root)
  currently yields no finding and only a DEBUG record. Reporting it as DS124 would leak nothing:
  the decision rests only on `os.lstat()`/`os.readlink()` of in-link-root objects, and the
  repository is the attacker's own tree. It would also remove the one exception to "every
  relative mention has an outcome". The recommendation is to keep the design as written (the
  target is outside the link root, so "missing" is the wrong word) and document it under M6.
  The owner may rule otherwise without a security impact.

## Mandatory mitigation ownership

| Mitigation | Implements | Tests |
|---|---|---|
| M20 | Task 03 | Task 06 |
| M8, M12, M13, M19 | Task 04 | Task 06 |
| M1-M7, M9-M11, M14-M17, M21 | Task 05 | Task 06 |
| M18 | Task 08 | review |
| A1, A3, A4 | spec owner, before Task 05 | - |
| A2 | spec owner, before Task 04 | - |
| F1 (DS101 `OSError` crash) | python-expert, separate change | testing-expert |
| F2 (extensionless escaping prose mentions) | product decision | - |

## Verdict: PASS_WITH_FOLLOWUP

There is no CRITICAL finding. The design already places `contained_path()` before every stat on
both steps, never resolves home or absolute mentions, and never opens a target. The two HIGH
findings (T1, T2) are design-mitigated, provided M1-M6 are implemented exactly. The follow-ups
are:

- amendments A1 and A4, which must land in the story README and ADR 0004 (or be quoted verbatim
  in the Task 05 briefing) before Task 05 starts;
- amendment A2, before Task 04;
- F1, as a separate change.

Merge-gate conditions for the human reviewer and the merge-blocking hook. Any of the following
in a Story 01.0 change is a **BLOCK** and must be kept out of `master`:

- DS124 stats, lstats or opens a path outside the scan root (step 1) or the link root (step 2),
  including via `realpath()`, `Path.resolve()` or `os.path.expanduser()`;
- DS124 makes any filesystem call for a `home` or `absolute` mention;
- DS124 opens or reads a target;
- one document can abort the scan through an uncaught `OSError` from DS124;
- DS116 drops a code span by `@` prefix;
- DS124 logs mention text, or echoes a resolved path.

ADR 0004 may move to Accepted on this verdict once the owner signs off and A1 to A4 are applied.
