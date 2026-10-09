# Story 02.0 - Text Complexity Detector (`DS201`)

The first `standard` detector, and the simplest: flag a document whose prose is harder to read than
a configurable grade-level threshold, using `textstat`'s readability metrics. It is single-document
(like a `fast` detector), but it belongs to `standard` - not `fast` - for one reason: it depends on
`textstat`, and `fast` is defined as stdlib-only, zero-dependency. The dependency is what puts it
behind the `docsentinel[standard]` extra, not corpus-wideness.

This story proves the Story 01.0 lazy-load plumbing end-to-end with a real detector: `DS201`
registers into the `standard` subpackage's import list, is reachable only via
`ensure_standard_loaded()`, and fires real findings.

## Tasks

| # | Task | Rule | Output |
|---|------|------|--------|
| 01 | [Complexity detector & grade threshold](01-complexity-detector.md) | `DS201` | `src/docsentinel/detectors/standard/complexity.py`, `Config.max_grade_level` |
| 02 | [Package wiring & end-to-end test](02-wiring-and-end-to-end.md) | - | `detectors/standard/__init__.py` import line, `tests/test_standard_profile_end_to_end.py` |

01 writes the detector and its config field; 02 wires it into the lazily-loaded subpackage and
proves the whole chain (extra present → `scan --profile standard` → `DS201` findings).
</content>
