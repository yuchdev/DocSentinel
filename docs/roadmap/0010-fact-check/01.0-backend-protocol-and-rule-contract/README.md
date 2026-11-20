# Story 01.0 — Backend Protocol and rule contract (DS302 core design)

**Profile:** `deep` · **New rule:** `DS302` (warning, advisory-only, always registered) ·
**New Protocol:** `FactCheckClient` (`src/docsentinel/telemetry/`-style structural typing, but
co-located with the detector, not telemetry) · **Touched/new sources (described, not yet written):**
`src/docsentinel/detectors/fact_check.py` (new, `DS302` registration + `detect()`),
`src/docsentinel/detectors/fact_check_protocol.py` (new, `FactCheckClient`/`FactCheckResult`/
`FactCheckError`), `src/docsentinel/config.py` (new `fact_check_*` keys), `src/docsentinel/cli.py`
(new `--use-external-api` flag), `src/docsentinel/engine.py` (new `use_external_api` keyword on
`scan()`, dispatch wiring), `src/docsentinel/rules.py` (no change — `DS302` needs no new
opt-in-option mechanism, see decision S4).
**Parent:** [Milestone 0010 plan](/docs/roadmap/0010-fact-check/plan.md) (contracts C1–C5, C7, C8).
**Security-sensitive:** yes. It designs where a secret enters the process and the exact shape of
network consent. Task 02 (threat model) must run before any code, exactly as Milestone 0009's
Stories 01.0/02.0/03.0 required.

## Goal

Define, to ADR depth, the complete interface and consent-gate contract `DS302` is built against:
the `FactCheckClient` Protocol, the `fact_check_*` config surface, the `--use-external-api`
CLI/env/library surface, the per-backend API-key environment-variable convention, and exactly how
and where a gate failure is reported. Nothing here calls a network backend — that is Story 03.0.

## Tasks

| Task | Deliverable | Role | Status |
|---|---|---|---|
| `01-adr-and-rule-contract.md` | ADR 0007 (backend Protocol, dual consent gate, API-key convention); `DS302` rule-code reservation confirmed; the `Rule` registration literal | Architect | ⬜ Not written |
| `02-threat-model-fact-check-gating.md` | Threat model for the dual consent gate, the API-key surface, and "what a `docsentinel.toml` can and cannot do here" | Security Auditor | ⬜ Not written |
| `03-fact-check-config-cli-and-env-surface.md` | `fact_check_backend`/`fact_check_min_salience`/`fact_check_min_confidence`/`fact_check_max_claims_per_document`/`fact_check_max_claims_total` in `config.py`; `--use-external-api` on `scan`/`baseline`; `DOCSENTINEL_USE_EXTERNAL_API`; `doctor`/`rules` lines | Python Expert | ⬜ Not written |
| `04-factcheckclient-protocol-and-data-contracts.md` | `FactCheckClient` Protocol, `FactCheckResult`, `FactCheckError`, the backend registry | Python Expert | ⬜ Not written |
| `05-ds302-registration-and-engine-dispatch.md` | `DS302` `Rule` registration; `detect()` skeleton calling Story 02.0's filter and Story 03.0's client through the Protocol only; `engine.py` `use_external_api` keyword, dispatch to analyzers declaring it (mirrors `link_root`) | Python Expert | ⬜ Not written |
| `06-fixtures-and-tests.md` | Unit tests for the gate resolution and config validation; mock tests for the engine dispatch wiring, with a fake `FactCheckClient` | Testing Expert | ⬜ Not written |

## Scope

- The `FactCheckClient` Protocol and its two data contracts (`FactCheckResult`, `FactCheckError`).
- The `DS302` `Rule` registration (eager, like `DS301`) and its `detect()` signature, wired through
  `engine.py`'s existing analyzer-introspection dispatch.
- The dual consent gate: `deep_confirm` (unchanged, reused as-is) and the new `use_external_api`
  resolution (CLI flag, `scan()` keyword, environment variable) plus the per-backend API-key
  environment variable convention.
- The `fact_check_*` config keys that tune *what* gets sent, never *whether* sending is allowed.
- How a gate-2 failure is reported (the WARNING line, and the recommended `pending`/`doctor`
  surfacing — decision S9, flagged open in `plan.md` D5).

## Non-goals

- The salience/dedup filter's internals (Story 02.0) — this story only defines the
  `CandidateClaim` shape the filter must produce and the config keys that bound it.
- The Lenz client's internals (Story 03.0) — this story only defines the Protocol it must satisfy
  and the API-key environment-variable convention it must follow.
- Changing `DS301`, `_triples.py`, `deep_support.py`, or the `deep_confirm` triple-gate itself.
- Any report-schema change. `ScanResult`'s *shape* gains one optional, defaulted mechanism (the
  `pending` entry — already an existing field, reused, not a new one) and no new top-level field.

## Design

### Decisions

| # | Decision | Rationale |
|---|---|---|
| S1 | `DS302` registers eagerly at import time, like `DS301`; `fact_check.py` imports `httpx` and the backend registry **lazily**, inside `detect()`, via `importlib.import_module`, exactly like `contradictions.py` imports `_triples` lazily | `import docsentinel` and every fast/standard scan must never pull in `httpx`, matching the existing spaCy/textacy lazy-import discipline |
| S2 | `DS302` has **no** `opt_in_option`/`opt_in_values` on its `Rule` registration | Those fields describe a *configuration-file-driven* policy (`getattr(config, option)`); `use_external_api` is deliberately never a config-file value (C5), so the generic mechanism does not fit. `DS302` is an ordinary always-registered deep rule whose own `detect()` self-gates, exactly like the documented `DS103` "analyzer guards the scope itself" deviation (Milestone 0009 status, Task 03 note) |
| S3 | `use_external_api` is a new **keyword-only parameter on `engine.scan()`**, not a `Config` field | Mirrors `link_root=` exactly: a trusted, invoker-only value threaded straight past `Config` to the analyzers that declare it (C5). The CLI resolves `--use-external-api` and the environment variable, then calls `scan(..., use_external_api=resolved)` |
| S4 | `rules.py` gains a new frozenset, `EXTERNAL_API_RULES = frozenset({"DS302"})`, mirroring `LINK_ROOT_RULES` | `engine.py` needs a declarative list of "which analyzers want the resolved `use_external_api` value forwarded as a keyword", the same role `LINK_ROOT_RULES` plays for `link_root` |
| S5 | `engine.py` gains `_analyzer_accepts_use_external_api(analyzer)` (signature introspection) alongside the existing `_analyzer_accepts_link_root`, and forwards `use_external_api=resolved` only to analyzers that declare a keyword-acceptable parameter of that name | Exact structural mirror of the existing `link_root` forwarding (`_run_analyzer`); no new dispatch concept, one more declarative check |
| S6 | The API-key environment variable is named **per backend**: `DOCSENTINEL_FACTCHECK_<BACKEND>_API_KEY`, declared as a `ClassVar[str]` on each backend class (`LenzFactCheckClient.API_KEY_ENV_VAR = "DOCSENTINEL_FACTCHECK_LENZ_API_KEY"`) | Rejected alternative: one fixed name (`DOCSENTINEL_FACTCHECK_API_KEY`) for every backend. Rejected because the day a second backend ships, both would need the same secret or the user would have to remember to swap one env var when switching `fact_check_backend` — a silent foot-gun. Per-backend naming costs one class attribute and collides with nothing |
| S7 | `fact_check_backend` is a `Config` string, enum-validated (`_require_enum`) against the names in a module-level backend registry, default `"lenz"` | Mirrors `reference_scope`/`table_dialect`'s enum validation style; it is **not** security-sensitive by itself (it only picks *which* class, never a URL or a secret), so it is an ordinary project-config-settable option, allowed at user-settings level too (not in `USER_SETTINGS_REFUSED_KEYS` — it names no path) |
| S8 | The backend's base URL, request timeout, and maximum response size it will read are **fixed `ClassVar` constants on the backend class**, never `Config` fields | Generalizes the project's existing "an output artifact path is not root-constrained, but an *input* that could be redirected is" reasoning (ADR 0002's `telemetry_sink`) to the opposite direction: here the *destination* itself must never be redirectable by an untrusted project file (SSRF/key-exfiltration risk — see Security notes) |
| S9 | A gate-2 failure (missing flag/env, or missing key) logs **one WARNING every time**, and additionally appends one entry to `ScanResult.pending` naming exactly which prerequisite is missing, and `docsentinel doctor` prints one `fact-check gate: off (...)` / `on (<backend>)` line — but it does **not** use the generic `Rule.opt_in_option`/`ScanResult.notice` "opt-in rule(s) not enabled" machinery | **Flagged open for the owner (plan.md D5).** That machinery tests exactly one `Config` attribute (`opt_in_satisfied`); gate 2 has *two* independent failure reasons (flag/env absent vs. key absent) that a single boolean attribute cannot distinguish, and S3 forbids making `use_external_api` a `Config` attribute at all. Reusing `pending` (already populated by the engine for the profile-wide `deep_confirm` gate, in the very same code path) needs no new `ScanResult` field and gives an equally discoverable, more precise message. The alternative — adding a non-file-settable `Config.use_external_api` shadow field purely so `opt_in_option="use_external_api"` can be reused — was considered and rejected as more code for a worse message |
| S10 | `DS302`'s own network-failure handling (per-claim, not per-gate) catches only `FactCheckError` (new, defined in this story) raised by the Protocol's `check_claim`; a backend implementation must translate every transport/HTTP/parsing failure into `FactCheckError`, never let `httpx` exceptions or `KeyError`/`json.JSONDecodeError` escape | Keeps `DS302`'s own loop backend-agnostic: it never needs to know which transport library a given backend uses, exactly the point of the Protocol boundary |

### Config reference

| Key | Type | Default | Validation | Allowed in user settings | Allowed in project config |
|---|---|---|---|---|---|
| `fact_check_backend` | string | `"lenz"` | enum against the backend registry's names; unknown name raises `ConfigError("fact_check_backend must be one of: lenz")` (grows as backends are added) | yes | yes |
| `fact_check_min_salience` | float | `0.5` | `0.0 <= value <= 1.0`, same `_finite_number` + range-check style as `duplicate_similarity` | yes | yes |
| `fact_check_min_confidence` | float | `0.6` | `0.0 <= value <= 1.0`, same style | yes | yes |
| `fact_check_max_claims_per_document` | int | `3` | `_require_bounded_int`, `>= 1`, `<= 50` | yes | yes |
| `fact_check_max_claims_total` | int | `25` | `_require_bounded_int`, `>= 1`, `<= 500` | yes | yes |

None of the five names a path, a URL, or a secret, so none joins `USER_SETTINGS_REFUSED_KEYS` (the
C6 list in Milestone 0009's ADR 0005) and all five behave like any other Milestone 0005/0007 typed
option: defaults reproduce "DS302 sends at most a few, well-chosen claims" out of the box, and a
project may narrow (never widen past the hard caps above) its own exposure/cost. `use_external_api`
is **deliberately absent** from this table and from `_CONFIG_OPTIONS` — see decision S3 and
contract C5. The fact-check API key is likewise absent from `Config` entirely — see the CLI/env
reference below.

### CLI and library reference

| Command | Flag / keyword | Values | Effect |
|---|---|---|---|
| `scan` | `--use-external-api` | flag (`store_true`) | Resolves gate 2's flag component for this run |
| `baseline` | `--use-external-api` | flag | Same, so a fact-check-enabled baseline run is possible |
| library | `scan(..., use_external_api=True)` | keyword-only `bool`, default `False` | Same resolution, for a caller that is not the CLI (mirrors `link_root=`) |
| environment | `DOCSENTINEL_USE_EXTERNAL_API` | exactly `"1"` | Alternative to the flag/keyword, read once by `engine.py` (mirrors the strict, non-lenient reading `ALLOW_PYTHON_EXTENSIONS_ENV` uses — `"true"`/`"yes"` do **not** count, unlike the more lenient `DOCSENTINEL_DEEP_CONFIRM`, because this gate authorizes outbound network egress of document content, a strictly higher-consequence action) |
| environment, per backend | `DOCSENTINEL_FACTCHECK_LENZ_API_KEY` (today's only backend; pattern `DOCSENTINEL_FACTCHECK_<BACKEND>_API_KEY`) | non-empty string | The secret. Read **only** inside the backend's own client class, at construction time, **never** inside `cli.py`, `config.py` or `engine.py` — the only module that reads the raw value is the backend client itself |
| `rules` | — | — | `DS302` is listed as an ordinary deep rule (warning, advisory), with a one-line note "requires --use-external-api and a backend API key; see `docsentinel doctor`" |
| `doctor` | — | — | New line: `fact-check gate: off (pass --use-external-api and set DOCSENTINEL_FACTCHECK_LENZ_API_KEY)` or `fact-check gate: on (backend: lenz)` — never prints whether the key's *value* looks valid, only whether the named variable is set |

There is no CLI flag and no config key for the API key itself (decision requirement 6 in the
milestone brief): a secret passed as a CLI argument is visible in shell history and process
listings, which this project's existing conventions already avoid everywhere else.

### Interface contracts

```python
# src/docsentinel/detectors/fact_check_protocol.py (new; stdlib + typing only, no httpx import)

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Protocol, runtime_checkable

#: Normalized, backend-independent verdict vocabulary. Each backend's client is
#: responsible for mapping its own raw vocabulary into this closed set.
Verdict = str  # one of "true", "false", "mixed", "unverifiable"


class FactCheckError(RuntimeError):
    """A backend's check_claim() failed (transport, HTTP status, or response shape).

    A concrete client MUST raise this for every failure mode it can produce
    (timeout, non-2xx, malformed JSON, missing expected keys) rather than letting
    its own transport library's exception type escape. DS302 catches exactly this
    type and skips the one claim that failed; nothing else propagates from
    check_claim().
    """


@dataclass(frozen=True)
class FactCheckResult:
    """One backend's verdict on one claim, already normalized."""

    verdict: Verdict           # see Verdict; backend-reported value, normalized by the client
    confidence: float          # clamped to [0.0, 1.0] by the client before this is built
    backend: str               # the backend's `name`, for the finding message and fault routing
    citations: tuple[str, ...] = ()  # optional; bounded count/length by the client, never raw HTML


@runtime_checkable
class FactCheckClient(Protocol):
    """Structural contract for a fact-check backend (one request, one claim, one verdict).

    Only `name`, `API_KEY_ENV_VAR` and `check_claim` are required. `close` is
    optional and duck-typed, exactly like `FaultEventSink.close` (ADR 0002): DS302
    calls it in a `finally` only when the client provides it, so a minimal client
    needs only the three required members.
    """

    name: str
    API_KEY_ENV_VAR: ClassVar[str]

    def check_claim(self, claim: str) -> FactCheckResult:
        """Check one claim and return its normalized verdict.

        :param claim: The bounded candidate-claim text (already produced by
            Story 02.0's filter; never a raw, unbounded document excerpt).
        :returns: The normalized result.
        :raises FactCheckError: On any transport, HTTP or response-shape failure.
            Never lets a backend-library-specific exception escape.
        """


#: name -> class. Populated by each backend module importing this one and
#: registering itself; Story 03.0 adds the one "lenz" entry. A future second
#: backend adds one more entry and touches no call site in fact_check.py.
FACT_CHECK_BACKENDS: dict[str, type[FactCheckClient]] = {}
```

```python
# src/docsentinel/detectors/fact_check.py (new; sketch, not final code)

from __future__ import annotations

import importlib
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from docsentinel import deep_support, models, rules
from docsentinel.config import Config
from docsentinel.log import safe

if TYPE_CHECKING:
    from docsentinel.detectors._triples import Claim
    from docsentinel.detectors.fact_check_protocol import FactCheckClient

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
        # No opt_in_option/opt_in_values -- see decision S2.
    )
)

logger = logging.getLogger(__name__)

#: Gate 2's environment-variable form, strict ("1" only) -- see the CLI/library reference.
USE_EXTERNAL_API_ENV = "DOCSENTINEL_USE_EXTERNAL_API"


def _env_allows_external_api() -> bool:
    return os.environ.get(USE_EXTERNAL_API_ENV) == "1"


def detect(
    root: Path,
    documents: tuple[models.Document, ...],
    config: Config,
    *,
    use_external_api: bool = False,
) -> tuple[models.Finding, ...]:
    """Fact-check high-salience claims against the configured external backend.

    Both consent gates (C1) are resolved here; a failed gate is reported and
    DS302 returns no findings, never raising. The deep-wide deep_confirm gate
    (C1 gate 1) has already passed by the time the engine calls any deep
    analyzer, including this one.
    """
    resolved_use_external_api = use_external_api or _env_allows_external_api()

    backends = importlib.import_module("docsentinel.detectors.fact_check_protocol").FACT_CHECK_BACKENDS
    client_cls = backends[config.fact_check_backend]  # enum-validated at config load time
    api_key = os.environ.get(client_cls.API_KEY_ENV_VAR, "")

    if not resolved_use_external_api or not api_key:
        reasons = []
        if not resolved_use_external_api:
            reasons.append("pass --use-external-api (or set DOCSENTINEL_USE_EXTERNAL_API=1)")
        if not api_key:
            reasons.append(f"set {client_cls.API_KEY_ENV_VAR}")
        logger.warning("DS302 skipped: %s", "; ".join(reasons))
        # Recommended (decision S9, open as plan.md D5): the engine also folds this
        # exact reason into ScanResult.pending and a `doctor` line.
        return ()

    extract_claims = importlib.import_module("docsentinel.detectors._triples").extract_claims
    pipeline = deep_support.load_pipeline()
    all_claims: list[Claim] = []
    for doc in documents:
        if not doc.path.endswith(".md"):
            continue
        text = (root / doc.path).read_text(encoding="utf-8")
        all_claims.extend(extract_claims(pipeline, text, doc.path))

    salience = importlib.import_module("docsentinel.detectors.fact_check_salience")
    candidates = salience.select_candidates(tuple(all_claims), config)  # Story 02.0

    client: FactCheckClient = client_cls(api_key=api_key)
    try:
        return _check_candidates(client, candidates, config)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()


rules.ANALYZERS[DS302.code] = detect
```

`_check_candidates` (Story 01.0/03.0 boundary; implemented once Story 03.0's client exists) loops
the bounded `candidates` tuple in deterministic order, calls `client.check_claim(candidate.text)`
inside a `try`/`except FactCheckError` that logs and skips that one claim (C8), and builds a
`Finding` only when the normalized verdict is `"false"` or `"mixed"` **and**
`confidence >= config.fact_check_min_confidence`:

```python
Finding(
    rule=DS302.code,
    path=candidate.claim.path,
    message=(
        f"external fact-check: '{bounded_claim_text}' rated {result.verdict} "
        f"(confidence {result.confidence:.2f}) by {result.backend} - review to confirm"
    ),
    severity=DS302.severity,
    value=bounded_claim_text,      # same bounded candidate.text, neutralized at report time
    type="unverified claim",
)
```

`engine.py` additions (sketch): a new constant in `rules.py`,
`EXTERNAL_API_RULES: Final[frozenset[str]] = frozenset({"DS302"})`; `scan()` gains
`use_external_api: bool = False` as a keyword-only parameter next to the existing `link_root=`;
`_run_analyzer` gains the same forwarding branch `link_root` already has, keyed off a new
`_analyzer_accepts_use_external_api(analyzer)` helper, and only when `"DS302"` is in
`active_codes` does the resolved value get computed and forwarded at all (mirrors the
`LINK_ROOT_RULES.intersection(active_codes)` short-circuit, so a fast/standard scan or a deep scan
that never selected `DS302` touches none of this).

### How the gate is reported (decision S9 detail)

| Surface | Gate 2 off | Gate 2 on, backend unreachable for one claim | Gate 2 on, verdict clean |
|---|---|---|---|
| Log | One `WARNING`: `DS302 skipped: <reason(s)>` | One `DEBUG`/`WARNING` per failed claim, naming the claim's document path only (never the claim text) | nothing beyond the normal per-rule debug line |
| `ScanResult.pending` (recommended, open as D5) | One entry naming `DS302` and the missing prerequisite(s) | unaffected | unaffected |
| `ScanResult.findings` | none | none for that claim; other candidates still checked | none |
| Exit code | unaffected (`0`, deep is always advisory) | unaffected | unaffected |
| `docsentinel doctor` | `fact-check gate: off (...)` | unaffected (gate state, not per-call status) | `fact-check gate: on (backend: lenz)` |

## Security notes

- **Data exfiltration is the primary new risk this story introduces**, not path traversal. The
  mitigation is layered: (a) gate 1 (`deep_confirm`) and gate 2 (`use_external_api` + API key) are
  both required and both invoker-controlled; (b) Story 02.0's salience filter bounds *what* claims
  are even candidates; (c) the per-document and per-scan caps (`fact_check_max_claims_*`) bound
  *how many*; (d) the backend's fixed base URL (S8) bounds *where* it can go.
- **The backend base URL must be a fixed class constant, never config-sourced.** If a project
  `docsentinel.toml` could set it, a compromised or malicious repository could redirect "the
  Lenz client" to an attacker-controlled host while the user believes they are talking to Lenz —
  the attacker's server would receive both the claim text *and*, if the request shape leaks it,
  the Bearer token. This is the same class of risk Milestone 0009 plan.md contract C8 names for
  path-shaped config values, generalized to a URL.
- **The API key is never logged, never echoed, and never reaches `Config`.** `log.safe()` and the
  `neutralize_text` report sinks already exist for this class of problem (every path/value this
  project logs goes through one of them); the key specifically never reaches either, because it
  never reaches a log call or a `Finding` field at all — only the backend client's own request
  headers see it.
- **TLS verification stays on.** No config key is introduced that could disable certificate
  verification for a backend's HTTP client (Story 03.0 detail, named here as a constraint on the
  Protocol's implementers).
- **Timeouts and response-size bounds are fixed per backend** (S8) so a slow or hostile endpoint
  cannot hang a scan indefinitely or exhaust memory reading an unbounded response body — Story
  03.0 implements the actual cap; this story fixes that it must be a class constant, not a config
  option (a config option could only ever be used to *weaken* a safety bound here, never to make
  the tool safer, so it is simply not offered).
- **No deep-specific baseline exists** (C6); `DS302` findings are never silently suppressed by a
  profile-specific mechanism — only the one generic, already-audited `baseline.py` applies, and
  only if a project deliberately points `baseline` at a file containing a `DS302` fingerprint.
- Task 02 (Security Auditor) writes the threat model under `/docs/security/` and must cover, at
  minimum: whether `use_external_api` can be set from an unexpected surface (a stray `Config`
  field name collision, an environment variable typo that is lenient by accident), whether the
  gate-2 WARNING log line could ever include the key or claim text, the `pending`/`doctor`
  surfacing's own echo bounds, and a review of decision S9's recommendation before it is adopted
  as more than a recommendation.

## Acceptance criteria

- [ ] `FactCheckClient` is a `@runtime_checkable` `Protocol` with exactly `name`,
      `API_KEY_ENV_VAR` and `check_claim` required; `close` is optional and duck-typed.
- [ ] `DS302` is registered once in `RULES` and `ANALYZERS`, deep profile, warning, with **no**
      `opt_in_option` set.
- [ ] `use_external_api` is resolvable from `--use-external-api`, `scan(use_external_api=)`, and
      `DOCSENTINEL_USE_EXTERNAL_API=1` (exact match only); it is **not** a `Config` field and is
      **not** accepted by any TOML/JSON/pyproject/user-settings file (an attempt raises the
      existing generic "unknown option" `ConfigError`).
- [ ] The API key is read only inside a backend client class, only from its own
      `API_KEY_ENV_VAR`, and never appears in a log line, a `Finding`, or `ScanResult`.
- [ ] `fact_check_backend`/`fact_check_min_salience`/`fact_check_min_confidence`/
      `fact_check_max_claims_per_document`/`fact_check_max_claims_total` are typed, validated,
      loaded from standalone TOML, `[tool.doc_sentinel]`, JSON, user settings and an injected
      `Config`, with the defaults above.
- [ ] A scan with gate 2 off logs exactly one `WARNING` naming the missing prerequisite(s) and
      returns zero `DS302` findings; `import docsentinel` and every fast/standard scan still
      import nothing outside the standard library plus the already-present
      `scikit-learn`/`textstat`/`docsig` (standard) — `httpx` is imported only inside `detect()`.
- [ ] `docsentinel rules` and `docsentinel doctor` show the lines in the reference tables above.

## Test plan

| Layer | File (new) | Covers |
|---|---|---|
| Unit | `test_fact_check_gate_resolution.py` | `_env_allows_external_api`, the flag/keyword/env precedence, the two-reason WARNING message, exact `"1"`-only matching |
| Unit | `test_fact_check_config.py` | Defaults, both TOML forms, JSON, invalid enum/range values, the five keys' bounds |
| Unit | `test_fact_check_protocol.py` | A minimal fake client with only `name`/`API_KEY_ENV_VAR`/`check_claim` satisfies `isinstance(..., FactCheckClient)`; one missing member fails it; `FactCheckResult`/`FactCheckError` construction |
| Mock | `test_fact_check_engine_dispatch.py` | `engine.py` forwards `use_external_api=` only to an analyzer declaring it; `EXTERNAL_API_RULES` short-circuits when `DS302` is not selected; a fake `FactCheckClient` registered in `FACT_CHECK_BACKENDS` is used, `httpx` is never imported by this test file |
| Mock | `test_fact_check_no_key_logged.py` | A patched `logging` handler asserts the literal API key value never appears in any log record across every code path in this story |
| Integration | `test_ds302_gate_off_ds101.py` | A full `scan(profile="deep", deep_confirm=True)` with no `use_external_api` reports zero `DS302` findings, one `WARNING`, and (once S9 lands) the `pending` entry |

Asset cases live under the `ds302` folder once Story 04.0 adds fixtures (this story's own tests are
unit/mock only, with no document assets to fact-check yet).

## Docs to update

Deferred to Story 04.0 (do not edit these in this story):
`/docs/user/reference/rules.md`, `/docs/user/reference/configuration.md`,
`/docs/user/tutorial/cli.md`, `/docs/specs/finding-types.md`, `/docs/specs/fault-classes.md`,
`/CLAUDE.md` (environment variables list, Architecture section), `/README.md`,
`/examples/docsentinel.toml`, a proposed `/RELEASE_NOTES.json` entry.
