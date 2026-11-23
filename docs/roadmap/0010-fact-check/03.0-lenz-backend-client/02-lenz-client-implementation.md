# Task 02 — `LenzFactCheckClient`: the one concrete backend

**Parent story:** [Story 03.0](/docs/roadmap/0010-fact-check/03.0-lenz-backend-client/README.md)  
**Role:** Python Expert  
**Depends on:** [Task 01](./01-egress-threat-review.md). Its verdict must not be BLOCK, and its
E-mitigations are binding requirements for this task.

## Goal

Implement `LenzFactCheckClient` in `src/docsentinel/fact_check/lenz.py` (amended 2026-11-21 from
the planned `detectors/fact_check_lenz.py`; plan contract C9). It satisfies the Story 01.0
`FactCheckClient` Protocol and follows the documented `/assess` shape. Its transport is fixed and
bounded. Every failure becomes `FactCheckError`. The module imports only the standard library,
`httpx`, `docsentinel.fact_check.protocol` and `docsentinel.log`; never `config`, `detectors` or
`mining`.

## Inputs

- Story README [decisions U1 to U7](/docs/roadmap/0010-fact-check/03.0-lenz-backend-client/README.md#decisions)
  and the [interface sketch](/docs/roadmap/0010-fact-check/03.0-lenz-backend-client/README.md#interface-concrete-implementation-sketch).
  The sketch is not final code. Where it disagrees with this task, follow this task. In particular,
  the sketch buffers the whole body before checking its size, and its `except` branch can read a
  `payload` that was never assigned.
- Contracts [C2](/docs/roadmap/0010-fact-check/plan.md#c2--backend-protocol),
  [C3](/docs/roadmap/0010-fact-check/plan.md#c3--api-key-environment-variable-naming) and
  [C4](/docs/roadmap/0010-fact-check/plan.md#c4--fixed-transport-bounded-content).
- The Task 01 egress threat model,
  [`threat-model-0010-fact-check-egress-2026-11-24.md`](/docs/security/threat-model-0010-fact-check-egress-2026-11-24.md)
  (PASS_WITH_FOLLOWUP; HIGH EG-4, EG-5, EG-7). Its mitigations E1 to E13 and its merge-gate
  conditions are binding. Where this task and the threat model disagree, the threat model wins.
- `/src/docsentinel/fact_check/protocol.py` (Story 01.0 Task 04).

> **Amended 2026-11-24 (egress threat model).** Steps 1 to 4 and 6 below are rewritten to fold in
> E1 to E12. Everywhere in this task, "`from None`" is replaced by: **raised outside the `except`
> block, so `__cause__` and `__context__` are `None`** (E7.4). Record the condition inside the
> handler, leave it, then raise.

## Steps

1. **Class constants** (C4; none of them read from any configuration). *Amended 2026-11-24
   (egress threat model, E1, E7, E8).*
   - `name = "lenz"`
   - `API_KEY_ENV_VAR = "DOCSENTINEL_FACTCHECK_LENZ_API_KEY"`
   - `BASE_URL = "https://lenz.io/api/v1"`
   - `ASSESS_URL: ClassVar[str] = BASE_URL + "/assess"` (E1). The only URL the client ever sends to.
   - `REQUEST_TIMEOUT_SECONDS = 30.0`. This value is passed to `httpx` as the per-operation timeout
     and is also the hard total per-request deadline of E4 (step 3).
   - `MAX_RESPONSE_BYTES = 65_536` (raw bytes, E5).
   - `MAX_CLAIM_CHARS: ClassVar[int] = 1000` (E8). Defined here, not imported from the detector
     (C9 forbids that import); a drift test keeps it equal to
     `detectors.fact_check.MAX_CANDIDATE_CHARS`.
   - `MIN_API_KEY_CHARS = 16`, `MAX_API_KEY_CHARS = 256` (E7.1).
   - Module level: `_monotonic = time.monotonic`, the clock alias that is the E4 test seam (patching
     it never touches the global `time` module).
2. **`__init__(self, api_key: str, *, transport: httpx.BaseTransport | None = None)`**. *Amended
   2026-11-24 (egress threat model, E3, E7, E8, E11).*
   - Validate the key first (E7.1): it must be a `str` that `re.fullmatch`es `[\x21-\x7e]{16,256}`
     (printable ASCII; no space, tab, CR, LF, DEL or non-ASCII). No stripping or repair. Otherwise
     raise `FactCheckError("lenz API key is missing or malformed")` before any `httpx` object
     exists. The message never contains the key. This makes the `h11` `Illegal header value` error,
     the only path by which `httpcore` would log the key, unreachable.
   - Build the header dictionary once (E7.2, E8): `Authorization: Bearer <key>`,
     `Accept: application/json`, `Accept-Encoding: identity`, `User-Agent: docsentinel` (fixed
     literal; no version, platform, host, user, path or repository). Give it only to
     `httpx.Client(headers=)`. The key is stored in no other attribute, and the constructor's local
     is not retained.
   - Build one `httpx.Client` with:
     - `timeout=REQUEST_TIMEOUT_SECONDS`; no `base_url` is needed, because the only call uses the
       absolute `ASSESS_URL` (E1)
     - `follow_redirects=False`, set explicitly (E2)
     - `trust_env=False`, set explicitly (E3): no proxy or CA environment variable and no OS proxy
       setting is honoured
     - the headers above
     - `transport=transport`
   - Never pass `verify=`, `cert=`, `proxy=`, `auth=`, `mounts=`, `event_hooks=` or `params=`
     anywhere in the module (E1, E3). The constructor has no such parameter.
   - `transport` is keyword-only, default `None`, and only a seam for injecting a test transport.
     Its docstring must say so. No module under `src/docsentinel/` passes it; `DS302` keeps
     `client_cls(api_key=...)` (E11).
3. **`check_claim(claim)`**. *Amended 2026-11-24 (egress threat model, E1, E2, E4, E5, E8, E12).*
   1. **Closed client:** if `close()` has run, raise `FactCheckError("lenz client is closed")`
      without touching `httpx` (E12).
   2. **Claim validation (E8), before any network use:** a non-`str`, an empty or whitespace-only
      string, more than `MAX_CLAIM_CHARS` code points, or a string that fails `.encode("utf-8")`
      (lone surrogate) raises
      `FactCheckError("lenz /assess claim text is empty, too long or not encodable")`.
   3. **Hard deadline (E4):** record `deadline = _monotonic() + REQUEST_TIMEOUT_SECONDS`. Run the
      whole request (connect, send, headers, status and encoding checks, capped raw read) in a
      `threading.Thread(daemon=True)`; the caller waits with `join(timeout=remaining)`. Never use
      `concurrent.futures` (its exit hook joins workers and would hang interpreter exit on a stuck
      read). On expiry the caller sets an abandon flag and raises
      `FactCheckError("lenz /assess request exceeded the time limit")`; the worker discards its
      result and closes its response when it next wakes, so the stuck connection never returns to
      the pool. An equivalent design (for example a deadline-aware network backend) is acceptable
      only if it passes the same Task 04 tests.
   4. **Request (E1, E8):** clear the cookie jar, then `client.stream("POST", ASSESS_URL,
      json={"claim": claim})`. The body is exactly `{"claim": claim}`. No URL, path, query or host
      component is ever derived from claim text, config, environment or response data.
   5. **Status (E2):** any status other than 200, 3xx included, raises
      `FactCheckError("lenz /assess returned HTTP <int>")` before the body is read. The message
      carries the integer status and nothing else (no `Location`, no reason phrase).
      `response.next_request` is never used.
   6. **Encoding and length (E5), before any body read:** split every `Content-Encoding` value on
      commas, strip and case-fold each token; any token other than `identity` raises
      `FactCheckError("lenz /assess response used an unsupported content encoding")`. A present
      `Content-Length` greater than `MAX_RESPONSE_BYTES` raises
      `FactCheckError("lenz /assess response exceeded the size cap")`; it is never used as an
      allocation hint.
   7. **Raw read (E5, E4):** read only with `response.iter_raw()` (transfer-decoded, not
      content-decoded); never `iter_bytes`, `iter_text`, `read`, `.content`, `.text` or `.json()`.
      Keep a running total of raw bytes; as soon as it exceeds `MAX_RESPONSE_BYTES`, close the
      response and raise the size-cap error. Between chunks, check `_monotonic() >= deadline` and
      stop with the time-limit error. *Replaces the earlier "read the decoded body with
      `iter_bytes()`" rule, which let one 64 KiB gzip chunk, or a 2 KB `gzip, gzip` body, inflate
      past the cap.*
   8. **Exception boundary (E12):** map `httpx.HTTPError`, `httpx.StreamError`, `httpx.InvalidURL`,
      `ValueError` (incl. `UnicodeError`), `OverflowError`, `RecursionError` and a `FactCheckError`
      from `FactCheckResult` to the fixed messages (transport failures:
      `lenz /assess request failed (<exception type name>)`). Never `str(exc)` or `repr(exc)` of a
      foreign exception. Anything else propagates to `DS302`'s M5 containment. Every
      `FactCheckError` is raised outside the `except` block (E7.4).
   The complete message set (each at most 200 characters, none containing request or response
   data) is the one listed in E12; Task 04 asserts each exact text.
4. **Parsing.** Apply these steps in order. *Amended 2026-11-24 (egress threat model, E6, E9).*
   1. Decode the collected raw bytes with `bytes.decode("utf-8", "strict")`, never the server's
      declared `charset`. Then call `json.loads(text, parse_constant=<raise>)` so `NaN`,
      `Infinity` and `-Infinity` are refused. `ValueError` (incl. `JSONDecodeError`,
      `UnicodeDecodeError` and the 4,300-digit integer limit) and `RecursionError` map to
      `FactCheckError("lenz /assess returned an unexpected response shape")`.
   2. The top level must be a `dict`.
   3. If `error_code == "no_claim"`, return `FactCheckResult("unverifiable", 0.0, "lenz")` (U6).
   4. If `error` or `error_code` holds any other non-null value, raise `FactCheckError`. Name the
      code (`lenz /assess returned error <code>`) only when it is a `str` that
      `re.fullmatch`es `[a-z_]{1,64}`; otherwise the message is `lenz /assess returned an error`.
      The `error` text is never used.
   5. `claims` must be a `list`. An empty list returns `unverifiable` with confidence `0.0`.
   6. Use the first element only, and document this choice in the module docstring. It must be a
      `dict`. Only `claims[0]["verdict"]` and `claims[0]["confidence"]` are read; the response's
      `claim` echo, extra fields and any citation-like content are never read, so
      `FactCheckResult.citations` is always `()` (E9).
   7. `verdict` must be a `str`.
   8. `confidence`: `type(v) in (int, float)` (so `bool` is refused; a `str` such as `"0.9"` is
      refused), then `float(v)` inside a `try` that maps `OverflowError` to the shape error, then
      `math.isfinite`. Otherwise raise `FactCheckError`.
   9. Clamp `confidence` to `[0.0, 1.0]`. Only a `float` is passed to `FactCheckResult`.
5. **`_normalize_verdict(raw: str) -> Optional[Verdict]`** (U7, amended 2026-11-21 by owner ruling
   Q4, ADR 0007 Contract 8):
   - Strip the raw string and case-fold it.
   - `"true"` maps to `"true"`, and `"false"` maps to `"false"`.
   - Any other value, including `""`, returns `None`. `check_claim` then raises
     `FactCheckError("lenz /assess returned an unrecognised verdict")`, which never echoes the raw
     value. `DS302` logs its per-claim WARNING and skips the claim.
   - There is no confidence band: an unknown value is never mapped to `"mixed"` or
     `"unverifiable"`. The earlier proposed 0.35 to 0.65 band and its `_MIXED_BAND_*` constants are
     dropped.
6. **`close()`** releases the `httpx.Client` and is idempotent. *Amended 2026-11-24 (egress
   threat model, E12, E7.3):* it never raises (an `Exception` from `httpx.Client.close()` is
   swallowed and logged at DEBUG by type name only) and sets a closed flag that step 3.1 checks.
   `__repr__` **and `__str__`** return `LenzFactCheckClient(base_url='https://lenz.io/api/v1')` and
   nothing more.
7. Logging:
   - The module itself logs at most DEBUG counts and status codes.
   - It never logs the claim, the body, the headers, the key or any response value (E9).
   - *Amended 2026-11-24 (egress threat model, E7.5):* DocSentinel never attaches a handler to,
     or changes the level or propagation of, the `httpx` or `httpcore` loggers.
   - *Amended 2026-11-24 (egress threat model, E13):* the module does no I/O, constructs no client
     and reads no environment at import; its only import-time side effect is the registry entry
     (Task 03).
8. The module docstring has a "Known limitations" section in the style of `DS301`: the verdict is a
   third party's heuristic output and not ground truth, the vocabulary may change on the provider's
   side, and only `/assess` is used.
9. Report a `Docs impact:` line covering triggers A and R.

## Deliverables

- `/src/docsentinel/fact_check/lenz.py` (new). Registration and the dependency are added in
  [Task 03](./03-backend-registry-wiring.md).

## Acceptance criteria

- [ ] `isinstance(LenzFactCheckClient("k" * 16, transport=mock), FactCheckClient)` is true.
- [ ] Each documented response shape maps exactly as specified: success, `no_claim`, empty `claims`,
      a non-200 status, a 3xx status, malformed JSON, deep nesting, a wrong-typed `confidence`
      (`bool`, `str`, a 400-digit integer), `NaN`/`Infinity`, a non-UTF-8 body, and an unrecognised
      or empty `verdict` string. Every failure is a `FactCheckError` with one of the fixed E12
      messages. *Amended 2026-11-24 (egress threat model):* "a body over the size cap (streamed and
      gzip-encoded)" becomes "a streamed body over the cap stops early; any non-identity
      `Content-Encoding` is refused before reading".
- [ ] *Amended 2026-11-24 (egress threat model, E4):* a stalled header phase or a dripping body
      raises `lenz /assess request exceeded the time limit`; no single `check_claim` blocks longer
      than `REQUEST_TIMEOUT_SECONDS` plus scheduling slack; no `concurrent.futures`.
- [ ] No `FactCheckError` message, log record (root, `httpx`, `httpcore` at DEBUG), `repr`/`str`
      or client attribute contains the key or the `Authorization` value. *Amended 2026-11-24
      (egress threat model, E7):* a malformed key is refused before any `httpx` object exists, and
      no `FactCheckError` has a `__cause__` or `__context__`.
- [ ] The request carries only the `claim` field, goes to exactly `https://lenz.io/api/v1/assess` and
      follows no redirect. *Amended 2026-11-24 (egress threat model, E1, E3, E8):* the client is
      built with `trust_env=False` and `follow_redirects=False`; headers are exactly the E8 set; no
      `Cookie` is sent; claim bounds are refused before send.
- [ ] *Amended 2026-11-24 (egress threat model, E12):* `close()` is idempotent and never raises;
      `check_claim` after `close()` raises `lenz client is closed`.
- [ ] No code path reads `os.environ`. The key arrives only through the constructor.
- [ ] The module is fully typed and passes ruff.

## Test expectations

The tests are in [Task 04](./04-fixtures-and-tests.md). They use mock transports only.

## Out of scope

- Retries, backoff and circuit breaking (story non-goals).
- `/extract`, `/verify` and `/ask`.
- Any `pyproject.toml` change (Task 03).
