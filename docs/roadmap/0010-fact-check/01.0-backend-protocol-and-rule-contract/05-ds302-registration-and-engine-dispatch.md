# Task 05: DS302 registration, gate helper, `detect()` and engine dispatch

**Parent story:** [Story 01.0](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/README.md)  
**Role:** Python Expert  
**Depends on:** [Task 04](./04-factcheckclient-protocol-and-data-contracts.md). The Task 02 threat model is a standing input.
Story 02.0 (`mining/salience.py`, behind the `select_candidates` wrapper in this module) and
Story 03.0 (the Lenz client, `fact_check/lenz.py`) are reached only through lazy
imports on the open-gate path. Until they land, that path is covered only by mock tests that inject
both.

> **Amended 2026-11-21 (owner rulings Q1–Q4, plan contract C10, ADR 0007 Contracts 6–9).** Steps 5
> and 6 change: confidence leaves `message` for `value` (Q2), `_check_candidates` enforces the time
> budget (Q3), an unrecognised verdict arrives as `FactCheckError` and is skipped (Q4), and a closed
> gate removes `DS302` from `rules_evaluated` (Q1).

> **Amended 2026-11-23 (Story 05.0, plan contract C11).** Steps 4.4 and 4.5 (extract, then
> `select_candidates`) become one call, `candidates = collect_candidates(root, documents, config)`.
> `collect_candidates` is the shared candidate source that `extract-facts` also uses
> ([Story 05.0 Task 01](/docs/roadmap/0010-fact-check/05.0-extract-facts-cli/01-shared-candidate-collection-and-public-api.md)).
> If this task lands first, implement steps 4.4–4.5 as written, and Story 05.0 Task 01 replaces
> them with the call without changing behaviour. The gate, the backend loading,
> `_check_candidates` and the finding format are unchanged.

> **Amended 2026-11-23 (threat model).** Applies
> [threat model 0010 fact-check gating](/docs/security/threat-model-0010-fact-check-gating-2026-11-23.md)
> amendments A3, A4, A5 and A7 and mitigations M1, M2, M3, M5, M6, M7, M8, M9, M10 and M11
> (findings HIGH FC-5, MEDIUM FC-3 and FC-10, and FC-1, FC-2, FC-7, FC-8, FC-11). Changed: step 3
> (the gate helper type-checks its `bool` input and checks backend membership before deriving the
> key variable), step 4.2 to 4.6 (key read with `os.environ.get` inside the constructor call;
> construction and `check_claim` wrapped so a backend or transport exception is re-raised as a
> type-name-only `RuntimeError` with no exception chain; this replaces "propagates" in S10),
> step 5 (the counts-only INFO line is required; `citations` is never echoed), step 6, and the
> acceptance criteria. These are merge-gate conditions of the threat model verdict.

## Goal

Register `DS302` and implement its self-gating `detect()`. Wire `use_external_api` through
`engine.scan()` to analyzers that declare it, following the same pattern as `link_root`. When the
gate is closed, surface it as one WARNING and one `ScanResult.pending` entry (owner ruling D5).

## Inputs

- Contracts [C1](/docs/roadmap/0010-fact-check/plan.md#c1--dual-independent-consent-gates),
  [C5](/docs/roadmap/0010-fact-check/plan.md#c5--use_external_api-is-never-a-configuration-file-key),
  [C7](/docs/roadmap/0010-fact-check/plan.md#c7--extraction-reuse-no-second-nlp-pipeline),
  [C9](/docs/roadmap/0010-fact-check/plan.md#c9--layering-mining-detectors-fact-check-backends),
  [C8](/docs/roadmap/0010-fact-check/plan.md#c8--fail-soft-on-the-network-never-on-consent).
- The story's [interface contracts](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/README.md#interface-contracts)
  and [gate reporting table](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/README.md#how-the-gate-is-reported-decision-s9-detail).
  The detect sketch there is illustrative. Where it differs from this task, this task wins.
- The Task 02 threat model: the mitigations for threats 2, 3, 5, 6, 8, 9 and 10.
- `/src/docsentinel/engine.py` (`_analyzer_accepts_link_root`, `_run_analyzer`, `scan()`, the
  `pending` branches), `/src/docsentinel/detectors/contradictions.py` (the lazy-import and
  document-reading pattern), `/src/docsentinel/detectors/__init__.py`, `/src/docsentinel/rules.py`.

## Steps

1. **`rules.py`.** Add `EXTERNAL_API_RULES: Final[frozenset[str]] = frozenset({"DS302"})`. Leave
   `Rule` and `opt_in_satisfied` unchanged.
2. **`detectors/fact_check.py` (new).** Module-level imports are limited to the standard library,
   `docsentinel` internals (including `docsentinel.mining.nlp`, which `DS301`'s
   `contradictions.py` also imports eagerly) and `docsentinel.fact_check.protocol`. The module must not import
   `httpx`, `docsentinel.mining.claims`, `docsentinel.mining.salience`,
   `docsentinel.mining.clustering` or any backend at import time. Register `DS302` with the exact literal from
   ADR 0007. Import the module from `/src/docsentinel/detectors/__init__.py` next to
   `contradictions`.
3. **Gate helper.** It uses only the standard library and imports no backend module.
   *Amended 2026-11-23 (threat model, A3/M1/M2/M3/M7/M8).*
   - `USE_EXTERNAL_API_ENV: Final = "DOCSENTINEL_USE_EXTERNAL_API"`. This helper is the only place
     the env variable is read. `detectors/fact_check.py` is the only module under
     `src/docsentinel/` that reads `DOCSENTINEL_USE_EXTERNAL_API` or a `DOCSENTINEL_FACTCHECK_*`
     variable, and no module under `src/docsentinel/` reads, or contains the string,
     `LENZ_API_KEY` (M8).
   - Consent is read only from the `use_external_api` argument and the environment, never from
     `Config`: no `getattr(config, ...)` for any consent spelling (M1).
   - `external_api_requested(use_external_api: bool) -> bool`: its first statement is
     `if not isinstance(use_external_api, bool): raise ConfigError("use_external_api must be True or False")`.
     It then returns a real `bool`,
     `use_external_api is True or os.environ.get(USE_EXTERNAL_API_ENV) == "1"` (M3). The env match
     is exact: it never calls `_env_confirms`, `.lower()`, `.strip()`, `int()` or `bool()` on the
     value (M2).
   - `ExternalApiGate` is a frozen dataclass with these fields: `requested: bool`, `backend: str`,
     `key_env_var: str`, `key_present: bool`. It has an `open` property. `reasons()` returns, in this
     order, `"pass --use-external-api (or set DOCSENTINEL_USE_EXTERNAL_API=1)"` when the gate was not
     requested and `f"set {key_env_var}"` when the key is absent. `skip_message()` returns
     `"DS302 skipped: " + "; ".join(reasons())`.
   - `resolve_external_api_gate(config, *, use_external_api: bool) -> ExternalApiGate`, in this
     order:
     1. Type-check `use_external_api` exactly as `external_api_requested` does (same
        `ConfigError`), and compute `requested` through that helper.
     2. If `config.fact_check_backend` is not in `FACT_CHECK_BACKEND_NAMES` or the
        `FACT_CHECK_BACKENDS` keys, raise
        `ConfigError("fact_check_backend must be one of: <sorted names>")`. This re-validates an
        injected `Config` and fails closed. Membership is checked **before** any name is derived,
        so an injected `Config(fact_check_backend="lenz\n")` raises `ConfigError`, never the
        `ValueError` of `expected_api_key_env_var` (M7).
     3. Only then `key_env_var` is `expected_api_key_env_var(config.fact_check_backend)`.
     4. `key_present` is `bool(os.environ.get(key_env_var))`. The value is never bound to a name
        that outlives this expression.
   - The WARNING, the `pending` entry and the `doctor` line use only `reasons()`, which is fixed
     text plus the C3 variable name; no value, path or exception text (M6).
4. **`detect(root, documents, config, *, use_external_api: bool = False)`.**
   1. Resolve the gate. If it is closed, log `logger.warning(gate.skip_message())` once and return
      `()`. Do this before reading any document, loading any pipeline or importing any heavy module.
   2. Call `load_backend(config.fact_check_backend)`. If it raises `ImportError` or `TypeError`, log
      one WARNING `DS302 skipped: backend <name> is unavailable (<exception type name>)` and return
      `()`. Never echo the exception message.
   3. *Amended 2026-11-23 (threat model, A4/M5).* Read the key with
      `os.environ.get(client_cls.API_KEY_ENV_VAR)` directly inside the constructor call
      (`client_cls(api_key=...)`). If the value is absent or empty at this point (the environment
      changed since the gate), log the gate WARNING (`skip_message()` of a re-resolved gate) and
      return `()`; no `KeyError` escapes. Log nothing that contains the key. Keep no copy on the
      module, on a `Finding` or in a closure. Wrap construction:
      - `FactCheckError` logs exactly one WARNING
        `DS302 skipped: backend <name> could not be initialised (FactCheckError)` and returns `()`;
        its message is not echoed;
      - any other exception is handled by the containment rule in step 4.7.
   4. Extract claims exactly as `DS301` does: a lazy `docsentinel.mining.claims` import,
      `mining.nlp.load_pipeline()`, and the same document filter and read (C7).
   5. Call `select_candidates(tuple(claims), config)`, the thin wrapper Story 02.0 Task 03 adds to
      this module; it lazily imports `docsentinel.mining.salience` itself.
   6. Call `_check_candidates(client, candidates, config)` inside `try`/`finally`. The `finally`
      calls `close()` when the client provides it.
   7. *Amended 2026-11-23 (threat model, A5/M5, HIGH FC-5).* **Exception containment.** Any
      exception other than `FactCheckError` raised by client construction, `check_claim` or
      `close()` is caught, its type name is kept, and after leaving the `except` block DS302
      raises `RuntimeError(f"DS302: backend {name} raised {type(exc).__name__}")` (in effect
      `from None`: the raise happens outside the handler, so `__cause__` and `__context__` are
      both `None`). The original message, arguments, traceback and chain are dropped, because a
      transport error (`h11` `Illegal header value`, re-raised by `httpx`) or a
      `UnicodeEncodeError` can carry the bearer key. `<name>` is the enum-validated backend name.
      No `exc_info=True`, `logger.exception` or `stack_info` on any `DS302` or backend path. This
      `RuntimeError` is the S10 programming error and propagates to the engine and CLI.
5. **`_check_candidates(client, candidates, config, *, clock: Callable[[], float] = time.monotonic)`.**
   `clock` is a test seam only; no configuration, environment or CLI path sets it. Process the
   candidates in their given order.
   - **Time budget (Q3).** Re-validate `config.fact_check_time_budget_seconds` with the `config.py`
     validator (fail closed, `ConfigError`). Take `deadline = clock() + budget` once, immediately
     before the first `check_claim`. Before each call, when `clock() >= deadline`, stop: log exactly
     one `logger.warning("DS302: time budget of %d s exhausted; %d of %d claim(s) not checked", ...)`
     (counts only, no path, no claim text) and return the findings built so far. Never send the
     remaining claims. Do not interrupt an in-flight call and add no `pending` entry.

   For each candidate:
   - Call `client.check_claim(candidate.text)` and catch `FactCheckError` (S10); every other
     exception follows the step 4.7 containment rule (amended 2026-11-23, threat model A5). On
     `FactCheckError`, log
     `logger.warning("DS302: fact-check failed for a claim in %s: %s", safe(path), safe(str(exc)))`
     and continue. The log line never contains the claim text. An unrecognised backend verdict
     reaches this branch as a `FactCheckError` (Q4) and is skipped the same way; it is never mapped
     to `mixed`.
   - Report a finding only when `result.verdict in REPORTABLE_VERDICTS` and
     `result.confidence >= config.fact_check_min_confidence`.
   - Build the `Finding`:
     - `rule="DS302"`, `path=candidate.claim.path`, `severity="warning"`, `type="unverified claim"`.
     - `value=f"{result.verdict} (confidence {result.confidence:.2f}): {candidate.text}"`. The
       suffix after the first `": "` is exactly the text that was sent (at most 1,000 characters).
       `value` is report-only (`compare=False`), so the confidence never enters the fingerprint (Q2).
     - `message` carries no confidence:
       `external fact-check: '<snippet>' rated <verdict> by <backend> - review to confirm`.
       `<snippet>` is `candidate.text` cut to 200 code points.
     - *Amended 2026-11-23 (threat model, M11):* a finding is built only from the validated
       `verdict`, the `.2f` confidence, the validated backend name and the candidate text.
       `result.citations` never reaches a `Finding`, a log record or a report.

   Sort the findings by `(path, message)`. Log the counts at DEBUG: candidates, sent, failed and
   reported; the per-document breakdown stays at DEBUG and may name `safe(path)` with a count,
   never claim text.

   *Amended 2026-11-23 (threat model, A7/M10, MEDIUM FC-10).* **Required INFO line.** Exactly one
   per `detect()` that passed both gates, emitted from a `finally` block so it is also logged when
   the loop stops early (time budget, or the step 4.7 `RuntimeError` mid-loop, with the counts so
   far), and none on a closed gate:

   ```text
   DS302: sent <n> claim(s) from <m> document(s) to backend <name>; <f> failed, <r> reported, <s> not sent (time budget)
   ```

   Integers and the enum-validated backend name only, passed as `%`-style logger arguments: no
   path, no claim text, no key-related value.
6. **`engine.py`.**
   - Add `use_external_api: bool = False` as a keyword-only parameter of `scan()`, next to
     `link_root`. A value that is not a `bool` raises `ConfigError("use_external_api must be True or False")`
     as the first statement of `scan()`, before any filesystem access. *Amended 2026-11-23 (threat
     model, M3):* the gate helper repeats the check (step 3), so a direct `detect()` call is
     covered too. The engine never reads `DOCSENTINEL_USE_EXTERNAL_API` or a key variable itself.
   - Add `_analyzer_accepts_use_external_api(analyzer)`, an `lru_cache`d copy of
     `_analyzer_accepts_link_root`.
   - `_run_analyzer` gains `use_external_api: Optional[bool] = None` and forwards it as a keyword
     only when the value is not `None` and the analyzer declares it.
   - Resolve the gate only when `EXTERNAL_API_RULES.intersection(active_codes)` is non-empty, right
     after `opt_in_off` is computed and before `_log_rule_plan`. Forward
     `external_api_requested(use_external_api)` (a bool) to the analyzers. When the resolved gate is
     closed, set `pending` to `(gate.skip_message(),)` on the branch that today sets `pending = ()`
     because rules are active.
   - **Evaluated count (Q1).** Let `external_off` be the number of active `EXTERNAL_API_RULES` codes
     when the resolved gate is closed, else `0`. Compute
     `rules_evaluated = len(active_codes) - len(opt_in_off) - external_off` and pass it to the
     unchanged `evaluated_notice()`. `_log_rule_plan` gains `external_off: int = 0` and subtracts it
     from its `evaluated` count; the INFO text is unchanged. `DS302` never enters `opt_in_off`, and no
     `ScanResult` field is added. When `DS302` is not active, `external_off` is `0` and `notice`,
     `pending`, `rules_evaluated` and the INFO line are byte-identical to master.
   - The engine never logs the gate WARNING itself; `detect()` is the only place that does, so a scan
     logs it exactly once.
   - The deep-wide early returns (not confirmed, dependencies unavailable) stay byte-identical and
     add no `DS302` entry.
7. Leave `/src/docsentinel/__init__.py` (the exports and `scan`'s identity) and the pytest plugin
   unchanged. Report a `Docs impact:` line covering triggers R, P and A.

## Deliverables

- `/src/docsentinel/detectors/fact_check.py` (new)
- `/src/docsentinel/detectors/__init__.py`
- `/src/docsentinel/rules.py`
- `/src/docsentinel/engine.py`
- The Story 04.0 Task 03 rows, which land in the same change (see the acceptance criteria)

## Acceptance criteria

- [ ] `DS302` appears once in `RULES` and once in `ANALYZERS` with the ADR literal and no `opt_in_option`.
- [ ] A confirmed deep scan with `DS302` selected and gate 2 closed has these properties:
  - exactly one WARNING that names only the missing prerequisites;
  - `pending == ("DS302 skipped: <reasons>",)` and no `DS302` findings;
  - `DS302` is not counted: with `DS301` and `DS302` active, `rules_evaluated == 1` and
    `notice == "1 deep rule(s) evaluated (heuristic, advisory-only)."`;
  - `DS301` still runs;
  - exit code `0`;
  - no document read by `DS302`, and no `httpx`, `mining.salience`/`mining.clustering` or backend
    import.
- [ ] A deep scan with `DS302` removed by `select`/`ignore` resolves no gate, adds no `pending` entry
      and logs no WARNING.
- [ ] Unconfirmed deep scans, standard scans and fast scans give `ScanResult` output identical to
      master's.
- [ ] `use_external_api` is forwarded only to analyzers that declare it. `scan(use_external_api=...)`
      with `"false"`, `"1"`, `1`, `0` or `None` raises `ConfigError` before discovery. *Amended
      2026-11-23 (threat model, M3):* `external_api_requested("false")` raises `ConfigError`, and a
      direct `detect(..., use_external_api="false")` with the key set raises and sends nothing.
- [ ] *Amended 2026-11-23 (threat model, M7):* an injected `Config(fact_check_backend="lenz\n")`
      makes `resolve_external_api_gate` raise `ConfigError`, never `ValueError`.
- [ ] One candidate raising `FactCheckError` is skipped, every other candidate is still checked, and
      no claim text is logged. *Amended 2026-11-23 (threat model, A5/M5):* any other exception from
      client construction, `check_claim` or `close()` is replaced by
      `RuntimeError("DS302: backend <name> raised <type name>")` with `__cause__ is None` and
      `__context__ is None`, and that `RuntimeError` propagates (the S10 programming error). A
      `FactCheckError` from the constructor gives the fixed `could not be initialised` WARNING and
      `()`. A key that disappears between gate and construction gives the gate WARNING and `()`.
- [ ] *Amended 2026-11-23 (threat model, M10):* a gate-open `detect()` logs exactly one INFO counts
      line in the step 5 format, also when the step 4.7 `RuntimeError` propagates; a closed gate
      logs none; the record contains no path and no claim text.
- [ ] *Amended 2026-11-23 (threat model, M11):* a `citations` marker from the backend appears in no
      finding, log record or rendered packaged template.
- [ ] *Amended 2026-11-23 (threat model, M8):* only `detectors/fact_check.py` reads
      `DOCSENTINEL_USE_EXTERNAL_API` or a `DOCSENTINEL_FACTCHECK_*` variable; no `src/docsentinel/`
      module contains `LENZ_API_KEY`; with only `LENZ_API_KEY` set and the flag given, the gate is
      closed and the fake backend records no call.
- [ ] With an injected clock past the deadline after the first call, exactly one claim is sent, one
      budget WARNING is logged and the first claim's finding (if any) is kept.
- [ ] No `DS302` `message` contains the confidence; two runs with the same verdict and different
      confidence give equal baseline fingerprints.
- [ ] The key value never appears in any log record, `Finding`, `ScanResult`, `pending` entry or
      `repr`. This is asserted with a sentinel key in Task 06. *Amended 2026-11-23 (threat model,
      M5):* neither the sentinel nor its first eight characters appear on stdout, stderr, the
      per-run log file (including tracebacks) or any rendered packaged template, on every path
      including the step 4.7 containment path.
- [ ] The rules-table, fault-class and finding-types drift tests are green in the same change that
      registers `DS302` ([Story 04.0 Task 03](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/03-rules-table-and-fault-class.md)
      content). They are never red on master.

## Test expectations

The tests are written in [Task 06](./06-fixtures-and-tests.md). Run
`uv run pytest -p docsentinel.pytest_plugin` (the full suite) and
`uv run docsentinel scan . --format json`. The scan must exit `0` with zero `DS302` findings.

## Out of scope

- Scoring internals (Story 02.0).
- Transport (Story 03.0).
- Adding `DS302` to the `opt_in_off`/`Rule.opt_in_option` opt-in machinery, which the owner ruled
  against (D5). The Q1 count adjustment in step 6 is the only `rules_evaluated` change.
- Retries or a circuit breaker.
