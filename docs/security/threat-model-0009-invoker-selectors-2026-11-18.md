# Threat Model - Milestone 0009 Story 02.0 Invoker Selectors (`--include`/`--exclude`) - 2026-11-18

Pre-implementation security review for
[Story 02.0](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/README.md)
([Task 02](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/02-threat-review-invoker-selectors.md)):
normalisation and containment of invoker selectors (`scan --include/--exclude`,
`baseline --include/--exclude`, `docsentinel.scan(include=, exclude=)`) and the directory-aware
literal matching that config values also gain. No code for this story exists yet. The design under
review is Contract 3 (and Contracts 1, 2, 5 and 6 where they touch it) of
[ADR 0006](/docs/adr/0006-invoker-include-exclude-and-directory-selectors.md) (status Proposed),
the story README ("Selector grammar", "Security notes", "Edge cases") and the amended
[Task 03](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/03-selector-normalisation-and-matching.md),
[Task 04](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/04-cli-and-library-surface.md)
and [Task 05](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/05-tests.md) specs. Plan
contracts C1, C5 and C8 and decisions D8 to D10 are those of the
[Milestone 0009 plan](/docs/roadmap/0009-improvements/plan.md#shared-contracts-authoritative).

This review is a standing input for Tasks 03, 04 and 05; each briefing must link it. It reuses the
controls of
[threat-model-ds116-path-boundaries-2026-10-22.md](/docs/security/threat-model-ds116-path-boundaries-2026-10-22.md)
(ruling G4: lexical containment first, then `os.lstat()`/`os.readlink()` only on in-boundary
objects), of [threat-model-0009-at-references-2026-11-14.md](/docs/security/threat-model-0009-at-references-2026-11-14.md)
(the `contained_path()`/`_walk()` contract) and of
[threat-model-0009-user-settings-2026-11-17.md](/docs/security/threat-model-0009-user-settings-2026-11-17.md)
(C6: `include`/`exclude` are refused at user level). Mitigation numbers M1, M2, ... and amendment
numbers A1, A2, ... are local to this file.

Relevant weaknesses: CWE-22/CWE-23 (path traversal), CWE-59 (link following), CWE-180/CWE-176
(validate-before-canonicalise, Unicode encoding), CWE-158 (NUL), CWE-203 (observable discrepancy,
existence oracle), CWE-367 (TOCTOU), CWE-117 (log injection), CWE-209/CWE-532 (information exposure
in errors and logs), CWE-400/CWE-1333 (resource and regex DoS), CWE-20 (input validation),
CWE-693 (protection-mechanism failure); OWASP A01:2021 Broken Access Control, A03:2021 Injection,
A04:2021 Insecure Design. The Windows "best-fit" character conversion class (WorstFit, DEVCORE
2025; for example CVE-2024-4577 in PHP and CVE-2024-47611 in XZ Utils) is relevant to the
look-alike separator ruling; verified by search, see Sources.

Adversarial example values that would escape the repository are written only inside fenced blocks
or as plain prose, so this page creates no live code-span traversal for the self-scan.

## Assets & trust boundaries

Assets:

- **Containment of the scan root.** No selector may cause any filesystem call (stat, lstat,
  readlink, realpath, open, listdir) on a path outside the canonical scan root.
- **The gate signal** (exit 0/1/2, "never a silent clean result"). A selector that silently
  narrows a scan to nothing hides every finding.
- **Stderr, the per-run log file and CI logs.** Echoed values must not inject terminal escapes,
  newlines, bidi controls or GitHub workflow commands, and must stay bounded.
- **Availability** of `scan`/`baseline` (bounded normalisation and matching cost).

Actors and input channels (Task 02 Step 1):

| ID | Actor / channel | Trust | Notes |
|---|---|---|---|
| I1 | Person at a terminal (argv) | Trusted invoker | Can already read anything they can name; containment protects against mistakes and against copy-pasted commands. |
| I2 | Repository pre-commit configuration (`args:` of a hook entry) | **Repository-controlled** | The packaged hooks set `pass_filenames: false`, so only `args:` reach argv. Running pre-commit on a repository already runs repository-chosen hooks; selectors must add no capability beyond the repository's own config file (C8). |
| I3 | CI workflow (`run:` step argv) | Workflow author; repository-controlled when the workflow file comes from the PR (`pull_request`), never to be fed PR data under `pull_request_target` | Same as I2 for the PR case. |
| I4 | Library caller (`scan(include=, exclude=)`) | Trusted caller, but may forward untrusted strings (a web form, a bot) | Can pass NUL, non-`str` items, generators, huge lists, values longer than any argv. |
| I5 | Scanned repository content (files, directories, symlinks) | Untrusted | Controls every in-root symlink the normaliser walks. |
| I6 | Environment (`PWD`) | Invoker | `_origin_spellings()` reads it today for the extension boundary. |

Trust boundaries crossed:

1. argv / keyword values to `normalize_invoker_selectors()` (shape, characters, separators).
2. Lexical value to the filesystem (`contained_path()` walk, one `os.lstat()`), for literals only.
3. Normalised strings to `discover_with_stats()` (pure string matching over `os.walk` output).
4. Values to `ConfigError` text, `Scan failed:` on stderr, `WARNING`/`DEBUG` log records.

Structural facts confirmed in code:

- `discover_with_skips()` (`/src/docsentinel/discovery.py`) only matches strings produced by
  `os.walk(root, topdown=True)`; it prunes symlinked directories and skips symlinked and
  non-regular files. A selector can therefore never make discovery **read** outside the root,
  whatever the normaliser does; the normaliser's own filesystem calls are the only new surface.
- `engine.scan()` canonicalises the root with `Path(root).resolve()`; the CLI with
  `_resolve_root()` (`/src/docsentinel/cli.py`). Both give a canonical root suitable for
  `contained_path()`.
- `cli.py` prints `Scan failed: {neutralize_text(str(exc))}`, which neutralises but does **not**
  bound length; the bound must come from the exception text itself.
- Config `include`/`exclude` (`_build_config` in `/src/docsentinel/config.py`) are bounded neither
  in count nor in length today.

## Evidence (probes in a scratch directory, Python 3.12.13, macOS)

| Probe | Result |
|---|---|
| UTF-8 of U+2215, U+FF0F, U+2044, U+29F8, U+FF3C, U+FE68, U+00A5 | No `0x2F` or `0x5C` byte in any of them. |
| `posixpath.normpath`, `ntpath.normpath`, `PurePosixPath`/`PureWindowsPath` parts | All seven treated as ordinary name characters (one component). |
| `fnmatchcase("docs/x.md", "docs" + ch + "x.md")` | False for all; a look-alike never matches a real `/`. |
| `unicodedata.normalize("NFKC", ...)` | **U+FF0F becomes `/`; U+FF3C and U+FE68 become `\`.** NFC leaves all unchanged. |
| A file named with U+2215 or U+FF0F created and `lstat`-ed | One directory entry; no `a/b.md` path exists. |
| `posixpath.normpath` of a value with a leading double slash | Leading `//` is **kept** (POSIX implementation-defined), so a plain prefix comparison refuses it, but only by accident. |
| `posixpath.normpath` of an absolute value holding a parent step | The parent step is **collapsed lexically** (`/repo/docs/../x` becomes `/repo/x`), unlike the relative rule that refuses it. |
| `ntpath.isabs("/x")` on 3.12 | True; it changes in 3.13 (a rooted path without a drive is no longer absolute). Detection must not depend on `isabs` for Windows forms. |
| `os.lstat` of a value holding NUL | `ValueError` (not `OSError`): it would bypass an `OSError`-only handler in the library. |
| `contained_path()` traced (`os.lstat`/`os.readlink` wrapped) for an in-root dir symlink, an in-root absolute dir symlink, a relative and an absolute escape symlink, a final file symlink, a self loop, a missing component, a path below a file | **Zero calls outside the root in every case.** Escape and loop return `None` (loop after 129 calls, bounded by the 64-hop limit); every in-root symlink expansion returns a path that differs from the lexical one; plain paths return the lexical path. |
| `fnmatchcase` cost, 1,024-character patterns | `fnmatch.translate` uses atomic groups (no catastrophic backtracking). Worst match about 0.1 ms per (pattern, 4,096-char path); worst compile 70 ms (1,024 unclosed `[`), cached per pattern (LRU 32,768). 256 pathological patterns over 200 255-character paths: 2.9 s (57 us per pair); simple patterns 1.3 us per pair. |
| Current engine with config `exclude = ["*"]` | 0 documents, exit **0**, no warning: a silent clean result reachable today through config. |
| Current engine with a non-Markdown file included by config (`include = [".env"]`) and secret text in it | The file is inventoried; no secret text reaches the JSON report (detectors skip non-`.md`). |

## Findings

### [HIGH] T1 Escaping the scan root: parent steps, absolute values, symlinked components

- Vector / evidence: Contract 3 steps 4, 5 and 7. A value such as the fenced examples below must
  never be accepted or touch the filesystem:

  ```text
  ../other            docs/../../x          ..
  /etc/passwd         /repo/docs/../../x    /repo-other/x   (root /repo)
  docs/outlink/x.md   (docs/outlink -> ../../outside, or -> /outside)
  ~/x                 $HOME/x
  ```

  Step 4 runs `os.path.normpath()` **before** step 5's parent-step refusal, so an absolute value
  with a parent step is collapsed lexically and accepted (`/repo/docs/../x` becomes `x`), while the
  relative spelling `docs/../x` is refused. The collapse can differ from what the kernel would do
  when `docs` is an in-root symlink (CWE-180, validate after canonicalise). It never leaves the
  root (the result is still contained and walked), but it breaks the one-rule property and is the
  same class of divergence DS116 documents as a residual. The ADR also does not say that the
  "equal or lie under" test must be separator-aware: a plain `str.startswith` accepts
  `/repo-other/x` for root `/repo`.
- Impact: without the mitigations, a value names an object outside the root and the normaliser
  lstats or walks it (existence oracle, see T2) or discovery reports a confusing selection.
  Discovery itself cannot read outside the root (it never follows symlinks), so the residual
  impact is information disclosure through the normaliser, not content access.
- Mitigation:
  - **M1** Refuse a `..` component in the **raw** value (after the backslash rule, before any
    `normpath`), for relative and absolute values alike. `normpath` may then only drop `.`,
    repeated `/` and a trailing `/` (amendment A1).
  - **M2** Absolute containment is separator-aware: reuse the `_within()` semantics of
    `/src/docsentinel/detectors/path_boundaries.py` (or `link_root.py`), never a bare
    `startswith` (A1).
  - **M3** Relative literals are joined onto the **canonical** root and checked with
    `contained_path()`; `None` (escape or hop limit) exits `2`. The CLI's early call passes the
    resolved directory from `_resolve_root()`, never the spelled root (A4).
  - **M4** No `os.path.expanduser`, `os.path.expandvars`, `glob.glob`, `Path.resolve`,
    `os.path.realpath` or `os.path.abspath` is applied to a **selector value** (`abspath` would
    join a relative value onto the current directory, which is not the base). `~/x` and `$HOME/x`
    are plain relative literals that name nothing (exit `2` for an include) (A1).
  - **M5** Globs get no filesystem access and, because discovery only matches strings produced by
    walking the root, cannot select anything outside it; a glob holding a `..` component is still
    refused (M1) for a clear message. A bracket form such as `[.][.]` is harmless: no walked
    relative path contains a parent step.
- Tests: `test_dotdot_component_refused_relative`, `test_dotdot_in_absolute_value_refused_before_normpath`,
  `test_absolute_sibling_prefix_refused`, `test_absolute_inside_root_made_relative`,
  `test_absolute_equal_root_is_dot`, `test_absolute_glob_refused`,
  `test_tilde_and_env_vars_not_expanded`, `test_lstat_only_inside_root_for_escaping_relative_symlink`,
  `test_lstat_only_inside_root_for_escaping_absolute_symlink`,
  `test_symlink_escape_refused_for_include_and_exclude`, `test_cli_early_validation_uses_canonical_root`.

### [HIGH] T2 Existence oracle outside the root (O2: realpath of the value's parent)

- Vector / evidence: the original Task 03 step 4 says "the parent resolved with
  `os.path.realpath()`". `realpath()` lstats and readlinks every component of a value **before**
  containment is known, so `--include /some/outside/dir/x` touches `/some/outside/dir`. Error text,
  exit code or timing then differ by existence (CWE-203). On macOS, `realpath` of a path under the
  autofs mount `/net/<host>/...` triggers an automount attempt to an attacker-named host (an
  outbound network request and a long hang); `/dev/fd/...`, FUSE and NFS paths have similar side
  effects. A pre-commit `args:` value (I2) is repository-controlled, so this is a
  repository-to-invoker oracle and a network trigger.
- Impact: disclosure of existence and type of files outside the checkout to whoever reads the CI
  log; an automount/network side effect; a hang.
- Mitigation: **ruling on O2, below**. **M6** Absolute values are made relative purely lexically
  against the canonical root and validated root spellings (A1, A4); a value outside every spelling
  is refused with zero filesystem calls, with one message that does not depend on whether the
  outside path exists (`--include value <v> is outside the scan root; values are relative to the
  scan root`). **M7** The only filesystem calls on a selector are those of `contained_path()` on
  the joined in-root path plus one `os.lstat()` of its result.
- Tests: `test_no_filesystem_call_for_absolute_outside_value`,
  `test_no_realpath_or_resolve_of_selector_value`,
  `test_cli_absolute_outside_root_message_independent_of_existence`.

### [MEDIUM] T3 Root spellings: `$PWD`, lexical spellings that name another directory, CLI and engine disagreeing

- Vector / evidence: Contract 3 lets absolute values match `root_spellings`, "the root as the
  caller spelled it, made absolute"; Contract 5 step 4 passes `root_spellings=...` without saying
  how the engine gets them. The only existing helper, `_origin_spellings()` in `cli.py`, adds
  `$PWD`-based logical spellings and was built for a **refusal** boundary (extension origins), where
  "extra anchors only widen the boundary" is safe. For selectors the spellings are an
  **acceptance** boundary. `os.path.abspath(spelled)` and the `$PWD` join collapse a parent step
  lexically, so a spelled root such as `link/..` (or `..` with `$PWD` through a symlink) names a
  different directory from the canonical root that `_resolve_root()` computed with kernel
  semantics. An absolute value under that wrong spelling is then relativised against the wrong
  directory and re-applied to the real root. The value stays contained (M3), so this is not an
  escape, but it selects a path the invoker did not name. Second, the CLI calls the normaliser
  early (Contract 6) and the engine calls it again with the raw lists: if their spellings differ
  (the engine cannot see `$PWD` or the CLI's spelling), a value accepted early is refused after
  `scan started` was logged, breaking the "Scan failed: is the first stderr line" rule. Third, when
  two spellings overlap (a spelling under another, through an in-root symlink to the root), the
  matching prefix is ambiguous.
- Impact: wrong-but-contained selection; inconsistent CLI versus library behaviour.
- Mitigation: **M8** (A4) one shared helper computes the selector spellings for both the CLI early
  call and the engine: the canonical root, plus `os.path.abspath(spelled_root)` **only when**
  `os.path.samefile(spelling, canonical_root)` holds (a stat of the invoker's own root spelling,
  never of a selector value). No `$PWD`; `_origin_spellings()` is not reused. **M9** the longest
  matching spelling wins, deterministically.
- Tests: `test_root_spelling_requires_samefile`, `test_cli_and_engine_use_same_root_spellings`,
  `test_absolute_longest_root_spelling_wins`, `test_pwd_not_used_for_selector_spellings`.

### [MEDIUM] T4 Windows drive, UNC, device and rooted-backslash forms (on POSIX and on Windows)

- Vector / evidence: Contract 3 step 3 refuses a backslash on POSIX and "a drive-letter prefix or
  a UNC form" unless step 4 accepts it, but does not say how they are detected. On POSIX
  `posixpath.normpath` keeps a leading double slash, `C:/x` and `C:x` are not absolute, and
  `ntpath.isabs` differs between 3.12 and 3.13. Forms that need an explicit rule:

  ```text
  C:/x   C:x   c:\x          (drive, drive-relative)
  \\srv\share\x   //srv/share/x       (UNC)
  \\?\C:\x   //?/C:/x   \\.\pipe\x    (Win32 device / verbatim namespace)
  \docs                               (rooted, no drive; Windows only)
  docs\a.md:stream   docs\a.md.   "docs\a.md "   (ADS, trailing dot/space; Windows only)
  ```

- Impact: on POSIX all of these fail closed today only by accident of other checks; on Windows a
  device or verbatim path bypasses `normpath` semantics and a rooted path names the current
  drive's root. CI runs on Linux only, so Windows behaviour is untested in CI.
- Mitigation: **M10** (A3) detect drive, UNC and device forms **lexically on every platform**,
  before the backslash conversion: refuse when `ntpath.splitdrive(value)[0]` is non-empty or the
  value starts with two separators (either slash), except that on the backslash-separator
  platform an absolute `X:\...` under a validated root spelling is accepted by step 4. **M11** On
  the backslash-separator platform additionally refuse a rooted value without a drive, a `:` after
  the drive (alternate data streams) and a component ending in `.` or a space. These rules are
  pure and testable on POSIX through `backslash_is_separator=True`. A legitimate POSIX name such as
  `a:b.md` is therefore refused as a selector (fail closed; select it with a glob such as
  `a[:]b.md`), consistent with DS116's treatment.
- Tests: `test_windows_drive_forms_refused_on_posix`, `test_unc_and_device_forms_refused`,
  `test_leading_double_slash_refused_on_posix`, `test_backslash_refused_on_posix`,
  `test_backslash_is_separator_when_injected`,
  `test_rooted_backslash_refused_when_backslash_is_separator`,
  `test_windows_ads_and_trailing_dot_refused_when_backslash_is_separator`.

### [LOW] T5 Unicode look-alike separators (U+2215, U+FF0F and relatives)

- Vector / evidence: see Evidence. No step of the planned pipeline (`neutralize()` comparison,
  backslash rule, `normpath`, `PurePath`, `contained_path()`'s `os.sep` split, the kernel,
  `fnmatchcase()`) turns them into a separator. The only transformations that do are Unicode
  compatibility normalisation (NFKC/NFKD: U+FF0F to `/`, U+FF3C and U+FE68 to `\`) and Windows
  best-fit conversion of a wide string to an ANSI code page (WorstFit; the published path-traversal
  character is U+FF3C). CPython's `os` functions on Windows call the wide (`W`) APIs for `str`
  paths, so no best-fit conversion happens in-process. macOS file systems fold only canonical
  equivalence (NFD family), never compatibility forms.
- Impact: none today; a future "helpful" normalisation (NFKC, `casefold`, bytes paths on Windows)
  would create a traversal.
- Mitigation: **ruling below**. **M12** (A2) the selector pipeline applies **no** Unicode
  normalisation of any form (no `unicodedata.normalize`, no `casefold`/`lower`), and never
  converts a selector to bytes for a filesystem call on Windows. Look-alikes stay ordinary name
  characters.
- Tests: `test_lookalike_separators_are_name_characters` (parametrised over U+2215, U+FF0F,
  U+2044, U+29F8, U+FF3C, U+FE68), `test_no_unicode_normalisation_applied`,
  `test_lookalike_separator_glob_does_not_match_slash`,
  `test_lookalike_named_file_selected_only_by_exact_name`.

### [LOW] T6 NUL, controls and format characters

- Vector / evidence: argv cannot carry NUL, but a library caller can (I4); `os.lstat` raises
  `ValueError`, not `OSError`, on NUL. On POSIX, undecodable argv bytes arrive as lone surrogates
  (`surrogateescape`). Contract 3 step 2 refuses everything `neutralize()` rewrites, which already
  covers C0/C1/DEL, CR/LF, bidi, zero-width, U+2028/U+2029 and lone surrogates. It also rewrites
  the ASCII sequence `##[` (GitHub command marker), so a glob such as `##[ab].md` is refused too,
  under a message that would wrongly say "control character".
- Impact: none if step 2 runs before every filesystem call; a misleading message for `##[`.
- Mitigation: **M13** step 2 runs before any filesystem call and before any message echoes the
  value. **M14** (A2) refusing `##[` is accepted (fail closed; such names are vanishingly rare and
  a glob such as `#[#][[]...` still selects them), but the message says "contains a control,
  format or unsupported character sequence". Non-UTF-8 file names (lone surrogates) cannot be
  selected by a literal; document it.
- Tests: `test_nul_and_controls_refused` (NUL, ESC, CR, LF, DEL, U+0085, U+202E, U+200B, U+2028,
  U+DC80), `test_no_filesystem_call_before_character_checks`,
  `test_github_command_marker_refused_with_clear_message`.

### [MEDIUM] T7 In-root symlinked components (O6) and non-regular targets

- Vector / evidence: Contract 3 steps 7 and 8. Discovery prunes symlinked directories and skips
  symlinked files, so a literal include reached through any in-root symlink names nothing that
  discovery will ever admit; accepting it would produce a zero-hit `WARNING` and, if it is the only
  include, an empty clean scan. Probes show that `contained_path()` returns the lexical path
  exactly when no symlink was followed: with parent steps refused (M1), a followed symlink can only
  reproduce the same path by visiting the same symlink again, which runs into the 64-hop limit
  and returns `None`. A literal include that exists but is a FIFO, socket or device is also
  accepted by an existence-only `lstat`, and then admits nothing (discovery skips non-regular
  files); `os.lstat` never opens it, so there is no blocking read.
- Impact: a silent empty or narrowed scan; no containment impact (no call leaves the root).
- Mitigation: **ruling on O6, below**. **M15** (A5) the "symlinked" signal is
  `contained != canonical_root.joinpath(*L.split("/"))` compared as `os.fspath` strings. **M16**
  (A5) a literal include must be `S_ISREG` or `S_ISDIR` per the one `os.lstat()`; anything else
  exits `2` (`not a regular file or directory`). **M17** (A5) an `OSError` from the walk or the
  `lstat` (for example `EACCES`) becomes a `ConfigError` echoing the bounded relative value and the
  `strerror` only, never the absolute path (no home-path PII in CI logs, consistent library
  exception type).
- Tests: `test_include_through_inroot_symlinked_dir_refused`,
  `test_include_final_component_symlink_refused`,
  `test_exclude_through_inroot_symlink_listed_unmatched`, `test_symlink_loop_refused_bounded`,
  `test_literal_include_non_regular_refused`, `test_lstat_oserror_becomes_config_error_with_relative_echo`.

### [MEDIUM] T8 Silent clean result through selection (challenges O8)

- Vector / evidence: the story refuses `--exclude .` because "excluding everything is refused",
  but `--exclude '*'`, `'**'`, `'?*'` or `--exclude docs` on a docs-only repository do the same:
  the current engine returns 0 documents with exit `0` and no warning (probe). A literal include
  can also pass existence but admit nothing on a case-insensitive or normalisation-insensitive file
  system (`DOCS/user` on default APFS or NTFS, an NFC value for an NFD-stored name): `lstat`
  succeeds, the case-sensitive string match fails, and only a zero-hit `WARNING` appears. O8 keeps
  "an existing directory with no Markdown file" at `WARNING` even when the inventory is empty.
- Impact: a pre-commit or CI gate passes with nothing scanned (CWE-693). A repository can already
  do this through its config file, so it is not a new capability for I2/I3 (see T9); it is a new,
  easy footgun for I1 and I4.
- Mitigation: **M18** (A6, required) when an invoker `include` or `exclude` was given and the
  final inventory is empty, the engine logs one `WARNING` `the selection admitted no document`
  (never echoing values). **Owner ruling requested (R1):** make that case exit `2` instead (the
  recommended choice; it is what S8 argues for a missing include). Matching stays case-sensitive
  and no normalisation is added (M12); the case and normalisation caveat is documented in Task 06.
- Tests: `test_exclude_star_empty_inventory_exits_2` (R1 ruled exit 2),
  `test_case_mismatched_literal_include_zero_hit_warning` (skipped unless the temp file system is
  case-insensitive).

### [LOW] T9 Hiding documents through repository-controlled pre-commit `args:` (accepted)

- Vector / evidence: a hook entry in the repository's own pre-commit configuration can pass
  `--exclude docs/security` or `--include README.md`.
- Impact: findings disappear from that lane.
- Mitigation: **accepted, not a new capability.** The same repository controls `exclude` and
  `include` in its config file, with no count or length bound at all, and the packaged hooks set
  `pass_filenames: false`. Selectors are not a trust gate (unlike `--link-root`); C6 already
  stops a user-settings file from narrowing other repositories. The literal include's in-root
  `lstat` gives the repository an existence oracle **inside the root only**, which DS101/DS113
  already give it through links. A literal include of a non-Markdown in-root file (for example a
  secrets file in the checkout) is inventoried, read and counted, but its content reaches no
  report (probe; detectors skip non-`.md`), exactly as a config include of it does today. The
  selection is visible in the `INFO` selection line on stderr.
- Tests: `test_config_literals_never_touch_filesystem` (config values gain only string semantics).

### [LOW] T10 Cost: 256 values, 1,024 characters, `fnmatchcase()` per path

- Vector / evidence: per file, every include pattern is now tested (hit counts forbid
  short-circuiting), and every exclude pattern is tested against the path and each directory name.
  Measured worst case about 0.1 ms per (pattern, path) pair and 70 ms compile per pathological
  pattern; `fnmatch.translate` uses atomic groups, so there is no exponential backtracking
  (CWE-1333 not reachable). 512 pathological invoker patterns (256 per flag) over a 10,000-file
  tree of depth 5 is roughly minutes of CPU, self-inflicted. The normaliser's walk per literal is
  bounded by 64 hops times the components of each target. The config lists, which a repository
  controls, are unbounded today, so the invoker bound adds no new DoS.
- Mitigation: **M19** (A8) shape checks run in this order: type (a `str`/`bytes` or a
  non-`Sequence` such as a generator is refused), `len()` at most 256 **before** iterating, then
  each item's type and length at most 1,024 **before** any character check or echo, so a
  multi-megabyte library value is never scanned or neutralised. **M20** literal patterns are
  matched with string comparison (Contract 2), never compiled. Accepted residual: pathological
  globs within the bounds. Follow-up F1 (optional): a total-character budget across all selector
  values, as `telemetry_domains` has.
- Tests: `test_shape_bounds`, `test_oversized_list_refused_before_item_processing`,
  `test_pathological_globs_complete` (256 values of 1,024 characters over a small tree, generous
  time bound).

### [LOW] T11 Echo of values in errors, stderr and logs

- Vector / evidence: `Scan failed:` applies `neutralize_text` without a length bound; library
  callers see `ConfigError` text raw and may log it themselves. Contract 5 echoes patterns in
  `DEBUG`, in the unmatched-exclude `WARNING` and in the zero-hit `WARNING`.
- Impact: terminal-escape, newline or `::`/`##[` workflow-command injection into stderr and CI
  logs (CWE-117), and unbounded log lines.
- Mitigation: **M21** (A7) every `ConfigError` raised by the normaliser echoes a value only as
  `log.safe(value, 200)` (neutralised and capped), so the text is already safe for library callers
  and the CLI's unbounded `neutralize_text` is a second, idempotent pass. Shape errors echo no
  value (counts and limits only). **M22** every log record echoes patterns only through `safe()`;
  the `INFO` selection line and the S9 single-file `WARNING` carry counts only. Because step 2
  refuses every control character, no accepted value can start a new stderr line, so a GitHub
  workflow command cannot be forged through a later `WARNING`.
- Tests: `test_error_message_bounded_and_neutralised`,
  `test_error_message_says_relative_to_scan_root`,
  `test_cli_refused_selector_first_stderr_line_is_scan_failed`,
  `test_cli_refused_selector_echo_neutralised`, `test_cli_warning_echo_bounded`,
  `test_selection_info_line_has_counts_only`.

### [LOW] T12 Repudiation: the selection is not recorded in the report

- Vector / evidence: ADR 0006 consequences: the selection is not in `ScanResult` or any report.
  An uploaded CI report artifact from a narrowed run looks like a full run.
- Mitigation: accepted for this story (the `INFO` selection line is in the CI log and the per-run
  log file). Follow-up F2: carry the selection counts (not values) in the report's optional run
  metadata (`report_include_run_meta`) in a later story.

### [LOW] T13 TOCTOU between normalisation and discovery, and between the two normalisations

- Vector / evidence: a symlink swapped in after the normaliser's walk, or a file deleted between
  the CLI's early call and the engine's call.
- Impact: none for containment: the normaliser returns strings only, and discovery independently
  never follows symlinks. A late deletion gives an exit `2` after `scan started` (cosmetic).
- Mitigation: accepted (CWE-367 residual, same as DS101/DS113/DS124).

### Not applicable / no finding

- No shell, SQL or AI backend is reached by a selector; no prompt injection surface.
- `--include`/`--exclude` do not affect `link_root`, the DS112 index, the DS115 mapping or the
  template directory resolution (all keep their own gates); a DS112 index removed by `--exclude`
  keeps today's fail-closed `ConfigError`.
- The deep-profile confirmation gate and `DOCSENTINEL_ALLOW_PYTHON_EXTENSIONS` are untouched.
- argparse: no `fromfile_prefix_chars` is set, so `--include @file` is a literal, never a file
  read. Adding `--include`/`--exclude` makes the abbreviations `--i` and `--ex` ambiguous (today
  they resolve to `--i-understand-deep-is-heuristic` and `--extension`); argparse then exits `2`,
  which fails closed. Task 06 should note it.

## Rulings on the open points

| Point | Ruling | Reason |
|---|---|---|
| **O2** | **Confirmed, lexical only, with amendments A1 and A4.** Task 03 step 4's "parent resolved with `os.path.realpath()`" is **struck**. An absolute selector is never `realpath`-ed, `stat`-ed, `abspath`-ed or `resolve`-d. Parent steps are refused on the raw value before `normpath`; containment against a spelling is separator-aware; the longest matching spelling wins; spellings are the canonical root plus `abspath(spelled root)` only when `samefile` with it, computed by one helper shared by the CLI and the engine, never from `$PWD`. | `realpath` of an outside parent is an existence oracle (CWE-203) and, under autofs/NFS/FUSE, a network or hang trigger; lexical handling is sufficient because discovery only matches walked in-root strings. |
| **O6** | **Confirmed.** A literal include reached through an in-root symlinked component, including a symlink as the final component, exits `2` (`symlinked paths are not inventoried`); the signal is "the contained path differs from the lexical join" (sound and complete once parent steps are refused). A literal exclude reached that way is kept and listed in `unmatched_exclude` (single-component excludes excepted, O3). A literal (include or exclude) whose walk returns `None` (escape or hop limit) exits `2`. Additionally, a literal include must be a regular file or directory (A5). | Discovery never walks through a symlink, so such an include can only name nothing (S8); the decision rests only on `lstat`/`readlink` of in-root objects, so it discloses nothing outside the root. |
| **U+2215 / U+FF0F** | **Confirmed as ordinary name characters; no refusal required**, on condition of A2: no Unicode normalisation (NFC/NFD/NFKC/NFKD), case folding or bytes-path conversion anywhere in the selector pipeline. The same holds for U+2044, U+29F8, U+FF3C and U+FE68. | No UTF-8 byte of these is `0x2F`/`0x5C`; `normpath`, `PurePath`, `contained_path()`, the kernel and `fnmatchcase()` treat them as name characters (probed). Only NFKC-style normalisation or Windows best-fit (not used by CPython's wide-API `os` calls) would turn them into separators. |
| O3 | Not challenged. | No security impact; the name rule still prunes every `build` directory. |
| O4 | Endorsed. | Fail closed on a caller bug whatever the target. |
| O5 | Endorsed, extended by A8 (a generator or other non-`Sequence` is refused too; length checked before iterating). | CWE-20; prevents one value becoming several patterns and unbounded iteration. |
| O7 | Not challenged. | `.` can only widen to the default include; configured excludes still apply. |
| O8 | **Challenged (partially).** The per-directory zero-hit `WARNING` may stay, but an empty final inventory under invoker selection must at least warn (A6, required) and should exit `2` (owner ruling R1). | "Never a silent clean result"; `--exclude '*'` reaches the same state `--exclude .` is refused for. |

## Required spec amendments (before Task 03 starts, unless noted)

| ID | Severity | Amend | Change |
|---|---|---|---|
| A1 | HIGH | ADR 0006 Contract 3 steps 4 and 5; Task 03 step 4 | O2 as ruled: strike `realpath`; refuse a `..` component on the raw value (after the backslash rule, before `normpath`) for relative and absolute values; separator-aware `_within` containment against spellings; no `expanduser`/`expandvars`/`abspath`/`resolve` of a value; one existence-independent "outside the scan root" message (M1, M2, M4, M6). |
| A2 | LOW | Contract 3 step 2; Task 03 step 4 | No Unicode normalisation or case folding of selectors, no bytes paths on Windows (M12). `##[` is refused with the wording "control, format or unsupported character sequence" (M14). |
| A3 | MEDIUM | Contract 3 step 3 | Drive/UNC/device detection on every platform via `ntpath.splitdrive` and a leading double separator, before the backslash conversion; on the backslash-separator platform also refuse a rooted value without a drive, a `:` after the drive, and a component ending in `.` or a space (M10, M11). |
| A4 | MEDIUM | Contract 3 (`root_spellings`), Contract 5 step 4, Contract 6; Task 04 step 1-2 | One shared spellings helper used by the CLI early call and the engine: canonical root plus `abspath(spelled)` when `samefile`; no `$PWD`; longest spelling wins; the CLI early call passes the canonical directory (M3, M8, M9). Before Task 04 for the CLI part. |
| A5 | MEDIUM | Contract 3 steps 7 and 8; Task 03 step 4 | O6 as ruled with the exact signal (M15); a literal include must be `S_ISREG` or `S_ISDIR` (M16); an `OSError` from the walk or `lstat` becomes a `ConfigError` with the bounded relative value and `strerror` only (M17). This replaces "an `OSError` from the walk propagates". |
| A6 | MEDIUM | Contract 5 step 6; Task 04 step 1 | Empty final inventory with invoker selectors: one `WARNING` `the selection admitted no document` (or exit `2` if the owner rules R1) (M18). Before Task 04. |
| A7 | LOW | Contract 3 (failure text), Contract 5 step 5 | Every echoed value is `safe(value, 200)`; shape errors echo no value; `INFO` and S9 lines carry counts only (M21, M22). |
| A8 | LOW | Contract 1 table, Contract 3 step 1 | Shape order: type (bare `str`/`bytes`, non-`Sequence` refused), `len` <= 256 before iterating, item type and length <= 1,024 before any other processing (M19). |

## Owner ruling requested

> **Ruled 2026-11-19 (owner): R1 = exit `2`.** An empty final inventory under invoker selection is a `ConfigError` (exit `2`); config-only selection keeps exit `0`. A6 and M18 therefore mean exit `2`, not a `WARNING`, and every "if the owner rules R1" below now reads as ruled. ADR 0006 Contract 5 records it.

- **R1 (MEDIUM, T8).** Should an empty final inventory under invoker selection exit `2`
  (recommended) or only warn (A6 minimum)? Either choice passes this review; the warning is the
  floor.

## Mitigation-to-test map (Task 05 adopts these names verbatim)

| Mitigation | Test (file) |
|---|---|
| M1 | `test_dotdot_component_refused_relative`, `test_dotdot_in_absolute_value_refused_before_normpath` (unit `test_invoker_selectors.py`) |
| M2 | `test_absolute_sibling_prefix_refused`, `test_absolute_inside_root_made_relative`, `test_absolute_equal_root_is_dot`, `test_absolute_glob_refused` (unit) |
| M3 | `test_lstat_only_inside_root_for_escaping_relative_symlink`, `test_lstat_only_inside_root_for_escaping_absolute_symlink`, `test_symlink_escape_refused_for_include_and_exclude` (mock `test_invoker_selectors_containment.py`); `test_cli_early_validation_uses_canonical_root` (integration `test_cli_include_exclude_ds101.py`) |
| M4 | `test_tilde_and_env_vars_not_expanded` (unit) |
| M5 | `test_no_filesystem_call_for_glob_values` (mock) |
| M6, M7 | `test_no_filesystem_call_for_absolute_outside_value`, `test_no_realpath_or_resolve_of_selector_value` (mock); `test_cli_absolute_outside_root_message_independent_of_existence` (integration) |
| M8, M9 | `test_root_spelling_requires_samefile`, `test_pwd_not_used_for_selector_spellings` (mock); `test_absolute_longest_root_spelling_wins` (unit); `test_cli_and_engine_use_same_root_spellings` (integration) |
| M10, M11 | `test_windows_drive_forms_refused_on_posix`, `test_unc_and_device_forms_refused`, `test_leading_double_slash_refused_on_posix`, `test_backslash_refused_on_posix`, `test_backslash_is_separator_when_injected`, `test_rooted_backslash_refused_when_backslash_is_separator`, `test_windows_ads_and_trailing_dot_refused_when_backslash_is_separator` (unit) |
| M12 | `test_lookalike_separators_are_name_characters`, `test_no_unicode_normalisation_applied` (unit); `test_lookalike_separator_glob_does_not_match_slash` (unit `test_selector_matching.py`); `test_lookalike_named_file_selected_only_by_exact_name` (integration `test_discovery_selectors.py`) |
| M13 | `test_nul_and_controls_refused` (unit); `test_no_filesystem_call_before_character_checks` (mock) |
| M14 | `test_github_command_marker_refused_with_clear_message` (unit) |
| M15 | `test_include_through_inroot_symlinked_dir_refused`, `test_include_final_component_symlink_refused`, `test_exclude_through_inroot_symlink_listed_unmatched`, `test_symlink_loop_refused_bounded` (mock) |
| M16 | `test_literal_include_non_regular_refused` (mock, `lstat` reporting a FIFO) |
| M17 | `test_lstat_oserror_becomes_config_error_with_relative_echo` (mock) |
| M18 | `test_exclude_star_empty_inventory_exits_2`, `test_case_mismatched_literal_include_zero_hit_warning` (integration) |
| M19 | `test_shape_bounds`, `test_oversized_list_refused_before_item_processing` (unit) |
| M20 | `test_pathological_globs_complete` (integration) |
| M21 | `test_error_message_bounded_and_neutralised`, `test_error_message_says_relative_to_scan_root` (unit); `test_cli_refused_selector_first_stderr_line_is_scan_failed`, `test_cli_refused_selector_echo_neutralised` (integration) |
| M22 | `test_cli_warning_echo_bounded`, `test_selection_info_line_has_counts_only` (integration) |
| T9 (accepted) | `test_config_literals_never_touch_filesystem` (mock) |

Mock tests record `os.lstat`, `os.stat`, `os.readlink`, `os.path.realpath`, `os.path.abspath`
(on selector values), `os.scandir`, `os.listdir` and `Path.resolve`, and assert every recorded
path is the canonical root or lies under it (separator-aware).

## Mandatory mitigation ownership

| Mitigation | Implements | Tests |
|---|---|---|
| M1, M2, M4-M7, M10-M17, M19-M21 | Task 03 | Task 05 |
| M3 (CLI part), M8, M9, M18, M22 | Task 04 | Task 05 |
| A1-A3, A5, A7, A8 | spec owner (ADR 0006 Contract 3 and Task 03), before Task 03 | - |
| A4, A6 | spec owner (ADR 0006 Contracts 5 and 6 and Task 04), before Task 04 | - |
| R1 | owner (ruled 2026-11-19: exit 2) | Task 04 |
| F1 (selector character budget), F2 (selection in run metadata) | product backlog | - |

## Verdict: PASS_WITH_FOLLOWUP

There is no CRITICAL finding. The design is sound at its core: discovery only matches strings from
a walk that never follows symlinks, so no selector can make DocSentinel read outside the scan
root, and `contained_path()` was shown to make zero calls outside the root for every symlink shape.
The two HIGH findings (T1, T2) are design-mitigated once A1 replaces Task 03's `realpath` step with
the lexical rule. Follow-ups: A1, A2, A3, A5, A7 and A8 must be folded into ADR 0006 Contract 3 and
Task 03 (or quoted verbatim in the Task 03 briefing) before Task 03 starts; A4 and A6 before
Task 04; R1 is for the owner.

Merge-gate conditions for the human reviewer and the merge-blocking hook. Any of the following in
a Story 02.0 change is a **BLOCK** and must be kept out of `master`:

- any `stat`, `lstat`, `readlink`, `realpath`, `resolve`, `abspath`, `open`, `listdir` or `scandir`
  of a selector value, or of a path derived from it, before it is lexically inside the canonical
  root, or of any path outside the root at all;
- a glob value reaching the filesystem;
- `expanduser`, `expandvars`, `glob.glob` or any Unicode normalisation or case folding applied to a
  selector;
- a parent step accepted in any spelling, or a non-separator-aware prefix test;
- a literal include accepted through a symlink (in-root or escaping);
- a selector echoed into an error or log record without `safe()` and a length bound;
- config `include`/`exclude` values triggering any filesystem access.

ADR 0006 may move to Accepted on this verdict once the owner confirms O3 to O5, O7 and O8 (with R1)
and A1 to A8 are applied.

**Note on step numbers.** References to ADR 0006 Contract 3 "steps 4 and 5" in this review use its original numbering. After A1 to A8 were folded in (2026-11-19), the steps are: parent steps 5, absolute values 6, symlink checks 9 and 10.

## Sources

- [DEVCORE, "WorstFit: Unveiling Hidden Transformers in Windows ANSI" (2025-01-09)](https://devco.re/blog/2025/01/09/worstfit-unveiling-hidden-transformers-in-windows-ansi/)
- [Black Hat EU 2024 slides, Tsai, "WorstFit"](https://i.blackhat.com/EU-24/Presentations/EU-24-Tsai-V2-WorstFit-Unveiling-Hidden-Transformers-in-Windows-ANSI.pdf)
- [CVE-2024-47611, XZ Utils Windows best-fit argument injection and traversal (reproduction notes)](https://vuln-reproduce-lab.pages.dev/en/CVE-2024-47611/path-traversal/)

## Task 03 code review (2026-11-19)

Scope: uncommitted `src/docsentinel/discovery.py` (`is_glob`, `selector_matches`,
`prunes_directory`, `Discovery`/`discover_with_stats`, `InvokerSelection`,
`normalize_invoker_selectors`, `selector_root_spellings`) and the tests
`tests/unit/test_selector_matching.py`, `tests/unit/test_invoker_selectors.py`,
`tests/mock/test_invoker_selectors_containment.py` (130 passed). Probes ran with `os.lstat` and
`os.readlink` wrapped, in a scratch directory.

BLOCK conditions checked, none hit:

- No `stat`/`lstat`/`readlink`/`realpath`/`resolve`/`abspath`/`open`/`listdir`/`scandir` of a
  selector value before it is lexically inside the root. The lexical phase (`_lexical_normalize`)
  runs for every value of both keys before the first `_check_literal` call. The only `abspath` is
  on the invoker's own root spelling in `selector_root_spellings` (A4). Probes found zero calls
  outside the root for an absolute escape symlink, a relative escape symlink, a self loop, a
  two-link cycle (129 calls, bounded by the hop limit), an absolute sibling-prefix value and an
  absolute outside value.
- Globs never reach the filesystem (`normalize_invoker_selectors` skips them, and an absolute
  glob is refused).
- No `expanduser`, `expandvars`, `glob.glob`, `unicodedata` or case folding (grep). `..` is refused
  on the raw `/`-split text after the backslash rule and before `normpath`. Containment uses
  `path_boundaries._within`, which is separator-aware, and spellings are sorted longest first.
- A literal include through an in-root symlinked component, through a final-component symlink or
  through an escaping symlink is refused (M15 signal plus `S_ISLNK`). `S_ISREG`/`S_ISDIR` is
  enforced for includes (M16). An `OSError` becomes a `ConfigError` with the relative literal and
  `safe(strerror)` only (M17). `ConfigError` is a `ValueError`, so the escape refusal raised
  inside the `try` is not re-wrapped.
- Every echo goes through `safe(value, 200)`. Shape errors echo no value. `##[` and bidi values are
  refused with the A2 wording and echoed neutralised (`##\[`).
- A3: `ntpath.splitdrive` and the leading-double-separator test run before the backslash rule on
  every platform. A8: the order is type, then `len` before iterating, then item type and length
  before `neutralize`.
- O1: a glob exclude still prunes by directory name only. Literal path pruning is plain string
  equality, so it cannot be steered by glob syntax. Config values stay string-only.

### [LOW] R03-1 `root_spellings` is accepted from the caller unverified
- Vector / evidence: `src/docsentinel/discovery.py:496` and `:526`. Any path passed in
  `root_spellings` becomes an acceptance prefix. A probe with `root_spellings=(Path("/"),)` turned
  `/etc/passwd` into the in-root literal `etc/passwd`. Nothing escapes the root (the result is
  joined to the canonical root and walked), but the selection differs from what the invoker named
  (T3 class).
- Mitigation (Task 04): the engine and the CLI pass only `selector_root_spellings(...)` output.
  `scan()` must not expose a `root_spellings` keyword.

### [LOW] R03-2 Windows reserved device names are not refused
- Vector / evidence: `_check_windows_forms`, `src/docsentinel/discovery.py:351-377`, refuses
  drive, UNC, device-namespace, rooted, ADS and trailing dot/space forms. It does not refuse
  `CON`, `NUL`, `AUX`, `PRN`, `COM1`-`COM9`, `LPT1`-`LPT9` or `CONIN$`/`CONOUT$` as a component.
  On older Windows, `os.lstat(<root>\docs\NUL)` resolves to the device and not to an in-root
  object. An include is still refused by M16 (character device). An exclude is accepted and does
  nothing. No file outside the root is read.
- Mitigation (follow-up, Windows lane): add a reserved-name refusal to M11 when
  `backslash_is_separator`.

### [LOW] R03-3 The shape-checked container is iterated again, and `str` subclasses are accepted
- Vector / evidence: `_check_shape` iterates `values` (`:343`), then
  `normalize_invoker_selectors` iterates the original object again (`:522`, `:529`). A custom
  `Sequence`, or a `str` subclass that overrides `split`/`replace`/`startswith`, can behave
  differently from what was checked. Only a library caller (I4) can reach this, and that caller
  already runs code in the process, so it is hardening only.
- Mitigation: have `_check_shape` return `tuple(str(item) for item in values)`, or require
  `type(item) is str`.

### [INFO] R03-4 Absolute literal under a root path holding `*`, `?` or `[`
- `src/docsentinel/discovery.py:429-431`: such a value is refused as `globs must be relative`.
  This fails closed. Document it in Task 06 (use a relative value).

### [LOW] R03-5 Mapped tests not yet present (Task 05)
- Missing by name: `test_lstat_only_inside_root_for_escaping_absolute_symlink`,
  `test_no_realpath_or_resolve_of_selector_value`, `test_symlink_loop_refused_bounded`,
  `test_config_literals_never_touch_filesystem`. The probes above confirm the behaviour each one
  is meant to pin down. Task 05 adds them under these exact names.

### Items for Task 04 and Task 05
- Task 04: pass the **resolved** directory as `scan_root`. The symlink signal compares
  `Path.joinpath` against `contained_path`'s `normpath` form, so a non-canonical root gives false
  "symlinked" refusals (fail closed, but wrong). Compute `root_spellings` only through
  `selector_root_spellings(directory, spelled)`, identically in the CLI early call and the engine
  (R03-1). Implement R1 (exit `2` on an empty final inventory under invoker selection), M18 and
  M22 (counts-only `INFO` line, `safe()` in the unmatched-exclude `WARNING`, which the normaliser
  leaves to the caller).
- Task 05: R03-5 plus the integration tests in the M3, M6-M9, M18 and M20-M22 rows.

### Verdict: PASS_WITH_FOLLOWUP
No CRITICAL or HIGH finding, and no merge-gate BLOCK condition is met. Task 03 implements A1, A2,
A3, A5, A7, A8 and the A4 helper as specified. R03-1 must be handled in Task 04. R03-2 and R03-3
are hardening follow-ups. R03-5 belongs to Task 05.

## Task 04 code review (2026-11-19)

Scope: uncommitted `src/docsentinel/engine.py` (`scan(include=, exclude=)`, `_apply_invoker_selection`,
`_log_selection`, the R1 `ConfigError`), `src/docsentinel/cli.py` (`--include`/`--exclude` on `scan`
and `baseline`, `_validate_selectors`, `_scan_overrides`, `_doctor_selection_lines`),
`src/docsentinel/discovery.py` (`check_invoker_selector_shape`, the R03-3 snapshot) and the tests
`tests/integration/test_cli_include_exclude_ds101.py` and `tests/integration/test_discovery_selectors.py`
(153 selector tests pass, Task 03 suites included). The CLI was probed with `DOCSENTINEL_SETTINGS=off`
in a scratch git checkout that held an in-root directory symlink and an outside symlink to the root.

BLOCK conditions checked. None is hit:

- **Canonical root (M3, Task 03 carry-over).** The engine passes `Path(root).resolve()` as
  `scan_root` (`engine.py:451`, `:475`). The CLI passes `_resolve_root(args.root)`
  (`cli.py:1034-1039`). For an existing directory both give the same canonical path. Strict versus
  non-strict resolution differs only for a loop, and the CLI already refuses that.
- **Spellings (A4, M8, R03-1).** Both callers compute spellings only through
  `selector_root_spellings(<canonical>, <root as given>)` (`engine.py:370`, `cli.py:1039`). Neither
  reads `$PWD`, and `_origin_spellings()` stays on the extension path only (`cli.py:1133`).
  `scan()` has no `root_spellings` keyword: a probe raised `TypeError`. R03-1 is closed. Probe:
  `scan rootlink --include <abs>/rootlink/docs/sub` and the canonical spelling select the same single
  document.
- **CLI and engine stay in step (Contract 6).** Both run the shape check for every target, then
  normalise only a directory target, with the same inputs (`cli.py:1017-1040`,
  `engine.py:464-475`). The CLI discards the result, and the normaliser logs nothing, so the
  unmatched-exclude `WARNING` appears once. A value the CLI refuses never reaches the engine. A
  value the CLI accepts can be refused by the engine only after a filesystem change between the two
  calls (T13). The engine then raises `ConfigError` and the run exits `2`, so the gap fails closed.
- **Echo (M21, M22).** Each pattern in a log record goes through `safe(pattern, 200)`
  (`engine.py:378`, `:406`, `:409`, `:481`). The `INFO` `selection:` line, the single-file
  `WARNING` (`:468`) and the R1 message (`:483`) carry counts only. Probes:
  - A value holding ESC and `##[` gave `Scan failed:` as the first stderr line, echoed as
    `\x1b[31m##\[`.
  - A `docs/::error::...` exclude is echoed mid-line after the `docsentinel: WARNING:` prefix, so it
    cannot start a workflow command.
  - The doctor `selection: error:` line goes through `neutralize_text` (`cli.py:430`).
- **R1.** `--exclude '*'` exits `2` on both `scan` and `baseline` with the fixed message, after the
  `INFO` selection line. A config-only empty inventory stays at exit `0` (test present).
- **Config values never reach the walk; C6 holds.** `_apply_invoker_selection` normalises only the
  invoker lists and appends them to `settings.exclude` by string (`engine.py:367-379`). Discovery
  matches strings only. `include` and `exclude` are still in `USER_SETTINGS_REFUSED_KEYS`. The
  doctor source is the project file name or `default`, never user settings.
- **Absolute outside values.** `/etc/passwd` and a path that does not exist give the same message,
  which does not depend on existence. A literal include through an in-root symlink is refused.
- **R03-3 closed.** `_check_shape` returns `tuple(str.__str__(item) ...)` (`discovery.py:349`).
  Both an item that is a `Path` and a generator are refused.

### [LOW] R04-1 Mapped Task 05 tests still missing
- Vector / evidence: no test of these names exists:
  - `test_cli_early_validation_uses_canonical_root`
  - `test_cli_absolute_outside_root_message_independent_of_existence`
  - `test_cli_and_engine_use_same_root_spellings`
  - `test_cli_refused_selector_echo_neutralised`
  - `test_cli_warning_echo_bounded`
  - `test_case_mismatched_literal_include_zero_hit_warning`
  - `test_pathological_globs_complete`
  - `test_lookalike_named_file_selected_only_by_exact_name`
  - the four R03-5 tests

  The probes above confirm the behaviour each one is meant to pin down.
- Mitigation: Task 05 adds them under these exact names. In particular, it pins the CLI/engine
  spelling parity and the escape-sequence echo, because a regression in either would be a BLOCK
  condition.

### [LOW] R04-2 Error lines in doctor have no length bound
- Vector / evidence: `cli.py:430`, like the four doctor error lines next to it (`:201`, `:342`,
  `:362`, `:393`), applies `neutralize_text` with no length bound. The text is a `ConfigError` from
  the current directory's config file, which is untrusted, and it can echo key names (for example
  `Unknown config options: ...`). The line is neutralised, so there is no injection. It is only
  unbounded.
- Mitigation (follow-up, not specific to this story): use one bounded helper for every doctor
  error line, for example `safe(error, 500)`.

### [INFO] R04-3 Selector refusals that fail closed with a confusing message
- A component longer than `NAME_MAX` in a literal exclude gives `cannot check it (File name too long)`
  and exits `2`, where an unmatched-exclude `WARNING` would be expected. A selector given with a
  root that does not exist reports `not found under the scan root` before the engine's
  `Not a directory`. Both fail closed. Document them in Task 06, or reword them.
- A logical `$PWD` spelling of a root entered through a symlink is refused as outside the scan
  root. M8 intends this. Task 06 should document using a relative value.

### Items for Task 05 and Task 06
- Task 05: R04-1 (all names above, verbatim from the mitigation-to-test map).
- Task 06 should document:
  - R04-3;
  - R03-4;
  - case and normalisation sensitivity (T8);
  - that `--i` and `--ex` are now ambiguous abbreviations;
  - that a `$PWD` spelling is not accepted.
- Backlog: R04-2, R03-2 (Windows reserved names), F1, F2.

### Verdict: PASS_WITH_FOLLOWUP
There is no CRITICAL or HIGH finding, and no merge-gate BLOCK condition is met. Task 04 implements
M3 (CLI part), M8, M9, M18 (R1 as exit `2`) and M22 as specified, and it closes R03-1 and R03-3.
Merging depends on Task 05 adding the R04-1 tests.

## Story 02.0 close review (2026-11-20)

Scope: the final uncommitted `src/docsentinel/discovery.py`, `engine.py` and `cli.py` (after the
Task 05 lint fix, which moved test imports to module scope and dropped a `-> None` from
`check_invoker_selector_shape`), the five Task 05 test files, and the Task 06 docs
(`docs/user/tutorial/cli.md` "Selecting files: --include and --exclude",
`docs/user/reference/configuration.md`, `docs/user/tutorial/library.md`, `README.md`, `CLAUDE.md`,
`RELEASE_NOTES.json`, `docs/specs/logging.md`). The suites ran with `DOCSENTINEL_SETTINGS=off`:
269 passed and 1 skipped. The CLI was probed in a scratch git checkout that held an in-root directory
symlink, an escaping directory symlink and a symlink to the root.

BLOCK conditions re-checked on the final code. None is hit:

- **Filesystem calls on selector values.** The only calls are in `_check_literal`
  (`discovery.py:461-497`): one `contained_path()` walk of the lexical in-root join and one
  `os.lstat`. They run only after `_lexical_normalize` has processed every value of both keys. The
  only `abspath` and `samefile` calls are on the invoker's own root spelling
  (`discovery.py:292-295`). Since the Task 04 review, the diff adds no `stat`, `open`, `realpath` or
  `resolve` call.
- **Globs, expansion, normalisation.** Globs are skipped before `_check_literal`
  (`discovery.py:553-554`), and an absolute glob is refused (`:449`). There is no
  `expanduser`, `expandvars`, `glob.glob`, `unicodedata`, `casefold` or `lower`.
- **Parent steps and containment.** `..` is refused on the raw text, after the backslash rule and
  before `normpath` (`:446`). Containment uses `_within`, which is separator-aware, and the
  spellings are tried longest first (`:545`).
- **Symlinks.** A literal include reached through any symlink is refused (`:492`). A
  symlink-escaping include or exclude is refused (`:479`).
- **Echo.** Every echo goes through `safe(value, 200)` (`:312`, `:486`; `engine.py:378`, `:406`,
  `:409`, `:481`). The INFO line, the single-file WARNING and the R1 message carry counts only.
- **Config values.** They match by string only. `include` and `exclude` stay in
  `USER_SETTINGS_REFUSED_KEYS`.
- **CLI/engine parity (M8).** The CLI normalises with `_resolve_root(args.root)` and
  `selector_root_spellings(target, args.root)` (`cli.py:1033-1040`). It passes `args.root`, not the
  resolved path, to `scan()` (`cli.py:1175`, baseline `:1093`), so the engine computes the same
  spellings (`engine.py:370`).

Probes confirmed the behaviour on the final build:

- `/etc/passwd` and a path that does not exist give the same message.
- A 1,024-character value is echoed cut to 200 characters.
- A `$PWD` spelling through a root symlink is refused as outside the scan root.
- The spelled root `../rootlink` with an absolute value under it is accepted.
- An escaping exclude exits 2.
- A missing root reports `not found under the scan root`.
- A literal exclude whose component exceeds `NAME_MAX` reports `cannot check it (File name too long)`.

**Mitigation-to-test map.** All 51 mapped names exist in the mapped files and pass. R03-5 and
R04-1 are closed. `test_exclude_star_empty_inventory_exits_2` and
`test_selection_info_line_has_counts_only` exist in both integration files, which is harmless.

**Docs.** `cli.md` accurately states:

- the refused inputs, including the existence-independent message for an outside value;
- the `$PWD`/M8 rule ("the real path, or the scan root exactly as you typed it");
- R03-4 (absolute value under a root that contains glob characters);
- R04-3 (`NAME_MAX` and a missing root);
- the T8 case and normalisation sensitivity, and the R1 exit 2;
- the `--i`/`--ex` ambiguity;
- the caution: "same power as the `include` and `exclude` keys of the repository's own
  configuration. Do not feed them from an untrusted source".

The caution does not overclaim. Invoker literals add an in-root `lstat`, but that oracle stays
inside the root, as T9 records. `configuration.md`, `README.md`, `CLAUDE.md`, `RELEASE_NOTES.json`
and `logging.md` are consistent with the code, and none claims more than the code does.

### [LOW] C1 Symlink-escaping exclude refusal not listed in the user docs
- Vector / evidence: `docs/user/tutorial/cli.md:330-341` lists the refusals for an include that
  goes through a symlink. It does not say that an `--exclude` leaving the root through a symlink
  also exits 2 (`discovery.py:479`). The CLAUDE.md discovery bullet has the same gap. The
  behaviour fails closed, and the docs only under-describe it.
- Mitigation: add "an include or exclude that leaves the scan root through a symlink" to the list.
  Owner: docs-updater, in the next docs pass.

### [LOW] C2 Untrusted-source caution and M14 note missing from the library guide
- Vector / evidence: `docs/user/tutorial/library.md:79-103` does not repeat the "do not feed from
  an untrusted source" caution. Library callers (I4) are the channel most likely to forward
  external strings. The M14 note, that a file name that is not valid UTF-8 cannot be selected by a
  literal, appears in no user doc.
- Mitigation: add both sentences to library.md. Optionally add the M14 note to cli.md as well.
  Neither is security-blocking, because every refusal fails closed.

### [INFO] C3 The T8 case-insensitivity test never runs in CI
- `tests/integration/test_discovery_selectors.py:370-392` skips on a case-sensitive file system.
  That covers Linux CI and this macOS host, whose temporary volume is case-sensitive. M18's
  primary test, `test_exclude_star_empty_inventory_exits_2`, runs everywhere. The no-casefold
  property is also covered by `test_no_unicode_normalisation_applied`. The skipped test is
  defence in depth only. A case-insensitive CI lane (for example macOS on a default APFS runner)
  would exercise it.

### [INFO] C4 `_EMPTY_REASON` is unreachable
- `discovery.py:60`, `:453-454`: after the shape check (a non-empty item), a value whose
  components are all empty or `.` either contains `.` or starts with `/`. A value that starts
  with `/` takes the absolute branch, which returns `"."` or a non-empty path or raises
  `outside`. A leading `//` is refused as UNC first. The branch is dead defensive code that fails
  closed. Keep it or remove it; there is no security impact.

### Disposition of open items
- **R03-2** (Windows reserved device names): deferred to the Windows lane backlog. It is not
  reachable from Linux CI. An include is still refused by M16, and an exclude does nothing.
- **R04-2** (unbounded doctor error lines): deferred to the backlog as a cross-story hardening
  task: one bounded helper for every doctor error line. The lines are neutralised, so there is no
  injection.
- **F1** (total character budget across selector values): deferred to the product backlog. The
  existing per-value and per-count bounds hold (`test_pathological_globs_complete`).
- **F2** (selection counts in the run metadata): deferred to the product backlog. Until then the
  INFO selection line is the audit record.
- **`_EMPTY_REASON` unreachable** (C4): accepted as is. Optional clean-up for `python-expert`.
- **C1, C2**: docs follow-ups for docs-updater. They do not block the merge.

### Verdict: PASS_WITH_FOLLOWUP
There is no CRITICAL or HIGH finding, and no merge-gate BLOCK condition is met on the final code.
Every mitigation maps to a passing test under its mapped name. The docs describe the
security-relevant behaviour accurately and do not overclaim. Story 02.0 may close on this verdict.
The follow-ups are C1 and C2 (docs) and the backlog items above.
