# Task 03 — Integration, CLI and regression tests for `DS207`

**Story:** [Story 06.0](/docs/roadmap/0004-deepening-test-cases/06.0-repeated-document-sections/README.md)

## Test files to add

- `tests/integration/test_detectors_sections_ds207.py` — mandatory asset-based integration coverage, named with rule-code suffix.
- `tests/unit/test_section_similarity_ds207.py` — pure parsing/normalization algorithm tests; miniature strings permitted *only here*.
- `tests/integration/test_scan.py` and cross-profile end-to-end suites — additive tests only where needed; do not destabilize existing profile coverage.

## Golden path test shape

```python
from collections.abc import Callable
from tests.asset_helpers import AssetCase


def test_ds207_asset_case(asset_case: Callable[[str, str], AssetCase]) -> None:
    case = asset_case("ds207", "identical_multisection_text")
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

- [ ] Write integration assertions for path, heading, line and earlier-section provenance.
- [ ] Test short/single-paragraph/code-only exclusion and threshold inclusivity.
- [ ] Assert deterministic ordering on a,b,c and repeated scans.
- [ ] Check absent standard extras give actionable CLI exit 2.

- [ ] A parametrized fixture test references **each** slug from `02-markdown-asset-cases.md` by name. No unreferenced directories.
- [ ] Three-plus pass fixtures assert no `DS207` findings, three-plus fail fixtures assert correct `DS207` findings, and every special edge is checked.
- [ ] Runtime `Config` overrides propagate to detector (not silently ignored due to reading a disk config).
- [ ] Registry includes the correct rule/profile/severity; `select=("DS207",)` executes only the intended rule within exact profile; `ignore` wins.
- [ ] Output is sorted deterministically by normalized path and source location; duplicate candidate pairs are suppressed as specified.
- [ ] JSON report includes `DS207` and meaningful evidence; line and severity are checked. CLI exit behavior follows profile policy.
- [ ] Baseline creation/suppression is demonstrated; a new finding not in baseline remains visible.
- [ ] Any missing capability returns actionable pending/error rather than a false clean report.
- [ ] Existing DS101–DS301 behavior and tests are unchanged.

## Targeted commands

```bash
uv sync --extra test --extra standard --extra deep
uv run pytest -p docsentinel.pytest_plugin tests/unit/test_section_similarity_ds207.py tests/integration/test_detectors_sections_ds207.py
uv run pytest -p docsentinel.pytest_plugin tests/integration/test_scan.py
uv run docsentinel rules
```

If the spaCy model is not installed, DS302/DS316 **must** remain testable when selected alone with `deep_confirm=True`. Model-dependent DS301 tests may keep their existing honest skip policy.

## Performance and quality gates

- Existing fast analyzer import budget must remain free of standard/deep modules.
- All text samples small enough for normal CI; stress tests explicitly bounded.
- Use the repository's `unit/mock/integration/e2e` taxonomy; no ephemeral fixture-generation substitute for required asset cases.
- No baseline update is accepted as a replacement for resolving a regression in a shipped detector.
