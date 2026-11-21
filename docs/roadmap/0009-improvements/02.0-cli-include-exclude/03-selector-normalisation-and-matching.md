# Task 03 — Selector normalisation and directory-aware matching

**Parent story:** [Story 02.0](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/README.md)  
**Role:** Python Expert  
**Depends on:** Tasks 01 and 02.

## Inputs

- Story README "Selector grammar" (normative table and examples), "Decisions" S5 to S8.
- `/src/docsentinel/discovery.py` (`discover_with_skips()`), `contained_path()` in
  `/src/docsentinel/detectors/path_boundaries.py`, `neutralize()` in
  `/src/docsentinel/telemetry/filters.py`.

## Steps

1. In `/src/docsentinel/discovery.py` add a pure helper that classifies a pattern as glob or
   literal, and a matcher `selector_matches(relative, pattern, *, include)` implementing the story
   table (literal include admits `.md` files below a directory; literal exclude removes everything
   below).
2. Use it in `discover_with_skips()`: for each directory keep the existing name test and add the
   relative-path test so excluded directories are pruned; for each file use the new matcher for
   both lists. Glob behaviour must stay byte-identical.
3. Return, besides documents and the skip count, a per-include-pattern hit count (a new internal
   function or an extended return value; keep `discover()` and `discover_with_skips()` signatures
   compatible for existing callers).
4. Add `normalize_invoker_selectors(scan_root, include, exclude, *, backslash_is_separator=None)`
   returning the normalised include tuple (or `None` when not given) and the exclude additions.
   Steps per value: bound checks; control and format characters refused (compare with
   `neutralize()`); backslash handling; absolute literal made relative (abspath, then the parent
   resolved with `os.path.realpath()` and compared against the resolved scan root, the last
   component never followed); leading `./`, repeated and trailing slashes removed; `..` or an
   empty result refused; `.` handled per the table; for literals `contained_path()` then
   `os.lstat()`; include missing or symlinked refused, exclude missing kept with a `WARNING`.
   Raise `ConfigError` with neutralised, bounded messages that say values are relative to the scan
   root.
5. Log per the story table (per-pattern at `DEBUG` through `safe()`; never in the per-file loop
   beyond what discovery logs today).

## Files

`/src/docsentinel/discovery.py` (and `/src/docsentinel/config.py` only if a shared lexical helper
is moved there; do not duplicate `_is_within_root()`).

## Verification

- Unit tests test_invoker_selectors.py and test_selector_matching.py (Task 05) green with `-q`.
- Existing discovery and integration tests unchanged and green.
- A test proves `os.walk()` never yields an excluded directory's children.

## Acceptance

- [ ] Literal patterns work as files or directories in config and for invoker values.
- [ ] Every refused input in the table raises `ConfigError` before any discovery.
- [ ] No filesystem access outside the scan root.

## Amendment (ADR 0006, 2026-11-18)

[ADR 0006](/docs/adr/0006-invoker-include-exclude-and-directory-selectors.md) Contracts 2 and 3 are
authoritative. They refine the steps above:

- **Literals-only prune (owner ruling on O1).** In step 2, only a **literal** exclude adds the
  relative-path test for a directory (`D == L`). A glob exclude keeps today's directory-name test
  and file matching exactly; its inventory and skip count stay byte-identical.
- **Step 4, absolute values.** Make an absolute literal relative **lexically**: after
  `os.path.normpath()` it must equal or lie under the scan root or one of the `root_spellings`, and
  that prefix is removed. No `realpath()` or `stat()` of the value before that. The Task 02 review
  confirmed this (O2); see the 2026-11-19 amendment below.
- **Step 4, return shape.** `normalize_invoker_selectors(scan_root, include, exclude, *,
  root_spellings=(), backslash_is_separator=None)` returns the frozen dataclass
  `InvokerSelection(include, exclude, unmatched_exclude)` and does **not** log the
  missing-exclude `WARNING`; the engine does, so an early CLI call does not log it twice.
  A single-component literal exclude (no `/`) is never listed in `unmatched_exclude` (O3,
  provisional). A literal include reached through an in-root symlinked component is refused (O6,
  confirmed by Task 02; see the 2026-11-19 amendment below).
- **Steps 1 to 3, names.** Add `is_glob()`, `selector_matches()` and `prunes_directory()`, and
  the frozen dataclass `Discovery(documents, skipped, include_hits)` returned by
  `discover_with_stats(root, config)`. `discover()` and `discover_with_skips()` keep their
  signatures and delegate to it.

## Amendment (Task 02 security review, 2026-11-19)

The [threat model](/docs/security/threat-model-0009-invoker-selectors-2026-11-18.md) (verdict
PASS_WITH_FOLLOWUP) is a standing input; link it in the briefing. Its amendments A1, A2, A3, A5,
A7 and A8 are this task's, and are folded into
[ADR 0006](/docs/adr/0006-invoker-include-exclude-and-directory-selectors.md) Contracts 1 and 3,
which give the exact step order. In short:

- **A1 (O2 ruled: lexical only).** Step 4's "parent resolved with `os.path.realpath()`" is
  **struck**.
  - Refuse a `..` component on the value after the backslash rule and **before** any
    `normpath()`, for relative, absolute and glob values.
  - Compare an absolute value with the root spellings using the separator-aware `_within()`
    semantics of `path_boundaries.py`, never a bare `startswith`. The longest matching spelling
    wins.
  - Never apply `realpath`, `abspath`, `resolve`, `stat`, `expanduser`, `expandvars` or
    `glob.glob` to a selector value.
  - A value outside the root gets one message that does not depend on whether the outside path
    exists.
- **A2.** No Unicode normalisation (NFC/NFD/NFKC/NFKD), no case folding, and no bytes paths on
  Windows. Look-alike separators are ordinary name characters. `##[` is refused with the reason
  `contains a control, format or unsupported character sequence`.
- **A3.** Detect drive, UNC and device forms on every platform, before the backslash rule:
  `ntpath.splitdrive(value)[0]` non-empty, or a leading double separator (any mix of `/` and `\`).
  With `backslash_is_separator`, also refuse a rooted value without a drive, a `:` after the drive,
  and a component ending in `.` or a space.
- **A5 (O6 ruled).**
  - The symlink signal is `os.fspath(contained) != os.fspath(lexical)`, or `S_ISLNK` from the one
    `lstat`.
  - A literal include must be `S_ISREG` or `S_ISDIR`.
  - An `OSError` from the walk or the `lstat` becomes a `ConfigError` echoing only the bounded
    relative value and the `strerror`.
- **A7.** Every echoed value is `safe(value, 200)`. Shape errors echo no value. Each message ends
  with "values are relative to the scan root".
- **A8.** Shape order: container type (a bare `str`/`bytes` or a non-`Sequence` such as a
  generator is refused), emptiness, `len() <= 256` before iterating, then each item's type and
  `len() <= 1024` before any character check or echo.
- **Also in scope here:** add `selector_root_spellings(canonical_root, spelled_root)`, which
  Task 04 uses (A4). It returns the canonical root plus `abspath(spelled_root)` only when
  `samefile` holds, and never reads `$PWD`.
- **Merge gate:** the threat model's BLOCK conditions apply to this change.
