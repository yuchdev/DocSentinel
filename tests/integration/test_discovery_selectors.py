"""``scan(include=, exclude=)`` over trees built in the test body (Milestone 0009 Story 02.0, Task 04).

ADR 0006 Contracts 1, 4 and 5: the keywords replace the include and append to the
exclude on top of a loaded or injected ``Config`` (never mutated), the walk never enters
a literal excluded directory, the selection is logged with counts only, a single-file
target ignores the keywords with one ``WARNING`` after the shape checks, and an empty
inventory under invoker selection is a ``ConfigError`` (owner ruling R1).
"""

import logging
import os
import time
from pathlib import Path

import pytest

from docsentinel import Config, ConfigError, cli, scan
from docsentinel.discovery import discover_with_skips, discover_with_stats
from docsentinel.engine import EMPTY_SELECTION_MESSAGE
from tests.log_helpers import problem_output


def _tree(root: Path, *relatives: str) -> Path:
    """Create one small Markdown file per relative path under ``root`` and return ``root``."""
    for relative in relatives:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {path.stem}\n\nSome words here.\n", encoding="utf-8")
    return root


def _paths(root: Path, **keywords: object) -> list[str]:
    """Return the inventory paths of a scan of ``root`` with the given keywords."""
    return [document.path for document in scan(root, **keywords).documents]


def _messages(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    """Return the docsentinel log messages at exactly ``level``."""
    return [r.getMessage() for r in caplog.records if r.name.startswith("docsentinel") and r.levelno == level]


def test_include_replaces_and_exclude_appends_on_injected_config(tmp_path: Path):
    """
    [Integration] discovery: verifies include replaces and exclude appends on an injected Config.

    Scenario:
        Given a tree with docs/a.md, docs/old/b.md, other/c.md and vendor/d.md
            and an injected Config that includes everything and excludes vendor
        When scan() runs with include=["docs"] and exclude=["docs/old"]
        Then only docs/a.md is inventoried (vendor stays excluded) and the Config is unchanged.

    Boundaries:
        - Focus: ADR 0006 Contract 4 merge; Contract 1 "the injected object is never mutated"
        - Fixtures/params: tmp_path tree built in the test body
        - Scope: library scan()

    On failure, first check:
        - engine._apply_invoker_selection
    """
    root = _tree(tmp_path, "docs/a.md", "docs/old/b.md", "other/c.md", "vendor/d.md")
    injected = Config(include=("**/*.md",), exclude=("vendor",))

    assert _paths(root, config=injected) == ["docs/a.md", "docs/old/b.md", "other/c.md"]
    assert _paths(root, config=injected, include=["docs"], exclude=["docs/old"]) == ["docs/a.md"]
    assert injected.include == ("**/*.md",)
    assert injected.exclude == ("vendor",)


def test_exclude_wins_and_configured_excludes_stay(tmp_path: Path):
    """
    [Integration] discovery: verifies exclude wins over include and configured excludes survive --include.

    Scenario:
        Given a tree with docs/a.md, docs/b.md and node_modules/pkg/readme.md and the default config
        When scan() runs with include=["docs", "node_modules/pkg/readme.md"] and exclude=["docs/a.md"]
        Then only docs/b.md is inventoried; and include=["node_modules/pkg/readme.md"] alone
            admits nothing (the configured node_modules exclude wins), so R1 fails the scan.

    Boundaries:
        - Focus: story decisions S3 and S4; ADR 0006 Contract 5 step 6 (R1)
        - Fixtures/params: tmp_path tree built in the test body
        - Scope: library scan()

    On failure, first check:
        - the merged exclude keeps Config().exclude first
    """
    root = _tree(tmp_path, "docs/a.md", "docs/b.md")
    (root / "node_modules" / "pkg").mkdir(parents=True)
    (root / "node_modules" / "pkg" / "readme.md").write_text("# pkg\n", encoding="utf-8")

    assert _paths(root, include=["docs", "node_modules/pkg/readme.md"], exclude=["docs/a.md"]) == ["docs/b.md"]
    with pytest.raises(ConfigError, match="^the selection admitted no document"):
        scan(root, include=["node_modules/pkg/readme.md"])


def test_literal_exclude_never_walked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Integration] discovery: verifies the walk never enters a literal excluded directory.

    Scenario:
        Given a tree with docs/a.md and docs/archive/deep/b.md
        When scan() runs with exclude=["docs/archive"] while os.walk is recorded
        Then no walked directory lies at or below docs/archive.

    Boundaries:
        - Focus: Story 02.0 acceptance "the walk never enters an excluded directory"
        - Fixtures/params: tmp_path tree; os.walk wrapped to record visited directories
        - Scope: library scan()

    On failure, first check:
        - discovery.prunes_directory for literal relative paths
    """
    root = _tree(tmp_path, "docs/a.md", "docs/archive/deep/b.md")
    visited: list[str] = []
    real_walk = os.walk

    def recording_walk(top, *args, **kwargs):
        """Record each directory os.walk yields."""
        for current, directories, filenames in real_walk(top, *args, **kwargs):
            visited.append(Path(current).relative_to(root.resolve()).as_posix())
            yield current, directories, filenames

    monkeypatch.setattr("docsentinel.discovery.os.walk", recording_walk)

    assert _paths(root, exclude=["docs/archive"]) == ["docs/a.md"]
    assert visited == [".", "docs"]


def test_selection_info_line_has_counts_only(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Integration] discovery: verifies the INFO selection line carries counts only and dedups invoker additions.

    Scenario:
        Given a tree with docs/a.md and the default config (three excludes)
        When scan() runs with include=["docs", "docs/"] and exclude=[".git", "secret-name", "secret-name"]
        Then the INFO line reads include 1 (invoker), exclude 4 (3 configured, 1 invoker),
            no INFO record names a pattern, and each pattern appears once at DEBUG.

    Boundaries:
        - Focus: ADR 0006 Contract 5 step 5; threat model M22
        - Fixtures/params: tmp_path tree; caplog at DEBUG
        - Scope: library scan()

    On failure, first check:
        - engine._log_selection
    """
    root = _tree(tmp_path, "docs/a.md")
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    scan(root, include=["docs", "docs/"], exclude=[".git", "secret-name", "secret-name"])

    info = [message for message in _messages(caplog, logging.INFO) if message.startswith("selection:")]
    assert info == ["selection: include 1 pattern(s) (invoker), exclude 4 pattern(s) (3 configured, 1 invoker)"]
    assert not any("secret-name" in message for message in _messages(caplog, logging.INFO))
    debug = _messages(caplog, logging.DEBUG)
    assert debug.count("selection: include docs (invoker)") == 1
    assert debug.count("selection: exclude secret-name (invoker)") == 1
    assert debug.count("selection: exclude .git (configured)") == 1


def test_config_only_selection_logs_configured_counts(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Integration] discovery: verifies a scan without keywords logs the configured selection and no warning.

    Scenario:
        Given a tree with docs/a.md and no config
        When scan() runs without include or exclude
        Then the INFO line reports the default counts and no WARNING is logged.

    Boundaries:
        - Focus: ADR 0006 Contract 5 step 5 (once per scan)
        - Fixtures/params: tmp_path tree; caplog
        - Scope: library scan()

    On failure, first check:
        - engine._log_selection with invoker_include False
    """
    root = _tree(tmp_path, "docs/a.md")
    caplog.set_level(logging.INFO, logger="docsentinel")

    assert _paths(root) == ["docs/a.md"]
    assert "selection: include 2 pattern(s) (configured), exclude 3 pattern(s) (3 configured, 0 invoker)" in (
        _messages(caplog, logging.INFO)
    )
    assert _messages(caplog, logging.WARNING) == []


def test_unmatched_exclude_and_zero_hit_include_warn_once(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Integration] discovery: verifies one WARNING per unmatched literal exclude and per zero-hit invoker include.

    Scenario:
        Given a tree with docs/a.md
        When scan() runs with include=["docs", "*.txt"] and exclude=["docs/missing"]
        Then the scan succeeds and logs exactly the two WARNINGs, each once.

    Boundaries:
        - Focus: ADR 0006 Contract 5 steps 5 and 6
        - Fixtures/params: tmp_path tree; caplog
        - Scope: library scan()

    On failure, first check:
        - InvokerSelection.unmatched_exclude logging and the include_hits loop in engine.scan
    """
    root = _tree(tmp_path, "docs/a.md")
    caplog.set_level(logging.INFO, logger="docsentinel")

    assert _paths(root, include=["docs", "*.txt"], exclude=["docs/missing"]) == ["docs/a.md"]
    assert _messages(caplog, logging.WARNING) == [
        "exclude pattern docs/missing names nothing under the scan root",
        "include pattern *.txt matched no document",
    ]


def test_empty_inventory_under_invoker_selection_raises(tmp_path: Path):
    """
    [Integration] discovery: verifies R1 for the library and that config-only selection stays clean.

    Scenario:
        Given a tree with docs/a.md
        When scan() runs with exclude=["docs"], and separately with an injected Config excluding docs
        Then the first raises ConfigError with the fixed message, the second returns an empty inventory.

    Boundaries:
        - Focus: owner ruling R1; ADR 0006 Contract 5 step 6
        - Fixtures/params: tmp_path tree
        - Scope: library scan()

    On failure, first check:
        - the invoker_selection guard on the R1 check
    """
    root = _tree(tmp_path, "docs/a.md")

    with pytest.raises(ConfigError) as caught:
        scan(root, exclude=["docs"])
    assert str(caught.value) == EMPTY_SELECTION_MESSAGE
    assert _paths(root, config=Config(exclude=("docs",))) == []


def test_single_file_target_shape_checks_then_ignores(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Integration] discovery: verifies a single-file target shape-checks the keywords, then ignores them.

    Scenario:
        Given a tree with docs/a.md
        When scan(docs/a.md) runs with a bare-string include, and with exclude=["docs/a.md"]
        Then the first raises the bare-string ConfigError; the second scans the file and warns once.

    Boundaries:
        - Focus: story decision S9; ADR 0006 Contract 5 steps 2 and 3 (O4, O5)
        - Fixtures/params: tmp_path tree; caplog
        - Scope: library scan()

    On failure, first check:
        - check_invoker_selector_shape runs before the selected_file branch
    """
    root = _tree(tmp_path, "docs/a.md")
    caplog.set_level(logging.INFO, logger="docsentinel")

    with pytest.raises(ConfigError, match="^include must be a sequence of patterns, not a single string"):
        scan(root / "docs" / "a.md", include="docs")  # type: ignore[arg-type]
    assert [document.path for document in scan(root / "docs" / "a.md", exclude=["docs/a.md"]).documents] == ["a.md"]
    assert _messages(caplog, logging.WARNING) == ["--include/--exclude ignored for a single-file scan target"]


def test_absolute_value_through_spelled_root(tmp_path: Path):
    """
    [Integration] discovery: verifies an absolute value under the root as spelled (a symlink) is accepted.

    Scenario:
        Given a tree with docs/a.md and docs/b.md and a symlink ``link`` to the tree
        When scan(link) runs with include=[<link>/docs/a.md]
        Then only docs/a.md is inventoried: the spelled root is a shared root spelling (A4).

    Boundaries:
        - Focus: threat model A4/M8; ADR 0006 Contract 5 step 4
        - Fixtures/params: tmp_path tree with a directory symlink
        - Scope: library scan()

    On failure, first check:
        - engine passes selector_root_spellings(directory, root) to the normaliser
    """
    root = _tree(tmp_path / "real", "docs/a.md", "docs/b.md")
    link = tmp_path / "link"
    link.symlink_to(root, target_is_directory=True)

    assert _paths(link, include=[str(link / "docs" / "a.md")]) == ["docs/a.md"]


_LOOKALIKE_SEPARATORS = ("∕", "／", "⁄", "⧸", "＼", "﹨")


def _case_insensitive(directory: Path) -> bool:
    """Return whether the file system holding ``directory`` folds letter case."""
    probe = directory / "case-probe"
    probe.write_text("x", encoding="utf-8")
    try:
        return (directory / "CASE-PROBE").exists()
    finally:
        probe.unlink()


def test_lookalike_named_file_selected_only_by_exact_name(tmp_path: Path):
    """
    [Integration] discovery: verifies a file named with a look-alike separator is selected only by its exact name.

    Scenario:
        Given docs/a.md and six root files docs<c>a.md, one per look-alike separator c
        When scan() runs with include=[docs<c>a.md], with include=[docs<c>*.md], with include=[docs/a.md]
            and with exclude=[docs]
        Then each look-alike include admits exactly its own file, docs/a.md admits only docs/a.md, and
            excluding docs keeps every look-alike file.

    Boundaries:
        - Focus: threat model M12 (ruling U1: look-alikes are name characters end to end)
        - Fixtures/params: tmp_path tree built in the test body
        - Scope: library scan()

    On failure, first check:
        - Any Unicode normalisation in the normaliser or the matcher
    """
    lookalikes = [f"docs{character}a.md" for character in _LOOKALIKE_SEPARATORS]
    root = _tree(tmp_path, "docs/a.md", *lookalikes)

    for name in lookalikes:
        assert _paths(root, include=[name]) == [name]
        assert _paths(root, include=[name.replace("a.md", "*.md")]) == [name]
    assert _paths(root, include=["docs/a.md"]) == ["docs/a.md"]
    assert sorted(_paths(root, exclude=["docs"])) == sorted(lookalikes)


@pytest.mark.parametrize("pattern", ["*", "**", "?*", "docs"])
def test_exclude_star_empty_inventory_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, pattern: str
):
    """
    [Integration] discovery: verifies an invoker exclude that empties the inventory fails (owner ruling R1).

    Scenario:
        Given a docs-only tree (docs/a.md, docs/sub/b.md)
        When scan() runs with exclude=[pattern], and the CLI runs ``scan --exclude pattern``
        Then scan() raises ConfigError with the fixed message, the CLI exits 2 with it as the first
            problem line, and the same pattern as a config-only exclude still exits 0.

    Boundaries:
        - Focus: threat model T8/M18 with R1; ADR 0006 Contract 5 step 6
        - Fixtures/params: tmp_path tree; capsys; monkeypatch (chdir away from the tree); pattern
        - Scope: library scan() and in-process CLI calls

    On failure, first check:
        - The invoker_selection guard on the R1 check in engine.scan

    :param pattern: An exclude that removes every document.
    """

    root = _tree(tmp_path / "repo", "docs/a.md", "docs/sub/b.md")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ConfigError) as caught:
        scan(root, exclude=[pattern])
    assert str(caught.value) == EMPTY_SELECTION_MESSAGE

    assert cli.main(["scan", str(root), f"--exclude={pattern}"]) == 2
    assert problem_output(capsys.readouterr().err).splitlines()[0] == f"Scan failed: {EMPTY_SELECTION_MESSAGE}"

    (root / "docsentinel.toml").write_text(f'exclude = ["{pattern}"]\n', encoding="utf-8")
    assert scan(root).documents == ()
    assert cli.main(["scan", str(root)]) == 0
    assert problem_output(capsys.readouterr().err) == ""


def test_case_mismatched_literal_include_zero_hit_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Integration] discovery: verifies a case-mismatched literal include that exists still admits nothing, loudly.

    Scenario:
        Given a case-insensitive file system holding docs/user/a.md and docs/b.md
        When scan() runs with include=["DOCS/user", "docs/b.md"], and then with include=["DOCS/user"] alone
        Then the first admits only docs/b.md and warns that DOCS/user matched no document;
            the second raises the R1 empty-selection ConfigError after the same warning.

    Boundaries:
        - Focus: threat model T8/M18 (lstat succeeds, case-sensitive matching fails); skipped on
            case-sensitive file systems
        - Fixtures/params: tmp_path tree; caplog
        - Scope: library scan()

    On failure, first check:
        - Any casefold added to matching (forbidden by M12) or a missing zero-hit WARNING
    """
    if not _case_insensitive(tmp_path):
        pytest.skip("the temporary file system is case-sensitive")
    root = _tree(tmp_path / "repo", "docs/user/a.md", "docs/b.md")
    caplog.set_level(logging.WARNING, logger="docsentinel")

    assert _paths(root, include=["DOCS/user", "docs/b.md"]) == ["docs/b.md"]
    assert _messages(caplog, logging.WARNING) == ["include pattern DOCS/user matched no document"]

    caplog.clear()
    with pytest.raises(ConfigError, match="^the selection admitted no document"):
        scan(root, include=["DOCS/user"])
    assert _messages(caplog, logging.WARNING) == ["include pattern DOCS/user matched no document"]


def test_pathological_globs_complete(tmp_path: Path):
    """
    [Integration] discovery: verifies 256 pathological 1,024-character globs per key finish in bounded time.

    Scenario:
        Given a three-file tree, 255 distinct alternating-star globs of 1,024 characters plus one
            1,024-character glob that matches every Markdown file
        When scan() runs with those 256 includes and the 255 pathological globs as excludes
        Then it completes well inside a generous time budget and inventories all three files.

    Boundaries:
        - Focus: threat model T10/M20 (no exponential backtracking; the accepted cost residual)
        - Fixtures/params: tmp_path tree built in the test body
        - Scope: library scan()

    On failure, first check:
        - A regex other than fnmatchcase's translate, or per-path recompilation of patterns
    """
    root = _tree(tmp_path, "a.md", "docs/b.md", "docs/user/c.md")
    pathological = [(f"{index:03d}" + "*a" * 511)[:1023] + "b" for index in range(255)]
    matching = "*" * 1021 + ".md"
    assert {len(pattern) for pattern in (*pathological, matching)} == {1024}

    started = time.perf_counter()
    result = scan(root, include=[matching, *pathological], exclude=pathological)
    elapsed = time.perf_counter() - started

    assert [document.path for document in result.documents] == ["a.md", "docs/b.md", "docs/user/c.md"]
    assert elapsed < 90.0


def test_include_never_prunes_the_walk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Integration] discovery: verifies a literal include narrows the inventory but not the walk.

    Scenario:
        Given docs/user/a.md, docs/dev/b.md and other/c.md
        When scan() runs with include=["docs/user"] while os.walk is recorded
        Then only docs/user/a.md is inventoried and every directory was still walked.

    Boundaries:
        - Focus: ADR 0006 Contract 2 rule 2 (include never prunes)
        - Fixtures/params: tmp_path tree; os.walk wrapped to record visited directories
        - Scope: library scan()

    On failure, first check:
        - prunes_directory being applied to include patterns
    """
    root = _tree(tmp_path, "docs/user/a.md", "docs/dev/b.md", "other/c.md")
    visited: list[str] = []
    real_walk = os.walk

    def recording_walk(top, *args, **kwargs):
        """Record each directory os.walk yields."""
        for current, directories, filenames in real_walk(top, *args, **kwargs):
            visited.append(Path(current).relative_to(root.resolve()).as_posix())
            yield current, directories, filenames

    monkeypatch.setattr("docsentinel.discovery.os.walk", recording_walk)

    assert _paths(root, include=["docs/user"]) == ["docs/user/a.md"]
    assert sorted(visited) == [".", "docs", "docs/dev", "docs/user", "other"]


def test_excluded_directory_counts_once_in_skip_count(tmp_path: Path):
    """
    [Integration] discovery: verifies a directory pruned by both the path and the name rule is skipped once.

    Scenario:
        Given docs/a.md and docs/archive/old.md
        When discover_with_skips runs with exclude ("docs/archive", "archive") and with each alone
        Then old.md is never inventoried and the skip count is 1 in every case.

    Boundaries:
        - Focus: ADR 0006 Contract 2 rule 4 ("an excluded directory counts once, by either rule")
        - Fixtures/params: tmp_path tree
        - Scope: discover_with_skips

    On failure, first check:
        - The any(...) prune test in discover_with_stats counting per pattern instead of per directory
    """
    root = _tree(tmp_path, "docs/a.md", "docs/archive/old.md")

    for exclude in (("docs/archive", "archive"), ("docs/archive",), ("archive",)):
        documents, skipped = discover_with_skips(root, Config(exclude=exclude))
        assert ([document.path for document in documents], skipped) == (["docs/a.md"], 1), exclude


def test_include_hits_count_every_matching_pattern_in_order(tmp_path: Path):
    """
    [Integration] discovery: verifies include hit counts follow the effective list and count overlaps.

    Scenario:
        Given top.md, docs/a.md and docs/sub/b.md
        When discover_with_stats runs with include ("docs", "**/*.md", "docs/a.md", "nothing")
        Then the docs files are admitted and the hits are (2, 2, 1, 0): a document counts toward
            every pattern it matches, and top.md (matched by none) counts toward none.

    Boundaries:
        - Focus: ADR 0006 Contract 2 rule 6 (hit counts)
        - Fixtures/params: tmp_path tree
        - Scope: discover_with_stats

    On failure, first check:
        - The per-pattern hits loop (no short-circuit on the first match)
    """
    root = _tree(tmp_path, "top.md", "docs/a.md", "docs/sub/b.md")

    found = discover_with_stats(root, Config(include=("docs", "**/*.md", "docs/a.md", "nothing")))

    assert [document.path for document in found.documents] == ["docs/a.md", "docs/sub/b.md"]
    assert found.include_hits == (2, 2, 1, 0)


def test_single_component_literal_exclude_naming_nothing_logs_no_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    """
    [Integration] discovery: verifies --exclude build without a build directory logs no WARNING (O3).

    Scenario:
        Given a tree with docs/a.md and no build directory anywhere
        When scan() runs with exclude=["build"], and then with exclude=["docs/build"]
        Then the first logs no WARNING; the second logs the unmatched-exclude WARNING once.

    Boundaries:
        - Focus: ADR 0006 open point O3; Contract 5 step 5
        - Fixtures/params: tmp_path tree; caplog
        - Scope: library scan()

    On failure, first check:
        - The single-component exception in normalize_invoker_selectors
    """
    root = _tree(tmp_path, "docs/a.md")
    caplog.set_level(logging.INFO, logger="docsentinel")

    assert _paths(root, exclude=["build"]) == ["docs/a.md"]
    assert _messages(caplog, logging.WARNING) == []
    assert _paths(root, exclude=["docs/build"]) == ["docs/a.md"]
    assert _messages(caplog, logging.WARNING) == ["exclude pattern docs/build names nothing under the scan root"]


def test_dot_include_uses_builtin_default_not_configured(tmp_path: Path):
    """
    [Integration] discovery: verifies include=["."] restores the built-in include over a narrower configured one.

    Scenario:
        Given top.md, docs/a.md, notes.txt and an injected Config whose include is docs/a.md only
        When scan() runs with include=["."]
        Then every Markdown file is inventoried (not notes.txt) and the injected Config is unchanged.

    Boundaries:
        - Focus: ADR 0006 Contract 3 step 8 (Config().include, not the configured include)
        - Fixtures/params: tmp_path tree
        - Scope: library scan()

    On failure, first check:
        - _lexical_normalize returning settings.include instead of Config().include
    """
    root = _tree(tmp_path, "top.md", "docs/a.md")
    (root / "notes.txt").write_text("plain\n", encoding="utf-8")
    injected = Config(include=("docs/a.md",))

    assert _paths(root, config=injected) == ["docs/a.md"]
    assert _paths(root, config=injected, include=["."]) == ["docs/a.md", "top.md"]
    assert injected.include == ("docs/a.md",)


def test_directory_include_under_excluded_directory_is_excluded(tmp_path: Path):
    """
    [Integration] discovery: verifies a directory include below an excluded directory admits nothing.

    Scenario:
        Given top.md and docs/archive/old.md
        When scan() runs with include=["docs/archive", "top.md"] and exclude=["docs"], and again with
            the same include and an injected Config excluding archive
        Then both inventories are [top.md].

    Boundaries:
        - Focus: story edge case "a directory include under an excluded directory"; story decision S4
        - Fixtures/params: tmp_path tree
        - Scope: library scan()

    On failure, first check:
        - Exclude pruning happening before include matching in discover_with_stats
    """
    root = _tree(tmp_path, "top.md", "docs/archive/old.md")
    include = ["docs/archive", "top.md"]

    assert _paths(root, include=include, exclude=["docs"]) == ["top.md"]
    assert _paths(root, config=Config(exclude=("archive",)), include=include) == ["top.md"]


def test_literal_non_markdown_file_include_inventoried(tmp_path: Path):
    """
    [Integration] discovery: verifies a literal include naming a non-Markdown file inventories it.

    Scenario:
        Given docs/a.md and docs/notes.txt
        When scan() runs with include=["docs/notes.txt"], and with include=["docs"]
        Then the first inventories docs/notes.txt with no finding; the directory include skips it.

    Boundaries:
        - Focus: story edge case "an include of a non-Markdown file named explicitly"; Contract 2 rule 3
        - Fixtures/params: tmp_path tree
        - Scope: library scan()

    On failure, first check:
        - The R == L branch of selector_matches
    """
    root = _tree(tmp_path, "docs/a.md")
    (root / "docs" / "notes.txt").write_text("See [x](missing.md).\n", encoding="utf-8")

    result = scan(root, include=["docs/notes.txt"])

    assert [document.path for document in result.documents] == ["docs/notes.txt"]
    assert result.findings == ()
    assert _paths(root, include=["docs"]) == ["docs/a.md"]


@pytest.mark.parametrize(
    ("keywords", "message"),
    [
        ({"include": []}, "include needs at least one value"),
        ({"include": ()}, "include needs at least one value"),
        ({"exclude": ["x"] * 257}, "exclude accepts at most 256 values"),
        ({"include": ["x" * 1025]}, "include value is longer than 1024 characters"),
    ],
)
def test_single_file_target_empty_or_oversized_list_refused(tmp_path: Path, keywords: dict, message: str):
    """
    [Integration] discovery: verifies an empty or oversized selector list fails for a single-file target.

    Scenario:
        Given a tree with docs/a.md
        When scan(docs/a.md) runs with an empty, 257-item or over-long selector
        Then the fixed shape ConfigError is raised although the target ignores selectors.

    Boundaries:
        - Focus: ADR 0006 owner point O4; Contract 5 step 2
        - Fixtures/params: tmp_path tree; keywords, message
        - Scope: library scan()

    On failure, first check:
        - check_invoker_selector_shape runs before the selected_file branch

    :param keywords: The malformed selector keyword.
    :param message: The expected message prefix.
    """
    root = _tree(tmp_path, "docs/a.md")

    with pytest.raises(ConfigError) as caught:
        scan(root / "docs" / "a.md", **keywords)

    assert str(caught.value) == f"{message}; values are relative to the scan root"
