# 0007 - Fact-Check Backend Protocol, Dual Consent Gate and API-Key Convention

> **Status:** Proposed
>
> **Date:** 2026-11-21
>
> **Supersedes:** _(none)_
>
> **Superseded by:** _(none)_

## Context and Problem Statement

Milestone 0010 adds `DS302`, a second `deep`-profile rule. It sends a small, bounded set of
high-salience claims, extracted by the existing `DS301` pipeline (`mining/claims.py`,
`mining/nlp.py`), to an external fact-checking service. It reports a claim that the service
rates `false` or `mixed`. This is the first time DocSentinel sends document-derived text over
the network and the first time it handles a secret.

Today nothing in the package covers this:

- The deep profile's only consent gate, `deep_confirm`, means "I accept heuristic noise". It
  does not mean "I accept that my text leaves the machine" (plan problem P3).
- There is no pluggable boundary for an external verification service. A hard-coded call to one
  vendor would block a second provider (P2).
- Every configuration file is the untrusted layer (Milestone 0009, ADR 0005). A design that lets
  `docsentinel.toml` grant network consent or carry an API key would let a cloned repository
  exfiltrate text or a key (P4).
- Checking every sentence would scale cost, time and exposure with the corpus size (P5).

The question is which contract `DS302` is built against: how consent is given, where the
backend boundary sits, where the secret comes from, how a closed gate is surfaced, and where the
new modules live. The authoritative input is
[plan contracts C1 to C9](/docs/roadmap/0010-fact-check/plan.md#shared-contracts-authoritative),
the owner rulings D1 to D10 and Q1 to Q4 of 2026-11-21 in
[status.md](/docs/roadmap/0010-fact-check/status.md#notes--decisions), and the
[Story 01.0 design](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/README.md#design).

## Decision Drivers

1. **No untrusted layer grants egress or carries a secret.** Project TOML, `[tool.doc_sentinel]`,
   `--config FILE.json` and the user settings file can tune what is sent, never whether it is
   sent, and never hold the key (design principle 5, C5).
2. **One engine.** CLI, library and pytest plugin keep a single `engine.scan()` path (principle 1).
3. **Swappable backend.** A second provider is a new class and one registry entry, never a new
   call site in the detector (principle 6, C2).
4. **Fixed transport.** Base URL, timeout and response cap are class constants (C4).
5. **Fail soft on the network, never on consent.** A closed gate, a failed claim, an exhausted
   time budget or an unrecognised verdict never raises into `scan()` and never changes the exit
   code (C8).
6. **Honest reporting.** A rule that sent nothing is never presented as evaluated (owner ruling Q1),
   and every closed gate is visible on three surfaces (WARNING, `pending`, `doctor`; ruling D5).
7. **Stable fingerprints.** A rerun with the same verdict gives the same baseline fingerprint
   (ruling Q2).
8. **Bounded cost.** Claim caps bound volume; a per-scan time budget bounds wall-clock time
   (ruling Q3).
9. **Import discipline.** `import docsentinel` and every fast or standard scan never import `httpx`,
   spaCy or a backend module; the mining layer stays pure (C9).
10. **Minimal blast radius.** No new `ScanResult` or `Finding` field, no report-schema change, no
    change to `Rule`, `opt_in_satisfied`, `DS301` or the `deep_confirm` gate.

## Considered Options

Seven decision points. A to E are the ones the task spec names. F and G record how the owner
rulings Q1 to Q4 are realised.

**A. Consent surface for gate 2**

- (A1) Invoker-only: CLI flag `--use-external-api`, keyword `scan(use_external_api=)`, and the
  environment variable `DOCSENTINEL_USE_EXTERNAL_API=1` (exact match) (**chosen**, C1, C5, D3)
- (A2) A configuration key `use_external_api`, settable like `deep_confirm`
- (A3) Reuse `deep_confirm` alone as consent for egress

**B. Backend boundary**

- (B1) A structural `@runtime_checkable` `Protocol`, `FactCheckClient` (**chosen**, C2)
- (B2) An abstract base class
- (B3) A hard-coded Lenz call inside the detector

**C. Secret source**

- (C1) One environment variable per backend, `DOCSENTINEL_FACTCHECK_<BACKEND>_API_KEY`, declared by
  the backend class (**chosen**, C3, D4)
- (C2) One fixed name, `DOCSENTINEL_FACTCHECK_API_KEY`, shared by every backend
- (C3) A configuration key or a CLI argument

**D. Gate surfacing**

- (D1) One WARNING, one scoped `ScanResult.pending` entry and one `doctor` line; no
  `Rule.opt_in_option` retrofit (**chosen**, owner ruling D5)
- (D2) Retrofit `Rule.opt_in_option` with a shadow, non-file-settable `Config.use_external_api`
  field so the generic "opt-in rule(s) not enabled" notice names `DS302`

**E. Module placement**

- (E1) Backends in a new `docsentinel.fact_check` package beside `mining/` (**chosen**, C9)
- (E2) Backends under `detectors/`
- (E3) Backends inside `mining/`

**F. Evaluated count while the gate is closed (ruling Q1)**

- (F1) The engine subtracts the active `EXTERNAL_API_RULES` codes from `rules_evaluated` when the
  resolved gate is closed (**chosen**)
- (F2) Count `DS302` as evaluated anyway (the earlier draft; overruled by Q1)
- (F3) Put `DS302` into `ScanResult.opt_in_off` (this is the D2 retrofit; refused by D5)

**G. Where the backend confidence lives (ruling Q2)**

- (G1) In the report-only `Finding.value` (`compare=False`), as a fixed-format prefix before the
  exact text that was sent; `message` carries no confidence (**chosen**)
- (G2) A new report-only field `Finding.confidence`
- (G3) Leave confidence out of the finding altogether

## Decision Outcome

Chosen: **A1, B1, C1, D1, E1, F1, G1**, plus the per-scan time budget (ruling Q3) and the
unrecognised-verdict skip (ruling Q4) as specified in Contracts 7 and 8. Each choice is the only
one that satisfies drivers 1, 6 and 10 together. The contracts below are proposed signatures and
schemas, not code. `python-expert` implements them in the tasks listed under
[Validation / Rollout](#validation--rollout).

### Decisions recorded

| # | Decision | Source |
|---|---|---|
| R1 | Rule code `DS302` is reserved (next free after `DS301`; `DS107`, `DS111`, `DS119` to `DS123` stay reserved by Milestone 0004) | D1 |
| R2 | ADR number `0007` is this record | D2 |
| R3 | Fault class `unverified_claim` and finding type `unverified claim` are reserved for `DS302`; their rows land with the code (Story 04.0 Task 03) | Story 01.0 |
| R4 | `use_external_api` is never a `Config` field and never in `_CONFIG_OPTIONS`; a file naming it gets the existing generic unknown-option `ConfigError` | C5, D3 |
| R5 | The API key is read only by the backend construction path in `detectors/fact_check.py` (one `os.environ[...]` read passed straight into `cls(api_key=...)`) and is otherwise only tested for presence; `cli.py`, `config.py` and `engine.py` never read it | C3, S6 |
| R6 | Closed gate surfacing is WARNING plus scoped `pending` plus `doctor`; no `opt_in_option` retrofit | D5 |
| R7 | While either gate is closed, `DS302` is not counted in `rules_evaluated`, so `ScanResult.notice` does not count it (Contract 6) | Q1 |
| R8 | Backend confidence is carried in `Finding.value`, never in `message` (Contract 9) | Q2 |
| R9 | A per-scan time budget, `fact_check_time_budget_seconds`, bounds the network loop (Contract 7) | Q3 |
| R10 | An unrecognised backend verdict is skipped with a WARNING and never mapped to `mixed` (Contract 8). **Superseded 2026-11-27:** it is rated `unverifiable`, printed, never reported | Q4 |
| R11 | `httpx` becomes a declared direct dependency, imported only on the open-gate deep path | D6 |

### Contract 1: `engine.scan()` keyword (`/src/docsentinel/engine.py`)

```text
def scan(
    root: Union[Path, str] = ".",
    *,
    config: Optional[Config] = None,
    link_root: Optional[Union[Path, str]] = None,
    include: Optional[Sequence[str]] = None,
    exclude: Optional[Sequence[str]] = None,
    use_external_api: bool = False,
) -> ScanResult
```

- `use_external_api` is keyword-only and defaults to `False`, so no library caller migrates.
- A value that is not a `bool` (`isinstance(value, bool)` is false, so `0`, `1`, `"1"` and `None`
  all fail) raises `ConfigError("use_external_api must be True or False")`. The check is the
  first statement of `scan()`, before any filesystem access, so a caller bug never depends on the
  profile.
- The value is never stored on `Config`. The engine forwards
  `external_api_requested(use_external_api)` (Contract 3) as the keyword `use_external_api=` to an
  analyzer only when the analyzer's signature declares a keyword-acceptable parameter of that name
  (`_analyzer_accepts_use_external_api`, an `lru_cache`d mirror of `_analyzer_accepts_link_root`)
  and only when `rules.EXTERNAL_API_RULES.intersection(active_codes)` is non-empty.
- The deep-wide early returns (not confirmed; dependencies unavailable) are byte-identical to
  today and resolve no gate.

### Contract 2: `DS302` analyzer (`/src/docsentinel/detectors/fact_check.py`)

```text
def detect(
    root: Path,
    documents: tuple[Document, ...],
    config: Config,
    *,
    use_external_api: bool = False,
) -> tuple[Finding, ...]
```

- Resolves the gate first (Contract 3). A closed gate logs `gate.skip_message()` once at WARNING
  and returns `()` before reading a document, loading a pipeline or importing `httpx`,
  `mining.claims`, `mining.salience`, `mining.clustering` or any backend.
- `load_backend(config.fact_check_backend)` raising `ImportError` or `TypeError` logs one WARNING
  `DS302 skipped: backend <name> is unavailable (<exception type name>)` and returns `()`.
- Raises `ConfigError` only when an injected `Config` holds an invalid `fact_check_*` value
  (re-validation through the `config.py` validators, fail closed). Never raises for a closed gate,
  a network failure, an exhausted budget or an unrecognised verdict. Any other exception type is a
  programming error and propagates (S10).

The `Rule` registration literal, exactly:

```text
DS302 = rules.register_rule(
    rules.Rule(
        code="DS302",
        profile="deep",
        title="External fact-check disagreement",
        description=(
            "A high-salience claim is rated false or mixed by an external "
            "fact-checking backend."
        ),
        severity="warning",
    )
)
```

No `opt_in_option` and no `opt_in_values` (S2). `rules.ANALYZERS["DS302"] = detect`. The module
is imported by `/src/docsentinel/detectors/__init__.py` next to `contradictions`, eagerly, like
`DS301`.

### Contract 3: gate helper (`/src/docsentinel/detectors/fact_check.py`)

Standard library plus `docsentinel.config` and `docsentinel.fact_check.protocol` only. It imports
no backend module and no `httpx`.

```text
USE_EXTERNAL_API_ENV: Final[str] = "DOCSENTINEL_USE_EXTERNAL_API"

def external_api_requested(use_external_api: bool) -> bool
    # use_external_api or os.environ.get(USE_EXTERNAL_API_ENV) == "1"   (exact match)

@dataclass(frozen=True)
class ExternalApiGate:
    requested: bool
    backend: str
    key_env_var: str
    key_present: bool

    @property
    def open(self) -> bool                 # requested and key_present
    def reasons(self) -> tuple[str, ...]
    def skip_message(self) -> str          # "DS302 skipped: " + "; ".join(reasons())

def resolve_external_api_gate(config: Config, *, use_external_api: bool) -> ExternalApiGate
```

- `reasons()` returns, in this order and only for what is missing:
  `"pass --use-external-api (or set DOCSENTINEL_USE_EXTERNAL_API=1)"` and `f"set {key_env_var}"`.
- `key_env_var` is `expected_api_key_env_var(config.fact_check_backend)` (C3). `key_present` is
  `bool(os.environ.get(key_env_var))`; the value is never bound to a name that outlives the
  expression and never stored on the dataclass.
- A `config.fact_check_backend` outside `config.FACT_CHECK_BACKEND_NAMES` union the keys of
  `FACT_CHECK_BACKENDS` raises `ConfigError("fact_check_backend must be one of: <sorted names>")`.
  This fails closed for an injected `Config`; the union admits a test fake registered in the
  dict.
- `USE_EXTERNAL_API_ENV` is read only here. The engine calls this helper; it never reads either
  variable itself.

### Contract 4: Protocol and registry (`/src/docsentinel/fact_check/protocol.py`)

Standard library and `typing` only. No `config`, `detectors`, `mining` or `httpx` import (C9).
`/src/docsentinel/fact_check/__init__.py` imports nothing.

```text
Verdict = Literal["true", "false", "mixed", "unverifiable"]
VERDICTS: Final[frozenset[str]]             # the same four values
REPORTABLE_VERDICTS: Final[frozenset[str]]  # {"false", "mixed"}
BACKEND_NAME_PATTERN: Final[str] = r"^[a-z][a-z0-9]{0,31}$"
MAX_CITATIONS: Final[int] = 8
MAX_CITATION_CHARS: Final[int] = 500

class FactCheckError(RuntimeError)
    # The only exception check_claim may raise. Message: fixed text, at most 200 characters,
    # never a response body, request header, key or claim text.

@dataclass(frozen=True)
class FactCheckResult:
    verdict: Verdict
    confidence: float
    backend: str
    citations: tuple[str, ...] = ()
    # __post_init__ raises FactCheckError (not ValueError) when verdict is not in VERDICTS,
    # confidence is a bool or not a finite int/float in [0.0, 1.0], backend does not match
    # BACKEND_NAME_PATTERN, or citations is not a tuple of at most MAX_CITATIONS str entries
    # of at most MAX_CITATION_CHARS characters each.

@runtime_checkable
class FactCheckClient(Protocol):
    name: str
    API_KEY_ENV_VAR: ClassVar[str]
    def check_claim(self, claim: str) -> FactCheckResult: ...
    # close(self) -> None is optional and duck-typed (FaultEventSink precedent, ADR 0002).
    # Construction convention (not expressible in the Protocol): cls(api_key=<str>);
    # __repr__ must not reveal the key.

def expected_api_key_env_var(name: str) -> str
    # f"DOCSENTINEL_FACTCHECK_{name.upper()}_API_KEY"; ValueError when name does not match
    # BACKEND_NAME_PATTERN.

FACT_CHECK_BACKEND_MODULES: Final[Mapping[str, str]]   # MappingProxyType({"lenz": "docsentinel.fact_check.lenz"})
FACT_CHECK_BACKENDS: dict[str, type[FactCheckClient]] = {}

def load_backend(name: str) -> type[FactCheckClient]
    # 1. return FACT_CHECK_BACKENDS[name] when registered;
    # 2. else, when name is a key of FACT_CHECK_BACKEND_MODULES, importlib.import_module that
    #    mapped module and look again;
    # 3. else raise KeyError.
    # Before returning: TypeError unless cls.name == name,
    # cls.API_KEY_ENV_VAR == expected_api_key_env_var(name) and check_claim is callable.
    # ImportError from the mapped module propagates. A name from configuration is imported
    # only when it is a key of the static map.
```

`config.py` holds its own `FACT_CHECK_BACKEND_NAMES: Final[frozenset[str]] = frozenset({"lenz"})`
and never imports `docsentinel.fact_check`, `docsentinel.detectors` or `httpx`. A drift test holds
`set(FACT_CHECK_BACKEND_MODULES) == FACT_CHECK_BACKEND_NAMES`. This resolves the S1/S7 tension:
config validation imports nothing heavy, and the `fact_check` package never imports `config`.

### Contract 5: rules constant (`/src/docsentinel/rules.py`)

```text
EXTERNAL_API_RULES: Final[frozenset[str]] = frozenset({"DS302"})
```

`Rule`, `opt_in_satisfied` and `opt_in_hint` do not change. `docsentinel rules` lists every code in
this set with the suffix
`[requires --use-external-api and a backend API key; see docsentinel doctor]`.

### Contract 6: evaluated count while the gate is closed (ruling Q1)

In `scan()`, right after `opt_in_off` is computed and before `_log_rule_plan`:

```text
external_active = EXTERNAL_API_RULES.intersection(active_codes)
gate = resolve_external_api_gate(settings, use_external_api=use_external_api) if external_active else None
external_off = len(external_active) if gate is not None and not gate.open else 0
```

- `rules_evaluated = len(active_codes) - len(opt_in_off) - external_off`. `evaluated_notice()` is
  unchanged; it receives the lower count. In the deep profile it adds `len(opt_in_off)`, which is
  `0` for every deep rule, so a confirmed deep scan with `DS301` and `DS302` active and the gate
  closed reads `1 deep rule(s) evaluated (heuristic, advisory-only).`
- `_log_rule_plan` gains one parameter, `external_off: int = 0`, and subtracts it from its
  `evaluated` count. The INFO line text does not change.
- On the branch that today sets `pending = ()` because rules are active, `pending` becomes
  `(gate.skip_message(),)` when `external_off` is non-zero.
- `ScanResult` gains no field. `DS302` never enters `opt_in_off` (D5). `enabled_rules` still lists
  `DS302` when selected, because selection stays orthogonal to evaluation.
- The engine logs no gate WARNING; `detect()` does, so a scan logs it once.
- **Byte-identity:** when `DS302` is not in `active_codes` (every fast and standard scan, an
  unconfirmed or dependency-less deep scan, and a deep scan that drops `DS302` through
  `select`/`ignore`), `external_off` is `0`, no gate is resolved, no environment variable is read,
  and `notice`, `pending`, `rules_evaluated` and the INFO line are byte-identical to master.
- Gate 1 closed: the existing early return happens first, so nothing here runs.
- Gate open but backend unavailable (Contract 2): `DS302` is counted, because the engine cannot
  know without importing the backend. The WARNING names the failure. This is a known limitation.

### Contract 7: per-scan time budget (ruling Q3)

| Key | Type | Default | Bounds | Validation | User settings | Project config |
|---|---|---|---|---|---|---|
| `fact_check_time_budget_seconds` | int | `300` | `1` to `3600`, inclusive | `_require_bounded_int` with the keyword-only `maximum` from Story 01.0 Task 03; `bool` and `float` refused; message `fact_check_time_budget_seconds must be an integer from 1 to 3600` | yes | yes |

- It is a sixth `fact_check_*` key, beside the five of C4. It names no path, URL or secret and
  grants no consent, so it is not in `USER_SETTINGS_REFUSED_KEYS`. An untrusted file can at most
  raise the wall-clock cap to one hour for an invoker who has already opened both gates; egress
  volume stays bounded by `fact_check_max_claims_total`.
- **Clock:** `time.monotonic()`, never `time.time()`, so a wall-clock jump cannot extend or end the
  budget. `_check_candidates(client, candidates, config, *, clock: Callable[[], float] = time.monotonic)`
  takes the clock as a test seam; no configuration, environment or CLI path sets it.
- **Scope:** the network stage of one scan. The deadline is `clock() + budget`, taken once,
  immediately before the first `check_claim` call. Claim extraction and selection are not
  charged.
- **Check:** before each `check_claim`, when `clock() >= deadline`, the loop stops. It logs exactly
  one WARNING, `DS302: time budget of <budget> s exhausted; <n> of <total> claim(s) not checked`
  (counts only, no path, no claim text), and returns the findings built so far. The remaining
  claims are never sent. No `pending` entry is added, and the exit code is unaffected.
- **Overrun:** an in-flight call is not interrupted. The worst case is the budget plus one backend
  per-request deadline (Lenz: `REQUEST_TIMEOUT_SECONDS = 30.0`).
  **Amended 2026-11-24 (egress threat model):** this holds only because the backend enforces a hard wall-clock deadline outside blocking reads (mitigation E4; the `httpx` per-operation timeout alone does not bound a dripping peer, EG-4) ([threat-model-0010-fact-check-egress-2026-11-24](/docs/security/threat-model-0010-fact-check-egress-2026-11-24.md)).
- `detect()` re-validates the key of an injected `Config` (fail closed, `ConfigError`).
  `select_candidates()` never reads it.

### Contract 8: unrecognised verdict (ruling Q4)

> **Superseded 2026-11-27 (owner ruling R, see
> [Amendment 2026-11-27](#amendment-2026-11-27-owner-rulings-after-the-first-live-run)).** Every
> verdict is now kept and printed, and an unrecognised label is rated `unverifiable` instead of
> raising `FactCheckError`. The text below is the original ruling Q4, kept as history.

- A backend maps only the raw values it recognises into `Verdict`. Anything else makes
  `check_claim` raise `FactCheckError` with fixed text that does not echo the raw value. The Lenz
  message is `lenz /assess returned an unrecognised verdict`.
- `DS302`'s existing per-claim handler logs one WARNING,
  `DS302: fact-check failed for a claim in <safe(path)>: <safe(message)>`, and skips that claim.
- No backend maps an unknown value to `mixed` or to `unverifiable`. The Lenz client has no
  confidence band: `_normalize_verdict(raw: str) -> Optional[Verdict]` returns `"true"` or
  `"false"` for a stripped, case-folded match and `None` otherwise. The earlier 0.35 to 0.65 band
  is dropped.
- `FactCheckResult.__post_init__` gives the same outcome for a backend that builds a result with an
  out-of-vocabulary verdict, so the rule holds for every backend, not only Lenz.
- `mixed` stays in `Verdict` and `REPORTABLE_VERDICTS` for a backend whose own vocabulary has a
  mixed-class value. Lenz produces none today.

### Contract 9: the `DS302` finding (ruling Q2)

```text
Finding(
    rule="DS302",
    path=candidate.claim.path,
    message=f"external fact-check: '{snippet}' rated {result.verdict} by {result.backend} - review to confirm",
    severity="warning",
    value=f"{result.verdict} (confidence {result.confidence:.2f}): {candidate.text}",
    type="unverified claim",
)
```

- `snippet` is `candidate.text` cut to 200 code points. `candidate.text` is the exact text sent, at
  most 1,000 code points (Story 02.0 Task 03).
- A finding is built only when `result.verdict in REPORTABLE_VERDICTS` and
  `result.confidence >= config.fact_check_min_confidence`. Findings are sorted by `(path, message)`.
- The fingerprint is `rule:path:sha256(message)[:12]` (C6). It no longer depends on confidence, so a
  rerun with the same verdict is run-stable. A change of verdict (`false` to `mixed`) changes the
  fingerprint, which is intended: it is a different outcome.
- `value` is `compare=False`, so equality, hashing and fingerprints ignore it. It keeps the exact
  sent text as its suffix after the first `": "`, so it is still the persisted record of what left
  the machine. The `text` template prints `value`, so a text report shows verdict, confidence and
  claim. `value` is untrusted and reaches a sink only through a neutralizing filter, as today.
- `value` is wider here than the usual "offending token" convention. The cost is recorded under
  Negative consequences.

### Gate reporting (decision S9, as ratified)

| Surface | Gate 2 closed | One claim fails, or verdict unrecognised | Budget exhausted | Gate 2 open, clean verdict |
|---|---|---|---|---|
| Log | One WARNING `DS302 skipped: <reasons>` | One WARNING per claim, path only | One WARNING, counts only | DEBUG counts |
| `ScanResult.pending` | One entry, `DS302 skipped: <reasons>` | unaffected | unaffected | unaffected |
| `ScanResult.notice` / `rules_evaluated` | `DS302` not counted | counted | counted | counted |
| `ScanResult.findings` | none from `DS302` | none for that claim | findings from checked claims | none |
| Exit code | unaffected | unaffected | unaffected | unaffected |
| `docsentinel doctor` | `fact-check gate: off (<reasons>)` | unaffected | unaffected | `fact-check gate: on (backend: <name>)` |

The `doctor` line is computed with `resolve_external_api_gate(settings, use_external_api=False)`,
so it reflects only the environment. It never shows a key's value, length or format.

### Configuration surface

Six keys, all typed, defaulted and allowed in user settings and project configuration:
`fact_check_backend` (`"lenz"`), `fact_check_min_salience` (`0.5`), `fact_check_min_confidence`
(`0.6`), `fact_check_max_claims_per_document` (`3`, 1 to 50), `fact_check_max_claims_total` (`25`,
1 to 500), and `fact_check_time_budget_seconds` (`300`, 1 to 3600). The bounds and messages are
normative in
[Story 01.0's config reference](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/README.md#config-reference).
None names a path, URL or secret; `USER_SETTINGS_REFUSED_KEYS` is unchanged.

Addendum (2026-11-26): a seventh key, `fact_check_combination` (`"each"`, `"all"` or claim ranges such
as `1-6,7-8,9-16`), and the `--fact-combination` flag on `scan` and `baseline` group selected claims
into combined facts. The 1000-character send bound still applies to the combined text: an over-long
fact is not sent and is never truncated. The key is allowed in user settings.

### Module placement (C9)

| Layer | Modules | May import | Never imports |
|---|---|---|---|
| Mining | `mining/corpus.py`, `mining/claims.py`, `mining/nlp.py`; new `mining/salience.py`, `mining/clustering.py` | stdlib, scikit-learn, numpy, scipy, spaCy, textacy, `models`, `log`, other `mining.*` | `config`, `rules`, `detectors`, `engine`, `cli`, `reporting`, `telemetry`, `baseline`, `discovery`, `fact_check`, `httpx` |
| Fact-check backends | `fact_check/protocol.py`, `fact_check/lenz.py` | stdlib, `httpx` (`lenz.py` only), `log`, other `fact_check.*` | everything the mining layer refuses, plus `mining` |
| Detectors | `detectors/fact_check.py` | everything above, `config`, `rules`, `models`, `log` | `engine`, `cli`, `reporting` |

Salience scoring and clustering are mining-layer modules, `mining/salience.py` and
`mining/clustering.py`. They are pure, take explicit numbers and no `Config`, and are reached only
through the detector-side wrapper `select_candidates(claims, config)` in `detectors/fact_check.py`,
which lazily imports `mining.salience`. `mining/corpus.py` exposes a public `create_vectorizer()`
(Story 02.0 Task 02). The tripwires are `tests/unit/test_mining_layering.py` and the new
`tests/unit/test_fact_check_layering.py`.

### Affected components and migration path

| Component | Change | Migration |
|---|---|---|
| `engine.py` | New keyword `use_external_api: bool = False`; `_analyzer_accepts_use_external_api`; `_run_analyzer` forwarding; Contract 6 count and `pending` | None for library callers (defaulted keyword). A caller passing a non-`bool` gets `ConfigError` |
| `cli.py` | `--use-external-api` on `scan` and `baseline`; the `rules` suffix; one `fact-check gate:` `doctor` line | None. `doctor` output gains one line; a consumer parsing `doctor` line by line must tolerate it |
| `config.py` | Six new defaulted `fact_check_*` keys; `FACT_CHECK_BACKEND_NAMES`; `_require_bounded_int` gains a keyword-only `maximum` | None; defaults keep `DS302` inert. A file naming `use_external_api` already gets the generic unknown-option `ConfigError` |
| `rules.py` | `EXTERNAL_API_RULES` | None |
| `detectors/fact_check.py` (new) | `DS302`, gate helper, `detect()`, `select_candidates()`, `CandidateClaim` | New module; imported by `detectors/__init__.py` |
| `fact_check/` (new package) | `__init__.py` (empty), `protocol.py`; `lenz.py` in Story 03.0 | New package |
| `mining/` | New `salience.py` and `clustering.py`; public `create_vectorizer()` in `corpus.py` | No existing mining function changes behaviour |
| `ScanResult.pending` | A confirmed deep scan with `DS302` selected and gate 2 closed carries one entry | A consumer that asserted an empty `pending` on such a scan must update |
| `ScanResult.rules_evaluated` / `notice` | `DS302` not counted while either gate is closed | A consumer that assumed `rules_evaluated == len(enabled_rules) - len(opt_in_off)` on a deep scan must also subtract closed `EXTERNAL_API_RULES` |
| `pyproject.toml` | `httpx` declared in `dependencies` (D6) | `uv.lock` already carries it transitively; the lock is regenerated in Story 03.0 Task 03 |
| `rules.md`, `fault-classes.md`, `finding-types.md`, `telemetry/classify.py` `FAULT_CLASSES` | `DS302` rows, `unverified_claim` | Land in the same change as the registration (Story 04.0 Task 03) |
| pytest plugin, `.pre-commit-hooks.yaml`, `__init__.py` exports | No change | None |

### Consequences

#### Positive

- No configuration file of any kind can open gate 2 or carry the key. The trust model of ADR 0005
  extends to data egress without a special case.
- A second backend is one class plus one entry in each of two static name sets, held equal by a
  drift test. `detect()` is untouched.
- A closed gate is visible on three surfaces and is not counted as evaluated, so "0 findings"
  never reads as "fact-checked".
- Baseline fingerprints are stable across reruns with the same verdict.
- Cost is bounded twice: by claim count and by a monotonic time budget.
- No new `ScanResult` or `Finding` field and no report-schema change.

#### Negative (what gets harder)

- Gate 2 has three entry surfaces (flag, keyword, environment) and one strict value (`"1"`), which
  differs from the lenient `DOCSENTINEL_DEEP_CONFIRM`. Users must learn the asymmetry.
- `rules_evaluated` is no longer `len(active) - len(opt_in_off)` on a deep scan. The relation now
  depends on gate state, which the engine resolves by reading the environment. A test that
  monkeypatches the environment can change the notice.
- The gate is resolved twice per scan (engine for `pending` and the count, `detect()` for its own
  skip). The two reads agree unless the environment changes between them, which no supported
  caller does.
- `doctor` cannot see the flag, only the environment, so it reports `off` for a user who always
  passes `--use-external-api`. The line names the flag to make this clear.
- `Finding.value` for `DS302` is a composite (`<verdict> (confidence <0.00>): <text>`), not a bare
  token. A consumer that wants the sent text must strip the prefix at the first `": "`.
- An unrecognised verdict is a WARNING per claim. A provider-side vocabulary change shows up as a
  stream of warnings and no findings, not as silent `mixed` noise. This is safer but louder.
- The time budget does not interrupt an in-flight request, so the real bound is the budget plus
  one backend timeout.
  **Amended 2026-11-24 (egress threat model):** "one backend timeout" means the E4 hard per-request deadline; the backend runs each request in a daemon worker thread, so an abandoned worker may hold one socket until the peer or its read timeout ends it (RE3).
- `httpx` becomes an always-installed dependency, as `spacy` already is.
  **Amended 2026-11-24 (egress threat model, E10):** declared `httpx>=0.28,<1`; the lock keeps `h11>=0.16.0` and `httpcore>=1.0.9`, with no `h2`, `brotli`, `zstandard` or `socksio`.

## Pros and Cons of the Options

### (A1) Invoker-only flag, keyword and environment (chosen)

- Good: no repository can grant its own egress consent (driver 1); mirrors the `link_root`
  invoker-override precedent; the strict `"1"` read matches `DOCSENTINEL_ALLOW_PYTHON_EXTENSIONS`.
- Bad: three surfaces to document; a repository can still put the flag in its own pre-commit
  `args:` or a `pull_request_target` workflow, which only documentation mitigates (threat model,
  Story 01.0 Task 02).

### (A2) A configuration key like `deep_confirm`

- Good: one familiar pattern; settable once per user.
- Bad: a cloned repository's `docsentinel.toml` could turn egress on. This directly breaks driver 1
  and Milestone 0009's untrusted-config model.

### (A3) Reuse `deep_confirm` alone

- Good: no new surface.
- Bad: conflates "accept heuristic noise" with "send my text to a third party" (P3). Every existing
  deep user would start sending text after an upgrade.

### (B1) Structural `Protocol` (chosen)

- Good: matches `FaultEventSink` (ADR 0002) and the report `Extension`; a backend needs no base
  class; test fakes are plain classes; `isinstance` works at runtime.
- Bad: `runtime_checkable` checks only member presence, not signatures, and cannot express the
  `cls(api_key=...)` constructor. `load_backend` adds explicit `TypeError` checks to cover this.

### (B2) Abstract base class

- Good: the constructor and members are enforced at class creation.
- Bad: every backend and fake must inherit from a shared class in the package; departs from the
  project's two existing Protocol precedents.

### (B3) Hard-coded Lenz call in the detector

- Good: least code today.
- Bad: couples `DS302` to one vendor and to `httpx` (P2); puts network code under `detectors/`;
  a second provider means editing `detect()`.

### (C1) Per-backend environment variable (chosen)

- Good: two backends never share or swap one secret; the name derives from the backend name, so
  `DS302` reads it generically; never in shell history or a config file.
- Bad: one more variable per backend to document.

### (C2) One fixed variable name

- Good: one name to remember.
- Bad: switching `fact_check_backend` silently sends one vendor's key to another (S6).

### (C3) Configuration key or CLI argument

- Good: discoverable.
- Bad: a config file is the untrusted tier and may be committed; a CLI argument is visible in shell
  history and process listings. Rejected.

### (D1) Scoped `pending`, `doctor` line and WARNING (chosen, D5)

- Good: reuses the existing `pending` field the deep-wide gate already fills; the message names
  exactly which of the two prerequisites is missing; no new `Config` field.
- Bad: the generic "opt-in rule(s) not enabled" text never names `DS302`; a second, bespoke
  surfacing path exists beside `opt_in_off`. Contract 6 closes the counting gap (Q1) but adds
  a third input to `rules_evaluated`.

### (D2) Retrofit `Rule.opt_in_option` with a shadow `Config` field

- Good: one surfacing mechanism for all inert rules.
- Bad: `opt_in_satisfied` tests one `Config` attribute and cannot say which of two prerequisites is
  missing; a `Config.use_external_api` field, even non-file-settable, invites a later loader change
  that makes it settable. Refused by the owner (D5).

### (E1) `docsentinel.fact_check` package beside `mining/` (chosen)

- Good: egress code is one small, auditable package with no upward imports; importing it does not
  run every rule registration.
- Bad: one more top-level package and one more layering tripwire.

### (E2) Backends under `detectors/`

- Good: next to their only caller.
- Bad: importing any `docsentinel.detectors` submodule runs the package `__init__` and every rule
  registration; a backend is not an analyzer.

### (E3) Backends inside `mining/`

- Good: beside the claim extraction.
- Bad: network I/O is not mining; it would break the mining layer's no-`httpx` rule (C9).

### (F1) Engine subtracts closed `EXTERNAL_API_RULES` (chosen, Q1)

- Good: a few lines in `scan()`; no new field; `opt_in_off` and `Rule` untouched; byte-identical
  whenever `DS302` is inactive.
- Bad: the engine reads the environment (through the helper) to compute a count.

### (F2) Count `DS302` anyway

- Good: no engine logic.
- Bad: a scan that sent nothing claims the rule was evaluated. Overruled by Q1.

### (F3) Put `DS302` into `opt_in_off`

- Good: the existing notice names it.
- Bad: `opt_in_off` pairs are `(code, Config option)`; there is no option to name. This is D2 by
  another route, refused by D5.

### (G1) Confidence in `value` (chosen, Q2)

- Good: no schema change; `compare=False` keeps fingerprints stable; the text report shows it.
- Bad: `value` becomes a composite rather than a bare token.

### (G2) New `Finding.confidence` field

- Good: typed and clean.
- Bad: changes `models.py`, `telemetry/model.py` `CONTEXT_SCHEMA` and the `json` and `text`
  templates for one rule; a report-schema change is a Story 01.0 non-goal.

### (G3) Leave confidence out

- Good: simplest.
- Bad: the user cannot judge how strongly the backend disagrees; `fact_check_min_confidence` would
  filter on a value the report never shows.

## Open questions

The task spec listed three questions for this section. The owner ruled on all of them on
2026-11-21 before this ADR was written, so they are recorded as decisions, not left open:

- `rules_evaluated` while gate 2 is closed: ruled by Q1, realised in Contract 6.
- Fingerprint stability with confidence in the message: ruled by Q2, realised in Contract 9.
- A total wall-clock bound for the network loop: ruled by Q3, realised in Contract 7.

Still open, for the owner:

- **O1.** Contract 9 keeps the verdict in `message`, so a verdict flip between runs changes the
  fingerprint. Confirm this is wanted, or move the verdict to `value` too, which would make
  `message` the same for `false` and `mixed`.
- **O2.** Contract 9 makes `value` a composite. Confirm, or ask for a dedicated report-only
  `Finding.confidence` field in a later milestone (option G2).
- `trust_env` (E-3), the API-key length bound (E-7) and the INFO count line (threat 10) stay with
  the two threat models, Story 01.0 Task 02 and Story 03.0 Task 01.
  **Amended 2026-11-24 (egress threat model):** resolved: `trust_env=False` (E3) and a key of 16 to 256 printable ASCII characters (E7.1); new owner items OQ-E1 (stop after 401/403) and OQ-E2 (invoker-only proxy support).

## Validation / Rollout

Execution order is Story 01.0, then 02.0, then 03.0, then 04.0. The Security Auditor tasks of
Stories 01.0 and 03.0 run before their first Python Expert task.

- Story 01.0:
  [Task 02, threat model](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/02-threat-model-fact-check-gating.md),
  [Task 03, config, CLI and env surface](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/03-fact-check-config-cli-and-env-surface.md),
  [Task 04, Protocol and registry](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/04-factcheckclient-protocol-and-data-contracts.md),
  [Task 05, registration and engine dispatch](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/05-ds302-registration-and-engine-dispatch.md),
  [Task 06, tests](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/06-fixtures-and-tests.md).
- Story 02.0:
  [Task 01, salience scoring](/docs/roadmap/0010-fact-check/02.0-claim-salience-and-data-mining/01-salience-scoring.md),
  [Task 02, clustering](/docs/roadmap/0010-fact-check/02.0-claim-salience-and-data-mining/02-corpus-dedup-clustering.md),
  [Task 03, selection and caps](/docs/roadmap/0010-fact-check/02.0-claim-salience-and-data-mining/03-candidate-selection-and-caps.md),
  [Task 04, tests](/docs/roadmap/0010-fact-check/02.0-claim-salience-and-data-mining/04-fixtures-and-tests.md).
- Story 03.0:
  [Task 01, egress threat review](/docs/roadmap/0010-fact-check/03.0-lenz-backend-client/01-egress-threat-review.md),
  [Task 02, Lenz client](/docs/roadmap/0010-fact-check/03.0-lenz-backend-client/02-lenz-client-implementation.md),
  [Task 03, registry wiring](/docs/roadmap/0010-fact-check/03.0-lenz-backend-client/03-backend-registry-wiring.md),
  [Task 04, tests](/docs/roadmap/0010-fact-check/03.0-lenz-backend-client/04-fixtures-and-tests.md).
- Story 04.0:
  [Task 01, fixtures and fake backend](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/01-fixtures-and-fake-backend.md),
  [Task 02, integration and mock tests](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/02-integration-and-mock-tests.md),
  [Task 03, rules table and fault class](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/03-rules-table-and-fault-class.md),
  [Task 04, docs and release notes](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/04-docs-and-release-notes.md),
  [Task 05, diagram follow-up](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/05-diagram-follow-up.md).

Verification:

- Unit tests pin Contracts 3 to 8: the exact `"1"` match, `reasons()` order, the six keys and their
  messages, `FactCheckResult` validation, `load_backend`, the budget with an injected clock, and
  the unrecognised-verdict skip.
- A mock test pins Contract 6: with `DS301` and `DS302` active and the gate closed, `notice` reads
  `1 deep rule(s) evaluated (heuristic, advisory-only).` and `pending` holds the one entry; every
  scan without `DS302` active gives a `ScanResult` equal to master's.
- A sentinel-key test proves the key never reaches a log record, `Finding`, `ScanResult`,
  `pending`, a `repr` or `doctor`/`rules` output.
- A fresh-interpreter check proves `httpx` is absent after `import docsentinel`, fast and standard
  scans, `rules`, `doctor` and a gate-closed deep scan.
  **Amended 2026-11-24 (egress threat model, E13):** for the gate-closed deep scan the check is that `docsentinel.fact_check.lenz` is absent and no socket opened (spaCy imports `httpx`); `doctor` holds only with `DOCSENTINEL_USE_EXTERNAL_API` unset.
- The self-scan `uv run docsentinel scan . --format json` exits `0` with zero `DS302` findings.
- Status moves to `Accepted` only on owner sign-off after the code lands.

## Diagram follow-up

No diagram source is edited now, because `/docs/diagrams/` shows the as-built package and none of
this code exists yet. Checked: `/docs/diagrams/README.md`, the five `.puml` sources, and
`/docs/architecture/README.md`, which has no Mermaid block. Follow-up for
[Story 04.0 Task 05](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/05-diagram-follow-up.md),
after Story 03.0's code is merged:

- `/docs/diagrams/component/detectors/component-detectors.puml`: a `detectors/fact_check.py` box in
  the deep group; edges to `mining/salience.py`, `mining/clustering.py` (to `mining/corpus.py`),
  `mining/claims.py` and `mining/nlp.py`; the `FactCheckClient` Protocol boundary to the
  `fact_check/` package.
- `/docs/diagrams/component/overview/component-overview.puml`: the mining layer and `fact_check/`
  as components; the first outbound network edge from `fact_check/lenz.py`, labelled opt-in and
  advisory; the `use_external_api` invoker input into `engine.scan`.
- New `sequence/ds302-fact-check-gate`: this ADR asks for it. It shows the engine's gate resolution,
  the Contract 6 count and `pending` entry, and the four fail-soft paths (closed gate, per-claim
  `FactCheckError` including an unrecognised verdict, exhausted time budget, unavailable backend).
- `config-layered-load.puml`, `scan-selection.puml` and `component-reporting.puml` are not
  affected: the six keys follow the existing layering, selection is unchanged, and no report
  schema changes.

## Amendment 2026-11-23: offline fact extraction (Story 05.0)

This amendment was added while the ADR is still `Proposed`, for the owner request recorded in
[status.md](/docs/roadmap/0010-fact-check/status.md#notes--decisions) and specified in
[Story 05.0](/docs/roadmap/0010-fact-check/05.0-extract-facts-cli/README.md) and plan contract
[C11](/docs/roadmap/0010-fact-check/plan.md#c11--one-candidate-source-for-ds302-and-extract-facts).
It adds contracts. It changes none of the gate, key, Protocol or finding decisions above.

- **Contract 10, one candidate source.**
  `trace_candidates(root, documents, config, *, policy=DS302_POLICY) -> CandidateTrace` and
  `collect_candidates(root, documents, config) -> tuple[CandidateClaim, ...]` (its `selected`
  projection, with no `policy` parameter) live in `detectors/fact_check.py`. Contract 2's
  `detect()` calls `collect_candidates()` after the gate and holds no extraction code.
  `CandidateClaim` gains `numeric`, `entity`, `distinctiveness`, `cluster_id` and `cluster_size`.
  `mining.salience.select_salient()` becomes the `selected` projection of `trace_salience()`.
- **Contract 11, offline consumer.** `docsentinel.extract_facts(...) -> FactExtractionResult`
  (`engine.py`, exported) and `docsentinel extract-facts` call `trace_candidates()` with no gate.
  They never resolve `use_external_api`, never read `DOCSENTINEL_USE_EXTERNAL_API` or a
  `DOCSENTINEL_FACTCHECK_*` variable, and never import `httpx` or a backend. Drivers 1 and 6 hold
  because the command has no egress path. Exploration settings (`SelectionPolicy`) are CLI and
  library only, never `Config`, and cannot reach `DS302`.
  **Correction 2026-11-24 (threat model F1/E1):** spaCy itself imports `httpx`, so "never import `httpx`" means no backend module, no `httpx` reference in DocSentinel code on the path and no outbound socket ([threat-model-0010-extract-facts-2026-11-24](/docs/security/threat-model-0010-extract-facts-2026-11-24.md)).
- **Affected components:** `detectors/fact_check.py`, `mining/salience.py`, `engine.py` (a shared
  inventory step with `scan()`, behaviour-preserving), `models.py` (`ExtractedFact`,
  `FactSettings`, `FactExtractionResult`), `__init__.py` (exports), `telemetry/loader.py`
  (additive `context` key), `telemetry/facts_model.py`, two packaged templates, `reporting.py`
  (`render_facts`), `cli.py`. **Migration:** none for existing callers. `scan()`, every existing
  template and every report are byte-identical. A `doctor` consumer sees one more
  `fact templates (packaged):` line.
- **What gets harder:** a change to `trace_salience` now affects two public surfaces at once.
  `ScoredClaim`/`CandidateClaim` construction sites grow. The template format has a second context
  that must stay disjoint from the first.
- **Diagram follow-up** additions are listed in
  [Story 04.0 Task 05](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/05-diagram-follow-up.md).

## Amendment 2026-11-23: threat-model mitigations

The pre-code threat model
[threat-model-0010-fact-check-gating-2026-11-23](/docs/security/threat-model-0010-fact-check-gating-2026-11-23.md)
(verdict PASS_WITH_FOLLOWUP) tightens four points of this record. Where the text above disagrees,
this section and the Story 01.0 task specs (marked "Amended 2026-11-23 (threat model)") win:

- **Contract 3 (M3, M7):** `resolve_external_api_gate` refuses a non-`bool` `use_external_api`
  and checks backend-name membership before it derives the key variable name; the environment
  gate is open only for the exact value `"1"` (M2).
- **R5 (M8):** the key is read with `os.environ.get(...)`, only in `detectors/fact_check.py`; no
  `fact_check/` module reads the environment, and nothing reads `LENZ_API_KEY`. **Superseded
  2026-11-26:** `LENZ_API_KEY` is now the fallback (see the amendment below).
- **Contract 2 / S10 (M5, HIGH FC-5):** a backend or transport exception no longer propagates
  unchanged. Anything other than `FactCheckError` is re-raised as `RuntimeError` naming only the
  exception type, with no chain (`from None`), because `httpx`/`h11` header errors carry the full
  `Bearer` value in their message.
- **Contract 4 (M7):** the backend-name pattern is applied with `re.fullmatch`.
- **Contract 6 (honesty, Task 05):** the gate is open only when the flag or environment gate is
  given, the key is set **and the backend loads** (`ExternalApiGate.backend_available`). A
  backend that fails to load (`ImportError`, `KeyError`, Protocol check) closes the gate: `DS302`
  leaves the evaluated count, `pending` and `doctor` say `backend <name> not available` (fixed
  text, never an exception message).
- **S10 (M5):** a `FactCheckError` from `check_claim` is logged by type name only, never its message.

## Amendment 2026-11-27: owner rulings after the first live run

These rulings are already implemented and win over the text above where they differ. The ADR stays
`Proposed`.

- **Key fallback (owner ruling of 2026-11-26; reverses threat-model M8 and the R5 ban).**
  `detectors/fact_check.py::_read_api_key` reads `DOCSENTINEL_FACTCHECK_<NAME>_API_KEY` and, when it is
  unset or empty, the vendor's standard variable `<NAME>_API_KEY` (`LENZ_API_KEY` for `lenz`). The closed-gate
  reason reads `set DOCSENTINEL_FACTCHECK_LENZ_API_KEY or LENZ_API_KEY`. Residual risk: a key exported for
  another Lenz tool can now open the key half of the gate. The `--use-external-api` consent half is
  unchanged, so nothing is sent without the invoker's explicit flag. Still never a configuration key, never logged.
- **Response parsing (ruling R of 2026-11-27; replaces Q4 and Contract 8).** Every verdict is kept and
  printed. `VERDICT_LABELS`: true and mostly true map to `true`; false and mostly false to `false`; mixed and
  half true to `mixed`; unverifiable to `unverifiable`; any other label to `unverifiable` (printed, never a
  finding). Confidence words `high`, `medium`, `low` map to 0.9, 0.6, 0.3 (`CONFIDENCE_WORDS`); numbers are
  still accepted. Every item of `claims` is read (Lenz splits a combined fact); the fact takes the most severe
  verdict (false, mixed, unverifiable, true), with the minimum confidence for `true` and the maximum otherwise.
  Reason: the live API returned confidence words and labels such as `Mostly True`, which the old client rejected as an unexpected shape.
- **Tracing (ruling O of 2026-11-27).** At INFO, `DS302` logs one line per selected claim and one per checked
  fact (verdict, confidence, `reported` or `not reported`); the lenz client logs one line per response claim
  (raw label capped at 40 characters, mapped verdict, confidence). The first ten words of a claim and of the
  backend's echo (`log.quote_start`) therefore reach stderr and the log file: an explicit owner exception to
  "document content is never logged". `FactCheckError` messages, citations and keys are still never logged,
  except the lenz client's own fixed rejection message at DEBUG.
- **Log format (ruling O of 2026-11-26).** stderr and the log file both use `[{timestamp}][{severity}]: {message}`
  (`log.LOG_FORMAT`).

## Links

- **Roadmap story/task:** [Story 01.0](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/README.md),
  [Task 01](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/01-adr-and-rule-contract.md),
  [plan](/docs/roadmap/0010-fact-check/plan.md), [status](/docs/roadmap/0010-fact-check/status.md)
- **Related ADRs:** [0002](/docs/adr/0002-fault-telemetry-event-emission.md) (`FaultEventSink`
  Protocol precedent), [0005](/docs/adr/0005-layered-configuration-user-settings-json.md)
  (untrusted configuration tier, refused user keys)
- **Diagrams:** see [Diagram follow-up](#diagram-follow-up)

Diagram impact: /docs/diagrams/component/detectors/component-detectors.puml, /docs/diagrams/component/overview/component-overview.puml, /docs/diagrams/component/reporting/component-reporting.puml, /docs/diagrams/sequence/scan-selection/scan-selection.puml, new: sequence/ds302-fact-check-gate -> deferred to Story 04.0 Task 05 after Stories 03.0 and 05.0 land (DS302 detector, mining salience/clustering, fact_check Protocol package, first gated outbound edge, gate/notice/pending sequence; amendment 2026-11-23: shared trace_candidates, extract-facts CLI/engine path, facts template context, shared inventory step); no edit now
