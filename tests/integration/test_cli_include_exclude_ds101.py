"""CLI ``--include``/``--exclude`` end to end over DS101 asset trees (Milestone 0009 Story 02.0, Task 04).

Each asset tree holds a dangling link inside and outside the selected directory, so the
DS101 findings show which documents the selection admitted. ADR 0006 Contracts 4 to 6:
``--include`` replaces, ``--exclude`` appends, a refused value leaves ``Scan failed:`` as
the first stderr line (exit 2), an empty inventory under invoker selection exits 2 (R1)
while a config-only empty inventory stays exit 0, and ``doctor`` counts the patterns.
"""

import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest

from docsentinel import cli, engine, scan
from docsentinel.baseline import fingerprint, load_baseline
from docsentinel.discovery import InvokerSelection
from tests.asset_helpers import AssetCase
from tests.log_helpers import problem_output, without_timestamps


def _report(capsys: pytest.CaptureFixture[str]) -> dict:
    """Return the schema-2 JSON report printed by the last CLI call."""
    return json.loads(capsys.readouterr().out)


def _paths(report: dict) -> list[str]:
    """Return the document paths of a schema-2 JSON report."""
    return [document["path"] for document in report["documents"]]


def _ds101_paths(report: dict) -> list[str]:
    """Return the paths of the documents that carry a DS101 problem."""
    return [
        document["path"]
        for document in report["documents"]
        if any(problem["rule"] == "DS101" for problem in document["problems"])
    ]


def test_cli_exclude_directory_drops_dangling_link(
    asset_case: Callable[[str, str], AssetCase], capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] cli ds101: verifies ``--exclude DIR`` removes every document below that directory.

    Scenario:
        Given a tree with a dangling link in README.md and in docs/archive/old.md
        When ``docsentinel scan --exclude docs/archive --format json`` runs
        Then docs/archive/old.md is not inventoried and only README.md keeps its DS101 finding.

    Boundaries:
        - Focus: Story 02.0 acceptance "--exclude docs/archive removes every document under it"
        - Fixtures/params: ds101/selection_excluded_directory
        - Scope: one in-process CLI call

    On failure, first check:
        - cli._scan_overrides and engine._apply_invoker_selection (exclude appended)
    """
    root = asset_case("ds101", "selection_excluded_directory").root

    code = cli.main(["scan", str(root), "--exclude", "docs/archive", "--format", "json"])
    report = _report(capsys)

    assert code == 1
    assert _paths(report) == ["README.md", "docs/guide.md"]
    assert _ds101_paths(report) == ["README.md"]


def test_cli_include_directory_admits_only_markdown_below(
    asset_case: Callable[[str, str], AssetCase], capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] cli ds101: verifies ``--include DIR`` replaces the include and admits only ``.md`` below it.

    Scenario:
        Given a tree with Markdown under docs/user and docs/dev, a README and a .txt in docs/user
        When ``docsentinel scan --include docs/user --format json`` runs
        Then only docs/user/guide.md is inventoried and carries the DS101 finding.

    Boundaries:
        - Focus: Story 02.0 acceptance "--include docs/user inventories only Markdown below it"
        - Fixtures/params: ds101/selection_included_directory
        - Scope: one in-process CLI call

    On failure, first check:
        - engine._apply_invoker_selection (include replaced) and discovery.selector_matches
    """
    root = asset_case("ds101", "selection_included_directory").root

    code = cli.main(["scan", str(root), "--include", "docs/user", "--format", "json"])
    report = _report(capsys)

    assert code == 1
    assert _paths(report) == ["docs/user/guide.md"]
    assert _ds101_paths(report) == ["docs/user/guide.md"]


def test_cli_and_library_give_identical_results(
    asset_case: Callable[[str, str], AssetCase], capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] cli ds101: verifies the CLI flags and the ``scan()`` keywords select the same documents.

    Scenario:
        Given the included-directory tree
        When the CLI runs with two --include values and one --exclude value
            and ``scan()`` runs with the same values as keywords
        Then both inventories and both sets of DS101 findings are equal.

    Boundaries:
        - Focus: ADR 0006 Contract 1 "the CLI and the library take the same path"
        - Fixtures/params: ds101/selection_included_directory
        - Scope: one in-process CLI call and one library call

    On failure, first check:
        - cli._scan_overrides passes the raw lists through to scan()
    """
    root = asset_case("ds101", "selection_included_directory").root
    include = ["docs", "README.md"]
    exclude = ["docs/dev"]

    argv = ["scan", str(root), "--format", "json"]
    argv += [f"--include={value}" for value in include] + [f"--exclude={value}" for value in exclude]
    assert cli.main(argv) == 1
    report = _report(capsys)
    result = scan(root, include=include, exclude=exclude)

    assert _paths(report) == [document.path for document in result.documents]
    assert _paths(report) == ["README.md", "docs/user/guide.md"]
    assert sorted(_ds101_paths(report)) == sorted({f.path for f in result.findings if f.rule == "DS101"})


@pytest.mark.parametrize(
    ("command", "prefix"),
    [("scan", "Scan failed: "), ("baseline", "Baseline generation failed: ")],
)
def test_cli_refused_selector_first_stderr_line_is_scan_failed(
    asset_case: Callable[[str, str], AssetCase], capsys: pytest.CaptureFixture[str], command: str, prefix: str
):
    """
    [Integration] cli ds101: verifies a refused selector fails before ``started`` is logged, with exit 2.

    Scenario:
        Given the excluded-directory tree
        When ``scan`` or ``baseline`` runs with ``--include ../outside``
        Then the first stderr line is the failure line naming the parent-step reason, and the exit code is 2.

    Boundaries:
        - Focus: ADR 0006 Contract 6 early validation; threat model M21
        - Fixtures/params: ds101/selection_excluded_directory; scan and baseline
        - Scope: one in-process CLI call

    On failure, first check:
        - cli._validate_selectors runs before the "scan started"/"baseline started" INFO line
    """
    root = asset_case("ds101", "selection_excluded_directory").root
    argv = [command, str(root), "--include", "../outside"]
    if command == "baseline":
        argv += ["--output", str(root / "baseline.json")]

    code = cli.main(argv)
    err = capsys.readouterr().err

    assert code == 2
    assert err.splitlines()[0] == (
        f"{prefix}include value ../outside: parent steps (..) are not allowed; values are relative to the scan root"
    )
    assert "started" not in err


def test_exclude_star_empty_inventory_exits_2(
    asset_case: Callable[[str, str], AssetCase], capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] cli ds101: verifies an invoker selection that admits no document exits 2 (owner ruling R1).

    Scenario:
        Given the excluded-directory tree
        When ``docsentinel scan --exclude '*'`` runs
        Then the scan fails with the fixed empty-selection message and exit code 2, echoing no value.

    Boundaries:
        - Focus: ADR 0006 Contract 5 step 6; threat model T8/M18
        - Fixtures/params: ds101/selection_excluded_directory
        - Scope: one in-process CLI call

    On failure, first check:
        - the R1 check after discover_with_stats() in engine.scan
    """
    root = asset_case("ds101", "selection_excluded_directory").root

    code = cli.main(["scan", str(root), "--exclude", "*"])
    err = problem_output(capsys.readouterr().err)

    assert code == 2
    assert err.splitlines()[0] == (
        "Scan failed: the selection admitted no document; values are relative to the scan root"
    )


def test_zero_hit_include_warning_precedes_empty_selection_error(
    asset_case: Callable[[str, str], AssetCase], capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] cli ds101: verifies the zero-hit include WARNING is logged before the R1 failure.

    Scenario:
        Given the included-directory tree
        When ``docsentinel scan --include 'nothing/*.md'`` runs
        Then stderr warns that the pattern matched no document, then reports the failure, exit 2.

    Boundaries:
        - Focus: ADR 0006 Contract 5 step 6 ordering
        - Fixtures/params: ds101/selection_included_directory
        - Scope: one in-process CLI call

    On failure, first check:
        - the zero-hit loop over Discovery.include_hits in engine.scan
    """
    root = asset_case("ds101", "selection_included_directory").root

    code = cli.main(["scan", str(root), "--include", "nothing/*.md"])
    lines = without_timestamps(problem_output(capsys.readouterr().err)).splitlines()

    assert code == 2
    assert lines[:2] == [
        "[WARNING]: include pattern nothing/*.md matched no document",
        "Scan failed: the selection admitted no document; values are relative to the scan root",
    ]


def test_config_only_empty_inventory_exits_0(
    asset_case: Callable[[str, str], AssetCase], capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] cli ds101: verifies a config that excludes everything keeps today's exit 0.

    Scenario:
        Given the excluded-directory tree with ``exclude = ["*"]`` in docsentinel.toml
        When ``docsentinel scan`` runs without selector flags
        Then it reports no document, prints no problem line and exits 0.

    Boundaries:
        - Focus: ADR 0006 Contract 5 "config-only selection keeps today's behaviour"
        - Fixtures/params: ds101/selection_excluded_directory plus an inline config
        - Scope: one in-process CLI call

    On failure, first check:
        - the R1 check must apply only when include or exclude was given
    """
    root = asset_case("ds101", "selection_excluded_directory").root
    (root / "docsentinel.toml").write_text('exclude = ["*"]\n', encoding="utf-8")

    code = cli.main(["scan", str(root), "--format", "json"])
    captured = capsys.readouterr()

    assert code == 0
    assert _paths(json.loads(captured.out)) == []
    assert problem_output(captured.err) == ""


def test_cli_single_file_target_ignores_selectors_with_warning(
    asset_case: Callable[[str, str], AssetCase], capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] cli ds101: verifies a single-file target ignores the flags with one counts-free WARNING.

    Scenario:
        Given the excluded-directory tree
        When ``docsentinel scan README.md --exclude README.md --include docs/missing`` runs
        Then README.md is still scanned (DS101, exit 1) and stderr holds exactly one WARNING with no value.

    Boundaries:
        - Focus: story decision S9; ADR 0006 Contract 5 step 3; threat model M22
        - Fixtures/params: ds101/selection_excluded_directory
        - Scope: one in-process CLI call

    On failure, first check:
        - the selected_file branch of engine.scan and cli._validate_selectors (no normalisation for a file)
    """
    root = asset_case("ds101", "selection_excluded_directory").root

    code = cli.main(
        ["scan", str(root / "README.md"), "--exclude", "README.md", "--include", "docs/missing", "--format", "json"]
    )
    captured = capsys.readouterr()

    assert code == 1
    assert _ds101_paths(json.loads(captured.out)) == ["README.md"]
    assert without_timestamps(problem_output(captured.err)) == (
        "[WARNING]: --include/--exclude ignored for a single-file scan target\n"
    )


def test_cli_single_file_target_still_shape_checks(
    asset_case: Callable[[str, str], AssetCase], capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] cli ds101: verifies an empty selector value fails for a single-file target too.

    Scenario:
        Given the excluded-directory tree
        When ``docsentinel scan README.md --include=`` runs
        Then the first stderr line is the shape error and the exit code is 2.

    Boundaries:
        - Focus: ADR 0006 Contract 5 step 2 (owner point O4)
        - Fixtures/params: ds101/selection_excluded_directory
        - Scope: one in-process CLI call

    On failure, first check:
        - discovery.check_invoker_selector_shape is called for every target
    """
    root = asset_case("ds101", "selection_excluded_directory").root

    code = cli.main(["scan", str(root / "README.md"), "--include="])
    err = capsys.readouterr().err

    assert code == 2
    assert err.splitlines()[0] == (
        "Scan failed: include values must be nonempty strings; values are relative to the scan root"
    )


def test_cli_baseline_honours_selectors(
    asset_case: Callable[[str, str], AssetCase], capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] cli ds101: verifies ``baseline --exclude`` records findings of the selected documents only.

    Scenario:
        Given the excluded-directory tree
        When ``docsentinel baseline --exclude docs/archive`` runs
        Then the saved baseline equals the library scan's fingerprints, with DS101 only for README.md.

    Boundaries:
        - Focus: story CLI reference (baseline flags)
        - Fixtures/params: ds101/selection_excluded_directory
        - Scope: one in-process CLI call and one library scan for the expected fingerprints

    On failure, first check:
        - cli._run_baseline passes _scan_overrides(args) to scan()
    """
    root = asset_case("ds101", "selection_excluded_directory").root
    output = root.parent / "selection-baseline.json"

    code = cli.main(["baseline", str(root), "--exclude", "docs/archive", "--output", str(output)])
    capsys.readouterr()

    assert code == 0
    recorded = load_baseline(output)
    assert recorded == {fingerprint(finding) for finding in scan(root, exclude=["docs/archive"]).findings}
    assert {entry.split(":")[1] for entry in recorded if entry.startswith("DS101:")} == {"README.md"}


@pytest.mark.parametrize(
    ("contents", "expected"),
    [
        ("", ["include: 2 pattern(s) (default)", "exclude: 3 pattern(s) (default)"]),
        (
            'exclude = [".git", "build"]\n',
            ["include: 2 pattern(s) (default)", "exclude: 2 pattern(s) (docsentinel.toml)"],
        ),
        ('include = ["docs"]\n', ["include: 1 pattern(s) (docsentinel.toml)", "exclude: 3 pattern(s) (default)"]),
    ],
)
def test_doctor_prints_selection_counts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    contents: str,
    expected: list[str],
):
    """
    [Integration] cli ds101: verifies ``doctor`` prints include/exclude counts and their source.

    Scenario:
        Given a current directory with no config, a config setting exclude, or one setting include
        When ``docsentinel doctor`` runs
        Then it prints one include and one exclude line, naming docsentinel.toml only for the key it sets.

    Boundaries:
        - Focus: ADR 0006 Contract 5 doctor lines
        - Fixtures/params: tmp_path as the current directory; three config contents
        - Scope: one in-process CLI call

    On failure, first check:
        - cli._doctor_selection_lines and ConfigSources.project_options
    """
    if contents:
        (tmp_path / "docsentinel.toml").write_text(contents, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert cli.main(["doctor"]) == 0
    lines = capsys.readouterr().out.splitlines()

    assert [line for line in lines if line.startswith(("include:", "exclude:"))] == expected


def _first_problem_line(err: str) -> str:
    """Return the first stderr line that is not an INFO/DEBUG progress line."""
    return problem_output(err).splitlines()[0]


def test_cli_early_validation_uses_canonical_root(
    asset_case: Callable[[str, str], AssetCase],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
):
    """
    [Integration] cli ds101: verifies the CLI early check normalises against the canonical root, not the spelling.

    Scenario:
        Given the included-directory tree, a symlink spelling of it outside the root and a <root>/docs/.. spelling
        When ``docsentinel scan <spelling> --include docs/user --format json`` runs for each spelling
            while the CLI's normalize_invoker_selectors call is recorded
        Then the early call received the resolved root every time, and the scan admits only
            docs/user/guide.md (exit 1, its DS101 finding).

    Boundaries:
        - Focus: threat model M3 (CLI part; the early call passes _resolve_root's directory)
        - Fixtures/params: ds101/selection_included_directory; a symlink in a separate temporary directory
        - Scope: in-process CLI calls with the CLI's normaliser call wrapped

    On failure, first check:
        - cli._validate_selectors passes ``target`` (from _resolve_root), not args.root, as scan_root
    """
    root = asset_case("ds101", "selection_included_directory").root
    alias = tmp_path_factory.mktemp("spelling") / "alias"
    alias.symlink_to(root, target_is_directory=True)
    seen: list[Path] = []
    real_normalize = cli.normalize_invoker_selectors

    def recording_normalize(scan_root: Path, *args: object, **kwargs: object) -> InvokerSelection:
        """Record the scan_root of the CLI's early call and call through."""
        seen.append(scan_root)
        return real_normalize(scan_root, *args, **kwargs)

    monkeypatch.setattr(cli, "normalize_invoker_selectors", recording_normalize)

    for spelling in (str(alias), f"{root}/docs/.."):
        code = cli.main(["scan", spelling, "--include", "docs/user", "--format", "json"])
        report = _report(capsys)
        assert code == 1, spelling
        assert _ds101_paths(report) == ["docs/user/guide.md"], spelling

    assert seen == [root.resolve(), root.resolve()]


def test_cli_absolute_outside_root_message_independent_of_existence(
    asset_case: Callable[[str, str], AssetCase],
    capsys: pytest.CaptureFixture[str],
    tmp_path_factory: pytest.TempPathFactory,
):
    """
    [Integration] cli ds101: verifies an absolute value outside the root gives one message whatever exists there.

    Scenario:
        Given the excluded-directory tree and, outside it, an existing file, an existing directory
            and a path that does not exist
        When ``scan --include <value>`` and ``scan --exclude <value>`` run for each
        Then every run exits 2 before ``scan started`` and the first stderr line, with the value
            replaced by a placeholder, is the same fixed text for every value of the key.

    Boundaries:
        - Focus: threat model M6/M7 (CWE-203: no existence oracle outside the root)
        - Fixtures/params: ds101/selection_excluded_directory; an outside temporary directory
        - Scope: in-process CLI calls

    On failure, first check:
        - Any stat/lstat/realpath of an absolute value before discovery._relative_to_spellings
    """
    root = asset_case("ds101", "selection_excluded_directory").root
    outside = tmp_path_factory.mktemp("outside")
    (outside / "exists.md").write_text("# Outside\n", encoding="utf-8")
    (outside / "dir").mkdir()
    values = [str(outside / "exists.md"), str(outside / "dir"), str(outside / "missing" / "x.md")]

    for key in ("include", "exclude"):
        templates = set()
        for value in values:
            code = cli.main(["scan", str(root), f"--{key}", value])
            err = capsys.readouterr().err
            assert code == 2, value
            assert "started" not in err, value
            templates.add(err.splitlines()[0].replace(value, "<v>"))
        assert templates == {
            f"Scan failed: {key} value <v> is outside the scan root; values are relative to the scan root"
        }


def test_cli_and_engine_use_same_root_spellings(
    asset_case: Callable[[str, str], AssetCase],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
):
    """
    [Integration] cli ds101: verifies the CLI early call and the engine compute identical root spellings.

    Scenario:
        Given the included-directory tree, an outside symlink spelling ``alias`` of it, and an in-root
            symlink ``self`` to the root itself
        When ``scan alias --include alias/docs/user`` and ``scan root/self --include root/self/docs/user``
            run with selector_root_spellings recorded in the CLI and in the engine
        Then both modules called it once per run with the same arguments and got the same spellings
            (canonical root first, then the samefile spelling), and both runs admit only
            docs/user/guide.md: the longest matching spelling wins (M9).

    Boundaries:
        - Focus: threat model M8/M9, A4; ADR 0006 Contract 6 "same inputs for both calls"
        - Fixtures/params: ds101/selection_included_directory; symlinks inside and outside the root
        - Scope: in-process CLI calls with both modules' helper wrapped

    On failure, first check:
        - cli._validate_selectors and engine._apply_invoker_selection call selector_root_spellings
            with (canonical root, root as given)
    """

    root = asset_case("ds101", "selection_included_directory").root.resolve()
    alias = tmp_path_factory.mktemp("spelling") / "alias"
    alias.symlink_to(root, target_is_directory=True)
    (root / "self").symlink_to(root, target_is_directory=True)
    calls: dict[str, list[tuple[object, ...]]] = {"cli": [], "engine": []}

    def recorder(name: str, original: Callable) -> Callable:
        """Return a wrapper of selector_root_spellings that records its arguments and result."""

        def wrapper(canonical_root: Path, spelled_root: object) -> tuple[Path, ...]:
            """Record one call and call through."""
            result = original(canonical_root, spelled_root)
            calls[name].append((canonical_root, os.fspath(spelled_root), result))
            return result

        return wrapper

    monkeypatch.setattr(cli, "selector_root_spellings", recorder("cli", cli.selector_root_spellings))
    monkeypatch.setattr(engine, "selector_root_spellings", recorder("engine", engine.selector_root_spellings))

    for spelling in (str(alias), str(root / "self")):
        code = cli.main(["scan", spelling, "--include", f"{spelling}/docs/user", "--format", "json"])
        report = _report(capsys)
        assert code == 1, spelling
        assert _paths(report) == ["docs/user/guide.md"], spelling

    assert calls["cli"] == calls["engine"]
    assert [entry[2] for entry in calls["cli"]] == [(root, alias), (root, root / "self")]


def test_cli_refused_selector_echo_neutralised(
    asset_case: Callable[[str, str], AssetCase],
    capsys: pytest.CaptureFixture[str],
    _isolated_cli_logging: Path,
):
    """
    [Integration] cli ds101: verifies a refused value holding ESC, ##[ and a bidi override is echoed neutralised.

    Scenario:
        Given the excluded-directory tree
        When ``scan``/``baseline`` run with ``--include``/``--exclude`` set to docs/<ESC>[31m##[x<U+202E>
        Then each exits 2 with the neutralised value on the first stderr line, and neither stderr
            nor the per-run log file holds a raw ESC, U+202E or ``##[``.

    Boundaries:
        - Focus: threat model M21 (A7), T11 (CWE-117 terminal and workflow-command injection)
        - Fixtures/params: ds101/selection_excluded_directory; the autouse per-test log directory
        - Scope: in-process CLI calls

    On failure, first check:
        - discovery._refuse uses safe(value, 200) and cli prints through neutralize_text
    """
    root = asset_case("ds101", "selection_excluded_directory").root
    value = "docs/\x1b[31m##[x‮"
    shown = "docs/\\x1b[31m##\\[x\\u202e"
    reason = "contains a control, format or unsupported character sequence; values are relative to the scan root"

    for command, prefix in (("scan", "Scan failed"), ("baseline", "Baseline generation failed")):
        for key in ("include", "exclude"):
            argv = [command, str(root), f"--{key}={value}"]
            if command == "baseline":
                argv += ["--output", str(root.parent / "never-written.json")]
            code = cli.main(argv)
            err = capsys.readouterr().err
            assert code == 2
            assert err.splitlines()[0] == f"{prefix}: {key} value {shown}: {reason}"
            assert not any(raw in err for raw in ("\x1b", "‮", "##["))

    logs = "".join(path.read_text(encoding="utf-8") for path in _isolated_cli_logging.glob("docsentinel-*.log"))
    assert shown in logs
    assert not any(raw in logs for raw in ("\x1b", "‮", "##["))
    assert not (root.parent / "never-written.json").exists()


def test_cli_warning_echo_bounded(asset_case: Callable[[str, str], AssetCase], capsys: pytest.CaptureFixture[str]):
    """
    [Integration] cli ds101: verifies the unmatched-exclude and zero-hit WARNINGs echo at most 200 characters.

    Scenario:
        Given the excluded-directory tree
        When ``scan --include docs --include zz/<600 q>*.md --exclude docs/::error file=a::pwn/<long missing path>``
            runs
        Then the scan proceeds (exit 1), each WARNING echoes its pattern cut at 200 characters plus ``...``,
            and no stderr line starts with a GitHub workflow command.

    Boundaries:
        - Focus: threat model M22, T11 (bounded echo; a value cannot start a stderr line)
        - Fixtures/params: ds101/selection_excluded_directory
        - Scope: one in-process CLI call

    On failure, first check:
        - safe(pattern, 200) in engine._apply_invoker_selection and the zero-hit loop
    """
    root = asset_case("ds101", "selection_excluded_directory").root
    glob = "zz/" + "q" * 600 + "*.md"
    exclude = "docs/::error file=a::pwn/" + "/".join(f"s{index:02d}" + "a" * 40 for index in range(12))

    code = cli.main(["scan", str(root), "--include", "docs", "--include", glob, "--exclude", exclude])
    lines = without_timestamps(capsys.readouterr().err).splitlines()

    assert code == 1
    warnings = [line for line in lines if line.startswith("[WARNING]: ")]
    assert warnings == [
        f"[WARNING]: exclude pattern {exclude[:200]}... names nothing under the scan root",
        f"[WARNING]: include pattern {glob[:200]}... matched no document",
    ]
    assert not any(line.startswith("::") for line in lines)


def test_selection_info_line_has_counts_only(
    asset_case: Callable[[str, str], AssetCase], capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] cli ds101: verifies the CLI's INFO selection line carries counts only.

    Scenario:
        Given the excluded-directory tree
        When ``scan --include docs --exclude secret-name-xyz --exclude docs/archive`` runs
        Then stderr holds the one selection line with counts (include 1 invoker, exclude 5 with 2 invoker)
            and the value secret-name-xyz appears nowhere on stderr.

    Boundaries:
        - Focus: threat model M22 at the CLI surface (the library-level twin is in test_discovery_selectors.py)
        - Fixtures/params: ds101/selection_excluded_directory
        - Scope: one in-process CLI call

    On failure, first check:
        - engine._log_selection (patterns only at DEBUG, never INFO)
    """
    root = asset_case("ds101", "selection_excluded_directory").root

    code = cli.main(
        ["scan", str(root), "--include", "docs", "--exclude", "secret-name-xyz", "--exclude", "docs/archive"]
    )
    err = capsys.readouterr().err

    assert code == 0
    assert [line for line in without_timestamps(err).splitlines() if line.startswith("[INFO]: selection:")] == [
        "[INFO]: selection: include 1 pattern(s) (invoker), exclude 5 pattern(s) (3 configured, 2 invoker)"
    ]
    assert "secret-name-xyz" not in err


def test_cli_config_literal_directory_exclude_matches_flag(
    asset_case: Callable[[str, str], AssetCase], capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] cli ds101: verifies a literal directory exclude in config removes the same documents as the flag.

    Scenario:
        Given the excluded-directory tree with ``exclude = [".git", "docs/archive"]`` in docsentinel.toml
        When ``docsentinel scan --format json`` runs without flags
        Then docs/archive/old.md is not inventoried and only README.md keeps its DS101 finding, as with
            ``--exclude docs/archive``.

    Boundaries:
        - Focus: Story 02.0 acceptance "the same value in config does the same"; ADR 0006 Contract 2 literal row
        - Fixtures/params: ds101/selection_excluded_directory plus an inline config
        - Scope: two in-process CLI calls

    On failure, first check:
        - discovery.prunes_directory for configured literals
    """
    root = asset_case("ds101", "selection_excluded_directory").root
    (root / "docsentinel.toml").write_text('exclude = [".git", "docs/archive"]\n', encoding="utf-8")

    assert cli.main(["scan", str(root), "--format", "json"]) == 1
    from_config = _report(capsys)
    (root / "docsentinel.toml").write_text('exclude = [".git"]\n', encoding="utf-8")
    assert cli.main(["scan", str(root), "--exclude", "docs/archive", "--format", "json"]) == 1
    from_flag = _report(capsys)

    assert _paths(from_config) == _paths(from_flag) == ["README.md", "docs/guide.md"]
    assert _ds101_paths(from_config) == _ds101_paths(from_flag) == ["README.md"]


@pytest.mark.parametrize(
    ("flags", "message"),
    [
        (["--include=x"] * 257, "include accepts at most 256 values"),
        (["--exclude=" + "x" * 1025], "exclude value is longer than 1024 characters"),
    ],
)
def test_cli_single_file_target_oversized_selectors_exit_2(
    asset_case: Callable[[str, str], AssetCase], capsys: pytest.CaptureFixture[str], flags: list[str], message: str
):
    """
    [Integration] cli ds101: verifies an oversized selector list or value fails for a single-file target too.

    Scenario:
        Given the excluded-directory tree
        When ``docsentinel scan README.md`` runs with 257 --include values or a 1,025-character --exclude
        Then the first stderr line is the fixed shape error and the exit code is 2.

    Boundaries:
        - Focus: ADR 0006 owner point O4; Contract 5 step 2
        - Fixtures/params: ds101/selection_excluded_directory; flags, message
        - Scope: one in-process CLI call

    On failure, first check:
        - cli._validate_selectors runs check_invoker_selector_shape for a file target

    :param flags: The oversized selector flags.
    :param message: The expected message prefix.
    """
    root = asset_case("ds101", "selection_excluded_directory").root

    code = cli.main(["scan", str(root / "README.md"), *flags])
    err = capsys.readouterr().err

    assert code == 2
    assert err.splitlines()[0] == f"Scan failed: {message}; values are relative to the scan root"
