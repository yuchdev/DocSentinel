"""CLI surfaces once DS124 is registered: notice, ``rules``, ``doctor``, baselines and link-root wiring.

Uses the DS103 ``unresolvable_path_file`` asset (one path-like code span) and the DS124
``prose_mention_missing`` asset (one missing ``@``-mention), so both rules' scope behaviour
is visible on the command line (Milestone 0009 Story 01.0, Task 05).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from docsentinel import cli
from docsentinel.baseline import load_baseline
from tests.asset_helpers import AssetCase

AssetLoader = Callable[[str, str], AssetCase]

_DEFAULT_NOTICE = (
    '12 fast rule(s) evaluated; opt-in rule(s) not enabled: DS103 (set reference_scope = "strict"), '
    "DS110 (set require_fence_languages), DS112 (set navigation_indexes), "
    "DS115 (set deprecated_references_file), DS118 (set documentation_naming)."
)


def _composed(asset_case: AssetLoader) -> Path:
    """Load the DS103 and DS124 cases into one tree and return its root.

    :param asset_case: The asset loader fixture.
    :returns: The tree root.
    """
    root = asset_case("ds103", "unresolvable_path_file").root
    asset_case("ds124", "prose_mention_missing")
    return root


def _rules_in(report: str) -> list[str]:
    """Return the rule codes of a schema-2 JSON report's problems.

    :param report: The JSON report text.
    :returns: Rule codes in report order.
    """
    document = json.loads(report)
    return [problem["rule"] for doc in document["documents"] for problem in doc["problems"]]


def test_default_notice_counts_ds124(asset_case: AssetLoader, capsys: pytest.CaptureFixture[str]):
    """
    [Integration] cli ds103 ds124: the default notice reads 12 evaluated with DS103 named; strict reads 13.

    Scenario:
        Given the composed tree and no config
        When ``scan`` runs in text format by default and with ``--reference-scope strict``
        Then the default notice is the ADR 0004 text, DS124 reports and DS103 does not;
            strict evaluates 13 rules and reports both.

    Boundaries:
        - Focus: Task 05 fact 4 (12 evaluated) and the scope's independence from DS124
        - Fixtures/params: ds103/unresolvable_path_file, ds124/prose_mention_missing

    On failure, first check:
        - The DS124 registration and engine.evaluated_notice
    """
    root = _composed(asset_case)

    assert cli.main(["scan", str(root)]) == 0
    default_out = capsys.readouterr().out
    assert cli.main(["scan", str(root), "--format", "json", "--reference-scope", "strict"]) == 0
    strict_report = capsys.readouterr().out

    assert _DEFAULT_NOTICE in default_out
    assert "DS124 dangling document mention" in default_out
    assert "DS103 unresolvable path" not in default_out
    assert sorted(_rules_in(strict_report)) == ["DS103", "DS124"]
    assert "13 fast rule(s) evaluated" in json.loads(strict_report)["run"]["notice"]


def test_rules_and_doctor_list_ds124(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """
    [Integration] cli ds124: ``rules`` lists DS124 as an ordinary rule and ``doctor`` counts 18 fast rules.

    Scenario:
        Given an empty working directory
        When ``rules`` and ``doctor`` run
        Then DS124 has a plain line (no opt-in tag) and doctor reports 18 registered, 5 opt-in.

    Boundaries:
        - Focus: Task 05 fact 4 (18 registered)
        - Fixtures/params: none

    On failure, first check:
        - cli rules/doctor counting and the DS124 registration
    """
    monkeypatch.chdir(tmp_path)

    assert cli.main(["rules"]) == 0
    rules_out = capsys.readouterr().out
    cli.main(["doctor"])
    doctor_out = capsys.readouterr().out

    assert "  DS124: Dangling @-document reference\n" in rules_out
    assert (
        "fast rules: 18 registered (5 opt-in, off unless configured: DS103, DS110, DS112, DS115, DS118)" in doctor_out
    )


def test_baseline_records_ds124_in_both_scopes(
    asset_case: AssetLoader, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] cli ds103 ds124: DS124 is baselined in both scopes; DS103 only in strict.

    Scenario:
        Given the composed tree
        When ``baseline`` runs with and without ``--reference-scope strict``
        Then the default baseline holds one fingerprint (DS124) and the strict one two.

    Boundaries:
        - Focus: S4, DS124 is not tied to the scope
        - Fixtures/params: ds103/unresolvable_path_file, ds124/prose_mention_missing

    On failure, first check:
        - cli._run_baseline scope replace
    """
    root = _composed(asset_case)
    default_out = tmp_path / "default.json"
    strict_out = tmp_path / "strict.json"

    assert cli.main(["baseline", str(root), "--output", str(default_out)]) == 0
    assert cli.main(["baseline", str(root), "--output", str(strict_out), "--reference-scope", "strict"]) == 0
    capsys.readouterr()

    assert len(load_baseline(default_out)) == 1
    assert len(load_baseline(strict_out)) == 2


def test_select_only_ds124_validates_link_root(asset_case: AssetLoader, capsys: pytest.CaptureFixture[str]):
    """
    [Integration] cli ds124: with only DS124 selected, an invalid configured link_root exits 2.

    Scenario:
        Given the DS124 case nested in a directory, and a config with select = ["DS124"] and
            link_root = ".." (an ancestor with no .git and no project marker)
        When ``scan`` runs
        Then it fails closed with exit 2 and a ``Scan failed:`` line naming link_root.

    Boundaries:
        - Focus: M21, DS124 is in LINK_ROOT_RULES
        - Fixtures/params: ds124/prose_mention_missing

    On failure, first check:
        - LINK_ROOT_RULES in link_root.py
    """
    case = asset_case("ds124", "prose_mention_missing")
    inner = case.root / "inner"
    inner.mkdir()
    (case.root / "README.md").rename(inner / "README.md")
    (inner / "docsentinel.toml").write_text('select = ["DS124"]\nlink_root = ".."\n', encoding="utf-8")

    code = cli.main(["scan", str(inner)])
    err = capsys.readouterr().err

    assert code == 2
    assert "Scan failed:" in err
    assert "link_root" in err
