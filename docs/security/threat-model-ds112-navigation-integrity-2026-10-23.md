# Threat Model - DS112 Declared documentation navigation integrity - 2026-10-23

This is the standing, **pre-implementation** threat model for Story 09.0
(`DS112`, `fast` profile, default severity `warning`, **opt-in** via the
`navigation_indexes` config option). It is normative input for every Task
01/02/03 briefing and every reviewer of Story 09.0 and must be linked from each.
No `DS112` code exists yet (the proposed module is
`src/docsentinel/detectors/navigation.py`); the behaviour attributed below to the
shared scanner, the resolver, `config.py`, `rules.py`, `engine.py`, `discovery.py`,
`DS101`, `DS113`, and `DS116` was confirmed against the committed code, not assumed.

`DS112` reads a small set of **user-configured navigation index** Markdown
documents, extracts the local links that constitute declared navigation, and
reports three contract violations inside the scan root only: a `navigation_required`
document that no navigation link points at, a navigation target linked more than
once (`navigation_unique_targets`), and a navigation link whose local destination
does not exist (`navigation_check_missing`). A missing or unreadable configured
index is a **config/readiness error**, never a silent clean result.

The novel trust-boundary fact that dominates this model: unlike `DS113`/`DS116`,
whose only hostile input is document content, `DS112` is also driven by
**attacker-controlled configuration**. In CI and pre-commit DocSentinel runs on a
contributor-controlled checkout, so `doc_sentinel.toml` / `[tool.doc_sentinel]`
(and therefore `navigation_indexes` and `navigation_required`) are untrusted
input. A PR author chooses *which files DS112 opens*. That is a config-injection
surface on top of the content surface. It maps to CWE-22 (path traversal),
CWE-23/CWE-36 (relative/absolute traversal), CWE-59 (link following), CWE-400
with CWE-1333 (resource / regex DoS, including opening a FIFO or a huge file),
CWE-20 (improper input validation of config paths), CWE-203 (observable
discrepancy / existence oracle), CWE-117 (log injection into the `Scan failed:`
line and report sinks), CWE-178 (case handling), CWE-693 (protection-mechanism
failure / scanner-masking evasion), and OWASP A01:2021 (Broken Access Control)
and A09:2021 (Security Logging).

The DS116 and DS113 standing requirements apply unchanged as a floor: filesystem
containment, no existence oracle outside root, no opening of non-Markdown or
special files, bounded repr-escaped echo, no quadratic shapes, decode-once,
tokenizer-evasion parity with CommonMark masking (requirement 16), and honest
scope. This document adds the DS112-specific controls and relaxes none of them.

## Scope and method

In scope: the proposed analyzer `src/docsentinel/detectors/navigation.py`; its use
of the shared scanner `scan_markdown` and resolver `resolve_local_reference` in
`src/docsentinel/markdown_blocks.py` (`index.local_references`,
`index.reference_definitions`, `index.reference_uses`, `index.inline_code`,
`index.comments`, and the masking those carry); the containment helpers
`is_ds116_owned` and `escapes_via_symlink` in `detectors/path_boundaries.py`; the
`DS112` config options in `config.py` (`navigation_indexes`, `navigation_required`,
`navigation_unique_targets`, `navigation_check_missing`, validated by
`_require_root_path_list` / `_is_within_root`); the opt-in registration machinery
in `rules.py` (`Rule.opt_in_option`, `opt_in_satisfied`); the engine notice and
dispatch in `engine.py`; discovery's symlink/regular-file handling in
`discovery.py`; and the report sinks in `reporting.py` plus the CLI `Scan failed:`
path in `cli.py`. The method is STRIDE-lite over two trust boundaries:
untrusted **config** -> which files are opened, and untrusted **content** ->
filesystem probes and report sinks.

## Assets and trust boundaries

| Asset | Trust level | Why it matters |
|-------|-------------|----------------|
| `navigation_indexes` / `navigation_required` config values | Hostile | In CI/pre-commit the config file lives in the contributor-controlled tree; a PR author picks which paths DS112 opens and stats. An injected `Config` (library caller) bypasses `load_config` validation entirely (see `rules.opt_in_satisfied` docstring). |
| Untrusted Markdown content of the index docs | Hostile | Authors control every nav link, reference definition, fragment, and HTML attribute inside a configured index. |
| Scan-root subtree | Trusted boundary | The only region DS112 may read or `stat`; existence disclosure here is of the repo's own files and is not sensitive. |
| Filesystem outside the root | Off-limits | Must never be opened, `stat`-ed, `realpath`-ed, or symlink-followed by DS112; this is the DS116 boundary and DS112 inherits it. |
| Special files inside the root (FIFO, device, socket, huge file) | Hostile-adjacent | A committed FIFO/device named as a configured index, or pointed at by a nav link, must never be `open()`-ed; opening blocks the scan or reads unbounded data. |
| Report sinks (text/json/github), CI logs, and the `Scan failed:` stderr line | Semi-public | `finding.message` and a readiness `ConfigError` message are rendered verbatim into CI logs and PR annotations; attacker-controlled target/config strings land here. |
| Pass/fail exit code (`0`/`1`/`2`) | Integrity/availability signal | `warning` severity means a finding blocks only under `--strict`; a readiness `ConfigError` is exit `2`. A false clean hides a broken nav contract; a spurious `ConfigError` is a merge-gate DoS. |

Threat actors: a contributor who submits a crafted tree **and config** that runs
through CI or pre-commit (to open an out-of-root or special file, probe host
paths, inject log bytes, stall the run, or wedge the gate); a reader of public CI
logs harvesting an out-of-root existence oracle. Supply chain is out of scope
(stdlib-only analyzer, no network, no execution of document content).

## Empirical grounding (confirmed against committed code)

- `config.py` validates `navigation_indexes`/`navigation_required` only
  **lexically** through `_require_root_path_list` -> `_is_within_root`
  (lines 382-421): absolute paths, drive/UNC, backslashes, and `..`-above-root are
  rejected at load; **but globs, non-Markdown paths, directories, FIFOs, symlinks,
  and nonexistent paths all pass** (it is a lexical containment check with no
  filesystem access). An **injected `Config`** skips this entirely.
- `opt_in_satisfied` (`rules.py:51-78`) already treats a non-empty
  `navigation_indexes` tuple as "on" and an empty one as "off"; the docstring
  names `navigation_indexes` explicitly. So DS112 registers with
  `opt_in_option="navigation_indexes"` exactly as DS110 uses
  `require_fence_languages`.
- `engine.py` (lines 197-212) excludes an off opt-in rule from the evaluated
  count and names it `DS112 (set navigation_indexes)`; it does **not** catch
  analyzer exceptions, so a `ConfigError` raised by DS112 propagates out of
  `scan()`.
- `cli.py` wraps `scan()` in `except (ConfigError, ValueError, OSError)` ->
  prints `Scan failed: {exc}` to stderr and returns **2** (lines 229-231). This is
  the existing config/scan-failure exit code; the readiness-error path needs no
  new exit code and no JSON schema change.
- `discovery.py` inventories **regular files only** (`path.is_file()` is true and
  `path.is_symlink()` is false, lines 31-32; directory symlinks pruned, line 26),
  so a FIFO/socket/directory/symlink at an index path is simply absent from the
  `documents` tuple. A huge *regular* file is still inventoried (only its size is
  `stat`-ed, never opened, line 42).
- The shared scanner does **not** model list structure, block quotes, or indented
  code (documented in `docs/dev/markdown_dialect.md:61`). `LocalReference`
  (`markdown_blocks.py:208-230`) carries no list-item context and its `category`
  is only `"ordinary"`/`"image"` (`"nav"` is reserved, never emitted). So the
  scanner cannot tell DS112 which links are navigation. This forces ruling R1.
- `is_ds116_owned` and `escapes_via_symlink` (`path_boundaries.py:206-297`) are the
  lexical, non-following containment gates DS112 must reuse before any `stat`.

## Threats (STRIDE findings)

Each finding lists vector, impact, and required control. "Matrix" marks a case
already covered by the 14 Task 02 fixtures (8 CLEAN, 5 FINDING, 1 ERROR); "extra"
marks a test the implementer must add beyond the matrix.

### [HIGH] Config-injection: opening an out-of-root, special, or oversized index

- Vector / evidence: `navigation_indexes` is attacker-controlled in CI. Lexical
  config validation (`_is_within_root`) rejects `..`/absolute/drive/UNC but
  **not** a symlink that points outside, a FIFO/device/socket, a directory, a
  non-Markdown file, a glob, or a path an injected `Config` never validated. A
  naive DS112 that does `open(root / index_path).read()` (the pattern DS116/DS113
  use for *discovered* docs, `path_boundaries.py:459-466`) on a configured path
  would: open a FIFO and **hang the whole scan forever** (CWE-400); `read()` a
  multi-gigabyte in-root file into memory (CWE-400); follow an in-root symlink to
  `/etc/passwd` and read it (CWE-22/CWE-59/CWE-203); or open a directory.
- Impact: one crafted PR config wedges every pre-commit/CI run, reads an
  out-of-root file, or exhausts memory - all before a single nav link is parsed.
- Mitigation (required, R2): DS112 opens an index **only** when it is a member of
  the engine-supplied `documents` tuple (discovery has already proven it is an
  in-root, non-symlink, regular, include-matched `.md` file). Before the open,
  **re-validate defensively** because an injected `Config` bypassed
  `load_config`: confirm `is_ds116_owned(root, ".", index_path)` is false and
  `escapes_via_symlink(root, root / index_path)` is false, and `os.stat` +
  `stat.S_ISREG` the path (never open a FIFO/device/socket/directory). Bound the
  read. A configured index that fails any check, or is absent from `documents`,
  is the **readiness error** of R3 - never a silent skip and never an open.
- Test case (extra, syscall recorder + `tmp_path`): a configured index that is a
  runtime `os.mkfifo`, a runtime in-root symlink to an outside file, a directory,
  and a nonexistent path each complete promptly, perform **zero** `open()` on the
  special/outside path, and raise the readiness error (R3). Assert via a patched
  `os.open`/`builtins.open` counter.

### [HIGH] Existence oracle and outside-root I/O on nav targets (inherited DS116/DS113)

- Vector / evidence: the `navigation_check_missing` probe must decide whether a
  nav link's destination exists. The resolver is lexical and returns `RESOLVED`
  for any non-escaping path, but `RESOLVED` is **not** proof of containment - an
  in-root symlink can still point outside (`escapes_via_symlink` exists for this).
  A DS112 that calls `Path.exists()`/`os.stat()` on a target classified
  `OUTSIDE_ROOT`, on an unsafe `UNSUPPORTED` category, or on an in-root symlink
  that escapes, re-creates the Story 11.0 oracle: it stats outside the root and
  leaks existence through the finding-vs-no-finding signal (CWE-203/CWE-22/CWE-59).
- Impact: a PR author learns whether arbitrary paths exist on the CI host, and
  DocSentinel touches the filesystem outside its promised boundary.
- Mitigation (required, R4/R6): before any `stat`, route every nav target through
  `resolve_local_reference` and `is_ds116_owned`; act on existence **only** for a
  `RESOLVED` in-root candidate for which `escapes_via_symlink` is false. Use
  `os.stat` only (never `open`), one `stat` per distinct resolved path (memoised).
  An escaping nav target is reported *lexically* as an escape finding with **no**
  filesystem call (R4), overlapping DS116 by design.
- Test case (matrix `unsafe_parent_navigation` + extra recorder): the escaping nav
  target yields a DS112 escape finding and **zero** `stat`/`open` on any path
  resolving outside the canonical root.

### [HIGH] Readiness error must fail closed, not fall through to clean

- Vector / evidence: Task 02 `missing_index_is_error` configures
  `navigation_indexes=["docs/missing.md"]`; the file does not exist, so it is
  absent from `documents`. If DS112 merely skips an absent index, the scan returns
  **zero findings** and the engine notice counts DS112 as "evaluated" - a false
  clean that hides a broken nav contract and a misconfiguration (CWE-20, OWASP
  A09). `error`-scenario fixtures explicitly forbid treating a dropped detector as
  a clean scan (Task 03 point 5).
- Impact: a typo or a deliberately broken index silently disables the entire nav
  check while appearing green.
- Mitigation (required, R3): a missing/unreadable/non-regular/out-of-root/non-`.md`
  configured index raises `ConfigError` (a readiness error). The engine propagates
  it; the CLI maps it to exit **2** with `Scan failed: ...`; the Python API raises;
  the pytest test asserts the exception (not zero findings). No new exit code, no
  JSON schema v1 change. The whole scan fails closed - correct for an operator
  misconfiguration.
- Test case (matrix `missing_index_is_error`): assert `ConfigError` (or the scan
  `pending`/failure state) from `scan`, the CLI exit `2`, and that no clean
  `ScanResult` with empty findings is produced.

### [MEDIUM] Log injection / path disclosure through the readiness-error message

- Vector / evidence: the readiness `ConfigError` message will embed the
  attacker-controlled configured index path, and `cli.py:230` prints it verbatim
  to stderr/CI logs; `reporting.py` renders finding messages verbatim and its
  `_escape_data` neutralises only `%`/CR/LF for the github format, not NUL/ESC or
  other C0/C1 bytes (CWE-117). A configured path such as
  `docs/\x1b]0;pwned\x07.md` or one carrying CR/NUL corrupts or spoofs a log line;
  echoing a resolved absolute path leaks host layout (CWE-203).
- Impact: control/ESC bytes corrupt or spoof CI log lines; a resolved absolute
  path discloses the CI host layout.
- Mitigation (required): both the readiness `ConfigError` message and every
  finding message echo **only** the author's raw target or the configured path,
  bounded and repr-escaped exactly as `path_boundaries._echo` / `assets._echo` do
  (bound to a small max, then `unicode_escape`). Never echo the resolved absolute
  path, a neighbouring path's existence, or a file type. Do not weaken the github
  newline/percent escaping.
- Test case (extra): a configured index and a nav target each carrying NUL/ESC/CR/LF
  and a 10,000-char length render under the bound with no raw control byte and no
  second github command line; assert the canonical root string never appears in any
  message or in the `ConfigError`.

### [MEDIUM] Scanner cannot scope "navigation"; DS112 must not add a hiding/over-masking hole

- Vector / evidence: the scanner does not model lists, so DS112 must itself decide
  which links are navigation (R1). CLEAN `prose_link_outside_list` requires an
  ordinary broken prose link **not** to be flagged, while list links are checked;
  CLEAN `fake_nav_in_fence` requires a nav-looking link inside a fenced block to be
  ignored. If DS112 scopes navigation with its own regex over **unmasked** source,
  it (a) over-masks or (b) hides a link the renderer makes live, either a false
  positive or a false clean (CWE-693). Contract C forbids a second parser and
  regex over unmasked source.
- Impact: at most a false clean (a broken nav link silently passes) or a false
  positive (a prose link wrongly flagged); both erode the gate.
- Mitigation (required, R1): DS112 derives list-item membership **line-by-line over
  the scanner's masked text** (fenced code, inline code, and HTML comments already
  blanked), using a bounded, linear marker test (`-`/`*`/`+`, or ordered `N.`/`N)`,
  with 0-3 spaces of indentation), exactly as `DS108` derives its reference view
  and `DS117` its table rows over masked text. Only `LocalReference`/`ReferenceUse`
  tokens whose start line is a navigation list item are navigation. Any construct
  DS112 treats as masked must be masked only where CommonMark hides it
  (requirement 16). Inherit and document the scanner's list/indent/block-quote gaps
  in `docs/dev/markdown_dialect.md`; do not claim complete nav detection.
- Test case (matrix `prose_link_outside_list`, `fake_nav_in_fence`,
  `valid_nested_navigation` + extra markdown-it differential): a nav-looking link
  in a fence/inline-code/comment is never navigation; a list link is; a prose link
  outside any list is not.

### [MEDIUM] Algorithmic DoS - huge nav lists, many required targets, per-link I/O

- Vector / evidence: a configured index can carry thousands of list items / links,
  and `navigation_required` thousands of entries. A naive "is each required target
  present among the nav links?" is O(required x links) (CWE-400), and a per-link
  `stat` for `navigation_check_missing` is one syscall each.
- Impact: a crafted index plus config stalls pre-commit/CI; quadratic required x
  link blows up super-linearly.
- Mitigation (required): build the set of resolved, fragment-stripped nav targets
  **once** (O(links)); each required check is a set membership (O(1)); duplicate
  detection is a dict count; so the whole check is O(links + required). Perform at
  most **one** `stat` per distinct resolved in-root path (memoised within the
  document), run the lexical containment gate before any `stat` so escaped targets
  cost no I/O, and bound the index read. The list-marker scan is a single linear
  pass with no catastrophic regex. Prove the bound with
  `tests/timing_helpers.assert_scales_linearly` over doubling series for
  (a) many list items/links, (b) many `navigation_required` entries, and
  (c) a single very long line, in CPU time, with fixed expected finding counts so
  the bound cannot pass vacuously.
- Test case (extra): the three doubling-series timing tests above.

### [MEDIUM] Case-insensitive filesystem divergence on the missing-destination probe

- Vector / evidence: `navigation_check_missing` stats a nav destination;
  `os.stat` on macOS/Windows is case-insensitive, so a link to `Docs/Guide.md`
  resolving to committed `docs/guide.md` exists there but not on a case-sensitive
  Linux runner (CWE-178). Separately, required-vs-nav **string** comparison (R5) is
  lexical and must pick one case policy.
- Impact: a platform-dependent nav finding; at `warning`/`--strict` this is a
  nondeterministic gate.
- Mitigation (required, documented): document that the existence probe is decided
  by the host filesystem's case policy (as `DS113` does), and that the
  required/duplicate **string** comparison is exact (case-sensitive, POSIX-
  normalized) - no per-directory `scandir` case check by default.
- Test case (extra): record the documented reason in the test module if the
  case-mismatch behaviour is not asserted portably.

### [LOW] Target identity / normalization mismatches (required vs nav vs duplicate)

- Vector / evidence: `navigation_required` entries are root-relative; a nav link
  resolves **relative to the index location** (`nested_relative_nav_path`), not the
  process cwd; `duplicate_with_fragments` requires two links to the same doc with
  different `#fragment` to count as one duplicate target. Comparing raw strings
  would miss `./guide.md` vs `docs/guide.md`, or split a duplicate on its fragment.
- Impact: false positives/negatives on the required and duplicate checks; no
  containment impact (all stays in-root).
- Mitigation (required, R5): normalize every nav link and every required entry to
  the same canonical **root-anchored, fragment-stripped** form via
  `resolve_local_reference(root, index_path_or_".", target).path`; the resolver's
  single HTML-entity + percent decode and `<...>` unwrap are reused (never a second
  decode). Duplicate identity is the resolved path **without** fragment.
- Test case (matrix `required_pages_all_listed`, `nested_relative_nav_path`,
  `duplicate_navigation_target`, `duplicate_with_fragments`,
  `fragment_navigation_is_local`, `external_navigation_links`).

### [LOW] Reference-style and shortcut nav items (false clean)

- Vector / evidence: CLEAN `reference_style_navigation_item` uses `[text][label]`
  with `[label]: docs/guide.md`; DS112 must join `index.reference_uses` (label +
  span) to `index.reference_definitions` (label -> target) to resolve it. But the
  shared scanner does **not** populate `reference_uses` for **shortcut** `[label]`
  forms (documented gap, `markdown_dialect.md:60`), so a nav item written as a bare
  shortcut is invisible to DS112 - a false clean (CWE-693, the lower-risk
  direction: hides a broken nav item, never blocks a good one).
- Impact: a broken shortcut-reference nav item silently passes.
- Mitigation (R7): join full/collapsed reference uses to definitions by normalized
  label; document shortcut-reference nav items as a known false negative in the
  rule docstring and `markdown_dialect.md`, consistent with the DS113 shortcut
  ruling. Do not add an ad-hoc shortcut regex over unmasked source.
- Test case (matrix `reference_style_navigation_item` CLEAN + extra differential
  pinning the shortcut false negative).

### [LOW] Opt-in honesty - "evaluated" accounting with sub-checks off

- Vector / evidence: `opt_in_satisfied` keys only on `navigation_indexes`. If an
  operator sets `navigation_indexes` but turns off `navigation_check_missing`,
  `navigation_unique_targets`, and leaves `navigation_required` empty, DS112 is
  counted as "evaluated" in the engine notice although it can emit nothing but an
  escape finding. Conversely DS112 in `enabled_rules` with empty
  `navigation_indexes` is correctly named `DS112 (set navigation_indexes)` and
  excluded from the evaluated count.
- Impact: a mildly misleading "evaluated" count; no security impact, but it is the
  "disabled policy masquerading as audited" honesty contract from contract D.
- Mitigation (R8): accept that the policy being *on* (indexes configured) makes
  DS112 genuinely evaluated even when the operator disabled sub-checks; document
  that the sub-check toggles are not part of the opt-in gate. Keep the DS110
  precedent: never present a disabled DS112 (empty `navigation_indexes`) as an
  evaluated rule.
- Test case (matrix `without_configured_indexes` behaviour via Task 03 point 3/20:
  with no indexes, assert DS112 registered, zero findings, and named not-applicable
  in the notice; with indexes set, assert it is counted evaluated).

### [INFO] Repudiation / Elevation - out of scope, recorded

DocSentinel is a local/CI CLI with no audit log, no authentication surface, and no
automated remediation; DS112 only reads and reports. There is no production action
and therefore no `DOC_SENTINEL_PROD_CONFIRMED`-style guard to respect. Consistent
with the DS116/DS113 models, repudiation and elevation have no DS112 surface.

## Required rulings (resolve before the 14 Task 02 fixtures freeze)

These change the DS112 behaviour contract and must be recorded in the rule
docstring and `docs/dev/markdown_dialect.md` before Task 02 freezes.

- **R1 - Navigation scope.** The shared scanner does not model lists, so DS112
  derives navigation-list membership itself, line-by-line **over the scanner's
  masked text**, with a bounded linear marker test (`-`/`*`/`+`, ordered `N.`/`N)`,
  0-3 space indent). Only local links / reference uses on a navigation list item
  (plus, optionally, a configured nav section) are navigation; prose links outside
  lists and links inside fenced/inline-code/comment regions are not. Confirm this
  is the scope, or state an alternative and prove `prose_link_outside_list` and
  `fake_nav_in_fence` still pass. No regex over unmasked source.

- **R2 - Index read discipline and membership.** A configured index is read only
  when it is a member of the engine-supplied `documents` (in-root, non-symlink,
  regular, include-matched `.md`), and only after a defensive re-check
  (`is_ds116_owned` false, `escapes_via_symlink` false, `os.stat` + `S_ISREG`,
  bounded read) because an injected `Config` bypasses `load_config` validation.
  DS112 performs **no** `open()` of any path not so validated. Confirm, or define
  an equivalently safe read path. (Settle whether a configured index that exists
  but is **excluded** by `include`/`exclude` is a readiness error or a silent skip
  - recommended: readiness error, since the configuration is internally
  inconsistent.)

- **R3 - Readiness-error surface and exit behaviour.** A missing, unreadable,
  non-regular, non-`.md`, or out-of-root configured index raises `ConfigError`
  (fail-closed), propagating through `engine.scan()` to CLI exit **2**
  (`Scan failed:`) and to a raised exception for the Python API / pytest. It is
  **not** a `Finding` (a warning-severity finding is exit 0, baseline-suppressible,
  and would read as a near-clean scan) and **not** a silent skip. No new exit code,
  no JSON schema v1 change. The `ConfigError` message repr-escapes and bounds the
  attacker-controlled index path. Confirm `ConfigError` is the surface (vs a shared
  `pending`/not-evaluated state if M4 provides one).

- **R4 - Escaping nav target.** `unsafe_parent_navigation` is a DS112 FINDING: an
  escaping nav target (resolver `OUTSIDE_ROOT`, or `is_ds116_owned` true) is
  reported by DS112 **purely lexically, with zero filesystem access**, as a
  "navigation target escapes the documentation root" finding; DS116 independently
  reports it at `error` (documented intentional overlap, contract E). DS112 never
  `stat`s or opens an escaped target. Confirm DS112 emits the finding (vs delegating
  wholly to DS116) - the fixture requires a DS112 finding.

- **R5 - Target identity / normalization.** Nav links and `navigation_required`
  entries are compared as canonical **root-anchored, fragment-stripped** paths
  produced by `resolve_local_reference` (reusing its single entity+percent decode
  and `<...>` unwrap; nav links resolve relative to the index location, not cwd).
  Duplicate identity ignores the fragment (`duplicate_with_fragments`). String
  comparison is exact/case-sensitive; the existence probe's case behaviour is the
  host FS's and is documented. Confirm.

- **R6 - Missing-destination ownership and discipline.** `navigation_check_missing`
  probes existence with `os.stat` only (never `open`), on `RESOLVED`, in-root,
  non-DS116-owned, non-symlink-escaping targets; fragment-only and `EXTERNAL`
  targets are skipped (`fragment_navigation_is_local`, `external_navigation_links`).
  This overlaps DS101's dangling-link check by design (both may flag a broken nav
  link) and is documented; DS112 does **not** depend on `DS107` (the M4 graph is
  not in the audited master tree) and does its own normalized resolution. Confirm
  the overlap and the DS107 independence.

- **R7 - Reference-style vs shortcut nav items.** Full `[text][label]` and
  collapsed `[label][]` nav items are resolved by joining `reference_uses` to
  `reference_definitions` by normalized label; **shortcut** `[label]` nav items are
  a documented scanner gap (not in `reference_uses`) and are an accepted DS112 false
  negative, not patched with an ad-hoc regex. Confirm.

- **R8 - Opt-in accounting.** The opt-in gate is `navigation_indexes` only;
  `navigation_check_missing`/`navigation_unique_targets`/`navigation_required` are
  sub-options, not part of the gate, so DS112 is "evaluated" whenever indexes are
  configured even if sub-checks are off. Empty `navigation_indexes` makes DS112
  not-applicable and it is named (not counted) in the engine notice, mirroring
  DS110. Confirm.

## Verdict on default severity `warning` + opt-in design

**The `warning` + opt-in posture is the right one and should stand.** It is
strictly safer than the DS116/DS113 `error` default-on posture:

- Opt-in (empty `navigation_indexes` by default) means DS112 has **zero**
  default-on attack surface: on an unconfigured repo it opens nothing, stats
  nothing, and is honestly reported as not-applicable. The config-injection surface
  (the HIGH finding) only exists once an operator opts in, and then the operator
  has chosen to trust the config - except in CI, where the config is still
  attacker-controlled, which is exactly why R2's defensive re-validation and R3's
  fail-closed readiness error are mandatory even under opt-in.
- `warning` severity means a nav-contract finding blocks the merge only under
  `--strict`, so a false positive is an advisory, not a hard merge-gate DoS. No
  severity-downgrade knob (like `root_escape_policy`/`missing_asset_policy`) is
  required, because `warning` + `select`/`ignore` + baseline already give the
  operator the downgrade path. **Do not** raise DS112 to `error` default-on: its
  findings fire on ordinary authoring patterns and its scope depends on a
  self-derived list heuristic (R1), both false-positive-prone.
- The one non-advisory outcome - the readiness `ConfigError` (exit 2) - is correct
  and intended: a misconfigured navigation policy should fail closed rather than
  pass green.

## Merge-gate BLOCK conditions (any one ships => BLOCK, keep out of `master`)

- DS112 opens, `stat`s, `realpath`s, `resolve`s, or symlink-follows any path that
  resolves **outside** the canonical root (including via a configured index or a
  nav target), or re-introduces the DS101/DS103 outside-root existence oracle.
- DS112 `open()`s a configured index or nav target that is **not** a validated
  in-root regular `.md` file - in particular opening a FIFO/device/socket
  (hang/unbounded read) or a directory, or reading an unbounded file.
- A missing/unreadable/out-of-root configured index yields a **clean** scan with
  empty findings (false clean) instead of the R3 readiness error.
- DS112 echoes a resolved absolute path, a neighbouring path's existence, or a file
  type into any report sink or the `Scan failed:` line, or leaves control/ESC bytes
  un-escaped in a message or `ConfigError`.
- DS112 adds a second path resolver, a third-party Markdown parser, a regex over
  **unmasked** source, a network call, or any execution of document content; or it
  is super-linear (quadratic required x links, or an unbounded symlink/line flood).

## Standing requirements checklist (apply to every Story 09.0 task and review)

1. **Opt-in registration.** Register `DS112` exactly once in `RULES` and
   `ANALYZERS`, `fast` profile, severity `warning`, with
   `opt_in_option="navigation_indexes"`; selectable via `select`/`ignore`,
   honouring baseline; CLI `rules` tags it `[opt-in: set navigation_indexes]`,
   `doctor` counts it among opt-in rules, and the engine notice names it when
   indexes are unset. Stdlib-only import graph; passes the fast-only import
   isolation test (no spacy/textacy/sklearn/docsig/network on the fast path).
2. **Config-injection containment (R2).** Open an index only when it is a member of
   the discovered `documents`; before the open re-validate with `is_ds116_owned`
   false, `escapes_via_symlink` false, and `os.stat` + `stat.S_ISREG`; bound the
   read. Never open a non-discovered, special, directory, symlink-out, or
   out-of-root path. Test: syscall recorder proving zero `open()` on a runtime
   FIFO/symlink-out/directory/nonexistent configured index.
3. **No filesystem access outside the root (R4/R6).** Route every nav target
   through `resolve_local_reference` + `is_ds116_owned`; `stat` only `RESOLVED`,
   in-root, non-symlink-escaping targets, with `os.stat` (never `open`), one `stat`
   per distinct resolved path (memoised), gate before stat. Escaping targets are
   reported lexically with no I/O. Test: recorder proving zero outside-root
   `stat`/`open` over a hostile corpus.
4. **Fail-closed readiness error (R3).** Missing/unreadable/non-regular/non-`.md`/
   out-of-root configured index raises `ConfigError` -> engine propagation -> CLI
   exit 2 / API exception; never a clean empty-findings scan; no JSON schema or
   exit-code change. Test: `missing_index_is_error` asserts the exception/exit 2.
5. **Bounded, repr-escaped echo.** Finding messages and the readiness `ConfigError`
   echo only the author's raw target / configured path, bounded and
   `unicode_escape`-escaped (reuse the DS116/DS113 `_echo` discipline); never a
   resolved absolute path, neighbour existence, or file type; preserve the github
   newline/percent escaping. Test: NUL/ESC/CR/LF and 10,000-char target render
   under the bound with no raw control byte and no injected github command.
6. **Linear cost.** O(index bytes + links + required); set/dict for required and
   duplicate checks (never quadratic); one linear masked-text list-marker pass with
   no catastrophic regex; bounded index read; memoised stat. Test:
   `assert_scales_linearly` doubling series for many links, many required entries,
   and one very long line, in CPU time, with fixed expected finding counts.
7. **Scanner-evasion parity (requirement 16, R1).** Derive navigation only over the
   scanner's masked text; mask only what CommonMark hides; add a `markdown-it-py`
   scratch-oracle differential over list/prose/fence/reference nav cases asserting
   DS112 treats as navigation no link the renderer would not make a live list link,
   and (best-effort) does not miss one within documented gaps. Inherit and document
   the list/indent/block-quote/shortcut gaps in `docs/dev/markdown_dialect.md`.
8. **Normalization & identity (R5/R7).** Compare canonical root-anchored,
   fragment-stripped resolver paths; nav links resolve relative to the index
   location; duplicate identity ignores the fragment; full/collapsed reference uses
   joined to definitions by normalized label; shortcut nav items documented as a
   known false negative. Document the platform-dependent case behaviour of the
   existence probe (R: case policy).
9. **Documented overlap & independence.** DS112's missing-destination overlaps
   DS101 (dangling link) and its escape finding overlaps DS116; both overlaps are
   documented (contract E). DS112 does not depend on DS107 (absent from the audited
   master tree) and does its own normalized resolution. Collapse duplicate
   `(line, message)` findings as DS116/DS113 do.
10. **Fixtures.** All 14 Task 02 fixtures (8 CLEAN, 5 FINDING, 1 ERROR) loaded
    individually via `asset_case` into fresh `tmp_path`; expected outcomes from a
    checked manifest, not from whatever the analyzer emits; symlink/FIFO fixtures
    generated at runtime and skipped only with an explicit unavailable reason;
    intentionally broken fixtures kept byte-for-byte and excluded from self-scan and
    formatters; no `.skip`/`.xfail` hiding regressions; `error` fixture asserts the
    exception, not zero findings.
11. **No regressions.** DS101-DS103 and the shipped M5 fast rules (DS104-DS110,
    DS113, DS116, DS117) stay green - especially source line offsets, escape
    handling, root resolution, and scanner masking; no accidental baseline change to
    make self-scan green.
12. **No network, no execution, no content transmission.** Never execute, import,
    or fetch documentation content; no raw document content persisted unsafely in
    reports.

Fix handoff: implementation of `navigation.py`, the masked-text list scoping, and
any shared-scanner change go to `python-expert`; the syscall-recorder, runtime
FIFO/symlink, markdown-it differential, flood-slope, and readiness-error regression
tests go to `testing-expert`.

## Verdict: PASS_WITH_FOLLOWUP

No CRITICAL exists because no `DS112` code is written yet; this is the pre-code
standing model. The spec is sufficient to begin **provided** the standing
requirements above are met and rulings **R1-R8** are recorded before the Task 02
fixtures freeze. The `warning` + opt-in design is endorsed and should not be
escalated to `error` default-on.

**DS112 must be documented as a best-effort structural guard, not a complete
navigation-integrity control:** it inherits every shared-scanner false negative
(multi-line/nested-paren destinations, multi-line HTML tags, unquoted attributes,
shortcut references) plus the self-derived list-membership heuristic and the
platform-dependent case behaviour of the existence probe.

## Security review findings - Story 09.0 DS112 - 2026-10-23

Post-implementation adversarial review of the shipped `src/docsentinel/detectors/navigation.py`
(uncommitted, branch `milestone/0005-deepening-test-case-stage-2`) against this model's
standing requirements, rulings R1-R8, and BLOCK conditions. The HIGH/MEDIUM pre-code threats
were re-tested against the real code and a recorder-backed hostile corpus; the implementation
holds the floor. Evidence is `file:line` into the audited tree. No CRITICAL exists and no BLOCK
condition is met.

### Pre-code HIGH/MEDIUM threats - verified closed

- **Config-injection open discipline (R2) - CLOSED.** `_require_readable_index`
  (`navigation.py:536-569`) gates every open behind, in order: `is_ds116_owned` (lexical,
  no FS), resolver `RESOLVED` containment, membership in the engine's discovered
  `document_identities`, `escapes_via_symlink`, and `os.stat` + `stat.S_ISREG`; the read is
  bounded to `_MAX_INDEX_BYTES` (`navigation.py:521-533`). The `documents` tuple is always
  engine-discovery output (regular, non-symlink, in-root `.md`), so an injected `Config`
  can only name a discovered file. Even a hostile *direct* `detect(root, documents, config)`
  caller that fabricates `documents` is contained: a directory is caught by `S_ISREG`
  (`tests/unit/test_detectors_navigation.py:462`), an out-of-root entry by the
  `is_ds116_owned`/`OUTSIDE_ROOT` gate (`:486`), and a parent-/final-symlink-to-outside by
  `escapes_via_symlink` before any `os.stat`. A FIFO configured as an index is never opened
  (`tests/mock/test_detectors_navigation_oracle.py:259-290`, skipped with a reason where
  `os.mkfifo` is absent).
- **Outside-root I/O / existence oracle (R4/R6) - CLOSED.** Every nav target is routed through
  `is_ds116_owned` + `resolve_local_reference` before any FS call; an escaping target is
  reported lexically with zero FS access (`navigation.py:467-475`), and the single
  `os.stat`-only existence probe runs only on a `RESOLVED`, in-root, non-`is_ds116_owned`,
  non-`escapes_via_symlink` target, memoised one `stat` per distinct resolved path
  (`navigation.py:388-413`, `:484-493`). The syscall recorder (wrapping `os.stat/lstat/
  readlink/scandir/listdir`, `os.path.*`, `builtins.open`, and `Path` methods) asserts zero
  access to any path resolving outside the canonical root over an adversarial corpus
  including an in-root symlink to a real outside secret
  (`tests/mock/test_detectors_navigation_oracle.py:176-217`). `os.stat` never opens content,
  so a FIFO/device target resolves without blocking.
- **Fail-closed readiness error (R3) - CLOSED for the enumerated cases.** Missing, non-regular,
  out-of-root, and non-discovered configured indexes all raise `ConfigError`
  (`navigation.py:553-569`), which `engine.scan()` does not catch and `cli.py:229-231` maps to
  exit 2 via `Scan failed: {exc}`; no clean empty-findings scan is produced
  (`tests/unit/test_detectors_navigation.py:437,462,486,556,583`). See the MEDIUM below for the
  one readiness case that escapes this surface.
- **Log injection / path disclosure (CWE-117/203) - CLOSED.** Both finding messages and every
  readiness `ConfigError` echo only the author's raw target / configured path through `_echo`
  (`navigation.py:208-222`): bounded to 80 chars then `unicode_escape`, so NUL/ESC/C1/CR/LF are
  rendered as printable `\xNN`/`\uNNNN` and never reach a sink raw. Because `_echo` already
  neutralises newlines, the GitHub sink (`reporting.py:14-16,26-35`, which escapes only
  `%`/CR/LF) cannot be driven to emit a second `::error`/`::warning` command line from an index
  name or nav target - the attacker's `::` lands mid-line with no raw newline to start a new
  command. The resolved absolute path is never echoed
  (`tests/unit/test_detectors_navigation.py:515`).
- **Algorithmic DoS (R6/linear) - CLOSED.** `navigation_required` is set membership over the
  resolved-target union (O(links + required), `navigation.py:638-643`); duplicate detection is a
  per-index set (`:481-485`); the list-marker test is an anchored, bounded-quantifier regex
  (`_LIST_MARKER_RE`, `navigation.py:198`) applied once per physical line, so a giant single line
  costs O(1) at the marker test; the index read is capped; the missing-destination `stat` is
  memoised across indexes (`navigation.py:630`). Linear scaling is pinned by
  `assert_scales_linearly` doubling series for single-line floods, multi-line floods, and the
  required-vs-links shape (`tests/unit/test_detectors_navigation.py:676-771`). "Many distinct
  missing targets" costs at most one `stat` per distinct resolved path (linear in links, bounded
  by the 5 MB read cap), satisfying the contract.
- **Opt-in honesty (R8) - CLOSED.** The gate is `navigation_indexes` only; `detect` returns `()`
  when it is empty (`navigation.py:618-619`), and `engine.py:199-210` excludes an off opt-in
  rule from the evaluated count and names it `DS112 (set navigation_indexes)`. With indexes set,
  DS112 is counted evaluated even if sub-checks are off (R8, accepted). A disabled policy never
  masquerades as evaluated.
- **Documented overlaps / no double-report defect.** The escape finding (R4) intentionally
  overlaps DS116 at `error`, and the missing-destination probe (R6) overlaps DS101; both are
  documented. Within DS112, duplicate `(line, message)` pairs are collapsed
  (`navigation.py:449-459`). No unintended double reporting against DS101/DS113/DS116.

### [MEDIUM] Non-UTF-8 (and mid-read OSError) index bypasses the R3 `ConfigError` surface

- Vector / evidence: `_require_readable_index` passes a committed non-UTF-8 regular `.md` index
  (it is a discovered, in-root, regular file), then `_read_index` opens it with
  `encoding="utf-8"` and no `errors=` (`navigation.py:532-533`), so decoding raises
  `UnicodeDecodeError` out of `detect()`. Confirmed empirically: a configured index containing
  `0xff 0xfe ... 0x80` raised `UnicodeDecodeError "'utf-8' codec can't decode byte 0xff in
  position 12: invalid start byte"` straight out of `detect`, not a `ConfigError`. A mid-read
  `OSError` (e.g. an I/O fault) propagates the same way. R3 names "unreadable" as a
  `ConfigError` readiness case, and a non-decodable index is functionally unreadable.
- Impact: fail-closed behaviour is preserved - no clean scan is produced, so this is **not** a
  BLOCK - and the message carries no path or absolute-path disclosure (`UnicodeDecodeError`
  omits the filename). But the Python/pytest API surface diverges from the documented `ConfigError`
  contract: a library caller catching only `ConfigError` sees an uncaught exception. The CLI still
  exits 2 because `cli.py:229` catches `ValueError` (the `UnicodeDecodeError` superclass) and
  `OSError`.
- Mitigation (followup, not blocking): wrap the `_read_index` open/read in `_require_readable_index`
  or `detect` so `UnicodeDecodeError`/`OSError` re-raise as the bounded, repr-escaped `ConfigError`
  ("configured navigation index could not be read: <echo>"), matching R3 and the existing stat
  failure path (`navigation.py:563-567`). Add a non-UTF-8 index regression test.

### [LOW] False positive: ordered-list marker (N!=1) interrupting a paragraph treated as navigation

- Vector / evidence: `_LIST_MARKER_RE` matches any `\d{1,9}[.)]` at 0-3 spaces of indent, but
  CommonMark lets an *ordered* list interrupt a paragraph only when it starts with `1`. A prose
  paragraph immediately followed by `3. See [guide](x.md)` is one paragraph with a prose link in
  CommonMark, yet DS112 classifies the line as a nav list item and flagged
  `navigation target does not exist: missing_gone.md` (confirmed empirically via `check_text`).
  This is the "prose link wrongly flagged as navigation" direction R1 warns against (CWE-693,
  low-risk form).
- Impact: a spurious `warning` on an ordinary prose link; advisory only (blocks only under
  `--strict`), and an escape/missing false positive here is bounded by the same lexical gates.
  Within R1's accepted "best-effort structural guard" imprecision, but currently undocumented.
- Mitigation (followup): require an ordered marker to be `1[.)]` (or a document position that may
  begin a list) before treating the line as navigation, and/or document this specific
  false-positive class in `docs/dev/markdown_dialect.md` alongside the existing indent/blockquote
  gaps. (Thematic-break-looking `- - -` lines are *not* a false positive: with a trailing link
  they are genuine bullet-list items in CommonMark.)

### [LOW] False negative: lazy-continuation navigation links are missed

- Vector / evidence: a nav link written on a lazy continuation line of a list item
  (`- intro\n  [cont](x.md)`) has no marker on its own physical line, so it fails
  `_LIST_MARKER_RE` and is dropped; DS112 returned `[]` where CommonMark makes the link a live
  list link (confirmed empirically). Blockquote-nested list links (`> - [x](y.md)`) are likewise
  dropped (the documented blockquote gap).
- Impact: a hidden missing/duplicate/escaping nav link silently passes - the lower-risk
  (false-clean) direction, consistent with the R1/R7 accepted gaps. The blockquote case is
  documented; the lazy-continuation case is not yet listed.
- Mitigation (followup): add lazy continuation to the enumerated list-membership gaps in the rule
  docstring and `docs/dev/markdown_dialect.md`; no code change required to keep the warning+opt-in
  posture safe.

### [LOW] TOCTOU between the readiness checks and the open/stat (inherited DS116 race)

- Vector / evidence: `_require_readable_index` runs `escapes_via_symlink` + `os.stat`/`S_ISREG`,
  then `detect` re-derives `canonical / index_path` and `_read_index` calls `Path.open`
  (`navigation.py:560-569,633`); the missing-destination probe likewise stats after its lexical
  gate. An index swapped from a regular file to a FIFO, or an in-root file symlinked out, between
  the check and the open/stat would be followed by the later call.
- Impact: only exploitable by concurrent filesystem mutation *during* a scan; a static CI/pre-commit
  checkout cannot trigger it. This is the same acknowledged TOCTOU recorded for DS116 (no cheap
  deterministic fix without a single atomic open the project avoids). No outside-root read occurs
  under the static threat model.
- Mitigation: acknowledged, not fixed; inherits the DS116 disposition.

### [INFO] Memory multiplier in `_masked_lines`

`_masked_lines` builds `list(text)` and re-joins it (`navigation.py:251-271`), a ~several-x
transient over the source size. It is bounded by `_MAX_INDEX_BYTES` (5 MB) per index and indexes
are processed sequentially, so peak memory is per-index and bounded - not a DoS, recorded for
awareness only.

### Verdict on `warning` + opt-in (post-implementation)

**The `warning` + opt-in posture stands and should not be escalated.** The implementation keeps the
DS116/DS113 floor: opt-in means zero default-on surface; the one non-advisory outcome (the R3
`ConfigError`, exit 2) is correct fail-closed behaviour; and the residual false positives/negatives
above are precisely the self-derived list-heuristic imprecision that justified `warning` (not
`error`) in the first place. Keeping them advisory is the right call; the MEDIUM is a contract-surface
gap, not a containment hole.

### Review verdict: PASS_WITH_FOLLOWUP

No CRITICAL; no BLOCK condition is met (no outside-root open/stat/realpath/symlink-follow, no FIFO/
directory/unbounded open, no false-clean on a missing/unreadable/out-of-root index, no raw-absolute-
path or unescaped-control-byte echo, no second resolver / unmasked-source regex / network / content
execution, and cost is linear). Followups to hand off - all non-blocking:

- `python-expert`: wrap `_read_index` decode/OS failures as the bounded R3 `ConfigError`
  (the MEDIUM); optionally tighten `_LIST_MARKER_RE` to the CommonMark `1`-interrupts-paragraph rule.
- `testing-expert`: regression tests for a non-UTF-8 configured index (assert `ConfigError`/exit 2),
  for the ordered-`N!=1` false positive, and for the lazy-continuation false negative.
- Docs: add the ordered-list-interrupts-paragraph and lazy-continuation differentials to the
  enumerated gaps in `docs/dev/markdown_dialect.md` and the rule docstring.
