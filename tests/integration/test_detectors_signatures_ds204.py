"""Integration tests for DS204 (docstring/signature mismatch) over Python sources in ``tests/assets/ds204``."""

from collections.abc import Callable, Iterator

import pytest

pytest.importorskip("docsig")

import docsentinel.detectors.standard as std_pkg
from docsentinel import models, rules
from docsentinel.detectors.standard import signatures
from tests.asset_helpers import AssetCase

if "signatures" not in getattr(std_pkg, "__all__", []):
    rules.RULES.pop("DS204", None)
    rules.ANALYZERS.pop("DS204", None)


@pytest.fixture(autouse=True)
def _ensure_ds204_registered() -> Iterator[None]:
    """Ensure DS204 rule and analyzer are registered for signature test duration."""
    rules.RULES["DS204"] = signatures.DS204
    rules.ANALYZERS["DS204"] = signatures.detect
    yield
    if "signatures" not in getattr(std_pkg, "__all__", []):
        rules.RULES.pop("DS204", None)
        rules.ANALYZERS.pop("DS204", None)


def test_check_file_flags_param_that_does_not_exist(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors signatures ds204: verifies check file flags param that does not exist.

    Scenario:
        Given test inputs and fixtures for check file flags param that does not exist
        When test_check_file_flags_param_that_does_not_exist executes the target flow
        Then the expected outcome for check file flags param that does not exist is confirmed.

    Boundaries:
        - Focus: check file flags param that does not exist
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to check file flags param that does not exist
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors signatures ds204
    """
    case = asset_case("ds204", "param_does_not_exist")

    findings = signatures.check_file(case.root, case.path("src/calc.py"))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule == "DS204"
    assert finding.path == "src/calc.py"
    assert finding.line == 1
    assert finding.severity == "error"
    assert "calculate: SIG202 includes parameters that do not exist" in finding.message


def test_check_file_flags_undocumented_param(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors signatures ds204: verifies check file flags undocumented param.

    Scenario:
        Given test inputs and fixtures for check file flags undocumented param
        When test_check_file_flags_undocumented_param executes the target flow
        Then the expected outcome for check file flags undocumented param is confirmed.

    Boundaries:
        - Focus: check file flags undocumented param
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to check file flags undocumented param
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors signatures ds204
    """
    case = asset_case("ds204", "undocumented_param")

    findings = signatures.check_file(case.root, case.path("src/process.py"))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule == "DS204"
    assert finding.path == "src/process.py"
    assert finding.line == 1
    assert finding.severity == "error"
    assert "process: SIG203" in finding.message


def test_well_documented_function_is_clean(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors signatures ds204: verifies well documented function is clean.

    Scenario:
        Given test inputs and fixtures for well documented function is clean
        When test_well_documented_function_is_clean executes the target flow
        Then the expected outcome for well documented function is clean is confirmed.

    Boundaries:
        - Focus: well documented function is clean
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to well documented function is clean
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors signatures ds204
    """
    case = asset_case("ds204", "well_documented_function")

    assert signatures.check_file(case.root, case.path("src/add.py")) == ()


def test_detect_ignores_markdown_documents(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors signatures ds204: verifies detect ignores markdown documents.

    Scenario:
        Given test inputs and fixtures for detect ignores markdown documents
        When test_detect_ignores_markdown_documents executes the target flow
        Then the expected outcome for detect ignores markdown documents is confirmed.

    Boundaries:
        - Focus: detect ignores markdown documents
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to detect ignores markdown documents
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors signatures ds204
    """
    case = asset_case("ds204", "markdown_documents_ignored")
    unrelated_docs = (models.Document(path="unrelated.md", bytes=100),)

    findings = signatures.detect(case.root, unrelated_docs)

    assert len(findings) == 1
    assert findings[0].rule == "DS204"
    assert findings[0].path == "src/bad.py"


def test_detect_respects_docsig_paths(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors signatures ds204: verifies detect respects docsig paths.

    Scenario:
        Given test inputs and fixtures for detect respects docsig paths
        When test_detect_respects_docsig_paths executes the target flow
        Then the expected outcome for detect respects docsig paths is confirmed.

    Boundaries:
        - Focus: detect respects docsig paths
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to detect respects docsig paths
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors signatures ds204
    """
    case = asset_case("ds204", "docsig_paths_selection")
    case.path("doc_sentinel.toml").write_text('docsig_paths = ["lib"]\n', encoding="utf-8")

    findings = signatures.detect(case.root, ())

    assert len(findings) == 1
    assert findings[0].path == "lib/bad.py"
