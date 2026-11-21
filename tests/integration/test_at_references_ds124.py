"""Integration tests for DS124 (dangling ``@``-document references) over ``tests/assets/ds124``.

Each case runs through :func:`docsentinel.scan` (or ``mentions.detect`` where the threat
model asks for a direct call), so the engine's link-root wiring, registration and
classification are exercised end to end. Symlinks, FIFOs and permission changes are built
in the test body, never committed.
"""

from __future__ import annotations

import dataclasses
import os
import re
import stat
from collections.abc import Callable
from pathlib import Path

import pytest

import docsentinel
from docsentinel import cli, models, reporting, rules
from docsentinel.config import Config
from docsentinel.detectors import mentions
from docsentinel.link_root import LINK_ROOT_RULES
from docsentinel.telemetry.classify import FAULT_CLASSES
from tests.asset_helpers import AssetCase
from tests.timing_helpers import assert_scales_linearly

AssetLoader = Callable[[str, str], AssetCase]


def _ds124(result: models.ScanResult) -> list[models.Finding]:
    """Return the DS124 findings of a scan result.

    :param result: A scan result.
    :returns: Its DS124 findings in order.
    """
    return [finding for finding in result.findings if finding.rule == "DS124"]


def _rules(result: models.ScanResult) -> list[str]:
    """Return the rule codes of a result's findings, in order.

    :param result: A scan result.
    :returns: The codes.
    """
    return [finding.rule for finding in result.findings]


def _shape(finding: models.Finding) -> tuple[object, ...]:
    """Return every reported field of a finding.

    :param finding: A finding.
    :returns: ``(rule, path, line, column, value, type, severity, message)``.
    """
    return (
        finding.rule,
        finding.path,
        finding.line,
        finding.column,
        finding.value,
        finding.type,
        finding.severity,
        finding.message,
    )


def _want(path: str, line: int, column: int, raw: str) -> tuple[object, ...]:
    """Return the expected :func:`_shape` of a DS124 finding (ADR 0004 Contract 3).

    :param path: The referring document.
    :param line: The 1-based line of the ``@``.
    :param column: The 1-based code-point column of the ``@``.
    :param raw: The bounded raw mention, echoed in value and message.
    :returns: The expected field tuple.
    """
    return ("DS124", path, line, column, raw, "dangling document mention", "warning", f"dangling @-reference -> {raw}")


def test_ds124_registration_matches_contract():
    """
    [Integration] DS124 registration: one fast warning rule, one analyzer, one fault class, in the link-root set.

    Scenario:
        Given ``import docsentinel``
        When RULES, ANALYZERS, FAULT_CLASSES and LINK_ROOT_RULES are read
        Then DS124 carries exactly the ADR 0004 Contract 3 metadata.

    Boundaries:
        - Focus: Task 05 acceptance "DS124 appears once in RULES and ANALYZERS"
        - Fixtures/params: none

    On failure, first check:
        - The register_rule call in detectors/mentions.py and the detectors package import
    """
    rule = rules.RULES["DS124"]
    assert (rule.profile, rule.severity, rule.title, rule.description, rule.opt_in_option) == (
        "fast",
        "warning",
        "Dangling @-document reference",
        "An @-document mention does not resolve to an existing file.",
        "",
    )
    assert rules.ANALYZERS["DS124"] is mentions.detect
    assert FAULT_CLASSES["DS124"] == "dangling_reference"
    assert "DS124" in LINK_ROOT_RULES
    assert docsentinel.scan  # the public entry point still imports


def test_prose_mention_resolves(asset_case: AssetLoader):
    """
    [Integration] DS124: document-relative prose mentions to existing files give no finding.

    Scenario:
        Given README.md mentioning @guide.md and (@sub/notes.md), both present
        When the case is scanned
        Then there is no DS124 finding.

    Boundaries:
        - Focus: step 1 resolution
        - Fixtures/params: ds124/prose_mention_resolves

    On failure, first check:
        - _Resolver._resolve step 1 and _is_regular
    """
    case = asset_case("ds124", "prose_mention_resolves")

    assert _ds124(docsentinel.scan(case.root)) == []


def test_prose_mention_missing(asset_case: AssetLoader):
    """
    [Integration] DS124: a missing prose mention gives one warning with the contract fields.

    Scenario:
        Given README.md line 3 "Follow @docs/missing.md before you start."
        When the case is scanned
        Then one DS124 warning at line 3, column 8, value and message echoing the raw mention.

    Boundaries:
        - Focus: the Finding shape of ADR 0004 Contract 3
        - Fixtures/params: ds124/prose_mention_missing

    On failure, first check:
        - The Finding built in mentions._check_text and _column
    """
    case = asset_case("ds124", "prose_mention_missing")

    (finding,) = _ds124(docsentinel.scan(case.root))

    assert finding == models.Finding(
        rule="DS124",
        path="README.md",
        message="dangling @-reference -> @docs/missing.md",
        severity="warning",
        line=3,
    )
    assert (finding.column, finding.value, finding.type) == (8, "@docs/missing.md", "dangling document mention")


def test_code_span_mention_missing(asset_case: AssetLoader):
    """
    [Integration] DS124: a missing code-span mention is reported at the column of its ``@``.

    Scenario:
        Given "The standard is `@docs/gone.md` here." on line 3
        When the case is scanned
        Then one DS124 finding with column 18 (the ``@`` after the backtick) and value @docs/gone.md.

    Boundaries:
        - Focus: code-span form (plan D6) and column computation
        - Fixtures/params: ds124/code_span_mention_missing

    On failure, first check:
        - _column's in_code_span branch
    """
    case = asset_case("ds124", "code_span_mention_missing")

    (finding,) = _ds124(docsentinel.scan(case.root))

    assert _shape(finding) == _want("README.md", 3, 18, "@docs/gone.md")


def test_project_root_fallback_resolves(asset_case: AssetLoader):
    """
    [Integration] DS124 step 2: mentions written from the project root resolve against the link root.

    Scenario:
        Given docs/README.md mentioning @AGENTS.md and `@docs/dev/standard.md`, both at the project root
        When docs/ is scanned with the project root as the invoker link root
        Then there is no DS124 finding; with link_root "." (the scan root) both are reported.

    Boundaries:
        - Focus: the link-root fallback and its boundary choice (M2, M18)
        - Fixtures/params: ds124/project_root_fallback_resolves

    On failure, first check:
        - The link_root= the engine passes to DS124 (LINK_ROOT_RULES)
    """
    case = asset_case("ds124", "project_root_fallback_resolves")

    widened = docsentinel.scan(case.root / "docs", link_root=case.root)
    narrow = docsentinel.scan(case.root / "docs")

    assert _ds124(widened) == []
    assert [_shape(finding) for finding in _ds124(narrow)] == [
        _want("README.md", 3, 6, "@AGENTS.md"),
        _want("README.md", 3, 22, "@docs/dev/standard.md"),
    ]


def test_link_root_dot_keeps_fallback_inside_scan_root(asset_case: AssetLoader):
    """
    [Integration] DS124: link_root = "." keeps the fallback inside the scan root even under a .git ancestor.

    Scenario:
        Given the fallback case with a .git directory at its root (built in the test)
        When docs/ is scanned with the default "auto" and with link_root = "."
        Then "auto" resolves both mentions and "." reports both.

    Boundaries:
        - Focus: M18 documented control for untrusted nested content
        - Fixtures/params: ds124/project_root_fallback_resolves

    On failure, first check:
        - resolve_link_root and the engine's link-root pass-through
    """
    case = asset_case("ds124", "project_root_fallback_resolves")
    (case.root / ".git").mkdir()

    auto = docsentinel.scan(case.root / "docs", config=Config())
    dot = docsentinel.scan(case.root / "docs", config=dataclasses.replace(Config(), link_root="."))

    assert _ds124(auto) == []
    assert [_shape(finding) for finding in _ds124(dot)] == [
        _want("README.md", 3, 6, "@AGENTS.md"),
        _want("README.md", 3, 22, "@docs/dev/standard.md"),
    ]


def test_parent_chain_above_link_root_no_finding(asset_case: AssetLoader, caplog: pytest.LogCaptureFixture):
    """
    [Integration] DS124 ruling R1: a fallback that climbs above the link root gives no finding.

    Scenario:
        Given a/b/README.md mentioning @../../above.md (step 1 stays in the scan root, above.md
            is missing; step 2 "/../../above.md" climbs above the link root)
        When the case is scanned with link_root = "."
        Then neither DS124 nor DS116 reports it, and one DEBUG record names the step-2 refusal.

    Boundaries:
        - Focus: M6, the single documented exception to "every mention has an outcome"
        - Fixtures/params: ds124/fallback_climbs_above_link_root

    On failure, first check:
        - The OUTSIDE_ROOT branch of step 2 in _Resolver._resolve
    """
    case = asset_case("ds124", "fallback_climbs_above_link_root")

    with caplog.at_level("DEBUG", logger="docsentinel"):
        result = docsentinel.scan(case.root, config=dataclasses.replace(Config(), link_root="."))

    assert "DS124" not in _rules(result)
    assert "DS116" not in _rules(result)
    assert any("step-2 boundary refusal" in record.getMessage() for record in caplog.records)


def test_fenced_and_comment_ignored(asset_case: AssetLoader):
    """
    [Integration] DS124: mentions in fences and HTML comments (prose and code-span) are not checked.

    Scenario:
        Given missing mentions only inside a fence and an HTML comment
        When the case is scanned
        Then there is no DS124 finding.

    Boundaries:
        - Focus: grammar exclusions reach the detector
        - Fixtures/params: ds124/fenced_and_comment_ignored

    On failure, first check:
        - The comment check on code-span mentions in scan_markdown
    """
    case = asset_case("ds124", "fenced_and_comment_ignored")

    assert _ds124(docsentinel.scan(case.root)) == []


def test_emails_and_handles_ignored(asset_case: AssetLoader):
    """
    [Integration] DS124: e-mail addresses, handles, scoped packages, versions and escaped @ are not mentions.

    Scenario:
        Given user@example.org, @octocat, @types/node, @1.2.3 and \\@docs/x.md
        When the case is scanned
        Then there is no DS124 finding.

    Boundaries:
        - Focus: README "Not recognised" row end to end
        - Fixtures/params: ds124/emails_and_handles_ignored

    On failure, first check:
        - _AT_BOUNDARY_CHARS and the extension requirement in _at_token
    """
    case = asset_case("ds124", "emails_and_handles_ignored")

    assert _ds124(docsentinel.scan(case.root)) == []


def test_escaped_space_path(asset_case: AssetLoader):
    """
    [Integration] DS124: an escaped space resolves to a directory with a space; the raw form is echoed.

    Scenario:
        Given "Design Docs/x.md" present and "@Design\\ Docs/y.md" missing
        When the case is scanned
        Then only the y.md mention is reported, with its value as written (backslash kept).

    Boundaries:
        - Focus: decoded target for resolution, raw for the finding
        - Fixtures/params: ds124/escaped_space_path

    On failure, first check:
        - That _Resolver receives AtReference.target and the Finding gets AtReference.raw
    """
    case = asset_case("ds124", "escaped_space_path")

    assert [_shape(finding) for finding in _ds124(docsentinel.scan(case.root))] == [
        _want("README.md", 3, 28, "@Design\\ Docs/y.md")
    ]


def test_unknown_extension_ignored(asset_case: AssetLoader):
    """
    [Integration] DS124: mentions whose extension is not in at_reference_extensions are not checked.

    Scenario:
        Given @example.com and @archive.zzz, both missing
        When the case is scanned with defaults, then with "zzz" added
        Then defaults report nothing and the widened list reports @archive.zzz.

    Boundaries:
        - Focus: extension filter end to end
        - Fixtures/params: ds124/unknown_extension_ignored

    On failure, first check:
        - _extension and the validated extension set
    """
    case = asset_case("ds124", "unknown_extension_ignored")
    widened = dataclasses.replace(Config(), at_reference_extensions=("md", "zzz"))

    assert _ds124(docsentinel.scan(case.root)) == []
    assert [_shape(finding) for finding in _ds124(docsentinel.scan(case.root, config=widened))] == [
        _want("README.md", 3, 23, "@archive.zzz")
    ]


def test_home_and_absolute_skipped(asset_case: AssetLoader):
    """
    [Integration] DS124/DS116: home and absolute mentions are never reported by either rule.

    Scenario:
        Given @~/notes/me.md, @/etc/hosts.txt and `@~/.ssh/id.pub`
        When the case is scanned
        Then there is no DS124 and no DS116 finding.

    Boundaries:
        - Focus: M7 at the scan level (the mock test proves no filesystem call)
        - Fixtures/params: ds124/home_and_absolute_skipped

    On failure, first check:
        - The kind branch in mentions._check_text and in DS116 check_text
    """
    case = asset_case("ds124", "home_and_absolute_skipped")
    result = docsentinel.scan(case.root)

    assert "DS124" not in _rules(result)
    assert "DS116" not in _rules(result)


def test_link_label_mention_ignored(asset_case: AssetLoader):
    """
    [Integration] DS124: a defined shortcut label and a reference-definition target are not mentions.

    Scenario:
        Given "[@missing.md]" with a matching definition and "[r]: @gone.md"
        When the case is scanned
        Then there is no DS124 finding.

    Boundaries:
        - Focus: Task 05 ruling (a) and (b)
        - Fixtures/params: ds124/link_label_mention_ignored

    On failure, first check:
        - The shortcut-label filter and the definition-target exclusion in scan_markdown
    """
    case = asset_case("ds124", "link_label_mention_ignored")

    assert _ds124(docsentinel.scan(case.root)) == []


def test_trailing_punctuation_stripped(asset_case: AssetLoader):
    """
    [Integration] DS124: trailing punctuation is not part of the mention.

    Scenario:
        Given "Read @guide.md. Then @missing.md?" with guide.md present
        When the case is scanned
        Then only @missing.md is reported, without the question mark.

    Boundaries:
        - Focus: punctuation strip reaches resolution and the finding value
        - Fixtures/params: ds124/trailing_punctuation_stripped

    On failure, first check:
        - _AT_TRAILING_PUNCTUATION
    """
    case = asset_case("ds124", "trailing_punctuation_stripped")

    assert [_shape(finding) for finding in _ds124(docsentinel.scan(case.root))] == [
        _want("README.md", 3, 22, "@missing.md")
    ]


def test_mention_escapes_root_is_ds116_only(asset_case: AssetLoader):
    """
    [Integration] DS116/DS124: escaping prose and code-span mentions are DS116 errors, never DS124.

    Scenario:
        Given docs/README.md with @../outside.md (the file exists above) and `@../../etc/hosts.md`
        When docs/ is scanned
        Then exactly two DS116 errors echo the raw mentions and there is no DS124 finding.

    Boundaries:
        - Focus: one owner per mention (M5) and A1 (the code span is classified once)
        - Fixtures/params: ds124/mention_escapes_root

    On failure, first check:
        - mention_ds116_reason and the mention candidates in DS116 check_text
    """
    case = asset_case("ds124", "mention_escapes_root")

    result = docsentinel.scan(case.root / "docs")

    # DS116 sets no column, value or type (CLAUDE.md, models.Finding); the message echoes the mention.
    assert [_shape(finding) for finding in result.findings] == [
        (
            "DS116",
            "README.md",
            3,
            None,
            None,
            None,
            "error",
            "reference escapes the documentation root: @../outside.md",
        ),
        (
            "DS116",
            "README.md",
            3,
            None,
            None,
            None,
            "error",
            "reference escapes the documentation root: @../../etc/hosts.md",
        ),
    ]


def test_tilde_user_is_literal_relative(asset_case: AssetLoader):
    """
    [Integration] DS124: a tilde-user token is a literal relative path, never expanded.

    Scenario:
        Given a directory literally named "~alice" holding notes.md and a mention @~alice/notes.md
        When the case is scanned
        Then the mention resolves (no finding).

    Boundaries:
        - Focus: M7 (only "~/" is home)
        - Fixtures/params: ds124/tilde_user_literal

    On failure, first check:
        - _at_token kind classification
    """
    case = asset_case("ds124", "tilde_user_literal")

    assert _ds124(docsentinel.scan(case.root)) == []


def test_value_and_message_bounded_to_200(asset_case: AssetLoader):
    """
    [Integration] DS124: a 1,000-character mention is echoed cut to 200 characters in value and message.

    Scenario:
        Given a missing mention of 1,001 characters with its @ (a single over-long file name)
        When the case is scanned
        Then one DS124 finding whose value is the first 200 characters and whose message echoes the same.

    Boundaries:
        - Focus: M15 (amendment A3), and M10 (ENAMETOOLONG never aborts)
        - Fixtures/params: ds124/long_mention_bounded

    On failure, first check:
        - MAX_ECHO_CHARS and the OSError handling in _Resolver
    """
    case = asset_case("ds124", "long_mention_bounded")

    (finding,) = _ds124(docsentinel.scan(case.root))

    assert _shape(finding) == _want("README.md", 3, 5, "@" + "x" * 199)


def test_overlong_component_reported_not_crash(asset_case: AssetLoader, capsys: pytest.CaptureFixture[str]):
    """
    [Integration] DS124: a 300-character file name is one finding; the scan does not abort.

    Scenario:
        Given a mention whose last component is over NAME_MAX
        When the CLI scans the case without and with --strict
        Then exit codes are 0 and 1 and the report names one DS124 finding.

    Boundaries:
        - Focus: M10 (ENAMETOOLONG means "does not resolve")
        - Fixtures/params: ds124/overlong_component

    On failure, first check:
        - _Resolver._contained and _is_regular OSError handling
    """
    case = asset_case("ds124", "overlong_component")

    token = case.read_text("README.md").splitlines()[2].split()[1]
    assert len(token) > 200
    assert [_shape(finding) for finding in _ds124(docsentinel.scan(case.root))] == [
        _want("README.md", 3, 5, token[:200])
    ]
    assert cli.main(["scan", str(case.root), "--format", "json"]) == 0
    assert cli.main(["scan", str(case.root), "--format", "json", "--strict"]) == 1
    assert '"DS124"' in capsys.readouterr().out


def test_path_max_token_reported_not_crash(tmp_path: Path):
    """
    [Integration] DS124: a 1,024-character token of many components (over PATH_MAX on macOS) is reported.

    Scenario:
        Given a missing mention made of 200-character components, 1,020 characters in total
        When it is scanned
        Then it is one DS124 finding and no exception escapes.

    Boundaries:
        - Focus: M10 for a total path length overflow
        - Fixtures/params: none (built in the test)

    On failure, first check:
        - _Resolver OSError handling on both steps
    """
    component = "d" * 200
    token = "/".join([component] * 5) + "/x.md"
    assert len(token) <= 1024
    (tmp_path / "README.md").write_text(f"See @{token} now.\n", encoding="utf-8")

    assert [_shape(finding) for finding in _ds124(docsentinel.scan(tmp_path))] == [
        _want("README.md", 1, 5, ("@" + token)[:200])
    ]


def test_unsearchable_directory_does_not_abort(tmp_path: Path):
    """
    [Integration] DS124: a mention under an unsearchable directory is reported; the scan continues.

    Scenario:
        Given locked/ with mode 000 and a mention @locked/x.md
        When it is scanned
        Then one DS124 finding and no PermissionError.

    Boundaries:
        - Focus: M10 for EACCES
        - Fixtures/params: chmod built in the test body

    On failure, first check:
        - _Resolver._contained swallowing OSError
    """
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("running as root bypasses the unreadable-file permission check")
    locked = tmp_path / "locked"
    locked.mkdir()
    (locked / "x.md").write_text("# X\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("@locked/x.md\n", encoding="utf-8")
    locked.chmod(0)
    try:
        result = docsentinel.scan(tmp_path, config=dataclasses.replace(Config(), exclude=("locked/**", "locked")))
    finally:
        locked.chmod(stat.S_IRWXU)

    assert [_shape(finding) for finding in _ds124(result)] == [_want("README.md", 1, 1, "@locked/x.md")]


def test_message_identical_for_missing_directory_and_fifo(tmp_path: Path):
    """
    [Integration] DS124: missing file, directory and FIFO targets give identical messages.

    Scenario:
        Given @gone.md (missing), @folder.md (a directory) and @pipe.md (a FIFO)
        When the document is checked
        Then three findings whose messages differ only by the echoed mention.

    Boundaries:
        - Focus: M17 (no type disclosure)
        - Fixtures/params: FIFO built in the test body

    On failure, first check:
        - That _is_regular collapses every non-regular outcome to False
    """
    if not hasattr(os, "mkfifo"):
        pytest.skip("os.mkfifo unavailable on this platform")
    (tmp_path / "folder.md").mkdir()
    os.mkfifo(tmp_path / "pipe.md")
    (tmp_path / "README.md").write_text("@gone.md @folder.md @pipe.md\n", encoding="utf-8")
    document = models.Document(path="README.md", bytes=1)

    findings = mentions.detect(tmp_path, (document,))

    assert [_shape(finding) for finding in findings] == [
        _want("README.md", 1, 1, "@gone.md"),
        _want("README.md", 1, 10, "@folder.md"),
        _want("README.md", 1, 21, "@pipe.md"),
    ]
    assert [finding.message.replace(finding.value or "", "M") for finding in findings] == [
        "dangling @-reference -> M"
    ] * 3


def test_finding_never_contains_resolved_path(asset_case: AssetLoader):
    """
    [Integration] DS124: no finding field carries the scan root or any absolute resolved path.

    Scenario:
        Given the missing-mention case
        When it is scanned and rendered as json
        Then neither the findings nor the report contain the absolute case directory.

    Boundaries:
        - Focus: M17 (never echo a resolved path)
        - Fixtures/params: ds124/prose_mention_missing

    On failure, first check:
        - The Finding fields in mentions._check_text
    """
    case = asset_case("ds124", "prose_mention_missing")

    result = docsentinel.scan(case.root)
    rendered = reporting.render(result, "json-v1")

    for finding in _ds124(result):
        assert str(case.root) not in f"{finding.message}{finding.value}{finding.path}"
    assert str(case.root) not in rendered


def test_text_and_github_reports_neutral(asset_case: AssetLoader):
    """
    [Integration] DS124 reports: text and github sinks carry one clean line per finding.

    Scenario:
        Given the missing prose and code-span mention cases composed into one tree
        When the result is rendered as text and github
        Then no control or bidi code point and no "##[" appears, and there is one annotation per finding.

    Boundaries:
        - Focus: M15 (existing neutralizing sinks, no new template)
        - Fixtures/params: ds124/prose_mention_missing, ds124/code_span_mention_missing

    On failure, first check:
        - The packaged text/github templates' neutralize filters
    """
    case = asset_case("ds124", "prose_mention_missing")
    (case.root / "README.md").rename(case.root / "first.md")
    asset_case("ds124", "code_span_mention_missing")

    result = docsentinel.scan(case.root)
    text = reporting.render(result, "text")
    github = reporting.render(result, "github")

    assert len(_ds124(result)) == 2
    for rendered in (text, github):
        assert not re.search("[\x00-\x08\x0b-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2066-\u2069]", rendered)
        assert "##[" not in rendered
    assert len([line for line in github.splitlines() if line.startswith("::warning") and "DS124" in line]) == 2


def test_direct_detect_without_link_root_stays_in_scan_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Integration] DS124 called directly without link_root= never looks above the scan root.

    Scenario:
        Given AGENTS.md only above the scan root (which has a .git ancestor) and a mention @AGENTS.md
        When mentions.detect runs without link_root
        Then the mention is reported and no lstat/stat touches a path above the scan root.

    Boundaries:
        - Focus: M21 lexical link_root_for fallback
        - Fixtures/params: os.stat/os.lstat recorded

    On failure, first check:
        - The link_root_for fallback in mentions.detect
    """
    repo = tmp_path.resolve()
    (repo / ".git").mkdir()
    (repo / "AGENTS.md").write_text("# A\n", encoding="utf-8")
    scan_root = repo / "docs"
    scan_root.mkdir()
    (scan_root / "README.md").write_text("@AGENTS.md\n", encoding="utf-8")
    calls: list[str] = []
    paused: list[bool] = [False]
    canonicalised: list[str] = []
    for name in ("stat", "lstat"):
        original = getattr(os, name)

        def recorder(
            path: object, *args: object, _original: Callable[..., object] = original, **kwargs: object
        ) -> object:
            """Record the probed path (unless paused), then delegate."""
            if not paused[0]:
                calls.append(os.fspath(path))  # type: ignore[arg-type]
            return _original(path, *args, **kwargs)

        monkeypatch.setattr(os, name, recorder)
    original_canonical = mentions.canonical_root

    def paused_canonical_root(root: Path) -> Path:
        """Canonicalise the trusted root with recording paused (security re-review R-1)."""
        canonicalised.append(os.fspath(root))
        paused[0] = True
        try:
            return original_canonical(root)
        finally:
            paused[0] = False

    monkeypatch.setattr(mentions, "canonical_root", paused_canonical_root)

    findings = mentions.detect(scan_root, (models.Document(path="README.md", bytes=1),))

    assert [
        (finding.path, finding.line, finding.column, finding.value, finding.type, finding.severity, finding.message)
        for finding in findings
    ] == [
        ("README.md", 1, 1, "@AGENTS.md", "dangling document mention", "warning", "dangling @-reference -> @AGENTS.md")
    ]
    # Only the trusted scan root is canonicalised; every recorded probe lies strictly below it,
    # with no allowance for the scan root itself or any of its ancestors.
    assert canonicalised == [os.fspath(scan_root)]
    assert calls, "the resolver must have probed in-root paths"
    assert all(path.startswith(os.fspath(scan_root) + os.sep) for path in calls), calls


def test_same_mention_twice_on_a_line_reported_once(tmp_path: Path):
    """
    [Integration] DS124: one finding per line for a repeated mention, one per document across files.

    Scenario:
        Given a.md with "@x.md @x.md" on one line and @x.md on another, and b.md with @x.md
        When scanned
        Then a.md has two findings (lines 1 and 2) and b.md one.

    Boundaries:
        - Focus: README "the same mention twice on one line is reported once"; edge case "two documents"
        - Fixtures/params: none

    On failure, first check:
        - The (line, bounded raw) seen-set in mentions._check_text
    """
    (tmp_path / "a.md").write_text("@x.md @x.md\n@x.md\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("@x.md\n", encoding="utf-8")

    found = [_shape(finding) for finding in _ds124(docsentinel.scan(tmp_path))]

    assert found == [_want("a.md", 1, 1, "@x.md"), _want("a.md", 2, 1, "@x.md"), _want("b.md", 1, 1, "@x.md")]


def test_ignore_ds124_silences_it(asset_case: AssetLoader):
    """
    [Integration] DS124 selection: ignore = ["DS124"] removes the rule.

    Scenario:
        Given the missing-mention case
        When scanned with ignore = ["DS124"]
        Then there is no DS124 finding and DS124 is not in enabled_rules.

    Boundaries:
        - Focus: the documented way to turn the rule off
        - Fixtures/params: ds124/prose_mention_missing

    On failure, first check:
        - effective_rules in the engine
    """
    case = asset_case("ds124", "prose_mention_missing")

    result = docsentinel.scan(case.root, config=dataclasses.replace(Config(), ignore=("DS124",)))

    assert _ds124(result) == []
    assert "DS124" not in result.enabled_rules


def test_detect_scales_linearly_with_mentions(tmp_path: Path):
    """
    [Integration] DS124: detection time grows linearly with distinct missing mentions.

    Scenario:
        Given documents with 500 to 4,000 distinct missing mentions, one per line
        When mentions.detect runs on each
        Then the CPU time scales near-linearly and every mention is reported.

    Boundaries:
        - Focus: M9 bounded cost per distinct target
        - Fixtures/params: timing helper

    On failure, first check:
        - _line_starts/_column (no per-finding rescan) and the memo dictionaries
    """

    def build(size: int) -> tuple[Path, tuple[models.Document, ...]]:
        """Write a document with ``size`` distinct missing mentions."""
        root = tmp_path / f"n{size}"
        root.mkdir()
        (root / "README.md").write_text("".join(f"@m{index}.md\n" for index in range(size)), encoding="utf-8")
        return root, (models.Document(path="README.md", bytes=1),)

    def run(payload: tuple[Path, tuple[models.Document, ...]]) -> tuple[models.Finding, ...]:
        """Run DS124 on one built payload."""
        return mentions.detect(payload[0], payload[1])

    assert_scales_linearly(build, run, (500, 1_000, 2_000, 4_000), expected_count=lambda size: size, label="ds124")


def test_single_file_target_checks_the_selected_file(asset_case: AssetLoader):
    """
    [Integration] DS124 single-file target: the selected file is checked, its directory is the scan root.

    Scenario:
        Given the prose_mention_missing and prose_mention_resolves cases side by side
        When each README.md is passed to scan() as a single-file target
        Then the missing mention is one DS124 finding with every contract field, the resolving
            one gives none, and each result inventories exactly the selected file.

    Boundaries:
        - Focus: README edge case "Single-file scan target"; a single-file scan must not skip the file
        - Fixtures/params: ds124/prose_mention_missing, ds124/prose_mention_resolves (in subdirectories)

    On failure, first check:
        - engine.scan's single-file root handling and discovery of a file target
    """
    missing = asset_case("ds124", "prose_mention_missing")
    (missing.root / "missing").mkdir()
    (missing.root / "README.md").rename(missing.root / "missing" / "README.md")
    resolves = asset_case("ds124", "prose_mention_resolves")

    missing_result = docsentinel.scan(missing.root / "missing" / "README.md")
    resolves_result = docsentinel.scan(resolves.root / "README.md")

    assert [document.path for document in missing_result.documents] == ["README.md"]
    assert [_shape(finding) for finding in _ds124(missing_result)] == [_want("README.md", 3, 8, "@docs/missing.md")]
    assert [document.path for document in resolves_result.documents] == ["README.md"]
    assert _ds124(resolves_result) == []


def test_non_utf8_document_is_ds100_only(tmp_path: Path):
    """
    [Integration] DS124 edge case: a non-UTF-8 document is withheld from DS124 and reported by DS100.

    Scenario:
        Given bad.md holding a missing mention and an invalid UTF-8 byte, and good.md with a missing mention
        When the directory is scanned
        Then bad.md has exactly one DS100 error and no DS124 finding; good.md keeps its DS124 warning.

    Boundaries:
        - Focus: README edge case "Unreadable or non-UTF-8 documents keep today's engine behaviour"
        - Fixtures/params: invalid bytes built in the test body

    On failure, first check:
        - engine._partition_readable and the analyzer document tuple
    """
    (tmp_path / "bad.md").write_bytes(b"@missing.md \xff\n")
    (tmp_path / "good.md").write_text("Intro @gone.md\n", encoding="utf-8")

    result = docsentinel.scan(tmp_path)

    assert [(finding.rule, finding.path, finding.severity, finding.type) for finding in result.findings] == [
        ("DS100", "bad.md", "error", "unreadable document"),
        ("DS124", "good.md", "warning", "dangling document mention"),
    ]
    assert [_shape(finding) for finding in _ds124(result)] == [_want("good.md", 1, 7, "@gone.md")]
