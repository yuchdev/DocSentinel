# Milestone 0009 — completion status

**Planning state:** 📝 Specification only (0 of 3 stories implemented). Every story is decomposed
into a README with a `## Tasks` table and one spec file per task. Execution order is 01.0, 03.0,
02.0 (see [plan.md](/docs/roadmap/0009-improvements/plan.md#stories)). Open decisions D1 to D16
await owner sign-off.

## Current status

| Story | Name | State | Tests executed |
|---|---|---|---|
| 01.0 | Reference scope and `@`-document references | ✅ Complete (2026-11-16) | — |
| 02.0 | CLI include and exclude | ✅ Complete (2026-11-20) | — |
| 03.0 | TOML and JSON configuration; user settings | ✅ Complete (2026-11-18) | — |

Legend: ⬜ Not started · 🔶 In progress · ✅ Complete.

**Milestone exit gates (2026-11-20): all passed.** Results for the eight gates in
[plan.md](/docs/roadmap/0009-improvements/plan.md#exit-gates):

1. **Locked sync and full suite.** `uv sync --locked` succeeded. Python 3.12: 5012 passed,
   17 skipped. Python 3.13: 5011 passed, 17 skipped, 1 failed. The failure was a Story 03.0 test
   whose expected column for a JSON trailing comma depended on the Python version; it now uses
   the version's own value. The fixed test passes on both versions; the full suite was not rerun
   on 3.13.
2. **Self-scan.** Exit 0, with 0 DS103 and 0 DS124 findings.
3. **Baselines.** `.docsentinel-baseline.json` holds no DS103 or DS124 entries.
   `.docsentinel-standard-baseline.json` is unchanged.
4. **Build.** `uv build` produced the sdist and the wheel.
5. **Links.** `check_doc_links.py docs/`: 312 files, 0 problems.
6. **Security.** PASS_WITH_FOLLOWUP for all three surfaces, with the follow-ups recorded in each
   threat model.
7. **Honesty review.** `rules` tags DS103 as opt-in; `doctor` prints
   `reference scope: links (DS103 off)`.
8. **Owner rulings.** The owner confirmed D1-D16 and accepted ADRs 0004, 0005 and 0006, including
   O3, O4, O5 and O7.

## Tracking rules

- Mark a story complete only when code, tests, docs and the proposed release-notes entry are
  merged and the full suite (`uv run pytest -p docsentinel.pytest_plugin`) and the self-scan
  (`uv run docsentinel scan . --format json`, exit `0`) are green.
- Story 01.0 records the self-scan finding counts per rule **before and after** the scope change,
  and the baseline fingerprint counts, in its close note.
- Each story's Security Auditor task runs before its first Python Expert task; a CRITICAL finding
  stops the story.
- Record every owner ruling on D1 to D16 below, dated.

## Notes & decisions

- **2026-11-20 — Milestone 0009 closed.**
  - **Owner rulings:** D1-D16 confirmed as taken. D7 fixes the release at 1.3.0; `pyproject.toml`
    still reads 1.2.0, so the version bump is part of the release. ADRs 0004, 0005 and 0006 are
    Accepted, and ADR 0006's provisional points O3, O4, O5 and O7 are confirmed as built.
  - **Exit gates:** all eight passed (see the gate results under the status table).
  - **Carried to the backlog** (each recorded in its threat model or story section):
    - user settings: F2, F3, T04-3, T05-1 to T05-4;
    - invoker selectors: R03-2, R04-2, F1, F2, the unreachable `_EMPTY_REASON` branch, `DS204`
      ignoring literal excludes, and the `_resolve_root`/`resolve()` agreement test;
    - the user-settings checklist steps 5-10 and 18, still to be run by hand.

- 2026-11-14: Execution started via `implement-milestone`. D1 to D16 adopted as recommended in plan.md (the owner delegated the technical detail and has not overridden any); any later owner ruling is recorded here and amends the affected specs. Decomposition audit: complete, no gaps. Note: DS100 (engine rule for unreadable documents) landed just before this milestone, so rule counts in the specs are now 17 fast rules.
- 2026-11-13: Milestone specified from the owner's outline (reference scope with `@`-documents,
  CLI include/exclude, TOML and JSON configuration with user-level settings). Decisions D1 to D16
  were taken provisionally by the architect; see
  [Open decisions for owner](/docs/roadmap/0009-improvements/plan.md#open-decisions-for-owner).
- 2026-11-13: Rule code DS124 reserved for dangling `@`-document references (DS107, DS111 and
  DS119 to DS123 remain reserved by Milestone 0004). ADR numbers are taken at authoring time;
  the next free numbers are expected to be 0004 (Story 01.0), 0005 (Story 03.0) and 0006
  (Story 02.0).
- 2026-11-14: Story 01.0 Task 02 complete. The threat model is
  [threat-model-0009-at-references-2026-11-14.md](/docs/security/threat-model-0009-at-references-2026-11-14.md).
  Verdict PASS_WITH_FOLLOWUP: 0 CRITICAL, 2 HIGH (T1, T2), 4 MEDIUM, 7 LOW; mitigations M1 to M21
  are standing inputs for Tasks 03 to 08. Spec amendments A1 to A4 (story README and ADR 0004)
  must land before Tasks 04 and 05. The owner ruling R1 (a step-2 refusal gives no finding) is
  adopted as recommended, pending owner override. Out-of-story follow-ups: F1 (a DS101 `OSError`
  crash on an over-long file name, a separate fix) and F2 (DS116 coverage of extensionless prose
  mentions, a product decision).
- 2026-11-14: Amendments A1 to A4 and ruling R1 applied by the architect to the Story 01.0 README,
  ADR 0004 (still Proposed) and task specs 03 to 05; shared contracts C1 to C8 unchanged. A2
  choice: the "no leading or trailing escaped space" rule is checked after trailing punctuation is
  stripped. The three DS103 self-scan warnings on ADR 0004 name the planned `mentions.py` and
  clear when Task 05 lands.
- 2026-11-15: Story 01.0 Task 03 complete (task-verifier PASS; full suite 4164 passed, 16 skipped).
  DS103 is opt-in on `reference_scope = "strict"` (default `"links"`); `Rule.opt_in_values` and
  `opt_in_hint()` landed; 65 tests added, 58 adapted (DS103 tests now run in strict scope). The
  self-scan drops from 4041 to 53 findings by default (DS103 3988 -> 0); strict scope reproduces
  4041 exactly. Accepted deviations: `paths.detect()` guards the scope itself (the engine still
  calls an opt-in analyzer whose policy is off); the default notice says 11 evaluated until DS124
  lands (Task 05 must check 12 evaluated and 18 registered); M20's injected-`Config` check for
  `at_reference_extensions` moves to Task 05. Docs follow-up for docs-updater: the log example at
  `docs/user/tutorial/cli.md:267` lacks `reference_scope=`.
- 2026-11-15: Story 01.0 Task 04 complete (task-verifier PASS; unit suite 2512 passed, scanner
  integration and mock tests 752 passed; full suite 4330 passed, 16 skipped). `AtReference` and
  `MarkdownBlockIndex.at_references` landed in `markdown_blocks.py` (stdlib only, no logging,
  filesystem or config access); 46 tests added (M8, M12, M13, M19 named tests included); scanner
  output is unchanged for all 670 Markdown files in `tests/assets`, `docs` and the repository
  root. Grammar calls accepted: a code-span mention's `span` is the whole `InlineCode` span (the
  same object, so DS116 matches it by identity per A1); only ASCII space and tab are boundaries; the
  cap applies before the punctuation strip; a dot-leading last component has no extension.
  Reconcile with Task 08 docs: the README and ADR say a code-span mention's span is "the offset of
  the @", and the ADR types `kind` as a `Literal` alias while the code uses `str`. Open for Task 05:
  a shortcut-reference label `[@a.md]` and a reference-definition target `[r]: @a.md` are recorded
  as mentions; prose tokens without an extension or with a dot-leading name (`@../.env`) are
  checked by neither DS116 nor DS124 (same gap as F2).
- 2026-11-16: Story 01.0 Task 05 implemented (task-verifier PASS; full suite 4403 passed, 16
  skipped) but security review
  [review-ds124-at-references-2026-11-16.md](/docs/security/review-ds124-at-references-2026-11-16.md)
  is BLOCK: H1 (a pre-existing `escapes_via_symlink()` walk lstats outside the root through a
  symlink nested in a symlink target; DS124 exposes it on every relative mention), M-A (ordinary
  components counted as symlink hops), L1 (abspath against realpath root), L2 (no DS116 memo).
  Task 05 stays open; the fix is routed back to the implementer, then the security review re-runs.
- 2026-11-16: Story 01.0 Task 05 complete. The security re-review lifts the BLOCK
  (PASS_WITH_FOLLOWUP, same review file): one shared component walker `_walk()` in
  `path_boundaries.py` backs `contained_path()` and `escapes_via_symlink()` (H1); only followed
  symlinks count toward the 64-hop cap (M-A); `canonical_root()` is shared by DS116 and DS124 (L1);
  DS116 memoises mention checks (L2, 64,008 to 509 lstat calls). Full suite 4410 passed, 16
  skipped; a 12,000-path fuzz shows `contained_path()` unchanged. DS116 behaviour changes (release
  note in Task 08): it now reports a symlink hidden inside a symlink target that leads outside, a
  symlink-out after more than 64 plain components, and a committed symlink whose target leaves the
  root and re-enters it (`../out/../root/d`; a link written that way was already an escape); DS101 and DS113 defer to DS116 there. Follow-ups: R-1 (the no-probe
  mock allows root ancestors in every test; subtract a mention-free baseline instead) goes to
  Task 06; R-2 (document "one `mention_cache` per root" on `check_text()`) and the threat-model M3
  wording exemption for the single realpath of the trusted root go to Task 08.

- 2026-11-16 — Story 01.0 Task 06 (fixtures and tests) complete; task-verifier PASS.
  New `tests/integration/test_reference_scope_ds103.py` (the three DS103 scope cases, scope
  precedence through `scan()`, strict baseline then default scan, strict plus `ignore DS103`) and
  the `ds103/` assets `links_scope_inert`, `strict_scope_reports`, `strict_scope_skips_mentions`.
  DS124/DS116 integration tests now assert every finding field. R-1 closed: the no-probe mock
  pauses recording inside `canonical_root` and no longer allows root ancestors, proven by an
  injected outside probe (old mock 12 passed, tightened 7 failed). All 59 tests the threat model
  names exist. Targeted selection 313 passed; full suite 4424 passed, 16 skipped. No `src/`
  change. Watch item: `test_adversarial_runtime_cases.py::...[many_tiny_files]` timed out once
  under heavy machine load (120 s CLI timeout; 79 s alone; DS124 costs ~1.7 s CPU of 12.1 s).
- 2026-11-16 — Milestone 0008 Story 05.0 (DS103 triage) shrinks to the opt-in strict lane: the
  default self-scan reports 0 DS103 (HEAD 3,930 after its baseline), `--reference-scope strict`
  reports 4,939 with no DS103 baseline entries left; 0008's specs are not edited here.
- 2026-11-16 — Story 01.0 Task 07 (self-scan and baseline migration) complete. Self-scan
  per-rule counts after baseline: HEAD 053fac3 default 3,983 (DS103 3,930, all warnings, exit
  0); working tree default 53 (DS103 0, DS124 0) and strict 4,992 (DS103 4,939). The working-tree
  default self-scan was blocked by one DS116 error in
  `docs/security/2026-11-14-logging.md:45` (an evidence code span carrying a `../` chain to
  `etc/passwd`); the evidence was reworded with its meaning kept, and the default self-scan now
  exits 0 (DS102 10, DS105 28, DS106 7, DS117 7 warnings). No DS124 fix was needed. The fast
  baseline fell from 711 entries (DS102 8, DS103 703) to 8 (DS102 8): the 703 DS103 entries were
  dropped as stale and nothing new was absorbed, so the pre-existing DS105/DS106/DS117 warnings
  stay visible, as at HEAD. The standard baseline is byte-identical. CI and pre-commit are
  unchanged, with no strict lane.
- 2026-11-16 — Story 01.0 Task 08 (docs and release notes) complete. This was the single
  docs-updater pass for the story (R, C, K, A). It updated `configuration.md` (Reference scope
  options), `cli.md` (`--reference-scope`, DS124 mentions, migration, the log example),
  `markdown_scanner.md`, `docs/architecture/README.md`, `CLAUDE.md` and `README.md`. It also
  covered the remaining Task 05 follow-ups: the R-2 docstring on `check_text()`, the
  threat-model M3 amendment, and the ADR 0004 / story README `span` and `kind` reconcile.
  `rules.md`, `finding-types.md`, `fault-classes.md` and the example config already matched the
  code. diagram-creator added `mentions.py` DS124 to `component-detectors` and relabelled
  DS103 as opt-in; the overview diagram lists no rules. A proposed 1.3.0 entry is in
  `RELEASE_NOTES.json`, with the version left to the owner and ADR 0004 still Proposed. Link
  check: 0 problems. Rules-table test: 4 passed. Self-scan: exit 0, 52 warnings.
- 2026-11-17 — Story 03.0 started. Task 02's threat model is the security pass that runs before
  any code (story README). Task 01 complete: ADR 0005 (layered configuration, user settings
  JSON under project TOML) is Proposed, and task-verifier gives PASS. The ADR adds a few
  details the README does not spell out, none of which contradict it:
  - `ConfigSources` gains `user_options` and `project_options` (option names only).
  - `load_json_options` errors carry no path; the user-file prefix adds the path in tilde form.
  - A bad `DOCSENTINEL_SETTINGS` value is not echoed.
  - The package exports `ConfigSources` and `load_config_with_sources`.
  - `scan()` gains no new keyword.

  Plan D14 says a user file with bad permissions is an error (exit 2); Task 02 confirms or
  amends this. Setting `DOCSENTINEL_SETTINGS=off` in `ci.yml` is optional and goes to Task 05.
  The diagram follow-up (overview diagram plus a new layered-load sequence diagram) runs after
  Tasks 04 and 05. Link check: 0 problems. Scan of `docs/adr`: exit 0.
- 2026-11-17 — Story 03.0 Task 02 complete. The threat model is
  `docs/security/threat-model-0009-user-settings-2026-11-17.md`, verdict PASS_WITH_FOLLOWUP, with
  no critical findings. It names threats U1-U16 (one high, U1, a settings file that another user
  owns or can write).
  - **D14 ratified as rules R1-R7.**
    - The decision uses `fstat()` on the opened file. The final target must be a regular file
      owned by the effective user or by root, with no group or other write bit.
    - The directory of the configured path and the directory of the final target are checked
      too; a sticky directory may be group- or other-writable.
    - Any violation is a `ConfigError` (exit 2). Non-POSIX platforms skip the check, with a DEBUG
      line.
  - **Spec amendments A1-A12** were applied to specs 03-07, the story README, ADR 0005 and plan
    D14 (ratification note only). C1-C8 are unchanged. CI must now set
    `DOCSENTINEL_SETTINGS=off` at job level (Task 05).
  - **TOML exception (A6).** TOML `nan`, `inf` and overflowing numbers now exit 2; today they
    are accepted or crash.
  - **Pre-existing follow-ups.** F1 (a TOML integer over the digit limit gives an uncaught error,
    and `doctor` crashes) goes to Task 03. F2 (unbounded echo of keys and values) and F3 (no size
    cap on TOML) are deferred.

  Link check over docs/adr, docs/roadmap and docs/security: 0 problems. Self-scan: exit 0.
- 2026-11-17 — Story 03.0 Task 03 complete (strict JSON loader, one validation path).
  - **What changed.** `config.py` now reads TOML, the pyproject table or JSON into a raw options
    mapping, and `_build_config()` validates every format on one path.
  - **Reading a JSON file.** `--config` routes a file ending in `.json`, any case, to
    `load_json_options()`. The file is opened once by `_read_config_once(source, *,
    check_descriptor=None)` with these steps:
    - an `os.stat` pre-check;
    - `os.open` with O_NONBLOCK and O_NOCTTY;
    - an authoritative `fstat` on the open descriptor;
    - a hook that lets Task 04 add the permission check;
    - a read capped at 1 MiB plus one byte.
  - **Number handling (A6, F1).** TOML and JSON nan, inf and overflowing values now give the
    option's existing message. A TOML integer over the 4,300-digit limit gives
    `number out of range`, and `doctor` no longer crashes on it.
  - **Security fix T03-1.** The security review found that a lone surrogate in JSON slipped
    through, and it is fixed: such a file is now refused with `lone surrogate is not allowed`.
    T03-2 (unbounded echo of unknown keys) is the existing follow-up F2. T03-3 is notes for
    Task 04: the hook raises only `ConfigError`, and the user path is logged in tilde form.
  - **Results.**
    - Security review: PASS_WITH_FOLLOWUP.
    - Task-verifier: PASS.
    - Checks: 71 of 71 acceptance probes pass.
    - Tests: config 453, unit+mock 2662, integration 1772 passed (16 skipped), lint 8.
    - No existing test needed editing.
- 2026-11-18 — Story 03.0 Task 04 complete (user settings layer).
  - **Where it lives.** `config.py` has these names:
    - the constants `USER_SETTINGS_ENV`, `USER_SETTINGS_OFF` and `USER_SETTINGS_REFUSED_KEYS`
      (exactly the C6 list);
    - `user_settings_path()`, the only place that reads the environment;
    - `ConfigSources`, which stores option names only;
    - `load_config_with_sources()`, and a `load_config(..., user_settings=)` keyword.

    Both `ConfigSources` and `load_config_with_sources()` are exported from `docsentinel`.
    `engine.py` is unchanged.
  - **Gate (R1-R7).** Before the file is opened, every directory that holds a link in the
    symlink chain, plus the directory holding the final target, must be owned by the user or
    root and must not be writable by group or others, unless it is sticky. The chain may have at
    most 40 links. After opening, R2 checks owner and mode with `fstat` on the descriptor that is
    read.
  - **Test isolation.** In `conftest.py`, every test gets `DOCSENTINEL_SETTINGS=off` and an
    empty `XDG_DATA_HOME`.
  - **Security review: PASS_WITH_FOLLOWUP.** Three findings fixed, one optional:
    - T04-1 (MEDIUM): only the two ends of a symlink chain were checked; every link's directory
      is now checked.
    - T04-2 (LOW): errors chained the underlying OS error, which carries the absolute path; they
      now use `from None`.
    - T04-4 (MEDIUM): a symlink owned by another user in a shared sticky directory was followed,
      which macOS does not block; it is now refused.
    - T04-3 (LOW, optional, left as is): a JSON `null` is reported before a refused key.
  - **Task-verifier: PASS.** Accepted deviations:
    - a home directory of `/` counts as having no home;
    - the missing-file check is a separate step from finding the path;
    - a missing `DOCSENTINEL_SETTINGS` file gives `not readable`.
  - **Checks.**
    - 107 of 107 acceptance probes passed.
    - Tests: 4,434 passed and 16 skipped across unit, mock and integration, with the real user
      settings file present on this machine (it shows the test isolation works).
    - The lint gate passed 8.
    - The self-scan exited 0.
- 2026-11-18 — Story 03.0 Task 05 complete (CLI surface for user settings).
  - **What was added** (`cli.py`):
    - `--no-user-settings` on `scan`, `baseline` and `doctor`.
    - `init --user`. It refuses when settings are `off` or the home directory is unknown, and
      runs the R3 directory check before creating anything. It creates missing directories with
      mode `0o700`. The file is opened with `O_EXCL|O_NOFOLLOW` at mode `0o600`, followed by
      `fchmod`. It never overwrites an existing file or follows a symlink. `--user` together
      with `--project-root` is an argparse error.
    - `doctor` lines for the user settings and the project config. A `ConfigError` prints one
      neutralised line, and `doctor` still exits 0.
    - An INFO line `config: user settings <state>[ (<names>)], project <file or none>`. It lists
      at most 20 names, then `and N more`, and never prints values.
    - Help text naming the settings path and `DOCSENTINEL_SETTINGS`.
  - **Other files.**
    - `config.py`: the R3 helpers gained a `final_is_directory` keyword.
    - `ci.yml`: the job-level environment sets `DOCSENTINEL_SETTINGS: "off"`.
    - `test_cli_logging_ds101.py`: two tests that compare the exact list of INFO lines were
      updated for the new line.
  - **Task-verifier: PASS.** Wording the story does not define was accepted: `off (--no-user-settings)`,
    `off (DOCSENTINEL_SETTINGS=off)`, `none (home directory unknown)`, `config sources: error:`
    and `1 option`.
  - **Security review: PASS.** No finding is required; four are optional:
    - T05-1 (LOW): a component planted after the check, or `..` in the path, fails safely with
      exit 2 but with a misleading "already exists" message. Empty directories that were already
      created are left behind.
    - T05-2 (LOW, goes with F2): `doctor` repeats a config error across four lines, with no length
      limit.
    - T05-3 (INFO): the pre-check is stricter than the loader for a group-writable home on a first
      run. Task 07 should document this.
    - T05-4 (INFO): the confirmation prompt cuts the path at 200 characters.
  - **Checks.**
    - 24 of 24 acceptance probes passed.
    - Full suite: 4,434 passed and 16 skipped. Lint gate: 8 passed. CLI test files re-run after
      the lint fix: 1,331 passed. Self-scan: exit 0.
- 2026-11-18 — Story 03.0 Task 06 complete (tests).
  - **New files.**
    - `tests/unit/test_json_config_loader.py`: 54 tests.
    - `tests/unit/test_config_message_parity.py`: 110 tests.
    - `tests/unit/test_user_settings_policy.py`: 35 tests.
    - `tests/mock/test_user_settings_location.py`: 71 tests.
    - `tests/integration/test_user_settings_cli_ds101_ds103.py`: 31 tests.
  - **Coverage of named tests.** Every test named in spec 06 and in the threat model's U1-U16, F1
    and A11 map exists under that name: 72 names, none missing.
  - **Follow-ups from the Task 03-05 reviews,** now with tests:
    - a lone surrogate is refused;
    - the R3 check covers every directory in a symlink chain, and a symlink in a sticky directory
      that belongs to another user is refused;
    - the chain is capped at 40 links;
    - every gate error is raised `from None`;
    - `--no-user-settings` works on all three commands;
    - the INFO line cuts the option names after 20.
  - **Mutation check.** Four deliberately broken versions of the gate and the INFO line were each
    caught.
  - **Task-verifier: PASS.**
    - Two optional mitigations have no test, because neither was adopted: T05-1
      (`test_init_user_raced_intermediate_dir_exits_2`) and T05-2
      (`test_doctor_config_error_one_bounded_line`).
    - The mock module is skipped as a whole on platforms other than POSIX, which is more than
      needed.
    - No src bug was found.
  - **Checks.**
    - The targeted run passed 301. The lint gate passed 8.
    - Full suite: 4,742 passed and 1 failed. The failure is
      `test_timing_helpers.py::test_root_times_n_workload_fails`, an unchanged timing self-test that
      depends on machine load. It passed when re-run alone. The full suite will be re-run at story
      close.
- 2026-11-18 — Story 03.0 Task 07 complete (docs, diagrams, release notes). The single docs-updater pass
  for this change set.
  - **Documents updated:**
    - `configuration.md` describes the four layers, strict JSON, the settings path, the refused keys,
      the R1-R7 rule in user terms, WSL (U14), the trust placed in `DOCSENTINEL_SETTINGS` (U10) and CI
      (U4).
    - `cli.md` covers `init --user` (and why its first-run check is stricter, T05-3),
      `--no-user-settings`, `--config FILE.json`, the `doctor` lines and the INFO line.
    - `library.md` covers `user_settings=` and `load_config_with_sources()`. A pre-existing
      `explicit_file=` mistake in its example was fixed.
    - `logging.md` was edited in place.
    - `README.md`, `CLAUDE.md` and `docs/architecture/README.md`: the Configuration sections were
      rewritten.
    - `docs/test/user-settings.md` is a new manual checklist.
    - `RELEASE_NOTES.json` has six new 1.3.0 lines.
    - `copilot-instructions.md` was not changed; it only points to `CLAUDE.md`.
  - **Diagrams (diagram-creator).** The component overview gains the user settings JSON file and the
    environment input. A new `sequence/config-layered-load` diagram was added in PlantUML, with SVG and
    PNG. Its participants are the as-built functions (`_read_config_once` and `_parse_json_options`),
    not the names the ADR uses.
  - **Checks.** The link check on `docs/` found 0 problems in 304 files. The self-scan exits 0
    (52 warnings, none in the edited documents).
  - **Still open:**
    - checklist steps 5-10 and 18 were written from the code and have not been run by hand;
    - `README.md` shows `docsentinel_scan(".")` as callable, but the fixture is a `ScanResult`. This
      predates the change.
- 2026-11-18 — Story 02.0 started. Its Task 02 threat review is the security pass before any code,
  the same pattern as Story 03.0. Task 01 is complete: ADR 0006 (invoker include/exclude and
  directory selectors) is `Proposed`.
  - **Contract.**
    - `scan(..., include=None, exclude=None)` is keyword-only. `None` means not given.
    - These inputs are a `ConfigError` (exit 2): an empty sequence, a bare `str` or `bytes`, an
      empty or non-`str` item, more than 256 values, or a value over 1,024 characters.
    - The keywords apply on top of an injected `Config` through `replace()`.
    - Include replaces the configured value. Exclude is the configured value plus the invoker's,
      deduplicated. This is the only list-merging exception to ADR 0005.
    - Selectors are relative to the scan root.
    - A literal means this file, or this directory and everything below it.
  - **Owner ruling O1 (2026-11-18): literals only.** Only a literal exclude (no `*`, `?` or `[`)
    prunes a directory by its relative path. Glob excludes keep today's name-only pruning, so
    existing configs give byte-identical results, and there is no glob behaviour-change note. The
    story README matching table and Task 03 were amended to match.
  - **Open for the Task 02 Security Auditor:**
    - O2: absolute values are handled lexically, with no `realpath` outside the root.
    - O6: an in-root symlinked directory component is refused for include.
    - whether U+2215 and U+FF0F act as separators.
  - **Provisional (they stand unless ruled otherwise):**
    - O3: a single-name literal exclude that names nothing gives no warning;
    - O4: a single-file target still gets the shape checks;
    - O5: a bare `str` keyword is a `ConfigError`;
    - O7: `--include .` means the built-in default;
    - O8: a directory with no Markdown gives a zero-hit warning, not exit 2.
  - **Spec amendments.** Dated amendment notes were added to Tasks 02 to 06:
    - the CLI validates selectors before `scan started`, so `Scan failed:` stays the first stderr
      line;
    - `InvokerSelection` gains `unmatched_exclude`;
    - new functions `discover_with_stats`, `prunes_directory` and `is_glob`;
    - extra tests in Task 05;
    - the `[` escaping note in Task 06.
  - **Diagram follow-up** (after Tasks 03 and 04): the component overview, `config-layered-load`
    and a new `sequence/scan-selection`. Task 01 step 3's diagram names were corrected to files that
    exist.
  - **Checks.** Link check: 0 problems. Scan of `docs/adr`: exit 0.
  - **Task-verifier: PARTIAL.** The `Diagram impact:` line was missing; I added it, which resolves
    the PARTIAL.

- 2026-11-19 — Story 02.0 Task 02 complete: the pre-code security review is
  `docs/security/threat-model-0009-invoker-selectors-2026-11-18.md`, verdict PASS_WITH_FOLLOWUP,
  no CRITICAL finding. Discovery matches only names it finds while walking the root and never follows
  symlinks, so a selector cannot make DocSentinel read outside the root.
  - **Rulings:**
    - O2 is confirmed: an absolute value is handled lexically, with `..` refused before
      `normpath`, a separator-aware prefix test, and the longest root spelling winning. No
      `realpath`, `stat` or user/variable expansion is applied to a value. A path under `/net/<host>`
      on macOS would trigger an automount.
    - O6 is confirmed: an include through an in-root symlink is refused, and a literal include must
      be a regular file or a directory.
    - U1: U+2215 and U+FF0F are ordinary name characters, provided nothing applies Unicode
      normalisation (NFKC would turn U+FF0F into `/`).
    - O3, O4, O5 and O7 stand.
  - **Owner ruling R1 (2026-11-19): exit 2.** When invoker selectors are given and the final
    inventory is empty, the scan raises `ConfigError` and exits `2`. Config-only selection keeps
    exit `0`, and a per-pattern zero-hit `WARNING` stays. This supersedes O8.
  - **Amendments A1 to A8** are folded into the ADR 0006 contracts and assigned through dated notes:
    - Task 03: A1 (lexical), A2 (no normalisation; `##[` refused), A3 (drive, UNC and device forms on
      every platform), A5 (symlink signal; an `OSError` becomes a `ConfigError` that echoes only the
      relative path), A7 (`safe(value, 200)`) and A8 (check order).
    - Task 04: A4 (a shared `selector_root_spellings()`) and A6 (now R1).
    - Task 05: the review's roughly 50 named tests, listed by file.
  - **Optional backlog:** F1 (a total character budget for selectors) and F2 (selection counts in
    the report's run metadata).
  - **Side effect:** the argparse abbreviations `--i` and `--ex` become ambiguous; Task 06 documents
    this.
  - **Task-verifier: PARTIAL.** The review had not recorded R1, a test name was stale, and so were
    two phrases in spec 03. I fixed all three. The story README's S8 row and selection table now
    mention R1.
  - **Checks.** Link check: 0 problems.
- **2026-11-19 — Story 02.0 Task 03 (selector normaliser and directory-aware matching) complete.**
  - **Delivered in `discovery.py`:** `is_glob`, `selector_matches`, `prunes_directory`,
    `Discovery` with `discover_with_stats` (`discover`/`discover_with_skips` delegate),
    `InvokerSelection` with `normalize_invoker_selectors`, and `selector_root_spellings`. Not yet
    wired into `scan()` or the CLI (Task 04).
  - **Tests:** 130 new tests in `tests/unit/test_selector_matching.py`,
    `tests/unit/test_invoker_selectors.py` and `tests/mock/test_invoker_selectors_containment.py`.
    Unit and mock suites: 3062 passed. Discovery and scan integration tests: 443 passed. Glob
    inventories are unchanged for 7 configurations over this repository.
  - **Accepted deviations:** every message ends with the "values are relative" hint; every `.`
    component is dropped; all values are checked as text before any literal touches the disk; the
    normaliser logs nothing (the engine logs, Task 04).
  - **Task-verifier: PASS.** **Security gate: PASS_WITH_FOLLOWUP**, recorded in the invoker threat
    model. R03-3 (snapshot the values as plain `str`) was fixed here; 148 selector and discovery
    tests pass after the fix.
  - **Carried to Task 04:** pass the resolved root as `scan_root`; compute spellings only through
    `selector_root_spellings` (no `root_spellings` keyword on `scan()`, R03-1); a public
    shape-check entry for single-file targets; the per-pattern DEBUG, INFO and WARNING lines; R1.
  - **Carried to Task 05:** the four missing threat-model test names (R03-5). **Deferred:** R03-2
    (Windows device names, Windows lane); R03-4 (root path containing glob characters) is a Task 06
    docs note.
- **2026-11-19 — Story 02.0 Task 04 (CLI and library surface) complete.**
  - **Delivered:** `--include`/`--exclude` (repeatable) on `scan` and `baseline`;
    `scan(..., include=, exclude=)`; `EMPTY_SELECTION_MESSAGE` (R1, exit 2 under invoker
    selectors); `check_invoker_selector_shape` in `discovery.py`; CLI early validation before
    `scan started`; `doctor` `include:`/`exclude:` count lines with the project file or `default`
    as source; the INFO `selection:` line on every directory scan (counts only), DEBUG lines per
    pattern, and the unmatched-exclude and zero-hit WARNINGs, each pattern through `safe(p, 200)`.
  - **Tests:** 23 new integration tests in `test_cli_include_exclude_ds101.py` and
    `test_discovery_selectors.py`, plus two assets; `test_cli_logging_ds101.py` updated for the new
    INFO line. Unit and mock suites: 3062 passed. Related integration tests: 282 passed, 5 skipped.
    `scan . --exclude docs` exits 0 with no `docs/` document.
  - **Task-verifier: PASS**, with all seven interpretations ruled acceptable. **Security gate:
    PASS_WITH_FOLLOWUP**, recorded in the invoker threat model. R03-1 and R03-3 are closed.
  - **Carried to Task 05:** the 12 named tests in R04-1, which include the four from R03-5.
    **Carried to Task 06:** the R04-3 messages, R03-4, case and normalisation sensitivity, the
    ambiguous `--i`/`--ex`, and the advice to use the real path or the root as typed, not `$PWD`,
    for absolute values. **Backlog:** R04-2 (cap the length of `doctor` error lines), R03-2, F1,
    F2.
- **2026-11-20 — Story 02.0 Task 05 (tests) complete.**
  - **Delivered:** the five selector test files now hold 270 tests (117 new in this task),
    with every threat-model test name present verbatim, including the 12 in R04-1. There is one
    test per row of ADR 0006 Contracts 1-3, and the O1, O3, O4, O5 and O6 amendment cases are
    covered. No product code changed and no bug was found.
  - **Results:** selector subset 271 passed, 1 skipped (was 155); `tests/unit` 2925 passed;
    `tests/mock` 227 passed.
  - **Task-verifier: PASS**, with all five implementer notes ruled acceptable:
    - `test_case_mismatched_literal_include_zero_hit_warning` skips on a case-sensitive file
      system; a mocked `lstat` twin covers the same behaviour.
    - The Contract 3 step 7 reason "names no path" (`_EMPTY_REASON`) cannot be reached, so it
      has no test. It is a candidate for removal later.
    - The Windows-root drive case is tested through the private `_lexical_normalize`.
    - Two mapped test names each appear in two files, testing different layers.
    - R03-2 stays in the backlog.
- **2026-11-20 — Story 02.0 Task 06 (docs and release notes) complete.**
  - **Docs (the story's single docs-updater run):**
    - `docs/user/tutorial/cli.md` gained "Selecting files: --include and --exclude".
    - `docs/user/reference/configuration.md` gained "Selection options: `include` and `exclude`".
    - Also updated: `library.md`, `README.md`, `CLAUDE.md`, `docs/architecture/README.md` (a
      "Document selection" subsection) and `docs/specs/logging.md`.
    - Three lines were added to the 1.3.0 entry of `RELEASE_NOTES.json`, the first marked
      BEHAVIOUR CHANGE (literal values now match directories). There is no glob note, per O1.
    - Every Task 06 security docs item is covered: R03-4, R04-3, T8, the ambiguous `--i`/`--ex`,
      and absolute values not taken from `$PWD`.
  - **Diagrams (diagram-creator, PlantUML):** `component/overview` and
    `sequence/config-layered-load` were updated, and `sequence/scan-selection` is new, including
    the R1 branch. The diagrams show the include/exclude merge done in
    `engine._apply_invoker_selection`, which is how the code works.
  - **Checks:**
    - Link check: 0 problems in this milestone's files. Four dangling links in
      `docs/roadmap/0010-fact-check/plan.md` belong to unrelated work in progress.
    - Self-scan: exit 0, with no finding in any edited document.
    - Task-verifier: PASS.


### Story 02.0 - CLI include and exclude (✅ 2026-11-20)

**Delivered**

- **Design and review:**
  - ADR 0006, Proposed. Owner rulings: O1 (only literal values prune a directory), R1 (an empty
    invoker selection exits 2). The threat review ruled O2 (absolute values are handled
    lexically) and O6 (an include through a symlinked component is refused).
  - Threat model `threat-model-0009-invoker-selectors-2026-11-18.md`, with amendments A1-A8 and
    reviews of the Task 03 code, the Task 04 code and the story close.
- **`discovery.py`:** `is_glob`, `selector_matches`, `prunes_directory`, `Discovery`,
  `discover_with_stats`, `InvokerSelection`, `normalize_invoker_selectors`,
  `selector_root_spellings` and `check_invoker_selector_shape`. A literal value means this file,
  or this directory and everything below it; a literal exclude prunes the walk. Glob behaviour is
  unchanged.
- **CLI and library:**
  - `--include`/`--exclude` on `scan` and `baseline`, checked before `scan started`.
  - `scan(..., include=, exclude=)`. Include replaces the configured value; exclude is appended
    and deduplicated.
  - The R1 `ConfigError`.
  - `doctor` gains `include:`/`exclude:` lines.
  - Logging: an INFO `selection:` line (counts only), DEBUG lines per pattern, and WARNINGs for
    an include that matched nothing and for an unmatched exclude.
- **Tests:** five selector test files with 270 tests, every threat-model test name present
  verbatim, and two `ds101/selection_*` asset cases.
- **Docs:**
  - Updated: the CLI tutorial, the configuration reference, the library guide, README, CLAUDE.md,
    the architecture page and the logging spec.
  - Three lines in the 1.3.0 entry of `RELEASE_NOTES.json`, one marked BEHAVIOUR CHANGE.
  - Diagrams: `component/overview` and `sequence/config-layered-load` updated,
    `sequence/scan-selection` added.

**Tests / gate**

- **Full suite:** `uv run pytest -p docsentinel.pytest_plugin` gave 5011 passed, 17 skipped and 1
  failed. The failure was the flakeforge lint gate (X006, X007 and X008 in the new tests and
  `discovery.py`). After the fix, the lint gate passed (8 passed) and the selector subset passed
  (271 passed, 1 skipped). The full suite was not rerun after the fix.
- **Self-scan:** `scan . --format json` exits 0.
- **`/pr-review`:**
  - feature-reviewer: LGTM.
  - security-auditor: PASS_WITH_FOLLOWUP, with no CRITICAL or HIGH finding. All 51 mapped test
    names exist.
  - Review docs items applied at close:
    - an exclude that escapes through a symlink exits 2;
    - R1 also applies to `baseline`;
    - `DS204` Python discovery does not follow literal directory excludes;
    - a file name that is not valid UTF-8 cannot be a literal;
    - the library guide repeats the untrusted-source caution.
  - Link check: 0 problems.
- **Task-verifier:** PASS on Tasks 01-06; Task 02 first came back PARTIAL and was fixed.

**Open and backlog**

- ADR 0006 still needs the owner's acceptance, including confirmation of O3-O5 and O7.
- Backlog: R03-2 (Windows device names, Windows lane), R04-2 (cap the length of `doctor` error
  lines), F1 (a total budget for selector characters), F2 (the selection in report run
  metadata), the unreachable `_EMPTY_REASON` branch, and the feature-review suggestions:
  - route `DS204` through `selector_matches`;
  - hoist the per-file split in `_first_exclude_reason`;
  - add a test pinning that the CLI's `_resolve_root` and the engine's `resolve()` agree.

### Story 03.0 - TOML and JSON configuration; user settings (✅ 2026-11-18)

**Delivered**
- **Layered configuration (ADR 0005, still `Proposed`).** The layers are defaults, then the user
  settings JSON, then the project TOML or `--config` file, then CLI flags. A layer replaces whole
  values, and an injected `Config` passes unchanged.
- **Strict JSON loader.** `--config FILE.json` with a `.json` suffix in any case. JSON is never
  discovered.
  - The file is opened once and read from one descriptor, with a 1 MiB cap.
  - It refuses a byte-order mark, invalid UTF-8, duplicate keys, NaN or infinite numbers, `null`
    anywhere and lone surrogates.
  - TOML and JSON share one validation path (`_build_config`), so their messages match.
  - A TOML integer with too many digits is now a `number out of range` `ConfigError`.
- **User settings layer.**
  - Location: `$XDG_DATA_HOME/docsentinel/settings.json`, else
    `~/.local/share/docsentinel/settings.json`. `DOCSENTINEL_SETTINGS` takes an absolute path or
    `off`.
  - `USER_SETTINGS_REFUSED_KEYS` holds the 10 repository-relative C6 keys; any of them exits 2.
  - Permission gate R1-R7:
    - before the file is opened, every directory holding a link in the symlink chain is checked,
      with at most 40 links;
    - a link owned by another user in a writable sticky directory is refused;
    - R2 checks owner and mode with `fstat` on the descriptor that is read;
    - when running as root, only root-owned files and directories pass;
    - error messages use fixed phrases and tilde-form paths, raised `from None`;
    - the gate is skipped on platforms other than POSIX.
  - New public API: `ConfigSources`, `load_config_with_sources()` and
    `load_config(..., user_settings=)`.
- **CLI.**
  - `--no-user-settings` on `scan`, `baseline` and `doctor`.
  - `init --user` creates directories at `0700` and the file at `0600` (`O_EXCL|O_NOFOLLOW` plus
    `fchmod`), and never overwrites.
  - New `doctor` source lines.
  - New INFO line `config: user settings <state>[ (<names>)], project <file>`, listing at most 20
    names and never values.
- **CI.** `DOCSENTINEL_SETTINGS: "off"` at job level. `tests/conftest.py` isolates every test from
  the real home directory.
- **Docs.**
  - Updated: configuration reference, CLI and library tutorials, `logging.md`, `README.md`,
    `CLAUDE.md`, architecture README, 6 release-note lines for 1.3.0.
  - New: manual checklist `docs/test/user-settings.md`, and the diagrams (component overview, new
    `sequence/config-layered-load`).
  - Threat model `docs/security/threat-model-0009-user-settings-2026-11-17.md`.

**Tests / gate**
- **New tests.** Five files with 301 tests: unit tests for the JSON loader, message parity and
  policy; mock tests for location and gate; CLI integration tests. All 72 tests named in spec 06 and
  the threat model exist. A mutation check caught each of four deliberately broken versions of the
  code.
- **Full suite** (`uv run pytest -p docsentinel.pytest_plugin`): 4,743 passed and 16 skipped,
  exit 0. The `test_timing_helpers` failure seen under load in Task 06 did not recur.
- **Self-scan:** exit 0, 386 documents, 52 warnings, 0 errors. Link check on `docs/`: 0 problems.
- **`/pr-review`:**
  - feature-reviewer: LGTM. Two optional suggestions: give public names to the two private config
    helpers that `cli.py` imports, and guard the per-key error attribution.
  - security-auditor (story close): PASS_WITH_FOLLOWUP. The required fix C-1 (the `chmod` advice now
    says which directories to check and that ownership is not fixable with `chmod`) and the optional
    fixes C-2 to C-4 (self-hosted runner, WSL drvfs and YAML quoting, checklist step 14) were applied
    to the docs.
- **Open optional follow-ups:** F2 (unbounded echo of keys and values), F3 (no TOML size cap, and a
  FIFO given to TOML `--config` blocks), T04-3, T05-1 to T05-4.
- **Owner sign-off pending:** ADR 0005 to Accepted.

**Reconciliation note.** All seven task specs were *consumed*. As-built refinements are recorded in
the dated task notes:
- the error-line wording;
- the `final_is_directory` keyword on the R3 helpers;
- the diagram participants named after the real functions;
- the docs-updater ran once, in Task 07.

### Story 01.0 - Reference scope and `@`-document references (✅ 2026-11-16)

**Delivered**
- `reference_scope` config key (`links` default, `strict`) and a `--reference-scope` flag on
  `scan` and `baseline`. DS103 is now an opt-in policy rule, driven by `Rule.opt_in_values` and
  `opt_in_hint()`. The notice, `rules` and `doctor` name it when it is off, and `doctor` prints a
  `reference scope:` line.
- `at_reference_extensions` (1 to 64 entries).
- Scanner record `AtReference` (`MarkdownBlockIndex.at_references`), with a 1,024-character token
  cap and backslash-space as its only escape.
- DS124 (`detectors/mentions.py`), an always-active fast rule at warning severity for dangling
  `@`-document mentions. It resolves against the scan root, then the link root, checking
  containment before its single `stat`, and never opens a target. Ownership is split three ways:
  DS116 reports escapes (`mention_ds116_reason`), DS124 reports missing targets, and DS103 skips
  `@` spans. A read-failure guard skips any document it cannot read.
- Shared containment walker `_walk()` behind both `contained_path()` and
  `escapes_via_symlink()`, plus a shared `canonical_root()`. This fixed H1, a nested-symlink
  probe that could reach outside the root, and changes DS116 in three symlink cases (see the
  release notes).
- Fast baseline 711 → 8 entries (DS103 dropped). Docs, diagrams, ADR 0004 (still Proposed) and a
  proposed `RELEASE_NOTES.json` 1.3.0 entry.

**Tests / gate**
- Full suite: 4441 passed, 16 skipped, 1 failed. The failure was the flakeforge X005 lint on
  `[Mock]` docstring headers; after fixing them, the lint gate and the affected files pass
  (13 passed).
- Self-scan: `scan . --format json` exits 0 (52 warnings; 0 DS103, DS116 or DS124 findings).
- Security: Task 05 BLOCK, then PASS_WITH_FOLLOWUP; story-close review PASS_WITH_FOLLOWUP, with
  SC-1 to SC-4 fixed.
- `/pr-review`: feature REQUEST_CHANGES, then LGTM after fixes.
- Every Task 02 mitigation (M1 to M21) has a named test. The new tests were checked by mutation.

**Reconciliation note**
- All eight task specs were consumed as written. The ADR, story README and specs 03 to 05 carry
  the Task 02 amendments A1 to A4.
- Story-close additions beyond the specs: a symlink-deferral test set
  (`test_symlink_deferral_ds101_ds113_ds116_ds124.py`, `test_symlink_deferral_no_probe.py`), the
  mentions read-failure guard, and the SC-1 link-root trust docs.

**Deferred / owner items**
- Owner sign-off: ADR 0004 to Accepted, and the 1.3.0 version for `RELEASE_NOTES.json`.
- Cleanup: dead code `links._resolve()` (two unit tests still call it).
- Open from the threat model: F1 (DS101 `OSError` crash) and F2 (extensionless or dot-leading
  prose mentions are unchecked).
- Watch item: `many_tiny_files` came close to its 120 s CLI timeout under load.
- Logging review: the DS103 DEBUG line logs code-span text through `safe()`.
