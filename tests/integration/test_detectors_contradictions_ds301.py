"""Integration tests for DS301 (fact-contradiction candidates) over text assets in ``tests/assets/ds301``.

These run the real spaCy pipeline and are skipped when the deep dependencies or model are not installed.
"""

from collections.abc import Callable

import pytest

from docsentinel import deep_support
from docsentinel.detectors.contradictions import detect
from tests.asset_helpers import AssetCase

pytestmark = pytest.mark.skipif(not deep_support.deep_ready(), reason="deep dependencies and model not installed")


def test_detect_end_to_end_number_contradiction(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors contradictions ds301: verifies detect end to end number contradiction.

    Scenario:
        Given test inputs and fixtures for detect end to end number contradiction
        When test_detect_end_to_end_number_contradiction executes the target flow
        Then the expected outcome for detect end to end number contradiction is confirmed.

    Boundaries:
        - Focus: detect end to end number contradiction
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to detect end to end number contradiction
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors contradictions ds301
    """
    case = asset_case("ds301", "number_contradiction")

    findings = detect(case.root, case.documents("a.md", "b.md"))

    assert len(findings) == 1
    assert findings[0].rule == "DS301"
    assert findings[0].path == "b.md"


def test_detect_no_finding_when_consistent(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors contradictions ds301: verifies detect no finding when consistent.

    Scenario:
        Given test inputs and fixtures for detect no finding when consistent
        When test_detect_no_finding_when_consistent executes the target flow
        Then the expected outcome for detect no finding when consistent is confirmed.

    Boundaries:
        - Focus: detect no finding when consistent
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to detect no finding when consistent
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors contradictions ds301
    """
    case = asset_case("ds301", "consistent_numbers")

    assert detect(case.root, case.documents("a.md", "b.md")) == ()


def test_detect_skips_non_markdown(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors contradictions ds301: verifies detect skips non markdown.

    Scenario:
        Given test inputs and fixtures for detect skips non markdown
        When test_detect_skips_non_markdown executes the target flow
        Then the expected outcome for detect skips non markdown is confirmed.

    Boundaries:
        - Focus: detect skips non markdown
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to detect skips non markdown
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors contradictions ds301
    """
    case = asset_case("ds301", "non_markdown_documents")

    assert detect(case.root, case.documents("a.txt", "b.txt")) == ()
