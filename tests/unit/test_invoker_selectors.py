"""Unit tests for :func:`docsentinel.discovery.normalize_invoker_selectors` (ADR 0006 Contract 3).

Most cases are lexical and use glob values or refused values, so no filesystem call
is reached. Cases whose literal must pass the in-root existence check build a tiny
``tmp_path`` tree inline; no assets are loaded.
"""

import logging
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Optional, Union

import pytest

from docsentinel.config import ConfigError
from docsentinel.discovery import (
    InvokerSelection,
    _lexical_normalize,
    check_invoker_selector_shape,
    normalize_invoker_selectors,
)

_ROOT = Path("/repo")
_HINT = "values are relative to the scan root"
_LOOKALIKE_SEPARATORS = ("∕", "／", "⁄", "⧸", "＼", "﹨")


def _include(*values: str, backslash: bool = False) -> InvokerSelection:
    """Normalise include values against the fictional root ``/repo``.

    :param values: The include values.
    :param backslash: Whether ``\\`` is a separator.
    :returns: The selection.
    """
    return normalize_invoker_selectors(_ROOT, list(values), None, backslash_is_separator=backslash)


def _refused(*values: str, backslash: bool = False, key: str = "include") -> str:
    """Return the ConfigError text for values that must be refused.

    :param values: The values.
    :param backslash: Whether ``\\`` is a separator.
    :param key: ``include`` or ``exclude``.
    :returns: The error message.
    """
    selectors = {"include": None, "exclude": None, key: list(values)}
    with pytest.raises(ConfigError) as caught:
        normalize_invoker_selectors(_ROOT, **selectors, backslash_is_separator=backslash)
    return str(caught.value)


def _tree(tmp_path: Path) -> Path:
    """Build ``root/docs/user/a.md`` and return the canonical root.

    :param tmp_path: The pytest scratch directory.
    :returns: The resolved root.
    """
    root = (tmp_path / "root").resolve()
    (root / "docs" / "user").mkdir(parents=True)
    (root / "docs" / "user" / "a.md").write_text("# A\n", encoding="utf-8")
    return root


def test_glob_normalised_lexically():
    """
    [Unit] discovery: verifies leading ./, repeated and trailing slashes are removed from a glob.

    Scenario:
        Given ./docs//*.md/ and a duplicate spelling of it
        When the include values are normalised
        Then one pattern docs/*.md remains, exclude is () and nothing is unmatched.

    Boundaries:
        - Focus: Contract 3 steps 7 and 11
        - Fixtures/params: none
        - Scope: normalize_invoker_selectors, globs only (no filesystem)

    On failure, first check:
        - _lexical_normalize clean-up and _unique
    """
    selection = _include("./docs//*.md/", "docs/*.md")

    assert selection == InvokerSelection(include=("docs/*.md",), exclude=(), unmatched_exclude=())


def test_not_given_keys_stay_none_and_empty():
    """
    [Unit] discovery: verifies None keys yield include None and exclude ().

    Scenario:
        Given include and exclude both None
        When normalised
        Then the selection is (None, (), ()).

    Boundaries:
        - Focus: "not given" semantics
        - Fixtures/params: none
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The given dict in normalize_invoker_selectors
    """
    assert normalize_invoker_selectors(_ROOT, None, None) == InvokerSelection(None, (), ())


def test_dot_include_is_default_and_dot_exclude_refused():
    """
    [Unit] discovery: verifies . as include is the built-in default include and as exclude is refused.

    Scenario:
        Given include . and then exclude .
        When normalised
        Then the include becomes *.md, **/*.md and the exclude raises ConfigError.

    Boundaries:
        - Focus: Contract 3 step 8
        - Fixtures/params: none
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The empty-parts branch of _lexical_normalize
    """
    assert _include(".", "./").include == ("*.md", "**/*.md")
    assert "excluding the scan root is not allowed" in _refused(".", key="exclude")


@pytest.mark.parametrize("value", ["../other", "docs/../../x", "..", "docs/../x", "**/../*.md"])
def test_dotdot_component_refused_relative(value: str):
    """
    [Unit] discovery: verifies a parent step is refused in relative literals and globs.

    Scenario:
        Given a relative value holding a .. component
        When normalised
        Then a ConfigError names parent steps.

    Boundaries:
        - Focus: threat model M1
        - Fixtures/params: value
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The .. check in _lexical_normalize

    :param value: The refused value.
    """
    assert "parent steps (..) are not allowed" in _refused(value)


def test_dotdot_in_absolute_value_refused_before_normpath():
    """
    [Unit] discovery: verifies /repo/docs/../x is refused, not collapsed by normpath to x.

    Scenario:
        Given an absolute value inside the root spelling that holds a parent step
        When normalised
        Then it is refused like its relative spelling.

    Boundaries:
        - Focus: threat model M1, A1 (check before normpath)
        - Fixtures/params: none
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - Whether normpath runs before the .. check
    """
    assert "parent steps (..) are not allowed" in _refused("/repo/docs/../x")


@pytest.mark.parametrize("value", ["/repo-other/x", "/etc/passwd", "/"])
def test_absolute_sibling_prefix_refused(value: str):
    """
    [Unit] discovery: verifies a sibling sharing the root's prefix is outside the root.

    Scenario:
        Given root /repo and an absolute value outside it
        When normalised
        Then the single "is outside the scan root" message is raised.

    Boundaries:
        - Focus: threat model M2 (separator-aware _within)
        - Fixtures/params: value
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - A bare startswith in _relative_to_spellings

    :param value: The outside value.
    """
    message = _refused(value)

    assert message.endswith(f"is outside the scan root; {_HINT}")


def test_absolute_inside_root_made_relative(tmp_path: Path):
    """
    [Unit] discovery: verifies an absolute literal inside the root is made relative.

    Scenario:
        Given a real root holding docs/user
        When <root>/docs/user/ is normalised
        Then the include is docs/user.

    Boundaries:
        - Focus: threat model M2, Contract 3 step 6
        - Fixtures/params: tmp_path
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - _relative_to_spellings prefix removal
    """
    root = _tree(tmp_path)

    selection = normalize_invoker_selectors(root, [f"{root}/docs/user/"], None)

    assert selection.include == ("docs/user",)


def test_absolute_equal_root_is_dot(tmp_path: Path):
    """
    [Unit] discovery: verifies an absolute value equal to the root becomes . (the default include).

    Scenario:
        Given the root itself as an absolute include
        When normalised
        Then the include is the built-in default.

    Boundaries:
        - Focus: Contract 3 step 6 then step 8
        - Fixtures/params: tmp_path
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The candidate == spelling branch
    """
    root = _tree(tmp_path)

    assert normalize_invoker_selectors(root, [str(root)], None).include == ("*.md", "**/*.md")


def test_absolute_glob_refused():
    """
    [Unit] discovery: verifies an absolute glob is refused even inside the root.

    Scenario:
        Given /repo/docs/x*
        When normalised
        Then "globs must be relative" is raised.

    Boundaries:
        - Focus: threat model M2
        - Fixtures/params: none
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The is_glob test in the absolute branch
    """
    assert "globs must be relative" in _refused("/repo/docs/x*")


def test_absolute_longest_root_spelling_wins(tmp_path: Path):
    """
    [Unit] discovery: verifies the longest matching root spelling is the one removed.

    Scenario:
        Given the canonical root and a longer spelling <root>/alias of the same root
        When <root>/alias/docs/user is normalised
        Then the result is docs/user, not alias/docs/user.

    Boundaries:
        - Focus: threat model M9
        - Fixtures/params: tmp_path
        - Scope: normalize_invoker_selectors (spellings passed in directly)

    On failure, first check:
        - The spelling sort order in normalize_invoker_selectors
    """
    root = _tree(tmp_path)

    selection = normalize_invoker_selectors(root, [f"{root}/alias/docs/user"], None, root_spellings=(root / "alias",))

    assert selection.include == ("docs/user",)


def test_tilde_and_env_vars_not_expanded():
    """
    [Unit] discovery: verifies ~ and $HOME are plain characters, never expanded.

    Scenario:
        Given the globs ~/*.md and $HOME/*.md
        When normalised
        Then they are returned verbatim.

    Boundaries:
        - Focus: threat model M4
        - Fixtures/params: none
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - Any expanduser/expandvars added to the pipeline
    """
    assert _include("~/*.md", "$HOME/*.md").include == ("~/*.md", "$HOME/*.md")


@pytest.mark.parametrize("value", ["C:/x", "C:x", "c:\\x", "a:b.md"])
def test_windows_drive_forms_refused_on_posix(value: str):
    """
    [Unit] discovery: verifies drive and drive-relative forms are refused when backslash is not a separator.

    Scenario:
        Given a value with a drive prefix
        When normalised with backslash_is_separator=False
        Then the drive/UNC/device reason is raised.

    Boundaries:
        - Focus: threat model M10
        - Fixtures/params: value
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - ntpath.splitdrive use in _check_windows_forms

    :param value: The refused value.
    """
    assert "drive, UNC and device paths are not allowed" in _refused(value)


@pytest.mark.parametrize("backslash", [False, True])
@pytest.mark.parametrize("value", ["\\\\srv\\share\\x", "//srv/share/x", "\\\\?\\C:\\x", "//?/C:/x", "\\\\.\\pipe\\x"])
def test_unc_and_device_forms_refused(value: str, backslash: bool):
    """
    [Unit] discovery: verifies UNC, verbatim and device forms are refused on every platform.

    Scenario:
        Given a UNC or device-namespace value
        When normalised with either backslash rule
        Then the drive/UNC/device reason is raised.

    Boundaries:
        - Focus: threat model M10
        - Fixtures/params: value, backslash
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The leading double separator test

    :param value: The refused value.
    :param backslash: Whether backslash is a separator.
    """
    assert "drive, UNC and device paths are not allowed" in _refused(value, backslash=backslash)


def test_leading_double_slash_refused_on_posix():
    """
    [Unit] discovery: verifies a leading // is refused, not kept by posixpath.normpath.

    Scenario:
        Given //repo/docs
        When normalised on POSIX rules
        Then it is refused.

    Boundaries:
        - Focus: threat model M10
        - Fixtures/params: none
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The leading double separator test
    """
    assert "drive, UNC and device paths are not allowed" in _refused("//repo/docs")


def test_backslash_refused_on_posix():
    """
    [Unit] discovery: verifies a backslash is refused when it is not a separator.

    Scenario:
        Given docs\\user
        When normalised with backslash_is_separator=False
        Then the backslash reason is raised.

    Boundaries:
        - Focus: Contract 3 step 4
        - Fixtures/params: none
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The backslash branch of _lexical_normalize
    """
    assert "a backslash is not a path separator" in _refused("docs\\user")


def test_backslash_is_separator_when_injected():
    """
    [Unit] discovery: verifies backslash becomes / when backslash_is_separator=True.

    Scenario:
        Given docs\\*.md
        When normalised with backslash_is_separator=True
        Then the include is docs/*.md.

    Boundaries:
        - Focus: Contract 3 step 4 (Windows rule tested on POSIX)
        - Fixtures/params: none
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The backslash replacement
    """
    assert _include("docs\\*.md", backslash=True).include == ("docs/*.md",)


@pytest.mark.parametrize("value", ["\\docs", "/docs"])
def test_rooted_backslash_refused_when_backslash_is_separator(value: str):
    """
    [Unit] discovery: verifies a rooted value without a drive is refused on the backslash platform.

    Scenario:
        Given \\docs or /docs
        When normalised with backslash_is_separator=True
        Then the rooted-path reason is raised.

    Boundaries:
        - Focus: threat model M11
        - Fixtures/params: value
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The rooted test in _check_windows_forms

    :param value: The refused value.
    """
    assert "a rooted path needs a drive letter" in _refused(value, backslash=True)


@pytest.mark.parametrize("value", ["docs\\a.md:stream", "docs\\a.md.", "docs\\a.md ", "C:\\repo\\a:b"])
def test_windows_ads_and_trailing_dot_refused_when_backslash_is_separator(value: str):
    """
    [Unit] discovery: verifies alternate data streams and trailing dots or spaces are refused.

    Scenario:
        Given an ADS, trailing-dot or trailing-space value
        When normalised with backslash_is_separator=True
        Then it is refused.

    Boundaries:
        - Focus: threat model M11
        - Fixtures/params: value
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The component loop in _check_windows_forms

    :param value: The refused value.
    """
    assert "alternate data streams and names ending in a dot or space" in _refused(value, backslash=True)


def test_drive_absolute_outside_root_refused_when_backslash_is_separator():
    """
    [Unit] discovery: verifies an X:/ absolute value goes to the lexical root comparison.

    Scenario:
        Given C:\\other\\a.md on a POSIX root with backslash_is_separator=True
        When normalised
        Then it is outside the scan root (not a drive refusal), with no filesystem call.

    Boundaries:
        - Focus: Contract 3 step 3 exception for X:\\ under the backslash rule
        - Fixtures/params: none
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - drive_absolute in _check_windows_forms
    """
    assert "is outside the scan root" in _refused("C:\\other\\a.md", backslash=True)


@pytest.mark.parametrize("character", _LOOKALIKE_SEPARATORS)
def test_lookalike_separators_are_name_characters(character: str):
    """
    [Unit] discovery: verifies look-alike separators pass through unchanged as name characters.

    Scenario:
        Given a glob holding a look-alike separator
        When normalised
        Then it is kept verbatim (no refusal, no mapping to /).

    Boundaries:
        - Focus: threat model M12, ruling U1
        - Fixtures/params: character
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - Any Unicode normalisation in the pipeline

    :param character: The look-alike separator.
    """
    value = f"docs{character}*.md"

    assert _include(value).include == (value,)


def test_no_unicode_normalisation_applied():
    """
    [Unit] discovery: verifies NFD text and fullwidth characters are not normalised or case folded.

    Scenario:
        Given an NFD glob and a mixed-case fullwidth glob
        When normalised
        Then both are returned code point for code point.

    Boundaries:
        - Focus: threat model M12 (A2)
        - Fixtures/params: none
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - unicodedata.normalize, casefold or lower in the pipeline
    """
    values = ("Cafe\u0301/*.md", "ＤＯＣＳ／*.md")

    assert _include(*values).include == values


@pytest.mark.parametrize(
    "character", ["\x00", "\x1b", "\r", "\n", "\x7f", "\x85", "\u202e", "\u200b", "\u2028", "\udc80"]
)
def test_nul_and_controls_refused(character: str):
    """
    [Unit] discovery: verifies NUL, controls, bidi, zero-width, separators and lone surrogates are refused.

    Scenario:
        Given a glob holding one unsafe code point
        When normalised
        Then the character reason is raised and the echo is neutralised.

    Boundaries:
        - Focus: threat model M13
        - Fixtures/params: character
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The neutralize comparison in _lexical_normalize

    :param character: The unsafe code point.
    """
    message = _refused(f"docs/{character}*.md")

    assert "contains a control, format or unsupported character sequence" in message
    assert character not in message


def test_github_command_marker_refused_with_clear_message():
    """
    [Unit] discovery: verifies ##[ is refused with the unsupported-sequence wording.

    Scenario:
        Given the literal ##[x.md
        When normalised
        Then the reason says "control, format or unsupported character sequence" and ##[ is not echoed raw.

    Boundaries:
        - Focus: threat model M14
        - Fixtures/params: none
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The neutralize comparison
    """
    message = _refused("##[x.md")

    assert "contains a control, format or unsupported character sequence" in message
    assert "##[" not in message


class _ExplodingSequence(Sequence):
    """A long sequence whose items must never be read."""

    def __len__(self) -> int:
        """Return a length above the 256-value limit.

        :returns: 257.
        """
        return 257

    def __getitem__(self, index: int) -> str:
        """Fail the test when an item is read.

        :param index: The requested index.
        :returns: Never returns.
        :raises AssertionError: Always.
        """
        raise AssertionError(f"item {index} was read before the length check")


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("docs", "include must be a sequence of patterns, not a single string"),
        (b"docs", "include must be a sequence of patterns, not a single string"),
        ((v for v in ["docs"]), "include must be a sequence of patterns"),
        ({"docs"}, "include must be a sequence of patterns"),
        ([], "include needs at least one value"),
        (["x"] * 257, "include accepts at most 256 values"),
        ([1], "include values must be nonempty strings"),
        ([""], "include values must be nonempty strings"),
        (["x" * 1025], "include value is longer than 1024 characters"),
    ],
)
def test_shape_bounds(value: object, message: str):
    """
    [Unit] discovery: verifies every shape row of Contract 1 and that shape errors echo no value.

    Scenario:
        Given a malformed include container or item
        When normalised
        Then the fixed shape message is raised, ending with the relative-to-root hint.

    Boundaries:
        - Focus: threat model M19, A7 (no value echoed)
        - Fixtures/params: value, message
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - _check_shape order and texts

    :param value: The malformed include.
    :param message: The expected message prefix.
    """
    with pytest.raises(ConfigError) as caught:
        normalize_invoker_selectors(_ROOT, value, None)

    assert str(caught.value) == f"{message}; {_HINT}"


def test_oversized_list_refused_before_item_processing():
    """
    [Unit] discovery: verifies the 256-value bound is checked with len() before any item is read.

    Scenario:
        Given a sequence of length 257 whose items raise when read
        When normalised
        Then the count error is raised and no item was read.

    Boundaries:
        - Focus: threat model M19 (A8 order)
        - Fixtures/params: none
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The len() check position in _check_shape
    """
    with pytest.raises(ConfigError, match="accepts at most 256 values"):
        normalize_invoker_selectors(_ROOT, None, _ExplodingSequence())


def test_error_message_bounded_and_neutralised():
    """
    [Unit] discovery: verifies an echoed value is neutralised and capped at 200 characters.

    Scenario:
        Given a 1,000-character value holding an escape character
        When normalised
        Then the message echoes at most 200 characters plus the marker and no raw control.

    Boundaries:
        - Focus: threat model M21
        - Fixtures/params: none
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - _refuse uses safe(value, 200)
    """
    message = _refused("\x1b" + "a" * 999)

    assert "\x1b" not in message
    assert "a" * 201 not in message
    assert len(message) < 400


def test_error_message_says_relative_to_scan_root():
    """
    [Unit] discovery: verifies a value error has the key, the value, the reason and the hint.

    Scenario:
        Given the exclude value ../x
        When normalised
        Then the message is "exclude value ../x: <reason>; values are relative to the scan root".

    Boundaries:
        - Focus: threat model M21 (A7 message form)
        - Fixtures/params: none
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - _refuse formatting
    """
    assert _refused("../x", key="exclude") == f"exclude value ../x: parent steps (..) are not allowed; {_HINT}"


def test_lexical_errors_win_over_filesystem_checks():
    """
    [Unit] discovery: verifies every value is checked lexically before any literal is checked on disk.

    Scenario:
        Given a missing literal include followed by an exclude with a control character
        When normalised against a root that does not exist
        Then the character error is raised, not the include's not-found error.

    Boundaries:
        - Focus: threat model M13 ordering across values
        - Fixtures/params: none
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The two-phase loop in normalize_invoker_selectors
    """
    with pytest.raises(ConfigError, match="control, format"):
        normalize_invoker_selectors(_ROOT, ["docs/missing"], ["a\x1b"])


def _table_tree(tmp_path: Path) -> Path:
    """Build ``root/docs/user/a.md`` plus ``root/docs/user.md`` and return the canonical root.

    :param tmp_path: The pytest scratch directory.
    :returns: The resolved root.
    """
    root = _tree(tmp_path)
    (root / "docs" / "user.md").write_text("# U\n", encoding="utf-8")
    return root


@pytest.mark.parametrize(
    ("value", "key", "backslash", "expected"),
    [
        ("docs/user", "include", False, ("docs/user",)),
        ("docs/user/", "include", False, ("docs/user",)),
        ("./docs//user", "include", False, ("docs/user",)),
        ("{root}/docs/user", "include", False, ("docs/user",)),
        ("docs\\user", "include", True, ("docs/user",)),
        ("docs\\user", "include", False, "a backslash is not a path separator"),
        ("**/*.draft.md", "include", False, ("**/*.draft.md",)),
        (".", "include", False, ("*.md", "**/*.md")),
        (".", "exclude", False, "excluding the scan root is not allowed"),
        ("../other", "include", False, "parent steps (..) are not allowed"),
        ("docs/../x", "include", False, "parent steps (..) are not allowed"),
        ("/etc", "include", False, "is outside the scan root"),
        ("{root}/docs/x*", "include", False, "globs must be relative"),
        ("", "include", False, "include values must be nonempty strings"),
        ("docs/\x07user", "include", False, "contains a control, format or unsupported character sequence"),
    ],
)
def test_normalisation_table_row(
    tmp_path: Path, value: str, key: str, backslash: bool, expected: Union[tuple[str, ...], str]
):
    """
    [Unit] discovery: verifies every row of the story README normalisation table.

    Scenario:
        Given a real root holding docs/user (the table's /repo) and one table input
        When the value is normalised as the row's key, with the row's backslash rule
        Then the result is the row's normalised pattern(s), or a ConfigError naming the row's reason.

    Boundaries:
        - Focus: Story 02.0 "Selector grammar" table, one parametrised case per row
        - Fixtures/params: tmp_path; value ({root} is the canonical root), key, backslash, expected
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The step of Contract 3 named by the row's reason

    :param value: The table input; ``{root}`` is replaced by the canonical root.
    :param key: ``include`` or ``exclude``.
    :param backslash: Whether ``\\`` is a separator (the Windows rows).
    :param expected: The normalised patterns, or a substring of the refusal.
    """
    root = _table_tree(tmp_path)
    selectors: dict[str, Optional[list[str]]] = {"include": None, "exclude": None}
    selectors[key] = [value.replace("{root}", os.fspath(root))]

    if isinstance(expected, str):
        with pytest.raises(ConfigError) as caught:
            normalize_invoker_selectors(root, **selectors, backslash_is_separator=backslash)
        assert expected in str(caught.value)
        assert str(caught.value).endswith(_HINT)
        return
    selection = normalize_invoker_selectors(root, **selectors, backslash_is_separator=backslash)
    assert getattr(selection, key) == expected


@pytest.mark.parametrize("key", ["include", "exclude"])
@pytest.mark.parametrize("value", ["docs", b"docs", bytearray(b"docs")])
def test_bare_string_or_bytes_keyword_refused_for_both_keys(key: str, value: object):
    """
    [Unit] discovery: verifies a bare str or bytes keyword value is refused, never split into characters.

    Scenario:
        Given "docs", b"docs" or bytearray(b"docs") as the include or exclude keyword
        When normalised, and when only shape-checked (the single-file path)
        Then both raise the "not a single string" ConfigError naming the key, echoing no value.

    Boundaries:
        - Focus: ADR 0006 Contract 1 bare str/bytes row, owner point O5
        - Fixtures/params: key, value
        - Scope: normalize_invoker_selectors and check_invoker_selector_shape

    On failure, first check:
        - The isinstance(str, bytes, bytearray) test in _check_shape

    :param key: ``include`` or ``exclude``.
    :param value: The bare scalar.
    """
    expected = f"{key} must be a sequence of patterns, not a single string; {_HINT}"
    selectors: dict[str, object] = {"include": None, "exclude": None, key: value}

    with pytest.raises(ConfigError) as normalised:
        normalize_invoker_selectors(_ROOT, **selectors)  # type: ignore[arg-type]
    with pytest.raises(ConfigError) as shaped:
        check_invoker_selector_shape(**selectors)  # type: ignore[arg-type]

    assert str(normalised.value) == expected
    assert str(shaped.value) == expected


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ((), "exclude needs at least one value"),
        (iter(["docs"]), "exclude must be a sequence of patterns"),
        ({"docs": 1}, "exclude must be a sequence of patterns"),
        (["x"] * 257, "exclude accepts at most 256 values"),
        ([Path("docs")], "exclude values must be nonempty strings"),
        ([None], "exclude values must be nonempty strings"),
        (["ok", ""], "exclude values must be nonempty strings"),
        (["ok", "x" * 1025], "exclude value is longer than 1024 characters"),
    ],
)
def test_shape_rows_for_exclude_key(value: object, message: str):
    """
    [Unit] discovery: verifies the Contract 1 shape rows name the exclude key and echo no value.

    Scenario:
        Given a malformed exclude container or item (tuple, iterator, mapping, 257 items,
            a Path item, a None item, a later empty item, a later 1,025-character item)
        When normalised
        Then the fixed exclude shape message is raised, exactly.

    Boundaries:
        - Focus: ADR 0006 Contract 1 table rows for the exclude key; threat model M19, A7
        - Fixtures/params: value, message
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - _check_shape uses the key name in every message

    :param value: The malformed exclude.
    :param message: The expected message prefix.
    """
    with pytest.raises(ConfigError) as caught:
        normalize_invoker_selectors(_ROOT, None, value)  # type: ignore[arg-type]

    assert str(caught.value) == f"{message}; {_HINT}"


def test_shape_upper_bounds_accepted():
    """
    [Unit] discovery: verifies exactly 256 values and a 1,024-character value are accepted.

    Scenario:
        Given 256 distinct glob includes and one 1,024-character glob exclude
        When normalised
        Then every include is kept in order and the long exclude is kept verbatim.

    Boundaries:
        - Focus: ADR 0006 Contract 1 bounds (off-by-one at 256 and 1,024)
        - Fixtures/params: none
        - Scope: normalize_invoker_selectors, globs only (no filesystem)

    On failure, first check:
        - MAX_SELECTOR_VALUES / MAX_SELECTOR_LENGTH comparisons (> versus >=)
    """
    includes = [f"g{index:03d}/*.md" for index in range(256)]
    long_exclude = "*" + "a" * 1023

    selection = normalize_invoker_selectors(_ROOT, includes, [long_exclude])

    assert selection.include == tuple(includes)
    assert selection.exclude == (long_exclude,)
    assert len(long_exclude) == 1024


def test_shape_checked_for_both_keys_before_any_value_check():
    """
    [Unit] discovery: verifies a shape error in exclude wins over a lexical error in include.

    Scenario:
        Given an include with a parent step and an empty exclude list
        When normalised
        Then the exclude shape error is raised (shape of both keys runs first).

    Boundaries:
        - Focus: ADR 0006 Contract 3 step 1 order across keys
        - Fixtures/params: none
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The given dict comprehension runs _check_shape for both keys before _lexical_normalize
    """
    with pytest.raises(ConfigError) as caught:
        normalize_invoker_selectors(_ROOT, ["../x"], [])

    assert str(caught.value) == f"exclude needs at least one value; {_HINT}"


def test_single_component_literal_exclude_naming_nothing_not_unmatched(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    """
    [Unit] discovery: verifies a one-name literal exclude that names nothing is not listed and logs nothing.

    Scenario:
        Given a root without build or docs/build
        When the excludes build and docs/build are normalised
        Then both are kept, only docs/build is in unmatched_exclude, and no record is logged.

    Boundaries:
        - Focus: ADR 0006 open point O3; Contract 3 step 10 (normaliser leaves logging to the engine)
        - Fixtures/params: tmp_path, caplog at DEBUG
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The '"/" in pattern' guard on unmatched in normalize_invoker_selectors
    """
    root = _tree(tmp_path)
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    selection = normalize_invoker_selectors(root, None, ["build", "docs/build"])

    assert selection == InvokerSelection(None, ("build", "docs/build"), ("docs/build",))
    assert [record for record in caplog.records if record.name.startswith("docsentinel")] == []


def test_literal_duplicates_kept_once_after_normalisation(tmp_path: Path):
    """
    [Unit] discovery: verifies spellings of one literal collapse to one pattern in first-occurrence order.

    Scenario:
        Given docs/user/a.md, ./docs/user/, <root>/docs/user, docs/user//, docs/user/a.md
        When normalised as includes
        Then the include is (docs/user/a.md, docs/user).

    Boundaries:
        - Focus: ADR 0006 Contract 3 step 11; story edge case "duplicate values"
        - Fixtures/params: tmp_path
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - _unique runs after _lexical_normalize, not before
    """
    root = _tree(tmp_path)
    values = ["docs/user/a.md", "./docs/user/", f"{root}/docs/user", "docs/user//", "docs/user/a.md"]

    assert normalize_invoker_selectors(root, values, None).include == ("docs/user/a.md", "docs/user")


def test_dot_include_merges_with_default_patterns_once():
    """
    [Unit] discovery: verifies include . expands to the default patterns, deduplicated with explicit ones.

    Scenario:
        Given the includes **/*.md, . and *.md
        When normalised
        Then the include is (**/*.md, *.md) in first-occurrence order.

    Boundaries:
        - Focus: ADR 0006 Contract 3 steps 8 and 11
        - Fixtures/params: none
        - Scope: normalize_invoker_selectors, globs only

    On failure, first check:
        - _lexical_normalize returns Config().include for "."
    """
    assert _include("**/*.md", ".", "*.md").include == ("**/*.md", "*.md")


def test_backslash_parent_step_refused_when_backslash_is_separator():
    """
    [Unit] discovery: verifies docs\\..\\x is refused as a parent step on the backslash platform.

    Scenario:
        Given docs\\..\\x and C:\\repo\\..\\x
        When normalised with backslash_is_separator=True
        Then both raise the parent-step reason (step 5 runs after the backslash rule).

    Boundaries:
        - Focus: ADR 0006 Contract 3 steps 4 and 5; threat model M1
        - Fixtures/params: none
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The order of the backslash replacement and the .. check
    """
    assert "parent steps (..) are not allowed" in _refused("docs\\..\\x", backslash=True)
    assert "parent steps (..) are not allowed" in _refused("C:\\repo\\..\\x", backslash=True)


def test_drive_absolute_value_under_spelling_made_relative_when_backslash_is_separator():
    """
    [Unit] discovery: verifies an X:\\ absolute literal under a drive spelling is made relative, lexically.

    Scenario:
        Given the spelling C:/repo and the value C:\\repo\\docs\\a.md
        When the lexical steps run with backslash_is_separator=True
        Then the pattern is docs/a.md (the step-3 exception; no filesystem call is possible here).

    Boundaries:
        - Focus: ADR 0006 Contract 3 step 3 exception and step 6
        - Fixtures/params: none
        - Scope: _lexical_normalize (private; the public path needs a real Windows root)

    On failure, first check:
        - drive_absolute in _check_windows_forms and the absolute branch of _lexical_normalize
    """
    assert _lexical_normalize("include", "C:\\repo\\docs\\a.md", ("C:/repo",), True) == ("docs/a.md",)


def test_existing_literal_file_and_directory_accepted(tmp_path: Path):
    """
    [Unit] discovery: verifies an existing in-root file and directory pass the existence and type check.

    Scenario:
        Given root/docs/user/a.md
        When the include docs/user/a.md and the exclude docs/user are normalised
        Then both are kept and nothing is unmatched.

    Boundaries:
        - Focus: ADR 0006 Contract 3 step 10 (S_ISREG or S_ISDIR accepted)
        - Fixtures/params: tmp_path
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The S_ISREG/S_ISDIR test in _check_literal
    """
    root = _tree(tmp_path)

    selection = normalize_invoker_selectors(root, ["docs/user/a.md"], ["docs/user"])

    assert selection == InvokerSelection(("docs/user/a.md",), ("docs/user",), ())


def test_not_a_directory_component_counts_as_missing(tmp_path: Path):
    """
    [Unit] discovery: verifies a path through a regular file is "missing", not an OSError refusal.

    Scenario:
        Given root/docs/user/a.md is a file
        When docs/user/a.md/x is normalised as an include, and as an exclude
        Then the include is "not found under the scan root" and the exclude is listed unmatched.

    Boundaries:
        - Focus: ADR 0006 Contract 3 OSError paragraph (NotADirectoryError counts as missing)
        - Fixtures/params: tmp_path
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The (FileNotFoundError, NotADirectoryError) handler in _check_literal
    """
    root = _tree(tmp_path)

    with pytest.raises(ConfigError) as caught:
        normalize_invoker_selectors(root, ["docs/user/a.md/x"], None)

    assert str(caught.value) == f"include value docs/user/a.md/x: not found under the scan root; {_HINT}"
    assert normalize_invoker_selectors(root, None, ["docs/user/a.md/x"]).unmatched_exclude == ("docs/user/a.md/x",)


def test_outside_message_form_has_no_colon(tmp_path: Path):
    """
    [Unit] discovery: verifies the outside-the-root message is the one fixed, existence-independent text.

    Scenario:
        Given an existing outside directory and a missing outside path
        When each is normalised as an exclude
        Then both messages are "exclude value <v> is outside the scan root; values are relative to the scan root".

    Boundaries:
        - Focus: ADR 0006 Contract 3 step 6 message; threat model M6
        - Fixtures/params: tmp_path
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The joiner in _refuse for _OUTSIDE_REASON
    """
    root = _tree(tmp_path)
    existing = os.fspath(tmp_path.resolve())
    missing = os.fspath(tmp_path.resolve() / "no-such-dir" / "x.md")

    for value in (existing, missing):
        with pytest.raises(ConfigError) as caught:
            normalize_invoker_selectors(root, None, [value])
        assert str(caught.value) == f"exclude value {value} is outside the scan root; {_HINT}"
