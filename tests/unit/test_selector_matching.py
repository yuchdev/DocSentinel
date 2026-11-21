"""Unit tests for the ADR 0006 Contract 2 matcher in :mod:`docsentinel.discovery`.

Covers :func:`is_glob`, :func:`selector_matches` and :func:`prunes_directory` with
tiny inline paths; no filesystem access.
"""

from fnmatch import fnmatchcase

import pytest

from docsentinel.discovery import is_glob, prunes_directory, selector_matches

_LOOKALIKE_SEPARATORS = ("∕", "／", "⁄", "⧸", "＼", "﹨")


@pytest.mark.parametrize(
    ("pattern", "expected"),
    [("*.md", True), ("docs/v?", True), ("notes[[]1].md", True), ("docs/user", False), ("a.md", False)],
)
def test_is_glob_detects_star_question_and_bracket(pattern: str, expected: bool):
    """
    [Unit] discovery: verifies is_glob classifies a pattern by *, ? and [ only.

    Scenario:
        Given glob and literal patterns
        When is_glob classifies them
        Then only patterns holding *, ? or [ are globs.

    Boundaries:
        - Focus: the glob/literal split of Contract 2
        - Fixtures/params: pattern, expected
        - Scope: is_glob only

    On failure, first check:
        - GLOB_CHARACTERS in discovery.py

    :param pattern: The selector pattern.
    :param expected: Whether it is a glob.
    """
    assert is_glob(pattern) is expected


@pytest.mark.parametrize(
    ("relative", "expected"),
    [
        ("docs/user", True),
        ("docs/user/a.md", True),
        ("docs/user/deep/b.md", True),
        ("docs/user/image.png", False),
        ("docs/user/A.MD", False),
        ("docs/users/a.md", False),
        ("docs/a.md", False),
    ],
)
def test_literal_include_admits_markdown_below_directory(relative: str, expected: bool):
    """
    [Unit] discovery: verifies a literal include admits itself and only .md files below it.

    Scenario:
        Given the literal include docs/user
        When selector_matches tests file paths
        Then the path itself and .md files below it match, other suffixes and siblings do not.

    Boundaries:
        - Focus: Contract 2 literal include row, Markdown-only directory include (rule 3)
        - Fixtures/params: relative, expected
        - Scope: selector_matches only

    On failure, first check:
        - The _under prefix test (separator-aware, docs/users is not under docs/user)

    :param relative: The file's relative path.
    :param expected: Whether the include admits it.
    """
    assert selector_matches(relative, "docs/user", include=True) is expected


def test_literal_include_equal_to_file_admits_any_suffix():
    """
    [Unit] discovery: verifies a literal include equal to a file path admits it whatever its suffix.

    Scenario:
        Given the literal include notes.txt
        When selector_matches tests notes.txt
        Then it matches, as a config include of that file does today.

    Boundaries:
        - Focus: Contract 2 literal include, R == L (unchanged)
        - Fixtures/params: none
        - Scope: selector_matches only

    On failure, first check:
        - The equality branch of selector_matches
    """
    assert selector_matches("notes.txt", "notes.txt", include=True)


@pytest.mark.parametrize(
    ("relative", "expected"),
    [
        ("docs/archive/a.png", True),
        ("docs/archive/x/b.md", True),
        ("docs/archive", True),
        ("other/docs/archive/a.md", False),
        ("docs/archived.md", False),
    ],
)
def test_literal_exclude_removes_everything_below(relative: str, expected: bool):
    """
    [Unit] discovery: verifies a literal exclude removes the path and everything below it.

    Scenario:
        Given the literal exclude docs/archive
        When selector_matches tests file paths for exclusion
        Then every path below it is removed, whatever the suffix, and a name prefix is not.

    Boundaries:
        - Focus: Contract 2 literal exclude row (new relative-path rule)
        - Fixtures/params: relative, expected
        - Scope: selector_matches only

    On failure, first check:
        - _exclude_reason in discovery.py

    :param relative: The file's relative path.
    :param expected: Whether the exclude removes it.
    """
    assert selector_matches(relative, "docs/archive", include=False) is expected


def test_single_component_literal_exclude_matches_directory_name_anywhere():
    """
    [Unit] discovery: verifies a one-name literal exclude still removes files under that name anywhere.

    Scenario:
        Given the literal exclude build
        When selector_matches tests a file below a nested build directory
        Then it is removed by the unchanged directory-name rule.

    Boundaries:
        - Focus: Contract 2 literal exclude, directory-name rule (unchanged)
        - Fixtures/params: none
        - Scope: selector_matches only

    On failure, first check:
        - The parent-name branch of _exclude_reason
    """
    assert selector_matches("pkg/build/a.md", "build", include=False)


@pytest.mark.parametrize(
    ("relative", "pattern", "include", "expected"),
    [
        ("docs/a.md", "**/*.md", True, True),
        ("a.md", "**/*.md", True, False),
        ("docs/v1/a.md", "docs/v?", False, False),
        ("docs/archive/a.md", "**/archive", False, False),
        ("docs/archive/a.md", "docs/archive/*", False, True),
        ("x/node_modules/a.md", "node_*", False, True),
    ],
)
def test_glob_rows_unchanged(relative: str, pattern: str, include: bool, expected: bool):
    """
    [Unit] discovery: verifies glob patterns keep today's fnmatchcase behaviour exactly.

    Scenario:
        Given glob include and exclude patterns
        When selector_matches applies them
        Then the result equals today's fnmatchcase path and directory-name tests (owner ruling O1).

    Boundaries:
        - Focus: Contract 2 glob row byte-identical
        - Fixtures/params: relative, pattern, include, expected
        - Scope: selector_matches only

    On failure, first check:
        - Whether a glob gained the literal _under rule

    :param relative: The file's relative path.
    :param pattern: The glob.
    :param include: Which column is applied.
    :param expected: The expected result.
    """
    assert selector_matches(relative, pattern, include=include) is expected


@pytest.mark.parametrize(
    ("relative", "pattern", "expected"),
    [
        ("docs/archive", "docs/archive", True),
        ("x/build", "build", True),
        ("docs/archive/old", "docs/archive", False),
        ("docs/v1", "docs/v?", False),
        ("docs/archive", "**/archive", False),
        ("x/node_modules", "node_*", True),
    ],
)
def test_prunes_directory_literal_by_path_glob_by_name_only(relative: str, pattern: str, expected: bool):
    """
    [Unit] discovery: verifies only a literal prunes by relative path; a glob prunes by name only.

    Scenario:
        Given literal and glob exclude patterns
        When prunes_directory tests directory paths
        Then a literal prunes by name or path, a glob by its name only.

    Boundaries:
        - Focus: Contract 2 prune column, owner ruling O1
        - Fixtures/params: relative, pattern, expected
        - Scope: prunes_directory only

    On failure, first check:
        - The is_glob branch of prunes_directory

    :param relative: The directory's relative path.
    :param pattern: The exclude pattern.
    :param expected: Whether the walk prunes it.
    """
    assert prunes_directory(relative, pattern) is expected


@pytest.mark.parametrize("character", _LOOKALIKE_SEPARATORS)
def test_lookalike_separator_glob_does_not_match_slash(character: str):
    """
    [Unit] discovery: verifies a look-alike separator in a pattern never matches a real slash.

    Scenario:
        Given a glob and a literal that use a look-alike separator between docs and the name
        When selector_matches tests docs/x.md
        Then neither matches (ruling U1: look-alikes are name characters).

    Boundaries:
        - Focus: threat model M12
        - Fixtures/params: character (six look-alikes)
        - Scope: selector_matches only

    On failure, first check:
        - Any Unicode normalisation added to the matcher

    :param character: The look-alike separator.
    """
    assert not selector_matches("docs/x.md", f"docs{character}*.md", include=True)
    assert not selector_matches("docs/x.md", f"docs{character}x.md", include=True)


#: Paths of the recorded glob table: root files, nested files, dot names, names holding glob characters.
_RECORDED_PATHS = (
    "a.md",
    "README.md",
    "docs/a.md",
    "docs/v1/a.md",
    "docs/archive/a.md",
    "docs/archive/x/b.txt",
    "x/node_modules/pkg/c.md",
    ".github/d.md",
    "notes[1].md",
    "docs/user/A.MD",
)

#: Glob patterns of the recorded table, including every glob shape used by packaged configs and tests.
_RECORDED_GLOBS = (
    "*.md",
    "**/*.md",
    "docs/*",
    "docs/v?",
    "**/archive",
    "docs/archive/*",
    "node_*",
    ".*",
    "*",
    "?*",
    "notes[[]1].md",
    "notes[1].md",
    "[!d]*.md",
    "*.MD",
)


def _legacy_exclude(relative: str, pattern: str) -> bool:
    """Return the pre-ADR-0006 exclude result: path match or a directory-name match.

    :param relative: The file's relative POSIX path.
    :param pattern: The glob.
    :returns: Whether the old discovery removed the file.
    """
    return fnmatchcase(relative, pattern) or any(fnmatchcase(part, pattern) for part in relative.split("/")[:-1])


@pytest.mark.parametrize("pattern", _RECORDED_GLOBS)
def test_glob_matching_equals_recorded_legacy_behaviour(pattern: str):
    """
    [Unit] discovery: verifies every glob gives today's include, exclude and prune result on a recorded table.

    Scenario:
        Given one recorded glob and the recorded path set
        When selector_matches (include and exclude) and prunes_directory are applied
        Then each result equals the pre-ADR-0006 fnmatchcase formula, path for path.

    Boundaries:
        - Focus: Task 05 step 2; ADR 0006 Contract 2 glob row byte-identical (owner ruling O1)
        - Fixtures/params: pattern (14 recorded globs) x 10 recorded paths
        - Scope: selector_matches and prunes_directory

    On failure, first check:
        - Whether a glob gained a literal-only rule (_under, relative-path prune)

    :param pattern: One recorded glob.
    """
    for relative in _RECORDED_PATHS:
        assert selector_matches(relative, pattern, include=True) is fnmatchcase(relative, pattern), relative
        assert selector_matches(relative, pattern, include=False) is _legacy_exclude(relative, pattern), relative
        directory = relative.rsplit("/", 1)[0] if "/" in relative else ""
        if directory:
            expected = fnmatchcase(directory.rsplit("/", 1)[-1], pattern)
            assert prunes_directory(directory, pattern) is expected, directory


@pytest.mark.parametrize(
    ("relative", "pattern", "include", "expected"),
    [
        ("a.md", "a.md", True, True),
        ("docs/a.md", "a.md", True, False),
        ("docs/a.md", "docs/a.md", False, True),
        ("pkg/a.md", "a.md", False, False),
        ("pkg/build/x/a.png", "build", False, True),
        ("pkg/builds/a.md", "build", False, False),
        ("docs/user", "docs/user", False, True),
        ("docs/user/a.md", "docs/user/a.md/x", True, False),
    ],
)
def test_literal_rows_contract_2_table(relative: str, pattern: str, include: bool, expected: bool):
    """
    [Unit] discovery: verifies the literal row of the Contract 2 table cell by cell.

    Scenario:
        Given literal file, directory and name patterns
        When selector_matches applies the include or exclude column
        Then R == L, R under L (exclude: any suffix), and a directory name equal to L behave as tabled;
            a file-name literal never removes a same-named file in a subdirectory.

    Boundaries:
        - Focus: ADR 0006 Contract 2 literal row
        - Fixtures/params: relative, pattern, include, expected
        - Scope: selector_matches only

    On failure, first check:
        - _exclude_reason and the include branch of selector_matches

    :param relative: The file's relative path.
    :param pattern: The literal.
    :param include: Which column is applied.
    :param expected: The expected result.
    """
    assert selector_matches(relative, pattern, include=include) is expected


@pytest.mark.parametrize(
    ("relative", "pattern", "expected"),
    [
        ("notes[1].md", "notes[1].md", False),
        ("notes1.md", "notes[1].md", True),
        ("notes[1].md", "notes[[]1].md", True),
        ("what?.md", "what?.md", True),
        ("whatX.md", "what?.md", True),
    ],
)
def test_no_escape_syntax_for_glob_characters(relative: str, pattern: str, expected: bool):
    """
    [Unit] discovery: verifies a name holding *, ? or [ is selected only by a glob that matches it.

    Scenario:
        Given file names holding [ or ? and patterns spelled with and without a bracket escape
        When selector_matches applies the include column
        Then the value is always a glob: notes[1].md does not select itself, notes[[]1].md does.

    Boundaries:
        - Focus: ADR 0006 Contract 2 rule 5 (no escape syntax)
        - Fixtures/params: relative, pattern, expected
        - Scope: selector_matches only

    On failure, first check:
        - is_glob classification and the fnmatchcase branch

    :param relative: The file's relative path.
    :param pattern: The glob.
    :param expected: Whether it matches.
    """
    assert selector_matches(relative, pattern, include=True) is expected


@pytest.mark.parametrize(
    ("relative", "pattern", "include"),
    [
        ("Docs/a.md", "docs", True),
        ("docs/a.md", "Docs", True),
        ("a.md", "*.MD", True),
        ("Docs/a.md", "docs", False),
        ("x/BUILD/a.md", "build", False),
    ],
)
def test_matching_is_case_sensitive(relative: str, pattern: str, include: bool):
    """
    [Unit] discovery: verifies literals and globs match case-sensitively in both columns.

    Scenario:
        Given a path and a pattern that differ only in letter case
        When selector_matches applies the include or exclude column
        Then it does not match (no casefold, threat model M12 / T8).

    Boundaries:
        - Focus: ADR 0006 Contract 2 "case-sensitive"; story edge case "case-insensitive filesystems"
        - Fixtures/params: relative, pattern, include
        - Scope: selector_matches only

    On failure, first check:
        - fnmatch (case-normalising) used instead of fnmatchcase, or a lower()/casefold()

    :param relative: The file's relative path.
    :param pattern: The pattern.
    :param include: Which column is applied.
    """
    assert selector_matches(relative, pattern, include=include) is False
