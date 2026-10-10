from pathlib import Path

import pytest


@pytest.fixture
def fast_profile_tree(tmp_path: Path) -> tuple[Path, Path]:
    (tmp_path / "dangling.md").write_text("[missing](missing.md)\n", encoding="utf-8")
    (tmp_path / "comment.md").write_text("<!-- stray -->\n", encoding="utf-8")
    (tmp_path / "path.md").write_text("See `nonexistent/path.py`.\n", encoding="utf-8")
    clean_file = tmp_path / "clean.md"
    clean_file.write_text("# Clean\n\nNo structural issues.\n", encoding="utf-8")
    return tmp_path, clean_file


def test_importing_engine_registers_all_fast_analyzers() -> None:
    from docsentinel.engine import ANALYZERS

    assert tuple(sorted(ANALYZERS)) == ("DS101", "DS102", "DS103")


def test_default_fast_scan_reports_all_three_rule_findings(
    fast_profile_tree: tuple[Path, Path],
) -> None:
    from docsentinel.engine import scan

    root, _ = fast_profile_tree

    result = scan(root)

    assert tuple((finding.rule, finding.path) for finding in result.findings) == (
        ("DS101", "dangling.md"),
        ("DS102", "comment.md"),
        ("DS103", "path.md"),
    )


def test_clean_tree_reports_zero_findings_with_evaluated_notice(
    fast_profile_tree: tuple[Path, Path],
) -> None:
    from docsentinel.engine import scan

    _, clean_file = fast_profile_tree

    result = scan(clean_file)

    assert result.findings == ()
    assert result.notice == "3 fast rule(s) evaluated."
    assert "not implemented" not in result.notice
    assert result.enabled_rules == ("DS101", "DS102", "DS103")


def test_ignore_narrows_the_active_set(fast_profile_tree: tuple[Path, Path]) -> None:
    from docsentinel.config import Config
    from docsentinel.engine import scan

    root, _ = fast_profile_tree

    result = scan(root, config=Config(ignore=("DS102",)))

    assert tuple((finding.rule, finding.path) for finding in result.findings) == (
        ("DS101", "dangling.md"),
        ("DS103", "path.md"),
    )
    assert result.enabled_rules == ("DS101", "DS103")


@pytest.mark.parametrize("profile", ("standard", "deep"))
def test_standard_and_deep_profiles_still_report_pending(
    fast_profile_tree: tuple[Path, Path],
    profile: str,
) -> None:
    from docsentinel.config import Config
    from docsentinel.engine import scan

    root, _ = fast_profile_tree

    result = scan(root, config=Config(profile=profile))

    assert result.findings == ()
    assert result.enabled_rules == ()
    assert result.pending == (f"{profile} detectors are not implemented in M0",)
    assert "not implemented" in result.notice


def test_cli_scan_exit_code_reflects_real_findings(
    fast_profile_tree: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    from docsentinel import cli

    root, clean_file = fast_profile_tree

    assert cli.main(["scan", str(root)]) == 1
    capsys.readouterr()
    assert cli.main(["scan", str(clean_file)]) == 0
