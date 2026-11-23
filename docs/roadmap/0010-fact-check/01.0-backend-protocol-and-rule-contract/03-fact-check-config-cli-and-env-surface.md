# Task 03: `fact_check_*` config keys, `--use-external-api`, and the `rules`/`doctor` lines

**Parent story:** [Story 01.0](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/README.md)  
**Role:** Python Expert  
**Depends on:** [Task 02](./02-threat-model-fact-check-gating.md) must be done first (threat model verdict not BLOCK).
[Task 04](./04-factcheckclient-protocol-and-data-contracts.md) supplies the module map that must equal the static name set defined here. The gate helper
`resolve_external_api_gate` comes from [Task 05](./05-ds302-registration-and-engine-dispatch.md) and is needed for the `doctor` line.
Tasks 03, 04 and 05 may land as one change set.

> **Amended 2026-11-21 (owner ruling Q3, plan contract C10, ADR 0007 Contract 7).** A sixth key,
> `fact_check_time_budget_seconds`, is added here.

> **Amended 2026-11-23 (threat model).** Applies
> [threat model 0010 fact-check gating](/docs/security/threat-model-0010-fact-check-gating-2026-11-23.md)
> amendment A2 (mitigation M6, finding FC-6) and the Task 03 parts of M1, M4 and M8: the `doctor`
> gate line is fixed text in every state, including a configuration error. Changed: step 5, the
> `doctor` and env-read acceptance criteria, and the test expectations.

## Goal

Add the invoker-facing and config-facing surface of `DS302`:

- six typed and validated `fact_check_*` keys;
- the `--use-external-api` flag on `scan` and `baseline`;
- the `rules` suffix;
- the `doctor` gate line.

`use_external_api` must never become a `Config` field, and the API key must never be read here.

## Inputs

- The story's [config reference](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/README.md#config-reference)
  and [CLI and library reference](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/README.md#cli-and-library-reference).
  These tables are normative.
- Contracts [C4](/docs/roadmap/0010-fact-check/plan.md#c4--fixed-transport-bounded-content) and
  [C5](/docs/roadmap/0010-fact-check/plan.md#c5--use_external_api-is-never-a-configuration-file-key).
- The Task 02 threat model (standing input), in particular the mitigations for threats 1, 3, 4, 6 and 7.
- `/src/docsentinel/config.py`: `_CONFIG_OPTIONS`, `Config`, the shared TOML/JSON builder,
  `_require_enum`, `_require_bounded_int`, `_finite_number`, `USER_SETTINGS_REFUSED_KEYS`.
- `/src/docsentinel/cli.py`: the `scan`/`baseline` parsers, the opt-in suffix helper, the `doctor`
  line helpers (follow the pattern of `_doctor_reference_scope_line`).

## Steps

1. **Config keys.** Add the six keys to `_CONFIG_OPTIONS` and to `Config`. Each gets an `:ivar`
   docstring line, plus the default, type and bounds from the config reference.
   - `fact_check_backend`: validate with `_require_enum` against
     `FACT_CHECK_BACKEND_NAMES: Final[frozenset[str]] = frozenset({"lenz"})`, which is defined in
     `config.py`. `config.py` never imports a `docsentinel.detectors` module, because that would run
     the package `__init__` and create an import cycle, and it never imports `docsentinel.fact_check`
     or `httpx` either (plan contract C9 keeps the dependency pointing from detectors to
     `fact_check`, never from `config`). A drift test (Task 06) keeps this set equal to the Task 04
     module map in `fact_check/protocol.py`.
   - `fact_check_min_salience` and `fact_check_min_confidence`: accept a finite `int` or `float` in
     the closed range `[0.0, 1.0]`. Reject `bool`, `NaN` and `inf`. Use the message style of
     `duplicate_similarity`.
   - `fact_check_max_claims_per_document` (1 to 50) and `fact_check_max_claims_total` (1 to 500):
     validate with `_require_bounded_int`. Extend it with an optional keyword-only `maximum`, or add
     an equivalent check. The message must name both bounds.
   - `fact_check_time_budget_seconds` (int, default `300`, 1 to 3600 inclusive): validate with the
     same `_require_bounded_int(..., maximum=3600)`. Refuse `bool` and `float` (including `300.0`).
     Message: `fact_check_time_budget_seconds must be an integer from 1 to 3600`. It is allowed in
     user settings and project config.
   - None of the six keys joins `USER_SETTINGS_REFUSED_KEYS`. The drift test for the refused set
     must stay green and unchanged.
2. **No consent key.** Do not add `use_external_api`, or any spelling of it, to `_CONFIG_OPTIONS` or
   `Config`. A file that names it gets the existing generic unknown-option `ConfigError`. Add no
   special-case code for it.
3. **CLI flag.** Add `--use-external-api` (`store_true`) to `scan` and `baseline`.
   - Pass the value as `scan(..., use_external_api=args.use_external_api)`.
   - The help text must say that it sends document-derived text to a third-party service and that a
     backend API key environment variable is also required.
   - `cli.py` reads neither `DOCSENTINEL_USE_EXTERNAL_API` nor any `DOCSENTINEL_FACTCHECK_*`
     variable. The env gate is read only by the Task 05 gate helper.
   - Do not add the flag to `doctor`, `init` or `rules`, or to `.pre-commit-hooks.yaml`.
4. **`rules` suffix.** List every code in `rules.EXTERNAL_API_RULES` as
   `DS302: External fact-check disagreement [requires --use-external-api and a backend API key; see docsentinel doctor]`.
   Do not change `Rule`, `opt_in_hint` or the existing `[opt-in: set ...]` suffix.
5. **`doctor` line.** Add one line after the deep-readiness lines, computed with
   `resolve_external_api_gate(settings, use_external_api=False)`:
   - when the gate is open: `fact-check gate: on (backend: <name>)`;
   - when the gate is closed: `fact-check gate: off (<reasons joined by "; ">)`. The reason strings
     are the same ones the WARNING uses (Task 05);
   - when the config failed to load: exactly `fact-check gate: unknown (configuration error)`.
     The error itself stays on the existing `doctor` error line; the gate line never echoes a
     `ConfigError` message, a key name from the repository or any other value.

   *Amended 2026-11-23 (threat model, A2/M6).* Every form of the line is built only from fixed
   text, the C3 variable name and the enum-validated backend name. `doctor` sees only the
   environment, never a flag. The line never reveals a key's value, length or format, only whether
   the named variable is set and not empty. The line honours `--no-user-settings` through the
   existing settings load.
6. Report a `Docs impact:` line covering triggers C (config), K (CLI) and P (public API).

## Deliverables

- `/src/docsentinel/config.py`
- `/src/docsentinel/cli.py`

## Acceptance criteria

- [ ] All six keys load with the documented defaults and bounds from standalone TOML (both file
      names), `[tool.doc_sentinel]`, `--config FILE.json` and the user-settings JSON. An injected
      `Config` carries them unchanged.
- [ ] Each invalid value raises `ConfigError` with an exact message: an unknown backend, a value
      outside `[0, 1]`, `NaN`, `bool`, `0`, `51` and `501`, and for the time budget `0`, `3601`,
      `True` and `300.0`. The CLI exits `2`.
- [ ] `use_external_api = true` in any of the four file kinds raises the existing unknown-option
      `ConfigError` (exit `2`). `Config` has no attribute of that name.
- [ ] `scan --use-external-api` and `baseline --use-external-api` forward `True`, and omitting the
      flag forwards `False`.
- [ ] `docsentinel rules` prints the `DS302` line exactly as in step 4. The listings of every other
      rule are byte-identical.
- [ ] `docsentinel doctor` prints exactly one `fact-check gate:` line in each of these states: env
      unset with no key, env `1` with no key, key only, both set, and config error. The output never
      contains the key's value. *Amended 2026-11-23 (threat model, M6):* in the config-error state
      the line is exactly `fact-check gate: unknown (configuration error)`, and the repository's
      offending key name appears in no `fact-check gate:` line.
- [ ] No code path in `config.py` or `cli.py` reads `DOCSENTINEL_USE_EXTERNAL_API` or a
      `DOCSENTINEL_FACTCHECK_*` variable, and no module contains `LENZ_API_KEY` (enforced by
      `tests/unit/test_fact_check_env_reads.py`, Task 06; amended 2026-11-23, threat model M8).
- [ ] *Amended 2026-11-23 (threat model, M1/M4):* `Config` and `_CONFIG_OPTIONS` hold no spelling
      of `use_external_api` (including the FC-1 near-miss list), and a key-shaped key such as
      `fact_check_lenz_api_key` is an unknown-option `ConfigError` whose message never contains
      the value. `/.pre-commit-hooks.yaml` stays free of `--use-external-api`.
- [ ] `import docsentinel`, `docsentinel rules` and `docsentinel doctor` do not import `httpx`.

## Test expectations

The tests are written in [Task 06](./06-fixtures-and-tests.md):

- `tests/unit/test_fact_check_config.py`
- the `rules`/`doctor` cases in `tests/integration/test_fact_check_gate_off_ds302.py`
- *Amended 2026-11-23 (threat model):* `tests/unit/test_fact_check_env_reads.py` (M8) and
  `tests/unit/test_fact_check_repo_hygiene.py` (M4)

Run `uv run pytest tests/unit tests/integration -q -k fact_check -p docsentinel.pytest_plugin`.
`tests/integration/test_rules_table.py` must stay green. That test is updated in
[Story 04.0 Task 03](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/03-rules-table-and-fault-class.md),
which lands in the same change as the registration.

## Out of scope

- The gate logic, the engine forwarding and the `pending` entry (Task 05).
- The Protocol and the registry (Task 04).
- User documentation (Story 04.0 Task 04).
