"""Tests for reporting format rendering and CLI format options."""

import json
from pathlib import Path

import pytest

from docsentinel import cli
from docsentinel.models import Finding, ScanResult
from docsentinel.reporting import _escape_data, _escape_property, _gha_level, render


def test_github_format_renders_error_and_warning_levels() -> None:
    result = ScanResult(
        profile="fast",
        documents=(),
        findings=(
            Finding(rule="DS101", path="README.md", message="Broken link", severity="error", line=10),
            Finding(rule="DS102", path="guide.md", message="Stray comment", severity="warning", line=20),
        ),
        enabled_rules=("DS101", "DS102"),
        pending=(),
    )
    rendered = render(result, "github")
    assert rendered == ("::error file=README.md,line=10::Broken link\n::warning file=guide.md,line=20::Stray comment")


def test_github_format_includes_known_line() -> None:
    result = ScanResult(
        profile="fast",
        documents=(),
        findings=(Finding(rule="DS101", path="docs/intro.md", message="Dangling link", severity="error", line=7),),
        enabled_rules=("DS101",),
        pending=(),
    )
    assert render(result, "github") == "::error file=docs/intro.md,line=7::Dangling link"


def test_github_format_omits_unknown_line_and_column() -> None:
    result = ScanResult(
        profile="fast",
        documents=(),
        findings=(
            Finding(rule="DS103", path="docs/ref.md", message="Unresolvable path", severity="warning", line=None),
        ),
        enabled_rules=("DS103",),
        pending=(),
    )
    rendered = render(result, "github")
    assert rendered == "::warning file=docs/ref.md::Unresolvable path"
    assert "line=" not in rendered
    assert "col=" not in rendered
    assert "column=" not in rendered


def test_github_format_with_no_findings_is_empty_string() -> None:
    result = ScanResult(
        profile="fast",
        documents=(),
        findings=(),
        enabled_rules=("DS101", "DS102"),
        pending=(),
    )
    assert render(result, "github") == ""


def test_unknown_severity_maps_to_warning_level() -> None:
    for severity in ("notice", "info", "critical", "suggestion", "custom", ""):
        result = ScanResult(
            profile="fast",
            documents=(),
            findings=(Finding(rule="DS999", path="file.md", message="Some finding", severity=severity, line=1),),
            enabled_rules=("DS999",),
            pending=(),
        )
        assert render(result, "github") == "::warning file=file.md,line=1::Some finding"
        assert _gha_level(severity) == "warning"


def test_gha_level_error_maps_to_error() -> None:
    assert _gha_level("error") == "error"


def test_github_format_escapes_message_newlines_carriage_returns_and_percents() -> None:
    message_with_injection = "Line 1\n::set-output name=injected::evil\r\nProgress: 100% complete %0A not decoded"
    result = ScanResult(
        profile="fast",
        documents=(),
        findings=(Finding(rule="DS101", path="doc.md", message=message_with_injection, severity="error", line=5),),
        enabled_rules=("DS101",),
        pending=(),
    )
    rendered = render(result, "github")
    assert "\n" not in rendered
    assert "\r" not in rendered
    assert rendered == (
        "::error file=doc.md,line=5::Line 1%0A::set-output name=injected::evil%0D%0A"
        "Progress: 100%25 complete %250A not decoded"
    )


def test_github_format_escapes_property_delimiters() -> None:
    path_with_delimiters = "docs/file,name:with%delims\r\nand,more.md"
    result = ScanResult(
        profile="fast",
        documents=(),
        findings=(
            Finding(rule="DS101", path=path_with_delimiters, message="Problem found", severity="error", line=12),
        ),
        enabled_rules=("DS101",),
        pending=(),
    )
    rendered = render(result, "github")
    assert "\n" not in rendered
    assert "\r" not in rendered
    assert rendered == ("::error file=docs/file%2Cname%3Awith%25delims%0D%0Aand%2Cmore.md,line=12::Problem found")


def test_escape_helpers_order_and_behavior() -> None:
    assert _escape_data("%\r\n") == "%25%0D%0A"
    assert _escape_data("%0A") == "%250A"
    assert _escape_property("%\r\n:,") == "%25%0D%0A%3A%2C"
    assert _escape_property("%2C%3A") == "%252C%253A"


def test_render_unsupported_format_raises_value_error() -> None:
    result = ScanResult(
        profile="fast",
        documents=(),
        findings=(),
        enabled_rules=(),
        pending=(),
    )
    with pytest.raises(ValueError, match="Unsupported format: invalid"):
        render(result, "invalid")


def test_cli_accepts_github_format_choice(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "valid.md").write_text("Hello world\n", encoding="utf-8")
    exit_code = cli.main(["scan", str(tmp_path), "--format", "github"])
    assert exit_code == 0
    assert capsys.readouterr().out == "\n"


def test_cli_scan_with_findings_and_github_format(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "broken.md").write_text("[Missing](missing.md)\n", encoding="utf-8")
    exit_code = cli.main(["scan", str(tmp_path), "--format", "github"])
    assert exit_code == 1
    out = capsys.readouterr().out
    assert out.startswith("::error file=broken.md,line=1::")


def test_render_text_and_json_formats() -> None:
    result = ScanResult(
        profile="fast",
        documents=(),
        findings=(Finding(rule="DS101", path="README.md", message="Broken link", severity="error", line=10),),
        enabled_rules=("DS101",),
        pending=("manual check",),
    )
    text_rendered = render(result, "text")
    assert "Profile: fast" in text_rendered
    assert "error: README.md: Broken link" in text_rendered
    assert "Pending: manual check" in text_rendered

    json_rendered = render(result, "json")
    assert '"profile": "fast"' in json_rendered
    assert '"rule": "DS101"' in json_rendered


def test_github_format_preserves_unicode_and_special_characters() -> None:
    result = ScanResult(
        profile="fast",
        documents=(),
        findings=(
            Finding(
                rule="DS101",
                path="docs/guide_日本語.md",
                message="Broken anchor ⚠️ -> #섹션",
                severity="error",
                line=42,
            ),
        ),
        enabled_rules=("DS101",),
        pending=(),
    )
    rendered = render(result, "github")
    assert rendered == "::error file=docs/guide_日本語.md,line=42::Broken anchor ⚠️ -> #섹션"


def test_json_output_includes_schema_version() -> None:
    result = ScanResult(
        profile="fast",
        documents=(),
        findings=(),
        enabled_rules=(),
        pending=(),
    )
    payload = json.loads(render(result, "json"))
    assert payload["schema_version"] == 1
    assert list(payload.keys())[0] == "schema_version"


def test_text_output_includes_schema_version_line() -> None:
    result = ScanResult(
        profile="fast",
        documents=(),
        findings=(),
        enabled_rules=(),
        pending=(),
    )
    rendered = render(result, "text")
    lines = rendered.splitlines()
    assert lines[0] == "Schema version: 1"


def test_schema_version_defaults_to_one_for_direct_construction() -> None:
    result = ScanResult(
        profile="fast",
        documents=(),
        findings=(),
        enabled_rules=(),
        pending=(),
    )
    assert result.schema_version == 1

    custom_result = ScanResult(
        schema_version=2,
        profile="fast",
        documents=(),
        findings=(),
        enabled_rules=(),
        pending=(),
    )
    assert custom_result.schema_version == 2


def test_json_output_includes_finding_line() -> None:
    result_with_line = ScanResult(
        profile="fast",
        documents=(),
        findings=(Finding(rule="DS101", path="README.md", message="Broken link", severity="error", line=42),),
        enabled_rules=("DS101",),
        pending=(),
    )
    payload_with_line = json.loads(render(result_with_line, "json"))
    assert payload_with_line["findings"][0]["line"] == 42

    result_without_line = ScanResult(
        profile="fast",
        documents=(),
        findings=(Finding(rule="DS101", path="README.md", message="Broken link", severity="error", line=None),),
        enabled_rules=("DS101",),
        pending=(),
    )
    payload_without_line = json.loads(render(result_without_line, "json"))
    assert payload_without_line["findings"][0]["line"] is None
