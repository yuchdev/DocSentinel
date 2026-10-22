"""Adversarial complexity regression tests for DS116 path-boundary analysis.

Path containment is a quadratic trap: a naive implementation re-scans a parent
flood, double-decodes, rescans a backtick tail from every opener, or walks the raw
(pre-collapse) parent-segment count with ``os.lstat``. ``path_boundaries`` instead
decodes exactly once (:func:`urllib.parse.unquote`, linear), normalizes with a
single push/pop pass, and only walks the collapsed in-root component count with a
hop-bounded symlink check. These tests drive the detector over doubling series
through :func:`tests.timing_helpers.assert_scales_linearly` (CPU time, best-of-N,
floored baseline, per-doubling ratio plus a log-log slope bound) and assert the
exact finding count at every size so a pass is never vacuous.

The shapes cover the performance contract: parent-segment, encoded-dot, encoded-
separator, oscillation, nested-oscillation, double-encoded, bare-percent and
``%2``-prefix floods; unclosed link, image-open and ``<a href>`` floods; one very
long path segment; many links and many reference definitions; ``C:\\`` and
backslash floods; backtick-wrapped path spans of increasing run length; CRLF and
CR-only line terminators; and a bounded N-deep symlink chain built with ``tmp_path``.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from docsentinel import models
from docsentinel.config import Config
from docsentinel.detectors import path_boundaries as pb
from tests.timing_helpers import assert_scales_linearly

_ROOT = Path(os.sep) / "scanroot"
_SETTINGS = Config(root_escape_policy="error")


def _run(text: str) -> tuple[models.Finding, ...]:
    """Run DS116 recognition over one document under the error policy."""
    return pb.check_text(text, "docs/README.md", _ROOT, _SETTINGS)


#: Single-line floods: one pathologically long line built by repeating a fragment
#: ``n`` times, mapped to the exact DS116 finding count that shape must yield.
_SINGLE_LINE: dict[str, tuple[Callable[[int], str], Callable[[int], int]]] = {
    "parent_segment_flood": (lambda n: "[x](" + "../" * n + "y.md)\n", lambda _n: 1),
    "encoded_dot_flood": (lambda n: "[x](" + "%2e%2e/" * n + "y.md)\n", lambda _n: 1),
    "encoded_separator_flood": (lambda n: "[x](" + "..%2f" * n + "y.md)\n", lambda _n: 1),
    "oscillation_flood": (lambda n: "[x](" + "a/../" * n + "y.md)\n", lambda _n: 0),
    "nested_oscillation_flood": (lambda n: "[x](" + "a/b/../../" * n + "y.md)\n", lambda _n: 0),
    "double_encoded_flood": (lambda n: "[x](" + "%252e" * n + "/y.md)\n", lambda _n: 1),
    "bare_percent_flood": (lambda n: "[x](" + "%" * n + ")\n", lambda _n: 0),
    "percent_two_flood": (lambda n: "[x](" + "%2" * n + ")\n", lambda _n: 0),
    "unclosed_link_flood": (lambda n: "[x](" * n + "\n", lambda _n: 0),
    "image_open_flood": (lambda n: "![" * n + "\n", lambda _n: 0),
    "anchor_href_flood": (lambda n: '<a href="' * n + "\n", lambda _n: 0),
    "long_single_segment": (lambda n: "[x](" + "a" * n + ".md)\n", lambda _n: 0),
    "many_identical_links_one_line": (lambda n: "[x](../../out.md)" * n + "\n", lambda _n: 1),
    "windows_drive_flood": (lambda n: "[x](" + "C:\\" * n + ")\n", lambda _n: 1),
    "backslash_flood": (lambda n: "[x](d" + "\\" * n + ")\n", lambda _n: 1),
}

#: Multi-line floods: ``n`` independent one-line units, each an escaping reference
#: with a distinct target so no de-duplication collapses the count.
_MULTI_LINE: dict[str, tuple[Callable[[int], str], Callable[[int], int]]] = {
    "many_distinct_links": (lambda n: "".join(f"[a](../../out{i}.md)\n" for i in range(n)), lambda n: n),
    "many_reference_definitions": (lambda n: "".join(f"[r{i}]: ../../out{i}.md\n" for i in range(n)), lambda n: n),
    "backtick_path_spans": (
        lambda n: "".join(f"see {'`' * ((i % 5) + 1)}../../x{i}.md{'`' * ((i % 5) + 1)}\n" for i in range(n)),
        lambda n: n,
    ),
    "crlf_escaping_links": (lambda n: "".join(f"[a](../../out{i}.md)\r\n" for i in range(n)), lambda n: n),
    "cr_only_escaping_links": (lambda n: "".join(f"[a](../../out{i}.md)\r" for i in range(n)), lambda n: n),
}

_SINGLE_LINE_SIZES = (2_000, 4_000, 8_000, 16_000)
_MULTI_LINE_SIZES = (400, 800, 1_600, 3_200)


@pytest.mark.parametrize("name", list(_SINGLE_LINE))
def test_single_line_floods_stay_linear(name: str):
    """
    [Unit] detectors path_boundaries: verifies single-line path floods scale near-linearly.

    Scenario:
        Given one pathologically long line of a parent-segment, encoded-dot, encoded-separator,
            oscillation, nested-oscillation, double-encoded, bare-percent, ``%2``-prefix, unclosed-link,
            image-open, ``<a href>``, long-single-segment, many-identical-link, ``C:\\`` or backslash flood
        When DS116 recognition runs over a doubling series of that line
        Then the exact finding count holds at every size and the scaling stays under the linear bound.

    Boundaries:
        - Focus: decode-once, single-pass normalization, no catastrophic regex or tail rescan
        - Fixtures/params: parametrized over every single-line flood shape

    On failure, first check:
        - Whether _classify began double-decoding or rescanning the line per opener
        - Whether _normalize_relative lost its single push/pop pass
    """
    builder, expected = _SINGLE_LINE[name]
    assert_scales_linearly(builder, _run, _SINGLE_LINE_SIZES, expected_count=expected, label=name)


@pytest.mark.parametrize("name", list(_MULTI_LINE))
def test_multi_line_floods_stay_linear(name: str):
    """
    [Unit] detectors path_boundaries: verifies multi-line reference floods scale near-linearly.

    Scenario:
        Given ``n`` independent escaping references (distinct links, reference definitions, backtick
            path spans of increasing run length, and CRLF/CR-only-terminated links) across a doubling series
        When DS116 recognition runs over each size
        Then exactly ``n`` findings are produced at every size and the scaling stays under the linear bound.

    Boundaries:
        - Focus: per-reference O(1) classification across many references and line terminators
        - Fixtures/params: parametrized over every multi-line flood shape

    On failure, first check:
        - Whether candidate gathering or sorting became super-linear in the reference count
        - Whether backtick-run resolution regained a per-opener tail rescan
    """
    builder, expected = _MULTI_LINE[name]
    assert_scales_linearly(builder, _run, _MULTI_LINE_SIZES, expected_count=expected, label=name)


def test_symlink_chain_walk_stays_linear(tmp_path: Path):
    """
    [Unit] detectors path_boundaries: verifies the bounded symlink walk scales near-linearly.

    Scenario:
        Given an in-root chain of ``n`` symlinks whose final link points outside the root, referenced
            by a document, across a small doubling series within the hop bound
        When DS116 follows the chain with its lexical, non-following containment walk
        Then exactly one escape finding is produced at every size and the walk scales near-linearly.

    Boundaries:
        - Focus: the walk runs over the collapsed in-root component/hop count, bounded and linear
        - Fixtures/params: tmp_path (symlink chain regenerated per size)

    On failure, first check:
        - Whether escapes_via_symlink lost its hop bound or per-component loop detection
        - Whether the walk began stat-ing the outside target instead of reading the link lexically
    """

    def build(size: int) -> tuple[Path, tuple[models.Document, ...]]:
        """Build a fresh in-root symlink chain of ``size`` links ending outside the root."""
        root = tmp_path / f"root{size}"
        root.mkdir()
        outside = tmp_path / f"outside{size}.md"
        outside.write_text("secret\n", encoding="utf-8")
        for index in range(size - 1):
            target = f"link{index + 1}"
            try:
                (root / f"link{index}").symlink_to(target)
            except (NotImplementedError, OSError) as error:
                pytest.skip(f"symlinks unavailable: {error}")
        (root / f"link{size - 1}").symlink_to(f"../outside{size}.md")
        (root / "README.md").write_text("[x](link0)\n", encoding="utf-8")
        return root, (models.Document("README.md", 0),)

    def run(payload: tuple[Path, tuple[models.Document, ...]]) -> tuple[models.Finding, ...]:
        """Run DS116 over the prebuilt symlink-chain document."""
        root, documents = payload
        return pb.detect(root, documents, _SETTINGS)

    assert_scales_linearly(build, run, (8, 16, 32), expected_count=1, label="symlink_chain")
