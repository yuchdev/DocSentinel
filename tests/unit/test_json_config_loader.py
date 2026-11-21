"""Unit tests for the strict JSON configuration reader (Milestone 0009 Story 03.0, Task 06 Step 1).

Covers ``load_json_options`` and its open-once reader ``_read_config_once``: the size cap,
strict UTF-8 without a byte-order mark, duplicate keys at any depth, non-finite and
overflowing numbers, nesting, ``null`` and lone surrogates anywhere, the top-level shape and
the unknown-key message shared with TOML (plan contract C7; threat model
docs/security/threat-model-0009-user-settings-2026-11-17.md U2, U6, U8, U9, U11, T03-1).
Every input is an inline string written to ``tmp_path`` in the test body; no asset is loaded.
"""

from __future__ import annotations

import builtins
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

from docsentinel.config import (
    MAX_JSON_CONFIG_BYTES,
    ConfigError,
    _load_toml_table,
    load_json_options,
)

#: A marker written into files to prove that no message echoes file content (U11).
_SENTINEL = "SENTINEL_CONTENT_7f3a"


def _write(tmp_path: Path, data: Any, name: str = "config.json") -> Path:
    """Write ``data`` (``str`` as UTF-8, or ``bytes`` verbatim) to ``tmp_path/name``.

    :param tmp_path: The test's temporary directory.
    :param data: The file content.
    :param name: The file name.
    :returns: The written path.
    """
    path = tmp_path / name
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")
    return path


def _error(tmp_path: Path, data: Any) -> str:
    """Return the ``ConfigError`` message ``load_json_options`` raises for ``data``.

    :param tmp_path: The test's temporary directory.
    :param data: The file content.
    :returns: The message text.
    """
    with pytest.raises(ConfigError) as caught:
        load_json_options(_write(tmp_path, data))
    return str(caught.value)


def _padded_object(size: int) -> bytes:
    """Return a valid JSON object of exactly ``size`` bytes, padded with spaces.

    :param size: The total byte length.
    :returns: ``{"profile": "fast"<spaces>}``.
    """
    head = b'{"profile": "fast"'
    return head + b" " * (size - len(head) - 1) + b"}"


def test_valid_object_keeps_int_and_float_types(tmp_path: Path):
    """
    [Unit] json config: a valid object maps to the raw options with TOML's number types.

    Scenario:
        Given a JSON object with a string, a list, an integer, a float and a boolean option
        When load_json_options reads it
        Then the mapping is returned unchanged, 5 stays an int and 16.0 stays a float, and an
            empty object is accepted as an empty mapping.

    Boundaries:
        - Focus: load_json_options happy path (story "Strict JSON parsing" step 6 note)
        - Fixtures/params: tmp_path
        - Scope: the reader only; no Config is built

    On failure, first check:
        - parse_float/parse_int hooks in _parse_json_options
        - That the top-level type check still uses type(parsed) is dict
    """
    text = (
        '{"profile": "standard", "select": ["DS1"], "min_document_words": 5, '
        '"max_grade_level": 16.0, "deep_confirm": true}'
    )

    options = load_json_options(_write(tmp_path, text))

    assert options == {
        "profile": "standard",
        "select": ["DS1"],
        "min_document_words": 5,
        "max_grade_level": 16.0,
        "deep_confirm": True,
    }
    assert type(options["min_document_words"]) is int
    assert type(options["max_grade_level"]) is float
    assert load_json_options(_write(tmp_path, "{}", "empty.json")) == {}


def test_json_loader_reads_once_from_one_descriptor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] json config U2: the file is opened exactly once and read only from that descriptor.

    Scenario:
        Given a valid JSON config file
        When load_json_options reads it with os.open/os.fstat/os.read/os.close spied
        Then os.open runs once with O_NONBLOCK, fstat, every read and the close use that same
            descriptor, and neither builtins.open nor Path.open is used for the file.

    Boundaries:
        - Focus: _read_config_once (threat model R7, amendment A1)
        - Fixtures/params: tmp_path, monkeypatch
        - Scope: spies delegate to the real calls

    On failure, first check:
        - That _read_config_once opens once and never reopens the path
        - That the read loop uses os.read on the same descriptor
    """
    source = _write(tmp_path, '{"profile": "deep"}')
    opened: list[tuple[str, int, int]] = []
    fstat_fds: list[int] = []
    read_fds: list[int] = []
    closed_fds: list[int] = []
    real_open, real_fstat, real_read, real_close = os.open, os.fstat, os.read, os.close

    def spy_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        """Record the opened path and flags, then delegate."""
        descriptor = real_open(path, flags, *args, **kwargs)
        opened.append((os.fspath(path), flags, descriptor))
        return descriptor

    def spy_fstat(descriptor: int) -> os.stat_result:
        """Record the descriptor, then delegate."""
        fstat_fds.append(descriptor)
        return real_fstat(descriptor)

    def spy_read(descriptor: int, size: int) -> bytes:
        """Record the descriptor, then delegate."""
        read_fds.append(descriptor)
        return real_read(descriptor, size)

    def spy_close(descriptor: int):
        """Record the descriptor, then delegate."""
        closed_fds.append(descriptor)
        real_close(descriptor)

    def refuse_open(*args: Any, **kwargs: Any) -> Any:
        """Fail the test if a high-level open reads the config file."""
        raise AssertionError(f"unexpected high-level open: {args!r}")

    monkeypatch.setattr(os, "open", spy_open)
    monkeypatch.setattr(os, "fstat", spy_fstat)
    monkeypatch.setattr(os, "read", spy_read)
    monkeypatch.setattr(os, "close", spy_close)
    monkeypatch.setattr(builtins, "open", refuse_open)
    monkeypatch.setattr(Path, "open", refuse_open)

    options = load_json_options(source)

    monkeypatch.undo()
    assert options == {"profile": "deep"}
    assert len(opened) == 1
    path, flags, descriptor = opened[0]
    assert path == os.fspath(source)
    assert flags & os.O_NONBLOCK
    assert fstat_fds == [descriptor]
    assert read_fds and set(read_fds) == {descriptor}
    assert closed_fds == [descriptor]


def test_json_size_exactly_1mib_accepted(tmp_path: Path):
    """
    [Unit] json config U6: a file of exactly MAX_JSON_CONFIG_BYTES bytes is accepted.

    Scenario:
        Given a valid JSON object padded with spaces to exactly 1,048,576 bytes
        When load_json_options reads it
        Then the object is returned.

    Boundaries:
        - Focus: the inclusive upper bound of the size cap (M11)
        - Fixtures/params: tmp_path
        - Scope: the reader only

    On failure, first check:
        - The comparison len(data) > MAX_JSON_CONFIG_BYTES in _parse_json_options
        - That the bounded read asks for MAX_JSON_CONFIG_BYTES + 1 bytes
    """
    data = _padded_object(MAX_JSON_CONFIG_BYTES)
    assert len(data) == 1_048_576

    assert load_json_options(_write(tmp_path, data)) == {"profile": "fast"}


@pytest.mark.parametrize("trailer", [b" ", b"\n"], ids=["space", "newline"])
def test_json_size_1mib_plus_one_refused(tmp_path: Path, trailer: bytes):
    """
    [Unit] json config U6: one byte over 1 MiB is refused with the size phrase.

    Scenario:
        Given an otherwise valid object of exactly 1 MiB plus one trailing byte
        When load_json_options reads it
        Then ConfigError "Cannot read JSON config: larger than 1 MiB" is raised.

    Boundaries:
        - Focus: the exclusive bound of the size cap (M11)
        - Fixtures/params: tmp_path, trailer (space, newline)
        - Scope: the reader only

    On failure, first check:
        - The size check runs before decoding and parsing
    """
    data = _padded_object(MAX_JSON_CONFIG_BYTES) + trailer

    assert _error(tmp_path, data) == "Cannot read JSON config: larger than 1 MiB"


def test_json_deep_nesting_100k_refused_as_nested_too_deeply(tmp_path: Path):
    """
    [Unit] json config U6: 100,000 nested arrays are refused as nested too deeply.

    Scenario:
        Given an option whose value is 100,000 nested arrays
        When load_json_options reads it
        Then ConfigError "nested too deeply" is raised, not a RecursionError.

    Boundaries:
        - Focus: RecursionError mapping in _parse_json_options (M13)
        - Fixtures/params: tmp_path
        - Scope: the reader only

    On failure, first check:
        - The except order ConfigError, RecursionError, JSONDecodeError, ValueError
    """
    text = '{"select": ' + "[" * 100_000 + "]" * 100_000 + "}"

    assert _error(tmp_path, text) == "Cannot read JSON config: nested too deeply"


def test_json_null_walk_iterative_at_depth_3000(tmp_path: Path):
    """
    [Unit] json config U6: a null 3,000 levels deep is found by an iterative walk.

    Scenario:
        Given an option holding a null nested 3,000 arrays deep (deeper than the
            interpreter's recursion limit of 1,000) that the JSON scanner accepts
        When load_json_options reads it
        Then ConfigError with the null phrase is raised and no RecursionError escapes.

    Boundaries:
        - Focus: _json_check_values explicit-stack walk (M13)
        - Fixtures/params: tmp_path
        - Scope: the reader only

    On failure, first check:
        - That _json_check_values never recurses
    """
    depth = 3000
    assert depth > sys.getrecursionlimit()
    text = '{"select": ' + "[" * depth + "null" + "]" * depth + "}"

    assert _error(tmp_path, text) == "Cannot read JSON config: null is not allowed; omit the key"


def test_json_100k_digit_integer_is_config_error(tmp_path: Path):
    """
    [Unit] json config U6: a 100,000-digit integer is a ConfigError, not a stray ValueError.

    Scenario:
        Given an integer option whose literal has 100,000 digits
        When load_json_options reads it
        Then ConfigError "number out of range" is raised.

    Boundaries:
        - Focus: the integer-string limit mapping (M14)
        - Fixtures/params: tmp_path
        - Scope: the reader only

    On failure, first check:
        - The ValueError clause after JSONDecodeError in _parse_json_options
    """
    text = '{"min_document_words": ' + "9" * 100_000 + "}"

    assert _error(tmp_path, text) == "Cannot read JSON config: number out of range"


@pytest.mark.parametrize(
    ("encoding", "expected"),
    [
        ("utf-16", "Cannot read JSON config: not valid UTF-8"),
        ("utf-32", "Cannot read JSON config: not valid UTF-8"),
        # No BOM: the NUL bytes are valid UTF-8, so the decoded str is invalid JSON.
        ("utf-16-le", "Cannot read JSON config: invalid JSON at line 1, column 2"),
    ],
)
def test_json_utf16_file_refused_as_not_utf8(tmp_path: Path, encoding: str, expected: str):
    """
    [Unit] json config U6: a UTF-16 or UTF-32 file is refused; no encoding is auto-detected.

    Scenario:
        Given a valid JSON object encoded as UTF-16 or UTF-32
        When load_json_options reads it
        Then a BOM-prefixed file is refused as not valid UTF-8 and a BOM-less UTF-16 file
            as invalid JSON; neither is decoded the way json.loads(bytes) would.

    Boundaries:
        - Focus: strict UTF-8 decode before json.loads receives a str (M12)
        - Fixtures/params: tmp_path, encoding
        - Scope: the reader only

    On failure, first check:
        - That _parse_json_options passes a str, never bytes, to json.loads
    """
    data = '{"profile": "fast"}'.encode(encoding)

    assert _error(tmp_path, data) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"profile": "fast", "profile": "deep"}', "Cannot read JSON config: duplicate key profile"),
        ('{"max_grade_level": NaN}', "Cannot read JSON config: NaN and Infinity are not allowed"),
        ('{"max_grade_level": 1e400}', "Cannot read JSON config: number out of range"),
    ],
    ids=["object_pairs_hook", "parse_constant", "parse_float"],
)
def test_hook_config_error_not_rewrapped(tmp_path: Path, text: str, expected: str):
    """
    [Unit] json config U6: a ConfigError raised inside a json hook propagates unchanged.

    Scenario:
        Given input that trips each of the three json.loads hooks
        When load_json_options reads it
        Then the hook's own message is raised exactly once, never rewritten as invalid JSON
            or prefixed twice.

    Boundaries:
        - Focus: the "except ConfigError: raise" clause (amendment A3)
        - Fixtures/params: tmp_path, text (one per hook)
        - Scope: the reader only

    On failure, first check:
        - The except order in _parse_json_options
    """
    message = _error(tmp_path, text)

    assert message == expected
    assert "invalid JSON" not in message
    assert message.count("Cannot read JSON config") == 1


def test_json_1e400_refused(tmp_path: Path):
    """
    [Unit] json config U8: 1e400 overflows to infinity and is refused; 1e308 is accepted.

    Scenario:
        Given max_grade_level written as 1e400, and separately as 1e308
        When load_json_options reads each
        Then 1e400 raises "number out of range" and 1e308 is returned as a finite float.

    Boundaries:
        - Focus: _json_finite_float (parse_float)
        - Fixtures/params: tmp_path
        - Scope: the reader only

    On failure, first check:
        - math.isfinite in _json_finite_float
    """
    assert _error(tmp_path, '{"max_grade_level": 1e400}') == "Cannot read JSON config: number out of range"
    assert load_json_options(_write(tmp_path, '{"max_grade_level": 1e308}', "ok.json")) == {"max_grade_level": 1e308}


def test_json_negative_1e400_refused(tmp_path: Path):
    """
    [Unit] json config U8: -1e400 overflows to negative infinity and is refused.

    Scenario:
        Given duplicate_similarity written as -1e400
        When load_json_options reads it
        Then ConfigError "number out of range" is raised.

    Boundaries:
        - Focus: _json_finite_float for the negative overflow
        - Fixtures/params: tmp_path
        - Scope: the reader only

    On failure, first check:
        - That the check is isfinite, not a positive-only comparison
    """
    assert _error(tmp_path, '{"duplicate_similarity": -1e400}') == "Cannot read JSON config: number out of range"


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_json_non_finite_constants_refused(tmp_path: Path, constant: str):
    """
    [Unit] json config U8: the JSON extensions NaN, Infinity and -Infinity are refused.

    Scenario:
        Given a float option whose value is a non-finite constant
        When load_json_options reads it
        Then ConfigError "NaN and Infinity are not allowed" is raised.

    Boundaries:
        - Focus: _json_refuse_constant (parse_constant)
        - Fixtures/params: tmp_path, constant
        - Scope: the reader only

    On failure, first check:
        - That parse_constant is passed to json.loads
    """
    message = _error(tmp_path, f'{{"max_grade_level": {constant}}}')

    assert message == "Cannot read JSON config: NaN and Infinity are not allowed"


def test_duplicate_key_top_level(tmp_path: Path):
    """
    [Unit] json config U9: a duplicate top-level key is refused, never last-wins.

    Scenario:
        Given two ignore keys at the top level
        When load_json_options reads the file
        Then ConfigError names the duplicate key.

    Boundaries:
        - Focus: _json_object_pairs at depth 0
        - Fixtures/params: tmp_path
        - Scope: the reader only

    On failure, first check:
        - That object_pairs_hook is passed to json.loads
    """
    message = _error(tmp_path, '{"ignore": [], "profile": "fast", "ignore": ["DS"]}')

    assert message == "Cannot read JSON config: duplicate key ignore"


def test_duplicate_key_nested(tmp_path: Path):
    """
    [Unit] json config U9: a duplicate key inside a nested object is refused.

    Scenario:
        Given a telemetry_domains entry with two glob keys
        When load_json_options reads the file
        Then ConfigError names the nested duplicate key.

    Boundaries:
        - Focus: _json_object_pairs at depth 2 (array of objects)
        - Fixtures/params: tmp_path
        - Scope: the reader only

    On failure, first check:
        - That the hook applies to every object, not only the top level
    """
    text = '{"telemetry_domains": [{"glob": "a/**", "glob": "b/**", "domain": "x"}]}'

    assert _error(tmp_path, text) == "Cannot read JSON config: duplicate key glob"


def test_duplicate_key_escaped_spelling(tmp_path: Path):
    """
    [Unit] json config U9: a duplicate spelled with a \\u escape is caught on the decoded key.

    Scenario:
        Given "ignore" and "\\u0069gnore" in one object
        When load_json_options reads the file
        Then ConfigError names the decoded key "ignore".

    Boundaries:
        - Focus: duplicate detection compares decoded keys
        - Fixtures/params: tmp_path
        - Scope: the reader only

    On failure, first check:
        - That _json_object_pairs compares the decoded str keys
    """
    text = '{"ignore": [], "\\u0069gnore": ["DS"]}'

    assert _error(tmp_path, text) == "Cannot read JSON config: duplicate key ignore"


def test_bom_refused(tmp_path: Path):
    """
    [Unit] json config U9: a UTF-8 byte-order mark is refused.

    Scenario:
        Given a valid object preceded by EF BB BF
        When load_json_options reads it
        Then ConfigError "starts with a byte-order mark" is raised.

    Boundaries:
        - Focus: the explicit BOM check before decoding
        - Fixtures/params: tmp_path
        - Scope: the reader only

    On failure, first check:
        - data.startswith(b"\\xef\\xbb\\xbf") in _parse_json_options
    """
    assert (
        _error(tmp_path, b'\xef\xbb\xbf{"profile": "fast"}') == "Cannot read JSON config: starts with a byte-order mark"
    )


def test_invalid_utf8_refused(tmp_path: Path):
    """
    [Unit] json config: an invalid UTF-8 byte is refused without echoing the bytes.

    Scenario:
        Given an object whose string value holds the byte 0xFF
        When load_json_options reads it
        Then ConfigError "not valid UTF-8" is raised.

    Boundaries:
        - Focus: the strict decode in _parse_json_options
        - Fixtures/params: tmp_path
        - Scope: the reader only

    On failure, first check:
        - errors="strict" in the decode call
    """
    assert _error(tmp_path, b'{"profile": "\xff"}') == "Cannot read JSON config: not valid UTF-8"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("null", "Cannot read JSON config: the top level must be an object"),
        ('{"profile": null}', "Cannot read JSON config: null is not allowed; omit the key"),
        ('{"select": ["DS1", null]}', "Cannot read JSON config: null is not allowed; omit the key"),
        (
            '{"telemetry_domains": [{"glob": "a", "domain": null}]}',
            "Cannot read JSON config: null is not allowed; omit the key",
        ),
    ],
    ids=["top_level", "option_value", "list_item", "nested_object"],
)
def test_null_top_level_and_nested(tmp_path: Path, text: str, expected: str):
    """
    [Unit] json config U9: null is refused at the top level and at every nested depth.

    Scenario:
        Given null as the whole document, as an option value, as a list item and inside a
            nested object
        When load_json_options reads each
        Then each is a ConfigError: the top-level shape phrase, otherwise the null phrase.

    Boundaries:
        - Focus: the top-level type check and _json_check_values
        - Fixtures/params: tmp_path, text
        - Scope: the reader only

    On failure, first check:
        - That _json_check_values walks dict values and list items
    """
    assert _error(tmp_path, text) == expected


@pytest.mark.parametrize("text", ["[]", '["profile"]', '"profile"', "5", "true"])
def test_top_level_must_be_object(tmp_path: Path, text: str):
    """
    [Unit] json config: an array, string, number or boolean at the top level is refused.

    Scenario:
        Given a document whose top-level value is not an object
        When load_json_options reads it
        Then ConfigError "the top level must be an object" is raised.

    Boundaries:
        - Focus: type(parsed) is dict check
        - Fixtures/params: tmp_path, text
        - Scope: the reader only

    On failure, first check:
        - The top-level type check in _parse_json_options
    """
    assert _error(tmp_path, text) == "Cannot read JSON config: the top level must be an object"


def test_duplicate_key_name_bounded_and_neutralised(tmp_path: Path):
    """
    [Unit] json config U9: the echoed duplicate key is cut to 80 characters and neutralised.

    Scenario:
        Given a duplicated 201-character key that starts with U+202E (RIGHT-TO-LEFT OVERRIDE)
            and holds an ESC
        When load_json_options reads it
        Then the message carries no raw U+202E or ESC, shows them as escapes, and the echoed
            key is at most 80 characters plus the "..." marker.

    Boundaries:
        - Focus: safe(key, 80) in _json_object_pairs
        - Fixtures/params: tmp_path
        - Scope: the reader only

    On failure, first check:
        - _JSON_DUPLICATE_KEY_ECHO_LIMIT and docsentinel.log.safe
    """
    key = "‮\x1b" + "k" * 199
    text = "{" + json.dumps(key) + ": 1, " + json.dumps(key) + ": 2}"

    message = _error(tmp_path, text)

    prefix = "Cannot read JSON config: duplicate key "
    assert message.startswith(prefix)
    echoed = message[len(prefix) :]
    assert "‮" not in message and "\x1b" not in message
    assert echoed.startswith("\\u202e\\x1b")
    assert echoed.endswith("...")
    assert len(echoed) == 80 + len("...")


@pytest.mark.parametrize(
    "text",
    ['{"profile": "\\ud800"}', '{"\\udc00": 1}', '{"select": ["DS1", "\\udfff"]}'],
    ids=["value", "key", "list_item"],
)
def test_json_lone_surrogate_refused(tmp_path: Path, text: str):
    """
    [Unit] json config T03-1: a lone surrogate in a key or string is refused before validation.

    Scenario:
        Given a lone surrogate written as a \\u escape in a value, a key and a list item
        When load_json_options reads each
        Then ConfigError "lone surrogate is not allowed" is raised (not an unknown-key or
            validator message, and never a later UnicodeEncodeError).

    Boundaries:
        - Focus: _json_check_values surrogate check (threat model T03-1)
        - Fixtures/params: tmp_path, text
        - Scope: the reader only

    On failure, first check:
        - _LONE_SURROGATE_PATTERN and that keys are walked as well as values
    """
    assert _error(tmp_path, text) == "Cannot read JSON config: lone surrogate is not allowed"


def test_json_surrogate_pair_is_valid_text(tmp_path: Path):
    """
    [Unit] json config T03-1 boundary: an escaped surrogate pair decodes to one valid character.

    Scenario:
        Given a fence-language entry written as the pair \\ud83d\\ude00
        When load_json_options reads it
        Then it is accepted as the single code point U+1F600.

    Boundaries:
        - Focus: only unpaired surrogates are refused
        - Fixtures/params: tmp_path
        - Scope: the reader only

    On failure, first check:
        - That the surrogate check runs on the decoded str, not the raw text
    """
    options = load_json_options(_write(tmp_path, '{"allowed_fence_languages": ["\\ud83d\\ude00"]}'))

    assert options == {"allowed_fence_languages": ["\U0001f600"]}


@pytest.mark.parametrize(
    ("text", "position"),
    [
        # Python 3.13 reports a trailing comma at the comma itself; 3.12 at the closing brace.
        ('{"profile": "fast",}', "line 1, column 19" if sys.version_info >= (3, 13) else "line 1, column 20"),
        ("{\n  \"profile\": 'fast'\n}", "line 2, column 14"),
    ],
    ids=["trailing_comma", "single_quotes"],
)
def test_invalid_json_reports_line_and_column_only(tmp_path: Path, text: str, position: str):
    """
    [Unit] json config: a syntax error reports its line and column only (no JSON5).

    Scenario:
        Given a trailing comma, and single-quoted strings
        When load_json_options reads each
        Then ConfigError "invalid JSON at line L, column C" is raised.

    Boundaries:
        - Focus: JSONDecodeError mapping in _parse_json_options
        - Fixtures/params: tmp_path, text, position
        - Scope: the reader only

    On failure, first check:
        - The JSONDecodeError clause uses exc.lineno and exc.colno only
        - The interpreter's json module: 3.13 moved the trailing-comma position to the comma
    """
    assert _error(tmp_path, text) == f"Cannot read JSON config: invalid JSON at {position}"


def test_unknown_key_message_equal_to_toml(tmp_path: Path):
    """
    [Unit] json config: unknown keys give exactly the TOML reader's message.

    Scenario:
        Given the unknown keys "zeta" and "alpha" written as TOML and as JSON
        When the TOML reader and load_json_options read them
        Then both raise "Unknown config options: alpha, zeta".

    Boundaries:
        - Focus: _require_known_options shared by both readers
        - Fixtures/params: tmp_path
        - Scope: the readers only

    On failure, first check:
        - That _parse_json_options calls _require_known_options
    """
    toml_path = tmp_path / "docsentinel.toml"
    toml_path.write_text('zeta = 1\nalpha = "x"\nprofile = "fast"\n', encoding="utf-8")

    with pytest.raises(ConfigError) as from_toml:
        _load_toml_table(toml_path, wrapped=False)
    from_json = _error(tmp_path, '{"zeta": 1, "alpha": "x", "profile": "fast"}')

    assert str(from_toml.value) == "Unknown config options: alpha, zeta"
    assert from_json == str(from_toml.value)


@pytest.mark.parametrize(
    "data",
    [
        _SENTINEL.encode() + b"{}",
        ('{"profile": "' + _SENTINEL + '", "profile": "fast"}').encode(),
        ('{"profile": "' + _SENTINEL + '"} trailing').encode(),
        ('{"select": ["' + _SENTINEL + '", NaN]}').encode(),
        ('{"select": ["' + _SENTINEL + '", 1e400]}').encode(),
        ('{"select": ["' + _SENTINEL + '", null]}').encode(),
        ('{"select": ["' + _SENTINEL + '\\ud800"]}').encode(),
        ('["' + _SENTINEL + '"]').encode(),
        b"\xef\xbb\xbf" + ('{"profile": "' + _SENTINEL + '"}').encode(),
        ('{"profile": "' + _SENTINEL + '\xff"}').encode("latin-1"),
        ('{"select": ' + "[" * 100_000 + '"' + _SENTINEL + '"' + "]" * 100_000 + "}").encode(),
        ('{"profile": "' + _SENTINEL + '"' + " " * MAX_JSON_CONFIG_BYTES + "}").encode(),
    ],
    ids=[
        "syntax",
        "duplicate",
        "trailing_data",
        "nan",
        "overflow",
        "null",
        "surrogate",
        "top_level_array",
        "bom",
        "invalid_utf8",
        "nesting",
        "oversized",
    ],
)
def test_config_error_never_echoes_file_content(tmp_path: Path, data: bytes):
    """
    [Unit] json config U11: no reader error message echoes a value from the file.

    Scenario:
        Given a sentinel string placed in a value of each malformed file kind
        When load_json_options refuses the file
        Then the ConfigError message does not contain the sentinel.

    Boundaries:
        - Focus: fixed, path-free reason phrases (ADR 0005 Contract 5)
        - Fixtures/params: tmp_path, data (one per refusal reason)
        - Scope: the reader only; unknown and duplicate key *names* are echoed by design
            (F2), so the sentinel is placed in values here

    On failure, first check:
        - Every _json_config_error call site uses a fixed phrase
    """
    message = _error(tmp_path, data)

    assert message.startswith("Cannot read JSON config: ")
    assert _SENTINEL not in message


def test_reader_refuses_non_regular_file(tmp_path: Path):
    """
    [Unit] json config: a directory or an absent path is refused without a path in the message.

    Scenario:
        Given a directory named config.json, and an absent file
        When load_json_options reads each
        Then the directory gives "not a regular file" and the absent file "not readable";
            neither message contains the path.

    Boundaries:
        - Focus: the os.stat pre-check and OSError mapping in _read_config_once
        - Fixtures/params: tmp_path
        - Scope: the reader only

    On failure, first check:
        - The S_ISREG pre-check and the "from None" OSError clause
    """
    directory = tmp_path / "config.json"
    directory.mkdir()

    with pytest.raises(ConfigError) as as_directory:
        load_json_options(directory)
    with pytest.raises(ConfigError) as absent:
        load_json_options(tmp_path / "absent.json")

    assert str(as_directory.value) == "Cannot read JSON config: not a regular file"
    assert str(absent.value) == "Cannot read JSON config: not readable"
    assert str(tmp_path) not in str(as_directory.value) + str(absent.value)
