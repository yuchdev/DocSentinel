# Task 03 — fixture manifest verification and test harness

1. Add `tests/integration/test_milestone_0005_fixture_catalog.py` that reads the checked-in `fixture-matrix.json` (or generated dict) and enumerates every promised directory under `tests/assets/`. Validate **2–4 snake-case words**, dsNNN matching the declared rule and at least one Markdown `.md` per case.
2. Require every scenario from manifest to appear in one rule-specific parametrized integration test; `clean`/`finding`/`error` expectations must be asserted, not merely constructed.
3. Raise an informative failure if a rule is not registered/selected/actually executed. A zero-findings result from an unexecuted optional rule is not a CLEAN result.
4. Make asset copies byte-exact and case-isolated. Reuse existing `tests/asset_helpers.py` and `asset_case` fixture; do not add a replacement asset loader.
5. Protect test assets from repository self-scan and format-on-save; preserve intentionally invalid Markdown. Add expected counts and verify matrix.csv/json/md synchronized.

**Acceptance:** manifest parity test fails on missing/extra/misnamed scenario folders; tests can load each specified case reproducibly and do not hide missing analyzers.
