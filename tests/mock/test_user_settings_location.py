"""Mock tests: user settings location and permission gate (Milestone 0009 Story 03.0, Task 06 Steps 4 and 6).

The location resolver (``user_settings_path``) is driven with ``DOCSENTINEL_SETTINGS``,
``XDG_DATA_HOME`` and ``HOME`` patched, and ``Path.home()`` replaced where it must fail. The
permission gate (threat model R1-R7, T04-1, T04-2, T04-4) runs on real files, directories and
symbolic links in ``tmp_path``, with ``os.stat()``, ``os.lstat()``, ``os.fstat()`` and
``os.geteuid()`` wrapped so that another owner, a group/other write bit or a sticky bit can be
reported without ``chown`` or root (amendment A11). Every path, the fake home included, lies under
``tmp_path``; the real home and the real settings file are never touched. Threat model:
docs/security/threat-model-0009-user-settings-2026-11-17.md.
"""

from __future__ import annotations

import logging
import os
import stat
import traceback
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pytest

from docsentinel import config
from docsentinel.config import (
    USER_SETTINGS_ENV,
    Config,
    ConfigError,
    _tilde_path,
    _user_settings_link_directories,
    load_config,
    load_config_with_sources,
    user_settings_path,
)

pytestmark = pytest.mark.skipif(os.name != "posix", reason="the permission gate and symlinks are POSIX-only")

#: A uid that is neither the effective user nor root.
_OTHER_UID = 4242

#: The three fixed gate phrases (threat model R6).
_OWNER = "owned by another user"
_MODE = "writable by group or others (run chmod go-w on it)"
_DIRECTORY = "its directory is owned by another user or writable by others"


@dataclass
class FakeMetadata:
    """Overrides applied by the wrapped ``os.stat``/``os.lstat``/``os.fstat`` (owner and mode bits).

    :ivar stat: ``realpath -> (uid, permission bits)`` for ``os.stat``; ``None`` keeps a field.
    :ivar lstat: ``abspath -> (uid, permission bits)`` for ``os.lstat`` (the link itself).
    :ivar fstat: ``(uid, permission bits)`` for every ``os.fstat``, or ``None``.
    :ivar euid: The value ``os.geteuid()`` returns.
    :ivar opened: Descriptors returned by ``os.open``.
    :ivar fstat_calls: Descriptors passed to ``os.fstat``.
    """

    stat: dict[str, tuple[Optional[int], Optional[int]]] = field(default_factory=dict)
    lstat: dict[str, tuple[Optional[int], Optional[int]]] = field(default_factory=dict)
    fstat: Optional[tuple[Optional[int], Optional[int]]] = None
    euid: int = 0
    opened: list[int] = field(default_factory=list)
    fstat_calls: list[int] = field(default_factory=list)


def _patched(result: os.stat_result, override: Optional[tuple[Optional[int], Optional[int]]]) -> os.stat_result:
    """Return ``result`` with the owner and permission bits of ``override`` applied.

    :param result: The real stat result.
    :param override: ``(uid, permission bits)``; ``None`` entries keep the real field.
    :returns: A new ``os.stat_result``; the file type bits are always kept.
    """
    if override is None:
        return result
    uid, permission = override
    fields = list(result[:10])
    if permission is not None:
        fields[0] = stat.S_IFMT(result.st_mode) | permission
    if uid is not None:
        fields[4] = uid
    return os.stat_result(fields)


@pytest.fixture
def metadata(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeMetadata]:
    """Wrap ``os.stat``, ``os.lstat``, ``os.fstat``, ``os.open`` and ``os.geteuid`` with overrides.

    :param monkeypatch: Restores the real functions after the test.
    :returns: The overrides, initially empty, with ``euid`` the real effective uid.
    """
    fake = FakeMetadata(euid=os.geteuid())
    real_stat, real_lstat, real_fstat, real_open = os.stat, os.lstat, os.fstat, os.open

    def fake_stat(path: Any, *args: Any, **kwargs: Any) -> os.stat_result:
        """Return the real ``os.stat`` with the override for the path's real path."""
        result = real_stat(path, *args, **kwargs)
        if isinstance(path, int) or kwargs.get("follow_symlinks") is False:
            return result
        return _patched(result, fake.stat.get(os.path.realpath(os.fspath(path))))

    def fake_lstat(path: Any, *args: Any, **kwargs: Any) -> os.stat_result:
        """Return the real ``os.lstat`` with the override for the link path."""
        result = real_lstat(path, *args, **kwargs)
        return _patched(result, fake.lstat.get(os.path.abspath(os.fspath(path))))

    def fake_fstat(descriptor: int) -> os.stat_result:
        """Record the descriptor and return the real ``os.fstat`` with the fstat override."""
        fake.fstat_calls.append(descriptor)
        return _patched(real_fstat(descriptor), fake.fstat)

    def fake_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        """Record the descriptor the real ``os.open`` returns."""
        descriptor = real_open(path, flags, *args, **kwargs)
        fake.opened.append(descriptor)
        return descriptor

    monkeypatch.setattr(os, "stat", fake_stat)
    monkeypatch.setattr(os, "lstat", fake_lstat)
    monkeypatch.setattr(os, "fstat", fake_fstat)
    monkeypatch.setattr(os, "open", fake_open)
    monkeypatch.setattr(os, "geteuid", lambda: fake.euid)
    yield fake


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point HOME at an owner-only fake home in ``tmp_path`` and clear XDG_DATA_HOME.

    :param tmp_path: The test's temporary directory.
    :param monkeypatch: Restores the environment after the test.
    :returns: The fake home.
    """
    directory = _private_dir(tmp_path / "home")
    monkeypatch.setenv("HOME", str(directory))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    return directory


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """Return an empty scan root without a project configuration.

    :param tmp_path: The test's temporary directory.
    :returns: The scan root.
    """
    return _private_dir(tmp_path / "repo")


def _private_dir(path: Path) -> Path:
    """Create ``path`` (and parents) with mode ``0o700`` regardless of the umask.

    :param path: The directory.
    :returns: ``path``.
    """
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def _settings(directory: Path, text: str = '{"reference_scope": "strict"}', name: str = "settings.json") -> Path:
    """Write a settings file with mode ``0o600`` in an owner-only ``directory``.

    :param directory: The holding directory.
    :param text: The JSON text.
    :param name: The file name.
    :returns: The file path.
    """
    _private_dir(directory)
    path = directory / name
    path.write_text(text, encoding="utf-8")
    os.chmod(path, 0o600)
    return path


def _select(monkeypatch: pytest.MonkeyPatch, path: Path):
    """Select ``path`` through ``DOCSENTINEL_SETTINGS``.

    :param monkeypatch: Restores the variable after the test.
    :param path: The settings path.
    """
    monkeypatch.setenv(USER_SETTINGS_ENV, str(path))


def _refusal(root: Path) -> ConfigError:
    """Return the ``ConfigError`` that ``load_config(root)`` raises.

    :param root: The scan root.
    :returns: The raised error.
    """
    with pytest.raises(ConfigError) as caught:
        load_config(root)
    return caught.value


class _NonPosixOs:
    """A stand-in for the ``os`` module seen by ``docsentinel.config`` that reports ``os.name == "nt"``.

    Only the config module's view changes; pathlib and every other module keep the real
    ``os.name``. Every other attribute is the real (possibly test-wrapped) ``os`` attribute.
    """

    name = "nt"

    def __getattr__(self, attribute: str) -> Any:
        """Return the real ``os`` attribute of that name."""
        return getattr(os, attribute)


def _real(path: Path) -> str:
    """Return the real path of ``path`` as the overrides key it.

    :param path: A path.
    :returns: ``os.path.realpath(path)``.
    """
    return os.path.realpath(path)


# --- R2: the final target, decided on fstat of the opened descriptor --------------------------------


def test_gate_refuses_file_owned_by_other_user(
    home: Path, root: Path, monkeypatch: pytest.MonkeyPatch, metadata: FakeMetadata
):
    """
    [Unit] user settings gate U1/R2: a settings file owned by another user is refused.

    Scenario:
        Given a mode-0600 settings file whose descriptor fstat reports another uid
        When load_config runs
        Then ConfigError is "user settings ~/cfg/settings.json: owned by another user".

    Boundaries:
        - Focus: _check_user_settings_descriptor owner check
        - Fixtures/params: home, root, monkeypatch, metadata (fstat uid 4242)
        - Scope: real file in the fake home; os.fstat wrapped

    On failure, first check:
        - _owner_trusted and the check_descriptor hook of _read_config_once
    """
    _select(monkeypatch, _settings(home / "cfg"))
    metadata.fstat = (_OTHER_UID, 0o600)

    assert str(_refusal(root)) == f"user settings ~/cfg/settings.json: {_OWNER}"


def test_gate_refuses_group_writable_file(
    home: Path, root: Path, monkeypatch: pytest.MonkeyPatch, metadata: FakeMetadata
):
    """
    [Unit] user settings gate U1/R2: a group-writable settings file is refused.

    Scenario:
        Given an owner-owned settings file whose fstat reports mode 0620
        When load_config runs
        Then ConfigError names the chmod go-w fix.

    Boundaries:
        - Focus: S_IWGRP in _check_user_settings_descriptor
        - Fixtures/params: home, root, monkeypatch, metadata (fstat mode 0620)
        - Scope: real file in the fake home; os.fstat wrapped

    On failure, first check:
        - The S_IWGRP | S_IWOTH mask
    """
    _select(monkeypatch, _settings(home / "cfg"))
    metadata.fstat = (None, 0o620)

    assert str(_refusal(root)) == f"user settings ~/cfg/settings.json: {_MODE}"


def test_gate_refuses_world_writable_file(
    home: Path, root: Path, monkeypatch: pytest.MonkeyPatch, metadata: FakeMetadata
):
    """
    [Unit] user settings gate U1/R2: a world-writable settings file is refused.

    Scenario:
        Given an owner-owned settings file whose fstat reports mode 0602
        When load_config runs
        Then ConfigError names the chmod go-w fix.

    Boundaries:
        - Focus: S_IWOTH in _check_user_settings_descriptor
        - Fixtures/params: home, root, monkeypatch, metadata (fstat mode 0602)
        - Scope: real file in the fake home; os.fstat wrapped

    On failure, first check:
        - The S_IWGRP | S_IWOTH mask
    """
    _select(monkeypatch, _settings(home / "cfg"))
    metadata.fstat = (None, 0o602)

    assert str(_refusal(root)) == f"user settings ~/cfg/settings.json: {_MODE}"


def test_gate_accepts_owner_file_mode_0644(
    home: Path, root: Path, monkeypatch: pytest.MonkeyPatch, metadata: FakeMetadata
):
    """
    [Unit] user settings gate R2: an owner-owned mode-0644 file is accepted (read bits are not checked).

    Scenario:
        Given a settings file with the real mode 0644 in an owner-only directory
        When load_config_with_sources runs
        Then the file is loaded, its option applies, and the decision used the descriptor's fstat.

    Boundaries:
        - Focus: the accepting path of R2
        - Fixtures/params: home, root, monkeypatch, metadata (no override)
        - Scope: real file in the fake home

    On failure, first check:
        - That only write bits are tested, not read bits
    """
    path = _settings(home / "cfg")
    os.chmod(path, 0o644)
    _select(monkeypatch, path)

    loaded, sources = load_config_with_sources(root)

    assert loaded.reference_scope == "strict"
    assert (sources.user, sources.user_state, sources.user_options) == (path, "loaded", ("reference_scope",))
    assert metadata.fstat_calls == metadata.opened[-1:]


def test_gate_accepts_root_owned_file(home: Path, root: Path, monkeypatch: pytest.MonkeyPatch, metadata: FakeMetadata):
    """
    [Unit] user settings gate R4: a root-owned mode-0644 file is accepted for a non-root user.

    Scenario:
        Given a settings file whose fstat reports uid 0 and mode 0644, and a non-root euid
        When load_config runs
        Then the file is loaded.

    Boundaries:
        - Focus: uid 0 in _owner_trusted (Nix home-manager, admin-managed files)
        - Fixtures/params: home, root, monkeypatch, metadata (fstat uid 0)
        - Scope: real file in the fake home; os.fstat wrapped

    On failure, first check:
        - _owner_trusted accepts {geteuid(), 0}
    """
    _select(monkeypatch, _settings(home / "cfg"))
    metadata.fstat = (0, 0o644)

    assert load_config(root).reference_scope == "strict"


def test_gate_as_root_refuses_user_owned_file(
    home: Path, root: Path, monkeypatch: pytest.MonkeyPatch, metadata: FakeMetadata
):
    """
    [Unit] user settings gate R4: when running as root only root-owned objects pass.

    Scenario:
        Given euid 0, root-owned holding directories, and a settings file owned by uid 1000
        When load_config runs
        Then ConfigError "owned by another user" is raised; the same file reported as
            root-owned loads.

    Boundaries:
        - Focus: _owner_trusted with geteuid() == 0 (sudo with a preserved HOME)
        - Fixtures/params: home, root, monkeypatch, metadata (euid 0, dirs uid 0, fstat uid 1000)
        - Scope: real file in the fake home; os.stat/os.fstat/os.geteuid wrapped

    On failure, first check:
        - That _owner_trusted reads os.geteuid() at call time
    """
    path = _settings(home / "cfg")
    _select(monkeypatch, path)
    directories = _user_settings_link_directories(path)
    metadata.euid = 0
    metadata.stat.update(dict.fromkeys(directories, (0, None)))
    metadata.fstat = (1000, 0o600)

    assert str(_refusal(root)) == f"user settings ~/cfg/settings.json: {_OWNER}"
    metadata.fstat = (0, 0o600)
    assert load_config(root).reference_scope == "strict"


def test_gate_decision_uses_fstat_of_opened_descriptor(
    home: Path, root: Path, monkeypatch: pytest.MonkeyPatch, metadata: FakeMetadata
):
    """
    [Unit] user settings gate U2/R7: a safe os.stat cannot outvote an unsafe fstat of the read descriptor.

    Scenario:
        Given a settings file whose path os.stat reports as a safe 0600 file, while fstat of the
            opened descriptor reports world-writable (a swap after the pre-check)
        When load_config runs
        Then it is refused with the mode phrase, fstat ran on exactly the descriptor os.open
            returned, and the file was opened once.

    Boundaries:
        - Focus: the check_descriptor hook runs on os.fstat of the same descriptor (amendment A1)
        - Fixtures/params: home, root, monkeypatch, metadata
        - Scope: real file in the fake home; os.stat, os.fstat and os.open wrapped

    On failure, first check:
        - That the gate never decides on os.stat of the path
    """
    path = _settings(home / "cfg")
    _select(monkeypatch, path)
    metadata.stat[_real(path)] = (os.geteuid(), 0o600)
    metadata.fstat = (None, 0o666)

    assert str(_refusal(root)) == f"user settings ~/cfg/settings.json: {_MODE}"
    assert len(metadata.opened) == 1
    assert metadata.fstat_calls == metadata.opened


def test_gate_checks_symlink_final_target_not_link(
    home: Path, root: Path, monkeypatch: pytest.MonkeyPatch, metadata: FakeMetadata
):
    """
    [Unit] user settings gate R2: a symlinked settings file is judged by its final target.

    Scenario:
        Given ~/links/settings.json -> ~/targets/real.json (a dotfile-manager link) in owner-only
            directories, the link itself reported as another user's
        When load_config runs with the target's fstat safe, then with it world-writable
        Then the first loads and the second is refused with the mode phrase.

    Boundaries:
        - Focus: os.open follows the link; fstat is the target's (story edge case "symlinked user file")
        - Fixtures/params: home, root, monkeypatch, metadata
        - Scope: real symlink; os.lstat and os.fstat wrapped

    On failure, first check:
        - That no O_NOFOLLOW is used for the read, and the fstat hook sees the target
    """
    target = _settings(home / "targets", name="real.json")
    link = _private_dir(home / "links") / "settings.json"
    link.symlink_to(target)
    _select(monkeypatch, link)
    metadata.lstat[str(link)] = (_OTHER_UID, None)

    assert load_config(root).reference_scope == "strict"
    metadata.fstat = (None, 0o666)
    assert str(_refusal(root)) == f"user settings ~/links/settings.json: {_MODE}"


# --- R3: the holding directories -----------------------------------------------------------------


def _link_layout(home: Path) -> tuple[Path, Path, Path]:
    """Create ~/links/settings.json -> ~/targets/real.json and return (link, link dir, target dir).

    :param home: The fake home.
    :returns: The link path, the directory holding it and the directory holding the target.
    """
    target = _settings(home / "targets", name="real.json")
    link_dir = _private_dir(home / "links")
    link = link_dir / "settings.json"
    link.symlink_to(target)
    return link, link_dir, target.parent


@pytest.mark.parametrize("permission", [0o777, 0o770, 0o722], ids=["world", "group", "write_only_others"])
def test_gate_refuses_writable_dir_holding_symlink(
    home: Path, root: Path, monkeypatch: pytest.MonkeyPatch, metadata: FakeMetadata, permission: int
):
    """
    [Unit] user settings gate U1/R3: a writable, non-sticky directory holding the symlink is refused.

    Scenario:
        Given a settings symlink whose holding directory is reported group- or world-writable
            without the sticky bit, and a safe target
        When load_config runs
        Then ConfigError carries the directory phrase.

    Boundaries:
        - Focus: _check_user_settings_directories for the link's directory
        - Fixtures/params: home, root, monkeypatch, metadata, permission
        - Scope: real symlink; os.stat of the link directory wrapped

    On failure, first check:
        - That _user_settings_link_directories collects the link's directory
    """
    link, link_dir, _ = _link_layout(home)
    _select(monkeypatch, link)
    metadata.stat[_real(link_dir)] = (None, permission)

    assert str(_refusal(root)) == f"user settings ~/links/settings.json: {_DIRECTORY}"


def test_gate_refuses_writable_dir_holding_target(
    home: Path, root: Path, monkeypatch: pytest.MonkeyPatch, metadata: FakeMetadata
):
    """
    [Unit] user settings gate U1/R3: a writable directory holding the final target is refused.

    Scenario:
        Given a settings symlink in a safe directory pointing into a world-writable, non-sticky
            directory
        When load_config runs
        Then ConfigError carries the directory phrase.

    Boundaries:
        - Focus: the final target's directory is checked (one hop later)
        - Fixtures/params: home, root, monkeypatch, metadata
        - Scope: real symlink; os.stat of the target directory wrapped

    On failure, first check:
        - The final setdefault(dirname(current)) in _user_settings_link_directories
    """
    link, _, target_dir = _link_layout(home)
    _select(monkeypatch, link)
    metadata.stat[_real(target_dir)] = (None, 0o777)

    assert str(_refusal(root)) == f"user settings ~/links/settings.json: {_DIRECTORY}"


@pytest.mark.parametrize("owner", ["self", "root"])
def test_gate_accepts_sticky_world_writable_dir(
    home: Path, root: Path, monkeypatch: pytest.MonkeyPatch, metadata: FakeMetadata, owner: str
):
    """
    [Unit] user settings gate R3: a sticky world-writable directory (as /tmp) is accepted.

    Scenario:
        Given the user's own settings file directly in a directory reported mode 1777, owned by
            the user or by root
        When load_config runs
        Then the file is loaded.

    Boundaries:
        - Focus: the S_ISVTX exception (DOCSENTINEL_SETTINGS=/tmp/... in CI)
        - Fixtures/params: home, root, monkeypatch, metadata, owner
        - Scope: real file; os.stat of its directory wrapped

    On failure, first check:
        - The sticky-bit branch of _check_user_settings_directories
    """
    path = _settings(home / "shared")
    _select(monkeypatch, path)
    metadata.stat[_real(path.parent)] = (0 if owner == "root" else None, 0o1777)

    assert load_config(root).reference_scope == "strict"


def test_gate_refuses_dir_owned_by_other_user(
    home: Path, root: Path, monkeypatch: pytest.MonkeyPatch, metadata: FakeMetadata
):
    """
    [Unit] user settings gate U1/R3: a directory owned by another user is refused even at mode 0755.

    Scenario:
        Given the settings file's directory reported as owned by uid 4242 with mode 0755
        When load_config runs
        Then ConfigError carries the directory phrase.

    Boundaries:
        - Focus: _owner_trusted on directories
        - Fixtures/params: home, root, monkeypatch, metadata
        - Scope: real file; os.stat of its directory wrapped

    On failure, first check:
        - The owner test in _check_user_settings_directories
    """
    path = _settings(home / "cfg")
    _select(monkeypatch, path)
    metadata.stat[_real(path.parent)] = (_OTHER_UID, 0o755)

    assert str(_refusal(root)) == f"user settings ~/cfg/settings.json: {_DIRECTORY}"


def _file_chain(home: Path) -> tuple[Path, Path]:
    """Create ~/safe/l.json -> ../ww/mid -> ../clone/evil.json and return (settings path, ww).

    :param home: The fake home.
    :returns: The configured path and the intermediate directory.
    """
    _settings(home / "clone", name="evil.json")
    ww = _private_dir(home / "ww")
    (ww / "mid").symlink_to(Path("..") / "clone" / "evil.json")
    link = _private_dir(home / "safe") / "l.json"
    link.symlink_to(Path("..") / "ww" / "mid")
    return link, ww


def _directory_chain(home: Path) -> tuple[Path, Path]:
    """Create ~/safe/dlink -> ../ww/dmid -> ../clone and return (dlink/evil.json, ww).

    :param home: The fake home.
    :returns: The configured path and the intermediate directory.
    """
    _settings(home / "clone", name="evil.json")
    ww = _private_dir(home / "ww")
    (ww / "dmid").symlink_to(Path("..") / "clone", target_is_directory=True)
    dlink = _private_dir(home / "safe") / "dlink"
    dlink.symlink_to(Path("..") / "ww" / "dmid", target_is_directory=True)
    return dlink / "evil.json", ww


_CHAINS: dict[str, Callable[[Path], tuple[Path, Path]]] = {
    "file_chain": _file_chain,
    "directory_chain": _directory_chain,
}


@pytest.mark.parametrize("chain", sorted(_CHAINS))
def test_gate_refuses_chain_through_writable_dir(
    home: Path, root: Path, monkeypatch: pytest.MonkeyPatch, metadata: FakeMetadata, chain: str
):
    """
    [Unit] user settings gate T04-1: a link chain whose middle link sits in a writable directory is refused.

    Scenario:
        Given a file chain (safe/l.json -> ww/mid -> clone/evil.json) or a directory chain
            (safe/dlink -> ww/dmid -> clone), all owner-only
        When load_config runs, first unchanged, then with ww reported world-writable and not sticky
        Then the first loads (the layout itself is fine) and the second is refused with the
            directory phrase, although the first and last directories are safe.

    Boundaries:
        - Focus: every link-holding directory of the chain is checked (threat model T04-1)
        - Fixtures/params: home, root, monkeypatch, metadata, chain
        - Scope: real relative symlinks; os.stat of ww wrapped

    On failure, first check:
        - The component walk in _user_settings_link_directories
    """
    path, ww = _CHAINS[chain](home)
    _select(monkeypatch, path)

    assert load_config(root).reference_scope == "strict"
    assert _real(ww) in _user_settings_link_directories(path)
    metadata.stat[_real(ww)] = (None, 0o777)
    assert str(_refusal(root)).endswith(f": {_DIRECTORY}")


@pytest.mark.parametrize("chain", sorted(_CHAINS))
def test_gate_accepts_chain_through_sticky_root_dir(
    home: Path, root: Path, monkeypatch: pytest.MonkeyPatch, metadata: FakeMetadata, chain: str
):
    """
    [Unit] user settings gate T04-1: a chain through a root-owned sticky directory (as /nix/store) is accepted.

    Scenario:
        Given the file or directory chain with ww reported as root-owned, mode 1777, holding the
            user's own link
        When load_config runs
        Then the final target is loaded.

    Boundaries:
        - Focus: the sticky exception applies to intermediate directories too
        - Fixtures/params: home, root, monkeypatch, metadata, chain
        - Scope: real relative symlinks; os.stat of ww wrapped

    On failure, first check:
        - The S_ISVTX test and the link-owner list of the sticky branch
    """
    path, ww = _CHAINS[chain](home)
    _select(monkeypatch, path)
    metadata.stat[_real(ww)] = (0, 0o1777)

    assert load_config(root).reference_scope == "strict"


def _sticky_link(home: Path, kind: str) -> tuple[Path, Path, Path]:
    """Create a link in ~/sticky pointing to ~/clone (file or directory link).

    :param home: The fake home.
    :param kind: ``file`` (sticky/s.json -> ../clone/evil.json) or ``directory``
        (sticky/d -> ../clone, configured as sticky/d/evil.json).
    :returns: The configured path, the link and the sticky directory.
    """
    _settings(home / "clone", name="evil.json")
    sticky = _private_dir(home / "sticky")
    if kind == "file":
        link = sticky / "s.json"
        link.symlink_to(Path("..") / "clone" / "evil.json")
        return link, link, sticky
    link = sticky / "d"
    link.symlink_to(Path("..") / "clone", target_is_directory=True)
    return link / "evil.json", link, sticky


@pytest.mark.parametrize("kind", ["file", "directory"])
def test_gate_refuses_foreign_link_in_sticky_dir(
    home: Path, root: Path, monkeypatch: pytest.MonkeyPatch, metadata: FakeMetadata, kind: str
):
    """
    [Unit] user settings gate T04-4: a link planted by another user in a sticky directory is refused.

    Scenario:
        Given a sticky world-writable directory holding a file link or a directory link that
            lstat reports as owned by uid 4242, pointing at the user's own safe file
        When load_config runs
        Then ConfigError carries the directory phrase (the protected_symlinks rule).

    Boundaries:
        - Focus: link-owner check of the sticky branch (threat model T04-4)
        - Fixtures/params: home, root, monkeypatch, metadata, kind
        - Scope: real symlink; os.stat of the sticky directory and os.lstat of the link wrapped

    On failure, first check:
        - That link_owners records lstat().st_uid of each link
    """
    path, link, sticky = _sticky_link(home, kind)
    _select(monkeypatch, path)
    metadata.stat[_real(sticky)] = (None, 0o1777)
    metadata.lstat[str(link)] = (_OTHER_UID, None)

    assert str(_refusal(root)).endswith(f": {_DIRECTORY}")


@pytest.mark.parametrize("kind", ["file", "directory"])
def test_gate_accepts_own_link_in_sticky_dir(
    home: Path, root: Path, monkeypatch: pytest.MonkeyPatch, metadata: FakeMetadata, kind: str
):
    """
    [Unit] user settings gate T04-4: the user's own link in a sticky directory is accepted.

    Scenario:
        Given the same sticky layout with the link owned by the user, and separately by root
        When load_config runs
        Then the target is loaded both times.

    Boundaries:
        - Focus: the accepting side of the T04-4 rule
        - Fixtures/params: home, root, monkeypatch, metadata, kind
        - Scope: real symlink; os.stat of the sticky directory wrapped

    On failure, first check:
        - _owner_trusted applied to link owners
    """
    path, link, sticky = _sticky_link(home, kind)
    _select(monkeypatch, path)
    metadata.stat[_real(sticky)] = (None, 0o1777)

    assert load_config(root).reference_scope == "strict"
    metadata.lstat[str(link)] = (0, None)
    assert load_config(root).reference_scope == "strict"


def _link_chain(directory: Path, count: int) -> Path:
    """Create ``count`` links l0 -> l1 -> ... -> real.json in ``directory`` and return l0.

    :param directory: An owner-only directory.
    :param count: The number of symbolic links.
    :returns: The first link.
    """
    _settings(directory, name="real.json")
    for index in range(count):
        target = "real.json" if index == count - 1 else f"l{index + 1}"
        (directory / f"l{index}").symlink_to(target)
    return directory / "l0"


def test_gate_too_many_symbolic_links(home: Path, root: Path, monkeypatch: pytest.MonkeyPatch, metadata: FakeMetadata):
    """
    [Unit] user settings gate T04-1: more than 40 links is "too many symbolic links".

    Scenario:
        Given chains of exactly 40 and of 41 symbolic links ending at a safe file
        When the R3 walker resolves them, and load_config runs on the 41-link chain with the
            kernel's own (lower) loop limit bypassed by os.stat reporting a regular file
        Then 40 links are walked, 41 raise "too many symbolic links", and load_config reports
            it behind the user prefix.

    Boundaries:
        - Focus: _MAX_SYMLINK_HOPS boundary in _user_settings_link_directories
        - Fixtures/params: home, root, monkeypatch, metadata
        - Scope: real relative symlinks; os.stat of the 41-link path wrapped to look regular

    On failure, first check:
        - The hops counter compares > _MAX_SYMLINK_HOPS
    """
    forty = _link_chain(_private_dir(home / "forty"), 40)
    forty_one = _link_chain(_private_dir(home / "forty_one"), 41)

    assert list(_user_settings_link_directories(forty)) == [_real(forty.parent)]
    with pytest.raises(ConfigError) as walked:
        _user_settings_link_directories(forty_one)
    assert str(walked.value) == "too many symbolic links"

    real_stat = os.stat
    regular = real_stat(forty_one.parent / "real.json")

    def stat_regular(path: Any, *args: Any, **kwargs: Any) -> os.stat_result:
        """Report the 41-link path as the regular file it ends at; delegate otherwise."""
        if not isinstance(path, int) and os.fspath(path) == str(forty_one):
            return regular
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", stat_regular)
    _select(monkeypatch, forty_one)
    assert str(_refusal(root)) == "user settings ~/forty_one/l0: too many symbolic links"


def test_gate_skipped_on_non_posix(
    home: Path,
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    metadata: FakeMetadata,
    caplog: pytest.LogCaptureFixture,
):
    """
    [Unit] user settings gate U14/R1: off POSIX the owner and mode checks are skipped with one DEBUG line.

    Scenario:
        Given os.name reported as "nt", a directory reported world-writable, a file fstat
            reporting another owner and mode 0666, and os.geteuid unavailable
        When load_config runs
        Then the file is loaded (regular-file and parse checks still apply) and the DEBUG
            line "user settings: permission check skipped (non-POSIX)" is logged once.

    Boundaries:
        - Focus: the os.name gate in _read_user_options
        - Fixtures/params: home, root, monkeypatch, metadata, caplog
        - Scope: the config module's os replaced by a proxy whose name is "nt"

    On failure, first check:
        - That _check_user_settings_directories and the descriptor hook are both skipped
    """
    path = _settings(home / "cfg")
    _select(monkeypatch, path)
    metadata.stat[_real(path.parent)] = (_OTHER_UID, 0o777)
    metadata.fstat = (_OTHER_UID, 0o666)

    def no_geteuid() -> int:
        """Fail like a platform without os.geteuid."""
        raise AssertionError("os.geteuid must not be called off POSIX")

    monkeypatch.setattr(os, "geteuid", no_geteuid)
    caplog.set_level(logging.DEBUG, logger="docsentinel.config")
    monkeypatch.setattr(config, "os", _NonPosixOs())

    loaded = load_config(root)

    assert loaded.reference_scope == "strict"
    skipped = [record for record in caplog.records if "permission check skipped" in record.getMessage()]
    assert [record.getMessage() for record in skipped] == ["user settings: permission check skipped (non-POSIX)"]
    assert skipped[0].levelno == logging.DEBUG


@pytest.mark.parametrize(
    ("violation", "phrase"),
    [("file_owner", _OWNER), ("file_mode", _MODE), ("link_dir", _DIRECTORY), ("target_dir", _DIRECTORY)],
)
def test_gate_messages_fixed_phrases_no_uid_no_target(
    home: Path, root: Path, monkeypatch: pytest.MonkeyPatch, metadata: FakeMetadata, violation: str, phrase: str
):
    """
    [Unit] user settings gate U1/R6: each refusal is a fixed phrase with no uid, mode or link target.

    Scenario:
        Given a symlinked settings file whose target name carries a sentinel, and one violation
            (foreign file owner, file mode 0666, writable link directory, writable target directory)
        When load_config runs
        Then the message is exactly "user settings ~/links/settings.json: <phrase>" and carries no
            uid, no mode digits and nothing of the target path.

    Boundaries:
        - Focus: the R6 message constants
        - Fixtures/params: home, root, monkeypatch, metadata, violation, phrase
        - Scope: real symlink; os.stat/os.fstat wrapped

    On failure, first check:
        - _GATE_* constants and that no f-string adds status fields
    """
    target = _settings(home / "TARGET_7c1e", name="TARGET_7c1e.json")
    link_dir = _private_dir(home / "links")
    link = link_dir / "settings.json"
    link.symlink_to(target)
    _select(monkeypatch, link)
    if violation == "file_owner":
        metadata.fstat = (_OTHER_UID, 0o600)
    elif violation == "file_mode":
        metadata.fstat = (None, 0o666)
    elif violation == "link_dir":
        metadata.stat[_real(link_dir)] = (_OTHER_UID, 0o777)
    else:
        metadata.stat[_real(target.parent)] = (_OTHER_UID, 0o777)

    message = str(_refusal(root))

    assert message == f"user settings ~/links/settings.json: {phrase}"
    for leaked in (str(_OTHER_UID), str(os.geteuid()), "666", "777", "0o", "TARGET_7c1e", str(home)):
        assert leaked not in message


# --- T04-2: no exception chain carries an absolute path ----------------------------------------------


def _scenario_directory(home: Path, metadata: FakeMetadata) -> Path:
    """Settings file in a world-writable directory; return the path to select."""
    path = _settings(home / "cfg")
    metadata.stat[_real(path.parent)] = (None, 0o777)
    return path


def _scenario_owner(home: Path, metadata: FakeMetadata) -> Path:
    """Settings file owned by another user; return the path to select."""
    metadata.fstat = (_OTHER_UID, 0o600)
    return _settings(home / "cfg")


def _scenario_mode(home: Path, metadata: FakeMetadata) -> Path:
    """World-writable settings file; return the path to select."""
    metadata.fstat = (None, 0o666)
    return _settings(home / "cfg")


def _scenario_dangling(home: Path, metadata: FakeMetadata) -> Path:
    """Dangling settings symlink; return the path to select."""
    link = _private_dir(home / "cfg") / "settings.json"
    link.symlink_to(home / "cfg" / "absent.json")
    return link


def _scenario_absent(home: Path, metadata: FakeMetadata) -> Path:
    """Absent invoker-named file; return the path to select."""
    return _private_dir(home / "cfg") / "absent.json"


def _scenario_refused_key(home: Path, metadata: FakeMetadata) -> Path:
    """C6 key in the file; return the path to select."""
    return _settings(home / "cfg", '{"baseline": "b.json"}')


def _scenario_parse(home: Path, metadata: FakeMetadata) -> Path:
    """Invalid UTF-8 in the file; return the path to select."""
    path = _settings(home / "cfg")
    path.write_bytes(b'{"profile": "\xff"}')
    return path


def _scenario_directory_file(home: Path, metadata: FakeMetadata) -> Path:
    """A directory where the file should be; return the path to select."""
    return _private_dir(home / "cfg" / "settings.json")


def _scenario_loop(home: Path, metadata: FakeMetadata) -> Path:
    """A two-link loop; return the path to select."""
    directory = _private_dir(home / "cfg")
    (directory / "a").symlink_to("b")
    (directory / "b").symlink_to("a")
    return directory / "a"


_SCENARIOS: dict[str, Callable[[Path, FakeMetadata], Path]] = {
    "directory": _scenario_directory,
    "owner": _scenario_owner,
    "mode": _scenario_mode,
    "dangling": _scenario_dangling,
    "absent": _scenario_absent,
    "refused_key": _scenario_refused_key,
    "parse": _scenario_parse,
    "directory_file": _scenario_directory_file,
    "loop": _scenario_loop,
}


@pytest.mark.parametrize("scenario", sorted(_SCENARIOS))
def test_user_settings_error_cause_has_no_absolute_path(
    home: Path, root: Path, monkeypatch: pytest.MonkeyPatch, metadata: FakeMetadata, scenario: str
):
    """
    [Unit] user settings T04-2: every user-layer ConfigError is raised from None, so no path leaks by chaining.

    Scenario:
        Given a settings file under the fake home failing the directory gate, the owner or mode
            check, as a dangling link, absent, a C6 key, invalid UTF-8, a directory, or a link loop
        When load_config raises
        Then __cause__ is None, __suppress_context__ is True, the message uses the tilde form,
            and the fully formatted traceback never contains the absolute home path.

    Boundaries:
        - Focus: "from None" in _load_user_layer and the gate helpers (threat model T04-2)
        - Fixtures/params: home, root, monkeypatch, metadata, scenario
        - Scope: traceback.format_exception of the raised error

    On failure, first check:
        - A "raise ... from exc" added to the user layer
    """
    path = _SCENARIOS[scenario](home, metadata)
    _select(monkeypatch, path)

    error = _refusal(root)

    assert error.__cause__ is None
    assert error.__suppress_context__ is True
    assert str(error).startswith("user settings ~/cfg/")
    formatted = "".join(traceback.format_exception(error))
    assert str(home) not in formatted
    assert _real(home) not in formatted


# --- Location: DOCSENTINEL_SETTINGS, XDG_DATA_HOME, HOME (U3, U7, U11, U12, U13) ---------------------


@pytest.mark.parametrize(
    ("value", "expected_state"),
    [("off", "off"), ("ABSOLUTE", "env"), ("", "default")],
    ids=["off", "absolute", "empty"],
)
def test_settings_env_off_absolute_and_empty(
    tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch, value: str, expected_state: str
):
    """
    [Unit] user settings location S4: DOCSENTINEL_SETTINGS off, absolute and empty.

    Scenario:
        Given DOCSENTINEL_SETTINGS set to "off", an absolute path, or the empty string
        When user_settings_path resolves the location
        Then off gives (None, "off"), an absolute path gives (that path, "env") and an empty
            value counts as unset (the default under the fake home).

    Boundaries:
        - Focus: the override branch of user_settings_path
        - Fixtures/params: tmp_path, home, monkeypatch, value, expected_state
        - Scope: resolver only; no filesystem access

    On failure, first check:
        - The empty-string check before the absolute-path test
    """
    absolute = tmp_path / "custom" / "settings.json"
    monkeypatch.setenv(USER_SETTINGS_ENV, str(absolute) if value == "ABSOLUTE" else value)

    path, state = user_settings_path()

    assert state == expected_state
    expected_path = {
        "off": None,
        "env": absolute,
        "default": home / ".local" / "share" / "docsentinel" / "settings.json",
    }[expected_state]
    assert path == expected_path


@pytest.mark.parametrize(
    "value",
    ["relative/SECRET_ab12.json", "./SECRET_ab12.json", "SECRET_ab12", "/abs/\x1bSECRET_ab12", "/abs/‮SECRET_ab12"],
    ids=["relative", "dot_relative", "bare_name", "escape", "bidi"],
)
def test_relative_settings_env_is_config_error_value_not_echoed(
    root: Path, home: Path, monkeypatch: pytest.MonkeyPatch, value: str
):
    """
    [Unit] user settings location U3: a relative or control-bearing DOCSENTINEL_SETTINGS is refused unechoed.

    Scenario:
        Given DOCSENTINEL_SETTINGS relative, a bare name, or absolute with an ESC or a bidi control
        When user_settings_path and load_config run, with os.stat/os.lstat/os.open/os.path.lexists spied
        Then both raise the fixed message, which never contains the value, and no filesystem
            call touched the value.

    Boundaries:
        - Focus: the absolute/plain-text check in user_settings_path (threat model A4)
        - Fixtures/params: root, home, monkeypatch, value
        - Scope: resolver and loader; spies delegate to the real calls

    On failure, first check:
        - _is_plain_path_text and os.path.isabs on the override
    """
    monkeypatch.setenv(USER_SETTINGS_ENV, value)
    touched: list[str] = []
    for name in ("stat", "lstat", "open"):
        real = getattr(os, name)

        def spy(path: Any, *args: Any, _real_call: Callable[..., Any] = real, **kwargs: Any) -> Any:
            """Record a call naming the sentinel, then delegate."""
            if not isinstance(path, int) and "SECRET_ab12" in os.fspath(path):
                touched.append(os.fspath(path))
            return _real_call(path, *args, **kwargs)

        monkeypatch.setattr(os, name, spy)
    real_lexists = os.path.lexists

    def spy_lexists(path: Any) -> bool:
        """Record a call naming the sentinel, then delegate."""
        if "SECRET_ab12" in os.fspath(path):
            touched.append(os.fspath(path))
        return real_lexists(path)

    monkeypatch.setattr(os.path, "lexists", spy_lexists)
    expected = f'{USER_SETTINGS_ENV} must be an absolute path or "off"'

    with pytest.raises(ConfigError) as resolved:
        user_settings_path()
    error = _refusal(root)

    assert str(resolved.value) == expected
    assert str(error) == expected
    assert "SECRET_ab12" not in str(error)
    assert touched == []


def test_xdg_data_home_absolute_is_used(tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] user settings location S3: an absolute XDG_DATA_HOME holds the default file.

    Scenario:
        Given DOCSENTINEL_SETTINGS unset and XDG_DATA_HOME an absolute directory
        When user_settings_path resolves the location
        Then it is XDG_DATA_HOME/docsentinel/settings.json with state "default".

    Boundaries:
        - Focus: the XDG branch of user_settings_path
        - Fixtures/params: tmp_path, home, monkeypatch
        - Scope: resolver only

    On failure, first check:
        - _USER_SETTINGS_RELATIVE
    """
    monkeypatch.delenv(USER_SETTINGS_ENV)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))

    assert user_settings_path() == (tmp_path / "xdg" / "docsentinel" / "settings.json", "default")


@pytest.mark.parametrize("xdg", ["", "relative/data", "./data"], ids=["empty", "relative", "dot_relative"])
def test_empty_xdg_and_relative_xdg_fall_back_to_home(home: Path, monkeypatch: pytest.MonkeyPatch, xdg: str):
    """
    [Unit] user settings location U3: an empty or relative XDG_DATA_HOME falls back to the home.

    Scenario:
        Given DOCSENTINEL_SETTINGS unset and XDG_DATA_HOME empty or relative
        When user_settings_path resolves the location
        Then it is ~/.local/share/docsentinel/settings.json under the fake home, never a
            current-directory path.

    Boundaries:
        - Focus: os.path.isabs on XDG_DATA_HOME
        - Fixtures/params: home, monkeypatch, xdg
        - Scope: resolver only

    On failure, first check:
        - The XDG condition in user_settings_path
    """
    monkeypatch.delenv(USER_SETTINGS_ENV)
    monkeypatch.setenv("XDG_DATA_HOME", xdg)

    path, state = user_settings_path()

    assert (path, state) == (home / ".local" / "share" / "docsentinel" / "settings.json", "default")
    assert path is not None and path.is_absolute()


@pytest.mark.parametrize("xdg", [None, "/abs/\x1bdata"], ids=["unset", "control"])
def test_xdg_unset_or_control_falls_back_to_home(home: Path, monkeypatch: pytest.MonkeyPatch, xdg: Optional[str]):
    """
    [Unit] user settings location S3: an unset or control-bearing XDG_DATA_HOME falls back to the home.

    Scenario:
        Given DOCSENTINEL_SETTINGS unset and XDG_DATA_HOME unset, or absolute with an ESC
        When user_settings_path resolves the location
        Then it is the file under ~/.local/share of the fake home.

    Boundaries:
        - Focus: _is_plain_path_text on XDG_DATA_HOME
        - Fixtures/params: home, monkeypatch, xdg
        - Scope: resolver only

    On failure, first check:
        - The XDG condition in user_settings_path
    """
    monkeypatch.delenv(USER_SETTINGS_ENV)
    if xdg is None:
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    else:
        monkeypatch.setenv("XDG_DATA_HOME", xdg)

    assert user_settings_path() == (home / ".local" / "share" / "docsentinel" / "settings.json", "default")


@pytest.mark.parametrize(
    "error", [RuntimeError("no home"), KeyError("HOME"), OSError("pwd")], ids=lambda error: type(error).__name__
)
def test_path_home_raising_is_no_home(root: Path, monkeypatch: pytest.MonkeyPatch, error: Exception):
    """
    [Unit] user settings location: Path.home() raising gives state no-home and the default Config.

    Scenario:
        Given DOCSENTINEL_SETTINGS and XDG_DATA_HOME unset and Path.home() raising
        When user_settings_path and load_config_with_sources run
        Then the location is (None, "no-home") and loading succeeds with the defaults.

    Boundaries:
        - Focus: _home_directory exception handling
        - Fixtures/params: root, monkeypatch, error
        - Scope: Path.home patched

    On failure, first check:
        - The exception tuple in _home_directory
    """
    monkeypatch.delenv(USER_SETTINGS_ENV)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    def broken_home() -> Path:
        """Raise like a platform without a home directory."""
        raise error

    monkeypatch.setattr(Path, "home", staticmethod(broken_home))

    assert user_settings_path() == (None, "no-home")
    loaded, sources = load_config_with_sources(root)
    assert loaded == Config()
    assert (sources.user, sources.user_state) == (None, "no-home")


@pytest.mark.parametrize(
    "home_value", [".", "rel/dir", "", "/", "//"], ids=["dot", "relative", "empty", "root", "double_root"]
)
def test_relative_home_is_no_home(root: Path, monkeypatch: pytest.MonkeyPatch, home_value: str):
    """
    [Unit] user settings location U3: a relative, empty or filesystem-root HOME is no-home, with no file access.

    Scenario:
        Given DOCSENTINEL_SETTINGS and XDG_DATA_HOME unset and HOME relative, empty or "/"
        When user_settings_path and load_config_with_sources run with os.stat/os.lstat/os.open
            and os.path.lexists spied
        Then the state is no-home and no call touched a settings path.

    Boundaries:
        - Focus: _home_directory's absolute and root checks (threat model A4)
        - Fixtures/params: root, monkeypatch, home_value
        - Scope: HOME patched; spies delegate

    On failure, first check:
        - home.is_absolute() and home == Path(home.anchor) in _home_directory
    """
    monkeypatch.delenv(USER_SETTINGS_ENV)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", home_value)
    touched: list[str] = []
    for name in ("stat", "lstat", "open"):
        real = getattr(os, name)

        def spy(path: Any, *args: Any, _real_call: Callable[..., Any] = real, **kwargs: Any) -> Any:
            """Record a call on a settings-like path, then delegate."""
            if not isinstance(path, int) and ("settings.json" in os.fspath(path) or ".local" in os.fspath(path)):
                touched.append(os.fspath(path))
            return _real_call(path, *args, **kwargs)

        monkeypatch.setattr(os, name, spy)

    assert user_settings_path() == (None, "no-home")
    _, sources = load_config_with_sources(root)
    assert sources.user_state == "no-home"
    assert touched == []


@pytest.mark.parametrize("blocker", ["absent", "parent_is_file"])
def test_default_location_absent_is_missing(
    tmp_path: Path, root: Path, home: Path, monkeypatch: pytest.MonkeyPatch, blocker: str
):
    """
    [Unit] user settings location U7: an absent default-location file is skipped as missing.

    Scenario:
        Given DOCSENTINEL_SETTINGS unset, XDG_DATA_HOME empty, and no file there (or a regular
            file where the docsentinel directory should be, so stat raises NotADirectoryError)
        When load_config_with_sources runs
        Then the state is missing, no user path is reported, and the Config is the default.

    Boundaries:
        - Focus: _user_settings_exist FileNotFoundError/NotADirectoryError branch
        - Fixtures/params: tmp_path, root, home, monkeypatch, blocker
        - Scope: real (empty) XDG directory in tmp_path

    On failure, first check:
        - The lexists test that separates absent from dangling
    """
    data_home = _private_dir(tmp_path / "xdg")
    if blocker == "parent_is_file":
        (data_home / "docsentinel").write_text("", encoding="utf-8")
    monkeypatch.delenv(USER_SETTINGS_ENV)
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))

    loaded, sources = load_config_with_sources(root)

    assert loaded == Config()
    assert (sources.user, sources.user_state, sources.user_options) == (None, "missing", ())


def test_default_location_dangling_symlink_is_error(root: Path, home: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] user settings location U7: a dangling default-location symlink is an error, never missing.

    Scenario:
        Given the default location ~/.local/share/docsentinel/settings.json as a dangling symlink
        When load_config runs
        Then ConfigError "user settings ~/.local/share/docsentinel/settings.json: Cannot read
            JSON config: not readable" is raised.

    Boundaries:
        - Focus: os.path.lexists in _user_settings_exist (amendment A5)
        - Fixtures/params: root, home, monkeypatch
        - Scope: real dangling symlink under the fake home

    On failure, first check:
        - That a FileNotFoundError with lexists true raises
    """
    directory = _private_dir(home / ".local" / "share" / "docsentinel")
    (directory / "settings.json").symlink_to(directory / "gone.json")
    monkeypatch.delenv(USER_SETTINGS_ENV)

    assert str(_refusal(root)) == (
        "user settings ~/.local/share/docsentinel/settings.json: Cannot read JSON config: not readable"
    )


@pytest.mark.parametrize(
    "error",
    [PermissionError(13, "Permission denied"), OSError(62, "Too many levels of symbolic links")],
    ids=lambda error: type(error).__name__,
)
def test_default_location_permission_denied_is_error(
    root: Path, home: Path, monkeypatch: pytest.MonkeyPatch, error: OSError
):
    """
    [Unit] user settings location U7: a stat failure other than absence fails closed.

    Scenario:
        Given a default-location file whose os.stat raises PermissionError or a loop OSError
        When load_config runs
        Then ConfigError "...: Cannot read JSON config: not readable" is raised; the user's
            settings never silently disappear.

    Boundaries:
        - Focus: the generic OSError branch of _user_settings_exist
        - Fixtures/params: root, home, monkeypatch, error
        - Scope: os.stat patched for the settings path only

    On failure, first check:
        - The except (OSError, ValueError) clause of _user_settings_exist
    """
    path = _settings(home / ".local" / "share" / "docsentinel")
    monkeypatch.delenv(USER_SETTINGS_ENV)
    real_stat = os.stat

    def failing_stat(target: Any, *args: Any, **kwargs: Any) -> os.stat_result:
        """Raise for the settings path; delegate otherwise."""
        if not isinstance(target, int) and os.fspath(target) == str(path):
            raise error
        return real_stat(target, *args, **kwargs)

    monkeypatch.setattr(os, "stat", failing_stat)

    assert str(_refusal(root)) == (
        "user settings ~/.local/share/docsentinel/settings.json: Cannot read JSON config: not readable"
    )


def test_env_path_absent_is_error(root: Path, home: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] user settings location U7/S4: an absent file named by DOCSENTINEL_SETTINGS is an error.

    Scenario:
        Given DOCSENTINEL_SETTINGS naming an absent file under the fake home
        When load_config runs
        Then ConfigError "user settings ~/absent.json: Cannot read JSON config: not readable".

    Boundaries:
        - Focus: required=True for state "env" in _user_settings_exist
        - Fixtures/params: root, home, monkeypatch
        - Scope: resolver and loader

    On failure, first check:
        - The required flag passed from _load_user_layer
    """
    _select(monkeypatch, home / "absent.json")

    assert str(_refusal(root)) == "user settings ~/absent.json: Cannot read JSON config: not readable"


def test_tilde_form_for_home_and_its_realpath(tmp_path: Path, root: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] user settings location U11: the home is shown as ~ whether spelled as HOME or as its real path.

    Scenario:
        Given HOME as a symlink to a real home directory
        When _tilde_path renders paths under the link, under the real path, the home itself, a
            sibling sharing the prefix, and a load error for a file reached through the real path
        Then both spellings become "~/...", the home is "~", the sibling stays as given, and the
            error message holds neither absolute spelling.

    Boundaries:
        - Focus: _tilde_path matching Path.home() and its realpath (amendment A7)
        - Fixtures/params: tmp_path, root, monkeypatch
        - Scope: real symlinked home in tmp_path

    On failure, first check:
        - The dict.fromkeys((home, realpath(home))) loop in _tilde_path
    """
    real_home = _private_dir(tmp_path / "real_home")
    link_home = tmp_path / "link_home"
    link_home.symlink_to(real_home, target_is_directory=True)
    monkeypatch.setenv("HOME", str(link_home))
    sibling = Path(str(real_home) + "x") / "settings.json"

    assert _tilde_path(link_home / "a" / "settings.json") == "~/a/settings.json"
    assert _tilde_path(real_home / "a" / "settings.json") == "~/a/settings.json"
    assert _tilde_path(link_home) == "~"
    assert _tilde_path(sibling) == str(sibling)
    _select(monkeypatch, real_home / "absent.json")
    message = str(_refusal(root))
    assert message == "user settings ~/absent.json: Cannot read JSON config: not readable"
    assert str(real_home) not in message and str(link_home) not in message


def test_user_settings_false_never_reads_env(root: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] user settings location U13: user_settings=False never reads the environment.

    Scenario:
        Given DOCSENTINEL_SETTINGS holding relative garbage, and user_settings_path replaced by
            a function that fails the test
        When load_config and load_config_with_sources run with user_settings=False
        Then both succeed with the default Config and state "off"; with the keyword left at
            True the same garbage is a ConfigError.

    Boundaries:
        - Focus: the early return of _load_user_layer
        - Fixtures/params: root, monkeypatch
        - Scope: config.user_settings_path patched

    On failure, first check:
        - That _load_user_layer checks the keyword before calling user_settings_path
    """
    monkeypatch.setenv(USER_SETTINGS_ENV, "garbage/relative.json")
    real_resolver = config.user_settings_path

    def forbidden() -> tuple[Optional[Path], str]:
        """Fail if the environment resolver runs."""
        raise AssertionError("user_settings_path must not run when user settings are off")

    monkeypatch.setattr(config, "user_settings_path", forbidden)

    assert load_config(root, user_settings=False) == Config()
    _, sources = load_config_with_sources(root, user_settings=False)
    assert sources.user_state == "off"
    monkeypatch.setattr(config, "user_settings_path", real_resolver)
    with pytest.raises(ConfigError):
        load_config(root)


def test_debug_log_names_options_not_values(
    home: Path, root: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """
    [Unit] user settings logging: the DEBUG line names the options in tilde form, never their values.

    Scenario:
        Given a loaded user file setting ignore to a sentinel rule code and max_grade_level 13.37
        When load_config runs with DEBUG logging captured
        Then one record reads "user settings ~/cfg/settings.json: loaded, options set:
            ignore, max_grade_level", and no record holds a value or the absolute home.

    Boundaries:
        - Focus: logger.debug in _load_user_layer (story logging table)
        - Fixtures/params: home, root, monkeypatch, caplog
        - Scope: docsentinel.config logger

    On failure, first check:
        - That only sorted option names are logged
    """
    _select(monkeypatch, _settings(home / "cfg", '{"ignore": ["DS999"], "max_grade_level": 13.37}'))
    caplog.set_level(logging.DEBUG, logger="docsentinel.config")

    load_config(root)

    messages = [record.getMessage() for record in caplog.records]
    assert "user settings ~/cfg/settings.json: loaded, options set: ignore, max_grade_level" in messages
    assert not any("DS999" in text or "13.37" in text or str(home) in text for text in messages)


# --- U12 guards: the autouse isolation in tests/conftest.py ---------------------------------------


def test_isolation_settings_off(_isolated_user_settings: Path):
    """
    [Unit] user settings isolation U12: the autouse fixture turns user settings off for every test.

    Scenario:
        Given no change to the environment made by this test
        When user_settings_path resolves the location
        Then it reports (None, "off") and XDG_DATA_HOME is the fixture's empty temporary directory.

    Boundaries:
        - Focus: tests/conftest.py _isolated_user_settings (threat model M16)
        - Fixtures/params: _isolated_user_settings (the temporary data home)
        - Scope: environment and resolver only

    On failure, first check:
        - That the autouse fixture still sets DOCSENTINEL_SETTINGS=off
    """
    assert os.environ[USER_SETTINGS_ENV] == "off"
    assert user_settings_path() == (None, "off")
    assert os.environ["XDG_DATA_HOME"] == str(_isolated_user_settings)
    assert list(_isolated_user_settings.iterdir()) == []


def test_isolation_default_location_is_temporary(monkeypatch: pytest.MonkeyPatch, _isolated_user_settings: Path):
    """
    [Unit] user settings isolation U12: without DOCSENTINEL_SETTINGS the default lies in the temporary XDG dir.

    Scenario:
        Given the autouse isolation with DOCSENTINEL_SETTINGS removed
        When user_settings_path resolves the default location
        Then it lies under the fixture's temporary XDG_DATA_HOME, not under the real home, and
            loading from there finds nothing (state missing).

    Boundaries:
        - Focus: the second isolation layer (XDG_DATA_HOME) of tests/conftest.py
        - Fixtures/params: monkeypatch, _isolated_user_settings
        - Scope: resolver and loader over an empty scan root

    On failure, first check:
        - That the autouse fixture points XDG_DATA_HOME at tmp_path_factory
    """
    monkeypatch.delenv(USER_SETTINGS_ENV)
    real_home = Path(os.path.expanduser("~"))

    path, state = user_settings_path()

    assert state == "default"
    assert path == _isolated_user_settings / "docsentinel" / "settings.json"
    assert not path.is_relative_to(real_home)
    _, sources = load_config_with_sources(_isolated_user_settings)
    assert sources.user_state == "missing"
