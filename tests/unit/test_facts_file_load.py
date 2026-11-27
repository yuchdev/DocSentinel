"""``load_facts_file``: the facts file of ``scan --include-facts`` (owner ruling of 2026-11-27).

The file is the ``facts-json`` output of ``extract-facts`` (schema ``docsentinel-facts`` 1). Every
listed fact is taken in file order whatever its ``disposition``; each refusal is a ``ConfigError``
whose message names the file and never echoes a fact text. Each file is written inline into
``tmp_path``; no asset is loaded.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from docsentinel.config import ConfigError
from docsentinel.detectors import fact_check
from docsentinel.detectors.fact_check import (
    MAX_CANDIDATE_CHARS,
    MAX_FACTS_FILE_BYTES,
    MAX_FACTS_FILE_ENTRIES,
    FileClaim,
    load_facts_file,
)

#: A fact text that must never appear in an error message.
_SECRET_TEXT = "Private roadmap claim 0010."


def _payload(facts: object, **header: object) -> dict[str, object]:
    """Return a facts-json payload.

    :param facts: The ``facts`` value.
    :param header: Replacements of ``schema``/``schema_version``.
    :returns: The payload.
    """
    payload: dict[str, object] = {"schema": "docsentinel-facts", "schema_version": 1}
    payload.update(header)
    payload["facts"] = facts
    return payload


def _write(tmp_path: Path, content: object, *, raw: bool = False) -> Path:
    """Write a facts file and return its path.

    :param tmp_path: Pytest temporary directory.
    :param content: The payload (dumped as JSON) or, with ``raw``, the exact bytes.
    :param raw: Write ``content`` as bytes unchanged.
    :returns: The file path.
    """
    path = tmp_path / "facts.json"
    path.write_bytes(content if raw else json.dumps(content).encode("utf-8"))  # type: ignore[arg-type]
    return path


def test_every_fact_is_taken_in_file_order_whatever_its_disposition(tmp_path: Path):
    """
    [Unit] facts file: verifies every listed fact becomes a candidate, in file order.

    Scenario:
        Given a facts-json file with three facts whose dispositions are total_cap, selected and
        below_floor, listed out of rank order, one with surrounding whitespace, a paragraph index
        and a score
        When load_facts_file reads it
        Then three candidates come back in file order with the stripped text, a FileClaim origin
        (paragraph_index 0 when absent) and the score (0.0 when absent or out of range).

    Boundaries:
        - Focus: owner ruling 2026-11-27 (the file is the selection)
        - Fixtures/params: tmp_path
        - Scope: fact_check.load_facts_file

    On failure, first check:
        - The entry loop of load_facts_file
    """
    facts = [
        {
            "rank": 3,
            "path": "b.md",
            "text": "  Third. ",
            "disposition": "total_cap",
            "paragraph_index": 4,
            "score": 0.7,
        },
        {"rank": 1, "path": "a.md", "text": "First.", "disposition": "selected"},
        {"rank": 2, "path": "a.md", "text": "Second.", "disposition": "below_floor", "score": 1.5},
    ]

    candidates = load_facts_file(_write(tmp_path, _payload(facts)))

    assert [(c.text, c.claim, c.score) for c in candidates] == [
        ("Third.", FileClaim("b.md", 4), 0.7),
        ("First.", FileClaim("a.md", 0), 0.0),
        ("Second.", FileClaim("a.md", 0), 0.0),
    ]


def test_boundaries_are_accepted(tmp_path: Path):
    """
    [Unit] facts file: verifies an empty list, MAX_FACTS_FILE_ENTRIES facts and a 1000-character text load.

    Scenario:
        Given a file with no facts, then one with MAX_FACTS_FILE_ENTRIES facts, the first of
        exactly MAX_CANDIDATE_CHARS characters, and a str path argument
        When load_facts_file reads them
        Then () and MAX_FACTS_FILE_ENTRIES candidates come back.

    Boundaries:
        - Focus: inclusive bounds
        - Fixtures/params: tmp_path
        - Scope: fact_check.load_facts_file

    On failure, first check:
        - The entry count and text length checks of load_facts_file
    """
    assert load_facts_file(_write(tmp_path, _payload([]))) == ()
    facts = [{"path": "a.md", "text": "x" * MAX_CANDIDATE_CHARS}]
    facts += [{"path": "a.md", "text": f"Fact {n}."} for n in range(MAX_FACTS_FILE_ENTRIES - 1)]

    candidates = load_facts_file(str(_write(tmp_path, _payload(facts))))

    assert len(candidates) == MAX_FACTS_FILE_ENTRIES
    assert candidates[0].text == "x" * MAX_CANDIDATE_CHARS


@pytest.mark.parametrize(
    ("content", "raw", "message"),
    [
        (b"\xff\xfe{}", True, "not valid UTF-8 JSON"),
        (b"{not json", True, "not valid UTF-8 JSON"),
        (
            b'{"schema": "docsentinel-facts", "schema": "docsentinel-facts", "schema_version": 1, "facts": []}',
            True,
            "not valid UTF-8 JSON",
        ),
        ([], False, "not a facts-json file (schema docsentinel-facts 1)"),
        (_payload([], schema="docsentinel-report"), False, "not a facts-json file"),
        (_payload([], schema_version=2), False, "not a facts-json file"),
        (_payload({"text": _SECRET_TEXT}), False, "facts must be a list"),
        (_payload([{"path": "a.md", "text": "ok"}] * (MAX_FACTS_FILE_ENTRIES + 1)), False, "more than 500 facts"),
        (_payload([{"path": "a.md"}]), False, "fact 1 needs a text of 1 to 1000 characters"),
        (_payload([{"path": "a.md", "text": "   "}]), False, "fact 1 needs a text of 1 to 1000 characters"),
        (_payload([{"path": "a.md", "text": 7}]), False, "fact 1 needs a text of 1 to 1000 characters"),
        (
            _payload([{"path": "a.md", "text": "ok"}, {"path": "a.md", "text": "y" * (MAX_CANDIDATE_CHARS + 1)}]),
            False,
            "fact 2 needs a text of 1 to 1000 characters",
        ),
        (_payload([{"text": _SECRET_TEXT}]), False, "fact 1 needs a path"),
        (_payload([{"text": _SECRET_TEXT, "path": ""}]), False, "fact 1 needs a path"),
        (_payload([{"text": _SECRET_TEXT, "path": "p" * 1025}]), False, "fact 1 needs a path"),
        (_payload(["just a string"]), False, "fact 1 needs a text"),
    ],
    ids=[
        "not-utf8",
        "not-json",
        "duplicate-key",
        "not-an-object",
        "wrong-schema",
        "wrong-version",
        "facts-not-list",
        "too-many",
        "no-text",
        "blank-text",
        "text-not-str",
        "text-too-long",
        "no-path",
        "empty-path",
        "path-too-long",
        "entry-not-object",
    ],
)
def test_invalid_files_are_a_config_error(tmp_path: Path, content: object, raw: bool, message: str):
    """
    [Unit] facts file: verifies each malformed file is a ConfigError naming the file, never the text.

    Scenario:
        Given a facts file breaking one rule (encoding, JSON, duplicate key, schema, list shape,
        entry count, text or path of an entry)
        When load_facts_file reads it
        Then ConfigError is raised, its message starts with 'facts file <path>: ', contains the
        rule's fixed text and never the fact text.

    Boundaries:
        - Focus: owner ruling 2026-11-27 (fail closed, exit 2 in the CLI)
        - Fixtures/params: content, raw, message
        - Scope: fact_check.load_facts_file

    On failure, first check:
        - The refusal branches of load_facts_file
    """
    path = _write(tmp_path, content, raw=raw)

    with pytest.raises(ConfigError) as caught:
        load_facts_file(path)

    text = str(caught.value)
    assert text.startswith(f"facts file {path}: ")
    assert message in text
    assert _SECRET_TEXT not in text
    assert caught.value.__cause__ is None


def test_missing_and_oversized_files_are_a_config_error(tmp_path: Path):
    """
    [Unit] facts file: verifies a missing file, a directory and a file over 1 MiB are refused.

    Scenario:
        Given a path that does not exist, a directory, and a file of MAX_FACTS_FILE_BYTES + 1 bytes
        When load_facts_file reads each
        Then ConfigError names 'cannot read it (<exception type>)' or 'larger than 1048576 bytes'.

    Boundaries:
        - Focus: bounded read and readable-file check
        - Fixtures/params: tmp_path
        - Scope: fact_check.load_facts_file

    On failure, first check:
        - The open/read and size check of load_facts_file
    """
    with pytest.raises(ConfigError, match=r"cannot read it \(FileNotFoundError\)$"):
        load_facts_file(tmp_path / "missing.json")
    with pytest.raises(ConfigError, match=r"cannot read it \((IsADirectoryError|PermissionError)\)$"):
        load_facts_file(tmp_path)
    big = tmp_path / "big.json"
    big.write_bytes(b" " * (MAX_FACTS_FILE_BYTES + 1))
    with pytest.raises(ConfigError, match=f"larger than {MAX_FACTS_FILE_BYTES} bytes$"):
        load_facts_file(big)


def test_limits_are_as_ruled():
    """
    [Unit] facts file: verifies the size, entry and schema constants.

    Scenario:
        Given the module constants
        When they are read
        Then the byte cap is 1 MiB, the entry cap 500 and the schema ('docsentinel-facts', 1).

    Boundaries:
        - Focus: owner ruling 2026-11-27 limits
        - Fixtures/params: none
        - Scope: module constants

    On failure, first check:
        - MAX_FACTS_FILE_BYTES, MAX_FACTS_FILE_ENTRIES and FACTS_FILE_SCHEMA in detectors/fact_check.py
    """
    assert (MAX_FACTS_FILE_BYTES, MAX_FACTS_FILE_ENTRIES) == (1_048_576, 500)
    assert fact_check.FACTS_FILE_SCHEMA == ("docsentinel-facts", 1)
