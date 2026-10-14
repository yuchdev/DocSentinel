"""Integration tests for DS101 (dangling link or anchor) over text assets in ``tests/assets/ds101``."""

import importlib
import types
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from docsentinel import models, rules
from tests.asset_helpers import AssetCase

links: types.ModuleType


@pytest.fixture(scope="module", autouse=True)
def isolate_rule_registration() -> Iterator[None]:
    """Isolate rule registrations for the links detector integration suite."""
    saved_rules = rules.RULES.copy()
    global links
    links = importlib.import_module("docsentinel.detectors.links")
    yield
    rules.RULES.clear()
    rules.RULES.update(saved_rules)


def _symlink_or_skip(link: Path, target: Path):
    """Create symlink or skip if symlinks are not supported on filesystem."""
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlinks unavailable: {error}")


def test_dangling_file_link_is_flagged(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors links ds101: verifies dangling file link is flagged.

    Scenario:
        Given test inputs and fixtures for dangling file link is flagged
        When test_dangling_file_link_is_flagged executes the target flow
        Then the expected outcome for dangling file link is flagged is confirmed.

    Boundaries:
        - Focus: dangling file link is flagged
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to dangling file link is flagged
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links ds101
    """
    case = asset_case("ds101", "dangling_file_link")

    assert links.detect(case.root, case.documents("README.md")) == (
        models.Finding(
            rule="DS101",
            path="README.md",
            message="dangling link -> missing.md",
            severity="error",
            line=1,
        ),
    )


def test_protocol_relative_link_is_skipped(tmp_path: Path):
    """
    [Integration] detectors links ds101: verifies protocol relative link is skipped.

    Scenario:
        Given test inputs and fixtures for protocol relative link is skipped
        When test_protocol_relative_link_is_skipped executes the target flow
        Then the expected outcome for protocol relative link is skipped is confirmed.

    Boundaries:
        - Focus: protocol relative link is skipped
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to protocol relative link is skipped
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links ds101
    """
    source = tmp_path / "README.md"
    source.write_text("[Example](//example.com/docs)\n", encoding="utf-8")

    assert links.detect(tmp_path, (models.Document("README.md", source.stat().st_size),)) == ()


def test_missing_file_with_anchor_reports_only_dangling_link(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors links ds101: verifies missing file with anchor reports only dangling link.

    Scenario:
        Given test inputs and fixtures for missing file with anchor reports only dangling link
        When test_missing_file_with_anchor_reports_only_dangling_link executes the target flow
        Then the expected outcome for missing file with anchor reports only dangling link is confirmed.

    Boundaries:
        - Focus: missing file with anchor reports only dangling link
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to missing file with anchor reports only dangling link
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links ds101
    """
    case = asset_case("ds101", "missing_file_with_anchor")

    findings = links.detect(case.root, case.documents("README.md"))

    assert len(findings) == 1
    assert findings[0].message == "dangling link -> missing.md#nope"


@pytest.mark.parametrize("case_name", ("valid_link_to_file", "valid_link_to_heading"))
def test_valid_link_produces_no_finding(asset_case: Callable[[str, str], AssetCase], case_name: str):
    """
    [Integration] detectors links ds101: verifies valid link produces no finding.

    Scenario:
        Given test inputs and fixtures for valid link produces no finding
        When test_valid_link_produces_no_finding executes the target flow
        Then the expected outcome for valid link produces no finding is confirmed.

    Boundaries:
        - Focus: valid link produces no finding
        - Fixtures/params: asset_case, case_name (parametrized, 2 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to valid link produces no finding
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links ds101
    """
    case = asset_case("ds101", case_name)

    assert links.detect(case.root, case.documents("README.md")) == ()


def test_missing_anchor_in_same_file_is_flagged(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors links ds101: verifies missing anchor in same file is flagged.

    Scenario:
        Given test inputs and fixtures for missing anchor in same file is flagged
        When test_missing_anchor_in_same_file_is_flagged executes the target flow
        Then the expected outcome for missing anchor in same file is flagged is confirmed.

    Boundaries:
        - Focus: missing anchor in same file is flagged
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to missing anchor in same file is flagged
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links ds101
    """
    case = asset_case("ds101", "missing_anchor_same_file")

    assert links.detect(case.root, case.documents("README.md")) == (
        models.Finding(
            rule="DS101",
            path="README.md",
            message="missing anchor '#nope' in this file",
            severity="error",
            line=3,
        ),
    )


def test_missing_anchor_in_other_file_is_flagged(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors links ds101: verifies missing anchor in other file is flagged.

    Scenario:
        Given test inputs and fixtures for missing anchor in other file is flagged
        When test_missing_anchor_in_other_file_is_flagged executes the target flow
        Then the expected outcome for missing anchor in other file is flagged is confirmed.

    Boundaries:
        - Focus: missing anchor in other file is flagged
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to missing anchor in other file is flagged
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links ds101
    """
    case = asset_case("ds101", "missing_anchor_other_file")

    assert links.detect(case.root, case.documents("README.md")) == (
        models.Finding(
            rule="DS101",
            path="README.md",
            message="missing anchor '#nope' in other.md",
            severity="error",
            line=1,
        ),
    )


def test_duplicate_headings_get_suffixed_anchors(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors links ds101: verifies duplicate headings get suffixed anchors.

    Scenario:
        Given test inputs and fixtures for duplicate headings get suffixed anchors
        When test_duplicate_headings_get_suffixed_anchors executes the target flow
        Then the expected outcome for duplicate headings get suffixed anchors is confirmed.

    Boundaries:
        - Focus: duplicate headings get suffixed anchors
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to duplicate headings get suffixed anchors
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links ds101
    """
    case = asset_case("ds101", "duplicate_headings_suffixed_anchors")

    assert links.detect(case.root, case.documents("README.md")) == ()


@pytest.mark.parametrize("case_name", ("html_anchor_id", "html_anchor_name"))
def test_html_anchor_tag_is_recognized(asset_case: Callable[[str, str], AssetCase], case_name: str):
    """
    [Integration] detectors links ds101: verifies html anchor tag is recognized.

    Scenario:
        Given test inputs and fixtures for html anchor tag is recognized
        When test_html_anchor_tag_is_recognized executes the target flow
        Then the expected outcome for html anchor tag is recognized is confirmed.

    Boundaries:
        - Focus: html anchor tag is recognized
        - Fixtures/params: asset_case, case_name (parametrized, 2 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to html anchor tag is recognized
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links ds101
    """
    case = asset_case("ds101", case_name)

    assert links.detect(case.root, case.documents("README.md")) == ()


def test_links_inside_fenced_code_are_ignored(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors links ds101: verifies links inside fenced code are ignored.

    Scenario:
        Given test inputs and fixtures for links inside fenced code are ignored
        When test_links_inside_fenced_code_are_ignored executes the target flow
        Then the expected outcome for links inside fenced code are ignored is confirmed.

    Boundaries:
        - Focus: links inside fenced code are ignored
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to links inside fenced code are ignored
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links ds101
    """
    case = asset_case("ds101", "links_inside_fenced_code")

    assert links.detect(case.root, case.documents("README.md")) == ()


def test_headings_inside_fenced_code_are_ignored(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors links ds101: verifies headings inside fenced code are ignored.

    Scenario:
        Given test inputs and fixtures for headings inside fenced code are ignored
        When test_headings_inside_fenced_code_are_ignored executes the target flow
        Then the expected outcome for headings inside fenced code are ignored is confirmed.

    Boundaries:
        - Focus: headings inside fenced code are ignored
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to headings inside fenced code are ignored
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links ds101
    """
    case = asset_case("ds101", "headings_inside_fenced_code")

    findings = links.detect(case.root, case.documents("README.md"))

    assert len(findings) == 1
    assert findings[0].message == "missing anchor '#not-a-heading' in this file"


def test_links_inside_inline_code_span_are_ignored(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors links ds101: verifies links inside inline code span are ignored.

    Scenario:
        Given test inputs and fixtures for links inside inline code span are ignored
        When test_links_inside_inline_code_span_are_ignored executes the target flow
        Then the expected outcome for links inside inline code span are ignored is confirmed.

    Boundaries:
        - Focus: links inside inline code span are ignored
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to links inside inline code span are ignored
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links ds101
    """
    case = asset_case("ds101", "link_inside_inline_code_span")

    assert links.detect(case.root, case.documents("README.md")) == ()


def test_asymmetric_backtick_stripping_exposes_one_dangling_link(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors links ds101: verifies asymmetric backtick stripping exposes one dangling link.

    Scenario:
        Given test inputs and fixtures for asymmetric backtick stripping exposes one dangling link
        When test_asymmetric_backtick_stripping_exposes_one_dangling_link executes the target flow
        Then the expected outcome for asymmetric backtick stripping exposes one dangling link is confirmed.

    Boundaries:
        - Focus: asymmetric backtick stripping exposes one dangling link
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to asymmetric backtick stripping exposes one dangling link
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links ds101
    """
    case = asset_case("ds101", "asymmetric_backtick_stripping")

    assert links.detect(case.root, case.documents("README.md")) == (
        models.Finding(
            rule="DS101",
            path="README.md",
            message="dangling link -> bad.md",
            severity="error",
            line=1,
        ),
    )


def test_external_and_template_and_glob_targets_are_skipped(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors links ds101: verifies external and template and glob targets are skipped.

    Scenario:
        Given test inputs and fixtures for external and template and glob targets are skipped
        When test_external_and_template_and_glob_targets_are_skipped executes the target flow
        Then the expected outcome for external and template and glob targets are skipped is confirmed.

    Boundaries:
        - Focus: external and template and glob targets are skipped
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to external and template and glob targets are skipped
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links ds101
    """
    case = asset_case("ds101", "skipped_targets")

    assert links.detect(case.root, case.documents("README.md")) == ()


def test_leading_slash_resolves_from_scan_root_not_cwd(
    asset_case: Callable[[str, str], AssetCase],
    monkeypatch: pytest.MonkeyPatch,
):
    """
    [Integration] detectors links ds101: verifies leading slash resolves from scan root not cwd.

    Scenario:
        Given test inputs and fixtures for leading slash resolves from scan root not cwd
        When test_leading_slash_resolves_from_scan_root_not_cwd executes the target flow
        Then the expected outcome for leading slash resolves from scan root not cwd is confirmed.

    Boundaries:
        - Focus: leading slash resolves from scan root not cwd
        - Fixtures/params: asset_case, monkeypatch
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to leading slash resolves from scan root not cwd
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links ds101
    """
    case = asset_case("ds101", "leading_slash_from_scan_root")
    scan_root = case.child("scan-root")
    different_cwd = case.path("different-cwd")
    different_cwd.mkdir()
    monkeypatch.chdir(different_cwd)

    assert links.detect(scan_root.root, scan_root.documents("README.md")) == ()


def test_nested_relative_link_resolves_from_document_directory(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors links ds101: verifies nested relative link resolves from document directory.

    Scenario:
        Given test inputs and fixtures for nested relative link resolves from document directory
        When test_nested_relative_link_resolves_from_document_directory executes the target flow
        Then the expected outcome for nested relative link resolves from document directory is confirmed.

    Boundaries:
        - Focus: nested relative link resolves from document directory
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to nested relative link resolves from document directory
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links ds101
    """
    case = asset_case("ds101", "nested_relative_link")

    assert links.detect(case.root, case.documents("docs/guides/intro.md")) == ()


def test_parent_traversal_outside_root_matches_source_script(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors links ds101: verifies parent traversal outside root matches source script.

    Scenario:
        Given test inputs and fixtures for parent traversal outside root matches source script
        When test_parent_traversal_outside_root_matches_source_script executes the target flow
        Then the expected outcome for parent traversal outside root matches source script is confirmed.

    Boundaries:
        - Focus: parent traversal outside root matches source script
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to parent traversal outside root matches source script
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links ds101
    """
    case = asset_case("ds101", "parent_traversal_outside_root")
    scan_root = case.child("scan-root")

    assert links.detect(scan_root.root, scan_root.documents("docs/README.md")) == ()


def test_symlink_to_existing_target_resolves(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors links ds101: verifies symlink to existing target resolves.

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
        - Recent changes in code paths exercised by detectors links ds101
    """
    case = asset_case("ds101", "symlink_to_existing_target")
    _symlink_or_skip(case.path("alias.md"), case.path("target.md"))

    assert links.detect(case.root, case.documents("README.md")) == ()


def test_broken_symlink_is_dangling(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors links ds101: verifies broken symlink is dangling.

    Scenario:
        Given test inputs and fixtures for broken symlink is dangling
        When test_broken_symlink_is_dangling executes the target flow
        Then the expected outcome for broken symlink is dangling is confirmed.

    Boundaries:
        - Focus: broken symlink is dangling
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to broken symlink is dangling
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links ds101
    """
    case = asset_case("ds101", "broken_symlink")
    _symlink_or_skip(case.path("alias.md"), case.path("missing.md"))

    assert links.detect(case.root, case.documents("README.md")) == (
        models.Finding(
            rule="DS101",
            path="README.md",
            message="dangling link -> alias.md",
            severity="error",
            line=1,
        ),
    )


def test_non_markdown_documents_are_not_scanned(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors links ds101: verifies non markdown documents are not scanned.

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
        - Recent changes in code paths exercised by detectors links ds101
    """
    case = asset_case("ds101", "non_markdown_document")

    assert links.detect(case.root, case.documents("notes.txt")) == ()


def test_finding_reports_one_based_source_line(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors links ds101: verifies finding reports one based source line.

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
        - Recent changes in code paths exercised by detectors links ds101
    """
    case = asset_case("ds101", "source_line_number")

    findings = links.detect(case.root, case.documents("README.md"))

    assert len(findings) == 1
    assert findings[0].line == 3


def test_invalid_utf8_read_error_is_propagated(tmp_path: Path):
    """
    [Integration] detectors links ds101: verifies invalid utf8 read error is propagated.

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
        - Recent changes in code paths exercised by detectors links ds101
    """
    source = tmp_path / "README.md"
    source.write_bytes(b"\xff")
    document = models.Document(path="README.md", bytes=1)

    with pytest.raises(UnicodeDecodeError):
        links.detect(tmp_path, (document,))


def test_invalid_utf8_target_heading_read_is_propagated(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors links ds101: verifies invalid utf8 target heading read is propagated.

    Scenario:
        Given test inputs and fixtures for invalid utf8 target heading read is propagated
        When test_invalid_utf8_target_heading_read_is_propagated executes the target flow
        Then the expected outcome for invalid utf8 target heading read is propagated is confirmed.

    Boundaries:
        - Focus: invalid utf8 target heading read is propagated
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to invalid utf8 target heading read is propagated
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links ds101
    """
    case = asset_case("ds101", "invalid_utf8_target_heading")
    case.path("target.md").write_bytes(b"\xff")

    with pytest.raises(UnicodeDecodeError):
        links.detect(case.root, case.documents("README.md"))


def test_os_read_error_is_propagated(tmp_path: Path):
    """
    [Integration] detectors links ds101: verifies os read error is propagated.

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
        - Recent changes in code paths exercised by detectors links ds101
    """
    document = models.Document(path="missing.md", bytes=0)

    with pytest.raises(FileNotFoundError):
        links.detect(tmp_path, (document,))


@pytest.mark.parametrize(
    "error_type",
    (OSError, PermissionError),
    ids=("os-error", "permission-error"),
)
def test_target_open_error_is_propagated(
    asset_case: Callable[[str, str], AssetCase],
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[OSError],
):
    """
    [Integration] detectors links ds101: verifies target open error is propagated.

    Scenario:
        Given test inputs and fixtures for target open error is propagated
        When test_target_open_error_is_propagated executes the target flow
        Then the expected outcome for target open error is propagated is confirmed.

    Boundaries:
        - Focus: target open error is propagated
        - Fixtures/params: asset_case, monkeypatch, error_type (parametrized, 2 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to target open error is propagated
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links ds101
    """
    case = asset_case("ds101", "target_read_error")
    target = case.path("target.md")
    original_read_lines = links._read_lines

    def fail_target_read(path: Path) -> list[str]:
        """Simulate read failure when accessing target path."""
        if path == target:
            raise error_type("target read failed")
        return original_read_lines(path)

    monkeypatch.setattr(links, "_read_lines", fail_target_read)

    with pytest.raises(error_type, match="target read failed"):
        links.detect(case.root, case.documents("README.md"))


def test_findings_preserve_supplied_document_and_link_order(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors links ds101: verifies findings preserve supplied document and link order.

    Scenario:
        Given test inputs and fixtures for findings preserve supplied document and link order
        When test_findings_preserve_supplied_document_and_link_order executes the target flow
        Then the expected outcome for findings preserve supplied document and link order is confirmed.

    Boundaries:
        - Focus: findings preserve supplied document and link order
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to findings preserve supplied document and link order
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links ds101
    """
    case = asset_case("ds101", "findings_preserve_document_order")

    assert links.detect(case.root, case.documents("z.md", "a.md")) == (
        models.Finding("DS101", "z.md", "dangling link -> z-one.md", "error", 1),
        models.Finding("DS101", "z.md", "dangling link -> z-two.md", "error", 1),
        models.Finding("DS101", "a.md", "dangling link -> a-one.md", "error", 1),
        models.Finding("DS101", "a.md", "dangling link -> a-two.md", "error", 1),
    )


def test_real_world_document_has_zero_findings():
    """
    [Integration] detectors links ds101: verifies real world document has zero findings.

    Scenario:
        Given test inputs and fixtures for real world document has zero findings
        When test_real_world_document_has_zero_findings executes the target flow
        Then the expected outcome for real world document has zero findings is confirmed.

    Boundaries:
        - Focus: real world document has zero findings
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to real world document has zero findings
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors links ds101
    """
    root = Path(__file__).resolve().parents[2]
    relative_path = "docs/adr/0001-config-loading-via-layered-settings.md"
    path = root / relative_path
    document = models.Document(path=relative_path, bytes=path.stat().st_size)

    findings = links.detect(root, (document,))

    assert len(findings) == 0
