import json
import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Optional

import pytest

from docsentinel import Config, ConfigError, cli, load_config, scan
from docsentinel.cli import _exit_code, main
from docsentinel.engine import ANALYZERS
from docsentinel.errors import ExtraNotInstalledError
from docsentinel.models import Document, Finding, ScanResult
from docsentinel.reporting import render
from docsentinel.rules import RULES, Rule, register_rule


@pytest.fixture
def fake_fast_analyzer() -> Iterator[list[tuple[Path, tuple[Document, ...]]]]:
    calls: list[tuple[Path, tuple[Document, ...]]] = []
    rule = register_rule(Rule("DS199", "fast", "Fake fast rule", "Exercises selection."))

    def analyzer(root: Path, documents: tuple[Document, ...]) -> tuple[Finding, ...]:
        calls.append((root, documents))
        return ()

    ANALYZERS[rule.code] = analyzer
    try:
        yield calls
    finally:
        RULES.pop(rule.code, None)
        ANALYZERS.pop(rule.code, None)


@pytest.fixture
def captured_cli_configs(monkeypatch: pytest.MonkeyPatch) -> list[Config]:
    configs: list[Config] = []

    def fake_scan(root: str, *, config: Config) -> ScanResult:
        configs.append(config)
        return ScanResult(
            profile=config.profile,
            documents=(),
            findings=(),
            enabled_rules=(),
            pending=(),
        )

    monkeypatch.setattr(cli, "scan", fake_scan)
    return configs


def test_empty_scan_is_inventory_not_detection(tmp_path: Path) -> None:
    result = scan(tmp_path, config=Config(profile="deep"))
    assert result.documents == ()
    assert result.findings == ()
    assert result.enabled_rules == ()
    assert "not implemented" in result.notice
    assert json.loads(render(result, "json"))["enabled_rules"] == []


def test_scan_runs_analyzer_for_active_profile(
    tmp_path: Path,
    fake_fast_analyzer: list[tuple[Path, tuple[Document, ...]]],
) -> None:
    scan(tmp_path, config=Config(profile="fast"))
    assert len(fake_fast_analyzer) == 1

    fake_fast_analyzer.clear()
    scan(tmp_path, config=Config(profile="standard"))
    assert fake_fast_analyzer == []


def test_scan_respects_select(
    tmp_path: Path,
    fake_fast_analyzer: list[tuple[Path, tuple[Document, ...]]],
) -> None:
    scan(tmp_path, config=Config(select=("DS1",)))
    assert len(fake_fast_analyzer) == 1

    fake_fast_analyzer.clear()
    scan(tmp_path, config=Config(select=("DS9",)))
    assert fake_fast_analyzer == []


def test_scan_respects_ignore_over_select(
    tmp_path: Path,
    fake_fast_analyzer: list[tuple[Path, tuple[Document, ...]]],
) -> None:
    scan(tmp_path, config=Config(select=("DS1",), ignore=("DS1",)))
    assert fake_fast_analyzer == []


def test_scan_notice_reflects_rules_evaluated(
    tmp_path: Path,
    fake_fast_analyzer: list[tuple[Path, tuple[Document, ...]]],
) -> None:
    result = scan(tmp_path, config=Config(profile="fast", select=("DS199",)))

    assert len(fake_fast_analyzer) == 1
    assert "evaluated" in result.notice
    assert "not implemented" not in result.notice
    assert result.enabled_rules == ("DS199",)


def test_scan_notice_distinguishes_unimplemented_profile_from_filtered_out(
    tmp_path: Path,
    fake_fast_analyzer: list[tuple[Path, tuple[Document, ...]]],
) -> None:
    unimplemented = scan(tmp_path, config=Config(profile="deep"))
    filtered = scan(tmp_path, config=Config(profile="fast", ignore=("DS1",)))

    assert fake_fast_analyzer == []
    assert "deep profile requires explicit opt-in" in unimplemented.pending[0]
    assert filtered.pending == ("all fast rules were excluded by select/ignore",)
    assert "not implemented" not in filtered.notice
    assert "evaluated" not in filtered.notice


def test_discovery_is_sorted_filtered_and_does_not_follow_symlinks(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "b.md").write_text("abc", encoding="utf-8")
    (tmp_path / "a.md").write_text("x", encoding="utf-8")
    (tmp_path / "docs" / "ignore.txt").write_text("not docs", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "hidden.md").write_text("hidden", encoding="utf-8")
    (tmp_path / "alias.md").symlink_to(tmp_path / "a.md")
    result = scan(tmp_path)
    assert [(doc.path, doc.bytes) for doc in result.documents] == [
        ("a.md", 1),
        ("docs/b.md", 3),
    ]


def test_discovery_prunes_excluded_directories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    excluded = tmp_path / ".git"
    excluded.mkdir()
    (excluded / "hidden.md").write_text("hidden", encoding="utf-8")
    original_scandir = os.scandir

    def scandir(path: str | bytes | Path):
        if Path(path) == excluded:
            raise AssertionError("excluded directory was traversed")
        return original_scandir(path)

    monkeypatch.setattr(os, "scandir", scandir)
    assert scan(tmp_path).documents == ()


def test_discovery_propagates_directory_listing_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    unreadable = tmp_path / "unreadable"
    unreadable.mkdir()
    original_scandir = os.scandir

    def scandir(path: str | bytes | Path):
        if Path(path) == unreadable:
            raise PermissionError("cannot list directory")
        return original_scandir(path)

    monkeypatch.setattr(os, "scandir", scandir)
    with pytest.raises(PermissionError, match="cannot list directory"):
        scan(tmp_path)


def test_config_and_pending_profile(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("x", encoding="utf-8")
    (tmp_path / "b.markdown").write_text("y", encoding="utf-8")
    (tmp_path / "doc_sentinel.toml").write_text(
        'profile = "deep"\ninclude = ["*.markdown"]\n',
        encoding="utf-8",
    )
    result = scan(tmp_path)
    assert [doc.path for doc in result.documents] == ["b.markdown"]
    assert "deep profile requires explicit opt-in" in result.pending[0]
    assert result.enabled_rules == ()


@pytest.mark.parametrize(
    "contents",
    [
        'profile = "wrong"\n',
        'include = "not a list"\n',
        "unknown = 1\n",
        "bad toml ===",
    ],
)
def test_bad_config_fails_clearly(tmp_path: Path, contents: str) -> None:
    (tmp_path / "doc_sentinel.toml").write_text(contents, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_invalid_utf8_config_raises_config_error(tmp_path: Path) -> None:
    (tmp_path / "doc_sentinel.toml").write_bytes(b"\xff")
    with pytest.raises(ConfigError):
        load_config(tmp_path)
    with pytest.raises(ConfigError):
        scan(tmp_path)


def test_init_creates_doc_sentinel_toml(tmp_path: Path) -> None:
    assert main(["init", str(tmp_path)]) == 0

    target = tmp_path / "doc_sentinel.toml"
    assert target.is_file()
    initial_content = target.read_text(encoding="utf-8")
    assert load_config(tmp_path) == Config()

    assert main(["init", str(tmp_path)]) == 2
    assert target.read_text(encoding="utf-8") == initial_content


def test_cli_select_flag_parses_comma_separated(
    tmp_path: Path,
    captured_cli_configs: list[Config],
) -> None:
    assert main(["scan", str(tmp_path), "--select", "DS1, DS2"]) == 0

    assert captured_cli_configs == [Config(select=("DS1", "DS2"))]


def test_cli_ignore_flag_works_without_config(
    tmp_path: Path,
    captured_cli_configs: list[Config],
) -> None:
    assert main(["scan", str(tmp_path), "--ignore", "DS3"]) == 0

    assert captured_cli_configs == [Config(ignore=("DS3",))]


def test_cli_ignore_flag_overrides_config_file(
    tmp_path: Path,
    captured_cli_configs: list[Config],
) -> None:
    (tmp_path / "doc_sentinel.toml").write_text('ignore = ["DS101"]\n', encoding="utf-8")

    assert main(["scan", str(tmp_path), "--ignore", "DS2"]) == 0

    assert captured_cli_configs == [Config(ignore=("DS2",))]


@pytest.mark.parametrize(
    ("arguments", "expected_profile", "expected_select", "expected_ignore", "expected_baseline"),
    [
        (("--profile", "standard"), "standard", ("DS10",), ("DS90",), None),
        (("--select", "DS2, DS3"), "deep", ("DS2", "DS3"), ("DS90",), None),
        (("--ignore", "DS201"), "deep", ("DS10",), ("DS201",), None),
        (("--baseline", "custom-baseline.json"), "deep", ("DS10",), ("DS90",), "custom-baseline.json"),
    ],
    ids=("profile", "select", "ignore", "baseline"),
)
def test_cli_explicit_override_preserves_other_loaded_settings(
    tmp_path: Path,
    captured_cli_configs: list[Config],
    arguments: tuple[str, ...],
    expected_profile: str,
    expected_select: tuple[str, ...],
    expected_ignore: tuple[str, ...],
    expected_baseline: Optional[str],
) -> None:
    (tmp_path / "doc_sentinel.toml").write_text(
        'profile = "deep"\n'
        'include = ["*.markdown"]\n'
        'exclude = ["build"]\n'
        'select = ["DS10"]\n'
        'ignore = ["DS90"]\n'
        "max_grade_level = 11.5\n"
        "duplicate_similarity = 0.75\n"
        "min_information_score = 0.25\n"
        'docsig_paths = ["lib"]\n',
        encoding="utf-8",
    )

    assert main(["scan", str(tmp_path), *arguments]) == 0

    assert captured_cli_configs == [
        Config(
            include=("*.markdown",),
            exclude=("build",),
            profile=expected_profile,
            select=expected_select,
            ignore=expected_ignore,
            baseline=expected_baseline,
            max_grade_level=11.5,
            duplicate_similarity=0.75,
            min_information_score=0.25,
            docsig_paths=("lib",),
        )
    ]


def test_rules_command_lists_real_registry(capsys: pytest.CaptureFixture[str]) -> None:
    expected_codes = ("DS101", "DS102", "DS103")
    assert main(["rules"]) == 0

    output = capsys.readouterr().out
    profiles = ("fast", "standard", "deep")
    positions = tuple(output.index(profile) for profile in profiles)
    assert positions == tuple(sorted(positions))
    for index, start in enumerate(positions):
        end = positions[index + 1] if index + 1 < len(positions) else len(output)
        profile_output = output[start:end]
        if profiles[index] == "fast":
            assert all(code in profile_output for code in expected_codes)
            assert "(none registered)" not in profile_output
        elif profiles[index] == "standard":
            assert "DS201" in profile_output
            assert "DS202" in profile_output
            assert "DS203" in profile_output
            assert "DS204" in profile_output
            assert "(none registered)" not in profile_output
        else:
            assert "DS301" in profile_output
            assert "(none registered)" not in profile_output
    assert tuple(sorted(RULES)) == (*expected_codes, "DS201", "DS202", "DS203", "DS204", "DS301")


def test_doctor_command_reports_counts(capsys: pytest.CaptureFixture[str]) -> None:
    expected_codes = ("DS101", "DS102", "DS103", "DS201", "DS202", "DS203", "DS204", "DS301")
    assert main(["doctor"]) == 0

    output = capsys.readouterr().out
    assert "Inventory: available" in output
    assert "standard profile: available" in output
    assert "deep profile:" in output
    assert "fast rules: 3 registered" in output
    assert "standard rules: 4 registered" in output
    assert "deep rules: 1 registered" in output
    assert tuple(sorted(RULES)) == expected_codes


def test_cli_scan_returns_one_and_renders_findings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_scan(root: str, *, config: Config) -> ScanResult:
        return ScanResult(
            profile=config.profile,
            documents=(),
            findings=(Finding(rule="DS101", path="README.md", message="Broken link", severity="error"),),
            enabled_rules=("DS101",),
            pending=(),
            notice="1 rule evaluated.",
        )

    monkeypatch.setattr(cli, "scan", fake_scan)

    assert main(["scan", str(tmp_path)]) == 1
    assert "error: README.md: Broken link" in capsys.readouterr().out.splitlines()


def test_invalid_root(tmp_path: Path) -> None:
    assert main(["scan", str(tmp_path / "missing")]) == 2


def test_public_config_can_select_only_nested_files(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("guide", encoding="utf-8")
    (tmp_path / "README.md").write_text("readme", encoding="utf-8")
    assert [doc.path for doc in scan(tmp_path, config=Config(include=("docs/*.md",))).documents] == ["docs/guide.md"]


def test_scan_accepts_a_single_selected_file(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / "b.md").write_text("bb", encoding="utf-8")
    result = scan(tmp_path / "b.md")
    assert [(item.path, item.bytes) for item in result.documents] == [("b.md", 2)]


def test_cli_scan_selected_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "a.md").write_text("a", encoding="utf-8")
    assert main(["scan", str(tmp_path / "a.md"), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["documents"][0]["path"] == "a.md"


def test_exit_code_zero_for_warnings_only_by_default() -> None:
    result = ScanResult(
        profile="fast",
        documents=(),
        findings=(
            Finding(rule="DS102", path="README.md", message="Stray comment", severity="warning"),
            Finding(rule="DS103", path="docs.md", message="Unresolvable path", severity="warning"),
        ),
        enabled_rules=("DS102", "DS103"),
        pending=(),
    )
    assert _exit_code(result, strict=False) == 0


def test_exit_code_one_for_any_error_by_default() -> None:
    result = ScanResult(
        profile="fast",
        documents=(),
        findings=(
            Finding(rule="DS102", path="README.md", message="Stray comment", severity="warning"),
            Finding(rule="DS101", path="links.md", message="Dangling link", severity="error"),
            Finding(rule="DS103", path="docs.md", message="Unresolvable path", severity="warning"),
        ),
        enabled_rules=("DS101", "DS102", "DS103"),
        pending=(),
    )
    assert _exit_code(result, strict=False) == 1


def test_exit_code_strict_fails_on_warnings_too() -> None:
    result = ScanResult(
        profile="fast",
        documents=(),
        findings=(Finding(rule="DS102", path="README.md", message="Stray comment", severity="warning"),),
        enabled_rules=("DS102",),
        pending=(),
    )
    assert _exit_code(result, strict=True) == 1


def test_exit_code_zero_when_no_findings_regardless_of_strict() -> None:
    result = ScanResult(
        profile="fast",
        documents=(),
        findings=(),
        enabled_rules=("DS101", "DS102", "DS103"),
        pending=(),
    )
    assert _exit_code(result, strict=False) == 0
    assert _exit_code(result, strict=True) == 0


def test_cli_strict_flag_wired_end_to_end(tmp_path: Path) -> None:
    (tmp_path / "comment.md").write_text("<!-- stray -->\n", encoding="utf-8")

    assert main(["scan", str(tmp_path)]) == 0
    assert main(["scan", str(tmp_path), "--strict"]) == 1


def _symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlinks unavailable: {error}")


def test_scan_selected_symlink_raises_value_error(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    target.write_text("content\n", encoding="utf-8")
    link = tmp_path / "link.md"
    _symlink_or_skip(link, target)

    with pytest.raises(ValueError, match=f"^Symlinked files are not inventoried: {re.escape(str(link))}$"):
        scan(link)


def test_scan_exclude_exact_relative_root_file(tmp_path: Path) -> None:
    (tmp_path / "skip.md").write_text("skip\n", encoding="utf-8")
    (tmp_path / "keep.md").write_text("keep\n", encoding="utf-8")
    result = scan(tmp_path, config=Config(exclude=("skip.md",)))
    assert [doc.path for doc in result.documents] == ["keep.md"]


def test_scan_exclude_parent_path_pattern_nested_document(tmp_path: Path) -> None:
    sub_dir = tmp_path / "sub"
    sub_dir.mkdir()
    (sub_dir / "doc.md").write_text("nested doc\n", encoding="utf-8")
    (sub_dir / "preserve.md").write_text("nested preserve\n", encoding="utf-8")
    (tmp_path / "root.md").write_text("root\n", encoding="utf-8")

    result = scan(tmp_path, config=Config(exclude=("sub/doc.md",)))
    assert [doc.path for doc in result.documents] == ["root.md", "sub/preserve.md"]


def test_fast_scan_does_not_import_standard_subpackage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[None] = []

    def fake_loader() -> None:
        calls.append(None)

    monkeypatch.setattr("docsentinel.engine.ensure_standard_loaded", fake_loader)
    scan(tmp_path, config=Config(profile="fast"))

    assert calls == []


def test_standard_scan_calls_loader(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[None] = []

    def fake_loader() -> None:
        calls.append(None)

    monkeypatch.setattr("docsentinel.engine.ensure_standard_loaded", fake_loader)
    scan(tmp_path, config=Config(profile="standard"))

    assert len(calls) == 1


def test_standard_scan_without_extra_raises_actionable_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cause = ModuleNotFoundError("No module named 'sklearn'", name="sklearn")

    def fake_loader() -> None:
        raise ExtraNotInstalledError("standard", cause)

    monkeypatch.setattr("docsentinel.engine.ensure_standard_loaded", fake_loader)

    with pytest.raises(ExtraNotInstalledError) as exc_info:
        scan(tmp_path, config=Config(profile="standard"))

    assert exc_info.value.extra == "standard"
    assert "docsentinel[standard]" in str(exc_info.value)


def test_cli_scan_standard_without_extra_exits_2_with_guidance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cause = ModuleNotFoundError("No module named 'sklearn'", name="sklearn")

    def fake_loader() -> None:
        raise ExtraNotInstalledError("standard", cause)

    monkeypatch.setattr("docsentinel.engine.ensure_standard_loaded", fake_loader)
    assert main(["scan", str(tmp_path), "--profile", "standard"]) == 2
    captured = capsys.readouterr()
    assert "docsentinel[standard]" in captured.err
    assert "Scan failed:" in captured.err


def test_cli_rules_lists_standard_when_extra_present(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("docsentinel.cli.ensure_standard_loaded", lambda: None)
    rule = register_rule(Rule("DS299", "standard", "Fake standard rule", "Tests standard CLI rules listing."))
    try:
        assert main(["rules"]) == 0
        output = capsys.readouterr().out
        assert "DS299: Fake standard rule" in output
    finally:
        RULES.pop(rule.code, None)


def test_cli_rules_notes_missing_extra_and_still_exits_0(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cause = ModuleNotFoundError("No module named 'sklearn'", name="sklearn")

    def fake_loader() -> None:
        raise ExtraNotInstalledError("standard", cause)

    monkeypatch.setattr("docsentinel.cli.ensure_standard_loaded", fake_loader)
    assert main(["rules"]) == 0
    output = capsys.readouterr().out
    assert "standard profile: install docsentinel[standard] to enable (DS2xx)" in output


@pytest.mark.parametrize(
    ("loader_raises", "expected_fragment"),
    [
        (False, "standard profile: available"),
        (True, "standard profile: not installed (pip install docsentinel[standard])"),
    ],
    ids=("available", "not_installed"),
)
def test_cli_doctor_reports_standard_availability(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    loader_raises: bool,
    expected_fragment: str,
) -> None:
    if loader_raises:
        cause = ModuleNotFoundError("No module named 'sklearn'", name="sklearn")

        def fake_loader() -> None:
            raise ExtraNotInstalledError("standard", cause)

        monkeypatch.setattr("docsentinel.cli.ensure_standard_loaded", fake_loader)
    else:
        monkeypatch.setattr("docsentinel.cli.ensure_standard_loaded", lambda: None)

    assert main(["doctor"]) == 0
    output = capsys.readouterr().out
    assert expected_fragment in output


def test_cli_scan_fast_profile_never_loads_standard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[None] = []

    def fake_loader() -> None:
        calls.append(None)

    monkeypatch.setattr("docsentinel.engine.ensure_standard_loaded", fake_loader)
    monkeypatch.setattr("docsentinel.cli.ensure_standard_loaded", fake_loader)

    assert main(["scan", str(tmp_path)]) == 0
    assert calls == []


def test_deep_unconfirmed_reports_opt_in_pending(tmp_path: Path) -> None:
    result = scan(tmp_path, config=Config(profile="deep"))
    assert result.findings == ()
    assert result.enabled_rules == ()
    assert "deep profile requires explicit opt-in" in result.pending[0]
    assert "not implemented" in result.notice


def test_deep_confirmed_via_config_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("docsentinel.engine.deep_ready", lambda: True)
    monkeypatch.setitem(ANALYZERS, "DS301", lambda root, docs: ())
    result = scan(tmp_path, config=Config(profile="deep", deep_confirm=True))
    assert result.findings == ()
    assert result.enabled_rules == ("DS301",)
    assert "evaluated" in result.notice


def test_deep_confirmed_via_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCSENTINEL_DEEP_CONFIRM", "1")
    monkeypatch.setattr("docsentinel.engine.deep_ready", lambda: True)
    monkeypatch.setitem(ANALYZERS, "DS301", lambda root, docs: ())
    result = scan(tmp_path, config=Config(profile="deep"))
    assert result.findings == ()
    assert result.enabled_rules == ("DS301",)
    assert "evaluated" in result.notice


def test_deep_confirmed_via_cli_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("docsentinel.engine.deep_ready", lambda: True)
    monkeypatch.setitem(ANALYZERS, "DS301", lambda root, docs: ())
    code = main(["scan", str(tmp_path), "--profile", "deep", "--i-understand-deep-is-heuristic"])
    assert code == 0
    out = capsys.readouterr().out
    assert "1 deep rule(s) evaluated" in out


def test_deep_confirmed_but_deps_missing_reports_pending(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("docsentinel.engine.deep_ready", lambda: False)
    result = scan(tmp_path, config=Config(profile="deep", deep_confirm=True))
    assert result.findings == ()
    assert result.enabled_rules == ()
    assert "deep profile confirmed, but its dependencies are unavailable" in result.pending[0]
    assert "pip install docsentinel[deep]" in result.pending[0]


def test_deep_findings_never_fail_exit_code() -> None:
    result = ScanResult(
        profile="deep",
        documents=(),
        findings=(Finding(rule="DS301", path="a.md", message="candidate contradiction", severity="warning"),),
        enabled_rules=("DS301",),
        pending=(),
    )
    assert _exit_code(result, strict=False) == 0


def test_deep_findings_exempt_even_under_strict() -> None:
    result = ScanResult(
        profile="deep",
        documents=(),
        findings=(Finding(rule="DS301", path="a.md", message="candidate contradiction", severity="warning"),),
        enabled_rules=("DS301",),
        pending=(),
    )
    assert _exit_code(result, strict=True) == 0


def test_deep_exemption_holds_even_for_error_severity() -> None:
    result = ScanResult(
        profile="deep",
        documents=(),
        findings=(Finding(rule="DS301", path="a.md", message="hypothetical error", severity="error"),),
        enabled_rules=("DS301",),
        pending=(),
    )
    assert _exit_code(result, strict=False) == 0
    assert _exit_code(result, strict=True) == 0


def test_fast_and_standard_exit_codes_unchanged() -> None:
    fast_err = ScanResult(
        profile="fast",
        documents=(),
        findings=(Finding(rule="DS101", path="a.md", message="error", severity="error"),),
        enabled_rules=("DS101",),
        pending=(),
    )
    assert _exit_code(fast_err, strict=False) == 1

    std_warn = ScanResult(
        profile="standard",
        documents=(),
        findings=(Finding(rule="DS201", path="a.md", message="warning", severity="warning"),),
        enabled_rules=("DS201",),
        pending=(),
    )
    assert _exit_code(std_warn, strict=False) == 0
    assert _exit_code(std_warn, strict=True) == 1


def test_deep_evaluated_notice_is_advisory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("docsentinel.engine.deep_ready", lambda: True)
    monkeypatch.setitem(ANALYZERS, "DS301", lambda root, docs: ())
    result = scan(tmp_path, config=Config(profile="deep", deep_confirm=True))
    assert "evaluated" in result.notice
    assert "advisory" in result.notice
    assert "not implemented" not in result.notice
