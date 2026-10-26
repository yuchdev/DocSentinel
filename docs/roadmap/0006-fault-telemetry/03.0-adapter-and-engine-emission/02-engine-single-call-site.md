# Task 02 — Single emission call site in `engine.scan()`

**Parent story:** [Story 03.0](/docs/roadmap/0006-fault-telemetry/03.0-adapter-and-engine-emission/README.md)  
**Proposed source:** `src/docsentinel/engine.py`

## Required work

Emit telemetry from exactly **one** place in `scan()`: immediately **after** the
`ScanResult` is assembled and **before** it is returned. There must be no second
`scan()` entry point and no duplication of the finding-iteration that already
builds `findings`.

Sketch of the single call site (described, not implemented):

```
result = ScanResult(...)            # the existing assembly, unchanged
if settings.telemetry_enabled:
    _emit_telemetry(result, settings, suppressed)   # one helper, swallows errors
return result
```

- `suppressed` is the set of findings removed by the baseline filter. `scan()`
  already computes `filter_baselined(findings, known)`; capture the difference
  (pre-filter minus post-filter) so the adapter can label those `"suppressed"`.
  When no baseline is configured, `suppressed` is empty.
- `_emit_telemetry` builds the sink via `telemetry.build_sink(settings)`, iterates
  `telemetry.events_for_result(result, model=settings.generated_by_model or None,
  suppressed=suppressed)`, calls `sink.emit(event)` for each, and — **only when the
  sink exposes `close`** (duck-typed per the Protocol) — calls `sink.close()` in a
  `finally`.
- **Error isolation:** wrap the whole emission (including `build_sink`, so a failed
  custom-sink import or a bad selector cannot crash the scan) in a `try/except
  Exception` that swallows. Telemetry is observational; a sink failure must never
  change the scan verdict, exit code, or `ScanResult`, and must not reach the CLI's
  `(ConfigError, ValueError, OSError)` handler.

## Constraints

- `ScanResult` shape, JSON report schema v1, exit codes, and `enabled_rules`
  semantics are unchanged.
- When `telemetry_enabled` is false, no sink is built and no event is created —
  zero overhead and zero output.
- The deep-profile early-return branches (opt-in not confirmed / deps missing)
  return before rule evaluation; per ADR intent those early returns emit nothing
  (no rule evaluated). Document this in the helper.

## Tests (for `testing-expert`)

- Integration: a scan with `telemetry_enabled` and a temp `file:` sink writes one
  JSON Lines event per finding plus one `"pass"` per evaluated clean rule; each line
  is valid JSON with the agreed keys.
- Integration: the same scan with telemetry off writes nothing and its stdout /
  exit code are unchanged.
- Mock: a sink whose `emit` raises, and a `python:` target that fails to import,
  each leave the exit code and returned `ScanResult` unchanged.
- Integration: baseline-suppressed findings appear as `"suppressed"` events.
- Integration: a sink exposing `close` has it called exactly once; a sink without
  `close` is not probed for one.
