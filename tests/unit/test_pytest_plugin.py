from docsentinel.models import ScanResult

pytest_plugins = ["docsentinel.pytest_plugin"]


def test_opt_in_fixture(docsentinel_scan: ScanResult) :
    """
    [Unit] pytest plugin: verifies opt in fixture.

    Scenario:
        Given test inputs and fixtures for opt in fixture
        When test_opt_in_fixture executes the target flow
        Then the expected outcome for opt in fixture is confirmed.

    Boundaries:
        - Focus: opt in fixture
        - Fixtures/params: docsentinel_scan
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to opt in fixture
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by pytest plugin
    """
    assert isinstance(docsentinel_scan, ScanResult)
    assert "README.md" in [document.path for document in docsentinel_scan.documents]
