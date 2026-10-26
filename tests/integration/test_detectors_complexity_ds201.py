"""Integration tests for DS201 (high text complexity) over text assets in ``tests/assets/ds201``."""

from collections.abc import Callable

import pytest

pytest.importorskip("textstat")

from docsentinel.detectors.standard import complexity
from tests.asset_helpers import AssetCase


def test_compute_grade_level_simple_text_below_threshold(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors complexity ds201: verifies compute grade level simple text below threshold.

    Scenario:
        Given test inputs and fixtures for compute grade level simple text below threshold
        When test_compute_grade_level_simple_text_below_threshold executes the target flow
        Then the expected outcome for compute grade level simple text below threshold is confirmed.

    Boundaries:
        - Focus: compute grade level simple text below threshold
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to compute grade level simple text below threshold
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors complexity ds201
    """
    case = asset_case("ds201", "clean_document")

    assert complexity.compute_grade_level(case.read_text("clean.md")) < 14.0


def test_compute_grade_level_dense_academic_text_above_threshold(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors complexity ds201: verifies compute grade level dense academic text above threshold.

    Scenario:
        Given test inputs and fixtures for compute grade level dense academic text above threshold
        When test_compute_grade_level_dense_academic_text_above_threshold executes the target flow
        Then the expected outcome for compute grade level dense academic text above threshold is confirmed.

    Boundaries:
        - Focus: compute grade level dense academic text above threshold
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to compute grade level dense academic text above threshold
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors complexity ds201
    """
    case = asset_case("ds201", "dense_document")

    assert complexity.compute_grade_level(case.read_text("dense.md")) > 14.0


def test_short_document_skipped(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors complexity ds201: verifies short document skipped.

    Scenario:
        Given test inputs and fixtures for short document skipped
        When test_short_document_skipped executes the target flow
        Then the expected outcome for short document skipped is confirmed.

    Boundaries:
        - Focus: short document skipped
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to short document skipped
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors complexity ds201
    """
    case = asset_case("ds201", "short_dense_document")

    findings = complexity.check_document(case.root, case.document("short.md"), max_grade=14.0)

    assert findings == ()


def test_check_document_emits_warning_finding_on_breach(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors complexity ds201: verifies check document emits warning finding on breach.

    Scenario:
        Given test inputs and fixtures for check document emits warning finding on breach
        When test_check_document_emits_warning_finding_on_breach executes the target flow
        Then the expected outcome for check document emits warning finding on breach is confirmed.

    Boundaries:
        - Focus: check document emits warning finding on breach
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to check document emits warning finding on breach
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors complexity ds201
    """
    case = asset_case("ds201", "dense_document")

    findings = complexity.check_document(case.root, case.document("dense.md"), max_grade=14.0)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule == "DS201"
    assert finding.path == "dense.md"
    assert finding.severity == "warning"
    assert "Readability grade level" in finding.message
    assert "exceeds threshold 14.0" in finding.message


def test_check_document_clean_below_threshold(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors complexity ds201: verifies check document clean below threshold.

    Scenario:
        Given test inputs and fixtures for check document clean below threshold
        When test_check_document_clean_below_threshold executes the target flow
        Then the expected outcome for check document clean below threshold is confirmed.

    Boundaries:
        - Focus: check document clean below threshold
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to check document clean below threshold
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors complexity ds201
    """
    case = asset_case("ds201", "clean_document")

    findings = complexity.check_document(case.root, case.document("clean.md"), max_grade=14.0)

    assert findings == ()


def test_detect_runs_over_all_documents(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors complexity ds201: verifies detect runs over all documents.

    Scenario:
        Given test inputs and fixtures for detect runs over all documents
        When test_detect_runs_over_all_documents executes the target flow
        Then the expected outcome for detect runs over all documents is confirmed.

    Boundaries:
        - Focus: detect runs over all documents
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to detect runs over all documents
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors complexity ds201
    """
    case = asset_case("ds201", "mixed_documents")

    findings = complexity.detect(case.root, case.documents("dense.md", "clean.md", "dense.txt"))

    assert len(findings) == 1
    assert findings[0].path == "dense.md"
    assert findings[0].rule == "DS201"


def test_detect_respects_custom_threshold_from_config(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors complexity ds201: verifies detect respects custom threshold from config.

    Scenario:
        Given test inputs and fixtures for detect respects custom threshold from config
        When test_detect_respects_custom_threshold_from_config executes the target flow
        Then the expected outcome for detect respects custom threshold from config is confirmed.

    Boundaries:
        - Focus: detect respects custom threshold from config
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to detect respects custom threshold from config
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors complexity ds201
    """
    case = asset_case("ds201", "dense_document")
    documents = case.documents("dense.md")

    case.path("docsentinel.toml").write_text("max_grade_level = 50.0\n", encoding="utf-8")
    assert complexity.detect(case.root, documents) == ()

    case.path("docsentinel.toml").write_text("max_grade_level = 10.0\n", encoding="utf-8")
    findings = complexity.detect(case.root, documents)
    assert len(findings) == 1
    assert "exceeds threshold 10.0" in findings[0].message
