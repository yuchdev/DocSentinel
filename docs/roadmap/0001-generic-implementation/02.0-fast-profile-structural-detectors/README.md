# Story 02.0 - Fast-Profile Structural Detectors

The first real entries in `engine.ANALYZERS`. All three detectors are single-document,
regex/stdlib-only, and zero-dependency - exactly the bar `docs/architecture/README.md` sets for
`fast`. This story is what turns `docsentinel scan` from "lists files" into "can actually fail a
build."

## Tasks

| # | Task | Rule | Output |
|---|------|------|--------|
| 01 | [Dangling link / anchor detector](01-dangling-link-anchor-detector.md) | `DS101` | `src/docsentinel/detectors/links.py` |
| 02 | [Stray HTML comment detector](02-stray-html-comment-detector.md) | `DS102` | `src/docsentinel/detectors/comments.py` |
| 03 | [Unresolvable path-like code span detector](03-unresolvable-path-detector.md) | `DS103` | `src/docsentinel/detectors/paths.py` |
| 04 | [Detector package wiring & end-to-end test](04-detector-package-wiring.md) | - | `src/docsentinel/detectors/__init__.py`, docs refresh |

01-03 are independent of each other (different rule codes, no shared state) and can be
implemented in any order; 04 depends on all three existing.
