# Threat Model - Milestone 0010 Story 01.0 DS302 Consent Gates, API-Key Surface and Config Trust Tier - 2026-11-23

Pre-code threat model for
[Story 01.0](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/README.md)
([Task 02](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/02-threat-model-fact-check-gating.md)).
It covers who can open the `DS302` consent gate, where the fact-check API key enters the process,
what a project or user configuration file can and cannot do, and what the D5 surfacing (`pending`,
`doctor`, WARNING) can echo. No `DS302` code exists yet. The design under review is
[ADR 0007](/docs/adr/0007-fact-check-backend-protocol-and-dual-consent-gate.md) (Proposed,
including the Amendment of 2026-11-23), plan contracts
[C1](/docs/roadmap/0010-fact-check/plan.md#c1--dual-independent-consent-gates),
[C3](/docs/roadmap/0010-fact-check/plan.md#c3--api-key-environment-variable-naming),
[C5](/docs/roadmap/0010-fact-check/plan.md#c5--use_external_api-is-never-a-configuration-file-key),
[C6](/docs/roadmap/0010-fact-check/plan.md#c6--no-deep-specific-baseline),
[C8](/docs/roadmap/0010-fact-check/plan.md#c8--fail-soft-on-the-network-never-on-consent),
[C9](/docs/roadmap/0010-fact-check/plan.md#c9--layering-mining-detectors-fact-check-backends),
[C10](/docs/roadmap/0010-fact-check/plan.md#c10--owner-rulings-q1q4-2026-11-21) and
[C11](/docs/roadmap/0010-fact-check/plan.md#c11--one-candidate-source-for-ds302-and-extract-facts),
and the owner rulings D1 to D10, D5, Q1 to Q4 and Story 05.0 O1 to O4 recorded in
[status.md](/docs/roadmap/0010-fact-check/status.md#notes--decisions).

This model is a standing input for
[Task 03](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/03-fact-check-config-cli-and-env-surface.md),
[Task 04](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/04-factcheckclient-protocol-and-data-contracts.md),
[Task 05](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/05-ds302-registration-and-engine-dispatch.md)
and [Task 06](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/06-fixtures-and-tests.md).
Finding IDs FC-1, FC-2, ..., mitigation numbers M1, M2, ... and amendment numbers A1, A2, ... are
local to this file. The egress code itself (base URL, TLS, `trust_env`, timeouts, response size,
header construction, key shape validation) is out of scope and belongs to
[Story 03.0 Task 01](/docs/roadmap/0010-fact-check/03.0-lenz-backend-client/01-egress-threat-review.md);
where a finding here depends on a ruling there, it says so.

Handling of reference material: `examples/check_fact.py` was read only (not run) to confirm that it
reads `LENZ_API_KEY` (threat 8). `examples/docs/lenz_fact-checking.md` was not opened for this
task. This document contains no API-key value, no key prefix and no instruction from that file, and
no request was sent to `lenz.io` or any other host while writing it. The embedded key in
examples/docs/lenz_fact-checking.md stays a separate owner item (status.md Q5: rotate and remove).

Relevant weaknesses: CWE-807 (reliance on untrusted inputs in a security decision), CWE-15
(external control of a system setting), CWE-843 (type confusion), CWE-625 (permissive regular
expression), CWE-526/CWE-214 (sensitive information in environment variables / process
listings), CWE-209/CWE-532/CWE-200 (exposure through error messages, logs and other sinks),
CWE-522 (insufficiently protected credentials), CWE-441 (unintended proxy or intermediary,
confused deputy), CWE-359 (exposure of private information), CWE-778 (insufficient logging),
CWE-770 (allocation of resources without limits), CWE-117 (log injection); OWASP A01:2021 Broken
Access Control, A04:2021 Insecure Design, A05:2021 Security Misconfiguration, A09:2021 Security
Logging and Monitoring Failures. No CVE is cited: every behaviour below was confirmed in the
installed package sources (`h11` 0.16.0, `httpx` 0.28.1) or in DocSentinel's own code.

## Scope

In scope (design, not yet code):

- Gate 2 resolution: `--use-external-api` on `scan`/`baseline`, `scan(use_external_api=)`,
  `DOCSENTINEL_USE_EXTERNAL_API`, the gate helper `external_api_requested` /
  `resolve_external_api_gate` / `ExternalApiGate` in `detectors/fact_check.py` (ADR Contract 3).
- The engine forwarding and the Q1 count and `pending` entry (ADR Contracts 1 and 6).
- The API-key surface: the per-backend variable `DOCSENTINEL_FACTCHECK_<BACKEND>_API_KEY` (C3), its
  single read in `detect()` and its hand-off to `cls(api_key=...)` (ADR R5, Task 05 step 4.3).
- The six `fact_check_*` configuration keys and the absence of `use_external_api` from `Config`
  (C4, C5, ADR Contract 7).
- `FactCheckClient`, `FactCheckResult`, `FactCheckError`, `BACKEND_NAME_PATTERN`,
  `expected_api_key_env_var`, `load_backend` and the static module map (ADR Contract 4).
- The D5 surfaces (WARNING, `ScanResult.pending`, `doctor` line), the `rules` suffix, the `DS302`
  finding (`message`, `value`; ADR Contract 9) and its baseline fingerprint (C6).
- Every log sink of `/src/docsentinel/log.py`: stderr, the per-run DEBUG log file, the traceback
  path; and the CLI error paths in `/src/docsentinel/cli.py`.
- The test-suite environment (`/tests/conftest.py`) and the CI workflow environment.
- One paragraph on `extract-facts` (Story 05.0): that it opens no gate and reads no consent or key
  variable. Its template-loader change has its own review and is not repeated here.

Trust boundaries:

1. Scanned repository (documents, `docsentinel.toml`, `doc_sentinel.toml`, `pyproject.toml`, a
   `--config FILE.json` the invoker names, `.pre-commit-config.yaml`, workflow files) to the
   configuration loader and the engine.
2. User settings JSON (trusted owner, but a configuration file that C5 excludes from consent) to
   the loader.
3. Process environment and argv (invoker) to the gate helper and the backend construction.
4. `DS302` to the backend client (the key and the claim text cross here) and, from Story 03.0 on,
   to the network.
5. Backend results and exceptions back to `DS302`, then to findings, logs, reports and CLI error
   output.

## Assets

| ID | Asset | Why it matters |
|---|---|---|
| AS1 | The fact-check API key (`DOCSENTINEL_FACTCHECK_<BACKEND>_API_KEY`) | Bills the invoker's account and identifies them to the backend operator. Its value, length and any prefix must never reach a sink. |
| AS2 | Document-derived text that may leave the machine | Up to `fact_check_max_claims_total` claims of at most 1,000 code points each per scan. Private repositories may hold unpublished or confidential text. |
| AS3 | The invoker's quota and bill with the backend | Each claim costs a request; a hostile repository may try to spend it. |
| AS4 | The integrity of the advisory signal | "0 `DS302` findings" must never read as "fact-checked" when nothing was sent (Q1), and a backend must not be able to inject free text into a finding. |
| AS5 | Informed consent itself | Gate 2 is the only consent for egress; who can flip it is the core question of this model. |
| AS6 | Test and CI hermeticity | A developer's real key or consent variable must never reach a test run or a CI job by accident. |

## Actors

| ID | Actor | Trust | Capabilities relevant here |
|---|---|---|---|
| T1 | Contributor controlling the scanned repository's files | Untrusted | Writes every document and every configuration file of the repository, including `profile = "deep"`, `deep_confirm = true`, `select`, the six `fact_check_*` keys, `.pre-commit-config.yaml` `args:`, workflow files in a PR, `.envrc`, `.env`, `.devcontainer/`, `tox.ini`, `[tool.pytest.ini_options]`. Cannot write the invoker's environment or argv directly. |
| T2 | Invoker | Trusted | Chooses argv, the process environment, the library keyword and which repository to scan. |
| T3 | User settings file | Trusted owner, configuration tier | Can set the six `fact_check_*` keys and `deep_confirm`. Excluded from consent and key by C5. |
| T4 | CI runner | Trusted platform, untrusted inputs | Runs workflows on PR content; `pull_request_target` jobs run base-branch workflow code with repository secrets while processing PR-head data. Self-hosted runners can keep state between jobs. |
| T5 | Backend operator | Semi-trusted third party | Receives claim text and the bearer key; controls the response (verdict, confidence, citations, error bodies). Response handling is Story 03.0's scope; this model covers what of it can reach a finding. |

## STRIDE analysis

Summary by category; the numbered findings below carry the detail.

- **Spoofing.** Gate 2 consent is invoker-only by design (A1 of ADR 0007). Gate 1 (`deep_confirm`)
  is not: it is a configuration key, so a hostile repository can open it itself (FC-4). A
  configuration file can choose which backend name is used; `load_backend` binds the key name to the
  class name, so a class registered as one backend never receives another's key (FC-7).
- **Tampering.** Consent spoofing through a configuration key, a near-miss spelling, an injected
  `Config` attribute (FC-1), a lenient environment value (FC-2) or a truthy non-`bool` keyword
  (FC-3). Backend-name injection into an import or an environment-variable name (FC-7).
  Repository-controlled invocation (FC-4). Untrusted configuration widening egress volume up to the
  hard caps (FC-13).
- **Repudiation.** A claim that was sent but rated `true`/`unverifiable`, or that failed, leaves no
  record today (FC-10).
- **Information disclosure.** The key through log records, tracebacks, CLI error lines, `repr`,
  `ScanResult`, findings and reports (FC-5); gate-message echo bounds (FC-6); reading another
  tool's variable (FC-8); document text sent before or without consent (FC-9); `value` as an echo
  path (FC-11).
- **Denial of service.** Quota burn and wall-clock cost bounded by the claim caps, the time budget
  and the per-request timeout (FC-13). Closed-gate cost is zero (FC-9).
- **Elevation of privilege.** No configuration tier can grant egress (C5 holds, FC-1). The only
  elevation paths are environment-setting mechanisms that already execute repository code
  (pre-commit, tox, pytest, Makefiles, direnv after `direnv allow`), which no flag design can
  protect against (FC-4, residual R1).

## Findings

### [LOW] FC-1 A configuration file of any kind grants consent (threat 1)

- Vector / evidence:
  - ADR R4 and C5: `use_external_api` is never a `Config` field and never in `_CONFIG_OPTIONS`. A
    file naming it reaches the generic `Unknown config options: <names>` `ConfigError`
    (`/src/docsentinel/config.py:813-815`), which echoes key names only, never values. The four
    file kinds (standalone TOML under either name, `[tool.doc_sentinel]`, `--config FILE.json`, user
    settings JSON) share this builder.
  - Near-miss spellings (`use-external-api`, `useExternalApi`, `use_external_apis`,
    `external_api`, `fact_check_enabled`, a nested `[tool.doc_sentinel.fact_check]` table, a
    key with a trailing space) are all unknown keys and are refused the same way.
  - A key-shaped key (`fact_check_api_key`, `fact_check_lenz_api_key`) is also unknown. The error
    names the key, not its value, so a user who pastes the key into a settings file sees no echo.
  - Residual: `Config` is a frozen dataclass without `__slots__` (`config.py:284`), so a library
    caller can attach an extra attribute with `object.__setattr__`, or pass a `Config` subclass
    with a `use_external_api` property. The design never reads consent from `Config`
    (`external_api_requested` takes only the keyword and the environment), so this is safe only as
    long as no future code does `getattr(config, "use_external_api", ...)`.
- Impact: none today; a regression would let a cloned repository grant its own egress (AS5).
- Mitigation: **M1**.

### [LOW] FC-2 A lenient environment value opens gate 2 (threat 2)

- Vector / evidence: ADR Contract 3 specifies `os.environ.get(USE_EXTERNAL_API_ENV) == "1"`. The
  existing deep-profile parser is lenient: `_env_confirms()` lower-cases and accepts
  `{"1", "true", "yes"}` (`/src/docsentinel/engine.py:172-174`). An implementer who reuses it, or
  adds `.strip()`/`.lower()`/`int()`, would make `"true"`, `" 1"`, `"1\n"` or `"01"` grant egress.
- Impact: consent given by a value the user did not intend (for example a dotenv loader that keeps
  a trailing CR, or a shared `=true` convention).
- Mitigation: **M2**. Exact-`"1"` matches the `DOCSENTINEL_ALLOW_PYTHON_EXTENSIONS` precedent
  (threat model 0007 extensions).

### [MEDIUM] FC-3 Type confusion on the consent keyword (threat 3)

- Vector / evidence:
  - `scan(use_external_api="false")`: ADR Contract 1 makes `isinstance(value, bool)` the first
    statement of `scan()`, so `"false"`, `"1"`, `1`, `0` and `None` raise
    `ConfigError("use_external_api must be True or False")` before any filesystem access. This is
    sound.
  - Gap: the check lives only in `scan()`. `DS302`'s `detect()` is reachable directly
    (`rules.ANALYZERS["DS302"]`, or an import of `docsentinel.detectors.fact_check`), and the
    helper as specified is `use_external_api or os.environ.get(...) == "1"`. For
    `detect(..., use_external_api="false")` this returns the string `"false"`, which is truthy, so
    `ExternalApiGate.requested` is truthy and the gate opens when the key is set. The helper also
    returns a non-`bool` object that then flows into the dataclass.
- Impact: accidental consent by a library or test caller that bypasses `scan()` (AS2, AS3, AS5).
  Not attacker-reachable from a repository, which is why this is MEDIUM and not HIGH.
- Mitigation: **M3** (amendment A3).

### [MEDIUM] FC-4 Repository-controlled invocation and ambient consent (threat 4)

- Vector / evidence:
  - A malicious repository adds `--profile deep --i-understand-deep-is-heuristic
    --use-external-api` to its own `.pre-commit-config.yaml` `args:` for the `docsentinel-fast` hook
    (argparse keeps the last `--profile`, so the hook's `--profile fast` entry in
    `/.pre-commit-hooks.yaml` does not protect), or to a workflow it controls. With the developer's
    key exported in the shell, a commit spends the key and sends the repository's text.
  - A `pull_request_target` workflow that the maintainer wires with `--use-external-api` and the
    key secret sends PR-author-controlled text with the maintainer's key on every PR (quota burn,
    and abusive content sent under the maintainer's account; CWE-441). If the job also installs or
    runs code from the PR head, the key is directly exposed (the general "pwn request" pattern).
  - **Gate 1 is repository-controllable.** `profile` and `deep_confirm` are ordinary project keys,
    so a hostile `docsentinel.toml` with `profile = "deep"` and `deep_confirm = true` opens gate 1
    by itself. The story README's Security notes item (a) calls both gates "invoker-controlled";
    that is inaccurate. Against a hostile repository, gate 2 alone carries the egress consent.
  - **Ambient environment consent.** A developer who exports `DOCSENTINEL_USE_EXTERNAL_API=1` and
    the key in a shell profile, then runs a plain `docsentinel scan` (no flags) in a cloned hostile
    repository with the configuration above, sends up to `fact_check_max_claims_total` claims with
    no per-run action. The repository can also raise the caps to their hard maxima (FC-13).
  - Repository-supplied environment files (`.envrc`, `.env` read by an IDE, `.devcontainer`
    `containerEnv`, `tox.ini` `setenv`, pytest-env) can set `DOCSENTINEL_USE_EXTERNAL_API`. Every
    one of these already runs repository code or requires an explicit user approval
    (`direnv allow`), and such code can read the key directly, so gate 2 cannot add protection there
    (residual R1, the same ruling as threat model 0007 extensions R4).
- Impact: AS2, AS3 and AS5 for an invoker who misconfigures their environment or CI; never for an
  invoker who passes the flag per run.
- Ruling: **documentation guidance plus repository-hygiene tests; no runtime code control.** A
  runtime heuristic (detecting `PRE_COMMIT`, `CI` or `GITHUB_EVENT_NAME`) is bypassable, breaks
  legitimate uses and has no precedent: `--link-root` and `DOCSENTINEL_ALLOW_PYTHON_EXTENSIONS` are
  governed by documentation only. The INFO line of FC-10 gives every gate-open run a visible stderr
  trace, which is the one code-level aid this model requires.
- Mitigation: **M4** (amendment A9; owner question OQ2).

### [HIGH] FC-5 Key disclosure through an uncaught backend or transport exception (threat 5)

- Vector / evidence:
  - The designed sinks are clean: the key is read once in `detect()` and passed straight into
    `cls(api_key=...)` (ADR R5); `ExternalApiGate` stores only `key_present: bool`; `doctor` reports
    only whether the variable is set; findings, `pending` and `ScanResult` carry no key; the
    Protocol docstring requires a `__repr__` that hides the key; `httpx` masks the `Authorization`
    header as `[secure]` in its own `Headers` repr (`httpx/_models.py:53,130-135`).
  - The gap is the **exception path**. Task 05 catches only `ImportError`/`TypeError` from
    `load_backend` and `FactCheckError` from `check_claim`; S10 says "any other exception type
    propagates". Exceptions raised while the key is in use carry it:
    - `h11` formats a rejected header value with `repr` into the message (`Illegal header value
      {!r}`, `h11/_headers.py:166`), and `httpx` re-raises transport errors with the same text
      (`message = str(exc); raise mapped_exc(message) from exc`, `httpx/_transports/default.py:117-118`).
      A key with a trailing CR/LF or space (a common copy-paste artefact) therefore puts
      `Bearer <full key>` into an exception message.
    - A non-ASCII key raises `UnicodeEncodeError` (a `ValueError`) when `httpx` encodes the header
      (`httpx/_models.py:82`); its message names one key character and its position.
    - A backend that validates the key in `__init__` (Story 03.0 step 7) raises `FactCheckError`
      from the constructor, which Task 05 step 4.3 does not catch.
  - Where those reach today:
    - `cli.py:1182-1183` prints `Scan failed: <str(exc)>` to **stderr** for any `ValueError`
      (neutralised, not length-capped), so the `UnicodeEncodeError` text reaches stderr and CI logs.
    - Any other `Exception` reaches `_UnexpectedErrorLog` (`cli.py:887`), which logs
      `unexpected error: <type>: <safe(exc)>` at ERROR to **stderr** (up to 200 characters of the
      message, so most or all of a key) and writes the full traceback, including the
      `__cause__`/`__context__` chain, to the per-run log file (`log.py:136-160`; the formatter
      neutralises but does not redact).
    - A library caller's own error reporter (for example one that captures frame locals) sees the
      original exception, its chain and frames whose locals include the client.
  - Length or prefix leaks: the reasons text, `doctor` and WARNING lines carry only the variable
    name (FC-6). No designed line logs the key's length. The exception path above is the only
    length/prefix leak found.
- Impact: AS1 disclosed to stderr, CI logs and the 0600 log file; CWE-209, CWE-532, CWE-522.
- Mitigation: **M5** (amendments A4, A5). Rated HIGH, not CRITICAL: no code exists yet, the leak
  needs a malformed key or a backend bug, and the fix is a small, specifiable boundary in Task 05.
  It is a merge-gate condition (see Verdict).

### [LOW] FC-6 Echo bounds of the gate messages (threat 6)

- Vector / evidence:
  - WARNING and `pending`: `"DS302 skipped: " + "; ".join(reasons())`, where `reasons()` is one fixed
    string and `f"set {key_env_var}"`; `key_env_var` derives from an enum-validated backend name.
    No value, no claim, no path. Confirmed fixed.
  - `doctor`: `fact-check gate: on (backend: <name>)` or `off (<reasons>)`, computed with
    `use_external_api=False` and the environment only. Confirmed fixed.
  - The unavailable-backend WARNING echoes only the exception **type name**, never its message.
    Confirmed fixed.
  - Gap: Task 03 step 5 specifies `fact-check gate: error: <neutralize_text(message)>` for a
    configuration error. That re-echoes a `ConfigError` message, which can carry
    repository-supplied key names (unbounded, pre-existing finding T03-2 of threat model 0009 user
    settings) and which `doctor` already prints on several other lines (T05-2). It is not a
    new class of echo, but it breaks the "fixed text only" property of the gate line.
  - The per-claim WARNING echoes `safe(str(exc))` of a `FactCheckError`, whose message is fixed by
    contract (at most 200 characters, no body, header, key or claim). The bound depends on each
    backend honouring the contract; `safe()` caps it at 200 characters.
- Impact: low; a configuration typo could be echoed once more.
- Mitigation: **M6** (amendment A2).

### [LOW] FC-7 The backend name as an injection vector (threat 7)

- Vector / evidence:
  - `fact_check_backend` is validated by `_require_enum` against `FACT_CHECK_BACKEND_NAMES`
    (`config.py:716-727`, message lists the allowed names only, never the value). `load_backend`
    imports only a value of the static `FACT_CHECK_BACKEND_MODULES` map and checks
    `cls.name == name` and `cls.API_KEY_ENV_VAR == expected_api_key_env_var(name)`. A configuration
    value is never passed to `importlib`. Sound.
  - Gap 1: `BACKEND_NAME_PATTERN = r"^[a-z][a-z0-9]{0,31}$"` used with `re.match` accepts a
    trailing newline (`$` matches before a final `\n`; confirmed: `re.match` accepts `"lenz\n"`,
    `re.fullmatch` refuses it). `FactCheckResult.backend` is validated with this pattern, and the
    value lands in the finding `message`. `expected_api_key_env_var("lenz\n")` would build a name
    with an embedded newline. The configuration path is protected by the enum; an injected `Config`
    or a backend result is not.
  - Gap 2: ADR Contract 3 computes `key_env_var = expected_api_key_env_var(config.fact_check_backend)`
    and then checks membership. For an injected `Config` with a non-matching name this raises
    `ValueError` (not the documented `ConfigError`), which the CLI would print as `Scan failed:`
    and a library caller would not expect.
  - With two or more backends registered, a repository's configuration chooses which third party
    receives the text (the key follows the name, so no key crosses backends). Not reachable with
    one backend; recorded as owner question OQ3.
- Impact: log/report injection (neutralised by the existing sinks) and an unexpected exception
  type; no import or key misrouting.
- Mitigation: **M7** (amendments A3, A6).

### [LOW] FC-8 Reading an environment variable meant for another tool (threat 8)

- Vector / evidence: `examples/check_fact.py` reads `LENZ_API_KEY` (lines 8 and 72-74). A
  developer who used it has that variable set. The design reads only the C3 name derived from the
  validated backend name, and `load_backend` holds `API_KEY_ENV_VAR` equal to it. Nothing reads
  `LENZ_API_KEY`. Separately, `httpx` reads proxy, CA-bundle and `.netrc` settings from the
  environment by default (`trust_env=True`, `httpx/_client.py:201`); that ruling belongs to Story
  03.0 Task 01 step 3 and is not decided here.
- Impact: a variable set for another tool silently opening gate 2 or being sent to a backend.
- Mitigation: **M8**.

### [LOW] FC-9 Exposure volume before the gate (threat 9)

- Vector / evidence: ADR Contract 2 and Task 05 step 4.1 resolve the gate first and return `()`
  before reading a document, loading a pipeline or importing `httpx`, `mining.claims`,
  `mining.salience`, `mining.clustering` or a backend. Module-level imports of
  `detectors/fact_check.py` are the standard library, `docsentinel.config`, `docsentinel.mining.nlp`
  (which itself imports only `importlib`, `logging` and `docsentinel.log`) and
  `docsentinel.fact_check.protocol` (standard library only). The engine itself already reads every
  discovered document once (`_partition_readable`), so "no document read" means no additional
  read and nothing extracted for `DS302`. With `DS301` active in the same scan, spaCy and
  `mining.claims` are loaded by `DS301`, so a `sys.modules` test for `mining.claims` must use
  `select = ["DS302"]`.
- Impact: none if implemented as specified.
- Mitigation: **M9**.

### [MEDIUM] FC-10 Repudiation: nothing records what was sent (threat 10)

- Vector / evidence: a `DS302` finding's `value` is the only record of sent text, and only for
  claims rated `false`/`mixed` at or above `fact_check_min_confidence`. Claims rated `true` or
  `unverifiable`, claims whose call failed and the total volume leave no trace above DEBUG. An
  invoker (or a CI reviewer) cannot tell from the default output whether 0 or 500 claims left the
  machine. This also hides an FC-4 abuse.
- Ruling: **an INFO line with counts only is required.** Exactly one per `detect()` that passed
  both gates, emitted from a `finally` block so it is also logged when the loop stops early:
  `DS302: sent <n> claim(s) from <m> document(s) to backend <name>; <f> failed, <r> reported, <s> not sent (time budget)`.
  Integers and the enum-validated backend name only: no path, no claim text, no key-related value.
  The per-document breakdown stays at DEBUG and may name `safe(path)` with a count, never text. The
  claim text itself is never logged (log.py convention: document content is never logged); the
  exact text a scan would send is already available offline from `extract-facts` (C11).
- Impact: CWE-778; weak consent transparency (AS5).
- Mitigation: **M10** (amendment A7).

### [LOW] FC-11 Baseline interplay and `value` as an echo path (threat 11)

- Vector / evidence:
  - A baseline cannot open a gate: `load_baseline` accepts exactly `{"fingerprints": [str, ...]}`
    (`/src/docsentinel/baseline.py:44-48`) and only filters findings after the scan. Gate state is
    never read from it. Deep is advisory, so a baseline never changes `DS302`'s effect on the exit
    code (C6).
  - The baseline file stores `rule:path:sha256(message)[:12]`; no claim text is persisted in it.
  - Q2: confidence moved into `value` (`compare=False`), so the fingerprint is run-stable for a
    given verdict. `value` is an existing report-only field; it reaches the text and GitHub sinks
    only through the neutralising filters and the JSON sink with `ensure_ascii`. It is wider than
    usual (up to about 1,030 characters) but is the document's own text plus fixed-format
    verdict and confidence. **No new echo path.**
  - Every backend-supplied part of a finding is validated: `verdict` is one of four literals,
    `confidence` a finite number in `[0, 1]` formatted `.2f`, `backend` matches the name pattern.
    `citations` (backend-controlled URLs or text, up to 8 x 500 characters) is not used by
    `DS302` in this milestone; it must stay out of every finding and log line until a later model
    reviews it (link or phishing text injected into reports).
  - A repository can commit a baseline that suppresses a specific `DS302` finding, as it can for
    any rule. Advisory only; no new risk.
- Impact: none beyond the accepted wider `value` (ADR Negative consequences).
- Mitigation: **M11**.

### [LOW] FC-12 Test-suite hygiene (threat 12)

- Vector / evidence: Task 06 step 1 adds an autouse fixture that removes
  `DOCSENTINEL_USE_EXTERNAL_API` and every `DOCSENTINEL_FACTCHECK_*` variable. Sound. Gaps: the
  fixture does not clear `LENZ_API_KEY` (defence in depth against a test that accidentally imports
  example code), nothing proves the fixture runs, and nothing stops a CI workflow from exporting a
  key secret or the consent variable at job level.
- Impact: a developer's real key reaching a test, a fake, a log captured by a test, or a network
  call (AS1, AS6).
- Mitigation: **M12**.

### [LOW] FC-13 Untrusted configuration widens egress volume and wall-clock cost

- Vector / evidence: the six `fact_check_*` keys are project-settable (ADR Configuration surface).
  For an invoker who has opened gate 2, a hostile repository can raise
  `fact_check_max_claims_total` from 25 to 500 and `fact_check_max_claims_per_document` from 3 to
  50 (a 20x increase in requests and sent text), lower `fact_check_min_salience` to `0.0`, and
  raise `fact_check_time_budget_seconds` from 300 to 3600. The story README's phrase "a project may
  narrow (never widen past the hard caps)" is accurate only in that the hard caps bound it; the
  defaults themselves are widenable 20x. ADR Contract 7 records the budget part as accepted.
- Impact: AS2, AS3, bounded by the hard caps, the budget and the per-request timeout (CWE-770
  mitigated by hard caps).
- Mitigation: covered by M4 (documentation) and M10 (the INFO line shows the volume); owner
  question OQ1 for a structural option.

### [LOW] FC-14 Specification inconsistencies that would mislead an implementer

- Vector / evidence: the story README CLI table says `DOCSENTINEL_USE_EXTERNAL_API` is "read once
  by `engine.py`" and the key is "read only inside the backend's own client class, at construction
  time". ADR Contract 3 and R5 and Task 05 say the gate helper in `detectors/fact_check.py` is the
  only reader of the consent variable, the engine never reads it, and the key is read once in
  `detect()` and passed to `cls(api_key=...)`. The story README Security notes item (a) calls gate 1
  invoker-controlled (FC-4). The ADR and Task 05 are correct; the README should follow them.
- Impact: a reader-induced implementation that reads the key or consent variable in a second
  module, which the M8 test would then flag late.
- Mitigation: amendment A8 (story README; not a Tasks 03 to 06 change).

### Not applicable / no finding

- Shell, SQL, `eval`: none on any path in scope.
- Prompt injection: the backend is a fact-check API, not an LLM DocSentinel instructs; claim text is
  data in a JSON body (Story 03.0 owns the request shape).
- `rules` output: the `DS302` suffix is a fixed literal (ADR Contract 5).
- `ScanResult`: gains no field (ADR driver 10).
- GitHub workflow-command injection through claim text in annotations: `gha_data` escapes `%`, CR
  and LF, `gha_property` also escapes `:` and `,`, and `##[` is rewritten, so claim text cannot
  start a new command line (existing control, `telemetry/filters.py`).

### `extract-facts` (Story 05.0), scoped confirmation

[Story 05.0](/docs/roadmap/0010-fact-check/05.0-extract-facts-cli/README.md) decision X10 and ADR
0007 Contract 11 state that the command never resolves `use_external_api`, never reads
`DOCSENTINEL_USE_EXTERNAL_API` or any `DOCSENTINEL_FACTCHECK_*` variable, never calls
`load_backend`, `resolve_external_api_gate` or `external_api_requested`, never imports `httpx` or a
backend module, and has no `--use-external-api` option (argparse rejects it with exit `2`). It
therefore has no egress path and never opens the gate. Its CLI-only `--weights` and
`--dedup-threshold` (and their library keywords) build a `SelectionPolicy` that is never a `Config`
field, never read from a file or the environment, and cannot reach `DS302`, because
`collect_candidates()` has no `policy` parameter (C11, X5, owner ruling O1). Its `--min-salience`,
`--max-per-document` and `--max-total` overrides replace `Config` values only for that command's
own run. Confirmed by design; the Story 05.0 tests (`test_extract_facts_offline.py`, the
fresh-interpreter check in `test_extract_facts_cli_ds302.py`) enforce it. The command is the
recommended way to preview, offline, exactly what a gate-open `DS302` scan would send (M4).

## Mitigations

Every mitigation names the task that implements it and the test that pins it. Test files are the
ones Task 06 already lists unless marked **new**.

- **M1 (FC-1).** Consent is read only from the `use_external_api` keyword and the environment,
  never from `Config` (no `getattr` on `Config` for any consent name). No `Config` field and no
  `_CONFIG_OPTIONS` entry for any spelling. Implements: Tasks 03 and 05. Tests:
  `tests/unit/test_fact_check_config.py` (each of the four file kinds with `use_external_api`, the
  near-miss list of FC-1, and `fact_check_lenz_api_key` set to the sentinel: unknown-option
  `ConfigError` whose message does not contain the sentinel);
  `tests/unit/test_fact_check_gate_resolution.py` (an injected `Config` carrying
  `use_external_api=True` through `object.__setattr__`, and a `Config` subclass with a property of
  that name, both give `requested is False`).
- **M2 (FC-2).** `external_api_requested` compares `os.environ.get(USE_EXTERNAL_API_ENV)` to `"1"`
  exactly; it never calls `_env_confirms`, `.lower()`, `.strip()`, `int()` or `bool()` on the value.
  Implements: Task 05 step 3. Tests: `tests/unit/test_fact_check_gate_resolution.py`, parametrised:
  only `"1"` is true; `"true"`, `"TRUE"`, `"yes"`, `" 1"`, `"1 "`, `"1\n"`, `"1\r"`, `"01"`, `"0"`,
  `""` and a full-width digit one are false; plus an AST assertion that the helper does not
  reference `_env_confirms`.
- **M3 (FC-3, FC-7).** The `bool` check exists in two places: the first statement of `scan()`
  (as specified) and inside `external_api_requested` / `resolve_external_api_gate`, which raise
  `ConfigError("use_external_api must be True or False")` for a non-`bool` and return a real `bool`
  (`use_external_api is True or env == "1"`). Implements: Task 05 steps 3 and 6. Tests:
  `tests/mock/test_fact_check_engine_dispatch.py` (`scan(use_external_api=...)` with `"false"`,
  `"1"`, `1`, `0`, `None` raises before discovery, with a discovery spy not called);
  `tests/unit/test_fact_check_gate_resolution.py` (`external_api_requested("false")` raises;
  calling `detect(..., use_external_api="false")` directly with the fake key set raises and the
  fake backend records no call).
- **M4 (FC-4, FC-13).** Documentation guidance, in the same style as the `--link-root` and
  `DOCSENTINEL_ALLOW_PYTHON_EXTENSIONS` guidance, in the user docs for `DS302` and the CLI reference:
  - never put `--use-external-api` in pre-commit `args:` or a `.pre-commit-hooks.yaml` entry;
  - never use it, or expose a `DOCSENTINEL_FACTCHECK_*` secret, in a `pull_request_target`
    workflow; never set `DOCSENTINEL_USE_EXTERNAL_API` or a key at workflow or job level; for CI,
    run gate-open scans only from a `workflow_dispatch` or scheduled workflow on the default branch,
    with the key scoped to that single step's `env:`;
  - never set `DOCSENTINEL_USE_EXTERNAL_API` in a shell profile, `.envrc`, `.env`,
    `.devcontainer` or `tox.ini`; prefer the per-run flag for interactive use, and pass the key per
    command rather than exporting it globally;
  - `deep_confirm` and `profile` can be set by the scanned repository, so the flag is the only
    egress consent; a repository's configuration can raise the claim caps up to 500 claims and the
    budget up to one hour;
  - preview what would be sent with `docsentinel extract-facts` before the first gate-open scan of
    a repository.

  No runtime code control. Implements: Story 04.0 Task 04 (docs, acceptance criterion) and Task 03
  step 3 (the hook file stays flag-free). Tests: **new**
  `tests/unit/test_fact_check_repo_hygiene.py`: `/.pre-commit-hooks.yaml` contains no
  `--use-external-api`, and no file under `/.github/workflows/` contains `--use-external-api`,
  `DOCSENTINEL_USE_EXTERNAL_API` or `DOCSENTINEL_FACTCHECK_`.
- **M5 (FC-5).** Key containment at the `DS302` boundary:
  1. The key is read with `os.environ.get(client_cls.API_KEY_ENV_VAR)` directly inside the
     constructor call; a missing or empty value at that point (environment changed since the gate)
     logs the gate WARNING and returns `()`; no `KeyError` escapes.
  2. Client construction is wrapped: `FactCheckError` logs one WARNING
     `DS302 skipped: backend <name> could not be initialised (FactCheckError)` and returns `()`.
  3. Any other exception from construction or from `check_claim` is replaced by
     `RuntimeError(f"DS302: backend {name} raised {type(exc).__name__}")`, raised **after** leaving
     the `except` block (so it has no `__cause__` and no `__context__`), and propagates as the S10
     programming error. Only the type name is kept.
  4. No `exc_info=True`, `logger.exception` or `stack_info` on any `DS302` or backend path.
  5. A backend stores the key only in a private attribute and defines a `__repr__` without it
     (Task 04 docstring, Story 03.0); `FactCheckError` messages are fixed text of at most 200
     characters (ADR Contract 4).

  Implements: Task 05 steps 4.2, 4.3 and 4.6 (amendments A4, A5), Task 04 (docstring). Tests:
  `tests/mock/test_fact_check_no_key_logged.py`, extended with fakes that (a) raise
  `FactCheckError` from `__init__`, (b) raise `ValueError` whose message contains the sentinel from
  `__init__`, (c) raise a plain `Exception` whose message contains `Bearer <sentinel>` from
  `check_claim` (the `h11` shape), and (d) succeed. Each case runs through `cli.main` with
  `DOCSENTINEL_LOG_DIR` set and asserts that the sentinel and its first eight characters appear in
  none of: stdout, stderr, the per-run log file (including tracebacks), every `LogRecord`
  (`msg`, `args`, `exc_text`), `ScanResult`, `pending`, every `Finding` field, every packaged
  template's rendered report, `repr` of the client, `doctor` and `rules` output; and that the
  re-raised `RuntimeError` has `__cause__ is None` and `__context__ is None`.
- **M6 (FC-6).** The WARNING, the `pending` entry and the `doctor` line are composed only of fixed
  text, the C3 variable name and the enum-validated backend name. In the configuration-error state
  the `doctor` gate line is the fixed text `fact-check gate: unknown (configuration error)`; the
  error itself stays on the existing `doctor` error line. Implements: Task 03 step 5 (amendment A2),
  Task 05 step 3. Tests: `tests/integration/test_fact_check_gate_off_ds302.py` (exact-string
  equality of all three surfaces for: neither, key only, flag only); the Task 03 `doctor` cases
  (config-error state gives exactly the fixed line, and the repository's offending key name
  appears in no `fact-check gate:` line).
- **M7 (FC-7).** `BACKEND_NAME_PATTERN` is applied with `re.fullmatch` (or written with `\Z`), in
  `expected_api_key_env_var` and `FactCheckResult.__post_init__`. `resolve_external_api_gate`
  checks membership first and only then derives `key_env_var`, so an injected `Config` with any
  invalid name raises `ConfigError`, never `ValueError`. `load_backend` imports only a value of
  `FACT_CHECK_BACKEND_MODULES`. Implements: Task 04 step 5, Task 05 step 3 (amendments A3, A6).
  Tests: `tests/unit/test_fact_check_protocol.py` (`"lenz\n"`, `"Lenz"`, `"lenz "`, a full-width
  letter, 33 characters, `"../x"`, `"docsentinel.fact_check.lenz"` refused; `importlib.import_module`
  patched and never called with an unmapped name; `FactCheckResult(backend="lenz\n")` raises
  `FactCheckError`); `tests/unit/test_fact_check_gate_resolution.py` (injected
  `Config(fact_check_backend="lenz\n")` raises `ConfigError`).
- **M8 (FC-8, FC-14).** Only `detectors/fact_check.py` reads `DOCSENTINEL_USE_EXTERNAL_API` and a
  `DOCSENTINEL_FACTCHECK_*` variable; no module under `src/docsentinel/` contains the string
  `LENZ_API_KEY`; no module under `src/docsentinel/fact_check/` reads `os.environ` or calls
  `os.getenv` (the key arrives through the constructor). The `trust_env` ruling stays with Story
  03.0 Task 01. Implements: Tasks 04 and 05. Tests: **new** `tests/unit/test_fact_check_env_reads.py`
  (the AST/grep test Task 06 step 5 calls for, extended to all three rules);
  `tests/mock/test_fact_check_engine_dispatch.py` (only `LENZ_API_KEY` set to the sentinel, flag
  given: gate closed, reason `set DOCSENTINEL_FACTCHECK_FAKE_API_KEY`, fake records no call).
- **M9 (FC-9).** Closed gate means no extraction, no candidate selection, no backend load and no
  `httpx` import. Implements: Task 05 steps 2 and 4.1. Tests:
  `tests/mock/test_fact_check_engine_dispatch.py` (spies on `mining.nlp.load_pipeline`,
  `collect_candidates`/`select_candidates`, `load_backend` and the fake constructor: none called
  with the gate closed); the fresh-interpreter test (`python -I`): a confirmed deep scan with
  `select = ["DS302"]` and the gate closed leaves `httpx`, `docsentinel.fact_check.lenz`,
  `docsentinel.mining.claims`, `docsentinel.mining.salience` and `docsentinel.mining.clustering`
  out of `sys.modules`.
- **M10 (FC-10, FC-13).** The INFO counts line of FC-10, exactly once per gate-open `detect()`,
  from a `finally` block; none on a closed gate. Implements: Task 05 step 5 (amendment A7). Tests:
  `tests/mock/test_fact_check_engine_dispatch.py` (gate open: exactly one INFO record with the
  format and integer args plus the backend name; also emitted when the M5 `RuntimeError`
  propagates mid-loop, with the counts so far; gate closed: none; record text contains no path and
  no claim text).
- **M11 (FC-11).** Findings are built only from the validated `verdict`, the `.2f` confidence,
  the validated backend name and the candidate text. `citations` never reaches a `Finding`, a log
  record or a report. The baseline loader keeps its exact schema. Implements: Task 05 step 5.
  Tests: `tests/mock/test_fact_check_engine_dispatch.py` (the Q2 fingerprint case; a fake result
  whose `citations` hold a marker string: the marker is absent from findings, log records and every
  packaged template's output).
- **M12 (FC-12).** The autouse fixture removes `DOCSENTINEL_USE_EXTERNAL_API`, every variable
  starting with `DOCSENTINEL_FACTCHECK_`, and `LENZ_API_KEY`. Tests only ever set the sentinel
  `sentinel-not-a-real-key-0010` through `monkeypatch`. CI never defines a key secret or the consent
  variable for the test or self-scan jobs. Implements: Task 06 step 1. Tests: **new**
  `tests/unit/test_fact_check_env_isolation.py` (runs a child `pytest -p docsentinel.pytest_plugin`
  on one inline test with the three variables set in the parent environment and asserts the child
  test sees none of them); the M4 hygiene test covers the workflows.

### Mitigation-to-test map

| Mitigation | Implements | Test file |
|---|---|---|
| M1 | Tasks 03, 05 | unit `test_fact_check_config.py`, unit `test_fact_check_gate_resolution.py` |
| M2 | Task 05 | unit `test_fact_check_gate_resolution.py` |
| M3 | Task 05 | mock `test_fact_check_engine_dispatch.py`, unit `test_fact_check_gate_resolution.py` |
| M4 | Story 04.0 Task 04, Task 03 | unit `test_fact_check_repo_hygiene.py` (new) plus the Story 04.0 Task 04 docs criterion |
| M5 | Tasks 04, 05 | mock `test_fact_check_no_key_logged.py` |
| M6 | Tasks 03, 05 | integration `test_fact_check_gate_off_ds302.py`, Task 03 `doctor` cases |
| M7 | Tasks 04, 05 | unit `test_fact_check_protocol.py`, unit `test_fact_check_gate_resolution.py` |
| M8 | Tasks 04, 05 | unit `test_fact_check_env_reads.py` (new), mock `test_fact_check_engine_dispatch.py` |
| M9 | Task 05 | mock `test_fact_check_engine_dispatch.py`, fresh-interpreter test |
| M10 | Task 05 | mock `test_fact_check_engine_dispatch.py` |
| M11 | Task 05 | mock `test_fact_check_engine_dispatch.py` |
| M12 | Task 06 | unit `test_fact_check_env_isolation.py` (new), unit `test_fact_check_repo_hygiene.py` (new) |

## D5 surfacing review (S9, as ratified in ADR 0007)

The ratified design (one WARNING from `detect()`, one `pending` entry from the engine, one `doctor`
line, no `opt_in_option` retrofit, `DS302` subtracted from `rules_evaluated` while closed)
introduces **no new echo path**. All three surfaces are built from the same `reasons()` strings,
which contain fixed text and one derived variable name; the engine logs no gate WARNING, so a scan
logs it once; the `doctor` line reads only the environment. The one deviation is the
configuration-error form of the `doctor` line (FC-6, fixed by M6). Refusing the D2 shadow
`Config.use_external_api` field is also the right security call: a `Config` attribute of that name
invites a later loader change that makes consent file-settable (FC-1). The resolve-twice
consequence (engine and `detect()`) cannot widen consent: both reads use the same helper, and a
changed environment between them can only close the gate in `detect()` (M5 item 1).

## Required spec amendments

Apply before the named task starts. A1 to A7 change Tasks 03 to 06; A8 and A9 change other
documents.

- **A1 (Task 06 steps 1, 4, 5).** Add the tests named in M1 to M12, including the three new files
  `tests/unit/test_fact_check_repo_hygiene.py`, `tests/unit/test_fact_check_env_reads.py` and
  `tests/unit/test_fact_check_env_isolation.py`; clear `LENZ_API_KEY` in the autouse fixture; run
  the M9 fresh-interpreter case with `select = ["DS302"]`; run the M5 cases through `cli.main`
  with a log directory and inspect the log file.
- **A2 (Task 03 step 5 and its `doctor` acceptance criterion).** Replace
  `fact-check gate: error: <neutralize_text(message)>` with the fixed line
  `fact-check gate: unknown (configuration error)`.
- **A3 (Task 05 step 3; ADR Contract 3).** `external_api_requested` and
  `resolve_external_api_gate` raise `ConfigError("use_external_api must be True or False")` for a
  non-`bool` and return a real `bool`; `resolve_external_api_gate` checks backend membership
  before calling `expected_api_key_env_var`.
- **A4 (Task 05 step 4.3; ADR R5).** Read the key with `os.environ.get(...)` inside the
  constructor call; an absent or empty value logs the gate WARNING and returns `()`. Wrap
  construction: `FactCheckError` gives the fixed `could not be initialised` WARNING and `()`.
- **A5 (Task 05 steps 4.6 and 5, the S10 acceptance criterion; story decision S10).** "Any other
  exception type propagates" becomes "any other exception from client construction or
  `check_claim` is replaced by `RuntimeError("DS302: backend <name> raised <type name>")`, raised
  outside the `except` block with no cause or context, and propagates". No `exc_info` on these
  paths.
- **A6 (Task 04 step 5; ADR Contract 4).** `BACKEND_NAME_PATTERN` is matched with `re.fullmatch`
  everywhere it is used.
- **A7 (Task 05 step 5).** Replace "If the Task 02 threat model requires it (threat 10), also log
  one INFO line" with the required INFO line of FC-10, emitted from a `finally` block.
- **A8 (story README, CLI and library reference table and Security notes item (a); not Tasks 03
  to 06).** The consent variable is read only by the gate helper in `detectors/fact_check.py`; the
  key is read once in `detect()` and passed to the constructor; gate 1 is repository-settable, so
  gate 2 alone is the egress consent.
- **A9 (Story 04.0 Task 04, docs acceptance criteria).** Add the M4 guidance items.

Story 03.0 Task 01 input (not an amendment here): its step 7 key validation must raise
`FactCheckError` from the constructor (which A4 now handles), and the Lenz client must translate
every `httpx`/`h11` exception into a fixed-text `FactCheckError` raised without exception chaining,
because the `h11` header error carries the full header value (FC-5).

## Open questions for the owner (not blocking)

- **OQ1 (FC-13).** Should raising `fact_check_max_claims_total`, `fact_check_max_claims_per_document`
  or `fact_check_time_budget_seconds` above their defaults be allowed only from user settings or the
  invoker, with project configuration limited to narrowing? Today a hostile repository can widen
  volume 20x for an invoker who opened the gate. Recommended: keep as designed for this milestone
  (hard caps, the INFO line and M4 bound it) and revisit with usage data.
- **OQ2 (FC-4).** Is the environment-variable form of gate 2 needed beyond CI? It is the only
  ambient form of consent. Recommended: keep it (ratified D3), document it as step-scoped CI use
  only (M4).
- **OQ3 (FC-7).** When a second backend ships, should `fact_check_backend` (which third party
  receives the text) remain project-settable? Re-assess in that backend's threat model.

## Residual risks

- **R1.** Mechanisms that already execute repository code (pre-commit hook definitions, pytest
  `conftest.py` and env plugins, tox, Makefiles, direnv after approval, IDE task runners) can set
  the consent variable and read the key directly. Gate 2 adds no protection there and none is
  claimed.
- **R2.** The resolve-twice design reads the environment twice; a change between the reads can
  only close the gate (M5 item 1).
- **R3.** The per-claim WARNING trusts each backend to keep `FactCheckError` text fixed; `safe()`
  caps it at 200 characters. A backend that violates the contract can echo up to 200 characters of
  whatever it put in the message.
- **R4.** The embedded key in examples/docs/lenz_fact-checking.md remains committed (status.md
  Q5); rotation and removal are owner actions outside this milestone.

## Verdict: PASS_WITH_FOLLOWUP

There is no CRITICAL finding. The core property holds by design: no configuration file of any tier
can open gate 2 or carry the key (C5), the backend name never reaches `importlib`, and a closed gate
is inert and visible. One **HIGH** finding, FC-5 (key disclosure through an uncaught backend or
transport exception), and three MEDIUM findings (FC-3, FC-4, FC-10) are fully mitigated in design
once amendments A1 to A7 land. Task 03 may start; A2 and A3 to A7 must be folded into Tasks 03, 04
and 05 before those tasks merge, and A1 into Task 06.

Merge-gate conditions for the human reviewer and the merge-blocking hook. Any of the following in a
Story 01.0 change (or a later change touching `DS302`) is a **BLOCK** and must be kept out of
`master`:

- any configuration file, of any kind, or any `Config` attribute can make the gate's `requested`
  true;
- an environment value other than exactly `"1"` opens gate 2, or a non-`bool` keyword opens it on
  any path (`scan()` or a direct `detect()` call);
- the sentinel key, or any prefix of it, appears in any sink listed in M5, or the M5 sentinel test
  is missing or skipped;
- an exception raised during client construction or `check_claim` can reach the CLI, a log record
  or a traceback with its original message or exception chain (A5 not implemented);
- with the gate closed, `DS302` extracts claims, loads a backend, or `httpx` is imported;
- any `src/docsentinel/` module reads `LENZ_API_KEY`, or a module other than
  `detectors/fact_check.py` reads `DOCSENTINEL_USE_EXTERNAL_API` or a `DOCSENTINEL_FACTCHECK_*`
  variable;
- `load_backend` imports a module name that is not a value of the static map;
- the test suite can see a real `DOCSENTINEL_FACTCHECK_*` value or `DOCSENTINEL_USE_EXTERNAL_API`,
  or any test, fixture, commit or log contains the embedded key in
  examples/docs/lenz_fact-checking.md or sends a real request.

ADR 0007 may move to Accepted on this verdict once the owner signs off and A3, A5 and A6 are folded
into its Contracts 3, 4 and the S10 text.

## Addendum 2026-11-27: owner rulings after the first live run

The findings above are kept as written. These owner rulings change what they describe.

- **FC-8 and M8 (owner ruling of 2026-11-26).** The "never read the other tool's key" position is
  reversed. `detectors/fact_check.py::_read_api_key` reads `DOCSENTINEL_FACTCHECK_<NAME>_API_KEY` and,
  when that is unset or empty, the vendor's standard variable `<NAME>_API_KEY` (`LENZ_API_KEY` for `lenz`).
  The gate reason now reads `set DOCSENTINEL_FACTCHECK_LENZ_API_KEY or LENZ_API_KEY`. The M8 test
  (`tests/unit/test_fact_check_env_reads.py`) was adjusted with the code. **Residual risk:** a key exported for
  another Lenz tool now opens the key half of gate 2 without a separate step. The consent half
  (`--use-external-api` or `DOCSENTINEL_USE_EXTERNAL_API=1`) is unchanged, so no text is sent without it, and
  the key is still never a configuration key and never logged. FC-14's "nothing reads `LENZ_API_KEY`" no longer holds.
- **M10 and the "claim text is never logged" convention (owner ruling of 2026-11-27).** At INFO, `DS302`
  logs the first ten words of each selected claim and of each checked fact (`log.quote_start`, through
  `safe()`), so document content now reaches stderr and the log file. This is an explicit owner exception. Counts-only
  M10 line is unchanged. Reviewers should treat a CI log of a deep scan with the gate open as containing sentence
  fragments of the scanned documents.

## Addendum 2026-11-27: facts file and shared selection options (second pass)

The findings above are kept as written.

- **Gate unchanged.** `scan --include-facts FILE` and the shared selection options (`--min-salience`,
  `--max-per-document`, `--max-total`, `--weights`, `--dedup-threshold`, `--fact-combination all`) change
  what is selected or listed, not the consent: nothing is sent without `--use-external-api` (or
  `DOCSENTINEL_USE_EXTERNAL_API=1`) and the key, and a closed gate still reads one WARNING, `pending` and no
  evaluated count, with the reason `set DOCSENTINEL_FACTCHECK_LENZ_API_KEY or LENZ_API_KEY`.
- **FC-selection integrity.** The earlier "exploration only, never DS302" position is reversed by owner ruling C of
  2026-11-27 (see ADR 0007's amendment). The options are invoker-only flags (never configuration keys, never in
  user settings), so a scanned repository still cannot widen what is sent; a pre-commit `args:` or workflow that
  passes them is the invoker's own choice, under the same rules as `--use-external-api`.
- **Verbatim egress from a facts file.** The file is a trusted invoker path and `DS302` sends its `text` values as
  written, one request each, whether or not they appear in the scanned documents. Treat the file as the consent
  record: review it, keep it out of version control if it holds private text, and never accept a facts file from
  an untrusted source (a pull request that adds one is not a way to run it: the file is named only on the command
  line). Details: egress model, addendum of the same date.
