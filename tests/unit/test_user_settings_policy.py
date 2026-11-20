"""Unit tests for the user settings key policy and layering (Milestone 0009 Story 03.0, Task 06 Step 3).

Covers the C6 refusal of repository-relative keys (plain and escaped spellings, before any
value validation), the builtin-only extension rule, one representative allowed key per
family, precedence (defaults, then user, then project; a whole key replaced, never merged),
the edge shapes of the story README, ``ConfigSources``, and the U5/U10/U11/U13 guards of
docs/security/threat-model-0009-user-settings-2026-11-17.md. Settings files are written inline
under a fake home inside ``tmp_path`` (mode ``0o600``, directories ``0o700``) and selected with
``DOCSENTINEL_SETTINGS`` or ``XDG_DATA_HOME``; the real home is never read. No asset is loaded.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import os
import re
from pathlib import Path
from typing import Optional

import pytest

import docsentinel
from docsentinel import reporting
from docsentinel.config import (
    _CONFIG_OPTIONS,
    USER_SETTINGS_ENV,
    USER_SETTINGS_REFUSED_KEYS,
    Config,
    ConfigError,
    ConfigSources,
    load_config,
    load_config_with_sources,
)
from docsentinel.models import ScanResult
from docsentinel.telemetry.model import ReportModel

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src" / "docsentinel"

#: Plan contract C6, copied verbatim; the drift test also reads it from plan.md.
_C6_KEYS = (
    "baseline",
    "include",
    "exclude",
    "docsig_paths",
    "navigation_indexes",
    "navigation_required",
    "deprecated_references_file",
    "report_templates_dir",
    "link_root",
    "telemetry_domains",
)

#: A value each C6 key would accept from a project file, so only the C6 rule can refuse it.
_C6_VALID_VALUES: dict[str, object] = {
    "baseline": "baseline.json",
    "include": ["docs/**/*.md"],
    "exclude": ["drafts"],
    "docsig_paths": ["src"],
    "navigation_indexes": ["index.md"],
    "navigation_required": ["guide.md"],
    "deprecated_references_file": "deprecated.toml",
    "report_templates_dir": "templates",
    "link_root": ".",
    "telemetry_domains": [{"glob": "docs/**", "domain": "guides"}],
}

_REFUSAL = "repository-relative options cannot be set in user settings: "


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point HOME at an owner-only directory in ``tmp_path`` and return it.

    :param tmp_path: The test's temporary directory.
    :param monkeypatch: Restores HOME after the test.
    :returns: The fake home directory.
    """
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    os.chmod(home, 0o700)
    monkeypatch.setenv("HOME", str(home))
    return home


def _settings_file(directory: Path, content: object, name: str = "settings.json") -> Path:
    """Write a user settings file with owner-only modes and return its path.

    :param directory: The directory to hold it (created ``0o700`` when absent).
    :param content: A JSON-serialisable object, or a ``str`` written verbatim.
    :param name: The file name.
    :returns: The file path.
    """
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    path = directory / name
    path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    os.chmod(path, 0o600)
    return path


def _use_settings(monkeypatch: pytest.MonkeyPatch, path: Path):
    """Select ``path`` as the user settings file through ``DOCSENTINEL_SETTINGS``.

    :param monkeypatch: Restores the variable after the test.
    :param path: The settings file.
    """
    monkeypatch.setenv(USER_SETTINGS_ENV, str(path))


def _repo(tmp_path: Path, toml: str = "") -> Path:
    """Create a scan root, optionally with a docsentinel.toml, and return it.

    :param tmp_path: The test's temporary directory.
    :param toml: The docsentinel.toml text; empty writes no file.
    :returns: The scan root.
    """
    root = tmp_path / "repo"
    root.mkdir(exist_ok=True)
    if toml:
        (root / "docsentinel.toml").write_text(toml, encoding="utf-8")
    return root


@pytest.mark.parametrize("key", _C6_KEYS)
def test_each_c6_key_refused_naming_key_and_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_home: Path, key: str
):
    """
    [Unit] user settings U5: each C6 key in the default-location file is refused by name.

    Scenario:
        Given a user settings file at the default XDG location holding one C6 key with a value
            a project file would accept
        When load_config runs
        Then ConfigError names the key and the file in tilde form, and no Config is returned.

    Boundaries:
        - Focus: USER_SETTINGS_REFUSED_KEYS in _read_user_options (plan C6)
        - Fixtures/params: tmp_path, monkeypatch, fake_home, key (the ten C6 keys)
        - Scope: XDG_DATA_HOME under the fake home; DOCSENTINEL_SETTINGS unset

    On failure, first check:
        - That the refusal runs on the parsed keys before _build_config
        - _tilde_path for the prefix
    """
    data_home = fake_home / "data"
    _settings_file(data_home / "docsentinel", {key: _C6_VALID_VALUES[key]})
    monkeypatch.delenv(USER_SETTINGS_ENV)
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))

    with pytest.raises(ConfigError) as caught:
        load_config(_repo(tmp_path))

    assert str(caught.value) == f"user settings ~/data/docsentinel/settings.json: {_REFUSAL}{key}"


def test_all_c6_keys_listed_sorted_in_one_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_home: Path):
    """
    [Unit] user settings U5: a file with every C6 key names all of them, sorted, in one error.

    Scenario:
        Given a user file with all ten C6 keys and one allowed key
        When load_config runs
        Then the single ConfigError lists the ten keys sorted and comma-joined, and not the
            allowed key.

    Boundaries:
        - Focus: the refusal lists every refused key (ADR 0005 Contract 4)
        - Fixtures/params: tmp_path, monkeypatch, fake_home
        - Scope: DOCSENTINEL_SETTINGS under the fake home

    On failure, first check:
        - sorted(set(options) & USER_SETTINGS_REFUSED_KEYS)
    """
    _use_settings(monkeypatch, _settings_file(fake_home, {**_C6_VALID_VALUES, "profile": "fast"}))

    with pytest.raises(ConfigError) as caught:
        load_config(_repo(tmp_path))

    assert str(caught.value) == f"user settings ~/settings.json: {_REFUSAL}{', '.join(sorted(_C6_KEYS))}"


def test_escaped_c6_key_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_home: Path):
    """
    [Unit] user settings U5: a C6 key spelled with \\u escapes is refused on the decoded name.

    Scenario:
        Given a user file whose only keys are "\\u0062aseline" and "\\u006c\\u0069nk_root"
        When load_config runs
        Then ConfigError names "baseline" and "link_root".

    Boundaries:
        - Focus: C6 refusal on decoded keys (threat model M6)
        - Fixtures/params: tmp_path, monkeypatch, fake_home
        - Scope: DOCSENTINEL_SETTINGS under the fake home

    On failure, first check:
        - That the refusal uses the json.loads result, not the raw text
    """
    text = '{"\\u0062aseline": "b.json", "\\u006c\\u0069nk_root": "."}'
    _use_settings(monkeypatch, _settings_file(fake_home, text))

    with pytest.raises(ConfigError) as caught:
        load_config(_repo(tmp_path))

    assert str(caught.value) == f"user settings ~/settings.json: {_REFUSAL}baseline, link_root"


@pytest.mark.parametrize(
    "options",
    [{"baseline": 5}, {"link_root": "/absolute", "profile": "bogus"}, {"include": "not-a-list", "max_grade_level": -1}],
    ids=["wrong_type", "invalid_value_and_bad_allowed_key", "both_invalid"],
)
def test_c6_refusal_precedes_value_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_home: Path, options: dict[str, object]
):
    """
    [Unit] user settings U5: a C6 key is refused before its value or any other value is validated.

    Scenario:
        Given a user file holding a C6 key with an invalid value, beside an invalid allowed key
        When load_config runs
        Then the ConfigError is the C6 refusal, not a validator message.

    Boundaries:
        - Focus: order in _read_user_options (refusal, then _build_config)
        - Fixtures/params: tmp_path, monkeypatch, fake_home, options
        - Scope: DOCSENTINEL_SETTINGS under the fake home; null values are avoided because the
            reader refuses null first (threat model T04-3)

    On failure, first check:
        - That _build_config runs after the refusal
    """
    _use_settings(monkeypatch, _settings_file(fake_home, options))
    refused = sorted(set(options) & USER_SETTINGS_REFUSED_KEYS)

    with pytest.raises(ConfigError) as caught:
        load_config(_repo(tmp_path))

    assert str(caught.value) == f"user settings ~/settings.json: {_REFUSAL}{', '.join(refused)}"
    assert "must be" not in str(caught.value)


@pytest.mark.parametrize(
    "extensions",
    [["python:mymodule:hook"], ["builtin:domain", "python:mymodule:hook"]],
    ids=["alone", "after_builtin"],
)
def test_user_python_extension_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_home: Path, extensions: list[str]
):
    """
    [Unit] user settings U5: a python: extension in the user file is refused like in a project file.

    Scenario:
        Given a user file whose telemetry_extensions names a python: extension
        When load_config runs
        Then ConfigError carries the builtin-only validator message behind the user prefix,
            and a builtin-only list from the same file is accepted.

    Boundaries:
        - Focus: validate_telemetry_extensions at user level (C6 note)
        - Fixtures/params: tmp_path, monkeypatch, fake_home, extensions
        - Scope: DOCSENTINEL_SETTINGS under the fake home

    On failure, first check:
        - That the user mapping is validated alone by _build_config
    """
    path = _settings_file(fake_home, {"telemetry_extensions": extensions})
    _use_settings(monkeypatch, path)
    index = len(extensions) - 1

    with pytest.raises(ConfigError) as caught:
        load_config(_repo(tmp_path))

    assert str(caught.value) == (
        f"user settings ~/settings.json: telemetry_extensions[{index}] is not a builtin:<name> spec; "
        "configuration may name only builtin extensions"
    )
    _settings_file(fake_home, {"telemetry_extensions": ["builtin:domain"]})
    assert load_config(_repo(tmp_path)).telemetry_extensions == ("builtin:domain",)


def test_refused_keys_drift_matches_c6():
    """
    [Unit] user settings U5: the refused-key set equals plan contract C6 and is a schema subset.

    Scenario:
        Given USER_SETTINGS_REFUSED_KEYS, the C6 list copied here and the C6 paragraph of
            docs/roadmap/0009-improvements/plan.md
        When they are compared
        Then all three hold the same ten keys, each a known option and a Config field.

    Boundaries:
        - Focus: drift guard between the contract and the frozenset
        - Fixtures/params: none
        - Scope: reads plan.md text only

    On failure, first check:
        - A new repository-relative option must be added to the frozenset and to C6 together
    """
    plan = (_REPO_ROOT / "docs" / "roadmap" / "0009-improvements" / "plan.md").read_text(encoding="utf-8")
    section = plan.split("### C6", 1)[1].split("### C7", 1)[0]
    listed = section.split("**except**", 1)[1].split("Such a key", 1)[0]
    from_plan = set(re.findall(r"`([a-z_]+)`", listed))
    field_names = {field.name for field in dataclasses.fields(Config)}

    assert USER_SETTINGS_REFUSED_KEYS == frozenset(_C6_KEYS) == frozenset(from_plan)
    assert len(USER_SETTINGS_REFUSED_KEYS) == 10
    assert USER_SETTINGS_REFUSED_KEYS <= _CONFIG_OPTIONS
    assert USER_SETTINGS_REFUSED_KEYS <= field_names


@pytest.mark.parametrize(
    ("project", "unknown"),
    [
        ('user_settings = "/tmp/other.json"\n', "user_settings"),
        ('settings_path = "/tmp/other.json"\n', "settings_path"),
        ('DOCSENTINEL_SETTINGS = "off"\n', "DOCSENTINEL_SETTINGS"),
    ],
)
def test_project_config_cannot_name_settings_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_home: Path, project: str, unknown: str
):
    """
    [Unit] user settings U5: no project key names or disables the user settings location.

    Scenario:
        Given a project docsentinel.toml (and the same as a JSON --config) that tries to name
            or turn off the settings file, and a valid user file selected by the environment
        When load_config runs
        Then it is the existing "Unknown config options" error; no schema option mentions
            settings, and without that key the user file still applies.

    Boundaries:
        - Focus: only the environment and the flag/keyword select the location (M6)
        - Fixtures/params: tmp_path, monkeypatch, fake_home, project, unknown
        - Scope: DOCSENTINEL_SETTINGS under the fake home

    On failure, first check:
        - _require_known_options; that _load_user_layer takes no root or path argument
    """
    _use_settings(monkeypatch, _settings_file(fake_home, {"reference_scope": "strict"}))
    root = _repo(tmp_path, project)
    json_config = tmp_path / "config.json"
    json_config.write_text(json.dumps({unknown: "/tmp/other.json"}), encoding="utf-8")

    with pytest.raises(ConfigError) as from_toml:
        load_config(root)
    with pytest.raises(ConfigError) as from_json:
        load_config(root, json_config)

    assert str(from_toml.value) == f"Unknown config options: {unknown}"
    assert str(from_json.value) == f"Unknown config options: {unknown}"
    assert not any("setting" in name for name in _CONFIG_OPTIONS)
    (root / "docsentinel.toml").write_text('profile = "fast"\n', encoding="utf-8")
    assert load_config(root).reference_scope == "strict"


def test_env_named_file_still_c6_restricted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_home: Path):
    """
    [Unit] user settings U10: a file named by DOCSENTINEL_SETTINGS outside the home is still C6-bound.

    Scenario:
        Given a "committed" file inside a repository, owned by the user and selected through
            DOCSENTINEL_SETTINGS, that sets exclude and ignore
        When load_config scans a different tree
        Then the exclude key is refused, naming that file as given (it is outside the home).

    Boundaries:
        - Focus: C6 applies to every user settings source, not only the default location
        - Fixtures/params: tmp_path, monkeypatch, fake_home
        - Scope: the file lives under tmp_path/checkout, not under the fake home

    On failure, first check:
        - That _read_user_options is used for state "env" too
    """
    committed = _settings_file(tmp_path / "checkout", {"exclude": ["docs"], "ignore": ["DS"]}, "ds-settings.json")
    _use_settings(monkeypatch, committed)

    with pytest.raises(ConfigError) as caught:
        load_config(_repo(tmp_path))

    assert str(caught.value) == f"user settings {committed}: {_REFUSAL}exclude"


def test_allowed_key_from_each_family_applies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_home: Path):
    """
    [Unit] user settings: one representative allowed key per family is applied from the user file.

    Scenario:
        Given a user file with profile, reference_scope, select/ignore, the thresholds, the
            size limits, fast-rule policy options, deep_confirm, report options, a builtin
            extension and the @-reference extensions
        When load_config runs with no project file
        Then every value reaches Config and ConfigSources reports the file as loaded with the
            sorted option names.

    Boundaries:
        - Focus: the user layer applies allowed keys (story key policy table)
        - Fixtures/params: tmp_path, monkeypatch, fake_home
        - Scope: DOCSENTINEL_SETTINGS under the fake home

    On failure, first check:
        - load_config_with_sources merge of user options
    """
    options: dict[str, object] = {
        "profile": "standard",
        "reference_scope": "strict",
        "select": ["DS1", "DS2"],
        "ignore": ["DS102"],
        "max_grade_level": 16.0,
        "duplicate_similarity": 0.9,
        "min_information_score": 0.2,
        "min_document_words": 80,
        "anchor_collision_policy": "off",
        "require_fence_languages": True,
        "allowed_fence_languages": ["python"],
        "first_heading_level": 2,
        "deep_confirm": True,
        "report_show_clean_documents": True,
        "report_include_run_meta": True,
        "telemetry_extensions": ["builtin:document_stats"],
        "at_reference_extensions": ["md"],
    }
    path = _settings_file(fake_home, options)
    _use_settings(monkeypatch, path)

    config, sources = load_config_with_sources(_repo(tmp_path))

    for name, value in options.items():
        expected = tuple(value) if isinstance(value, list) else value
        assert getattr(config, name) == expected, name
    assert sources == ConfigSources(
        user=path,
        user_state="loaded",
        project=None,
        project_kind="none",
        user_options=tuple(sorted(options)),
        project_options=(),
    )


def test_precedence_user_under_project_whole_key_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_home: Path
):
    """
    [Unit] user settings: defaults, then user, then project; a key's value is replaced, not merged.

    Scenario:
        Given a user file setting reference_scope, profile and ignore, and a project
            docsentinel.toml setting reference_scope and ignore
        When load_config_with_sources runs, then a CLI-style dataclasses.replace is applied
        Then the project wins for its keys (ignore is the project list only), the user value
            stays for profile, an unset key keeps its default, and the replace wins over both.

    Boundaries:
        - Focus: layering in load_config_with_sources (plan C1, story S5)
        - Fixtures/params: tmp_path, monkeypatch, fake_home
        - Scope: library layers 1-3; layer 4 is the CLI's dataclasses.replace

    On failure, first check:
        - The {**user, **project} merge order
    """
    _use_settings(
        monkeypatch,
        _settings_file(fake_home, {"reference_scope": "strict", "profile": "standard", "ignore": ["DS101"]}),
    )
    root = _repo(tmp_path, 'reference_scope = "links"\nignore = ["DS102"]\n')

    config, sources = load_config_with_sources(root)

    assert config.reference_scope == "links"
    assert config.ignore == ("DS102",)
    assert config.profile == "standard"
    assert config.max_grade_level == Config().max_grade_level
    assert sources.user_options == ("ignore", "profile", "reference_scope")
    assert sources.project_options == ("ignore", "reference_scope")
    assert (sources.project, sources.project_kind) == (root / "docsentinel.toml", "toml")
    assert dataclasses.replace(config, reference_scope="strict").reference_scope == "strict"


def test_user_settings_keyword_false_skips_layer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_home: Path):
    """
    [Unit] user settings: user_settings=False ignores a valid user file.

    Scenario:
        Given a valid user file setting reference_scope = "strict"
        When load_config runs with user_settings=True and with user_settings=False
        Then only the first applies it; the second reports state "off".

    Boundaries:
        - Focus: the user_settings keyword (library form of --no-user-settings)
        - Fixtures/params: tmp_path, monkeypatch, fake_home
        - Scope: DOCSENTINEL_SETTINGS under the fake home

    On failure, first check:
        - _load_user_layer early return
    """
    _use_settings(monkeypatch, _settings_file(fake_home, {"reference_scope": "strict"}))
    root = _repo(tmp_path)

    assert load_config(root).reference_scope == "strict"
    config, sources = load_config_with_sources(root, user_settings=False)
    assert config == Config()
    assert (sources.user, sources.user_state, sources.user_options) == (None, "off", ())


def test_user_settings_apply_beneath_explicit_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_home: Path):
    """
    [Unit] user settings: an explicit --config (TOML, pyproject or JSON) keeps the user layer beneath it.

    Scenario:
        Given a user file setting profile and reference_scope, and explicit project configs
            setting reference_scope only (a TOML file, a pyproject.toml and a .JSON file)
        When load_config_with_sources runs with each as path
        Then the project value wins, the user profile still applies, and project_kind is
            toml, pyproject or json.

    Boundaries:
        - Focus: path replaces discovery only (story S2, edge case "--config names pyproject.toml")
        - Fixtures/params: tmp_path, monkeypatch, fake_home
        - Scope: DOCSENTINEL_SETTINGS under the fake home

    On failure, first check:
        - _read_project_options suffix rule (case-insensitive .json)
    """
    _use_settings(monkeypatch, _settings_file(fake_home, {"profile": "standard", "reference_scope": "strict"}))
    root = _repo(tmp_path)
    toml_file = tmp_path / "custom.toml"
    toml_file.write_text('reference_scope = "links"\n', encoding="utf-8")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.doc_sentinel]\nreference_scope = "links"\n', encoding="utf-8")
    json_file = tmp_path / "custom.JSON"
    json_file.write_text('{"reference_scope": "links"}', encoding="utf-8")

    for path, kind in ((toml_file, "toml"), (pyproject, "pyproject"), (json_file, "json")):
        config, sources = load_config_with_sources(root, path)
        assert (config.profile, config.reference_scope) == ("standard", "links"), kind
        assert (sources.project, sources.project_kind, sources.user_state) == (path, kind, "loaded")


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("", "Cannot read JSON config: invalid JSON at line 1, column 1"),
        ("[]", "Cannot read JSON config: the top level must be an object"),
        ('{"include": ["docs/**"]}', f"{_REFUSAL}include"),
        ('{"profile": "bogus"}', "profile must be fast, standard, or deep"),
        ('{"bogus_option": 1}', "Unknown config options: bogus_option"),
    ],
    ids=["empty", "array", "include", "bad_value", "unknown_key"],
)
def test_user_file_edge_shapes_name_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_home: Path, content: str, expected: str
):
    """
    [Unit] user settings edge cases: an empty, array, refused or invalid user file names the file.

    Scenario:
        Given a user file that is empty, a top-level array, an include key, an invalid value or
            an unknown key
        When load_config runs
        Then ConfigError is the reader or validator message behind "user settings ~/settings.json: ".

    Boundaries:
        - Focus: story README "Edge cases" first bullet; the prefix of ADR 0005 S7
        - Fixtures/params: tmp_path, monkeypatch, fake_home, content, expected
        - Scope: DOCSENTINEL_SETTINGS under the fake home

    On failure, first check:
        - The prefixing except clause in _load_user_layer
    """
    _use_settings(monkeypatch, _settings_file(fake_home, content))

    with pytest.raises(ConfigError) as caught:
        load_config(_repo(tmp_path))

    assert str(caught.value) == f"user settings ~/settings.json: {expected}"


def test_user_file_directory_and_empty_object(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_home: Path):
    """
    [Unit] user settings edge cases: a directory is refused; {} is valid and changes nothing.

    Scenario:
        Given DOCSENTINEL_SETTINGS naming a directory, then a file holding {}
        When load_config runs
        Then the directory gives "not a regular file" behind the prefix, and {} gives the
            default Config with state "loaded" and no option names.

    Boundaries:
        - Focus: story README edge cases (directory, {})
        - Fixtures/params: tmp_path, monkeypatch, fake_home
        - Scope: DOCSENTINEL_SETTINGS under the fake home

    On failure, first check:
        - The S_ISREG pre-check in _read_config_once
    """
    directory = fake_home / "settings.json"
    directory.mkdir(mode=0o700)
    _use_settings(monkeypatch, directory)
    root = _repo(tmp_path)

    with pytest.raises(ConfigError) as caught:
        load_config(root)

    assert str(caught.value) == "user settings ~/settings.json: Cannot read JSON config: not a regular file"
    empty = _settings_file(fake_home, {}, "empty.json")
    _use_settings(monkeypatch, empty)
    config, sources = load_config_with_sources(root)
    assert config == Config()
    assert (sources.user, sources.user_state, sources.user_options) == (empty, "loaded", ())


def test_both_standalone_names_still_ambiguous_with_user_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_home: Path
):
    """
    [Unit] user settings edge cases: two standalone TOML names stay an error; the user file is no third name.

    Scenario:
        Given a valid user file and a root holding both docsentinel.toml and doc_sentinel.toml
        When load_config runs
        Then the unchanged "found both ... keep only one" ConfigError is raised, unprefixed.

    Boundaries:
        - Focus: discovery is unchanged (story S1)
        - Fixtures/params: tmp_path, monkeypatch, fake_home
        - Scope: DOCSENTINEL_SETTINGS under the fake home

    On failure, first check:
        - _read_project_options discovery branch
    """
    _use_settings(monkeypatch, _settings_file(fake_home, {"profile": "fast"}))
    root = _repo(tmp_path, 'profile = "fast"\n')
    (root / "doc_sentinel.toml").write_text('profile = "fast"\n', encoding="utf-8")

    with pytest.raises(ConfigError) as caught:
        load_config(root)

    assert str(caught.value) == f"found both docsentinel.toml and doc_sentinel.toml in {root}; keep only one"


def test_config_sources_not_in_report_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] user settings U11: ConfigSources and the settings path never reach a report.

    Scenario:
        Given a loaded user file (in a uniquely named directory) that turns on
            report_show_clean_documents, and a clean one-document tree
        When the scan runs and every packaged template renders it, and the report context is built
        Then the user setting visibly applied, yet no report or context holds the settings
            path, its directory name or "settings.json", and neither Config nor ScanResult has a
            sources field.

    Boundaries:
        - Focus: ConfigSources stays out of ReportModel (amendment A7)
        - Fixtures/params: tmp_path, monkeypatch
        - Scope: docsentinel.scan with the user layer; render() for the five packaged formats

    On failure, first check:
        - Whether a Config or ScanResult field or a context variable was added for sources
    """
    marker_dir = tmp_path / "cfg_marker_91c2"
    path = _settings_file(marker_dir, {"report_show_clean_documents": True})
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    _use_settings(monkeypatch, path)
    root = _repo(tmp_path)
    (root / "guide.md").write_text("# Guide\n\nClean text.\n", encoding="utf-8")

    config = load_config(root)
    result = docsentinel.scan(root)
    context = json.dumps(ReportModel.build(result, config, report_include_run_meta=True), default=str)
    reports = {
        name: reporting.render(result, name, config=config, root=root)
        for name in ("text", "github", "json", "json-v1", "json-documents")
    }

    assert config.report_show_clean_documents is True
    assert "guide.md" in reports["text"]
    for text in (context, *reports.values()):
        assert str(path) not in text
        assert marker_dir.name not in text
        assert "settings.json" not in text
    for model in (Config, ScanResult):
        names = {field.name for field in dataclasses.fields(model)}
        assert not any("source" in name or "settings" in name for name in names), model


def _environment_reads(tree: ast.AST) -> list[tuple[str, int, str]]:
    """Return ``(function, line, variable)`` for each read of a settings variable in ``tree``.

    A read is ``os.environ.get(X)``, ``os.environ[X]``, ``os.getenv(X)`` or ``X in os.environ``
    where ``X`` is the literal ``DOCSENTINEL_SETTINGS``/``XDG_DATA_HOME`` or one of the names
    ``USER_SETTINGS_ENV``/``_XDG_DATA_HOME_ENV``.

    :param tree: A parsed module.
    :returns: The reads with the enclosing function name (``<module>`` at module level).
    """
    variables = {"DOCSENTINEL_SETTINGS", "XDG_DATA_HOME", "USER_SETTINGS_ENV", "_XDG_DATA_HOME_ENV"}

    def label(node: ast.AST) -> str:
        """Return the literal or name a key expression spells, or an empty string."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return ""

    def is_environ(node: ast.AST) -> bool:
        """Return whether ``node`` spells ``os.environ`` or ``environ``."""
        return (isinstance(node, ast.Attribute) and node.attr == "environ") or (
            isinstance(node, ast.Name) and node.id == "environ"
        )

    reads: list[tuple[str, int, str]] = []
    for function in [tree, *[node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]]:
        owner = function.name if isinstance(function, ast.FunctionDef) else "<module>"
        for node in ast.walk(function):
            key: Optional[ast.AST] = None
            if isinstance(node, ast.Call) and node.args:
                func = node.func
                if (isinstance(func, ast.Attribute) and func.attr == "get" and is_environ(func.value)) or (
                    isinstance(func, ast.Attribute) and func.attr == "getenv"
                ):
                    key = node.args[0]
            elif isinstance(node, ast.Subscript) and is_environ(node.value):
                key = node.slice
            elif isinstance(node, ast.Compare) and any(is_environ(item) for item in node.comparators):
                key = node.left
            if key is not None and label(key) in variables:
                reads.append((owner, node.lineno, label(key)))
    return reads


def test_settings_env_read_only_in_resolver():
    """
    [Unit] user settings U13: DOCSENTINEL_SETTINGS and XDG_DATA_HOME are read only by user_settings_path.

    Scenario:
        Given every module under src/docsentinel parsed with ast
        When environment reads of the two variables (by literal or by their constant names)
            are collected, with the enclosing function
        Then every read sits in config.user_settings_path, both variables are read there, the
            literals appear only in config.py, and Path.home() is called in config.py only by
            _home_directory.

    Boundaries:
        - Focus: one reader of the settings environment (threat model M17)
        - Fixtures/params: none
        - Scope: static AST scan; nested functions are attributed to every enclosing def

    On failure, first check:
        - A new os.environ access to the settings variables outside the resolver
    """
    reads: dict[str, list[tuple[str, int, str]]] = {}
    literal_files: set[str] = set()
    home_callers: list[str] = []
    for source in sorted(_SRC.rglob("*.py")):
        relative = source.relative_to(_SRC).as_posix()
        tree = ast.parse(source.read_text(encoding="utf-8"))
        found = _environ_reads_innermost(tree)
        if found:
            reads[relative] = found
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value in ("DOCSENTINEL_SETTINGS", "XDG_DATA_HOME"):
                literal_files.add(relative)
        if relative == "config.py":
            for function in (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)):
                for node in ast.walk(function):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "home"
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "Path"
                    ):
                        home_callers.append(function.name)

    assert set(reads) == {"config.py"}
    assert {owner for owner, _, _ in reads["config.py"]} == {"user_settings_path"}
    assert {variable for _, _, variable in reads["config.py"]} == {"USER_SETTINGS_ENV", "_XDG_DATA_HOME_ENV"}
    assert literal_files == {"config.py"}
    assert home_callers == ["_home_directory"]


def _environ_reads_innermost(tree: ast.AST) -> list[tuple[str, int, str]]:
    """Return the settings-variable reads of ``tree``, each attributed to its innermost function.

    :param tree: A parsed module.
    :returns: ``(function, line, variable)`` tuples without duplicates.
    """
    innermost: dict[tuple[int, str], str] = {}
    for owner, line, variable in _environment_reads(tree):
        # ast.walk visits outer functions first, so a later entry is the inner function.
        innermost[(line, variable)] = owner
    return sorted((owner, line, variable) for (line, variable), owner in innermost.items())
