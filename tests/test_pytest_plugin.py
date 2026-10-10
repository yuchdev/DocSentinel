from docsentinel.models import ScanResult


def test_opt_in_fixture(docsentinel_scan: ScanResult) -> None:
    assert isinstance(docsentinel_scan, ScanResult)
    assert "README.md" in [document.path for document in docsentinel_scan.documents]
