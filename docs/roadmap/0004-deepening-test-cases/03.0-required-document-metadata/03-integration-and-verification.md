# Task 03 — Integration, CLI and regression tests for `DS111`

**Story:** [Story 03.0](/docs/roadmap/0004-deepening-test-cases/03.0-required-document-metadata/README.md)

## Test files to add

- `tests/integration/test_detectors_metadata_ds111.py` — mandatory asset-based integration coverage, named with rule-code suffix.
- `tests/unit/test_frontmatter_ds111.py` — pure parsing/normalization algorithm tests; miniature strings permitted *only here*.
- `tests/integration/test_scan.py` and cross-profile end-to-end suites — additive tests only where needed; do not destabilize existing profile coverage.

## Golden path test shape

```python
from collections.abc import Callable
from tests.asset_helpers import AssetCase


def test_ds111_asset_case(asset_case: Callable[[str, str], AssetCase]) -> None:
    case = asset_case("ds111", "missing_title_field")
    # Supply explicit Markdown paths when companion .py/.toml files exist.
    documents = case.documents(*sorted(
        str(p.relative_to(case.root).as_posix())
        for p in case.root.rglob("*.md")
    ))
    # Invoke the detector and assert exact DS code, locations, message and severity.
    # The completed test MUST have concrete executable assertions: no pass/TODO placeholder.
```

In the real implementation use project imports, the shared `asset_case` fixture, `Config` overrides where required, and the stabilized adapter from Story 01.0. The illustrative code above is not a full test.

## Mandatory checks

- [ ] Test applicable and exempt paths using asset cases plus an injected config.
- [ ] Test duplicates, empty strings, CRLF, zero/false, unsupported YAML and malformed delimiters.
- [ ] Confirm DS102 does not unexpectedly flag legitimate metadata comments unless comments actually exist.
- [ ] Check strictly deterministic key ordering, line numbers and output formatting.

- [ ] A parametrized fixture test references **each** slug from `02-markdown-asset-cases.md` by name. No unreferenced directories.
- [ ] Three-plus pass fixtures assert no `DS111` findings, three-plus fail fixtures assert correct `DS111` findings, and every special edge is checked.
- [ ] Runtime `Config` overrides propagate to detector (not silently ignored due to reading a disk config).
- [ ] Registry includes the correct rule/profile/severity; `select=("DS111",)` executes only the intended rule within exact profile; `ignore` wins.
- [ ] Output is sorted deterministically by normalized path and source location; duplicate candidate pairs are suppressed as specified.
- [ ] JSON report includes `DS111` and meaningful evidence; line and severity are checked. CLI exit behavior follows profile policy.
- [ ] Baseline creation/suppression is demonstrated; a new finding not in baseline remains visible.
- [ ] Any missing capability returns actionable pending/error rather than a false clean report.
- [ ] Existing DS101–DS301 behavior and tests are unchanged.

## Targeted commands

```bash
uv sync --extra test --extra standard --extra deep
uv run pytest -p docsentinel.pytest_plugin tests/unit/test_frontmatter_ds111.py tests/integration/test_detectors_metadata_ds111.py
uv run pytest -p docsentinel.pytest_plugin tests/integration/test_scan.py
uv run docsentinel rules
```

If the spaCy model is not installed, DS302/DS316 **must** remain testable when selected alone with `deep_confirm=True`. Model-dependent DS301 tests may keep their existing honest skip policy.

## Performance and quality gates

- Existing fast analyzer import budget must remain free of standard/deep modules.
- All text samples small enough for normal CI; stress tests explicitly bounded.
- Use the repository's `unit/mock/integration/e2e` taxonomy; no ephemeral fixture-generation substitute for required asset cases.
- No baseline update is accepted as a replacement for resolving a regression in a shipped detector.
