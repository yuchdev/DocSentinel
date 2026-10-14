"""Unit tests for DS203 function logic: rule metadata and the lexical/distinctiveness scoring.

Detection over documents is covered by ``tests/integration/test_detectors_low_information_ds203.py``.
"""

import math

import pytest

pytest.importorskip("sklearn")

from docsentinel.detectors.standard import low_information


def test_rule_metadata():
    """
    [Unit] detectors low information: verifies rule metadata.

    Scenario:
        Given test inputs and fixtures for rule metadata
        When test_rule_metadata executes the target flow
        Then the expected outcome for rule metadata is confirmed.

    Boundaries:
        - Focus: rule metadata
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to rule metadata
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors low information
    """
    assert low_information.DS203.code == "DS203"
    assert low_information.DS203.profile == "standard"
    assert low_information.DS203.title == "Low-information content"
    assert low_information.DS203.description == "A paragraph is both lexically thin and non-distinctive."
    assert low_information.DS203.severity == "warning"


def test_type_token_ratio():
    """
    [Unit] detectors low information: verifies type token ratio.

    Scenario:
        Given test inputs and fixtures for type token ratio
        When test_type_token_ratio executes the target flow
        Then the expected outcome for type token ratio is confirmed.

    Boundaries:
        - Focus: type token ratio
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to type token ratio
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors low information
    """
    assert low_information.type_token_ratio("") == 0.0
    assert low_information.type_token_ratio("   ") == 0.0
    assert low_information.type_token_ratio("word word word") == pytest.approx(1 / 3)
    assert low_information.type_token_ratio("Word word WORD") == pytest.approx(1 / 3)
    assert low_information.type_token_ratio("one two three") == pytest.approx(1.0)


def test_information_score_is_geometric_mean():
    # Zero in either signal produces zero
    """
    [Unit] detectors low information: verifies information score is geometric mean.

    Scenario:
        Given test inputs and fixtures for information score is geometric mean
        When test_information_score_is_geometric_mean executes the target flow
        Then the expected outcome for information score is geometric mean is confirmed.

    Boundaries:
        - Focus: information score is geometric mean
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to information score is geometric mean
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors low information
    """
    assert low_information.information_score(0.0, 0.9) == 0.0
    assert low_information.information_score(0.5, 0.0) == 0.0
    assert low_information.information_score(0.0, 0.0) == 0.0
    assert low_information.information_score(-0.1, 0.5) == 0.0
    assert low_information.information_score(0.5, -0.1) == 0.0

    # Reference values scale to 1.0
    assert low_information.information_score(0.5, 0.3) == pytest.approx(1.0)
    assert low_information.information_score(1.0, 1.0) == pytest.approx(1.0)

    # Intermediate value matches sqrt of normalized product
    expected = math.sqrt((0.25 / 0.5) * (0.15 / 0.3))
    assert low_information.information_score(0.25, 0.15) == pytest.approx(expected)

    # Monotonic in TTR
    assert low_information.information_score(0.1, 0.2) < low_information.information_score(0.2, 0.2)
    assert low_information.information_score(0.2, 0.2) < low_information.information_score(0.4, 0.2)

    # Monotonic in max TF-IDF
    assert low_information.information_score(0.3, 0.05) < low_information.information_score(0.3, 0.15)
    assert low_information.information_score(0.3, 0.15) < low_information.information_score(0.3, 0.25)
