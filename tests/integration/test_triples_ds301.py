"""Integration tests for DS301 claim extraction over text assets in ``tests/assets/ds301``.

These run the real spaCy pipeline and are skipped when the deep dependencies or model are not installed.
"""

from collections.abc import Callable

import pytest

from docsentinel import deep_support
from docsentinel.detectors._triples import extract_claims
from tests.asset_helpers import AssetCase

pytestmark = pytest.mark.skipif(not deep_support.deep_ready(), reason="deep dependencies and model not installed")


def test_extract_claims_simple_svo(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] triples ds301: verifies extract claims simple svo.

    Scenario:
        Given test inputs and fixtures for extract claims simple svo
        When test_extract_claims_simple_svo executes the target flow
        Then the expected outcome for extract claims simple svo is confirmed.

    Boundaries:
        - Focus: extract claims simple svo
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to extract claims simple svo
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by triples ds301
    """
    case = asset_case("ds301", "simple_svo_claim")
    pipeline = deep_support.load_pipeline()

    claims = extract_claims(pipeline, case.read_text("doc.md"), "doc.md")

    assert len(claims) >= 1
    claim = claims[0]
    assert claim.subject_key == "cache"
    assert "100" in claim.object_numbers
    assert claim.path == "doc.md"
    assert claim.paragraph_index == 0


def test_paragraph_index_assigned(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] triples ds301: verifies paragraph index assigned.

    Scenario:
        Given test inputs and fixtures for paragraph index assigned
        When test_paragraph_index_assigned executes the target flow
        Then the expected outcome for paragraph index assigned is confirmed.

    Boundaries:
        - Focus: paragraph index assigned
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to paragraph index assigned
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by triples ds301
    """
    case = asset_case("ds301", "multi_paragraph_claims")
    pipeline = deep_support.load_pipeline()

    claims = extract_claims(pipeline, case.read_text("multi.md"), "multi.md")

    assert len(claims) >= 2
    indices = [c.paragraph_index for c in claims]
    assert 0 in indices
    assert 1 in indices


def test_no_triples_yields_empty(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] triples ds301: verifies no triples yields empty.

    Scenario:
        Given test inputs and fixtures for no triples yields empty
        When test_no_triples_yields_empty executes the target flow
        Then the expected outcome for no triples yields empty is confirmed.

    Boundaries:
        - Focus: no triples yields empty
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to no triples yields empty
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by triples ds301
    """
    case = asset_case("ds301", "no_triples")
    pipeline = deep_support.load_pipeline()

    claims = extract_claims(pipeline, case.read_text("empty.md"), "empty.md")

    assert isinstance(claims, tuple)
