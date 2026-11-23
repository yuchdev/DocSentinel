# Task 04 — Lenz client tests on mocked transport; session-wide network guard

**Parent story:** [Story 03.0](/docs/roadmap/0010-fact-check/03.0-lenz-backend-client/README.md)  
**Role:** Testing Expert  
**Depends on:** Tasks 02 and 03. The Task 01 egress threat model is a standing input.

## Goal

Test the Lenz client against hand-written response bodies through `httpx.MockTransport`. Add a
test-session guard that fails any test that reaches a real `httpx` transport. Never send a real
request.

## Inputs

- Story README [acceptance criteria](/docs/roadmap/0010-fact-check/03.0-lenz-backend-client/README.md#acceptance-criteria)
  and [test plan](/docs/roadmap/0010-fact-check/03.0-lenz-backend-client/README.md#test-plan).
- The acceptance criteria of Tasks 02 and 03. Write one test for each E-mitigation in the Task 01
  threat model.
- `/tests/conftest.py` and `/tests/fact_check_fakes.py` from Story 01.0 Task 06.

## Steps

1. **Network guard.** In `/tests/conftest.py`, add a session-scoped autouse fixture that patches
   `httpx.HTTPTransport.handle_request` and `httpx.AsyncHTTPTransport.handle_async_request` to raise
   `AssertionError("real network transport reached")`. `MockTransport` is not affected.
   - The fixture may import `httpx` in the test process. Every lazy-import assertion runs in a
     fresh `python -I` subprocess, so importing `httpx` here cannot hide a lazy-import regression.
   - Add one self-test proving the guard trips. It uses a default `httpx.Client` against a
     non-routable test address and expects the guard's assertion.
2. **Fixtures.** Write every JSON body inline in the test module as a literal. Build each body from
   the five documented field names only. Do not load, copy or paraphrase text from
   `examples/docs/lenz_fact-checking.md`, and do not import `examples/check_fact.py`. Use a sentinel
   key such as `"sentinel-not-a-real-key-0010"`.
3. **`tests/unit/test_lenz_verdict_normalization.py`**:
   - `"True"`, `"False"`, `" true "` and `"FALSE"` map to `true`/`false`.
   - `""`, `"Mixed"` and an unknown string return `None` (owner ruling Q4, 2026-11-21; there is no
     confidence band), and through `check_claim` (mock transport) they raise `FactCheckError` whose
     message does not contain the raw value, at confidence `0.0`, `0.5` and `1.0` alike.
   - The verdict strings `"True"` and `"False"` are typed by hand. They are not imported from
     `CLAIMS_DB`.
4. **`tests/mock/test_lenz_client_transport.py`** uses `MockTransport` handlers that record the
   request. Cover these cases:
   - Success: the result maps correctly and confidence is clamped (for example 1.4 becomes 1.0).
   - `no_claim` and empty `claims` both give `unverifiable`.
   - Any other `error_code` raises `FactCheckError`.
   - HTTP 401, 429 and 500 raise `FactCheckError`.
   - A 302 response with a `Location` header raises `FactCheckError` and makes no second request.
   - Malformed JSON, a top level that is not a dict, a `claims` value that is not a list,
     `confidence` given as `"0.9"`, as `True` or as `NaN`, and nesting 10,000 levels deep each raise
     `FactCheckError`.
   - A body of `MAX_RESPONSE_BYTES + 1` bytes, streamed in chunks, raises `FactCheckError` before the
     whole body is read. Assert on the number of bytes read.
   - *Amended 2026-11-24 (egress threat model, E5):* ~~A gzip-encoded body that decodes past the
     cap raises `FactCheckError`.~~ Any `Content-Encoding` other than `identity` is refused before
     decoding (see `test_gzip_encoded_body_refused` in step 7).
   - A slow-drip stream that exceeds the deadline raises `FactCheckError`. Patch the clock; do not
     sleep in real time.
   - The recorded request has method `POST`, URL `https://lenz.io/api/v1/assess`, body exactly
     `{"claim": ...}`, an `Authorization` header with the sentinel key, and no other identifying
     header.
   - A malformed key (empty, containing CR/LF or a space, or too long) raises `FactCheckError`
     without echoing the key.
   - `close()` is idempotent.
5. **`tests/mock/test_lenz_client_no_secret_leak.py`**:
   - Capture every log record at DEBUG, including the `httpx` and `httpcore` loggers, across every
     case in step 4.
   - Assert that the sentinel key never appears in any record, in any `FactCheckError` message or its
     chained `__cause__` string, in any `FactCheckResult` field, or in `repr(client)` and `str(client)`.
   - *Amended 2026-11-24 (egress threat model, E7):* the capture also covers `__context__` and
     `vars(client)` (excluding the masked `httpx` header store), and every `FactCheckError` must
     have `__cause__ is None` and `__context__ is None`.
6. **Registry and lazy import** (in the transport test module, or a separate small module):
   - `load_backend("lenz")` returns the class.
   - A fresh-interpreter subprocess check shows that `httpx` is absent after a fast scan, a standard
     scan and a gate-closed deep scan (Task 03 acceptance criterion).
   - *Amended 2026-11-24 (egress threat model, E13):* for the gate-closed deep scan the assertion is
     that `docsentinel.fact_check.lenz` is absent and no socket was opened; `httpx` may be present
     because spaCy imports it. See `test_lenz_import_isolation` in step 7.
   - `tests/unit/test_fact_check_layering.py` (Story 01.0 Task 06) now also covers
     `fact_check/lenz.py` and stays green; `httpx` is allowed there and nowhere else in the package
     (plan contract C9, amended 2026-11-21).
7. **Egress mitigation tests.** *Amended 2026-11-24 (egress threat model).* One test per entry of
   the [mitigation-to-test map](/docs/security/threat-model-0010-fact-check-egress-2026-11-24.md#mitigation-to-test-map);
   the threat model's E-text defines each assertion. Where a test below overlaps a case in steps 3
   to 6, use the name below.

   | Mitigation | File | Tests |
   |---|---|---|
   | E1 | mock `test_lenz_client_transport.py` | `test_request_targets_exact_assess_url` (claim text with `?`, `#`, a dot-dot path segment, `@` and a full URL leaves the recorded URL `https://lenz.io/api/v1/assess`) |
   | E1 | unit `test_lenz_client_static.py` | `test_lenz_no_url_from_data` (AST: the only URL argument is `ASSESS_URL`; no `auth`/`event_hooks`/`mounts`/`proxy` keyword) |
   | E2 | mock transport | `test_redirect_302_not_followed` (one request recorded; message holds `302`, not the `Location` value), `test_status_401_429_500_raise` |
   | E3 | unit static | `test_client_trust_env_false_and_no_verify_knob` (AST: no `verify`/`cert`/`proxy` keyword; constructor has no such parameter) |
   | E3 | mock transport | `test_env_proxy_and_ca_vars_ignored` (`HTTPS_PROXY`, `ALL_PROXY`, `SSL_CERT_FILE`, `SSL_CERT_DIR` via `monkeypatch`, **no** transport injected: `trust_env is False`, no proxy mounts, no request sent) |
   | E4 | mock transport | `test_slow_drip_body_exceeds_deadline` (patched module `_monotonic`, no real sleep); `test_hung_header_phase_bounded` (handler blocks on a `threading.Event`; a test subclass sets `REQUEST_TIMEOUT_SECONDS = 0.05`; `FactCheckError` within 1 s; the event is set in teardown) |
   | E4 | unit static | `test_no_executor_used` (AST: no `concurrent.futures`) |
   | E5 | mock transport | `test_oversized_streamed_body_stops_early` (`MAX_RESPONSE_BYTES + 1` bytes in 4 KiB chunks from a generator stream; bytes pulled at most cap plus one chunk); `test_gzip_encoded_body_refused` (`gzip`, `gzip, gzip`, `deflate`, including a small double-gzip bomb built in the test: refused before decoding, no decoder invoked); `test_content_length_over_cap_refused`; `test_misleading_content_length_ignored_for_cap` |
   | E6 | mock transport | `test_deep_nesting_raises_fact_check_error` (10,000 levels, within the cap); `test_nan_infinity_refused`; `test_huge_integer_confidence_refused` (400 digits: `FactCheckError`, not `OverflowError`); `test_confidence_bool_str_refused`; `test_non_utf8_body_refused` (also with `charset=latin-1` declared); `test_top_level_and_claims_types`; `test_error_code_not_echoed_unless_safe` (CR/LF, `##[`, 65 characters, ANSI escape; `error` text never in the message) |
   | E7 | mock transport | `test_malformed_key_refused_without_echo` (empty, CR/LF, trailing space, tab, DEL, non-ASCII, 15 and 257 characters, a `Bearer `-prefixed value) |
   | E7 | mock no-secret-leak | `test_sentinel_absent_from_all_sinks` (DEBUG capture on root, `httpx`, `httpcore`; `repr`/`str`; messages; `__cause__`; `__context__`; result fields; `vars(client)`); `test_exceptions_have_no_chain` |
   | E7 | unit static | `test_lenz_does_not_touch_httpx_loggers` (AST over `src/docsentinel/`) |
   | E8 | mock transport | `test_request_body_and_headers_exact` (header name set equals the E8 list; body parses to exactly one key); `test_claim_bounds_refused_before_send` (1,001 code points, `""`, `"\ud800"`: no request recorded); `test_set_cookie_not_replayed` |
   | E8 | unit static | `test_max_claim_chars_matches_detector` (drift with `detectors.fact_check.MAX_CANDIDATE_CHARS`) |
   | E9 | unit `test_lenz_verdict_normalization.py` | `test_normalize_verdict_known_and_unknown` (step 3 cases) |
   | E9 | mock transport | `test_unrecognised_verdict_message_does_not_echo` (marker verdict at 0.0, 0.5, 1.0); `test_response_claim_and_extra_fields_never_used` (markers in the `claim` echo, an extra `citations` field and `error`: absent from result, messages and log records) |
   | E10 | unit static | `test_lenz_dependency_floor` (reads `uv.lock` and `pyproject.toml` as text: declared floor, locked `httpx>=0.28`, `h11>=0.16.0`) |
   | E11 | unit static | `test_transport_is_keyword_only_test_seam` (signature); `test_no_production_transport_argument` (AST over `src/docsentinel/`) |
   | E12 | mock transport | `test_every_failure_is_fact_check_error` (one case per fixed message, exact text); `test_close_idempotent_and_never_raises` (close twice; `httpx.Client.close` patched to raise); `test_check_claim_after_close` |
   | E13 | integration | `test_lenz_import_isolation` (fresh `python -I` subprocess with a socket guard: after `import docsentinel`, a fast scan, a standard scan, `rules` and `doctor` with the consent variable unset, neither `docsentinel.fact_check.lenz` nor `httpx` is loaded; after a confirmed gate-closed deep scan, `docsentinel.fact_check.lenz` is absent and no socket opened; with consent and a sentinel key, `doctor` may import the client but opens no socket) |

   - **Real time (amended 2026-11-24, egress threat model).** No test sleeps in real time, with one
     exception: `test_hung_header_phase_bounded` may make **one** bounded `join` of at most 1 s.
     Every other deadline test patches `_monotonic`.
   - The E13 integration test lives under `tests/integration/` (for example
     `tests/integration/test_lenz_import_isolation.py`); it loads no rule assets.

## Deliverables

New:
- `tests/unit/test_lenz_verdict_normalization.py`
- `tests/unit/test_lenz_client_static.py` (amended 2026-11-24, egress threat model: AST and
  signature checks, no network)
- `tests/mock/test_lenz_client_transport.py`
- `tests/mock/test_lenz_client_no_secret_leak.py`
- `tests/integration/test_lenz_import_isolation.py` (amended 2026-11-24, egress threat model, E13)

Updated:
- `tests/conftest.py` (the network guard)

## Acceptance criteria

- [ ] Every acceptance criterion in the story README and every E-mitigation has a named test.
- [ ] The network guard is active for the whole session, and its self-test proves it trips.
- [ ] No test file contains the key embedded in `examples/docs/lenz_fact-checking.md`, any prefix of
      that key, or text copied from that file.
- [ ] No test sleeps in real time for the deadline case. *Amended 2026-11-24 (egress threat
      model):* the only allowed real wait is the one `join` of at most 1 s in
      `test_hung_header_phase_bounded`, which is never skipped.
- [ ] *Amended 2026-11-24 (egress threat model):* every test of the
      [mitigation-to-test map](/docs/security/threat-model-0010-fact-check-egress-2026-11-24.md#mitigation-to-test-map)
      exists under its name, and none is skipped or marked `xfail`.

## Test expectations

- `uv run pytest tests/unit tests/mock -q -k lenz -p docsentinel.pytest_plugin` passes.
- `uv run pytest -p docsentinel.pytest_plugin` (the full suite) passes on Python 3.12 and 3.13 and
  makes no real network request.

## Out of scope

- End-to-end `DS302` through `scan()` (Story 04.0).
- Any test against the real endpoint, including a test that is "manual" or skipped by default.
