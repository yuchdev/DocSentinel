# Task 04 — `FactCheckClient` Protocol, data contracts and backend registry

**Parent story:** [Story 01.0](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/README.md)  
**Role:** Python Expert  
**Depends on:** [Task 02](./02-threat-model-fact-check-gating.md) (verdict not BLOCK). Its threat-7
mitigation (static module map) is a standing input.

> **Amended 2026-11-21 (mining layer, plan contract C9).** The module is
> `src/docsentinel/fact_check/protocol.py` in a new `docsentinel.fact_check` package, not
> `detectors/fact_check_protocol.py`. Backends do network I/O, so they stay out of `mining/`; they
> are not rule analyzers, so they stay out of `detectors/` (importing a `docsentinel.detectors`
> submodule runs every rule registration in the package `__init__`, which a backend must not
> depend on).

> **Amended 2026-11-23 (threat model).** Applies
> [threat model 0010 fact-check gating](/docs/security/threat-model-0010-fact-check-gating-2026-11-23.md)
> amendment A6 (mitigation M7, finding FC-7) and the Task 04 parts of M5 and M8:
> `BACKEND_NAME_PATTERN` is always applied with `re.fullmatch`; the `FactCheckError` and
> constructor docstrings carry the key-containment contract; no `fact_check/` module reads the
> environment. Changed: steps 2, 4, 5 and 6, and the acceptance criteria.

## Goal

Create the package `src/docsentinel/fact_check/` with an `__init__.py` that imports nothing, and the
module `src/docsentinel/fact_check/protocol.py`. The module uses only the standard library and
`typing`, with no `httpx`, no `config`, no `detectors` and no `mining` import. It holds the
backend-independent contract that `DS302` and every backend are written against:

- `Verdict`
- `FactCheckError`
- `FactCheckResult`
- `FactCheckClient`
- the two-part backend registry

## Inputs

- Contracts [C2](/docs/roadmap/0010-fact-check/plan.md#c2--backend-protocol) and
  [C3](/docs/roadmap/0010-fact-check/plan.md#c3--api-key-environment-variable-naming); the story's
  [interface contracts](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/README.md#interface-contracts)
  and decision S10.
- ADR 0007 (Task 01), which records the registry split chosen here.
- The `Protocol` precedents in `/src/docsentinel/telemetry/extensions.py` and ADR 0002.

## Steps

1. **`Verdict`**: a `Literal["true", "false", "mixed", "unverifiable"]` alias, plus
   `VERDICTS: Final[frozenset[str]]` holding the same four values. `REPORTABLE_VERDICTS:
   Final[frozenset[str]] = frozenset({"false", "mixed"})` is the set `DS302` reports.
2. **`FactCheckError(RuntimeError)`**: the one exception a backend may raise from `check_claim`. Its
   docstring states the message contract: no response body, no request header, no key, no claim
   text, at most 200 characters. Callers pass the message through `safe()` before logging it.
   *Amended 2026-11-23 (threat model, M5):* the docstring also states that a backend may raise
   `FactCheckError` from its constructor (for example on key-shape validation) with the same fixed
   message contract, and that it is raised without exception chaining (`from None`), because a
   transport exception (`h11`/`httpx`) can carry the full `Authorization` header value.
3. **`FactCheckResult`**: a frozen dataclass with `verdict`, `confidence`, `backend` and
   `citations=()`. `__post_init__` raises `FactCheckError`, not `ValueError`, so that a buggy
   backend still fails soft in `DS302`'s loop. It raises when any of these holds:
   - `verdict` is not in `VERDICTS`;
   - `confidence` is not a finite `int`/`float` in `[0.0, 1.0]`, or is a `bool`;
   - `backend` does not match `BACKEND_NAME_PATTERN`;
   - `citations` is not a tuple of `str`, has more than `MAX_CITATIONS` (proposed 8) entries, or has
     an entry longer than `MAX_CITATION_CHARS` (proposed 500) characters.

   `DS302` does not use `citations` in this milestone, and the Lenz client leaves it empty.
4. **`FactCheckClient`**: a `@runtime_checkable` `Protocol` with exactly `name: str`,
   `API_KEY_ENV_VAR: ClassVar[str]` and `check_claim(self, claim: str) -> FactCheckResult`. `close()`
   is optional and duck-typed (C2). The docstring documents the construction convention, which the
   Protocol cannot express: a backend class must be constructible as `cls(api_key=<str>)`, and its
   `__repr__` must not reveal the key. *Amended 2026-11-23 (threat model, M5/M8):* the backend
   stores the key only in a private attribute, never reads `os.environ` or calls `os.getenv` (the
   key arrives only through the constructor), and never reads `LENZ_API_KEY` or any other tool's
   variable.
5. **Naming:**
   - `BACKEND_NAME_PATTERN = r"^[a-z][a-z0-9]{0,31}$"`.
   - *Amended 2026-11-23 (threat model, A6/M7):* the pattern is applied with `re.fullmatch`
     everywhere it is used (`expected_api_key_env_var` and `FactCheckResult.__post_init__`), never
     with `re.match` or `re.search`. With `re.match`, `$` matches before a final `\n`, so
     `"lenz\n"` would pass and could build an environment-variable name or a finding `message`
     with an embedded newline. Compile it once as a module constant; a non-`str` name is refused
     the same way.
   - `expected_api_key_env_var(name) -> str` returns `f"DOCSENTINEL_FACTCHECK_{name.upper()}_API_KEY"`,
     per C3. It raises `ValueError` for a name that does not fully match the pattern. Callers that
     handle configuration values check membership first (Task 05 step 3), so this `ValueError`
     never reaches a user for a configured name.
6. **Registry.** This is a split design so that config validation never imports `httpx`:
   - `FACT_CHECK_BACKEND_MODULES: Final[Mapping[str, str]]` is a `MappingProxyType` holding
     `{"lenz": "docsentinel.fact_check.lenz"}`. It is static and is the only source of
     module names that are ever imported.
   - `config.py` validates `fact_check_backend` against `FACT_CHECK_BACKEND_NAMES`, which Task 03
     defines in `config.py` itself. It is not imported from this module, so that `config.py` never
     depends on the `fact_check` package and the dependency direction of contract C9 stays one-way
     (detectors import both `config` and `fact_check`; neither imports the other). A drift test keeps
     `set(FACT_CHECK_BACKEND_MODULES) == config.FACT_CHECK_BACKEND_NAMES`.
   - `FACT_CHECK_BACKENDS: dict[str, type[FactCheckClient]] = {}` is filled by each backend module
     when it is imported (Story 03.0 Task 03). Tests may register a fake here.
   - `load_backend(name: str) -> type[FactCheckClient]` works as follows:
     1. Return `FACT_CHECK_BACKENDS[name]` if the name is already registered.
     2. Otherwise, if `name` is a key of `FACT_CHECK_BACKEND_MODULES`, import exactly that mapped
        module with `importlib.import_module` and look the name up again.
     3. Otherwise raise `KeyError`.
     4. Before returning, verify the class: `cls.name == name`,
        `cls.API_KEY_ENV_VAR == expected_api_key_env_var(name)`, and `check_claim` is callable. If
        any check fails, raise `TypeError`.

     An `ImportError` from the mapped module propagates to the caller, and Task 05 turns it into a
     fail-soft skip. `load_backend` never imports a name that comes from a configuration value
     unless that name is a key of the static map.
     *Amended 2026-11-23 (threat model, M7):* `importlib.import_module` is only ever called with a
     value of `FACT_CHECK_BACKEND_MODULES`, never with `name` or any string derived from it.
7. Report a `Docs impact:` line (trigger A: new module, new Protocol).

## Deliverables

- `/src/docsentinel/fact_check/__init__.py` (new, imports nothing).
- `/src/docsentinel/fact_check/protocol.py` (new).
- The module may be imported eagerly by `detectors/fact_check.py`, because it uses only the
  standard library. `config.py` never imports it.

## Acceptance criteria

- [ ] A minimal class with only `name`, `API_KEY_ENV_VAR` and `check_claim` passes
      `isinstance(obj, FactCheckClient)`. Removing any one of the three makes the check fail.
- [ ] `FactCheckResult` construction rejects every invalid case in step 3 with `FactCheckError`.
      This includes `confidence=True` and `float("nan")`.
- [ ] `expected_api_key_env_var("lenz") == "DOCSENTINEL_FACTCHECK_LENZ_API_KEY"`. Names such as
      `"Lenz"`, `"le-nz"`, `""` and a 33-character name raise `ValueError`.
- [ ] *Amended 2026-11-23 (threat model, M7):* `"lenz\n"`, `"lenz "`, a full-width letter,
      `"../x"` and `"docsentinel.fact_check.lenz"` are refused by `expected_api_key_env_var`, and
      `FactCheckResult(backend="lenz\n", ...)` raises `FactCheckError`. With
      `importlib.import_module` patched, it is never called with an unmapped name.
- [ ] *Amended 2026-11-23 (threat model, M8):* no module under `src/docsentinel/fact_check/` reads
      `os.environ`, calls `os.getenv` or contains `LENZ_API_KEY`
      (`tests/unit/test_fact_check_env_reads.py`, Task 06).
- [ ] `load_backend` returns a pre-registered fake without importing anything. It raises `KeyError`
      for an unknown name and `TypeError` for a class whose `API_KEY_ENV_VAR` does not follow C3. It
      imports only modules listed in `FACT_CHECK_BACKEND_MODULES` (checked with a patched
      `importlib.import_module`).
- [ ] Importing `docsentinel.fact_check.protocol` does not import `httpx`, `docsentinel.detectors`
      or `docsentinel.mining` (checked in a fresh interpreter).
      `set(FACT_CHECK_BACKEND_MODULES) == config.FACT_CHECK_BACKEND_NAMES` (drift test).
- [ ] `tests/unit/test_fact_check_layering.py` (Task 06) is green: the package imports only the
      standard library, `httpx` (in `lenz.py` only, Story 03.0) and `docsentinel.log`, and
      `fact_check/__init__.py` imports nothing.
- [ ] The module is fully typed, passes ruff, and its docstrings follow
      `/docs/dev/python_coding_standard.md`.

## Test expectations

Testing is done in [Task 06](./06-fixtures-and-tests.md), in `tests/unit/test_fact_check_protocol.py`
and `tests/unit/test_fact_check_layering.py`.

## Out of scope

- Any concrete backend (Story 03.0).
- `DS302` detection logic (Task 05).
- Retry or timeout policy, which belongs to each backend class (C4).
