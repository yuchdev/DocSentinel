"""Mock tests for the filesystem side of invoker selector normalisation and discovery pruning.

Every filesystem call the normaliser makes is recorded by patching ``os.lstat``,
``os.stat``, ``os.readlink``, ``os.path.realpath``, ``os.path.abspath``, ``os.scandir``,
``os.listdir`` and ``Path.resolve``; tests assert that each recorded path is the
canonical root or lies under it. Trees are tiny ``tmp_path`` layouts built inline.
"""

import logging
import os
import stat
from collections.abc import Callable
from pathlib import Path

import pytest

from docsentinel import cli, engine, scan
from docsentinel.config import Config, ConfigError
from docsentinel.discovery import (
    InvokerSelection,
    discover_with_skips,
    discover_with_stats,
    normalize_invoker_selectors,
    selector_root_spellings,
)

_RECORDED = ("lstat", "stat", "readlink", "scandir", "listdir")


def _root(tmp_path: Path) -> Path:
    """Build a small tree and return its canonical root.

    The tree is ``root/docs/user/a.md``, ``root/docs/archive/old.md``, an in-root
    directory symlink ``root/docs/alias -> user``, a file symlink
    ``root/docs/link.md -> user/a.md`` and an escaping symlink ``root/docs/out``
    pointing at a sibling directory ``outside`` next to the root.

    :param tmp_path: The pytest scratch directory.
    :returns: The resolved root.
    """
    base = tmp_path.resolve()
    root = base / "root"
    (root / "docs" / "user").mkdir(parents=True)
    (root / "docs" / "archive").mkdir()
    (root / "docs" / "user" / "a.md").write_text("# A\n", encoding="utf-8")
    (root / "docs" / "archive" / "old.md").write_text("# Old\n", encoding="utf-8")
    (base / "outside").mkdir()
    (base / "outside" / "x.md").write_text("# X\n", encoding="utf-8")
    (root / "docs" / "alias").symlink_to("user")
    (root / "docs" / "link.md").symlink_to("user/a.md")
    (root / "docs" / "out").symlink_to(base / "outside")
    (root / "docs" / "relout").symlink_to("../../outside")
    return root


def _record(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Patch the filesystem entry points and return the list they append paths to.

    :param monkeypatch: The pytest monkeypatch fixture.
    :returns: The recorded call paths, as strings.
    """
    calls: list[str] = []

    def wrap(name: str, original: Callable) -> Callable:
        """Return a wrapper of ``original`` that records its first argument.

        :param name: The attribute name, for the record.
        :param original: The function to wrap.
        :returns: The wrapper.
        """

        def recorder(path, *args, **kwargs) -> object:
            """Record ``path`` and call through.

            :param path: The path argument.
            :param args: Positional arguments passed through.
            :param kwargs: Keyword arguments passed through.
            :returns: The wrapped function's result.
            """
            calls.append(f"{name}:{os.fspath(path)}")
            return original(path, *args, **kwargs)

        return recorder

    for name in _RECORDED:
        monkeypatch.setattr(os, name, wrap(name, getattr(os, name)))
    for name in ("realpath", "abspath"):
        monkeypatch.setattr(os.path, name, wrap(name, getattr(os.path, name)))
    original_resolve = Path.resolve

    def resolve(self: Path, *args, **kwargs) -> Path:
        """Record a ``Path.resolve`` call and call through.

        :param self: The path being resolved.
        :param args: Positional arguments passed through.
        :param kwargs: Keyword arguments passed through.
        :returns: The resolved path.
        """
        calls.append(f"resolve:{self}")
        return original_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    return calls


def _inside(root: Path, calls: list[str]) -> bool:
    """Return whether every recorded call is on the root or below it (separator-aware).

    :param root: The canonical root.
    :param calls: Recorded ``name:path`` entries.
    :returns: ``True`` when no call left the root.
    """
    text = os.fspath(root)
    return all(path == text or path.startswith(text + os.sep) for path in (c.split(":", 1)[1] for c in calls))


def test_include_through_inroot_symlinked_dir_refused(tmp_path: Path):
    """
    [Unit] discovery: verifies a literal include reached through an in-root directory symlink is refused.

    Scenario:
        Given docs/alias -> user inside the root
        When docs/alias/a.md is normalised as an include
        Then "symlinked paths are not inventoried" is raised (ruling O6).

    Boundaries:
        - Focus: threat model M15
        - Fixtures/params: tmp_path
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The contained != lexical signal in _check_literal
    """
    root = _root(tmp_path)

    with pytest.raises(ConfigError, match="symlinked paths are not inventoried"):
        normalize_invoker_selectors(root, ["docs/alias/a.md"], None)


def test_include_final_component_symlink_refused(tmp_path: Path):
    """
    [Unit] discovery: verifies a literal include whose last component is a symlink is refused.

    Scenario:
        Given docs/link.md -> user/a.md
        When docs/link.md is normalised as an include
        Then "symlinked paths are not inventoried" is raised.

    Boundaries:
        - Focus: threat model M15
        - Fixtures/params: tmp_path
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The symlink signal in _check_literal
    """
    root = _root(tmp_path)

    with pytest.raises(ConfigError, match="symlinked paths are not inventoried"):
        normalize_invoker_selectors(root, ["docs/link.md"], None)


def test_exclude_through_inroot_symlink_listed_unmatched(tmp_path: Path):
    """
    [Unit] discovery: verifies a symlinked or missing literal exclude is kept and listed as unmatched.

    Scenario:
        Given excludes docs/alias, docs/missing, build (one component) and docs/archive
        When normalised
        Then all are kept; only docs/alias and docs/missing are unmatched (O3: build is not).

    Boundaries:
        - Focus: threat model M15, ADR open point O3
        - Fixtures/params: tmp_path
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The unmatched condition in normalize_invoker_selectors
    """
    root = _root(tmp_path)

    selection = normalize_invoker_selectors(root, None, ["docs/alias", "docs/missing", "build", "docs/archive"])

    assert selection == InvokerSelection(
        include=None,
        exclude=("docs/alias", "docs/missing", "build", "docs/archive"),
        unmatched_exclude=("docs/alias", "docs/missing"),
    )


@pytest.mark.parametrize("key", ["include", "exclude"])
@pytest.mark.parametrize("value", ["docs/out/x.md", "docs/relout/x.md"])
def test_symlink_escape_refused_for_include_and_exclude(tmp_path: Path, key: str, value: str):
    """
    [Unit] discovery: verifies a literal leaving the root through a symlink is refused for both keys.

    Scenario:
        Given absolute and relative symlinks that point outside the root
        When a literal through them is normalised as include or exclude
        Then "leaves the scan root through a symlink" is raised.

    Boundaries:
        - Focus: threat model M3
        - Fixtures/params: tmp_path, key, value
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The contained_path None branch in _check_literal

    :param key: include or exclude.
    :param value: The escaping literal.
    """
    root = _root(tmp_path)
    selectors = {"include": None, "exclude": None, key: [value]}

    with pytest.raises(ConfigError, match="leaves the scan root through a symlink"):
        normalize_invoker_selectors(root, **selectors)


@pytest.mark.parametrize("value", ["docs/out/x.md", "docs/relout/x.md"])
def test_lstat_only_inside_root_for_escaping_relative_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str
):
    """
    [Unit] discovery: verifies an escaping symlink is detected with no call outside the root.

    Scenario:
        Given absolute and relative escaping symlinks
        When a literal through them is normalised (and refused)
        Then every recorded filesystem call is on the root or below it.

    Boundaries:
        - Focus: threat model M3, M7
        - Fixtures/params: tmp_path, monkeypatch, value
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The order of the contained_path walk and the lstat

    :param value: The escaping literal.
    """
    root = _root(tmp_path)
    calls = _record(monkeypatch)

    with pytest.raises(ConfigError):
        normalize_invoker_selectors(root, [value], None)

    assert calls
    assert _inside(root, calls)


@pytest.mark.parametrize("value", ["/etc/passwd", "/net/attacker/x"])
def test_no_filesystem_call_for_absolute_outside_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str):
    """
    [Unit] discovery: verifies an absolute value outside the root is refused with zero filesystem calls.

    Scenario:
        Given an absolute value outside the root (existing or not)
        When normalised
        Then "is outside the scan root" is raised and nothing was stat-ed, realpath-ed or resolved.

    Boundaries:
        - Focus: threat model M6, M7, A1
        - Fixtures/params: tmp_path, monkeypatch, value
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - Any realpath/abspath/stat on the value before _relative_to_spellings

    :param value: The outside value.
    """
    root = _root(tmp_path)
    calls = _record(monkeypatch)

    with pytest.raises(ConfigError, match="is outside the scan root"):
        normalize_invoker_selectors(root, [value], None)

    assert calls == []


def test_no_filesystem_call_for_glob_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] discovery: verifies glob values never reach the filesystem.

    Scenario:
        Given glob include and exclude values, including one under a symlink name
        When normalised
        Then they are returned and no filesystem call was made.

    Boundaries:
        - Focus: threat model M5
        - Fixtures/params: tmp_path, monkeypatch
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The is_glob skip in normalize_invoker_selectors
    """
    root = _root(tmp_path)
    calls = _record(monkeypatch)

    selection = normalize_invoker_selectors(root, ["docs/out/*.md"], ["**/archive/*"])

    assert selection.include == ("docs/out/*.md",)
    assert calls == []


def test_no_filesystem_call_before_character_checks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] discovery: verifies a refused character makes the call fail before any filesystem access.

    Scenario:
        Given a valid literal include and an exclude with a NUL
        When normalised
        Then the character error is raised and nothing was stat-ed.

    Boundaries:
        - Focus: threat model M13
        - Fixtures/params: tmp_path, monkeypatch
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The two-phase order in normalize_invoker_selectors
    """
    root = _root(tmp_path)
    calls = _record(monkeypatch)

    with pytest.raises(ConfigError, match="control, format"):
        normalize_invoker_selectors(root, ["docs/user"], ["a\x00b"])

    assert calls == []


def test_literal_include_non_regular_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] discovery: verifies a literal include that lstat reports as a FIFO is refused.

    Scenario:
        Given os.lstat reporting S_IFIFO for the final path
        When docs/user/a.md is normalised as an include
        Then "not a regular file or directory" is raised.

    Boundaries:
        - Focus: threat model M16
        - Fixtures/params: tmp_path, monkeypatch
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The S_ISREG/S_ISDIR test in _check_literal
    """
    root = _root(tmp_path)
    target = os.fspath(root / "docs" / "user" / "a.md")
    original = os.lstat

    def fake_lstat(path, *args, **kwargs) -> os.stat_result:
        """Report a FIFO for the target path.

        :param path: The path.
        :param args: Passed through.
        :param kwargs: Passed through.
        :returns: A stat result.
        """
        if os.fspath(path) == target:
            return os.stat_result((stat.S_IFIFO | 0o644, 0, 0, 1, 0, 0, 0, 0, 0, 0))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", fake_lstat)

    with pytest.raises(ConfigError, match="not a regular file or directory"):
        normalize_invoker_selectors(root, ["docs/user/a.md"], None)


def test_lstat_oserror_becomes_config_error_with_relative_echo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] discovery: verifies an lstat OSError becomes a ConfigError echoing only the relative value.

    Scenario:
        Given os.lstat raising PermissionError
        When docs/user is normalised as an include
        Then the ConfigError says "cannot check it (<strerror>)" and holds no absolute path.

    Boundaries:
        - Focus: threat model M17
        - Fixtures/params: tmp_path, monkeypatch
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The OSError handler in _check_literal
    """
    root = _root(tmp_path)

    def denied(path, *args, **kwargs):
        """Raise a permission error.

        :param path: The path.
        :param args: Ignored.
        :param kwargs: Ignored.
        :raises PermissionError: Always.
        """
        raise PermissionError(13, "Permission denied", os.fspath(path))

    monkeypatch.setattr(os, "lstat", denied)

    with pytest.raises(ConfigError) as caught:
        normalize_invoker_selectors(root, ["docs/user"], None)

    message = str(caught.value)
    assert message.startswith("include value docs/user: cannot check it (Permission denied)")
    assert os.fspath(root) not in message


def test_missing_literal_include_refused(tmp_path: Path):
    """
    [Unit] discovery: verifies a literal include that names nothing is refused.

    Scenario:
        Given an include docs/nope
        When normalised
        Then "not found under the scan root" is raised.

    Boundaries:
        - Focus: Contract 3 step 10, story S8
        - Fixtures/params: tmp_path
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The missing branch of _check_literal
    """
    root = _root(tmp_path)

    with pytest.raises(ConfigError, match="not found under the scan root"):
        normalize_invoker_selectors(root, ["docs/nope"], None)


def test_root_spelling_requires_samefile(tmp_path: Path):
    """
    [Unit] discovery: verifies a spelled root is added only when it is the same directory.

    Scenario:
        Given a symlink spelling of the root and an unrelated directory
        When selector_root_spellings is called with each
        Then only the same-directory spelling is added after the canonical root.

    Boundaries:
        - Focus: threat model M8
        - Fixtures/params: tmp_path
        - Scope: selector_root_spellings

    On failure, first check:
        - The samefile test in selector_root_spellings
    """
    root = _root(tmp_path)
    spelled = tmp_path.resolve() / "spelled"
    spelled.symlink_to(root)

    assert selector_root_spellings(root, spelled) == (root, spelled)
    assert selector_root_spellings(root, tmp_path.resolve() / "outside") == (root,)
    assert selector_root_spellings(root, tmp_path.resolve() / "missing") == (root,)


def test_pwd_not_used_for_selector_spellings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] discovery: verifies $PWD never adds a spelling.

    Scenario:
        Given PWD set to a symlink spelling of the root and the root spelled canonically
        When selector_root_spellings is called
        Then only the canonical root is returned.

    Boundaries:
        - Focus: threat model M8
        - Fixtures/params: tmp_path, monkeypatch
        - Scope: selector_root_spellings

    On failure, first check:
        - Any os.environ read in selector_root_spellings
    """
    root = _root(tmp_path)
    alias = tmp_path.resolve() / "alias"
    alias.symlink_to(root)
    monkeypatch.setenv("PWD", os.fspath(alias))

    assert selector_root_spellings(root, root) == (root,)


def test_literal_exclude_prunes_walk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] discovery: verifies os.walk never yields an excluded literal directory or its children.

    Scenario:
        Given exclude docs/archive in the config and os.walk wrapped to record each yielded directory
        When discover_with_stats walks the root
        Then no yielded directory is docs/archive or below it, and old.md is not inventoried.

    Boundaries:
        - Focus: Task 03 verification (the walk never enters an excluded directory)
        - Fixtures/params: tmp_path, monkeypatch
        - Scope: discover_with_stats

    On failure, first check:
        - prunes_directory in the directory loop
    """
    root = _root(tmp_path)
    yielded: list[str] = []
    original_walk = os.walk

    def spy_walk(top, *args, **kwargs):
        """Record each directory os.walk yields.

        :param top: The walk root.
        :param args: Passed through.
        :param kwargs: Passed through.
        :returns: The wrapped generator's items.
        """
        for entry in original_walk(top, *args, **kwargs):
            yielded.append(os.fspath(entry[0]))
            yield entry

    monkeypatch.setattr(os, "walk", spy_walk)
    config = Config(exclude=(".git", "docs/archive"))

    found = discover_with_stats(root, config)

    archive = os.fspath(root / "docs" / "archive")
    assert yielded
    assert not any(path == archive or path.startswith(archive + os.sep) for path in yielded)
    assert [document.path for document in found.documents] == ["docs/user/a.md"]
    assert found.include_hits == (1, 1)


def test_glob_exclude_inventory_and_skips_unchanged(tmp_path: Path):
    """
    [Unit] discovery: verifies a glob exclude keeps the name-only prune (owner ruling O1).

    Scenario:
        Given exclude **/archive, which matches no directory name
        When discover_with_skips walks the root
        Then docs/archive/old.md is still inventoried and the skip count is the four symlinks.

    Boundaries:
        - Focus: Contract 2 glob row byte-identical
        - Fixtures/params: tmp_path
        - Scope: discover_with_skips

    On failure, first check:
        - Whether prunes_directory tests a glob against the relative path
    """
    root = _root(tmp_path)

    documents, skipped = discover_with_skips(root, Config(exclude=("**/archive",)))

    assert [document.path for document in documents] == ["docs/archive/old.md", "docs/user/a.md"]
    assert skipped == 4


def test_literal_include_admits_markdown_below_directory_only(tmp_path: Path):
    """
    [Unit] discovery: verifies a configured literal directory include admits only .md files below it.

    Scenario:
        Given include docs/user and a PNG next to a.md
        When discover_with_stats walks the root
        Then only docs/user/a.md is admitted and the include hit count is 1.

    Boundaries:
        - Focus: Contract 2 rule 3, config literal semantics
        - Fixtures/params: tmp_path
        - Scope: discover_with_stats

    On failure, first check:
        - selector_matches include branch
    """
    root = _root(tmp_path)
    (root / "docs" / "user" / "pic.png").write_bytes(b"\x89PNG")

    found = discover_with_stats(root, Config(include=("docs/user",)))

    assert [document.path for document in found.documents] == ["docs/user/a.md"]
    assert found.include_hits == (1,)


def _outside_calls(base: Path, calls: list[str]) -> list[str]:
    """Return the recorded calls whose path is the outside directory or lies below it.

    :param base: The resolved ``tmp_path`` that holds ``root`` and ``outside``.
    :param calls: Recorded ``name:path`` entries.
    :returns: The offending entries.
    """
    outside = os.fspath(base / "outside")
    return [c for c in calls if c.split(":", 1)[1] == outside or c.split(":", 1)[1].startswith(outside + os.sep)]


@pytest.mark.parametrize("key", ["include", "exclude"])
@pytest.mark.parametrize("value", ["docs/out/x.md", "{root}/docs/out/x.md", "docs/out", "docs/hop/x.md"])
def test_lstat_only_inside_root_for_escaping_absolute_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, key: str, value: str
):
    """
    [Unit] discovery: verifies a symlink with an absolute outside target is refused with no call outside the root.

    Scenario:
        Given docs/out -> <abs>/outside and an in-root relay docs/hop -> out
        When a literal through docs/out (relative or absolute spelling, final component, or via the relay)
            is normalised as include or exclude
        Then "leaves the scan root through a symlink" is raised, every recorded call is under the root,
            and nothing under the outside directory was touched.

    Boundaries:
        - Focus: threat model M3, M7 (absolute symlink targets)
        - Fixtures/params: tmp_path, monkeypatch, key, value ({root} is the canonical root)
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The absolute-target branch of path_boundaries._walk (refuse without lstat of the target)

    :param key: include or exclude.
    :param value: The escaping literal.
    """
    root = _root(tmp_path)
    (root / "docs" / "hop").symlink_to("out")
    selectors = {"include": None, "exclude": None, key: [value.replace("{root}", os.fspath(root))]}
    calls = _record(monkeypatch)

    with pytest.raises(ConfigError, match="leaves the scan root through a symlink"):
        normalize_invoker_selectors(root, **selectors)

    assert calls
    assert _inside(root, calls)
    assert _outside_calls(tmp_path.resolve(), calls) == []


def test_no_realpath_or_resolve_of_selector_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] discovery: verifies no selector value is ever realpath-ed, abspath-ed or resolved.

    Scenario:
        Given relative and absolute literals, a glob, a tilde literal and an absolute outside value
        When the root spellings are computed for the canonical spelling and the values are normalised
        Then no realpath or resolve call was recorded, and the only abspath call is on the spelled root.

    Boundaries:
        - Focus: threat model M4, M6, M7 (A1: lexical handling of absolute values)
        - Fixtures/params: tmp_path, monkeypatch
        - Scope: selector_root_spellings and normalize_invoker_selectors

    On failure, first check:
        - Any os.path.realpath / os.path.abspath / Path.resolve on a value in discovery.py
    """
    root = _root(tmp_path)
    outside_value = f"{tmp_path.resolve()}/outside/x.md"
    calls = _record(monkeypatch)

    spellings = selector_root_spellings(root, os.fspath(root))
    selection = normalize_invoker_selectors(
        root,
        ["docs/user", f"{root}/docs/user/a.md", "docs/*.md"],
        ["~/x", "$HOME/y/z", f"{root}/docs/archive"],
        root_spellings=spellings,
    )
    with pytest.raises(ConfigError, match="is outside the scan root"):
        normalize_invoker_selectors(root, [outside_value], None, root_spellings=spellings)

    assert selection.include == ("docs/user", "docs/user/a.md", "docs/*.md")
    assert selection.unmatched_exclude == ("~/x", "$HOME/y/z")
    resolving = [c for c in calls if c.startswith(("realpath:", "resolve:"))]
    assert resolving == []
    assert [c for c in calls if c.startswith("abspath:")] == [f"abspath:{root}"]
    assert _inside(root, calls)


@pytest.mark.parametrize("key", ["include", "exclude"])
@pytest.mark.parametrize("value", ["docs/loop/x.md", "docs/loop", "docs/ping/x.md"])
def test_symlink_loop_refused_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, key: str, value: str):
    """
    [Unit] discovery: verifies a symlink self-loop or two-link cycle is refused after a bounded walk.

    Scenario:
        Given docs/loop -> loop and the cycle docs/ping -> pong, docs/pong -> ping
        When a literal through the loop is normalised as include or exclude
        Then "leaves the scan root through a symlink" is raised (hop limit), the walk made at most
            a few hundred calls, and every call is under the root.

    Boundaries:
        - Focus: threat model M15 (hop limit), T10 cost bound
        - Fixtures/params: tmp_path, monkeypatch, key, value
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - _MAX_SYMLINK_HOPS in path_boundaries and the None branch of _check_literal

    :param key: include or exclude.
    :param value: A literal through a loop.
    """
    root = _root(tmp_path)
    (root / "docs" / "loop").symlink_to("loop")
    (root / "docs" / "ping").symlink_to("pong")
    (root / "docs" / "pong").symlink_to("ping")
    selectors = {"include": None, "exclude": None, key: [value]}
    calls = _record(monkeypatch)

    with pytest.raises(ConfigError) as caught:
        normalize_invoker_selectors(root, **selectors)

    assert str(caught.value) == (
        f"{key} value {value}: leaves the scan root through a symlink; values are relative to the scan root"
    )
    assert 64 < len(calls) <= 4 * 64 + 16
    assert _inside(root, calls)


def test_config_literals_never_touch_filesystem(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] discovery: verifies configured literals are matched as strings, with no filesystem access of their own.

    Scenario:
        Given a Config whose include and exclude name missing paths, paths through escaping symlinks
            and an absolute outside path, plus docs/user
        When discover_with_stats walks the root, and scan() runs with that injected Config
            while normalize_invoker_selectors is replaced by a tripwire
        Then only docs/user/a.md is admitted, every call stays under the root, no call names a
            configured literal that the walk does not reach, and the normaliser is never invoked.

    Boundaries:
        - Focus: threat model T9 (accepted) and the merge gate "config values triggering filesystem access"
        - Fixtures/params: tmp_path, monkeypatch
        - Scope: discover_with_stats and engine.scan (config-only path)

    On failure, first check:
        - engine._apply_invoker_selection returns early when both keywords are None
    """

    root = _root(tmp_path)
    config = Config(
        include=("docs/user", "docs/missing/x.md", "docs/out/x.md", "docs/relout/x.md", "/etc/passwd"),
        exclude=(".git", "docs/nothere", "docs/out/y", "/etc"),
    )
    calls = _record(monkeypatch)

    found = discover_with_stats(root, config)

    assert [document.path for document in found.documents] == ["docs/user/a.md"]
    assert found.include_hits == (1, 0, 0, 0, 0)
    assert _inside(root, calls)
    missing = {os.fspath(root / "docs" / name) for name in ("missing", "nothere")}
    below = tuple(f"{os.fspath(root / 'docs' / name)}{os.sep}" for name in ("missing", "nothere", "out", "relout"))
    paths = [c.split(":", 1)[1] for c in calls]
    assert [p for p in paths if p in missing or p.startswith(below)] == []

    def tripwire(*args: object, **kwargs: object):
        """Fail when configured values reach the invoker normaliser.

        :param args: Ignored.
        :param kwargs: Ignored.
        :raises AssertionError: Always.
        """
        raise AssertionError("configured values reached normalize_invoker_selectors")

    monkeypatch.setattr(engine, "normalize_invoker_selectors", tripwire)

    assert [document.path for document in engine.scan(root, config=config).documents] == ["docs/user/a.md"]


def test_walk_oserror_becomes_config_error_with_relative_echo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] discovery: verifies an OSError from the containment walk (readlink) becomes a bounded ConfigError.

    Scenario:
        Given os.readlink raising PermissionError while the walk crosses docs/alias
        When docs/alias/a.md is normalised as an exclude
        Then the ConfigError says "cannot check it (Permission denied)" and holds no absolute path.

    Boundaries:
        - Focus: threat model M17 (the step-9 walk, not only the step-10 lstat)
        - Fixtures/params: tmp_path, monkeypatch
        - Scope: normalize_invoker_selectors

    On failure, first check:
        - The try block in _check_literal covers contained_path
    """
    root = _root(tmp_path)

    def denied(path, *args, **kwargs):
        """Raise a permission error.

        :param path: The path.
        :param args: Ignored.
        :param kwargs: Ignored.
        :raises PermissionError: Always.
        """
        raise PermissionError(13, "Permission denied", os.fspath(path))

    monkeypatch.setattr(os, "readlink", denied)

    with pytest.raises(ConfigError) as caught:
        normalize_invoker_selectors(root, None, ["docs/alias/a.md"])

    message = str(caught.value)
    assert message == (
        "exclude value docs/alias/a.md: cannot check it (Permission denied); values are relative to the scan root"
    )
    assert os.fspath(root) not in message


def test_cli_include_through_inroot_symlinked_dir_exits_2_without_following(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """
    [Unit] cli: verifies a literal include through an in-root directory symlink exits 2 without following it.

    Scenario:
        Given docs/alias -> user inside the root
        When ``docsentinel scan <root> --include docs/alias/a.md`` runs with filesystem calls recorded
        Then the exit code is 2, the first stderr line is the symlinked-path refusal, and no call
            was made on a path below docs/alias (the link is read, never traversed).

    Boundaries:
        - Focus: ADR 0006 owner point O6 as ruled by Task 02; threat model M15
        - Fixtures/params: tmp_path, monkeypatch, capsys
        - Scope: one in-process CLI call

    On failure, first check:
        - cli._validate_selectors and the M15 signal in _check_literal
    """

    root = _root(tmp_path)
    calls = _record(monkeypatch)

    code = cli.main(["scan", os.fspath(root), "--include", "docs/alias/a.md"])
    err = capsys.readouterr().err

    assert code == 2
    assert err.splitlines()[0] == (
        "Scan failed: include value docs/alias/a.md: symlinked paths are not inventoried; "
        "values are relative to the scan root"
    )
    through = os.fspath(root / "docs" / "alias") + os.sep
    assert [c for c in calls if c.split(":", 1)[1].startswith(through)] == []


def test_case_folding_lstat_simulated_zero_hit_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """
    [Unit] engine: verifies the case-mismatch path on any file system by simulating a case-folding lstat.

    Scenario:
        Given os.lstat patched to fold the component DOCS to docs (as default APFS or NTFS would)
        When scan() runs with include=["DOCS/user", "docs/archive"]
        Then DOCS/user passes the existence check, admits nothing (case-sensitive matching) and is
            reported by the zero-hit WARNING; docs/archive/old.md is inventoried.

    Boundaries:
        - Focus: threat model T8/M18; twin of the integration test that is skipped on case-sensitive
            temporary file systems
        - Fixtures/params: tmp_path, monkeypatch, caplog
        - Scope: library scan()

    On failure, first check:
        - A casefold added to matching, or the zero-hit loop over Discovery.include_hits
    """


    root = _root(tmp_path)
    original = os.lstat
    folded = os.fspath(root / "DOCS")

    def folding_lstat(path, *args, **kwargs) -> os.stat_result:
        """Fold the DOCS component of a path below the root to docs.

        :param path: The path.
        :param args: Passed through.
        :param kwargs: Passed through.
        :returns: The stat result of the folded path.
        """
        text = os.fspath(path)
        if text == folded or text.startswith(folded + os.sep):
            text = os.fspath(root / "docs") + text[len(folded) :]
        return original(text, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", folding_lstat)
    caplog.set_level(logging.WARNING, logger="docsentinel")

    result = scan(root, include=["DOCS/user", "docs/archive"])

    assert [document.path for document in result.documents] == ["docs/archive/old.md"]
    assert [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING] == [
        "include pattern DOCS/user matched no document"
    ]
