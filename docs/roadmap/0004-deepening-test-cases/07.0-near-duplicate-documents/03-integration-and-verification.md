# Task 03 — Integration, CLI and regression tests for `DS208`

**Story:** [Story 07.0](/docs/roadmap/0004-deepening-test-cases/07.0-near-duplicate-documents/README.md)

## Test files to add

- `tests/integration/test_detectors_documents_ds208.py` — mandatory asset-based integration coverage, named with rule-code suffix.
- `tests/unit/test_document_similarity_ds208.py` — pure parsing/normalization algorithm tests; miniature strings permitted *only here*.
- `tests/integration/test_scan.py` and cross-profile end-to-end suites — additive tests only where needed; do not destabilize existing profile coverage.

## Golden path test shape

```python
from collections.abc import Callable
from tests.asset_helpers import AssetCase


def test_ds208_asset_case(asset_case: Callable[[str, str], AssetCase]) -> None:
    case = asset_case("ds208", "identical_full_documents")
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

- [ ] Corpus tests with two and three docs, threshold equality and order stability.
- [ ] Check handling of markdown metadata, code listings and short docs.
- [ ] Test explicit generated-doc exclusion and config validation.
- [ ] Record a small runtime regression check without hardware-specific thresholds.

- [ ] A parametrized fixture test references **each** slug from `02-markdown-asset-cases.md` by name. No unreferenced directories.
- [ ] Three-plus pass fixtures assert no `DS208` findings, three-plus fail fixtures assert correct `DS208` findings, and every special edge is checked.
- [ ] Runtime `Config` overrides propagate to detector (not silently ignored due to reading a disk config).
- [ ] Registry includes the correct rule/profile/severity; `select=("DS208",)` executes only the intended rule within exact profile; `ignore` wins.
- [ ] Output is sorted deterministically by normalized path and source location; duplicate candidate pairs are suppressed as specified.
- [ ] JSON report includes `DS208` and meaningful evidence; line and severity are checked. CLI exit behavior follows profile policy.
- [ ] Baseline creation/suppression is demonstrated; a new finding not in baseline remains visible.
- [ ] Any missing capability returns actionable pending/error rather than a false clean report.
- [ ] Existing DS101–DS301 behavior and tests are unchanged.

## Targeted commands

```bash
uv sync --extra test --extra standard --extra deep
uv run pytest -p docsentinel.pytest_plugin tests/unit/test_document_similarity_ds208.py tests/integration/test_detectors_documents_ds208.py
uv run pytest -p docsentinel.pytest_plugin tests/integration/test_scan.py
uv run docsentinel rules
```

If the spaCy model is not installed, DS302/DS316 **must** remain testable when selected alone with `deep_confirm=True`. Model-dependent DS301 tests may keep their existing honest skip policy.

## Performance and quality gates

- Existing fast analyzer import budget must remain free of standard/deep modules.
- All text samples small enough for normal CI; stress tests explicitly bounded.
- Use the repository's `unit/mock/integration/e2e` taxonomy; no ephemeral fixture-generation substitute for required asset cases.
- No baseline update is accepted as a replacement for resolving a regression in a shipped detector.
