"""Integration tests: DS103 reference-scope behaviour through :func:`docsentinel.scan` (Milestone 0009 Story 01.0).

Covers the story Test-plan row "DS103 inert by default, reports in strict, skips ``@`` spans"
over the ``tests/assets/ds103`` cases ``links_scope_inert``, ``strict_scope_reports`` and
``strict_scope_skips_mentions``, plus the library-level scope precedence (built-in default,
standalone config, ``[tool.doc_sentinel]``, an injected ``Config``) and the baseline migration
case (a strict baseline read by a default-scope scan). The CLI precedence lives in
``test_reference_scope_cli_ds103.py``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from pathlib import Path
from typing import Optional

import pytest

import docsentinel
from docsentinel import models
from docsentinel.baseline import load_baseline, save_baseline
from docsentinel.config import Config
from tests.asset_helpers import AssetCase

AssetLoader = Callable[[str, str], AssetCase]

_LEGACY_OFF = (
    "DS110 (set require_fence_languages), DS112 (set navigation_indexes), "
    "DS115 (set deprecated_references_file), DS118 (set documentation_naming)."
)
_DEFAULT_NOTICE = (
    f'12 fast rule(s) evaluated; opt-in rule(s) not enabled: DS103 (set reference_scope = "strict"), {_LEGACY_OFF}'
)
_STRICT_NOTICE = f"13 fast rule(s) evaluated; opt-in rule(s) not enabled: {_LEGACY_OFF}"
_STRICT = Config(reference_scope="strict")

#: (path, line, column, value, type, severity, message) of the single DS103 finding of links_scope_inert.
_INERT_FINDING = (
    "README.md",
    3,
    6,
    "scripts/missing_tool.py",
    "unresolvable path",
    "warning",
    "unresolvable path -> scripts/missing_tool.py",
)


def _fields(finding: models.Finding) -> tuple[object, ...]:
    """Return every reported field of a finding except the rule code.

    :param finding: A finding.
    :returns: ``(path, line, column, value, type, severity, message)``.
    """
    return (
        finding.path,
        finding.line,
        finding.column,
        finding.value,
        finding.type,
        finding.severity,
        finding.message,
    )


def _ds103(result: models.ScanResult) -> list[tuple[object, ...]]:
    """Return the fields of every DS103 finding of a result, in order.

    :param result: A scan result.
    :returns: One field tuple per DS103 finding.
    """
    return [_fields(finding) for finding in result.findings if finding.rule == "DS103"]


def test_links_scope_inert(asset_case: AssetLoader):
    """
    [Integration] DS103 scope: the default scope runs no DS103 check and names DS103 in the notice.

    Scenario:
        Given one unresolvable path-like code span and no configuration file
        When docsentinel.scan runs with no config argument
        Then there is no DS103 finding, DS103 stays in enabled_rules (selection is orthogonal),
            opt_in_off names it first, and the notice is the ADR 0004 default text.

    Boundaries:
        - Focus: story acceptance "with no configuration, a scan never runs DS103"
        - Fixtures/params: ds103/links_scope_inert

    On failure, first check:
        - The opt_in_satisfied self-gate at the top of detectors/paths.detect
    """
    case = asset_case("ds103", "links_scope_inert")

    result = docsentinel.scan(case.root)

    assert _ds103(result) == []
    assert result.findings == ()
    assert "DS103" in result.enabled_rules
    assert result.opt_in_off[0] == ("DS103", "reference_scope")
    assert result.rules_evaluated == 12
    assert result.notice == _DEFAULT_NOTICE


def test_strict_scope_reports(asset_case: AssetLoader):
    """
    [Integration] DS103 scope: strict scope reports every unresolvable span with its full contract fields.

    Scenario:
        Given README.md with a missing span on line 3, a present span and a missing one on line 4,
            and sub/page.md with a present and a missing parent-relative span on line 3
        When the case is scanned with reference_scope = "strict"
        Then exactly three DS103 warnings, in document then source order, with their line, column,
            value, type, severity and message, and the notice counts 13 evaluated rules.

    Boundaries:
        - Focus: strict scope keeps DS103 behaviour (document-relative resolution, existing files silent)
        - Fixtures/params: ds103/strict_scope_reports

    On failure, first check:
        - detectors/paths.detect and its candidate filters
    """
    case = asset_case("ds103", "strict_scope_reports")

    result = docsentinel.scan(case.root, config=_STRICT)

    assert _ds103(result) == [
        (
            "README.md",
            3,
            6,
            "scripts/missing_tool.py",
            "unresolvable path",
            "warning",
            "unresolvable path -> scripts/missing_tool.py",
        ),
        ("README.md", 4, 27, "sub/notes.md", "unresolvable path", "warning", "unresolvable path -> sub/notes.md"),
        (
            "sub/page.md",
            3,
            24,
            "../absent/file.md",
            "unresolvable path",
            "warning",
            "unresolvable path -> ../absent/file.md",
        ),
    ]
    assert [finding.rule for finding in result.findings] == ["DS103"] * 3
    assert result.opt_in_off == (
        ("DS110", "require_fence_languages"),
        ("DS112", "navigation_indexes"),
        ("DS115", "deprecated_references_file"),
        ("DS118", "documentation_naming"),
    )
    assert result.notice == _STRICT_NOTICE


def test_strict_scope_skips_mentions(asset_case: AssetLoader):
    """
    [Integration] DS103 scope: strict DS103 skips every ``@`` code span; DS124 owns the mention.

    Scenario:
        Given `@docs/missing.md` (a mention), `@scripts/run` (an ``@`` span with no extension, so
            not a mention) and the plain span `missing/thing.py`, all missing
        When the case is scanned in both scopes
        Then strict DS103 reports only missing/thing.py; the mention is one DS124 warning in both
            scopes; the extensionless ``@`` span is reported by nobody (it stays in the root).

    Boundaries:
        - Focus: decision S7 (DS103 excludes the ``@`` prefix) and S4 (DS124 independent of scope)
        - Fixtures/params: ds103/strict_scope_skips_mentions

    On failure, first check:
        - The "@" entry in detectors/paths._is_excluded
    """
    case = asset_case("ds103", "strict_scope_skips_mentions")
    mention = (
        "DS124",
        "README.md",
        3,
        18,
        "@docs/missing.md",
        "dangling document mention",
        "warning",
        "dangling @-reference -> @docs/missing.md",
    )

    strict = docsentinel.scan(case.root, config=_STRICT)
    default = docsentinel.scan(case.root)

    assert [(finding.rule, *_fields(finding)) for finding in strict.findings] == [
        (
            "DS103",
            "README.md",
            4,
            17,
            "missing/thing.py",
            "unresolvable path",
            "warning",
            "unresolvable path -> missing/thing.py",
        ),
        mention,
    ]
    assert [(finding.rule, *_fields(finding)) for finding in default.findings] == [mention]
    assert not any("@" in str(finding.value) for finding in strict.findings if finding.rule == "DS103")


@pytest.mark.parametrize(
    ("config_text", "file_name", "injected", "expected"),
    [
        pytest.param(None, None, None, [], id="built_in_default"),
        pytest.param(
            'reference_scope = "strict"\n', "docsentinel.toml", None, [_INERT_FINDING], id="standalone_strict"
        ),
        pytest.param(
            '[tool.doc_sentinel]\nreference_scope = "strict"\n',
            "pyproject.toml",
            None,
            [_INERT_FINDING],
            id="pyproject_strict",
        ),
        pytest.param('reference_scope = "links"\n', "docsentinel.toml", None, [], id="standalone_links"),
        pytest.param(
            'reference_scope = "links"\n',
            "docsentinel.toml",
            "strict",
            [_INERT_FINDING],
            id="injected_beats_file_enable",
        ),
        pytest.param('reference_scope = "strict"\n', "docsentinel.toml", "links", [], id="injected_beats_file_disable"),
        pytest.param(None, None, "strict", [_INERT_FINDING], id="injected_strict_alone"),
    ],
)
def test_scan_scope_precedence(
    asset_case: AssetLoader,
    config_text: Optional[str],
    file_name: Optional[str],
    injected: Optional[str],
    expected: list[tuple[object, ...]],
):
    """
    [Integration] DS103 scope precedence through scan(): default < config file < injected Config.

    Scenario:
        Given the links_scope_inert case, optionally with reference_scope in docsentinel.toml or
            [tool.doc_sentinel], and optionally an injected Config with its own scope
        When docsentinel.scan runs
        Then DS103 reports the span exactly when the winning layer says "strict".

    Boundaries:
        - Focus: README "library callers set the key on Config"; both TOML forms; no scan() keyword
        - Fixtures/params: ds103/links_scope_inert; seven layer combinations

    On failure, first check:
        - engine.scan's config= handling (an injected Config replaces file discovery)
    """
    case = asset_case("ds103", "links_scope_inert")
    if config_text is not None and file_name is not None:
        (case.root / file_name).write_text(config_text, encoding="utf-8")
    config = None if injected is None else Config(reference_scope=injected)

    result = docsentinel.scan(case.root, config=config)

    assert _ds103(result) == expected
    named = ("DS103", "reference_scope") in result.opt_in_off
    assert named is (not expected)


def test_strict_with_ignore_ds103_is_neither_evaluated_nor_named(asset_case: AssetLoader):
    """
    [Integration] DS103 scope edge case: strict scope plus ignore = ["DS103"] drops the rule entirely.

    Scenario:
        Given the links_scope_inert case
        When scanned with reference_scope = "strict" and ignore = ["DS103"]
        Then no DS103 finding, DS103 is not in enabled_rules, not counted and not named as opt-in off.

    Boundaries:
        - Focus: README edge case "strict with ignore DS103"
        - Fixtures/params: ds103/links_scope_inert

    On failure, first check:
        - effective_rules and engine.evaluated_notice
    """
    case = asset_case("ds103", "links_scope_inert")

    result = docsentinel.scan(case.root, config=dataclasses.replace(_STRICT, ignore=("DS103",)))

    assert result.findings == ()
    assert "DS103" not in result.enabled_rules
    assert all(code != "DS103" for code, _ in result.opt_in_off)
    assert result.notice == f"12 fast rule(s) evaluated; opt-in rule(s) not enabled: {_LEGACY_OFF}"


def test_strict_baseline_then_default_scan_ignores_stale_fingerprints(asset_case: AssetLoader, tmp_path: Path):
    """
    [Integration] DS103 baseline migration: a strict baseline is read by a default-scope scan without error.

    Scenario:
        Given a baseline recorded from a strict scan (one DS103 fingerprint)
        When the same tree is scanned with that baseline in the default scope, then in strict scope
        Then the default scan succeeds with no finding (the stale fingerprint just matches nothing),
            and the strict scan suppresses the DS103 finding the baseline recorded.

    Boundaries:
        - Focus: README "Baselines and self-scan" (stale DS103 entries are not an error)
        - Fixtures/params: ds103/links_scope_inert; baseline written under tmp_path

    On failure, first check:
        - engine.scan's baseline filter and baseline.load_baseline
    """
    case = asset_case("ds103", "links_scope_inert")
    baseline_path = tmp_path / "strict-baseline.json"
    recorded = docsentinel.scan(case.root, config=_STRICT)
    assert _ds103(recorded) == [_INERT_FINDING]
    save_baseline(baseline_path, recorded.findings)
    assert len(load_baseline(baseline_path)) == 1

    default = docsentinel.scan(case.root, config=Config(baseline=str(baseline_path)))
    strict = docsentinel.scan(case.root, config=dataclasses.replace(_STRICT, baseline=str(baseline_path)))

    assert default.findings == ()
    assert default.notice == _DEFAULT_NOTICE
    assert strict.findings == ()
    assert strict.notice == _STRICT_NOTICE
