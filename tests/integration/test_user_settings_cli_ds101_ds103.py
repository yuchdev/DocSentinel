"""Integration tests: user settings and JSON config through the CLI (Milestone 0009 Story 03.0, Task 06 Step 5).

The CLI runs in process (``cli.main``) over the existing ``ds103/unresolvable_path_file`` and
``ds101/dangling_file_link`` asset cases. User settings files are written in the test body,
in a fake home created with ``tmp_path_factory`` (outside the scan root) and selected through
``DOCSENTINEL_SETTINGS`` or the default location under ``HOME``; the real home and the real
settings file are never touched. Covers precedence (user, project, CLI), ``--no-user-settings``
on ``scan``/``baseline``/``doctor``, ``--config FILE.json``, ``init --user``, the ``doctor``
source lines, the INFO ``config:`` line, exit codes and ``Scan failed:`` messages, and the
U1, U2, U4, U11, U15, U16 and F1 tests of
docs/security/threat-model-0009-user-settings-2026-11-17.md. The FIFO and chmod tests are
POSIX-only and run under a ``SIGALRM`` timeout guard (amendment A11).
"""

from __future__ import annotations

import json
import os
import re
import signal
import stat
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pytest

from docsentinel import cli
from docsentinel.config import _BOOL_OPTIONS, _ENUM_OPTIONS, USER_SETTINGS_ENV, Config, ConfigError, load_config
from tests.asset_helpers import AssetCase
from tests.log_helpers import problem_output, without_timestamps

_REPO_ROOT = Path(__file__).resolve().parents[2]
_POSIX_ONLY = pytest.mark.skipif(os.name != "posix", reason="POSIX modes, FIFOs and SIGALRM")

#: Seconds a FIFO or chmod test may take before the guard fails it instead of hanging.
_GUARD_SECONDS = 60

#: A marker placed in user files; it must never reach stdout, stderr or the log file.
_SENTINEL = "SENT_4d2e"

_DEFAULT_SHOWN = "~/.local/share/docsentinel/settings.json"


@dataclass
class UserHome:
    """A fake home for one test, outside the scan root.

    :ivar home: The fake home directory (HOME points here).
    :ivar monkeypatch: The test's monkeypatch, used to set the environment.
    """

    home: Path
    monkeypatch: pytest.MonkeyPatch

    def write(self, content: Any, relative: str = "settings.json", *, select: bool = True) -> Path:
        """Write a user settings file under the home with owner-only modes.

        :param content: A JSON-serialisable object, a ``str`` or ``bytes`` written verbatim.
        :param relative: The path below the home.
        :param select: Whether to point ``DOCSENTINEL_SETTINGS`` at the file.
        :returns: The file path.
        """
        path = self.home / relative
        _private_dirs(self.home, path.parent)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
        os.chmod(path, 0o600)
        if select:
            self.monkeypatch.setenv(USER_SETTINGS_ENV, str(path))
        return path

    def write_default(self, content: Any) -> Path:
        """Write the default-location file and unset ``DOCSENTINEL_SETTINGS``/``XDG_DATA_HOME``.

        :param content: The settings object.
        :returns: The file path (``~/.local/share/docsentinel/settings.json``).
        """
        self.use_default_location()
        return self.write(content, ".local/share/docsentinel/settings.json", select=False)

    def use_default_location(self):
        """Resolve the settings file from HOME: unset DOCSENTINEL_SETTINGS and XDG_DATA_HOME."""
        self.monkeypatch.delenv(USER_SETTINGS_ENV, raising=False)
        self.monkeypatch.delenv("XDG_DATA_HOME", raising=False)


def _private_dirs(base: Path, directory: Path):
    """Create ``directory`` below ``base`` with every new component at mode ``0o700``.

    :param base: An existing owner-only directory.
    :param directory: The directory to create (may equal ``base``).
    """
    current = base
    for part in directory.relative_to(base).parts:
        current = current / part
        current.mkdir(exist_ok=True)
        os.chmod(current, 0o700)


@pytest.fixture
def user_home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> UserHome:
    """Return a fake owner-only home outside ``tmp_path`` and point HOME at it.

    :param tmp_path_factory: Creates the home outside the scan root.
    :param monkeypatch: Restores HOME and the settings variables after the test.
    :returns: The fake home helper; DOCSENTINEL_SETTINGS stays ``off`` until a file is written.
    """
    home = tmp_path_factory.mktemp("fake-home")
    os.chmod(home, 0o700)
    monkeypatch.setenv("HOME", str(home))
    return UserHome(home=home, monkeypatch=monkeypatch)


@contextmanager
def _timeout_guard(seconds: int = _GUARD_SECONDS) -> Iterator[None]:
    """Fail the enclosed block with ``TimeoutError`` after ``seconds`` (``SIGALRM``).

    :param seconds: The limit.
    :returns: A context manager.
    """

    def expire(signum: int, frame: object):
        """Raise inside the blocked call so the test fails instead of hanging."""
        raise TimeoutError(f"blocked for more than {seconds} seconds")

    previous = signal.signal(signal.SIGALRM, expire)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def _run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    """Run ``docsentinel`` in process and return ``(exit code, stdout, stderr)``.

    :param capsys: Captures the output.
    :param argv: The command line after ``docsentinel``.
    :returns: The exit code and the captured streams.
    """
    capsys.readouterr()
    code = cli.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _ds103_count(report: str) -> int:
    """Return the number of DS103 problems in a schema-2 JSON report.

    :param report: The JSON report text.
    :returns: The DS103 problem count.
    """
    document = json.loads(report)
    return sum(1 for doc in document["documents"] for problem in doc["problems"] if problem["rule"] == "DS103")


def _config_line(stderr: str) -> str:
    """Return the single INFO ``config:`` line of one CLI run.

    :param stderr: The captured stderr.
    :returns: The text after ``[<timestamp>][INFO]: config: ``.
    """
    lines = [line for line in without_timestamps(stderr).splitlines() if line.startswith("[INFO]: config: ")]
    assert len(lines) == 1, stderr
    return lines[0][len("[INFO]: config: ") :]


def _log_text(log_dir: Path) -> str:
    """Return the concatenated per-run log files in ``log_dir``.

    :param log_dir: The isolated ``DOCSENTINEL_LOG_DIR``.
    :returns: Their text.
    """
    return "".join(path.read_text(encoding="utf-8") for path in sorted(log_dir.glob("docsentinel-*.log")))


# --- Precedence: user, then project, then CLI ---------------------------------------------------------


def test_user_strict_scope_turns_ds103_on(
    asset_case: Callable[[str, str], AssetCase], user_home: UserHome, capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] user settings ds103: a user reference_scope = "strict" turns DS103 on with no project config.

    Scenario:
        Given the DS103 unresolvable-path asset, no project config, and a user file setting
            reference_scope to "strict"
        When docsentinel scan --format json runs, without and with --strict
        Then one DS103 problem is reported, the run exits 0 (warning) and 1 under --strict;
            with DOCSENTINEL_SETTINGS=off the same scan reports none.

    Boundaries:
        - Focus: story acceptance criterion 1 (user layer alone)
        - Fixtures/params: asset_case (ds103/unresolvable_path_file), user_home, capsys
        - Scope: in-process CLI

    On failure, first check:
        - load_config_with_sources in cli._run_scan
    """
    root = asset_case("ds103", "unresolvable_path_file").root
    user_home.write({"reference_scope": "strict"})

    code, out, err = _run(capsys, "scan", str(root), "--format", "json")
    strict_code, _, _ = _run(capsys, "scan", str(root), "--format", "json", "--strict")

    assert (code, strict_code) == (0, 1)
    assert _ds103_count(out) == 1
    assert _config_line(err) == "user settings loaded (reference_scope), project none"
    user_home.monkeypatch.setenv(USER_SETTINGS_ENV, "off")
    off_code, off_out, off_err = _run(capsys, "scan", str(root), "--format", "json", "--strict")
    assert (off_code, _ds103_count(off_out)) == (0, 0)
    assert _config_line(off_err) == "user settings off, project none"


def test_project_scope_overrides_user_and_cli_overrides_both(
    asset_case: Callable[[str, str], AssetCase], user_home: UserHome, capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] user settings ds103: the project value beats the user value; --reference-scope beats both.

    Scenario:
        Given a user file with reference_scope "strict" and a project docsentinel.toml with "links"
        When scan runs plainly, with --reference-scope strict, and (project removed) with
            --reference-scope links
        Then DS103 is off, on, and off respectively.

    Boundaries:
        - Focus: story acceptance criterion 1 (layers 2, 3 and 4; plan C1)
        - Fixtures/params: asset_case (ds103/unresolvable_path_file), user_home, capsys
        - Scope: in-process CLI

    On failure, first check:
        - The {**user, **project} merge and the CLI's dataclasses.replace
    """
    root = asset_case("ds103", "unresolvable_path_file").root
    user_home.write({"reference_scope": "strict"})
    project = root / "docsentinel.toml"
    project.write_text('reference_scope = "links"\n', encoding="utf-8")

    _, project_wins, err = _run(capsys, "scan", str(root), "--format", "json")
    _, cli_enables, _ = _run(capsys, "scan", str(root), "--format", "json", "--reference-scope", "strict")
    project.unlink()
    _, cli_disables, _ = _run(capsys, "scan", str(root), "--format", "json", "--reference-scope", "links")

    assert _ds103_count(project_wins) == 0
    assert _config_line(err) == "user settings loaded (reference_scope), project docsentinel.toml"
    assert _ds103_count(cli_enables) == 1
    assert _ds103_count(cli_disables) == 0


def test_no_user_settings_on_scan_baseline_and_doctor(
    asset_case: Callable[[str, str], AssetCase],
    user_home: UserHome,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """
    [Integration] user settings ds103: --no-user-settings ignores the file on scan, baseline and doctor.

    Scenario:
        Given a user file with reference_scope "strict" over the DS103 asset
        When scan, baseline and doctor run with and without --no-user-settings, and then with a
            relative (invalid) DOCSENTINEL_SETTINGS
        Then the flag drops DS103 from the scan and the baseline, doctor prints
            "user settings: off (--no-user-settings)", and with the flag the invalid variable is
            never read (exit 0) while without it scan exits 2.

    Boundaries:
        - Focus: --no-user-settings (story CLI reference; threat model U13 flag precedence)
        - Fixtures/params: asset_case, user_home, tmp_path_factory, monkeypatch, capsys
        - Scope: in-process CLI; doctor runs in the scan root

    On failure, first check:
        - user_settings=not args.no_user_settings in each command
    """
    root = asset_case("ds103", "unresolvable_path_file").root
    user_home.write({"reference_scope": "strict"})
    out_dir = tmp_path_factory.mktemp("baselines")
    monkeypatch.chdir(root)

    _, with_user, _ = _run(capsys, "scan", str(root), "--format", "json")
    _, without_user, err = _run(capsys, "scan", str(root), "--format", "json", "--no-user-settings")
    _run(capsys, "baseline", str(root), "--output", str(out_dir / "with.json"))
    _run(capsys, "baseline", str(root), "--output", str(out_dir / "without.json"), "--no-user-settings")
    _, doctor_on, _ = _run(capsys, "doctor")
    _, doctor_off, _ = _run(capsys, "doctor", "--no-user-settings")

    assert (_ds103_count(with_user), _ds103_count(without_user)) == (1, 0)
    assert _config_line(err) == "user settings off, project none"
    with_fingerprints = json.loads((out_dir / "with.json").read_text(encoding="utf-8"))["fingerprints"]
    without_fingerprints = json.loads((out_dir / "without.json").read_text(encoding="utf-8"))["fingerprints"]
    assert [item.split(":")[0] for item in with_fingerprints] == ["DS103"]
    assert without_fingerprints == []
    assert "reference scope: strict (DS103 on)" in doctor_on
    assert "user settings: off (--no-user-settings)" in doctor_off.splitlines()
    assert "reference scope: links (DS103 off)" in doctor_off.splitlines()

    monkeypatch.setenv(USER_SETTINGS_ENV, "relative/garbage.json")
    flagged = [
        _run(capsys, "scan", str(root), "--no-user-settings")[0],
        _run(capsys, "baseline", str(root), "--output", str(out_dir / "g.json"), "--no-user-settings")[0],
        _run(capsys, "doctor", "--no-user-settings")[0],
    ]
    code, _, garbage_err = _run(capsys, "scan", str(root))
    assert flagged == [0, 0, 0]
    assert code == 2
    assert problem_output(garbage_err).splitlines()[0] == (
        f'Scan failed: {USER_SETTINGS_ENV} must be an absolute path or "off"'
    )
    assert "garbage" not in garbage_err


def test_config_json_file_is_project_layer_over_user(
    asset_case: Callable[[str, str], AssetCase],
    user_home: UserHome,
    tmp_path_factory: pytest.TempPathFactory,
    capsys: pytest.CaptureFixture[str],
):
    """
    [Integration] user settings ds101 ds103: --config FILE.json is read as JSON and layered over the user file.

    Scenario:
        Given the DS101 and DS103 assets in one tree, a user file ignoring DS101, and a project
            config.JSON setting reference_scope "strict"
        When scan --config config.JSON runs; then with a duplicate-key JSON config
        Then DS103 is reported, DS101 stays ignored by the user layer (exit 0), the INFO line
            names the JSON file; the malformed config exits 2 with the reader's message.

    Boundaries:
        - Focus: story S2 (suffix rule, case-insensitive) and "user settings still apply beneath it"
        - Fixtures/params: asset_case (ds101/dangling_file_link, ds103/unresolvable_path_file),
            user_home, tmp_path_factory, capsys
        - Scope: in-process CLI

    On failure, first check:
        - _read_project_options suffix check and the merge order
    """
    asset_case("ds101", "dangling_file_link")
    root = asset_case("ds103", "unresolvable_path_file").root
    user_home.write({"ignore": ["DS101"]})
    configs = tmp_path_factory.mktemp("configs")
    json_config = configs / "config.JSON"
    json_config.write_text('{"reference_scope": "strict"}', encoding="utf-8")
    broken = configs / "broken.json"
    broken.write_text('{"profile": "fast", "profile": "deep"}', encoding="utf-8")

    code, out, err = _run(capsys, "scan", str(root), "--format", "json", "--config", str(json_config))
    broken_code, _, broken_err = _run(capsys, "scan", str(root), "--config", str(broken))

    rules = {problem["rule"] for doc in json.loads(out)["documents"] for problem in doc["problems"]}
    assert code == 0
    assert rules == {"DS103"}
    assert _config_line(err) == "user settings loaded (ignore), project config.JSON"
    assert broken_code == 2
    assert problem_output(broken_err).splitlines()[0] == "Scan failed: Cannot read JSON config: duplicate key profile"


_MALFORMED: list[tuple[str, Any, str]] = [
    (
        "duplicate",
        '{"profile": "' + _SENTINEL + '", "profile": "fast"}',
        "Cannot read JSON config: duplicate key profile",
    ),
    (
        "bom",
        b"\xef\xbb\xbf" + ('{"profile": "' + _SENTINEL + '"}').encode(),
        "Cannot read JSON config: starts with a byte-order mark",
    ),
    (
        "nan",
        '{"select": ["' + _SENTINEL + '"], "max_grade_level": NaN}',
        "Cannot read JSON config: NaN and Infinity are not allowed",
    ),
    ("null", '{"select": ["' + _SENTINEL + '", null]}', "Cannot read JSON config: null is not allowed; omit the key"),
    (
        "oversized",
        '{"profile": "' + _SENTINEL + '"' + " " * 1_048_576 + "}",
        "Cannot read JSON config: larger than 1 MiB",
    ),
    (
        "nesting",
        '{"select": ' + "[" * 100_000 + '"' + _SENTINEL + '"' + "]" * 100_000 + "}",
        "Cannot read JSON config: nested too deeply",
    ),
    (
        "refused_key",
        '{"include": ["' + _SENTINEL + '"]}',
        "repository-relative options cannot be set in user settings: include",
    ),
    ("bad_value", '{"profile": "' + _SENTINEL + '"}', "profile must be fast, standard, or deep"),
]


@pytest.mark.parametrize(("case", "content", "message"), _MALFORMED, ids=[case for case, _, _ in _MALFORMED])
def test_malformed_user_file_exits_2_without_echo(
    asset_case: Callable[[str, str], AssetCase],
    user_home: UserHome,
    tmp_path_factory: pytest.TempPathFactory,
    capsys: pytest.CaptureFixture[str],
    _isolated_cli_logging: Path,
    case: str,
    content: Any,
    message: str,
):
    """
    [Integration] user settings ds101: a malformed or refused user file exits 2 naming the file, without echo.

    Scenario:
        Given the DS101 asset and a user file that has a duplicate key, a BOM, NaN, a null, more
            than 1 MiB, deep nesting, a C6 key, or an invalid value, each around a sentinel
        When scan and baseline run
        Then both exit 2, the first problem line is "Scan failed: user settings ~/settings.json:
            <reason>" (or "Baseline generation failed: ..."), and the sentinel appears in no output
            or log file.

    Boundaries:
        - Focus: story acceptance criteria 2 and 4; ConfigError path of the CLI
        - Fixtures/params: asset_case (ds101/dangling_file_link), user_home, tmp_path_factory,
            capsys, _isolated_cli_logging, case/content/message
        - Scope: in-process CLI

    On failure, first check:
        - The (ConfigError, ValueError) clause of _run_scan/_run_baseline
    """
    root = asset_case("ds101", "dangling_file_link").root
    user_home.write(content)
    output = tmp_path_factory.mktemp("out") / "baseline.json"

    scan_code, scan_out, scan_err = _run(capsys, "scan", str(root))
    baseline_code, baseline_out, baseline_err = _run(capsys, "baseline", str(root), "--output", str(output))

    assert (scan_code, baseline_code) == (2, 2)
    assert problem_output(scan_err).splitlines()[0] == f"Scan failed: user settings ~/settings.json: {message}"
    assert problem_output(baseline_err).splitlines()[0] == (
        f"Baseline generation failed: user settings ~/settings.json: {message}"
    )
    assert not output.exists()
    for text in (scan_out, scan_err, baseline_out, baseline_err, _log_text(_isolated_cli_logging)):
        assert _SENTINEL not in text, case


# --- doctor -----------------------------------------------------------------------------------------


def test_doctor_lines_for_each_user_state(
    asset_case: Callable[[str, str], AssetCase],
    user_home: UserHome,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """
    [Integration] user settings ds103: doctor prints the source lines for loaded, missing, off and no-home.

    Scenario:
        Given the DS103 asset as the current directory with a one-option docsentinel.toml
        When doctor runs with a two-option default-location user file, with no file, with
            DOCSENTINEL_SETTINGS=off and with a relative HOME
        Then it prints the tilde path with "(loaded, 2 options)", "(missing)", "off
            (DOCSENTINEL_SETTINGS=off)" and "none (home directory unknown)", the project line
            "docsentinel.toml (1 option)", the project-wins reference scope, and exits 0.

    Boundaries:
        - Focus: _doctor_config_source_lines (story "doctor adds")
        - Fixtures/params: asset_case, user_home, monkeypatch, capsys
        - Scope: in-process CLI in the scan root

    On failure, first check:
        - The user_state branches of _doctor_config_source_lines
    """
    root = asset_case("ds103", "unresolvable_path_file").root
    (root / "docsentinel.toml").write_text('reference_scope = "links"\n', encoding="utf-8")
    monkeypatch.chdir(root)
    settings = user_home.write_default({"reference_scope": "strict", "profile": "fast"})

    loaded = _run(capsys, "doctor")
    settings.unlink()
    missing = _run(capsys, "doctor")
    monkeypatch.setenv(USER_SETTINGS_ENV, "off")
    off = _run(capsys, "doctor")
    user_home.use_default_location()
    monkeypatch.setenv("HOME", ".")
    no_home = _run(capsys, "doctor")

    assert [result[0] for result in (loaded, missing, off, no_home)] == [0, 0, 0, 0]
    assert f"user settings: {_DEFAULT_SHOWN} (loaded, 2 options)" in loaded[1].splitlines()
    assert "project config: docsentinel.toml (1 option)" in loaded[1].splitlines()
    assert "reference scope: links (DS103 off)" in loaded[1].splitlines()
    assert f"user settings: {_DEFAULT_SHOWN} (missing)" in missing[1].splitlines()
    assert f"user settings: off ({USER_SETTINGS_ENV}=off)" in off[1].splitlines()
    assert "user settings: none (home directory unknown)" in no_home[1].splitlines()


def test_doctor_survives_oversized_toml_integer(
    asset_case: Callable[[str, str], AssetCase], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] user settings ds103 F1: a TOML integer past the digit limit is a config error, not a crash.

    Scenario:
        Given a project docsentinel.toml whose max_grade_level has 5,000 digits (over Python's
            4,300-digit conversion limit)
        When doctor runs in that directory, and scan runs on it
        Then doctor exits 0 and prints "config sources: error: Cannot read <file>: number out of
            range" without a traceback, and scan exits 2 with the same reason.

    Boundaries:
        - Focus: the ValueError clause of _load_toml_table (threat model F1)
        - Fixtures/params: asset_case (ds103/unresolvable_path_file), monkeypatch, capsys
        - Scope: in-process CLI

    On failure, first check:
        - _load_toml_table maps ValueError to "number out of range"
    """
    root = asset_case("ds103", "unresolvable_path_file").root
    toml = root / "docsentinel.toml"
    toml.write_text("max_grade_level = " + "9" * 5000 + "\n", encoding="utf-8")
    monkeypatch.chdir(root)

    doctor_code, doctor_out, doctor_err = _run(capsys, "doctor")
    scan_code, _, scan_err = _run(capsys, "scan", str(root))

    assert doctor_code == 0
    assert f"config sources: error: Cannot read {toml}: number out of range" in doctor_out.splitlines()
    assert "Traceback" not in doctor_out + doctor_err + scan_err
    assert scan_code == 2
    assert problem_output(scan_err).splitlines()[0] == f"Scan failed: Cannot read {toml}: number out of range"


# --- INFO config line (U16) ------------------------------------------------------------------------


def test_info_config_line_names_user_options_not_values(
    asset_case: Callable[[str, str], AssetCase],
    user_home: UserHome,
    tmp_path_factory: pytest.TempPathFactory,
    capsys: pytest.CaptureFixture[str],
    _isolated_cli_logging: Path,
):
    """
    [Integration] user settings ds101 U16: the INFO config line names the user options, never their values.

    Scenario:
        Given a user file setting ignore to ["DS999"], max_grade_level 13.37 and reference_scope
        When scan and baseline run
        Then each logs "config: user settings loaded (ignore, max_grade_level, reference_scope),
            project none" once, and neither "DS999" nor "13.37" appears on stderr or in the log file.

    Boundaries:
        - Focus: cli._config_sources_text (amendment A10)
        - Fixtures/params: asset_case (ds101/dangling_file_link), user_home, tmp_path_factory,
            capsys, _isolated_cli_logging
        - Scope: in-process CLI

    On failure, first check:
        - That _config_sources_text uses ConfigSources.user_options only
    """
    root = asset_case("ds101", "dangling_file_link").root
    user_home.write({"ignore": ["DS999"], "max_grade_level": 13.37, "reference_scope": "strict"})
    output = tmp_path_factory.mktemp("out") / "baseline.json"

    _, _, scan_err = _run(capsys, "scan", str(root))
    _, _, baseline_err = _run(capsys, "baseline", str(root), "--output", str(output))

    expected = "user settings loaded (ignore, max_grade_level, reference_scope), project none"
    assert _config_line(scan_err) == expected
    assert _config_line(baseline_err) == expected
    log = _log_text(_isolated_cli_logging)
    assert f"config: {expected}" in log
    for text in (scan_err, baseline_err, log):
        assert "DS999" not in text
        assert "13.37" not in text


def _allowed_default_options(count: int) -> dict[str, object]:
    """Return ``count`` allowed user options set to their default values, by sorted name.

    :param count: How many options.
    :returns: The options mapping.
    """
    defaults = Config()
    names = sorted({*_BOOL_OPTIONS, *_ENUM_OPTIONS})[:count]
    assert len(names) == count
    return {name: getattr(defaults, name) for name in names}


@pytest.mark.parametrize("count", [20, 21, 25])
def test_info_config_line_truncates_after_20_names(
    asset_case: Callable[[str, str], AssetCase],
    user_home: UserHome,
    capsys: pytest.CaptureFixture[str],
    count: int,
):
    """
    [Integration] user settings ds101 U16: the INFO line lists at most 20 sorted names, then "and N more".

    Scenario:
        Given a user file setting 20, 21 or 25 allowed options to their defaults
        When scan runs
        Then the line lists the first 20 sorted names, followed by "and N more" only past 20.

    Boundaries:
        - Focus: MAX_LOGGED_OPTION_NAMES in cli._config_sources_text
        - Fixtures/params: asset_case (ds101/dangling_file_link), user_home, capsys, count
        - Scope: in-process CLI

    On failure, first check:
        - The slice and the "and N more" suffix
    """
    root = asset_case("ds101", "dangling_file_link").root
    options = _allowed_default_options(count)
    user_home.write(options)
    names = sorted(options)
    listed = ", ".join(names[:20]) + (f" and {count - 20} more" if count > 20 else "")

    _, _, err = _run(capsys, "scan", str(root))

    assert _config_line(err) == f"user settings loaded ({listed}), project none"


# --- U11: no absolute home in INFO, doctor or the log file ---------------------------------------------


@pytest.mark.parametrize("spelling", ["plain", "symlinked"])
def test_no_absolute_home_in_info_or_doctor(
    asset_case: Callable[[str, str], AssetCase],
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    _isolated_cli_logging: Path,
    spelling: str,
):
    """
    [Integration] user settings ds103 U11: the fake home's absolute path never reaches stdout, stderr or the log.

    Scenario:
        Given HOME pointing at a fake home (directly, or through a symlink) holding a default-
            location user file, and the DS103 asset as the current directory
        When scan -v, baseline and doctor run, and then a scan with a refused key
        Then doctor shows "~/.local/share/docsentinel/settings.json (loaded, 1 option)", and no
            output or log file contains the home's absolute path or its real path.

    Boundaries:
        - Focus: _tilde_path for HOME and its realpath (threat model M15)
        - Fixtures/params: asset_case, tmp_path_factory, monkeypatch, capsys,
            _isolated_cli_logging, spelling
        - Scope: in-process CLI; DEBUG level on stderr via -v

    On failure, first check:
        - Every rendering of ConfigSources.user goes through _tilde_path
    """
    root = asset_case("ds103", "unresolvable_path_file").root
    real_home = tmp_path_factory.mktemp("real-home")
    os.chmod(real_home, 0o700)
    home = real_home
    if spelling == "symlinked":
        home = tmp_path_factory.mktemp("links") / "home-link"
        home.symlink_to(real_home, target_is_directory=True)
    monkeypatch.setenv("HOME", str(home))
    helper = UserHome(home=real_home, monkeypatch=monkeypatch)
    settings = helper.write_default({"reference_scope": "strict"})
    monkeypatch.chdir(root)
    output = tmp_path_factory.mktemp("out") / "baseline.json"

    outputs = [
        _run(capsys, "scan", str(root), "-v"),
        _run(capsys, "baseline", str(root), "--output", str(output), "-v"),
        _run(capsys, "doctor"),
    ]
    settings.write_text('{"exclude": ["x"]}', encoding="utf-8")
    refused = _run(capsys, "scan", str(root))

    assert f"user settings: {_DEFAULT_SHOWN} (loaded, 1 option)" in outputs[2][1].splitlines()
    assert refused[0] == 2
    assert f"Scan failed: user settings {_DEFAULT_SHOWN}: " in refused[2]
    texts = [text for _, out, err in (*outputs, refused) for text in (out, err)]
    texts.append(_log_text(_isolated_cli_logging))
    for text in texts:
        assert str(home) not in text
        assert str(real_home) not in text
        assert os.path.realpath(real_home) not in text


# --- U1, U2: real chmod and a real FIFO -----------------------------------------------------------


@_POSIX_ONLY
@pytest.mark.parametrize(("mode", "phrase"), [(0o620, "file"), (0o602, "file"), (0o777, "directory")])
def test_cli_group_writable_settings_exits_2(
    asset_case: Callable[[str, str], AssetCase],
    user_home: UserHome,
    capsys: pytest.CaptureFixture[str],
    mode: int,
    phrase: str,
):
    """
    [Integration] user settings ds101 U1: a group/world-writable settings file or directory exits 2 (real chmod).

    Scenario:
        Given a user file that would ignore DS101, made group- or world-writable with chmod, or
            held in a world-writable directory
        When scan runs over the DS101 asset under a timeout guard
        Then it exits 2 with the gate phrase; after chmod go-w the same file loads and DS101 is
            ignored (exit 0).

    Boundaries:
        - Focus: R2/R3 on real modes (geteuid() owns the files)
        - Fixtures/params: asset_case (ds101/dangling_file_link), user_home, capsys, mode, phrase
        - Scope: in-process CLI; POSIX only; SIGALRM guard

    On failure, first check:
        - _check_user_settings_descriptor and _check_user_settings_directories
    """
    root = asset_case("ds101", "dangling_file_link").root
    settings = user_home.write({"ignore": ["DS101"]}, "cfg/settings.json")
    target = settings if phrase == "file" else settings.parent
    expected = (
        "writable by group or others (run chmod go-w on it)"
        if phrase == "file"
        else "its directory is owned by another user or writable by others"
    )
    os.chmod(target, mode)
    try:
        with _timeout_guard():
            code, _, err = _run(capsys, "scan", str(root))
    finally:
        os.chmod(target, 0o600 if phrase == "file" else 0o700)

    assert code == 2
    assert problem_output(err).splitlines()[0] == f"Scan failed: user settings ~/cfg/settings.json: {expected}"
    with _timeout_guard():
        fixed_code, _, _ = _run(capsys, "scan", str(root))
    assert fixed_code == 0


@_POSIX_ONLY
def test_fifo_settings_file_refused_without_blocking(
    asset_case: Callable[[str, str], AssetCase], user_home: UserHome, capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] user settings ds101 U2: a FIFO at the settings path is refused without blocking (real mkfifo).

    Scenario:
        Given DOCSENTINEL_SETTINGS naming a FIFO with no writer
        When load_config and then scan run under a timeout guard
        Then both refuse it with "not a regular file" (exit 2) instead of hanging on open().

    Boundaries:
        - Focus: the os.stat pre-check and O_NONBLOCK of _read_config_once (R7)
        - Fixtures/params: asset_case (ds101/dangling_file_link), user_home, capsys
        - Scope: library and in-process CLI; POSIX only; SIGALRM guard

    On failure, first check:
        - That no open happens before S_ISREG is confirmed
    """
    root = asset_case("ds101", "dangling_file_link").root
    fifo = user_home.home / "fifo.json"
    os.mkfifo(fifo, 0o600)
    user_home.monkeypatch.setenv(USER_SETTINGS_ENV, str(fifo))
    expected = "user settings ~/fifo.json: Cannot read JSON config: not a regular file"

    with _timeout_guard():
        with pytest.raises(ConfigError) as caught:
            load_config(root)
        code, _, err = _run(capsys, "scan", str(root))

    assert str(caught.value) == expected
    assert code == 2
    assert problem_output(err).splitlines()[0] == f"Scan failed: {expected}"


# --- U4: CI workflow ---------------------------------------------------------------------------------

_DOCSENTINEL_COMMAND = re.compile(r"\bdocsentinel (?:scan|baseline|doctor|init|rules)\b|-p docsentinel\.pytest_plugin")
_JOB_HEADER = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")


def _workflow_jobs(text: str) -> dict[str, list[str]]:
    """Split a workflow's ``jobs:`` mapping into job name -> its non-comment lines.

    :param text: The workflow YAML text.
    :returns: The jobs in file order.
    """
    jobs: dict[str, list[str]] = {}
    current: Optional[str] = None
    in_jobs = False
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            in_jobs = line.rstrip() == "jobs:"
            current = None
            continue
        header = _JOB_HEADER.match(line)
        if in_jobs and header:
            current = header.group(1)
            jobs[current] = []
        elif in_jobs and current is not None:
            jobs[current].append(line)
    return jobs


def _job_env(lines: list[str]) -> dict[str, str]:
    """Return the job-level ``env:`` mapping (raw value text) of one job's lines.

    :param lines: The job's lines (indented by four or more spaces).
    :returns: Variable name -> value text as written (quotes kept).
    """
    env: dict[str, str] = {}
    inside = False
    for line in lines:
        indent = len(line) - len(line.lstrip(" "))
        if indent == 4:
            inside = line.strip() == "env:"
            continue
        if inside and indent == 6 and ":" in line:
            name, value = line.strip().split(":", 1)
            env[name] = value.strip()
    return env


def test_ci_workflow_sets_settings_off():
    """
    [Integration] user settings U4: every CI job that runs docsentinel sets DOCSENTINEL_SETTINGS: "off".

    Scenario:
        Given every workflow under .github/workflows
        When each job that runs docsentinel (a docsentinel command or the pytest plugin) is found
        Then its job-level env sets DOCSENTINEL_SETTINGS to the quoted string "off" (unquoted YAML
            off would become the boolean false), and at least one such job exists.

    Boundaries:
        - Focus: threat model U4 / amendment A9
        - Fixtures/params: none
        - Scope: text parse of the workflow YAML (no YAML library in the environment)

    On failure, first check:
        - .github/workflows/ci.yml job env
    """
    checked: list[str] = []
    workflows = sorted((_REPO_ROOT / ".github" / "workflows").glob("*.y*ml"))
    for workflow in workflows:
        for job, lines in _workflow_jobs(workflow.read_text(encoding="utf-8")).items():
            if not any(_DOCSENTINEL_COMMAND.search(line) for line in lines):
                continue
            env = _job_env(lines)
            assert env.get(USER_SETTINGS_ENV) in ('"off"', "'off'"), f"{workflow.name}:{job}"
            checked.append(f"{workflow.name}:{job}")

    assert "ci.yml:test" in checked


# --- U15: init --user ------------------------------------------------------------------------------


@_POSIX_ONLY
@pytest.mark.parametrize("location", ["env", "default"])
def test_init_user_creates_0600_file_and_0700_dirs_under_umask_002(
    user_home: UserHome, capsys: pytest.CaptureFixture[str], location: str
):
    """
    [Integration] user settings U15: init --user creates 0700 directories and a 0600 file under umask 002.

    Scenario:
        Given umask 002 and a settings path three missing directories deep (named by
            DOCSENTINEL_SETTINGS, or the default ~/.local/share/docsentinel/settings.json)
        When init --user --yes runs
        Then it exits 0 and prints "Created <tilde path>", every created directory is 0700, the
            file is 0600 with the starter object, and it loads as a valid user file.

    Boundaries:
        - Focus: cli._run_init_user (os.mkdir 0700 per component, O_EXCL + fchmod 0600; amendment A8)
        - Fixtures/params: user_home, capsys, location
        - Scope: in-process CLI; umask restored in finally

    On failure, first check:
        - That each missing directory gets its own os.mkdir(path, 0o700)
    """
    if location == "env":
        path = user_home.home / "a" / "b" / "c" / "settings.json"
        user_home.monkeypatch.setenv(USER_SETTINGS_ENV, str(path))
        created_dirs = [user_home.home / "a", user_home.home / "a" / "b", user_home.home / "a" / "b" / "c"]
        shown = "~/a/b/c/settings.json"
    else:
        user_home.use_default_location()
        path = user_home.home / ".local" / "share" / "docsentinel" / "settings.json"
        created_dirs = [path.parent.parent.parent, path.parent.parent, path.parent]
        shown = _DEFAULT_SHOWN
    previous = os.umask(0o002)
    try:
        code, out, err = _run(capsys, "init", "--user", "--yes")
    finally:
        os.umask(previous)

    assert code == 0, err
    assert out.strip() == f"Created {shown}"
    assert [stat.S_IMODE(os.stat(directory).st_mode) for directory in created_dirs] == [0o700] * 3
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert path.read_text(encoding="utf-8") == cli.USER_SETTINGS_TEMPLATE
    assert json.loads(path.read_text(encoding="utf-8")) == {"profile": "fast", "reference_scope": "links"}
    assert load_config(user_home.home).reference_scope == "links"


@pytest.mark.parametrize("target", ["existing", "dangling"])
def test_init_user_refuses_existing_symlink(user_home: UserHome, capsys: pytest.CaptureFixture[str], target: str):
    """
    [Integration] user settings U15: init --user never follows or overwrites a symlink at the settings path.

    Scenario:
        Given the settings path is a symlink to an existing victim file, or a dangling symlink
        When init --user --yes runs
        Then it exits 2 with "~/settings.json already exists; not overwriting it", the victim is
            unchanged and a dangling target is not created.

    Boundaries:
        - Focus: os.path.lexists check and O_EXCL/O_NOFOLLOW in cli._run_init_user
        - Fixtures/params: user_home, capsys, target
        - Scope: in-process CLI

    On failure, first check:
        - lexists (not exists) before creation
    """
    victim = user_home.home / "victim.json"
    if target == "existing":
        victim.write_text("VICTIM", encoding="utf-8")
    link = user_home.home / "settings.json"
    link.symlink_to(victim)
    user_home.monkeypatch.setenv(USER_SETTINGS_ENV, str(link))

    code, out, err = _run(capsys, "init", "--user", "--yes")

    assert code == 2
    assert problem_output(err).splitlines()[0] == "~/settings.json already exists; not overwriting it"
    assert out == ""
    assert link.is_symlink()
    if target == "existing":
        assert victim.read_text(encoding="utf-8") == "VICTIM"
    else:
        assert not os.path.lexists(victim)


@_POSIX_ONLY
def test_init_user_refuses_unsafe_directory(user_home: UserHome, capsys: pytest.CaptureFixture[str]):
    """
    [Integration] user settings U15: init --user refuses a world-writable deepest directory before creating anything.

    Scenario:
        Given DOCSENTINEL_SETTINGS at ~/shared/new/settings.json where ~/shared is mode 0777
        When init --user --yes runs under a timeout guard
        Then it exits 2 with the R3 directory phrase and ~/shared/new is not created.

    Boundaries:
        - Focus: _check_user_settings_directories(existing, final_is_directory=True) before mkdir
        - Fixtures/params: user_home, capsys
        - Scope: in-process CLI; real chmod restored in finally; POSIX only

    On failure, first check:
        - The R3 check precedes the os.mkdir loop
    """
    shared = user_home.home / "shared"
    shared.mkdir()
    user_home.monkeypatch.setenv(USER_SETTINGS_ENV, str(shared / "new" / "settings.json"))
    os.chmod(shared, 0o777)
    try:
        with _timeout_guard():
            code, _, err = _run(capsys, "init", "--user", "--yes")
        created = os.path.lexists(shared / "new")
    finally:
        os.chmod(shared, 0o700)

    assert code == 2
    assert problem_output(err).splitlines()[0] == (
        "Cannot create user settings ~/shared/new/settings.json: "
        "its directory is owned by another user or writable by others"
    )
    assert created is False


def test_init_user_twice_exits_2(user_home: UserHome, capsys: pytest.CaptureFixture[str]):
    """
    [Integration] user settings U15: a second init --user exits 2 and leaves the first file unchanged.

    Scenario:
        Given init --user --yes created the settings file and the user edited it
        When init --user --yes runs again, and once more with DOCSENTINEL_SETTINGS=off
        Then the second run exits 2 with "already exists; not overwriting it", the edit survives,
            and the off run exits 2 naming the off setting.

    Boundaries:
        - Focus: no overwrite (story CLI reference, init --user)
        - Fixtures/params: user_home, capsys
        - Scope: in-process CLI

    On failure, first check:
        - The lexists guard and the off branch of cli._run_init_user
    """
    path = user_home.home / "settings.json"
    user_home.monkeypatch.setenv(USER_SETTINGS_ENV, str(path))

    first, _, _ = _run(capsys, "init", "--user", "--yes")
    path.write_text('{"profile": "standard"}', encoding="utf-8")
    second, _, err = _run(capsys, "init", "--user", "--yes")
    user_home.monkeypatch.setenv(USER_SETTINGS_ENV, "off")
    off, _, off_err = _run(capsys, "init", "--user", "--yes")

    assert (first, second, off) == (0, 2, 2)
    assert problem_output(err).splitlines()[0] == "~/settings.json already exists; not overwriting it"
    assert path.read_text(encoding="utf-8") == '{"profile": "standard"}'
    assert problem_output(off_err).splitlines()[0] == (
        f"Cannot create the user settings file: user settings are off ({USER_SETTINGS_ENV}=off)"
    )
