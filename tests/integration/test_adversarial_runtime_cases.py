"""Adversarial runtime cases driven end to end through the CLI (Story 15.0 Task 02 D).

Each case materializes a real temporary tree and runs ``docsentinel scan`` on it as a
subprocess. For every case the test asserts the same release invariants: the process
exits with a documented code (0 clean/advisory, 1 blocking findings, 2 config/scan
failure), stderr carries no Python traceback, neither stdout nor stderr leaks a raw
control byte (ESC/BEL/NUL/DEL -- the reporter must neutralise them), the run finishes
under a generous wall-clock ceiling, and two runs produce byte-identical stdout. A
crash, traceback, timeout or non-determinism here is a real defect, not an expected
outcome; the config-error and invalid-UTF-8 cases must fail *gracefully* with exit 2.
"""

import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest

#: Generous per-run wall-clock ceiling. Measured worst case on a quiet machine is ~4s
#: (2,000 files / 1 MB line); the ceiling is far above that so it cannot flake.
_CEILING_SECONDS: float = 120.0

#: Control bytes that must never reach a terminal or CI log, in stdout or stderr.
_FORBIDDEN_BYTES: tuple[bytes, ...] = (b"\x1b", b"\x07", b"\x00", b"\x7f")

#: Documented CLI exit codes.
_DOCUMENTED_EXITS: frozenset[int] = frozenset({0, 1, 2})


def _write(root: Path, relative: str, text: str):
    """Write UTF-8 text to ``root/relative``, creating parent directories.

    :param root: Scan root.
    :param relative: Path relative to the root.
    :param text: File contents.
    """
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def build_unicode_names_and_content(root: Path):
    """Build a tree with a Unicode file name and Unicode body text."""
    _write(root, "café_日本語_Ωμέγα.md", "# Título 日本語\n\nPárrafo con acentos y 漢字 and emoji 🚀.\n")


def build_unmatched_delimiters_one_line(root: Path):
    """Build one line packing 2,000 each of unmatched [, (, backtick, <!-- and fence markers."""
    line = ("[" * 2000) + ("(" * 2000) + ("`" * 2000) + ("<!--" * 2000) + ("```" * 2000)
    _write(root, "delims_one_line.md", f"# Delimiters\n\n{line}\n")


def build_unmatched_delimiters_across_lines(root: Path):
    """Build 2,000 lines each contributing one unmatched delimiter of each kind."""
    body = "\n".join("[ ( ` <!-- ```" for _ in range(2000))
    _write(root, "delims_multi_line.md", f"# Delimiters\n\n{body}\n")


def build_single_line_one_megabyte(root: Path):
    """Build a document whose body is a single ~1 MB line."""
    _write(root, "big_line.md", "# Big\n\n" + ("a " * 500_000) + "\n")


def build_traversal_and_absolute_targets(root: Path):
    """Build links, images, reference definitions and HTML with ../ traversal and absolute targets."""
    body = (
        "# Traversal\n\n"
        "[rel](../../etc/passwd)\n\n"
        "![img](../../../secret.png)\n\n"
        "[abs](/etc/shadow)\n\n"
        "[ref][r]\n\n"
        "[r]: ../../../../root/.ssh/id_rsa\n\n"
        '<a href="../../outside.md">x</a>\n\n'
        '<img src="/absolute/outside.png">\n'
    )
    _write(root, "traversal.md", body)


def build_windows_drive_unc_backslash(root: Path):
    """Build targets using Windows drive letters, UNC paths and backslash separators."""
    body = (
        "# Windows\n\n"
        "[drive](C:\\Windows\\win.ini)\n\n"
        "[unc](\\\\host\\share\\file.md)\n\n"
        "[back](..\\..\\outside.md)\n\n"
        "![driveimg](D:\\assets\\logo.png)\n"
    )
    _write(root, "windows.md", body)


def build_crlf_and_lone_cr(root: Path):
    """Build a document mixing CRLF line endings and a lone CR."""
    (root / "crlf.md").write_bytes(b"# CRLF\r\n\r\nLine one.\r\nLine two with lone\rCR here.\r\n")


def build_invalid_utf8(root: Path):
    """Build a document containing invalid UTF-8 byte sequences."""
    (root / "bad_utf8.md").write_bytes(b"# Title\n\n\xff\xfe invalid \x80\x81 bytes\n")


def build_bom(root: Path):
    """Build a document that begins with a UTF-8 byte-order mark."""
    (root / "bom.md").write_bytes(b"\xef\xbb\xbf# BOM\n\nContent after a byte-order mark.\n")


def build_symlink_escapes(root: Path):
    """Build in-root file and directory symlinks that escape the root, plus a link to one.

    :raises OSError: When the platform or filesystem cannot create symlinks; the test
        turns this into an allowlisted skip.
    """
    outside = root.parent / "adversarial_outside"
    outside.mkdir(parents=True, exist_ok=True)
    (outside / "secret.md").write_text("# Secret\n\nOutside the root.\n", encoding="utf-8")
    _write(root, "home.md", "# Home\n\n[escape](./link_out.md)\n")
    os.symlink(outside / "secret.md", root / "link_out.md")
    os.symlink(outside, root / "link_dir")


def build_config_docsentinel_header(root: Path):
    """Build a config that wrongly uses a ``[docsentinel]`` table header."""
    _write(root, "a.md", "# A\n\nprose\n")
    (root / "doc_sentinel.toml").write_text('[docsentinel]\nprofile = "fast"\n', encoding="utf-8")


def build_config_unknown_key(root: Path):
    """Build a config carrying an unknown top-level key."""
    _write(root, "a.md", "# A\n\nprose\n")
    (root / "doc_sentinel.toml").write_text('profile = "fast"\nbogus_key = 1\n', encoding="utf-8")


def build_missing_navigation_index(root: Path):
    """Build a config pointing at a navigation index that does not exist."""
    _write(root, "a.md", "# A\n\nprose\n")
    (root / "doc_sentinel.toml").write_text('profile = "fast"\nnavigation_indexes = ["SUMMARY.md"]\n', encoding="utf-8")


def build_missing_deprecated_mapping(root: Path):
    """Build a config pointing at a deprecated-references mapping that does not exist."""
    _write(root, "a.md", "# A\n\nprose\n")
    (root / "doc_sentinel.toml").write_text(
        'profile = "fast"\ndeprecated_references_file = "mapping.toml"\n', encoding="utf-8"
    )


def build_empty_repo(root: Path):
    """Build an empty repository with no documents at all."""


def build_many_tiny_files(root: Path):
    """Build 2,000 tiny documents that cross-link in a ring."""
    for index in range(2000):
        _write(root, f"f{index}.md", f"# F{index}\n\nLink [next](./f{(index + 1) % 2000}.md)\n")


def build_deeply_nested_directories(root: Path):
    """Build a 200-level-deep directory chain with one document at the bottom."""
    current = root
    for index in range(200):
        current = current / f"d{index}"
    _write(current, "deep.md", "# Deep\n\nDocument at the bottom of a deep tree.\n")


#: (id, builder, allowed exit codes, needs-symlink). ``needs_symlink`` cases skip with an
#: allowlisted reason when the filesystem cannot create symlinks.
CASES: tuple[tuple[str, Callable[[Path], None], frozenset[int], bool], ...] = (
    ("unicode_names_and_content", build_unicode_names_and_content, frozenset({0, 1}), False),
    ("unmatched_delimiters_one_line", build_unmatched_delimiters_one_line, frozenset({0, 1}), False),
    ("unmatched_delimiters_across_lines", build_unmatched_delimiters_across_lines, frozenset({0, 1}), False),
    ("single_line_one_megabyte", build_single_line_one_megabyte, frozenset({0, 1}), False),
    ("traversal_and_absolute_targets", build_traversal_and_absolute_targets, frozenset({0, 1}), False),
    ("windows_drive_unc_backslash", build_windows_drive_unc_backslash, frozenset({0, 1}), False),
    ("crlf_and_lone_cr", build_crlf_and_lone_cr, frozenset({0, 1}), False),
    ("invalid_utf8", build_invalid_utf8, frozenset({2}), False),
    ("bom", build_bom, frozenset({0, 1}), False),
    ("symlink_escapes", build_symlink_escapes, frozenset({0, 1}), True),
    ("config_docsentinel_header", build_config_docsentinel_header, frozenset({2}), False),
    ("config_unknown_key", build_config_unknown_key, frozenset({2}), False),
    ("missing_navigation_index", build_missing_navigation_index, frozenset({2}), False),
    ("missing_deprecated_mapping", build_missing_deprecated_mapping, frozenset({2}), False),
    ("empty_repo", build_empty_repo, frozenset({0}), False),
    ("many_tiny_files", build_many_tiny_files, frozenset({0, 1}), False),
    ("deeply_nested_directories", build_deeply_nested_directories, frozenset({0, 1}), False),
)


def _run_cli(root: Path) -> tuple[int, bytes, bytes, float]:
    """Run ``docsentinel scan`` on a root, returning exit code, stdout, stderr and elapsed seconds.

    :param root: Scan root to inspect.
    :returns: ``(returncode, stdout_bytes, stderr_bytes, elapsed_seconds)``.
    """
    started = time.monotonic()
    completed = subprocess.run(
        [sys.executable, "-m", "docsentinel.cli", "scan", str(root)],
        capture_output=True,
        check=False,
        timeout=_CEILING_SECONDS,
    )
    return completed.returncode, completed.stdout, completed.stderr, time.monotonic() - started


@pytest.mark.parametrize("case_id, builder, allowed_exits, needs_symlink", CASES, ids=[row[0] for row in CASES])
def test_adversarial_case_is_handled_safely(
    case_id: str,
    builder: Callable[[Path], None],
    allowed_exits: frozenset[int],
    needs_symlink: bool,
    tmp_path: Path,
):
    """
    [Integration] adversarial runtime cases: verifies each hostile tree is handled safely end to end.

    Scenario:
        Given a real temporary tree built for one adversarial case (Unicode, delimiter floods, a 1 MB
        line, symlink/traversal/Windows/absolute targets, CRLF, invalid UTF-8, BOM, bad config,
        missing nav/mapping, empty repo, 2,000 files, 200-deep nesting)
        When the CLI scans it twice as a subprocess
        Then it exits with a documented code in the case's allowed set, writes no traceback to stderr,
        leaks no raw control byte in stdout or stderr, finishes under the wall-clock ceiling, and both
        runs emit byte-identical stdout.

    Boundaries:
        - Focus: graceful, deterministic, bounded, injection-free handling of hostile runtime input
        - Fixtures/params: parametrized over every adversarial case; symlink cases skip if unsupported
        - Scope: the CLI entry point end to end, two runs per case

    On failure, first check:
        - The reported exit code versus the case's allowed set, and any traceback text in stderr
        - Which forbidden control byte leaked, or which run's stdout diverged (non-determinism)
    """
    if needs_symlink:
        try:
            builder(tmp_path)
        except OSError as exc:
            pytest.skip(f"symlinks unavailable: {exc}")
    else:
        builder(tmp_path)

    first_code, first_out, first_err, first_elapsed = _run_cli(tmp_path)
    second_code, second_out, _second_err, _second_elapsed = _run_cli(tmp_path)

    assert first_code in _DOCUMENTED_EXITS, f"{case_id}: undocumented exit {first_code}"
    assert first_code in allowed_exits, f"{case_id}: exit {first_code} not in allowed {sorted(allowed_exits)}"
    assert b"Traceback" not in first_err, f"{case_id}: scan raised a traceback: {first_err!r}"
    combined = first_out + first_err
    for forbidden in _FORBIDDEN_BYTES:
        assert forbidden not in combined, f"{case_id}: raw control byte {forbidden!r} leaked"
    assert first_elapsed < _CEILING_SECONDS, f"{case_id}: run exceeded {_CEILING_SECONDS}s ({first_elapsed:.1f}s)"
    assert first_code == second_code, f"{case_id}: exit code not deterministic ({first_code} vs {second_code})"
    assert first_out == second_out, f"{case_id}: stdout not deterministic across two runs"
