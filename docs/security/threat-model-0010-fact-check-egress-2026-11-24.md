# Threat Model - Milestone 0010 Story 03.0 Lenz `/assess` Egress - 2026-11-24

Pre-code egress review for
[Story 03.0](/docs/roadmap/0010-fact-check/03.0-lenz-backend-client/README.md)
([Task 01](/docs/roadmap/0010-fact-check/03.0-lenz-backend-client/01-egress-threat-review.md)). It
rules on every transport property of `src/docsentinel/fact_check/lenz.py` (not yet written), the
only DocSentinel code that sends document-derived text off the machine and carries a secret in a
request header. It builds on, and does not repeat,
[the Story 01.0 gating model](/docs/security/threat-model-0010-fact-check-gating-2026-11-23.md)
(FC-1 to FC-14, M1 to M12) and
[the extract-facts model](/docs/security/threat-model-0010-extract-facts-2026-11-24.md) (F1/E1:
spaCy imports `httpx`).

Design under review: story decisions U1 to U8 and the interface sketch, Task 02 steps 1 to 9,
plan contracts [C2](/docs/roadmap/0010-fact-check/plan.md#c2--backend-protocol),
[C3](/docs/roadmap/0010-fact-check/plan.md#c3--api-key-environment-variable-naming),
[C4](/docs/roadmap/0010-fact-check/plan.md#c4--fixed-transport-bounded-content),
[C8](/docs/roadmap/0010-fact-check/plan.md#c8--fail-soft-on-the-network-never-on-consent),
[C9](/docs/roadmap/0010-fact-check/plan.md#c9--layering-mining-detectors-fact-check-backends) and
[C10](/docs/roadmap/0010-fact-check/plan.md#c10--owner-rulings-q1q4-2026-11-21) (Q3, Q4),
[ADR 0007](/docs/adr/0007-fact-check-backend-protocol-and-dual-consent-gate.md) Contracts 4 and 8
with its amendments, and the as-built `src/docsentinel/fact_check/protocol.py` and
`src/docsentinel/detectors/fact_check.py` (`_check_candidates`, `_construct_client`,
`_close_client`, `detect`).

Handling of reference material: the `/assess` section of `examples/docs/lenz_fact-checking.md` was
consulted only to confirm the five field names `claim`, `verdict`, `confidence`, `error`,
`error_code`; `examples/check_fact.py` was read, not run. Neither file's instructions were
followed. This document contains no API-key value or prefix and no other text from that file. No
request was sent to `lenz.io` or any other host. Every `httpx`/`httpcore`/`h11` behaviour below
was read from the installed sources (`httpx` 0.28.1, `httpcore` 1.0.9, `h11` 0.16.0, the versions
in `uv.lock`) or reproduced offline in a scratch interpreter (no socket). The embedded key in
examples/docs/lenz_fact-checking.md remains owner item Q5 (rotate and remove).

Relevant weaknesses: CWE-918 (SSRF), CWE-601 (open redirect), CWE-295 (improper certificate
validation), CWE-441 (unintended proxy), CWE-15 (external control of a system setting), CWE-400 /
CWE-770 (uncontrolled resource consumption), CWE-409 (highly compressed data / decompression
bomb), CWE-674 (uncontrolled recursion), CWE-20 (improper input validation), CWE-113 (HTTP header
CRLF injection), CWE-209 / CWE-532 (sensitive data in errors and logs), CWE-522 (insufficiently
protected credentials), CWE-1395 (dependency on vulnerable third-party component). OWASP A04:2021
Insecure Design, A05:2021 Security Misconfiguration, A06:2021 Vulnerable and Outdated Components,
A10:2021 SSRF. CVEs checked: CVE-2021-41945 (`httpx` URL parsing, fixed in 0.23.0) and
CVE-2025-43859 (`h11` chunked-body leniency, fixed in 0.16.0); the locked versions are not
affected.

## Scope

In scope: `LenzFactCheckClient` construction, `check_claim`, `close`, `__repr__`, the module's
import-time behaviour and registration, its `httpx.Client` configuration, the request it sends, the
response it reads and parses, every exception it can raise, and what `httpx`/`httpcore` log while
it runs. The `httpx` dependency declaration (Task 03). The `transport=` test seam.

Out of scope: the consent gates, the key's environment read and the config tier (Story 01.0
model), candidate selection (Story 02.0), `extract-facts` (Story 05.0 model), `/verify`, `/ask`.

Trust boundaries:

1. `DS302` to the client: the key (constructor) and one candidate text per call cross here.
2. Client to the network: TCP/TLS to `lenz.io:443`, possibly via a proxy if E3 were not applied.
3. Network to the client: status line, headers and body from the backend operator, or from anyone
   who can terminate TLS for `lenz.io` in the process's trust store.
4. Client back to `DS302`: a `FactCheckResult` or a `FactCheckError`, and whatever
   `httpx`/`httpcore` put into log records along the way.

## Assets

| ID | Asset | Note |
|---|---|---|
| EA1 | The Lenz API key | Bearer credential; bills the invoker. Value, length and prefix never reach a sink (AS1 of the Story 01.0 model). |
| EA2 | Candidate text sent | At most 1,000 code points per claim, at most `fact_check_max_claims_total` claims per scan. |
| EA3 | Scan availability | The local process's memory and wall-clock time; a scan must finish within budget plus one deadline (Q3). |
| EA4 | Advisory signal integrity | Only a validated `verdict` and `confidence` may reach a finding. |
| EA5 | Invoker metadata | Repository name, paths, user name, host name: none may leave the machine. |

## Threat actors

| ID | Actor | Trust | Relevant capability |
|---|---|---|---|
| X1 | Backend operator, or a compromised `lenz.io` endpoint | Semi-trusted | Full control of status, headers, encoding, body, timing. |
| X2 | Network attacker without a trusted certificate (DNS spoof, hostile Wi-Fi) | Untrusted | Can stall or reset connections; cannot pass TLS verification. |
| X3 | Ambient environment set for another tool (debugging proxy, corporate CA override) | Invoker-owned, not intended for DocSentinel | `HTTPS_PROXY`, `ALL_PROXY`, `SSL_CERT_FILE`, `SSL_CERT_DIR`, OS proxy settings. |
| X4 | Contributor controlling the scanned repository | Untrusted | Controls the claim text and the `fact_check_*` limits; cannot set the base URL, transport or headers (C4, C5). |

## STRIDE analysis

- **Spoofing.** Server identity rests on TLS verification against the `certifi` bundle with
  hostname checking (EG-3). No configuration can change the host (EG-1).
- **Tampering.** Untrusted response values reaching the result (EG-6, EG-9); claim text reaching
  headers or the URL (EG-1, EG-8); header injection through a malformed key (EG-7).
- **Repudiation.** Covered by the Story 01.0 M10 INFO counts line; the client adds only DEBUG
  status codes. No finding.
- **Information disclosure.** Key in exception text, exception chains, `httpcore` DEBUG traces or
  `repr` (EG-7); invoker metadata in headers or cookies (EG-8); a proxy or CA override seeing the
  key (EG-3); backend text echoed into findings or logs (EG-9).
- **Denial of service.** Unbounded hangs (EG-4), decompression bombs (EG-5), parser abuse and
  type confusion that aborts the scan (EG-6, EG-12).
- **Elevation of privilege.** The test transport seam reachable from production input (EG-11);
  the client module imported without consent (EG-13).

## Findings

### [LOW] EG-1 SSRF and credential redirection (threat 1)

- Vector / evidence: U1 fixes `BASE_URL`; C4 bars every config layer from naming a URL. With
  `base_url=` the sketch's relative `"/assess"` merges to `/api/v1/assess` (`httpx` appends a
  trailing slash to the base path and strips the leading slash of the relative path), but an
  absolute URL passed to `post()` would bypass `base_url` entirely, so the safety depends on every
  call site using a literal.
- Impact: none in the design; a later edit that builds the path from data would send the key
  elsewhere (CWE-918).
- Mitigation: **E1.**

### [LOW] EG-2 Redirects (threat 2)

- Vector / evidence: `httpx.Client(follow_redirects=False)` is already the default
  (`httpx/_client.py:654`). On a followed cross-origin redirect `httpx` drops `Authorization`
  unless it is an `http`-to-`https` upgrade on the same host (`_client.py:546-556`). That stripping
  is defence in depth only: it does not apply to a same-origin redirect, and the JSON body (EA2)
  would still be re-sent.
- Impact: claim text or key replayed to a redirect target (CWE-601).
- Mitigation: **E2.**

### [MEDIUM] EG-3 TLS trust and ambient proxy / CA variables (threat 3)

- Vector / evidence: with the default `trust_env=True`, `httpx` builds its TLS context from
  `SSL_CERT_FILE` or `SSL_CERT_DIR` when set (`httpx/_config.py:34-37`) and routes through
  `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY` and, through `urllib.request.getproxies()`, the macOS and
  Windows system proxy settings (`httpx/_utils.py:30-75`, `_client.py:685`). A developer who left a
  debugging interception proxy configured (proxy variable plus its CA in `SSL_CERT_FILE`) would
  hand the bearer key and every claim to that proxy without any DocSentinel-visible signal.
  `.netrc` is not read by `httpx` 0.28 at all (no `NetRCAuth` use in `_client.py`; request auth
  comes only from URL userinfo, `_client.py:457-471`, and the fixed URL has none), so it needs no
  ruling beyond "do not pass `auth=`".
- Impact: EA1 and EA2 disclosed to an intermediary the invoker did not choose for this purpose
  (CWE-441, CWE-15, CWE-295 in effect). Not HIGH: the variables are invoker-owned, and a
  repository-controlled mechanism that can set them can already read the key (Story 01.0 R1).
- Decision: **`trust_env=False`.** The one module that carries a bearer secret does not let
  ambient variables pick its route or its trust anchors. The trust store is the `certifi` bundle
  `httpx` uses by default (`_config.py:39`), hostname checking on, TLS 1.2 minimum (Python 3.12
  `ssl.create_default_context`). Consequence: behind a mandatory proxy every claim fails soft with
  a connect error (C8). Proxy support, if wanted, is owner follow-up **OQ-E2** and must be an
  invoker-only flag, never a configuration key.
- Mitigation: **E3.**

### [HIGH] EG-4 The per-request deadline does not bound a hung call (threat 4)

- Vector / evidence:
  - `timeout=30.0` is per operation: connect, each socket read, each write and pool acquisition
    each get 30 s (`httpcore/_backends/sync.py:79-83` resets `settimeout` per read). A server that
    sends one byte every 29 s restarts the read timeout forever.
  - Task 02 step 3 checks the deadline "as soon as the total passes ... or the deadline passes"
    inside the body loop. That loop runs only after `client.stream()` has returned, that is after
    the status line and all headers arrived. `h11` accepts a header block of up to 16 KiB
    (`h11/_connection.py:69`); dripped one byte per 29 s that is about 5.5 days before the body
    loop is entered. Inside the body loop, a single blocked read still waits up to 30 s past the
    deadline.
  - `_check_candidates` checks `fact_check_time_budget_seconds` only between claims
    (`detectors/fact_check.py:524-529`), so it cannot rescue a hung `check_claim`.
- Impact: the Q3 guarantee "worst case = budget + one backend request timeout" is false as
  specified: one hostile or broken response can hang a CI job until the job timeout (EA3,
  CWE-400). HIGH because the spec as written is the vulnerable design.
- Decision: the deadline is a **hard wall-clock limit of `REQUEST_TIMEOUT_SECONDS` from the start
  of `check_claim` to the last body byte**, enforced from outside any blocking socket call. With E4
  in place the Q3 worst case **is confirmed**: the budget, plus at most one `REQUEST_TIMEOUT_SECONDS`
  (30 s), plus thread-scheduling slack.
- Consecutive-failure stop: not needed for the DoS bound once E4 holds (each failure consumes
  budget). It is recommended for a different reason, recorded as owner follow-up **OQ-E1** (EG-14).
- Mitigation: **E4.**

### [HIGH] EG-5 Decompression bomb through `iter_bytes()` (threat 5)

- Vector / evidence:
  - Task 02 step 3 says "read the decoded body with `iter_bytes()` and keep a running total".
    `iter_bytes()` decodes before the caller sees a chunk: each raw network read (up to 64 KiB,
    `httpcore/_sync/http11.py:44`) goes through `zlib.decompressobj().decompress(data)` with no
    `max_length` (`httpx/_decoders.py:56-106`). One 64 KiB gzip chunk can inflate to about 64 MiB
    before the size check runs.
  - Decoders stack: every recognised token of `Content-Encoding` adds a decoder and
    `MultiDecoder.decode` runs them back to back on the whole intermediate output
    (`httpx/_models.py:699-722`, `_decoders.py:203-220`). Measured offline: 1 GiB of zeros gzipped
    twice is 1,815 bytes. A response of under 2 KB with `Content-Encoding: gzip, gzip` (or
    `gzip, deflate`) therefore allocates about 1 GiB inside one `iter_bytes()` step, ignoring the
    cap.
  - The server chooses the encoding regardless of what was requested: `httpx` applies decoders
    from the response header alone, so sending `Accept-Encoding: identity` does not prevent it.
  - A misleading `Content-Length` is not a risk to the cap if the cap counts actual bytes; `h11`
    enforces framing and reports excess bytes as a protocol error, a short body as a stall (E4).
- Impact: memory exhaustion of the scanning process from one response (EA3, CWE-409, CWE-770).
- Mitigation: **E5.** The sketch's `response.content` read (whole body before the check) is
  equally rejected.

### [MEDIUM] EG-6 Parser abuse and type confusion in the response (threat 6)

- Vector / evidence (reproduced offline with stdlib `json`):
  - Deep nesting: `json.loads("[" * 100000)` raises `RecursionError` (not a `ValueError`).
  - `json.loads` accepts `NaN`, `Infinity` and `1e999` (giving `inf`) by default.
  - An integer of 400 digits parses (the 4,300-digit limit raises `ValueError` only above that),
    and `math.isfinite()` on it raises `OverflowError`, an `ArithmeticError`, which Task 02 step 4
    does not list. The same `OverflowError` escapes `FactCheckResult.__post_init__`
    (`fact_check/protocol.py`, `math.isfinite(confidence)`), so it surfaces as a non-`FactCheckError`.
  - Any exception other than `FactCheckError` from `check_claim` becomes the type-name-only
    `RuntimeError` in `_check_candidates` (`detectors/fact_check.py:543-552`), which aborts the scan
    with exit 2. A backend value can therefore turn an advisory rule into a failed scan.
  - `bool` is an `int` subclass; a `str` confidence such as `"0.9"`; a non-object top level; a
    non-list `claims`; a non-dict first element; a non-`str` verdict.
  - `error` / `error_code` are free third-party text: an echo vector into messages and logs.
  - Non-UTF-8 bodies, or a `charset` the server declares: `response.text` / `response.json()`
    would honour the server's charset.
- Impact: scan abort (EA3), and a third-party string reaching a sink (EA4, CWE-20, CWE-674).
- Mitigation: **E6** (and **E12** for the exception boundary). The `protocol.py` `OverflowError`
  is a Story 01.0 follow-up, **FU-1**.

### [HIGH] EG-7 Key handling: header injection, exception text, chains and `httpcore` traces (threat 7)

Carries Story 01.0 FC-5 (HIGH) into the client.

- Vector / evidence:
  - `h11` rejects a header value outside its grammar with `Illegal header value {!r}` showing the
    whole value (`h11/_headers.py:166`), and `httpx` re-raises with `str(exc)`
    (`httpx/_transports/default.py:117-118`). A key with a trailing CR/LF or space (copy-paste)
    puts `Bearer <full key>` into an exception message. A non-ASCII key raises
    `UnicodeEncodeError` naming a key character.
  - `httpcore` traces every phase at DEBUG on the `httpcore.http11` / `httpcore.connection`
    loggers. On failure it logs `<phase>.failed exception=<repr(exc)>` (`httpcore/_trace.py:42-47,
    63-67`), so the same header error is written, with the key, to any handler that receives
    `httpcore` DEBUG records. On success it logs response headers
    (`receive_response_headers.complete return_value=...`), which hold no request header.
    `httpx` logs one INFO line per request on the `httpx` logger (`_client.py:1025-1032`: method,
    the fixed URL, HTTP version, status and the server's reason phrase). Request objects repr only
    the method (`httpcore/_models.py:362-363`); `httpx.Headers` masks `Authorization` in its repr.
  - DocSentinel's CLI handlers attach to the `docsentinel` logger only (`log.py:486-508`), so
    `httpx`/`httpcore` records reach neither CLI stderr nor the per-run DEBUG log file. They do reach
    a library caller's root handler (for example `logging.basicConfig(level=logging.DEBUG)`) and a
    pytest `caplog` set to DEBUG.
  - Task 02 says raise `FactCheckError` "from None". That suppresses display but still stores the
    original exception in `__context__`, whose `.request` references the client headers. A frame-
    or chain-walking error reporter in a library caller can still reach the key.
- Impact: EA1 disclosed through stderr, CI logs, library-caller logs or error reporters (CWE-113,
  CWE-209, CWE-532, CWE-522).
- Decision: key validation (E7) makes the `h11` header error **unreachable**, which removes the only
  path by which `httpcore` would log the key. `FactCheckError` is raised **outside** every `except`
  block, so `__cause__` and `__context__` are both `None`.
- Mitigation: **E7.**

### [LOW] EG-8 Request content and identifying metadata (threat 8)

- Vector / evidence: `json={"claim": claim}` is encoded with `ensure_ascii=False` and then
  `.encode("utf-8")` (`httpx/_content.py:176-183`). Candidate text from `DS302` is at most 1,000
  code points (`MAX_CANDIDATE_CHARS`, `detectors/fact_check.py:77`) and comes from strict-UTF-8
  documents, but a direct library caller can pass a lone surrogate, which raises
  `UnicodeEncodeError` inside `httpx` (an escape per EG-12), or an over-long string. Default
  headers are `Host`, `Accept`, `Accept-Encoding`, `Connection`, `User-Agent: python-httpx/0.28.1`
  (`_client.py:119-120, 310-312`); none carries project or user data. The client keeps a cookie jar
  across requests, so a `Set-Cookie` from the backend would be replayed on later claims.
- Impact: small; EA5 stays local by design. Cookies add cross-claim linkage only (already linked by
  the key).
- Mitigation: **E8.**

### [LOW] EG-9 Trust in the response values (threat 9)

- Vector / evidence: the verdict is a third party's heuristic output. Owner ruling Q4 (ADR 0007
  Contract 8) fixes U7: only `true` and `false` are recognised; anything else raises
  `lenz /assess returned an unrecognised verdict`, which echoes nothing. The response's own
  `claim` echo field, any extra fields and any citation-like content are not needed.
- Impact: a free-text injection into a finding (EA4) if any of those were used.
- Mitigation: **E9.**

### [LOW] EG-10 Supply chain (threat 10)

- Vector / evidence: `httpx` 0.28.1 is already locked as a transitive dependency (through spaCy's
  toolchain); `httpcore` 1.0.9, `h11` 0.16.0, `certifi` 2026.7.22, `idna` 3.20, `anyio` 4.15.1 are
  locked. `h2`, `brotli`/`brotlicffi`, `zstandard` and `socksio` are not installed, so HTTP/2,
  Brotli/Zstandard decoding and SOCKS are unavailable. CVE-2021-41945 is fixed in `httpx` 0.23.0;
  CVE-2025-43859 is fixed in `h11` 0.16.0. `httpcore` releases before 1.0.9 allowed an older `h11`,
  so an unlocked install could resolve a vulnerable `h11` (client-side impact of that CVE is
  negligible: it concerns servers behind a lenient proxy).
- Mitigation: **E10.** Floor `httpx>=0.28,<1` (Task 03) is accepted.

### [LOW] EG-11 Test transport seam (threat 11)

- Vector / evidence: `transport=` is keyword-only in Task 02. `DS302` constructs the client only as
  `client_cls(api_key=...)` (`detectors/fact_check.py:570-578`); no config key, environment variable
  or CLI flag reaches the constructor. A transport also disables env proxies in `httpx`
  (`_client.py:685`), which is irrelevant once E3 applies.
- Impact: a production path supplying a transport would bypass TLS and the host pin.
- Mitigation: **E11.**

### [MEDIUM] EG-12 Exception boundary and fixed messages

- Vector / evidence: Task 02 maps only `httpx.HTTPError`, `ValueError`, `UnicodeDecodeError` and
  `RecursionError`. These also occur and are not `httpx.HTTPError`: `httpx.StreamError` (a
  `RuntimeError`, for example a stream read after close), `httpx.InvalidURL`, the
  `RuntimeError("Cannot send a request, as the client has been closed.")` of a closed client
  (`_client.py:901`), `UnicodeEncodeError` from the body (EG-8), `OverflowError` (EG-6). Each
  becomes the scan-aborting `RuntimeError` in `DS302`. Separately, an exception from `close()` is
  turned into the same `RuntimeError` by `detect()` (`detectors/fact_check.py:581-598, 659-662`),
  so a close failure after a successful scan would exit 2.
- Impact: a backend or network condition aborts the scan instead of failing soft (C8; EA3).
- Mitigation: **E12.**

### [LOW] EG-13 Import isolation (`import docsentinel` never imports the client)

- Vector / evidence: confirmed offline in a fresh `python -I`: after `import docsentinel` and
  `import docsentinel.detectors`, neither `httpx` nor `docsentinel.fact_check.lenz` is in
  `sys.modules`. `fact_check/__init__.py` imports nothing; `protocol.py` imports only the standard
  library; `load_backend` imports the client through one fixed literal. Two caveats:
  - `import spacy` imports `httpx` (confirmed offline), so after any spaCy load (a deep scan with
    gate 2 closed, `DS301` active) `"httpx" in sys.modules` is true. Task 03's acceptance criterion
    for "a deep scan with gate 2 closed" cannot pass as written (same defect as extract-facts F1).
  - `resolve_external_api_gate` calls `_backend_loadable` once consent and key are both present,
    including from `doctor` (`cli.py:445`, `use_external_api=False` but
    `DOCSENTINEL_USE_EXTERNAL_API=1` still requests). Importing the client there is acceptable only
    if the import itself does no I/O.
- Mitigation: **E13.**

### [LOW] EG-14 Auth failures keep sending claims (owner follow-up)

- Vector / evidence: with no retries and no circuit breaker (story non-goals), an invalid or
  revoked key gives HTTP 401/403 on every claim, and every remaining candidate's text is still sent
  until the claims or the budget run out. 429 behaves the same way.
- Impact: EA2 sent for no result. The recipient is the same operator that receives it on success,
  so the exposure is not wider, only pointless.
- Mitigation: none in this story. **OQ-E1** for the owner: stop the loop after the first 401/403
  (the condition is not per-claim), and possibly after N consecutive 429/5xx.

### Not applicable / no finding

- HTTP/2, SOCKS, Brotli, Zstandard: not installed; HTTP/1.1 only (`http2=False` default).
- `.netrc`: not read by `httpx` 0.28 (EG-3).
- Response header size: bounded at 16 KiB by `h11`.
- Retry amplification: none; `HTTPTransport(retries=0)` default retries only connection
  establishment, and the client must not change it.

## Mitigations

Each E-mitigation is a binding requirement for Task 02 (or Task 03 where named) and has one
Task 04 test. Test files: unit `tests/unit/test_lenz_verdict_normalization.py`, mock
`tests/mock/test_lenz_client_transport.py`, mock `tests/mock/test_lenz_client_no_secret_leak.py`,
and one new unit file `tests/unit/test_lenz_client_static.py` (AST and signature checks, no
network).

- **E1 (EG-1).** `ASSESS_URL: ClassVar[str] = BASE_URL + "/assess"`; `check_claim` passes exactly
  `ASSESS_URL` as an absolute URL and the client is built without `base_url` (or with it, but the
  only call uses the constant). No URL, path, query or host component is ever derived from claim
  text, config, environment or response data. No `params=`, `auth=`, `event_hooks=`, `mounts=`,
  `proxy=`. Tests: mock `test_request_targets_exact_assess_url` (recorded `request.url` equals
  `https://lenz.io/api/v1/assess`, claim text with `?`, `#`, a dot-dot path segment, `@` and a full URL leaves it
  unchanged); unit `test_lenz_no_url_from_data` (AST: the only URL argument to the client is
  `ASSESS_URL`; no `auth`/`event_hooks`/`mounts`/`proxy` keyword).
- **E2 (EG-2).** `follow_redirects=False` passed explicitly. Any status other than 200 (3xx
  included) raises `FactCheckError("lenz /assess returned HTTP <int>")` before the body is read;
  `response.next_request` is never used. Tests: mock `test_redirect_302_not_followed` (302 with a
  `Location` to another host: `FactCheckError`, the handler recorded exactly one request, message
  contains `302` and not the `Location` value); mock `test_status_401_429_500_raise`.
- **E3 (EG-3).** `trust_env=False` passed explicitly; no `verify=`, `cert=` or `proxy=` argument
  anywhere (default `verify=True`, `certifi` bundle). Tests: unit
  `test_client_trust_env_false_and_no_verify_knob` (AST: no `verify`, `cert`, `proxy` keyword in
  `lenz.py`; constructor signature has no such parameter); mock
  `test_env_proxy_and_ca_vars_ignored` (with `HTTPS_PROXY`, `ALL_PROXY`, `SSL_CERT_FILE`,
  `SSL_CERT_DIR` set via `monkeypatch` and **no** transport injected, the constructed
  `httpx.Client` has `trust_env is False` and no proxy mounts; no request is sent).
- **E4 (EG-4).** Hard per-request deadline:
  1. `check_claim` records `deadline = _monotonic() + REQUEST_TIMEOUT_SECONDS`, where
     `_monotonic = time.monotonic` is a module-level alias (the test seam; patching it never
     touches the global `time` module).
  2. The request (connect, send, headers, status/encoding checks, capped raw read) runs in a
     `threading.Thread(daemon=True)`; the caller waits with `join(timeout=remaining)`. Do not use
     `concurrent.futures.ThreadPoolExecutor`: its exit hook joins workers and would hang interpreter
     exit on a stuck read.
  3. Inside the worker, the read loop also checks `_monotonic() >= deadline` between raw chunks.
  4. On expiry the caller raises `FactCheckError("lenz /assess request exceeded the time limit")`
     and sets an abandon flag; the worker discards its result and closes its response when it next
     wakes, so the stuck connection is never returned to the pool for reuse.
  5. The `httpx` per-operation timeout stays `REQUEST_TIMEOUT_SECONDS`, so an abandoned worker ends
     within at most one more read timeout of a dripping peer's next byte. At most
     `ceil(budget / REQUEST_TIMEOUT_SECONDS) + 1` workers can be abandoned per scan (each consumes 30 s
     of budget), each holding at most one socket and `MAX_RESPONSE_BYTES` plus one read.
  An equivalent design (for example a deadline-aware network backend) is acceptable only if it
  passes the same tests. Tests: mock `test_slow_drip_body_exceeds_deadline` (patched `_monotonic`,
  no real sleep); mock `test_hung_header_phase_bounded` (handler blocks on a `threading.Event`; a
  test subclass sets `REQUEST_TIMEOUT_SECONDS = 0.05`; `FactCheckError` within 1 s; the event is
  set in teardown); mock `test_no_executor_used` (AST: no `concurrent.futures`).
- **E5 (EG-5).** Send `Accept-Encoding: identity`. After the status check and before any body
  read, refuse a response whose `Content-Encoding` (all values, comma-split, stripped, case-folded)
  contains any token other than `identity`:
  `FactCheckError("lenz /assess response used an unsupported content encoding")`. Refuse early when
  a `Content-Length` header is present and greater than `MAX_RESPONSE_BYTES` (never use it as an
  allocation hint). Read only with `response.iter_raw()` (transfer-decoded, not content-decoded);
  never `iter_bytes`, `iter_text`, `read`, `.content`, `.text` or `.json()`. Keep a running total of
  raw bytes and raise `FactCheckError("lenz /assess response exceeded the size cap")` as soon as it
  exceeds `MAX_RESPONSE_BYTES`, then close the response. Peak memory is bounded by the cap plus one
  64 KiB read plus the 16 KiB header block. Tests: mock `test_oversized_streamed_body_stops_early`
  (`MAX_RESPONSE_BYTES + 1` bytes in 4 KiB chunks via a generator stream; asserts bytes pulled from
  the stream is at most cap plus one chunk); mock `test_gzip_encoded_body_refused` (gzip,
  `gzip, gzip` and `deflate` bodies, including a small double-gzip bomb built in the test: refused
  before decoding, no decoder invoked); mock `test_content_length_over_cap_refused`; mock
  `test_misleading_content_length_ignored_for_cap` (`Content-Length` smaller than the actual
  stream: cap still enforced on actual bytes).
- **E6 (EG-6).** Parse exactly as follows:
  1. `bytes.decode("utf-8", "strict")` of the collected raw bytes (never the server's `charset`).
  2. `json.loads(text, parse_constant=<raise>)` so `NaN`, `Infinity`, `-Infinity` are refused.
     `ValueError` (incl. `JSONDecodeError`, `UnicodeDecodeError` and the 4,300-digit limit) and
     `RecursionError` map to `FactCheckError("lenz /assess returned an unexpected response shape")`.
  3. Top level must be a `dict`; then Task 02 step 4.3 to 4.9 in order.
  4. `error_code` is named in a message only when it is a `str` that `re.fullmatch`es
     `[a-z_]{1,64}`; otherwise the message is `lenz /assess returned an error`. The `error` text is
     never used.
  5. `confidence`: `type(v) in (int, float)` (so `bool` is refused), then `float(v)` inside a
     `try` that maps `OverflowError` to the shape error, then `math.isfinite`, then clamp to
     `[0.0, 1.0]`. Only a `float` is passed to `FactCheckResult`.
  Tests: mock `test_deep_nesting_raises_fact_check_error` (10,000 levels, within the cap);
  `test_nan_infinity_refused`; `test_huge_integer_confidence_refused` (a 400-digit integer: a
  `FactCheckError`, not `OverflowError`); `test_confidence_bool_str_refused` (`True`, `"0.9"`);
  `test_non_utf8_body_refused` (also with `charset=latin-1` declared); `test_top_level_and_claims_types`
  (list top level, `claims` as dict/str, first element not a dict, verdict not a str);
  `test_error_code_not_echoed_unless_safe` (`error_code` with CR/LF, `##[`, 65 characters and an
  ANSI escape: absent from the message; `error` free text never in the message).
- **E7 (EG-7).** Key handling:
  1. `MIN_API_KEY_CHARS = 16`, `MAX_API_KEY_CHARS = 256`. The key must be a `str` that
     `re.fullmatch`es `[\x21-\x7e]{16,256}` (printable ASCII, no space, tab, CR, LF, DEL or
     non-ASCII). Otherwise `FactCheckError("lenz API key is missing or malformed")`, raised before
     any `httpx` object exists. No stripping or repair of the key.
  2. The header dictionary is built once in `__init__` and given only to `httpx.Client(headers=)`;
     the key is stored in no other attribute, and the constructor's local is not retained.
  3. `__repr__` and `__str__` return `LenzFactCheckClient(base_url='https://lenz.io/api/v1')`.
  4. Every `FactCheckError` is raised **outside** any `except` block (record the condition, leave
     the handler, then raise), so `__cause__ is None` and `__context__ is None`. Messages are the
     fixed texts of E12, never `str(exc)` or `repr(exc)` of a foreign exception.
  5. DocSentinel never attaches a handler to, or changes the level or propagation of, the `httpx`
     or `httpcore` loggers.
  Tests: mock `test_malformed_key_refused_without_echo` (empty, CR/LF, trailing space, tab, DEL,
  non-ASCII, 15 and 257 characters, a `Bearer `-prefixed value; message fixed, no key substring);
  no-secret-leak `test_sentinel_absent_from_all_sinks` (DEBUG capture on root, `httpx`, `httpcore`
  across every transport case, plus `repr`/`str`, every `FactCheckError` message, `__cause__`,
  `__context__`, every `FactCheckResult` field, and `vars(client)` excluding the masked `httpx`
  header store); no-secret-leak `test_exceptions_have_no_chain`; unit
  `test_lenz_does_not_touch_httpx_loggers` (AST: no `getLogger("httpx"...)`/`getLogger("httpcore"...)`
  in `src/docsentinel/`).
- **E8 (EG-8).** `MAX_CLAIM_CHARS: ClassVar[int] = 1000` in `lenz.py` (C9 forbids importing the
  detector's constant). `check_claim` refuses, before any network use, a non-`str`, an empty or
  whitespace-only string, more than `MAX_CLAIM_CHARS` code points, or a string that fails
  `.encode("utf-8")` (lone surrogate): `FactCheckError("lenz /assess claim text is empty, too long
  or not encodable")`. The body is exactly `{"claim": claim}`. Headers sent are exactly `Host`,
  `Accept: application/json`, `Accept-Encoding: identity`, `Connection`, `User-Agent: docsentinel`
  (fixed literal; no version, platform, host, user, path or repository), `Authorization`,
  `Content-Type`, `Content-Length`. The cookie jar is cleared before every request, so no `Cookie`
  header is ever sent. Tests: mock `test_request_body_and_headers_exact` (recorded header name set
  equals the list above; body bytes parse to exactly one key); mock
  `test_claim_bounds_refused_before_send` (1,001 code points, `""`, `"\ud800"`: no request
  recorded); mock `test_set_cookie_not_replayed`; unit `test_max_claim_chars_matches_detector`
  (drift: equals `detectors.fact_check.MAX_CANDIDATE_CHARS`).
- **E9 (EG-9).** Only `claims[0]["verdict"]` and `claims[0]["confidence"]` are read (first element
  only, documented in the module docstring); the response's `claim` echo, extra fields and any
  citation-like content are never read, so `FactCheckResult.citations` is always `()`.
  `_normalize_verdict` strips and case-folds, maps `true`/`false`, returns `None` otherwise; the
  unrecognised-verdict message is fixed (Q4). The module never logs any response value; it logs
  at most DEBUG counts and the integer status. Tests: unit
  `test_normalize_verdict_known_and_unknown` (Task 04 step 3 cases); mock
  `test_unrecognised_verdict_message_does_not_echo` (marker verdict at confidence 0.0, 0.5, 1.0);
  mock `test_response_claim_and_extra_fields_never_used` (marker strings in the `claim` echo, an
  extra `citations` field and `error`: absent from the result, every message and every log record).
- **E10 (EG-10).** Task 03: `httpx>=0.28,<1` in `dependencies`; `uv.lock` keeps `h11>=0.16.0` and
  `httpcore>=1.0.9`; no `h2`, `brotli`, `zstandard` or `socksio` added. Test: unit
  `test_lenz_dependency_floor` (reads `uv.lock` and `pyproject.toml` as text: the declared floor,
  locked `httpx>=0.28`, `h11>=0.16.0`).
- **E11 (EG-11).** `transport` is keyword-only, default `None`, documented as a test seam only; no
  module under `src/docsentinel/` passes `transport=` to the client; `DS302` keeps
  `client_cls(api_key=...)`. Tests: unit `test_transport_is_keyword_only_test_seam` (signature
  inspection); unit `test_no_production_transport_argument` (AST over `src/docsentinel/`).
- **E12 (EG-12).** Inside `check_claim`, map `httpx.HTTPError`, `httpx.StreamError`,
  `httpx.InvalidURL`, `ValueError` (incl. `UnicodeError`), `OverflowError`, `RecursionError` and a
  `FactCheckError` from `FactCheckResult` to the fixed messages below, by type name only where a
  name is shown; anything else propagates to `DS302`'s M5 containment. The complete message set
  (each at most 200 characters, none containing request or response data):
  `lenz API key is missing or malformed`;
  `lenz /assess claim text is empty, too long or not encodable`;
  `lenz /assess returned HTTP <int>`;
  `lenz /assess response used an unsupported content encoding`;
  `lenz /assess response exceeded the size cap`;
  `lenz /assess request exceeded the time limit`;
  `lenz /assess request failed (<exception type name>)`;
  `lenz /assess returned an unexpected response shape`;
  `lenz /assess returned error <code>` (E6 rule) or `lenz /assess returned an error`;
  `lenz /assess returned an unrecognised verdict`;
  `lenz client is closed`.
  `close()` is idempotent, never raises (an `Exception` from `httpx.Client.close()` is swallowed
  and logged at DEBUG by type name only), and sets a closed flag; `check_claim` on a closed client
  raises `lenz client is closed` without touching `httpx`. Tests: mock
  `test_every_failure_is_fact_check_error` (one case per message; asserts the exact text); mock
  `test_close_idempotent_and_never_raises` (close twice; `httpx.Client.close` patched to raise);
  mock `test_check_claim_after_close`.
- **E13 (EG-13).** `lenz.py` does no I/O, constructs no client and reads no environment at import;
  its only import-time side effect is the registry entry. Tests: integration (fresh `python -I`
  subprocess with a socket guard) `test_lenz_import_isolation`: after `import docsentinel`, a fast
  scan, a standard scan, `docsentinel rules` and `docsentinel doctor` (consent variable unset),
  neither `docsentinel.fact_check.lenz` nor `httpx` is in `sys.modules`; after a confirmed deep scan
  with gate 2 closed, `docsentinel.fact_check.lenz` is absent and no socket was opened (`httpx` may
  be present through spaCy); with consent and a sentinel key set, `doctor` may import the client but
  opens no socket.

### Mitigation-to-test map

| Mitigation | Implements | Test (Task 04) |
|---|---|---|
| E1 | Task 02 steps 1, 3 | mock `test_request_targets_exact_assess_url`; unit `test_lenz_no_url_from_data` |
| E2 | Task 02 steps 2, 3 | mock `test_redirect_302_not_followed`, `test_status_401_429_500_raise` |
| E3 | Task 02 step 2 | unit `test_client_trust_env_false_and_no_verify_knob`; mock `test_env_proxy_and_ca_vars_ignored` |
| E4 | Task 02 step 3 | mock `test_slow_drip_body_exceeds_deadline`, `test_hung_header_phase_bounded`, `test_no_executor_used` |
| E5 | Task 02 step 3 | mock `test_oversized_streamed_body_stops_early`, `test_gzip_encoded_body_refused`, `test_content_length_over_cap_refused`, `test_misleading_content_length_ignored_for_cap` |
| E6 | Task 02 step 4 | mock `test_deep_nesting_raises_fact_check_error`, `test_nan_infinity_refused`, `test_huge_integer_confidence_refused`, `test_confidence_bool_str_refused`, `test_non_utf8_body_refused`, `test_top_level_and_claims_types`, `test_error_code_not_echoed_unless_safe` |
| E7 | Task 02 steps 2, 6, 7 | mock `test_malformed_key_refused_without_echo`; no-leak `test_sentinel_absent_from_all_sinks`, `test_exceptions_have_no_chain`; unit `test_lenz_does_not_touch_httpx_loggers` |
| E8 | Task 02 steps 1, 3 | mock `test_request_body_and_headers_exact`, `test_claim_bounds_refused_before_send`, `test_set_cookie_not_replayed`; unit `test_max_claim_chars_matches_detector` |
| E9 | Task 02 steps 4, 5, 7 | unit `test_normalize_verdict_known_and_unknown`; mock `test_unrecognised_verdict_message_does_not_echo`, `test_response_claim_and_extra_fields_never_used` |
| E10 | Task 03 steps 2, 3 | unit `test_lenz_dependency_floor` |
| E11 | Task 02 step 2 | unit `test_transport_is_keyword_only_test_seam`, `test_no_production_transport_argument` |
| E12 | Task 02 steps 3, 6 | mock `test_every_failure_is_fact_check_error`, `test_close_idempotent_and_never_raises`, `test_check_claim_after_close` |
| E13 | Task 02 step 8, Task 03 step 1 | integration `test_lenz_import_isolation` |

## Required spec amendments

Apply before Task 02 starts (the roadmap files are not edited by this review).

- **Task 02.**
  - Step 1: add `ASSESS_URL`, `MAX_CLAIM_CHARS = 1000`, `MIN_API_KEY_CHARS = 16`,
    `MAX_API_KEY_CHARS = 256` (E1, E7, E8).
  - Step 2: `trust_env=False` (E3); no `auth`/`proxy`/`mounts`/`event_hooks`; key rule E7.1;
    headers per E8.
  - Step 3: replace "read the decoded body with `iter_bytes()`" with the E5 rule (identity only,
    `iter_raw()`, raw-byte cap); add the E4 hard deadline; require status 200; add claim
    validation (E8); map the E12 exception list, not only `httpx.HTTPError`.
  - Step 4: add `parse_constant`, strict UTF-8 decode of raw bytes, the `OverflowError` rule and
    `re.fullmatch` for `error_code` (E6).
  - Step 6: `close()` never raises and sets a closed flag (E12).
  - Everywhere: replace "`from None`" with "raised outside the `except` block, so `__cause__` and
    `__context__` are `None`" (E7.4).
  - Acceptance: "a body over the size cap (streamed and gzip-encoded)" becomes "a streamed body over
    the cap stops early; any non-identity `Content-Encoding` is refused before reading".
- **Task 03.** Acceptance criterion "`httpx` is not in `sys.modules` ... after ... a deep scan with
  gate 2 closed" becomes "`docsentinel.fact_check.lenz` is absent and no socket is opened" (spaCy
  imports `httpx`, E13, extract-facts E1); `doctor` holds only with the consent variable unset. Add
  the E10 lock conditions.
- **Task 04.** Add every test in the map above, including the new file
  `tests/unit/test_lenz_client_static.py`. Step 4 "a gzip-encoded body that decodes past the cap"
  becomes "any `Content-Encoding` other than `identity` is refused before decoding". The "no real
  sleep" rule allows the one bounded `join` of `test_hung_header_phase_bounded` (at most 1 s). The
  no-secret-leak capture includes `__context__`.
- **Story README.** U2: the deadline is a hard wall-clock limit enforced outside blocking reads
  (E4); the cap counts raw bytes of an identity-encoded body (E5). U5: the exception list of E12.
  Security notes: "size cap ... enforced on the raw response body" now means E5, and add the
  `trust_env=False` decision (E3).
- **Plan C10 / ADR 0007 (Q3 text).** "the worst case is the budget plus one backend request
  timeout" holds only with E4; add the reference.
- **status.md.** Pointer line still to be added (Task 01 deliverable): verdict PASS_WITH_FOLLOWUP,
  this file.

## Follow-ups and open questions for the owner (not blocking)

- **OQ-E1 (EG-14).** Stop `DS302`'s loop after the first HTTP 401/403 (and optionally after N
  consecutive 429/5xx). It is a circuit-break, which the story's non-goals exclude, so it is not
  added here.
- **OQ-E2 (EG-3).** Proxy and private-CA support for users behind a mandatory proxy: if wanted, an
  invoker-only CLI flag or keyword, never a configuration key and never ambient variables.
- **FU-1 (EG-6, Story 01.0 code).** `FactCheckResult.__post_init__` lets `OverflowError` escape for
  a huge `int` confidence; convert with `float()` in a `try` and raise the fixed `FactCheckError`.
  Test: unit `test_fact_check_protocol.py` with `confidence=10**400`.

## Residual risks

- **RE1.** The backend operator receives every sent claim and the key by design; TLS protects only
  against third parties.
- **RE2.** A library caller who enables root DEBUG logging receives `httpcore` traces with response
  headers and the `httpx` INFO line with the server's reason phrase (untrusted text, not
  neutralised by DocSentinel). E7 removes the only path by which the key could appear there.
- **RE3.** An abandoned E4 worker keeps a socket open until the peer closes it, its read times out
  or the process exits; bounded in count by the time budget.
- **RE4.** The trust anchors are the `certifi` bundle shipped in the lock; a compromised CA in that
  bundle is out of scope.
- **RE5.** The embedded key in examples/docs/lenz_fact-checking.md stays committed until the owner
  acts on Q5.

## Verdict: PASS_WITH_FOLLOWUP

There is no CRITICAL finding, so the story is not stopped and the merge is not blocked by this
review. Three findings are **HIGH**: EG-4 (the per-request deadline does not bound a hung call),
EG-5 (decompression bomb through `iter_bytes()`) and EG-7 (key handling, carrying FC-5). All three
are specification defects with concrete mitigations; Task 02 may start once the Task 02 amendments
above are folded in.

Merge-gate conditions. Any of the following in a Story 03.0 change, or a later change to
`fact_check/lenz.py`, is a **BLOCK** and must be kept out of `master`:

- the request URL, host or path depends on anything but the class constants, or
  `follow_redirects` is not explicitly `False` (E1, E2);
- `trust_env` is not explicitly `False`, or any `verify`/`cert`/`proxy` setting exists (E3);
- a response body is read through a content decoder, the cap counts decoded bytes, or a body is
  fully buffered before the cap check (E5);
- a single `check_claim` can block longer than `REQUEST_TIMEOUT_SECONDS` plus scheduling slack, or
  `test_hung_header_phase_bounded` is missing or skipped (E4);
- the key is not validated before use, any `FactCheckError` has a `__cause__` or `__context__`, or
  the sentinel key or any prefix appears in any E7 sink (E7);
- any exception type listed in E12 can leave `check_claim` as something other than
  `FactCheckError`, or `close()` can raise (E12);
- `import docsentinel`, a fast or standard scan, or a gate-closed deep scan imports
  `docsentinel.fact_check.lenz` (E13);
- any test sends a real request, or any file contains the embedded key in
  examples/docs/lenz_fact-checking.md or any part of it.

## Addendum 2026-11-27: response parsing and logging rulings

The findings above are kept as written. Owner ruling R of 2026-11-27 replaces ruling Q4 and changes EG-9 and E9:

- **EG-9 / E9.** Every item of `claims` is now read (`verdict`, `confidence`, and `claim` for the trace line only), not
  only `claims[0]`. Labels map through `VERDICT_LABELS` (true, mostly true, false, mostly false, mixed, half true,
  unverifiable); any other label is rated `unverifiable` (printed, never a finding), so the fixed message
  `lenz /assess returned an unrecognised verdict` is no longer raised for an unknown label. The confidence words
  `high`, `medium` and `low` map to 0.9, 0.6 and 0.3. The response is still strict-UTF-8 JSON under the same size cap,
  and citations and every other field are still ignored.
- **Logging.** "The module never logs any response value" no longer holds. The client logs, at INFO, per claim row: the
  first ten words of the backend's `claim` echo (`log.quote_start`), the raw verdict label capped at 40 characters
  through `safe()`, the mapped verdict and the confidence; at DEBUG it logs its own fixed rejection message. Both
  strings are third-party controlled and pass through `safe()`, so they cannot forge a record or a GitHub Actions
  command. Citations, other fields and keys are still never logged.
- **Key fallback.** See the gating model's addendum of the same date: `LENZ_API_KEY` is now read as a fallback.
