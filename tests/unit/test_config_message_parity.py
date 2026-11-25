"""Unit tests: TOML and JSON configuration give the same validator messages (Story 03.0 Task 06 Step 2).

For each validator of ``docsentinel.config``, one invalid value is written as a standalone
``docsentinel.toml``, as a ``[tool.doc_sentinel]`` table in ``pyproject.toml``, as an explicit
JSON ``--config`` file and, for keys a user may set, as a user settings file. The project
messages must be identical; the user message is the same text behind the
``user settings <path>: `` prefix (plan contract C7, story acceptance criterion 3, threat model
docs/security/threat-model-0009-user-settings-2026-11-17.md U8, amendment A6). Every file is
generated inline in ``tmp_path``; no asset is loaded.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Callable
from pathlib import Path

import pytest

from docsentinel.config import (
    _BOOL_OPTIONS,
    _CONFIG_OPTIONS,
    _ENUM_OPTIONS,
    _ROOT_PATH_LIST_OPTIONS,
    _STR_LIST_OPTIONS,
    USER_SETTINGS_ENV,
    USER_SETTINGS_REFUSED_KEYS,
    ConfigError,
    load_config,
)

#: A 400-digit integer: too large for a float (threat model U8 evidence row).
_HUGE_INT = int("9" * 400)

#: One invalid value per validator (and per branch where a validator has two).
_INVALID: list[tuple[str, object]] = [
    ("include", [""]),
    ("include", "docs/*.md"),
    ("exclude", [""]),
    ("profile", "bogus"),
    ("select", ["XX"]),
    ("ignore", [5]),
    ("baseline", ""),
    ("baseline", 5),
    ("max_grade_level", 0),
    ("max_grade_level", -1.5),
    ("max_grade_level", "high"),
    ("max_grade_level", True),
    ("duplicate_similarity", 1.5),
    ("min_information_score", -0.1),
    ("docsig_paths", [""]),
    *((name, "yes") for name in _BOOL_OPTIONS),
    *((name, "bogus") for name in _ENUM_OPTIONS),
    *((name, 5) for name in _STR_LIST_OPTIONS),
    ("allowed_fence_languages", ["python bash"]),
    *((name, ["../outside.md"]) for name in _ROOT_PATH_LIST_OPTIONS),
    *((name, "index.md") for name in _ROOT_PATH_LIST_OPTIONS),
    ("first_heading_level", 7),
    ("first_heading_level", 1.0),
    ("empty_section_min_text_chars", -1),
    ("min_document_words", 0),
    ("min_document_words", 5.0),
    ("min_paragraph_words", 0),
    ("min_paragraph_chars", -1),
    ("document_id_field", ""),
    ("document_id_field", "1bad"),
    ("deprecated_references_file", 5),
    ("deprecated_references_file", "../mapping.toml"),
    ("report_templates_dir", ""),
    ("report_templates_dir", "../templates"),
    ("telemetry_extensions", 5),
    ("telemetry_extensions", ["python:module:hook"]),
    ("telemetry_domains", "docs"),
    ("telemetry_domains", [{"glob": "docs/**"}]),
    ("telemetry_domains", [{"glob": "docs/**", "domain": "BAD"}]),
    ("link_root", "/absolute"),
    ("link_root", ""),
    ("at_reference_extensions", []),
    ("at_reference_extensions", ["md", "MD"]),
    ("at_reference_extensions", ["m.d"]),
    ("fact_check_min_salience", 1.5),
    ("fact_check_min_salience", True),
    ("fact_check_min_confidence", -0.1),
    ("fact_check_max_claims_per_document", 51),
    ("fact_check_max_claims_total", 0),
    ("fact_check_time_budget_seconds", 300.0),
    ("fact_check_combination", "1-3,2-4"),
]


def _toml_value(value: object) -> str:
    """Return ``value`` as a TOML literal (strings, numbers, booleans, arrays, inline tables).

    :param value: A JSON-compatible value.
    :returns: The TOML spelling.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{key} = {_toml_value(item)}" for key, item in value.items()) + "}"
    raise TypeError(f"no TOML spelling for {type(value).__name__}")


def _message(call: Callable[[], object]) -> str:
    """Return the ``ConfigError`` message raised by ``call()``.

    :param call: A zero-argument callable expected to raise ``ConfigError``.
    :returns: The message text.
    """
    with pytest.raises(ConfigError) as caught:
        call()
    return str(caught.value)


def _project_messages(tmp_path: Path, key: str, toml_literal: str, json_literal: str) -> tuple[str, str, str]:
    """Return the messages of a standalone TOML, a pyproject table and a JSON --config file.

    :param tmp_path: The test's temporary directory.
    :param key: The option name.
    :param toml_literal: The value spelled as TOML.
    :param json_literal: The value spelled as JSON.
    :returns: ``(standalone, pyproject, json)`` messages.
    """
    standalone = tmp_path / "standalone"
    pyproject = tmp_path / "pyproject"
    json_root = tmp_path / "json"
    for directory in (standalone, pyproject, json_root):
        directory.mkdir()
    (standalone / "docsentinel.toml").write_text(f"{key} = {toml_literal}\n", encoding="utf-8")
    (pyproject / "pyproject.toml").write_text(f"[tool.doc_sentinel]\n{key} = {toml_literal}\n", encoding="utf-8")
    json_file = json_root / "config.json"
    json_file.write_text(f'{{"{key}": {json_literal}}}', encoding="utf-8")
    return (
        _message(lambda: load_config(standalone, user_settings=False)),
        _message(lambda: load_config(pyproject, user_settings=False)),
        _message(lambda: load_config(json_root, json_file, user_settings=False)),
    )


@pytest.mark.parametrize(("key", "value"), _INVALID, ids=[f"{key}-{index}" for index, (key, _) in enumerate(_INVALID)])
def test_validator_message_parity_toml_json_and_user(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, key: str, value: object
):
    """
    [Unit] config message parity: every validator gives one message for TOML, pyproject and JSON.

    Scenario:
        Given one invalid value for a validator, written as docsentinel.toml, as a
            [tool.doc_sentinel] table and as an explicit JSON config
        When load_config reads each
        Then the three ConfigError messages are identical and name the option; for a key a user
            may set, the user settings file gives the same text behind the
            "user settings <path>: " prefix.

    Boundaries:
        - Focus: _build_config as the single validation path (ADR 0005 Contract 2)
        - Fixtures/params: tmp_path, monkeypatch (HOME, DOCSENTINEL_SETTINGS), key/value
        - Scope: load_config with a temporary settings file; the real home is never read

    On failure, first check:
        - Whether a new validator branch reads the raw TOML/JSON type differently
        - _finite_number for the float options
    """
    standalone, pyproject, from_json = _project_messages(tmp_path, key, _toml_value(value), json.dumps(value))

    assert standalone == pyproject == from_json
    assert key in standalone
    if key in USER_SETTINGS_REFUSED_KEYS:
        return
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    settings = home / "settings.json"
    settings.write_text(json.dumps({key: value}), encoding="utf-8")
    os.chmod(settings, 0o600)
    monkeypatch.setenv("HOME", str(tmp_path / "elsewhere"))
    monkeypatch.setenv(USER_SETTINGS_ENV, str(settings))
    empty_root = tmp_path / "empty"
    empty_root.mkdir()

    from_user = _message(lambda: load_config(empty_root))

    assert from_user == f"user settings {settings}: {standalone}"


def test_parity_table_covers_every_option():
    """
    [Unit] config message parity: the invalid-value table names every configuration option.

    Scenario:
        Given the parity table and the configuration schema _CONFIG_OPTIONS
        When their key sets are compared
        Then every option has at least one invalid value, so a new option needs a parity case.

    Boundaries:
        - Focus: drift guard for test_validator_message_parity_toml_json_and_user
        - Fixtures/params: none
        - Scope: pure set comparison

    On failure, first check:
        - Add an invalid value for the new option to _INVALID
    """
    assert {key for key, _ in _INVALID} == set(_CONFIG_OPTIONS)


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("max_grade_level", "max_grade_level must be a positive number"),
        ("duplicate_similarity", "duplicate_similarity must be a number between 0 and 1"),
        ("min_information_score", "min_information_score must be a number between 0 and 1"),
    ],
)
def test_numeric_overflow_int_is_config_error_both_formats(tmp_path: Path, key: str, expected: str):
    """
    [Unit] config message parity U8: a 400-digit integer in a float option is the option's message.

    Scenario:
        Given a float-valued option set to a 400-digit integer in TOML and in JSON
        When load_config reads each
        Then both raise the option's existing ConfigError (no OverflowError traceback).

    Boundaries:
        - Focus: _finite_number OverflowError mapping (amendment A6)
        - Fixtures/params: tmp_path, key, expected
        - Scope: project files only

    On failure, first check:
        - That float() of the value is wrapped in _finite_number
    """
    literal = str(_HUGE_INT)

    messages = _project_messages(tmp_path, key, literal, literal)

    assert messages == (expected, expected, expected)


def test_huge_integer_in_int_option_accepted_in_both_formats(tmp_path: Path):
    """
    [Unit] config message parity U8 boundary: an int option never converts to float, so it accepts.

    Scenario:
        Given min_document_words set to a 400-digit integer in TOML and in JSON
        When load_config reads each
        Then both Configs hold that exact integer.

    Boundaries:
        - Focus: _require_bounded_int keeps integer semantics
        - Fixtures/params: tmp_path
        - Scope: project files only

    On failure, first check:
        - That no int option is passed through _finite_number
    """
    toml_root = tmp_path / "toml"
    json_root = tmp_path / "json"
    toml_root.mkdir()
    json_root.mkdir()
    (toml_root / "docsentinel.toml").write_text(f"min_document_words = {_HUGE_INT}\n", encoding="utf-8")
    json_file = json_root / "config.json"
    json_file.write_text(f'{{"min_document_words": {_HUGE_INT}}}', encoding="utf-8")

    from_toml = load_config(toml_root, user_settings=False)
    from_json = load_config(json_root, json_file, user_settings=False)

    assert from_toml.min_document_words == _HUGE_INT
    assert from_toml == from_json


@pytest.mark.parametrize("literal", ["nan", "+nan", "-nan", "inf", "+inf", "-inf"])
@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("max_grade_level", "max_grade_level must be a positive number"),
        ("duplicate_similarity", "duplicate_similarity must be a number between 0 and 1"),
        ("min_information_score", "min_information_score must be a number between 0 and 1"),
    ],
)
def test_toml_nan_and_inf_refused_with_existing_message(tmp_path: Path, key: str, expected: str, literal: str):
    """
    [Unit] config message parity U8: TOML nan and inf are refused with the option's existing message.

    Scenario:
        Given a float option set to a TOML non-finite literal (JSON cannot spell these)
        When load_config reads the docsentinel.toml
        Then ConfigError carries the same message a finite out-of-range value gives.

    Boundaries:
        - Focus: _finite_number in _build_config (sanctioned TOML change, amendment A6)
        - Fixtures/params: tmp_path, key, expected, literal
        - Scope: standalone TOML only

    On failure, first check:
        - math.isfinite in _finite_number
    """
    (tmp_path / "docsentinel.toml").write_text(f"{key} = {literal}\n", encoding="utf-8")

    message = _message(lambda: load_config(tmp_path, user_settings=False))

    assert message == expected
    assert not math.isfinite(float(literal))


def test_valid_values_build_equal_configs_from_toml_and_json(tmp_path: Path):
    """
    [Unit] config message parity: the same valid options give equal Configs from TOML and JSON.

    Scenario:
        Given one option of each value kind (string, bool, int, float, list, table array)
        When load_config reads them as TOML and as JSON
        Then the two Configs are equal and differ from the defaults.

    Boundaries:
        - Focus: the shared builder on the happy path
        - Fixtures/params: tmp_path
        - Scope: project files only

    On failure, first check:
        - That the JSON reader returns the same Python types tomllib does
    """
    options: dict[str, object] = {
        "profile": "standard",
        "require_fence_languages": True,
        "first_heading_level": 2,
        "max_grade_level": 16.5,
        "select": ["DS1"],
        "telemetry_domains": [{"glob": "docs/**", "domain": "guides"}],
    }
    toml_root = tmp_path / "toml"
    json_root = tmp_path / "json"
    toml_root.mkdir()
    json_root.mkdir()
    toml_text = "".join(f"{key} = {_toml_value(value)}\n" for key, value in options.items())
    (toml_root / "docsentinel.toml").write_text(toml_text, encoding="utf-8")
    json_file = json_root / "config.json"
    json_file.write_text(json.dumps(options), encoding="utf-8")

    from_toml = load_config(toml_root, user_settings=False)
    from_json = load_config(json_root, json_file, user_settings=False)

    assert from_toml == from_json
    assert from_json.profile == "standard"
    assert from_json.max_grade_level == 16.5
    assert from_json.telemetry_domains == (("docs/**", "guides"),)
