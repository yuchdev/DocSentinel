"""Unit tests for the asset loader that materializes ``tests/assets/dsNNN/<case>/`` trees."""

from pathlib import Path

import pytest

from tests.asset_helpers import ASSETS_ROOT, load_asset_case


def _make_case(assets_root: Path, rule: str, case: str, files: dict[str, bytes]):
    """Create a case directory with the given relative files under a stand-in assets root."""
    for relative, content in files.items():
        target = assets_root / rule / case / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def test_assets_root_points_at_tests_assets_directory():
    """
    [Unit] asset helpers: verifies assets root points at tests assets directory.

    Scenario:
        Given test inputs and fixtures for assets root points at tests assets directory
        When test_assets_root_points_at_tests_assets_directory executes the target flow
        Then the expected outcome for assets root points at tests assets directory is confirmed.

    Boundaries:
        - Focus: assets root points at tests assets directory
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to assets root points at tests assets directory
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by asset helpers
    """
    assert ASSETS_ROOT.name == "assets"
    assert ASSETS_ROOT.parent.name == "tests"
    assert ASSETS_ROOT.is_dir()


def test_load_copies_case_files_byte_for_byte(tmp_path: Path):
    """
    [Unit] asset helpers: verifies load copies case files byte for byte.

    Scenario:
        Given test inputs and fixtures for load copies case files byte for byte
        When test_load_copies_case_files_byte_for_byte executes the target flow
        Then the expected outcome for load copies case files byte for byte is confirmed.

    Boundaries:
        - Focus: load copies case files byte for byte
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to load copies case files byte for byte
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by asset helpers
    """
    assets = tmp_path / "assets"
    _make_case(assets, "ds900", "sample", {"a.md": b"no trailing newline", "docs/b.md": b"\xe2\x9c\x93\r\n"})
    destination = tmp_path / "work"

    case = load_asset_case("ds900", "sample", destination, assets_root=assets)

    assert case.root == destination
    assert (destination / "a.md").read_bytes() == b"no trailing newline"
    assert (destination / "docs" / "b.md").read_bytes() == b"\xe2\x9c\x93\r\n"


def test_load_unknown_case_raises_with_rule_and_case_name(tmp_path: Path):
    """
    [Unit] asset helpers: verifies load unknown case raises with rule and case name.

    Scenario:
        Given test inputs and fixtures for load unknown case raises with rule and case name
        When test_load_unknown_case_raises_with_rule_and_case_name executes the target flow
        Then the expected outcome for load unknown case raises with rule and case name is confirmed.

    Boundaries:
        - Focus: load unknown case raises with rule and case name
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to load unknown case raises with rule and case name
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by asset helpers
    """
    with pytest.raises(FileNotFoundError, match=r"ds900/missing"):
        load_asset_case("ds900", "missing", tmp_path / "work", assets_root=tmp_path / "assets")


def test_loading_several_cases_composes_one_tree(tmp_path: Path):
    """
    [Unit] asset helpers: verifies loading several cases composes one tree.

    Scenario:
        Given test inputs and fixtures for loading several cases composes one tree
        When test_loading_several_cases_composes_one_tree executes the target flow
        Then the expected outcome for loading several cases composes one tree is confirmed.

    Boundaries:
        - Focus: loading several cases composes one tree
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to loading several cases composes one tree
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by asset helpers
    """
    assets = tmp_path / "assets"
    _make_case(assets, "ds900", "first", {"one.md": b"1"})
    _make_case(assets, "ds901", "second", {"two.md": b"2"})
    destination = tmp_path / "work"

    load_asset_case("ds900", "first", destination, assets_root=assets)
    load_asset_case("ds901", "second", destination, assets_root=assets)

    assert sorted(path.name for path in destination.iterdir()) == ["one.md", "two.md"]


def test_document_reports_relative_path_and_size(tmp_path: Path):
    """
    [Unit] asset helpers: verifies document reports relative path and size.

    Scenario:
        Given test inputs and fixtures for document reports relative path and size
        When test_document_reports_relative_path_and_size executes the target flow
        Then the expected outcome for document reports relative path and size is confirmed.

    Boundaries:
        - Focus: document reports relative path and size
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to document reports relative path and size
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by asset helpers
    """
    assets = tmp_path / "assets"
    _make_case(assets, "ds900", "sample", {"docs/guide.md": b"12345"})

    case = load_asset_case("ds900", "sample", tmp_path / "work", assets_root=assets)
    document = case.document("docs/guide.md")

    assert document.path == "docs/guide.md"
    assert document.bytes == 5


def test_documents_without_arguments_lists_every_file_sorted(tmp_path: Path):
    """
    [Unit] asset helpers: verifies documents without arguments lists every file sorted.

    Scenario:
        Given test inputs and fixtures for documents without arguments lists every file sorted
        When test_documents_without_arguments_lists_every_file_sorted executes the target flow
        Then the expected outcome for documents without arguments lists every file sorted is confirmed.

    Boundaries:
        - Focus: documents without arguments lists every file sorted
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to documents without arguments lists every file sorted
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by asset helpers
    """
    assets = tmp_path / "assets"
    _make_case(assets, "ds900", "sample", {"z.md": b"z", "a.md": b"a", "docs/m.md": b"m"})

    case = load_asset_case("ds900", "sample", tmp_path / "work", assets_root=assets)

    assert [document.path for document in case.documents()] == ["a.md", "docs/m.md", "z.md"]


def test_documents_with_arguments_preserves_requested_order(tmp_path: Path):
    """
    [Unit] asset helpers: verifies documents with arguments preserves requested order.

    Scenario:
        Given test inputs and fixtures for documents with arguments preserves requested order
        When test_documents_with_arguments_preserves_requested_order executes the target flow
        Then the expected outcome for documents with arguments preserves requested order is confirmed.

    Boundaries:
        - Focus: documents with arguments preserves requested order
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to documents with arguments preserves requested order
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by asset helpers
    """
    assets = tmp_path / "assets"
    _make_case(assets, "ds900", "sample", {"z.md": b"z", "a.md": b"a"})

    case = load_asset_case("ds900", "sample", tmp_path / "work", assets_root=assets)

    assert [document.path for document in case.documents("z.md", "a.md")] == ["z.md", "a.md"]


def test_child_roots_a_nested_scan_directory(tmp_path: Path):
    """
    [Unit] asset helpers: verifies child roots a nested scan directory.

    Scenario:
        Given test inputs and fixtures for child roots a nested scan directory
        When test_child_roots_a_nested_scan_directory executes the target flow
        Then the expected outcome for child roots a nested scan directory is confirmed.

    Boundaries:
        - Focus: child roots a nested scan directory
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to child roots a nested scan directory
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by asset helpers
    """
    assets = tmp_path / "assets"
    _make_case(assets, "ds900", "nested", {"scan-root/README.md": b"hi", "outside.md": b"out"})

    case = load_asset_case("ds900", "nested", tmp_path / "work", assets_root=assets)
    scan_root = case.child("scan-root")

    assert scan_root.root == case.root / "scan-root"
    assert [document.path for document in scan_root.documents()] == ["README.md"]
    assert scan_root.read_text("README.md") == "hi"
