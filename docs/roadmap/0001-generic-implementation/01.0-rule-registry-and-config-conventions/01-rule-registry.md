# Task 01 - Rule Registry

**Story:** [01.0 - Rule Registry & Config Conventions](README.md)

## Purpose

Every later detector, and `select`/`ignore` in Task 02, need one authoritative place that maps a
rule code (`DS101`) to its metadata (which profile it belongs to, a human title, a description,
a default severity). This task creates that registry with zero detectors in it - Story 02.0
populates it.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/rules.py` | Create |
| `tests/test_rules.py` | Create |

## Symbols / fields

`src/docsentinel/rules.py`:

| Symbol | Kind | Fields / signature | Notes |
|--------|------|---------------------|-------|
| `Rule` | `@dataclass(frozen=True)` | `code: str`, `profile: str`, `title: str`, `description: str`, `severity: str = "warning"` | Mirrors the field style of `models.Finding`/`models.Document` already in the codebase. |
| `RULES` | `dict[str, Rule]` module-level | - | The registry. Keyed by `Rule.code`. |
| `register_rule(rule: Rule) -> Rule` | function | - | Inserts into `RULES`, returns `rule` unchanged (so detector modules can do `MY_RULE = register_rule(Rule(...))` as a one-liner at import time). |
| `rules_for_profile(profile: str) -> tuple[Rule, ...]` | function | - | Returns registered rules whose `.profile == profile`, sorted by `.code`. Used by the `rules`/`doctor` CLI commands (Task 04) and by Task 03's resolver. |

## Validators

- `register_rule` raises `ValueError(f"Duplicate rule code: {rule.code}")` if `rule.code` is
  already in `RULES` - a code collision between two detector modules must fail at import time,
  not silently overwrite.
- `register_rule` raises `ValueError` if `rule.profile not in ("fast", "standard", "deep")` -
  same closed set `config.Config.profile` already validates, so a rule can never target a
  profile that does not exist.
- No validation of `code`'s shape (`DS\d{3}`) is required by this task - Task 02's config
  validation is where an *unknown* code in `select`/`ignore` is rejected; this task only owns
  registration, not selection.

## Tests (`tests/test_rules.py`)

- `test_register_rule_adds_to_registry` - registering a `Rule` makes it retrievable via `RULES`.
- `test_register_rule_rejects_duplicate_code` - registering the same code twice raises
  `ValueError`; use `pytest.raises` and a fixture that clears/restores `RULES` around the test
  (module-level mutable state must not leak between tests - see Constraints).
- `test_register_rule_rejects_unknown_profile` - `profile="nonsense"` raises `ValueError`.
- `test_rules_for_profile_filters_and_sorts` - register rules for two different profiles out of
  code order; assert `rules_for_profile("fast")` returns only the fast ones, sorted by code.

## Success criteria

- [ ] `RULES` is empty at interpreter start (no detector modules exist yet in this milestone,
      so nothing self-registers) - `len(RULES) == 0` is a valid assertion in this task's own
      tests, guarded by import isolation (see Constraints).
- [ ] `rules_for_profile` never mutates `RULES`.
- [ ] `docsentinel.rules` has no import-time side effects beyond defining `RULES = {}`.

## Constraints

- Full type annotations on every public symbol (project rule).
- `RULES` is mutable global state shared process-wide; tests that register rules **must** restore
  it afterward (a `pytest` fixture with `yield` + `RULES.clear()` / re-populate from a saved
  copy), so test order never changes behavior - this is the one piece of global state this
  codebase intentionally carries (`engine.ANALYZERS` already works the same way), so follow its
  existing pattern rather than inventing a new one.
- No bare `except:`; this task introduces no I/O, so no exception handling is expected at all.
