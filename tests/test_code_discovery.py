from pathlib import Path

import pytest

from docsentinel.code_discovery import discover_python
from docsentinel.config import Config


def _symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlinks unavailable: {error}")


def test_discovers_py_files_under_default_src(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "src" / "pkg"
    pkg_dir.mkdir(parents=True)
    file_b = pkg_dir / "b.py"
    file_a = pkg_dir / "a.py"
    file_b.write_text("b = 2\n", encoding="utf-8")
    file_a.write_text("a = 1\n", encoding="utf-8")

    result = discover_python(tmp_path, Config())
    assert result == (file_a, file_b)


def test_ignores_non_py_files(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    py_file = src_dir / "code.py"
    py_file.write_text("print('hello')\n", encoding="utf-8")
    (src_dir / "notes.md").write_text("# Notes\n", encoding="utf-8")
    (src_dir / "data.json").write_text("{}\n", encoding="utf-8")
    (src_dir / "binary.pyc").write_bytes(b"\x00\x01")

    result = discover_python(tmp_path, Config())
    assert result == (py_file,)


def test_respects_exclude_dirs(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    valid_file = src_dir / "app.py"
    valid_file.write_text("app = 1\n", encoding="utf-8")

    venv_dir = src_dir / ".venv"
    venv_dir.mkdir()
    (venv_dir / "x.py").write_text("x = 1\n", encoding="utf-8")

    git_dir = src_dir / ".git"
    git_dir.mkdir()
    (git_dir / "y.py").write_text("y = 1\n", encoding="utf-8")

    custom_excluded = src_dir / "build"
    custom_excluded.mkdir()
    (custom_excluded / "generated.py").write_text("gen = 1\n", encoding="utf-8")

    config = Config(exclude=(".git", ".venv", "build"))
    result = discover_python(tmp_path, config)
    assert result == (valid_file,)


def test_skips_symlinked_dirs_and_files(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    real_file = src_dir / "real.py"
    real_file.write_text("real = True\n", encoding="utf-8")

    symlinked_file = src_dir / "link.py"
    _symlink_or_skip(symlinked_file, real_file)

    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (outside_dir / "extra.py").write_text("extra = True\n", encoding="utf-8")

    symlinked_dir = src_dir / "linked_dir"
    _symlink_or_skip(symlinked_dir, outside_dir)

    result = discover_python(tmp_path, Config())
    assert result == (real_file,)


def test_nonexistent_configured_path_is_skipped(tmp_path: Path) -> None:
    config = Config(docsig_paths=("does-not-exist", "also-missing"))
    result = discover_python(tmp_path, config)
    assert result == ()


def test_single_file_path_is_allowed(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "src" / "pkg"
    pkg_dir.mkdir(parents=True)
    file_a = pkg_dir / "a.py"
    file_b = pkg_dir / "b.py"
    file_a.write_text("a = 1\n", encoding="utf-8")
    file_b.write_text("b = 2\n", encoding="utf-8")

    config = Config(docsig_paths=("src/pkg/a.py",))
    result = discover_python(tmp_path, config)
    assert result == (file_a,)


def test_multiple_roots(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    src_file = src_dir / "lib.py"
    src_file.write_text("lib = 1\n", encoding="utf-8")

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True)
    script_file = scripts_dir / "run.py"
    script_file.write_text("run = 1\n", encoding="utf-8")

    config = Config(docsig_paths=("src", "scripts"))
    result = discover_python(tmp_path, config)
    assert result == (script_file, src_file)


def test_result_is_deterministically_sorted(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    names = ["z.py", "a.py", "m.py", "c.py", "b.py"]
    for name in names:
        (src_dir / name).write_text(f"# {name}\n", encoding="utf-8")

    result = discover_python(tmp_path, Config())
    expected = tuple(sorted(src_dir / name for name in names))
    assert result == expected


def test_root_not_a_directory_raises(tmp_path: Path) -> None:
    not_a_dir = tmp_path / "not_a_dir.py"
    not_a_dir.write_text("x = 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Not a directory"):
        discover_python(not_a_dir, Config())


def test_overlapping_docsig_paths_deduplicated(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    file_a = src_dir / "a.py"
    file_a.write_text("a = 1\n", encoding="utf-8")

    config = Config(docsig_paths=("src", "src/a.py"))
    result = discover_python(tmp_path, config)
    assert result == (file_a,)


def test_docsig_path_as_symlink_is_skipped(tmp_path: Path) -> None:
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (outside_dir / "module.py").write_text("mod = 1\n", encoding="utf-8")

    symlink_src = tmp_path / "src"
    _symlink_or_skip(symlink_src, outside_dir)

    result = discover_python(tmp_path, Config())
    assert result == ()
