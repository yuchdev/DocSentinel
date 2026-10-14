# Task 01 — Fixture coverage audit

1. Build `tests/integration/test_milestone_0004_fixture_catalog.py` (or equivalent) to enumerate `tests/assets/dsNNN/*` and cross-check the manifest from `fixture-matrix.csv`. Do not omit fixture cases only because their detector is slow.
2. Verify per rule **>=3 clean** and **>=3 finding** independent directories plus each named edge; use 2–4-word snake-case slugs and at least one `.md` per case.
3. Require a parametrized integration test to load **each** case with `asset_case(rule,slug)` and assert its declared outcome, including exact `Finding.rule`, path, relevant line, severity and meaningful evidence. Cases with an expected `pending` verify explicit unreadiness/error, not no findings.
4. Check companion `.py`/`.toml` are realistic and that no main test input was generated ad hoc in Python rather than committed text files.
5. Preserve intentionally malformed docs: exclusions in self-scan, Ruff and Flakeforge remain intact.
6. Check fixture independence: running one case then another in the same tmp dir cannot hide a finding through overwritten README, cached vectorizers, or shared state.
7. Enforce no `xfail`, TODO, pass-only placeholders or `pytest.skip` masking an implemented rule. Model-dependent DS301 can retain a justified environment skip, but DS302 and DS316 must be independently runnable without it.

Deliver a checked manifest listing each rule, count and actual test that exercises each case; attach summary counts to milestone status.
