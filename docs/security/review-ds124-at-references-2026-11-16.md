# Security review - DS124 @-document references (Milestone 0009 Story 01.0 Task 05) - 2026-11-16

Post-implementation adversarial review of the **as-built, uncommitted** DS124 change against
the pre-implementation model
[threat-model-0009-at-references-2026-11-14.md](/docs/security/threat-model-0009-at-references-2026-11-14.md)
(cited as "TM"), mitigations M1-M7, M9-M11, M14-M17, M20 (injected-`Config` half) and M21, and
every merge-gate BLOCK condition of its Verdict section.

Code reviewed (only the @-mention hunks of each diff; other hunks belong to other work):

- `src/docsentinel/detectors/mentions.py` (new, DS124)
- `src/docsentinel/detectors/path_boundaries.py` (`mention_ds116_reason()`, mentions as DS116
  candidates, code spans dropped by span identity), including the pre-existing
  `escapes_via_symlink()` that the new shared predicate now calls on DS124's path
- `src/docsentinel/detectors/paths.py` (DS103 `@` code-span skip)
- `src/docsentinel/markdown_blocks.py` (`AtReference`, `_consume_at_token`, `_at_token`,
  `_find_prose_at_references`, `_code_span_at_reference`, `_find_html_tags`, shortcut-label and
  definition-target exclusions)
- `src/docsentinel/link_root.py` (DS124 in `LINK_ROOT_RULES`)
- tests: `tests/mock/test_at_reference_no_probe.py`,
  `tests/integration/test_at_references_ds116_ds124.py`,
  `tests/integration/test_at_references_ds124.py`,
  `tests/unit/test_mentions_no_home_expansion.py`,
  `tests/integration/test_at_references_logging_ds124.py` (45 passed, run in isolation).

Every claim of the implementer was checked in the code and, where it concerns the filesystem,
with scratch probes that patch `os.lstat`/`os.stat`/`os.readlink` and record each call. The
probes live only in the session scratchpad; no product code or test was changed. Relevant
identifiers: CWE-22, CWE-59, CWE-203, CWE-367, CWE-693, CWE-117, CWE-400; OWASP A01:2021.

Adversarial examples below are inside fenced blocks only, so this page creates no live mention,
code-span path or link for the self-scan.

## Assets & trust boundaries

Unchanged from TM: the filesystem outside the scan root (step 1) and the link root (step 2),
the invoker's home directory, report sinks and CI logs, the gate signal (DS116 error severity,
"never a silent clean result"), and CI availability. A1 (document author) controls document
text, file names **and committed symlinks, including relative symlink targets**. The boundary
that matters for this review is TM boundary 2: `AtReference.target` to the ownership predicate
to `resolve_local_reference()` to `contained_path()` to `os.stat()`.

## Verification of the implementer's claims

| Claim | Result |
|---|---|
| Ownership decided first by the shared check | **True.** `mentions.py:191` calls `mention_ds116_reason()` before any other step; DS116 calls the same function for mentions (`path_boundaries.py:587`, `:604`). But the shared check is **not** itself contained (finding H1). |
| Only stat is one `os.stat(..., follow_symlinks=False)` on the `contained_path()` result | **True for DS124's own code** (`mentions.py:157`, called only with a `contained_path()` return). Not the only target-touching call: `escapes_via_symlink()` runs `os.lstat`/`os.readlink` in step 1 (via the predicate) and in the step-2 refusal branch (`mentions.py:216`). |
| No realpath/resolve/expanduser (AST tripwire) | **True** for `mentions.py` (`tests/unit/test_mentions_no_home_expansion.py`). The tripwire does not cover the helpers DS124 calls, which is where H1 lives. |
| Home/absolute mentions branch on kind before any resolver call | **True.** `mentions.py:270` precedes the extension filter and the resolver; DS116 skips them at `path_boundaries.py:585`. Probed: zero calls. |
| Every `OSError` means "does not resolve", at DEBUG | **True.** `mentions.py:158`, `:178`, `:192`, `:217`. |
| DS116 drops a code span only by `id()` of the recorded mention's span | **True** (`path_boundaries.py:589`, `:591`). Probed: the code-span mention's `span` **is** the `InlineCode.span` object. No `@`-prefix drop in DS116. |
| Scan root via abspath, not realpath | **True** (`mentions.py:356`). It diverges from DS116, which uses `realpath` (`path_boundaries.py:675`) - finding L1. |
| Memoised per `(directory, target)` | **True** (`mentions.py:139-145`); the key is two strings, built with no filesystem call. Per-contained-path stat memo at `:154-161`. |

## Findings

### [HIGH] H1 Shared ownership predicate lstats/readlinks outside the scan root through a symlink hidden in a relative symlink target

- Vector / evidence: `escapes_via_symlink()` (`src/docsentinel/detectors/path_boundaries.py:301-361`),
  reached by DS124 on **every** relative mention through `mention_ds116_reason()`
  (`path_boundaries.py:450-472`, called at `mentions.py:191`) and in the step-2 refusal branch
  (`mentions.py:216`). When a component is a symlink, the walk joins the link's relative target
  onto the link's directory, normalises it **lexically**, checks that string with `_within()`, and
  then jumps to it as a whole (`current = Path(resolved)`, `:360`) and calls `os.lstat(current)`
  (`:342`) and `os.readlink(current)` (`:353`) on it. The intermediate components of that
  target are never re-walked, so the kernel follows any symlink among them. Layout (A1 commits
  both links; `outside` is any host path, an absolute target works too):

  ```text
  root/a -> ../outside        (or -> /any/host/dir)
  root/l -> a/b               (lexically root/a/b, "in root")
  document text:  @l/x.md
  ```

  Recorded calls for this mention (scratch probe `probe2.py`): `lstat root/a/b` and
  `readlink root/a/b`, both of which the kernel resolves to `outside/b`, i.e. **outside the scan
  root**. Outcome depends on that outside object:

  ```text
  outside/b missing / dir / regular   -> DS124: 1 finding, DS116: 0
  outside/b symlink -> /etc           -> DS124: 0,         DS116: 1 "symlink escape"
  outside/b symlink -> into root      -> walk continues inside root (readlink content used)
  ```

  So finding versus no-finding (and which rule fires) is an oracle on whether an arbitrary
  host path is a symlink and whether its target leaves the root, and `readlink` content of an
  outside object steers the walk (CWE-59, CWE-203, CWE-22). `contained_path()` itself is safe
  here (it pushes link-target components back onto its deque and re-walks them one by one, and
  refuses at `root/a`); the defect is only in `escapes_via_symlink()`.
- The mock gate cannot see it: `tests/mock/test_at_reference_no_probe.py:27-36` (`_inside`)
  checks each recorded path **lexically** (`normpath` + prefix), and `root/a/b` passes.
- Pre-existing: the same walk is reachable from a plain DS116 Markdown link
  (`[x](l/x.md)`, probe `probe3.py`) and from DS113/DS101 callers of `escapes_via_symlink()`, so
  this is a DS116-TM G4 regression that predates Story 01.0. Story 01.0 newly exposes it through
  DS124, also when DS116 is ignored or `root_escape_policy = "off"` (TM M3 explicitly requires
  containment "even when DS116 is ignored").
- Impact: matches merge-gate BLOCK condition 1 ("DS124 ... lstats ... a path outside the scan
  root"). The leak is bounded (lstat/readlink metadata, symlink-ness and link target
  containment of attacker-chosen host paths, no content), so HIGH rather than CRITICAL, but the
  gate condition is explicit.
- Mitigation (python-expert):
  - Rewrite the inner walk of `escapes_via_symlink()` to use the same component deque as
    `contained_path()`: on a symlink, split `readlink()` into components, reset `parts` for an
    absolute target, `extendleft(reversed(...))` the components, and continue the per-component
    walk from the verified prefix; never `lstat` a multi-component path that has not been
    walked one component at a time. Return `True` as soon as a `..` pops above the root or an
    absolute target falls outside it; keep "cycle / hop overflow = not an escape".
  - Simpler alternative that keeps one walker: implement `escapes_via_symlink()` on top of a
    shared internal walker that also backs `contained_path()` and reports the refusal reason
    (`escape` / `cycle` / `hops`).
- Regression tests (testing-expert): in `tests/mock/test_at_reference_no_probe.py` replace the
  lexical `_inside` with a kernel-aware check (assert `os.path.realpath(os.path.dirname(p))` is
  inside the boundary for every recorded `lstat`/`readlink`/`stat` path, computed with the real
  functions outside the patch), and add `test_hidden_intermediate_symlink_no_outside_probe` with
  the layout above for DS124 (DS116 on and ignored); add the link form to the DS116 oracle mock
  (`tests/mock/test_path_boundaries_oracle.py`).

### [MEDIUM] M-A `escapes_via_symlink()` counts every component as a hop, so a symlink-out after 64 plain components is no DS116 escape (error demoted to DS124 warning)

- Vector / evidence: `path_boundaries.py:336-340` increments `hops` once per **component**
  visited, not per symlink followed, and returns `False` ("not an escape") on overflow. A
  mention of 70 plain directory components followed by a component that is a symlink to an
  outside directory:

  ```text
  depth 10:  DS116 = 1 symlink escape, DS124 = 0
  depth 70:  DS116 = 0,                DS124 = 1 (warning)
  ```

  (probe `probe5.py`). DS124 then reports it because `contained_path()` (which counts real
  hops, `:284`) refuses and the step-2 `escapes_via_symlink()` also overflows, so `_MISSING`.
  No probe leaves the root (the walk stops early), so this is integrity, not disclosure: A1 turns
  an error-severity DS116 gate into a warning that does not fail CI without `--strict`
  (CWE-693). The link form is equally affected and pre-existing. The 1,024-character token cap
  allows about 500 components, so this is reachable with a mention.
- Mitigation: count hops only when a symlink is followed (as `contained_path()` does); bound
  component work separately by the candidate's component count, which is already finite. This
  is naturally fixed by the H1 rewrite. Regression test: in
  `tests/integration/test_at_references_ds116_ds124.py`, `test_deep_prefix_symlink_out_is_ds116`
  (70 plain components plus a symlink-out: exactly one DS116, zero DS124), plus the link form in
  the DS116 suite.

### [LOW] L1 DS124 abspath root versus DS116 realpath root: a direct `detect()` call through a symlinked scan root leaves a mention with no outcome

- Vector / evidence: `mentions.py:356` uses `os.path.abspath(root)`; DS116 uses
  `os.path.realpath(root)` (`path_boundaries.py:675`). With the scan root reached through a
  symlink (`via -> real`) and an in-root absolute symlink spelt canonically
  (`real/abs.md -> <base>/real/missing.md`), `mention_ds116_reason(via, ...)` returns `"symlink"`
  (DS124 defers) while DS116, with the canonical root, returns `None` (no finding): DS124 0,
  DS116 0, a silent clean result for a dangling mention (probe `probe4.py`). With the canonical
  root, DS124 correctly reports 1.
- On (c), confidentiality: abspath does **not** weaken `contained_path()`. Every lstat is under
  the abspath root string, whose only symlink is the trusted root itself; the divergence makes
  containment *stricter* (canonical in-root targets look outside), never looser. Not reachable
  through `scan()`, which canonicalises the root (`engine.py:355`, `Path(root).resolve()`); only
  direct Python-API callers of `detect()`.
- Mitigation: canonicalise the root once in one place shared by both rules, e.g. a
  `canonical_root(root)` helper in `path_boundaries.py` (where `realpath` of the trusted root is
  already used), and call it from `mentions.detect`; keep the tripwire on `mentions.py`.
  Alternatively have `mention_ds116_reason()` canonicalise `root` itself. Regression test:
  `test_symlinked_scan_root_mention_has_one_outcome` in
  `tests/integration/test_at_references_ds116_ds124.py`.

### [LOW] L2 DS116 mention classification is not memoised (amplification)

- Vector / evidence: DS124 memoises (`mentions.py:139-145`), but DS116 calls
  `mention_ds116_reason()` once per **occurrence** (`path_boundaries.py:604` in
  `check_text`) and deduplicates only after classifying. 1,000 identical 500-component
  mentions: DS124 1,016 lstat calls, DS116 64,008 (capped at 64 per walk only because of M-A;
  after the M-A fix it becomes about 500,000). TM M9 scoped memoisation to DS124, so this is
  not a violation, but the H1/M-A fix removes the accidental cap (CWE-400).
- Mitigation: memoise `mention_ds116_reason()` per `(document directory, target)` within one
  DS116 run (a dict in `detect`, passed to `check_text`). Test: extend
  `test_repeated_mention_probes_once` to DS116.

### [INFO] Observations, no change required

- **(b) `follow_symlinks=False` on the final stat.** `contained_path()` expands every symlink,
  including the last component, so its result never ends in a symlink (a hop overflow returns
  `None`). Probed: an in-root final-component alias resolves (no false DS124); a final
  component leaving the root is one DS116 symlink finding and zero DS124. Under a TOCTOU swap of
  the final component the stat sees `S_ISLNK` and reports DS124 instead of following: fail-closed.
  M16 hardening as recommended.
- **(d) `id()` span match.** Both `id()`s are taken from objects held by the same live
  `MarkdownBlockIndex` for the whole of `check_text`; the set is local per document and never
  enters the DS124 memo (which keys on strings), so no lifetime or reuse collision is possible.
  If a future scanner change ever gave the mention a distinct span object, the code span would
  be classified a second time and deduplicated by `(line, message)`: fail-safe, never a drop.
  An `@` code span removed by the shortcut-label exclusion is not in the set and keeps its
  traversal check. Extensionless `@` code-span escapes still get one DS116 finding (M11 test
  passes; probe `probe1.py` case E).
- **(e) Outcome gaps.** Besides R1 (step-2 refusal) and F2 (extensionless prose escapes), the
  only gaps are L1 and the deliberate ones: a mention whose extension is not in
  `at_reference_extensions` gets DS116 or nothing (by contract), and an escaping mention gets no
  finding when DS116 is ignored or `root_escape_policy = "off"` (the invoker disabled the owner;
  DS124 still makes no outside probe, apart from H1). Step-2 `second.status` can only be
  `OUTSIDE_ROOT` when not `RESOLVED`, given the token alphabet.
- **(f) Injection.** `raw` is restricted by the grammar to ASCII letters, digits, `._~+-/` and
  escaped spaces (`markdown_blocks.py:98`), cut to 200 characters in both `message` and `value`
  (`mentions.py:289`); the DS116 mention message is repr-escaped and bounded to 80. DS124 logs
  only `safe(document_path)`, line numbers, counts and fixed reasons via `%`-style arguments;
  the logging test with a unique marker passes. Findings never contain the resolved path, the
  step or the file type (M17). Outside DS124's scope: the new DS103 DEBUG record at
  `src/docsentinel/detectors/paths.py:217` logs the code-span text (document content, through
  `safe()`); refer it to the logging-story review against `docs/specs/logging.md`.
- **DS103 `@` prefix skip** (`paths.py:81`) is the accepted S7 behaviour; DS116 keeps those
  spans.
- **M20 / M21.** `detect` re-validates `at_reference_extensions` of an injected `Config`
  (`mentions.py:355`); DS124 is in `LINK_ROOT_RULES` (`link_root.py:69`); without `link_root=` it
  uses the lexical `link_root_for()`.
- **Recognition cost.** `scan_markdown` is linear in CPU time with and without mentions (about
  1.1 s/MB without `@`, 1.4 s/MB with dense 1,000-character mentions); no new hot spot.

## Mitigation status

| Mitigation | Status |
|---|---|
| M1 step-1 order, stat only the contained path | Met in `mentions.py`; the shared predicate before it violates containment (H1) |
| M2 step-2 resolution and containment | Met; refusal branch calls `escapes_via_symlink()` (H1) |
| M3 every call inside the boundary, also with DS116 off | **Not met** (H1) |
| M4 no realpath/resolve/following stat before containment | Met in `mentions.py`; `escapes_via_symlink()` lets the kernel follow intermediate links (H1) |
| M5 one ownership predicate, cycles and hop overflow go to DS124 | Met; root canonicalisation diverges (L1) and hop counting is wrong (M-A) |
| M6 step-2 refusal = no finding + DEBUG | Met |
| M7 home/absolute skipped on kind, AST tripwire | Met |
| M9 memoisation | Met for DS124 (L2 for DS116) |
| M10 `OSError` never propagated | Met |
| M11 DS116 drops a code span by span identity only | Met |
| M14 DEBUG only, no mention text | Met |
| M15 bounded echo in `message` and `value` | Met |
| M16 never open/read/list a target; `follow_symlinks=False` | Met |
| M17 no resolved path, step or type disclosed | Met |
| M20 (injected `Config`) | Met |
| M21 DS124 in `LINK_ROOT_RULES`, lexical fallback | Met |

## Merge-gate BLOCK conditions (TM Verdict)

| Condition | Status |
|---|---|
| DS124 stats, lstats or opens a path outside the scan root / link root (incl. realpath, resolve, expanduser) | **TRIGGERED** (H1: `lstat`/`readlink` through a hidden intermediate symlink via `mention_ds116_reason()` and the step-2 refusal branch) |
| Any filesystem call for a `home` or `absolute` mention | Clear |
| DS124 opens or reads a target | Clear |
| One document aborts the scan through an uncaught `OSError` from DS124 | Clear |
| DS116 drops a code span by `@` prefix | Clear |
| DS124 logs mention text or echoes a resolved path | Clear |

## Initial verdict (2026-11-16, superseded by the re-review below): BLOCK

No CRITICAL finding, but merge-gate condition 1 is triggered by H1, so this change must be kept
out of `master` until `escapes_via_symlink()` walks symlink targets component by component and
the no-probe mock checks containment the way the kernel resolves paths. H1 is pre-existing in
DS116 and DS113 link handling; fixing it in the shared helper fixes every caller at once and
also resolves M-A. L1 and L2 are follow-ups that may land with the fix or separately. Fixes go
to `python-expert`; the kernel-aware no-probe assertion and the regression tests for H1, M-A, L1
and L2 go to `testing-expert`. Re-review only the helper rewrite and the new tests.

## Re-review after fixes - 2026-11-16

Scope: the implementer's fixes for H1, M-A, L1 and L2 in
`src/docsentinel/detectors/path_boundaries.py` (`_relative_components()` at line 237,
`canonical_root()` at 253, `_walk()` at 269, `contained_path()`, `escapes_via_symlink()`, the DS116
mention memo at 644-645) and `src/docsentinel/detectors/mentions.py:362`, plus the new and changed
tests. I verified every point against the code and with probes, not the summary: `probe1.py` to
`probe5.py` again, and a new `probe6.py`. `probe6.py` runs walker edge cases, plus a 12,000-candidate
differential fuzz of `contained_path()` against the HEAD implementation over random trees of
relative, absolute, `..`-bearing, cyclic and out-pointing symlinks. Its audit checks every
`lstat`/`readlink` with the kernel's view of the path: the realpath of its parent must be inside
the root. The targeted suites pass (192 tests): the five DS124 files, the DS116 oracle mock,
the DS116 and DS113 integration suites.

### Fix verification

| Item | Result |
|---|---|
| H1 | **Fixed.** `_walk()` lstats only one new component, appended to a verified prefix of plain components (`:314`). A symlink target is split and pushed back onto the deque (`:329` onward), so a joined target is never lstat-ed or readlink-ed. probe2: for `l -> a/b`, `a -> ../outside`, the only calls are `lstat`/`readlink` of `root/l` and `root/a` (plus the root canonicalisation, below), and the outcome no longer varies with `outside/b`: missing, directory, symlink-out and symlink-in all give the same result, so the oracle is closed. Fuzz: 0 outside probes from `contained_path()` or `escapes_via_symlink()`. New tests `test_hidden_intermediate_symlink_no_outside_probe` (`tests/mock/test_at_reference_no_probe.py:445`, DS116 on and off) and `test_hidden_intermediate_symlink_link_never_probes_outside` (`tests/mock/test_path_boundaries_oracle.py:252`) use the kernel-aware check. |
| M-A | **Fixed.** Only followed symlinks count as hops. probe5: a symlink-out after 70 plain components now gives DS116 errors (link and mention) and zero DS124 findings. Tests: `test_deep_prefix_symlink_out_is_ds116` (`tests/integration/test_at_references_ds116_ds124.py:278`), `test_deep_prefix_symlink_out_link_is_ds116` (`tests/integration/test_detectors_repository_root_path_boundaries_ds116.py:1415`). The 64-hop cap is above the kernel's own limits (32 on macOS, 40 on Linux), so a chain the walker refuses for hops is one the kernel would refuse with `ELOOP` as well. Reporting it as a DS124 "does not resolve" therefore hides no real escape. |
| L1 | **Fixed.** DS116 (`:717`) and DS124 (`mentions.py:362`) both call `canonical_root()`. probe4: the symlinked-root dangling mention is now one DS124 finding. `mention_ds116_reason()` still gives the raw answer for a non-canonical root when called directly (probe3), which is fine as a documented precondition ("already canonicalised"). Test: `test_symlinked_scan_root_mention_has_one_outcome` (`:308`). |
| L2 | **Fixed.** probe4: 1,000 identical 500-component mentions cost DS116 509 lstat calls (was 64,008, and about 500,000 after the M-A fix without a memo). Test: `test_repeated_mention_ds116_probes_once` (`tests/mock/test_at_reference_no_probe.py:489`). |

### The four checks requested

1. **Walker edge cases** (probe6; every case also gives the same `contained_path()` result as HEAD, and none probes outside the root):
   - an absolute in-root target is followed;
   - an absolute outside target is an escape with no outside call;
   - an absolute target spelt `root/../root/d`, or `root/d/../../out`, is refused (fail-closed);
   - a relative `..` that stays in the root resolves, and one that climbs above it is an escape;
   - one-link, two-link and self cycles are refusals with no escape;
   - a target that re-enters the root through a relative path resolves;
   - a target that leaves and re-enters (`../out/../root/d`) is an escape. This is correct, because the kernel would resolve `../out` first and that component may itself be an outside symlink.

   **Undeclared behaviour change (INFO):** HEAD's `escapes_via_symlink()` collapsed such round-trip targets lexically and answered "no escape". It now answers "escape", so a repository with a round-trip symlink gets new DS116 errors. The change is safe and matches `contained_path()`, which always refused them. Add it to the release notes next to the two declared changes.
2. **`contained_path()` unchanged for existing callers: confirmed.** With `tolerate_errors=False` the walker is the HEAD body line for line, with the same exception set: `FileNotFoundError` and `NotADirectoryError` are tolerated, any other `OSError` and `readlink` errors propagate. The fuzz found 0 mismatches against the HEAD function in 12,000 candidates. `escapes_via_symlink()` uses `tolerate_errors=True`: an `EACCES` or `ENAMETOOLONG` component counts as plain, and every later lstat beneath it fails the same way, so nothing is followed. Its `readlink` is unwrapped as before. It can fail only in a race after `lstat` reported a symlink, and DS124 catches it.
3. **Root canonicalisation is invoker-controlled: accepted.** `canonical_root()` realpaths the root the caller passed: the CLI argument or API argument, which `scan()` has already resolved (`engine.py:355`). The calls touch only that root and its ancestors. They happen once per run whatever the documents contain, so they carry no bit an author chooses. `test_home_and_absolute_mentions_cause_no_filesystem_call` proves this: a document full of home and absolute mentions produces exactly the call list of a document without mentions. **M7 is therefore not weakened. M3 is not weakened in substance either.** Its wording ("every call ... inside the scan root") should be amended to exempt the single canonicalisation of the trusted root, which DS116 and DS103 already performed before this story. Pre-existing, out of scope: if the invoker names a directory that is itself a committed symlink, the engine's `resolve()` already moves the scan root to its target. That is engine behaviour, unchanged by DS124.
4. **Memo key cannot merge outcomes: confirmed.** `mention_ds116_reason()` depends only on the run-constant canonical root, on the document's directory (`Path(document_path).parent` inside the resolver), on the target, and on the fixed `_MENTION_SETTINGS`. It never depends on the link root or the DS116 options. The key `(document_path.rpartition("/")[0], target)` determines that directory: the same prefix always gives the same parent. Distinct prefixes that normalise alike (`x//a.md`, `x/a.md`) only split the memo, never merge it. The one string whose pathlib parent differs from its prefix (`x/.`) cannot end in `.md`, and both detectors process only `.md` documents. The DS124 memo (`mentions.py:144`) has the same property, and its step 2 depends only on the target.

### New findings

- **[LOW] R-1 The mock's containment check whitelists every ancestor of the boundary for every test.** `tests/mock/test_at_reference_no_probe.py:35-58` (`_Probes.inside`: `given.startswith(normal + os.sep)`). This is needed because `canonical_root()` realpaths the root inside the measured window. But a future regression in which a *mention* triggers an lstat of an ancestor of the root would pass every no-probe test except the home/absolute one. The walker cannot produce such a call today: a `..` above the root and an outside absolute target are both refused before any lstat. Fix (testing-expert): record the call list of a run over a document without mentions and subtract that baseline, as `test_home_and_absolute_mentions_cause_no_filesystem_call` already does. Alternatively, monkeypatch `path_boundaries.canonical_root` to pause recording, then drop the ancestor allowance.
- **[INFO] R-2** `check_text(..., mention_cache=)` is public, and its key does not include the root. A caller that reuses one cache across different roots would merge outcomes. `detect()` creates the cache per run, so nothing is affected today. Document "one cache per root" on the parameter, or add the root to the key.
- **[INFO] R-3** The round-trip symlink behaviour change from check 1 needs a release note.

### Merge-gate BLOCK conditions (re-review)

| Condition | Status |
|---|---|
| DS124 stats, lstats or opens a path outside the scan root / link root (incl. realpath, resolve, expanduser) | **Clear.** No target-driven call leaves the root (probe2, probe6 audit, kernel-aware mocks). The one realpath is of the trusted invoker root, made once per run and independent of the documents (check 3). |
| Any filesystem call for a `home` or `absolute` mention | Clear (exact baseline equality in the mock) |
| DS124 opens or reads a target | Clear |
| One document aborts the scan through an uncaught `OSError` from DS124 | Clear (the `OSError` handling at `mentions.py` is unchanged; the ENAMETOOLONG, EACCES and loop tests pass) |
| DS116 drops a code span by `@` prefix | Clear |
| DS124 logs mention text or echoes a resolved path | Clear |

### Mitigation status changes

M1 to M5 and M9 are now **Met**, including in the shared helpers. M3 is Met under the
trusted-root canonicalisation exemption above, which needs a wording amendment in the TM. All
other rows are unchanged (Met).

## Verdict: PASS_WITH_FOLLOWUP

H1 and M-A are fixed at the root, in the one shared walker, which also closes the same
pre-existing oracle for DS116, DS113 and DS101 links. L1 and L2 are fixed. No BLOCK condition
holds and there is no CRITICAL or HIGH finding. Follow-ups, none of which blocks the merge:

- R-1: testing-expert tightens the mock's ancestor allowance.
- R-2: python-expert documents or keys the public `mention_cache`.
- R-3 and the two declared `escapes_via_symlink()` behaviour changes go into the Task 08 release
  notes.
- The TM's M3 wording gets the trusted-root canonicalisation exemption.

## Story-close review - Milestone 0009 Story 01.0 - 2026-11-16

Scope: the Story 01.0 hunks only (`git diff HEAD`) of `detectors/mentions.py` (new),
`markdown_blocks.py` (`AtReference`), `detectors/path_boundaries.py` (`_walk`, `canonical_root`,
`mention_ds116_reason`, the `check_text` `mention_cache`), `detectors/paths.py`, `config.py`
(`reference_scope`, `at_reference_extensions`), `rules.py` (`opt_in_values`), `cli.py`
(`--reference-scope`), `link_root.py`, `tests/mock/test_at_reference_no_probe.py` and
`.docsentinel-baseline.json`, plus the user docs and `RELEASE_NOTES.json` entries of the story.
The working tree also holds unrelated work from earlier milestones (logging, `DS100`,
telemetry), which is out of scope here. Evidence: targeted suites, 241 + 210 passed (the
DS124 suites, the DS116 oracle mock, the DS101, DS113 and DS116 integration suites, the
link-root suite, grammar timing), and a new scratch probe `story_close_probe.py`. That probe runs
DS101, DS113, DS116 and DS124 on the three new DS116 cases. It records every `os.stat`,
`os.lstat`, `os.readlink` and `open`, and judges each path the way the kernel does: the realpath
of its parent must be inside the root. Recording pauses only for a `realpath` of the scan root
itself, so a `Path.resolve()` of a target would still be caught. No product code or test was
changed.

### Check 1 - R-1 and R-2

| Item | Result |
|---|---|
| R-1 strict mock | **Closed.** `_Probes.inside()` (`tests/mock/test_at_reference_no_probe.py:43-63`) has no ancestor allowance. It accepts a probe only when the kernel-resolved parent is the boundary or below it, so a probe of the boundary itself or of any ancestor fails. The trusted-root `realpath` is excluded structurally: `canonical_root` is wrapped in both `path_boundaries` and `mentions` (`:104-119`) so recording pauses for its duration only. Its argument is kept in `canonicalised` and asserted to be the boundary or below it (`:65-77`), and to be exactly the scan root at `:367`. A document full of home and absolute mentions records zero calls (`:364-366`). |
| R-2 `mention_cache` | **Closed.** The docstring at `src/docsentinel/detectors/path_boundaries.py:574-579` states that the key holds no root and that a cache must be one per scan root. `detect()` creates the cache per run (`:721`). The parameter remains public, which is acceptable with the documented precondition. |

### Check 2 - DS101 and DS113 defer to DS116 in the three new cases

How each rule defers, in code: DS101 calls `contained_path()` (`src/docsentinel/detectors/links.py:273`), and a `None` result skips the target before `resolved.exists()` (`:274-282`). DS113 calls `escapes_via_symlink()` (`src/docsentinel/detectors/assets.py:378`) before its only following `os.stat` (`:258`). Both helpers now run the single component walker `_walk()` (`path_boundaries.py:270-342`). DS101's `_resolve()` with `Path.resolve()` (`links.py:147-151`) is dead code with no caller (pre-existing; see INFO below).

| Case (link, image and mention forms) | DS116 | DS101 | DS113 | DS124 | Outside probes / opens |
|---|---|---|---|---|---|
| Nested symlink-out inside a symlink target (`l -> a/b`, `a/b -> ../../out/secret`) | 3 | 0 | 0 | 0 | none / document only |
| Symlink-out after 70 plain components | 3 | 0 | 0 | 0 | none / document only |
| Symlink whose target is `../out/../root/d` | 3 | 0 | 0 | 0 | none / document only |

All three forms are reported once each by DS116. DS101, DS113 and DS124 make no finding and no
probe outside the root. In the round-trip case the kernel might land back inside the root. The
walker refuses it on the first `..` above the root (`path_boundaries.py:306-309`), which is
conservative and fail-closed. A direct link spelt `../out/../root/...` is unchanged: it was
already a lexical `OUTSIDE_ROOT` at HEAD, because the resolver is untouched.

### Check 3 - probes, opens, logging

- **Step 1 versus step 2.** Step 1 (`mentions.py:184-197`) asks `mention_ds116_reason()` first and
  stops on a DS116 category. Otherwise it contains with the scan root and stats only the
  `contained_path()` result, with `follow_symlinks=False` (`:158`). Step 2 (`:200-214`) resolves
  `"/" + target` against the link root, refuses `OUTSIDE_ROOT` before any call, and contains with
  the link root. On a refusal, `escapes_via_symlink(self.link_root, ...)` walks inside the link
  root only. No walk-driven call left either boundary in the probe or in the strict mock. The
  only realpath is the trusted root (`canonical_root`, `path_boundaries.py:253-267`), which is
  the amended M3 exemption. DS113 and DS103 make the same one-off realpath of the root
  (`assets.py:443`, `paths.py:164`), which is pre-existing.
- **Never opened.** The probe recorded no `open` except each rule's read of the scanned
  document, and `test_target_never_opened` passes.
- **No mention text logged.** `mentions.py` logs `safe(document_path)`, line numbers, counts and
  fixed reasons only (`:166`, `:251-254`, `:277-287`). DS116 logs per document counts only
  (`path_boundaries.py:665-670`). The new DS103 DEBUG record (`paths.py:216-221`) echoes a
  path-like code-span candidate through `safe()`. That is the same class as the DS101 target
  record and is allowed by `docs/specs/logging.md:40,62`. An `@` span never reaches it, because
  `_is_excluded` (`paths.py:81`) runs first.
- **Config and CLI.** `reference_scope` is enum-validated (`config.py` `_ENUM_OPTIONS`), and
  `--reference-scope` uses argparse `choices` (`cli.py:439`, `:474`, `:556`), so the unescaped
  doctor line (`cli.py:330`) only ever prints `links` or `strict`. `at_reference_extensions` is a
  bounded set compared by membership only, never compiled into a pattern, and the rejected value
  is never echoed; it is re-validated in `mentions.detect` for an injected `Config` (M20).
  `opt_in_values` entries must match `OPT_IN_VALUE_PATTERN` (`rules.py:52`, `:70-72`), and an
  unknown injected value keeps DS103 inert (`:114-115`). DS124 is in `LINK_ROOT_RULES`
  (`link_root.py:69`).
- **Baseline.** `.docsentinel-baseline.json` goes from 711 to 8 fingerprints: 703 `DS103`
  entries are removed (DS103 is now opt-in) and one `DS102` line is only reformatted. No
  fingerprint was added and nothing for DS116 or DS124 is suppressed.
- **Logging TM line 45.** `docs/security/2026-11-14-logging.md:45` now describes the vector
  ("a root-escaping link (four `..` segments up to `etc/passwd`)") instead of writing a live
  link. The meaning is preserved: the test document still combines a root escape, a dangling
  link and one `0xFF` byte, and the HEAD versus working-tree outcomes that follow are unchanged.

### Findings

#### [MEDIUM] SC-1 The link-root trust guidance says only `/` targets reach the link root; DS124 sends every relative mention there (TM M18 not met)

- Vector / evidence: `docs/user/reference/configuration.md:799-800` ("Only `/` targets are
  affected; relative targets still resolve against the referring document"), and the **Trust**
  paragraph (`:805-810`), which tells users to set `link_root = "."` for untrusted content only
  because of `/` links. In code, DS124 step 2 (`src/docsentinel/detectors/mentions.py:200`)
  resolves **every** relative mention (for example one naming `secret.md`) as `"/" + target` against the link
  root. Under the default `"auto"`, untrusted content unpacked inside another checkout can
  therefore learn whether files of the enclosing repository exist. Each mention yields one bit
  (finding or no finding), visible to A3 in CI annotations. No content, type or path is
  disclosed (M17 holds).
- Impact: a user who follows the documented guidance underestimates the existence-oracle reach
  of an always-active rule (CWE-203, a documentation-level CWE-1059). TM M18 required Task 08 to
  state that DS124 uses the link root and that `link_root = "."` keeps it inside the scan root.
  `docs/user/tutorial/cli.md:248` names the step but not the trust consequence.
- Mitigation (docs-updater, before the push): in `configuration.md`, change the `link_root`
  section to "Only `/` targets of links, and the step-2 fallback of DS124 `@`-mentions, are
  affected". Name DS124 in the Trust paragraph, and add a pointer to that paragraph under
  "Document mentions (DS124)" in `docs/user/tutorial/cli.md`. Existing coverage:
  `test_link_root_dot_keeps_fallback_inside_scan_root`.

#### [LOW] SC-2 The silent step-2 refusal (owner ruling R1, TM M6) is not in the user docs

- Vector / evidence: `docs/user/tutorial/cli.md:245-251` says a mention "is reported only when
  both fail" and that an escape of the scan root is a DS116 error. It does not say that a step-2
  target outside the link root (a `..` above it, or a symlink out of it) gives **no finding at
  all** (`mentions.py:201-214`, 269-275). It also does not say that an escaping mention is
  unreported when `DS116` is ignored or `root_escape_policy = "off"`. TM M6 requires Task 08 to
  record the first of these. Both gaps are by design, but no reader can find them (CWE-693,
  silent clean result).
- Mitigation (docs-updater): add two sentences after the two-step list in
  `docs/user/tutorial/cli.md`. First, a mention whose fallback leaves the link root is not
  reported. Second, escaping mentions are reported only by `DS116`, so ignoring `DS116` or
  setting `root_escape_policy = "off"` silences them.

#### [LOW] SC-3 The release note for the round-trip case drops the word "symlink"

- Vector / evidence: `RELEASE_NOTES.json`, the DS116 behaviour-change entry ("a target that
  leaves the root and re-enters it (for example `../out/../root/d`), now a traversal error").
  The change applies only to a **symlink whose target** takes that shape. A link written that
  way was already a DS116 escape before this story (resolver unchanged, probe
  `direct_reentry.py`). As written, the note suggests the old release missed direct traversal
  links. That overstates the old gap, not the new guarantee, but it would mislead an incident
  reviewer.
- Mitigation (docs-updater): change it to "an in-root symlink whose target leaves the root and
  re-enters it (for example `../out/../root/d`) ...".

#### [LOW] SC-4 No regression tests for the round-trip case, and none for DS113 in the two other new cases

- Vector / evidence: `tests/` has no test for the `../out/../root/d` symlink target in any
  rule. DS113 has no hidden-intermediate or deep-prefix test. DS101 has only the
  hidden-intermediate one (`tests/mock/test_path_boundaries_oracle.py:252`). All of these pass
  today (probe above). Without tests, a future change to `_walk()` that went back to lexical
  collapsing of symlink targets could pass the suite.
- Mitigation (testing-expert): add `test_round_trip_symlink_target_is_ds116` to
  `tests/integration/test_at_references_ds116_ds124.py` (mention form). Add link and image forms
  to `tests/integration/test_detectors_repository_root_path_boundaries_ds116.py`. Extend
  `tests/mock/test_path_boundaries_oracle.py` so that `assets.detect` runs alongside
  `links.detect` with the kernel-aware check, for the hidden-intermediate, deep-prefix and
  round-trip layouts.

#### [INFO]

- `links._resolve()` (`src/docsentinel/detectors/links.py:147-151`) calls `Path.resolve()` and
  has no caller. It is pre-existing and harmless today, but it is a dormant symlink-following
  helper beside the safe `_lexical_target()`. python-expert may delete it in a later clean-up.
- `test_step2_never_probes_outside_link_root` checks step-1 probes against the link root, not
  the scan root (`tests/mock/test_at_reference_no_probe.py:213`). That is acceptable because
  the scan root is inside the link root in that test, and `test_step1_never_probes_outside_scan_root`
  covers step 1 strictly.

### Merge-gate BLOCK conditions (story close)

| Condition | Status |
|---|---|
| DS124 stats, lstats or opens a path outside the scan root / link root | Clear (strict mock, probe; the only realpath is the trusted root under the amended M3) |
| Any filesystem call for a `home` or `absolute` mention | Clear (zero recorded calls) |
| DS124 opens or reads a target | Clear |
| One document aborts the scan through an uncaught `OSError` from DS124 | Clear |
| DS116 drops a code span by `@` prefix | Clear (span identity, `path_boundaries.py:624-633`) |
| DS124 logs mention text or echoes a resolved path | Clear |

### Mitigation status changes

M6 and M18 (Task 08 documentation): **Partly met** (SC-2, SC-1). All other rows are unchanged
(Met).

## Verdict (story close): PASS_WITH_FOLLOWUP

There is no CRITICAL or HIGH finding and no merge-gate BLOCK condition holds. The code meets the
threat model: R-1 and R-2 are closed, and DS101 and DS113 defer to DS116 without an outside
probe in all three new cases. The follow-ups are documentation and test coverage. SC-1 should
land before the push, because the published trust guidance currently understates DS124's
reach. SC-2 and SC-3 go to docs-updater, and SC-4 to testing-expert.
