# Task 01 - Deep Opt-In Confirmation Gate

**Story:** [01.0 - Deep Profile Opt-In Gating & Dependency Plumbing](README.md)
**Depends on:** Milestone 0001 Story 01.0 (rule registry, `Config`, `select`/`ignore`,
`effective_rules`) and Story 03.0 Task 01 (the `pending`/`notice` branching and `_exit_code` shape
this task extends). This task writes the gate; Story 02.0 is the first thing it gates.

## Purpose

`profile = "deep"` must not, by itself, run anything heuristic. `deep` detectors load a model,
read full document contents, and emit *candidate* findings with expected false positives - so a
project (or a mis-set CI lane) that merely selects the profile must get an honest "nothing ran,
here's how to really enable it" result, never a silent multi-second model load. This task adds a
**second, explicit confirmation** - separate from profile selection - that a human deliberately
accepts the heuristic, slower `deep` behavior, and wires `engine.scan()` to refuse to run `deep`
analyzers until it is set.

## Decision this task implements (record precisely - do not improvise at implementation time)

1. **Confirmation is a distinct gesture from selecting the profile.** Three equivalent ways to
   confirm, checked with this precedence (most explicit wins; any one being truthy confirms):
   1. CLI flag `--i-understand-deep-is-heuristic` on the `scan` subcommand (`action="store_true"`).
   2. Environment variable `DOCSENTINEL_DEEP_CONFIRM` set to a truthy value (`"1"`, `"true"`,
      `"yes"`, case-insensitive; anything else, including unset/empty, is not confirmed).
   3. Config field `deep_confirm: bool = False` in `doc_sentinel.toml` / `[tool.doc_sentinel]`.
2. **The gate only matters for `profile == "deep"`.** For `fast`/`standard`, `deep_confirm` and the
   flag/env are inert (parsed, allowed, ignored) - they never change a non-deep run. Setting the
   flag on a `fast` run is not an error; it simply has no effect.
3. **Unconfirmed `deep` is a no-op-with-explanation, not an error.** When `profile == "deep"` and
   confirmation is absent, `engine.scan()` runs **zero** deep analyzers, returns empty `findings`,
   `enabled_rules == ()`, and a **new, distinct** `pending` message (see §4). Exit code is `0` (per
   Story 04.0 `deep` is advisory-only anyway) - selecting an unconfirmed profile is not a failure.
   This is deliberately the same *shape* as Milestone 0001 Story 01.0 Task 03's
   "all fast rules were excluded by select/ignore" branch: a true statement about why nothing ran,
   never confused with "not implemented."
4. **`pending` wording** for `deep`, in priority order (first matching case wins), replacing today's
   single `"deep detectors are not implemented in M0"` string:
   - **Deep not confirmed:** `"deep profile requires explicit opt-in: set deep_confirm = true, pass --i-understand-deep-is-heuristic, or set DOCSENTINEL_DEEP_CONFIRM=1 (deep checks are heuristic and may report false positives)"`.
   - **Confirmed but no deep rules registered yet** (true until Story 02.0 lands): keep an
     "no deep rules are registered" message - do not claim opt-in is missing when it is actually
     present; the honest reason is "nothing to run." Use
     `"deep profile confirmed, but no deep rules are registered"`.
   - **Confirmed, deep rules registered, but all filtered out by `select`/`ignore`:** reuse the
     Story 01.0 Task 03 filtered-out shape, worded for deep:
     `"all deep rules were excluded by select/ignore"`.
   - (The "deps missing" case is Task 02's; this task's branching assumes deps are present and
     leaves a clearly-marked insertion point for Task 02 to add the deps-missing message ahead of
     the "confirmed but nothing registered" case.)
5. **`deep_confirm` is resolved into the engine, not consumed in the CLI.** The CLI translates its
   flag/env into the same confirmation signal the config carries, so `scan()` sees a single
   resolved boolean and library callers (`docsentinel.scan(...)`) get identical behavior without
   touching argparse. Do **not** branch on `sys.argv` inside `engine.py`.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/config.py` | Modify - add `deep_confirm` field + validation |
| `src/docsentinel/engine.py` | Modify - resolve confirmation, gate deep analyzers, branch `pending`/`notice` |
| `src/docsentinel/cli.py` | Modify - `--i-understand-deep-is-heuristic` flag, env read, fold into resolved `Config` |
| `tests/test_config.py` | Modify - `deep_confirm` parsing/validation tests |
| `tests/test_scan.py` | Modify - engine-level gating tests |

## Symbols / fields

| Symbol | Kind | Signature / change | Notes |
|--------|------|--------------------|-------|
| `Config.deep_confirm` | field | `deep_confirm: bool = False` | New frozen-dataclass field, appended after `select`/`ignore` so existing keyword construction is unaffected. Validated as a real `bool` (TOML `true`/`false`), not a truthy string. |
| `_resolve_deep_confirm(settings: Config) -> bool` | function in `engine.py` | - | `settings.deep_confirm or _env_confirms()`. Pure except for the one `os.environ` read it delegates to `_env_confirms`. |
| `_env_confirms() -> bool` | function in `engine.py` | - | Reads `DOCSENTINEL_DEEP_CONFIRM`; returns `True` iff its lowercased value is in `{"1", "true", "yes"}`. Unset → `False`. |
| `cli` flag | `scan_parser.add_argument("--i-understand-deep-is-heuristic", action="store_true", dest="deep_confirm")` | - | When set, CLI constructs the resolved `Config` with `deep_confirm=True` (OR-ed with the file's value), so the flag can *add* confirmation but never *remove* it. |

## Validators (raise `ConfigError` - unchanged exception type)

- `deep_confirm`, if present, must be a TOML boolean (`isinstance(value, bool)`); a string
  `"true"` or an int `1` in the config file raises `ConfigError("deep_confirm must be true or
  false")`. (The *string* coercion only applies to the environment variable, which is inherently a
  string; the config file is typed TOML and must use a real boolean.)
- `deep_confirm` is accepted for every profile (not rejected on `fast`/`standard`); it is simply
  inert there. Do not cross-validate it against `profile`.

## Tests

`tests/test_config.py` additions:
- `test_deep_confirm_defaults_false` - `Config().deep_confirm is False`.
- `test_deep_confirm_true_loads` - `doc_sentinel.toml` with `deep_confirm = true` → `True`.
- `test_deep_confirm_non_bool_raises` - `deep_confirm = "true"` (string) → `ConfigError`.
- `test_deep_confirm_accepted_on_fast_profile` - `profile = "fast"` + `deep_confirm = true` loads
  without error (inert, not rejected).

`tests/test_scan.py` additions (use the Story 01.0 Task 03 fixture pattern that registers a
throwaway `deep` `Rule` + `ANALYZERS` entry and tears both down - see that task's Constraints on
not leaking global-registry state):
- `test_deep_unconfirmed_runs_nothing` - a fake `deep` rule/analyzer registered; `profile="deep"`,
  `deep_confirm=False`, no env, no flag → analyzer **not** invoked, `findings == ()`,
  `enabled_rules == ()`, and `pending` carries the explicit-opt-in message.
- `test_deep_confirmed_via_config_runs_rule` - same fixture, `Config(profile="deep",
  deep_confirm=True)` → analyzer invoked, finding returned.
- `test_deep_confirmed_via_env_var` - `monkeypatch.setenv("DOCSENTINEL_DEEP_CONFIRM", "1")`,
  `deep_confirm=False` in config → analyzer invoked.
- `test_env_var_non_truthy_does_not_confirm` - `DOCSENTINEL_DEEP_CONFIRM="maybe"` → not confirmed.
- `test_flag_confirmation_via_cli` - `main(["scan", str(tmp_path), "--profile", "deep",
  "--i-understand-deep-is-heuristic"])` with a fake deep rule present → analyzer runs; without the
  flag (and no env/config) → the opt-in `pending` message is printed and no analyzer runs.
- `test_confirmed_but_nothing_registered_pending` - real registry empty for `deep`,
  `profile="deep"`, confirmed → the "confirmed, but no deep rules are registered" message, **not**
  the opt-in-missing one and **not** "not implemented."
- `test_deep_confirm_inert_on_fast` - `profile="fast"`, `deep_confirm=True` → identical result to
  `deep_confirm=False` (no behavior change on non-deep profiles).

## Success criteria

- [ ] `profile = "deep"` without any confirmation gesture runs zero deep analyzers and emits the
      explicit-opt-in `pending` message - proven by a test that would fail if the analyzer ran.
- [ ] Any one of the three confirmation channels (config field, env var, CLI flag) independently
      enables deep; the flag/env can only *add* confirmation, never override a config `true` back
      to `false`.
- [ ] `deep_confirm` is a real `bool` in `Config`; a string in the config file is a `ConfigError`.
- [ ] No deep-gating branch reads `sys.argv` or argparse state inside `engine.py` - the engine
      sees a single resolved signal, so `docsentinel.scan(config=...)` library callers behave
      identically to the CLI.
- [ ] `fast`/`standard` runs are byte-identical whether or not `deep_confirm`/the flag/the env is
      set - the gate is `deep`-only.

## Constraints

- Full type annotations; no bare `except:`; `ConfigError` stays the single config exception type.
- `_env_confirms` is the **only** place this task reads the environment - do not scatter
  `os.environ` reads; one helper, unit-testable via `monkeypatch`.
- Do not add a `--no-deep` / disable flag or a numeric confirmation level - exactly one binary
  "confirmed / not confirmed" signal with three equivalent sources. Keep it minimal until a real
  use case demands more.
