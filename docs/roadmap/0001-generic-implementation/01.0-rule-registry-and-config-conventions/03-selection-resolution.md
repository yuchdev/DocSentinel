# Task 03 - Selection Resolution & Engine Wiring

**Story:** [01.0 - Rule Registry & Config Conventions](README.md)
**Depends on:** [01 - Rule registry](01-rule-registry.md), [02 - Config conventions](02-config-conventions.md)

## Purpose

`Config.select`/`Config.ignore` (Task 02) and `rules.RULES` (Task 01) exist but nothing yet
turns them into "which analyzers does `engine.scan()` actually run." This task writes that
resolver and rewires `engine.py` around it, including the honesty rule `CLAUDE.md` states
explicitly: an empty findings list must never look like a passed audit.

## Decision this task implements

1. **Profile scoping is exact, not cumulative.** `profile = "fast"` runs only rules registered
   with `Rule.profile == "fast"`; it does **not** also run `standard`/`deep` rules at a lower
   priority. This matches the existing `elif` chain in today's `engine.scan()` (`pending` is
   computed per-profile, not additively) - keep that shape, don't change it to a cumulative one.
2. **`select`/`ignore` matching is prefix-based**, ruff-style: a selector `s` matches a code `c`
   if `c == s` or `c.startswith(s)` (so `select = ["DS1"]` means "every `DS1xx` code").
   **`ignore` always wins** over `select` for a code matched by both - the same precedence
   `flake8`/`ruff` use.
3. **An unmatched selector is inert, not an error** - `select = ["DS999"]` when no such rule is
   registered yet simply selects nothing extra; it was already validated as *well-formed* in
   Task 02 and must not raise here either. This lets a config reference a future milestone's
   codes ahead of time.
4. **`ANALYZERS` is keyed by rule code** (e.g. `"DS101"`), not by an arbitrary name - this was
   left unspecified in M0 since the dict was empty; fixing the key's meaning here is this task's
   job, because the resolver and `rules_for_profile` both need to join on it.
5. **Honesty about `notice`**: `ScanResult.notice` must say something true for the profile and
   selection in effect:
   - At least one rule evaluated this run → `notice` becomes
     `f"{len(active_codes)} {profile} rule(s) evaluated."` (empty findings then means "ran and
     found nothing," not "not implemented").
   - Zero rules evaluated **because the profile has no registered rules yet** (true for
     `standard`/`deep` this whole milestone) → keep today's wording, via the existing `pending`
     tuple mechanism - do not change `pending`'s existing two messages.
   - Zero rules evaluated **because `select`/`ignore` filtered everything out of a profile that
     *does* have registered rules** (possible for `fast` once Story 02.0 lands, e.g.
     `ignore = ["DS1"]`) → a **new**, distinct `pending` message:
     `"all fast rules were excluded by select/ignore"` - this is the case Task 02's docstring
     anticipates and must not be confused with "not implemented."

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/rules.py` | Modify - add `effective_rules` |
| `src/docsentinel/engine.py` | Modify - `scan()` body; `ANALYZERS` docstring clarifies the key is a rule code |
| `tests/test_rules.py` | Modify - add resolver tests |
| `tests/test_scan.py` | Modify - add engine-level selection tests (register a fake rule + analyzer via a fixture, assert it is/isn't included under various `select`/`ignore`) |

## Symbols / fields

`src/docsentinel/rules.py` (additions):

| Symbol | Kind | Signature | Notes |
|--------|------|-----------|-------|
| `matches_selector(code: str, selector: str) -> bool` | function | - | `code == selector or code.startswith(selector)`. |
| `effective_rules(available: Iterable[str], select: tuple[str, ...], ignore: tuple[str, ...]) -> tuple[str, ...]` | function | - | `available` sorted first for deterministic output order; empty `select` means "all of `available`"; then drop anything matched by `ignore`. |

`src/docsentinel/engine.py` (`scan()` body, in order):

1. Resolve `settings` and `documents` (unchanged from today).
2. `profile_codes = tuple(code for code, rule in RULES.items() if rule.profile == settings.profile)`
3. `active_codes = effective_rules(profile_codes, settings.select, settings.ignore)`
4. `findings = tuple(f for code in active_codes if code in ANALYZERS for f in ANALYZERS[code](directory, documents))`
5. Build `pending` per the Decision's §5 branching (three cases: ran something / profile has
   nothing registered / everything filtered out).
6. Build `notice` per the same branching.
7. Return `ScanResult(settings.profile, documents, findings, active_codes, pending, notice=notice)`
   - `enabled_rules` is now `active_codes` (the codes actually evaluated this run), replacing
     today's `tuple(ANALYZERS)` (which was "every registered analyzer regardless of profile or
     selection" - correct for an empty registry, wrong once one exists).

## Tests

`tests/test_rules.py` additions:
- `test_matches_selector_exact_and_prefix` - `"DS101"` matches selectors `"DS101"`, `"DS1"`,
  `"DS"`; does not match `"DS102"` or `"DS2"`.
- `test_effective_rules_empty_select_means_all` - `select=()` returns all of `available`, sorted.
- `test_effective_rules_ignore_wins_over_select` - a code present in both `select` and `ignore`
  (directly, or via overlapping prefixes) is excluded from the result.
- `test_effective_rules_unmatched_selector_is_inert` - `select=("DS999",)` against
  `available=("DS101",)` returns `()`, no exception.

`tests/test_scan.py` additions (use a `pytest` fixture that registers a throwaway `Rule`
+ `ANALYZERS` entry for the test and tears both down afterward - see Task 01's Constraints on
not leaking global-registry state between tests):
- `test_scan_runs_analyzer_for_active_profile` - a fake `fast`-profile rule/analyzer pair is
  invoked when `profile="fast"`, not invoked when `profile="standard"`.
- `test_scan_respects_select` - `select=("DS1",)` includes the fake rule; `select=("DS9",)`
  excludes it.
- `test_scan_respects_ignore_over_select` - `select=("DS1",), ignore=("DS1",)` excludes it.
- `test_scan_notice_reflects_rules_evaluated` - with the fake rule active, `notice` contains
  "evaluated" and not "not implemented"; `enabled_rules == ("DS1??",)` (the fake code).
- `test_scan_notice_distinguishes_unimplemented_profile_from_filtered_out` - `profile="standard"`
  (nothing registered) keeps today's `pending` wording; `profile="fast"` with the fake rule
  present but `ignore=("DS1",)` wiping it out produces the **new** filtered-out `pending` message
  from Decision §5, not the "not implemented" one.

## Success criteria

- [ ] `ScanResult.enabled_rules` reflects codes actually evaluated this run, never the full
      static registry regardless of selection.
- [ ] The three `notice`/`pending` branches in Decision §5 are each covered by a test - the
      "not implemented" wording is never produced when a rule genuinely ran, and "evaluated"
      wording is never produced when nothing ran.
- [ ] `tests/test_scan.py`'s existing M0 test, `test_empty_scan_is_inventory_not_detection`,
      still passes unmodified - with the real registry still empty for `fast` (Story 02.0 not
      yet landed at the point this task ships), `scan()` on a document-free tree must still
      report the original "not implemented" notice and `enabled_rules == ()`.

## Constraints

- Full type annotations throughout; `Iterable` import from `collections.abc`, matching this
  project's existing style elsewhere.
- `effective_rules` must be a pure function (no global-state reads) so Task 01's test-isolation
  pattern is not required for it specifically - only the fixture-based tests touching the real
  `RULES`/`ANALYZERS` globals need teardown.
- Do not change `Analyzer`'s type alias (`Callable[[Path, tuple[Document, ...]], tuple[Finding, ...]]`)
  - only the *meaning* of `ANALYZERS`'s keys changes (arbitrary name → rule code), not the
    callable shape.
