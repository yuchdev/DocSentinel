"""Integration tests for DS103 (unresolvable path-like code span) over text assets in ``tests/assets/ds103``."""

import importlib
import sys
import types
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from docsentinel import models, rules
from tests.asset_helpers import AssetCase

paths: types.ModuleType


@pytest.fixture(scope="module", autouse=True)
def isolate_rule_registration() -> Iterator[None]:
    """Isolate rule registration state for paths detector integration tests."""
    saved_rules = rules.RULES.copy()
    links_module_name = "docsentinel.detectors.links"
    paths_module_name = "docsentinel.detectors.paths"
    saved_links_module = sys.modules.get(links_module_name)
    saved_paths_module = sys.modules.get(paths_module_name)
    global paths
    paths = importlib.import_module(paths_module_name)
    yield
    rules.RULES.clear()
    rules.RULES.update(saved_rules)
    if saved_links_module is None:
        sys.modules.pop(links_module_name, None)
    else:
        sys.modules[links_module_name] = saved_links_module
    if saved_paths_module is None:
        sys.modules.pop(paths_module_name, None)
    else:
        sys.modules[paths_module_name] = saved_paths_module


def _write_document(root: Path, relative_path: str, content: str) -> models.Document:
    """Write generated text to disk and return its Document model."""
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return models.Document(path=relative_path, bytes=path.stat().st_size)


def _symlink_or_skip(link: Path, target: Path):
    """Create symlink or skip if symlinks are not supported."""
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlinks unavailable: {error}")


def test_unresolvable_relative_path_is_flagged(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors paths ds103: verifies unresolvable relative path is flagged.

    Scenario:
        Given test inputs and fixtures for unresolvable relative path is flagged
        When test_unresolvable_relative_path_is_flagged executes the target flow
        Then the expected outcome for unresolvable relative path is flagged is confirmed.

    Boundaries:
        - Focus: unresolvable relative path is flagged
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to unresolvable relative path is flagged
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths ds103
    """
    case = asset_case("ds103", "unresolvable_relative_path")

    assert paths.detect(case.root, case.documents("README.md")) == (
        models.Finding(
            rule="DS103",
            path="README.md",
            message="unresolvable path -> src/missing.py",
            severity="warning",
            line=1,
        ),
    )


def test_leading_slash_resolves_from_root(
    asset_case: Callable[[str, str], AssetCase],
    monkeypatch: pytest.MonkeyPatch,
):
    """
    [Integration] detectors paths ds103: verifies leading slash resolves from root.

    Scenario:
        Given test inputs and fixtures for leading slash resolves from root
        When test_leading_slash_resolves_from_root executes the target flow
        Then the expected outcome for leading slash resolves from root is confirmed.

    Boundaries:
        - Focus: leading slash resolves from root
        - Fixtures/params: asset_case, monkeypatch
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to leading slash resolves from root
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths ds103
    """
    case = asset_case("ds103", "leading_slash_from_scan_root")
    scan_root = case.child("scan-root")
    other_directory = case.path("other")
    other_directory.mkdir()
    monkeypatch.chdir(other_directory)

    assert paths.detect(scan_root.root, scan_root.documents("README.md")) == ()


@pytest.mark.parametrize(
    "case_name",
    (
        "cli_flag_like_span",
        "version_number_like_span",
        "bare_extension_span",
        "span_with_whitespace",
        "shell_prompt_and_variable_like_spans",
    ),
)
def test_non_path_like_spans_are_excluded(asset_case: Callable[[str, str], AssetCase], case_name: str):
    """
    [Integration] detectors paths ds103: verifies non path like spans are excluded.

    Scenario:
        Given test inputs and fixtures for non path like spans are excluded
        When test_non_path_like_spans_are_excluded executes the target flow
        Then the expected outcome for non path like spans are excluded is confirmed.

    Boundaries:
        - Focus: non path like spans are excluded
        - Fixtures/params: asset_case, case_name (parametrized, 5 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to non path like spans are excluded
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths ds103
    """
    case = asset_case("ds103", case_name)

    assert paths.detect(case.root, case.documents("README.md")) == ()


def test_code_span_inside_link_label_is_not_double_reported(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors paths ds103: verifies code span inside link label is not double reported.

    Scenario:
        Given test inputs and fixtures for code span inside link label is not double reported
        When test_code_span_inside_link_label_is_not_double_reported executes the target flow
        Then the expected outcome for code span inside link label is not double reported is confirmed.

    Boundaries:
        - Focus: code span inside link label is not double reported
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to code span inside link label is not double reported
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths ds103
    """
    links = importlib.import_module("docsentinel.detectors.links")
    case = asset_case("ds103", "code_span_inside_link_label")
    documents = case.documents("README.md")

    assert len(links.detect(case.root, documents)) == 1
    assert paths.detect(case.root, documents) == ()


def test_code_span_inside_fenced_block_is_ignored(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors paths ds103: verifies code span inside fenced block is ignored.

    Scenario:
        Given test inputs and fixtures for code span inside fenced block is ignored
        When test_code_span_inside_fenced_block_is_ignored executes the target flow
        Then the expected outcome for code span inside fenced block is ignored is confirmed.

    Boundaries:
        - Focus: code span inside fenced block is ignored
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to code span inside fenced block is ignored
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths ds103
    """
    case = asset_case("ds103", "code_span_inside_fenced_block")

    assert paths.detect(case.root, case.documents("README.md")) == ()


def test_opposite_fence_marker_does_not_close_active_fence(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors paths ds103: verifies opposite fence marker does not close active fence.

    Scenario:
        Given test inputs and fixtures for opposite fence marker does not close active fence
        When test_opposite_fence_marker_does_not_close_active_fence executes the target flow
        Then the expected outcome for opposite fence marker does not close active fence is confirmed.

    Boundaries:
        - Focus: opposite fence marker does not close active fence
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to opposite fence marker does not close active fence
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths ds103
    """
    case = asset_case("ds103", "opposite_fence_marker")

    assert paths.detect(case.root, case.documents("README.md")) == ()


def test_non_markdown_documents_are_not_scanned(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors paths ds103: verifies non markdown documents are not scanned.

    Scenario:
        Given test inputs and fixtures for non markdown documents are not scanned
        When test_non_markdown_documents_are_not_scanned executes the target flow
        Then the expected outcome for non markdown documents are not scanned is confirmed.

    Boundaries:
        - Focus: non markdown documents are not scanned
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to non markdown documents are not scanned
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths ds103
    """
    case = asset_case("ds103", "non_markdown_document")

    assert paths.detect(case.root, case.documents("notes.txt")) == ()


def test_finding_reports_one_based_source_line(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors paths ds103: verifies finding reports one based source line.

    Scenario:
        Given test inputs and fixtures for finding reports one based source line
        When test_finding_reports_one_based_source_line executes the target flow
        Then the expected outcome for finding reports one based source line is confirmed.

    Boundaries:
        - Focus: finding reports one based source line
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to finding reports one based source line
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths ds103
    """
    case = asset_case("ds103", "source_line_number")

    findings = paths.detect(case.root, case.documents("README.md"))

    assert len(findings) == 1
    assert findings[0].line == 3


def test_ds101_and_ds103_report_only_their_own_shared_fixture_spans(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors paths ds103: verifies ds101 and ds103 report only their own shared fixture spans.

    Scenario:
        Given test inputs and fixtures for ds101 and ds103 report only their own shared fixture spans
        When test_ds101_and_ds103_report_only_their_own_shared_fixture_spans executes the target flow
        Then the expected outcome for ds101 and ds103 report only their own shared fixture spans is confirmed.

    Boundaries:
        - Focus: ds101 and ds103 report only their own shared fixture spans
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to ds101 and ds103 report only their own shared fixture spans
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths ds103
    """
    links = importlib.import_module("docsentinel.detectors.links")
    case = asset_case("ds103", "shared_spans_with_ds101")
    documents = case.documents("README.md")

    link_findings = links.detect(case.root, documents)
    path_findings = paths.detect(case.root, documents)

    assert tuple(finding.rule for finding in link_findings) == ("DS101",)
    assert tuple(finding.rule for finding in path_findings) == ("DS103",)
    assert link_findings[0].line == 1
    assert path_findings[0].line == 2


def test_findings_preserve_supplied_document_and_regex_match_order(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors paths ds103: verifies findings preserve supplied document and regex match order.

    Scenario:
        Given test inputs and fixtures for findings preserve supplied document and regex match order
        When test_findings_preserve_supplied_document_and_regex_match_order executes the target flow
        Then the expected outcome for findings preserve supplied document and regex match order is confirmed.

    Boundaries:
        - Focus: findings preserve supplied document and regex match order
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to findings preserve supplied document and regex match order
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths ds103
    """
    case = asset_case("ds103", "findings_preserve_document_order")

    assert paths.detect(case.root, case.documents("z.md", "a.md")) == (
        models.Finding("DS103", "z.md", "unresolvable path -> z-one.md", "warning", 1),
        models.Finding("DS103", "z.md", "unresolvable path -> z-two.md", "warning", 1),
        models.Finding("DS103", "a.md", "unresolvable path -> a-one.md", "warning", 1),
        models.Finding("DS103", "a.md", "unresolvable path -> a-two.md", "warning", 1),
    )


def test_source_lines_are_preserved_after_fence_stripping(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors paths ds103: verifies source lines are preserved after fence stripping.

    Scenario:
        Given test inputs and fixtures for source lines are preserved after fence stripping
        When test_source_lines_are_preserved_after_fence_stripping executes the target flow
        Then the expected outcome for source lines are preserved after fence stripping is confirmed.

    Boundaries:
        - Focus: source lines are preserved after fence stripping
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to source lines are preserved after fence stripping
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths ds103
    """
    case = asset_case("ds103", "source_lines_after_fence_stripping")

    assert paths.detect(case.root, case.documents("README.md")) == (
        models.Finding("DS103", "README.md", "unresolvable path -> src/missing.py", "warning", 6),
    )


def test_relative_path_resolves_from_document_directory(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors paths ds103: verifies relative path resolves from document directory.

    Scenario:
        Given test inputs and fixtures for relative path resolves from document directory
        When test_relative_path_resolves_from_document_directory executes the target flow
        Then the expected outcome for relative path resolves from document directory is confirmed.

    Boundaries:
        - Focus: relative path resolves from document directory
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to relative path resolves from document directory
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths ds103
    """
    case = asset_case("ds103", "relative_path_from_document_directory")

    assert paths.detect(case.root, case.documents("docs/guides/intro.md")) == ()


def test_parent_traversal_outside_root_matches_ds101_resolution(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors paths ds103: verifies parent traversal outside root matches ds101 resolution.

    Scenario:
        Given test inputs and fixtures for parent traversal outside root matches ds101 resolution
        When test_parent_traversal_outside_root_matches_ds101_resolution executes the target flow
        Then the expected outcome for parent traversal outside root matches ds101 resolution is confirmed.

    Boundaries:
        - Focus: parent traversal outside root matches ds101 resolution
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to parent traversal outside root matches ds101 resolution
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths ds103
    """
    case = asset_case("ds103", "parent_traversal_outside_root")
    scan_root = case.child("scan-root")

    assert paths.detect(scan_root.root, scan_root.documents("docs/README.md")) == ()


def test_missing_parent_traversal_is_flagged_without_creating_files(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors paths ds103: verifies missing parent traversal is flagged without creating files.

    Scenario:
        Given test inputs and fixtures for missing parent traversal is flagged without creating files
        When test_missing_parent_traversal_is_flagged_without_creating_files executes the target flow
        Then the expected outcome for missing parent traversal is flagged without creating files is confirmed.

    Boundaries:
        - Focus: missing parent traversal is flagged without creating files
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to missing parent traversal is flagged without creating files
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths ds103
    """
    case = asset_case("ds103", "missing_parent_traversal")
    scan_root = case.child("scan-root")

    assert paths.detect(scan_root.root, scan_root.documents("docs/README.md")) == (
        models.Finding("DS103", "docs/README.md", "unresolvable path -> ../../missing.py", "warning", 1),
    )


@pytest.mark.parametrize(
    ("case_name", "candidate"),
    (
        ("windows_drive_anchored", r"C:\missing.py"),
        ("windows_rooted_backslash", r"\missing.py"),
        ("windows_unc_path", r"\\server\share\missing.py"),
    ),
    ids=("drive-anchored", "rooted-backslash", "unc"),
)
def test_windows_anchored_path_is_flagged_without_filesystem_calls(
    asset_case: Callable[[str, str], AssetCase],
    monkeypatch: pytest.MonkeyPatch,
    case_name: str,
    candidate: str,
):
    """
    [Integration] detectors paths ds103: verifies windows anchored path is flagged without filesystem calls.

    Scenario:
        Given test inputs and fixtures for windows anchored path is flagged without filesystem calls
        When test_windows_anchored_path_is_flagged_without_filesystem_calls executes the target flow
        Then the expected outcome for windows anchored path is flagged without filesystem calls is confirmed.

    Boundaries:
        - Focus: windows anchored path is flagged without filesystem calls
        - Fixtures/params: asset_case, monkeypatch, case_name, candidate (parametrized, 3 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to windows anchored path is flagged without filesystem calls
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths ds103
    """
    case = asset_case("ds103", case_name)
    documents = case.documents("README.md")
    original_resolve = Path.resolve
    original_exists = Path.exists

    def fail_resolve(self: Path, *args: object, **kwargs: object) -> Path:
        """Fail if resolving unexpected path candidate."""
        if candidate in str(self):
            raise AssertionError(f"unexpected resolve call for {self}")
        return original_resolve(self, *args, **kwargs)

    def fail_exists(self: Path) -> bool:
        """Fail if checking existence of unexpected candidate."""
        if candidate in str(self):
            raise AssertionError(f"unexpected exists call for {self}")
        return original_exists(self)

    monkeypatch.setattr(Path, "resolve", fail_resolve)
    monkeypatch.setattr(Path, "exists", fail_exists)

    assert paths.detect(case.root, documents) == (
        models.Finding(
            "DS103",
            "README.md",
            f"unresolvable path -> {candidate}",
            "warning",
            1,
        ),
    )


def test_symlink_to_existing_target_resolves(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors paths ds103: verifies symlink to existing target resolves.

    Scenario:
        Given test inputs and fixtures for symlink to existing target resolves
        When test_symlink_to_existing_target_resolves executes the target flow
        Then the expected outcome for symlink to existing target resolves is confirmed.

    Boundaries:
        - Focus: symlink to existing target resolves
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to symlink to existing target resolves
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths ds103
    """
    case = asset_case("ds103", "symlink_to_existing_target")
    _symlink_or_skip(case.path("alias.md"), case.path("target.md"))

    assert paths.detect(case.root, case.documents("README.md")) == ()


def test_broken_symlink_is_unresolvable(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors paths ds103: verifies broken symlink is unresolvable.

    Scenario:
        Given test inputs and fixtures for broken symlink is unresolvable
        When test_broken_symlink_is_unresolvable executes the target flow
        Then the expected outcome for broken symlink is unresolvable is confirmed.

    Boundaries:
        - Focus: broken symlink is unresolvable
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to broken symlink is unresolvable
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths ds103
    """
    case = asset_case("ds103", "broken_symlink")
    _symlink_or_skip(case.path("alias.md"), case.path("missing.md"))

    assert paths.detect(case.root, case.documents("README.md")) == (
        models.Finding("DS103", "README.md", "unresolvable path -> alias.md", "warning", 1),
    )


@pytest.mark.parametrize(
    "case_name",
    ("hostile_empty_span", "hostile_unterminated_span", "hostile_backticks_only", "hostile_newline_in_span"),
    ids=("empty", "unterminated", "backticks-only", "newline"),
)
def test_hostile_incomplete_span_shapes_are_ignored(asset_case: Callable[[str, str], AssetCase], case_name: str):
    """
    [Integration] detectors paths ds103: verifies hostile incomplete span shapes are ignored.

    Scenario:
        Given test inputs and fixtures for hostile incomplete span shapes are ignored
        When test_hostile_incomplete_span_shapes_are_ignored executes the target flow
        Then the expected outcome for hostile incomplete span shapes are ignored is confirmed.

    Boundaries:
        - Focus: hostile incomplete span shapes are ignored
        - Fixtures/params: asset_case, case_name (parametrized, 4 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to hostile incomplete span shapes are ignored
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths ds103
    """
    case = asset_case("ds103", case_name)

    assert paths.detect(case.root, case.documents("README.md")) == ()


def test_invalid_utf8_read_error_is_propagated(tmp_path: Path):
    """
    [Integration] detectors paths ds103: verifies invalid utf8 read error is propagated.

    Scenario:
        Given test inputs and fixtures for invalid utf8 read error is propagated
        When test_invalid_utf8_read_error_is_propagated executes the target flow
        Then the expected outcome for invalid utf8 read error is propagated is confirmed.

    Boundaries:
        - Focus: invalid utf8 read error is propagated
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to invalid utf8 read error is propagated
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths ds103
    """
    source = tmp_path / "README.md"
    source.write_bytes(b"\xff")
    document = models.Document(path="README.md", bytes=1)

    with pytest.raises(UnicodeDecodeError):
        paths.detect(tmp_path, (document,))


def test_os_read_error_is_propagated(tmp_path: Path):
    """
    [Integration] detectors paths ds103: verifies os read error is propagated.

    Scenario:
        Given test inputs and fixtures for os read error is propagated
        When test_os_read_error_is_propagated executes the target flow
        Then the expected outcome for os read error is propagated is confirmed.

    Boundaries:
        - Focus: os read error is propagated
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to os read error is propagated
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths ds103
    """
    document = models.Document(path="missing.md", bytes=0)

    with pytest.raises(FileNotFoundError):
        paths.detect(tmp_path, (document,))


def test_many_unclosed_code_span_openers_are_handled(tmp_path: Path):
    """
    [Integration] detectors paths ds103: verifies many unclosed code span openers are handled.

    Scenario:
        Given test inputs and fixtures for many unclosed code span openers are handled
        When test_many_unclosed_code_span_openers_are_handled executes the target flow
        Then the expected outcome for many unclosed code span openers are handled is confirmed.

    Boundaries:
        - Focus: many unclosed code span openers are handled
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to many unclosed code span openers are handled
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors paths ds103
    """
    document = _write_document(tmp_path, "README.md", "`\n" * 2_000)

    assert paths.detect(tmp_path, (document,)) == ()
