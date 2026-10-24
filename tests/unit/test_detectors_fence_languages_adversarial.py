"""Adversarial complexity regression tests for DS110 fence-language recognition.

DS110 adds only a fence-metadata pass on top of the shared scanner: it iterates
the already-tokenized fences once, extracts the first info-string token per
fence, and does set-based allowlist lookups. Each of those steps is a quadratic
trap if written naively (a per-fence rescan of the whole token list, a full
``info_string.split()`` instead of a bounded first-token split, or a per-fence
linear scan of a large allowlist). These tests drive the detector over doubling
series of both single-line floods (one pathologically long line) and multi-line
floods (many fenced blocks) through the shared
:func:`tests.timing_helpers.assert_scales_linearly` (CPU time, best-of-N, floored
baseline, per-doubling ratio plus a log-log slope bound), asserting the exact
DS110 finding count at every size so the pass is never vacuous.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from docsentinel.config import Config
from docsentinel.detectors import fence_languages
from tests.timing_helpers import assert_scales_linearly

#: Enabled default policy; most floods run under this opt-in configuration.
_ENABLED = Config(require_fence_languages=True)

#: A doubling series of sizes kept small enough to run quickly yet large enough to
#: separate a linear detector from a quadratic one under the shared criterion.
_SIZES = (500, 1_000, 2_000, 4_000)


def _run(config: Config) -> Callable[[str], object]:
    """Return a timed run that recognizes DS110 findings in a document under ``config``.

    :param config: Effective settings for the DS110 recognition pass.
    :returns: A ``text -> findings`` callable for :func:`assert_scales_linearly`.
    """
    return lambda text: fence_languages.check_text(text, "README.md", config)


#: Single-line floods: each builds ONE pathologically long line (optionally wrapped
#: as a closed fence) keyed to the exact DS110 finding count it must produce. The raw
#: delimiter floods are unclosed or malformed openers DS109 owns (0 findings); the
#: info-string floods are closed, labelled fences that exercise the first-token split
#: on a huge info string (0 findings, no allowlist).
_SINGLE_LINE_FLOODS: dict[str, tuple[Callable[[int], str], int]] = {
    "backtick_opener": (lambda n: "`" * n + "\n", 0),
    "tilde_opener": (lambda n: "~" * n + "\n", 0),
    "triple_backtick_run": (lambda n: "```" * n + "\n", 0),
    "backtick_space_run": (lambda n: "``` " * n + "\n", 0),
    "backtick_python_run": (lambda n: "```python" * n + "\n", 0),
    "space_run": (lambda n: " " * n + "\n", 0),
    "long_info_string": (lambda n: "```" + "a" * n + "\ncode\n```\n", 0),
    "brace_info_string": (lambda n: "```" + "{" * n + "\ncode\n```\n", 0),
    "comma_info_string": (lambda n: "```" + "a," * n + "\ncode\n```\n", 0),
}


@pytest.mark.parametrize("flood", _SINGLE_LINE_FLOODS.values(), ids=list(_SINGLE_LINE_FLOODS))
def test_single_line_flood_stays_linear(flood: tuple[Callable[[int], str], int]):
    """
    [Unit] detectors fence_languages: verifies ONE long flooded line stays near-linear.

    Scenario:
        Given a single pathologically long line built by repeating an adversarial fragment
            ('`', '~', '```', '``` ', '```python', ' ', a long info string, '{', 'a,')
            across a doubling series
        When DS110 recognition runs over each size through check_text(text, path, config)
        Then the exact expected finding count holds at every size (so the pass is never vacuous)
            and the scaling stays under the shared linear bound, ruling out a full info-string split
            or a per-fence rescan on one long line.

    Boundaries:
        - Focus: the first-token info-string split and DS109-ownership guard on ONE long line
        - Fixtures/params: parametrized over every single-line flood builder

    On failure, first check:
        - Whether _fence_language dropped its maxsplit=1 first-token split
        - Whether the DS109-ownership guard began rescanning the line
    """
    builder, expected = flood
    assert_scales_linearly(builder, _run(_ENABLED), _SIZES, expected_count=expected, label="single-line")


#: Multi-line floods: each builds ``n`` repeat units and a finding count as a function of
#: ``n``. These guard the per-fence iteration (and the finding-producing paths) against a
#: per-fence rescan of the token list.
_MULTI_LINE_FLOODS: dict[str, tuple[Callable[[int], str], Callable[[int], int]]] = {
    "many_unlabelled_blocks": (lambda n: "```\ncode\n```\n" * n, lambda n: n),
    "many_labelled_blocks": (lambda n: "```python\ncode\n```\n" * n, lambda n: 0),
    "consecutive_empty_fences": (lambda n: "```\n" * n, lambda n: 0),
    "one_unclosed_long_body": (lambda n: "```\n" + "x\n" * n, lambda n: 0),
    "alternating_markers": (lambda n: "```\na\n```\n~~~\nb\n~~~\n" * n, lambda n: 2 * n),
}


@pytest.mark.parametrize("flood", _MULTI_LINE_FLOODS.values(), ids=list(_MULTI_LINE_FLOODS))
def test_multi_line_flood_stays_linear(flood: tuple[Callable[[int], str], Callable[[int], int]]):
    """
    [Unit] detectors fence_languages: verifies many fenced blocks stay near-linear.

    Scenario:
        Given many fenced blocks of one shape (unlabelled, labelled, consecutive empty-fence
            pairs, one unclosed block over a huge body, and alternating backtick/tilde blocks)
            across a doubling series
        When DS110 recognition runs over each size through check_text(text, path, config)
        Then the exact expected finding count holds at every size (so the pass is never vacuous)
            and the scaling stays under the shared linear bound, ruling out a per-fence token rescan.

    Boundaries:
        - Focus: the single pass over the fence token list and its finding-producing branches
        - Fixtures/params: parametrized over every multi-line flood builder

    On failure, first check:
        - Whether the per-fence loop regained a scan over the whole token list
        - Whether empty-fence exemption or DS109 ownership misclassified a block shape
    """
    builder, count_of = flood
    # Liveness guard so a zero-count shape (labelled blocks, consecutive empty-fence pairs, one
    # unclosed block) can never pass vacuously: under the SAME enabled config a plain unlabelled
    # block must still be flagged, so a zero below reflects exemption/ownership, not a dead detector.
    assert len(fence_languages.check_text("```\ncode\n```\n", "README.md", _ENABLED)) == 1
    assert_scales_linearly(builder, _run(_ENABLED), _SIZES, expected_count=count_of, label="multi-line")


def test_strict_empty_fence_flood_stays_linear():
    """
    [Unit] detectors fence_languages: verifies the strict empty-fence path stays near-linear.

    Scenario:
        Given many consecutive empty fence pairs and allow_unlabelled_empty_fences disabled
        When DS110 recognition runs across a doubling series
        Then each empty fence is flagged (count equals the pair count) at every size and the
            scaling stays under the shared linear bound.

    Boundaries:
        - Focus: the finding-producing empty-fence branch under a strict policy
        - Fixtures/params: strict enabled Config

    On failure, first check:
        - The body_nonempty/allow_unlabelled_empty_fences branch in _fence_finding
        - Whether the per-fence loop became super-linear when every fence is a finding
    """
    strict = Config(require_fence_languages=True, allow_unlabelled_empty_fences=False)
    assert_scales_linearly(
        lambda n: "```\n```\n" * n,
        _run(strict),
        _SIZES,
        expected_count=lambda n: n,
        label="strict-empty",
    )


def test_large_allowlist_lookup_stays_linear():
    """
    [Unit] detectors fence_languages: verifies a huge allowlist does not slow per-fence lookups.

    Scenario:
        Given a 10k-entry allowlist that omits the fences' language and many labelled fences
        When DS110 recognition runs across a doubling series of fence counts
        Then every fence is flagged as an unknown language (count equals the fence count) and the
            scaling stays under the shared linear bound, proving the allowlist is a set lookup rather
            than a per-fence scan of the 10k entries.

    Boundaries:
        - Focus: set-based allowlist membership (O(1) per fence, not O(allowlist))
        - Fixtures/params: enabled Config with a 10k-entry allowlist

    On failure, first check:
        - That allowed is built once as a frozenset in check_text
        - That the membership test is `language not in allowed`, not a list scan
    """
    allowlist = tuple(f"lang{i}" for i in range(10_000))
    config = Config(require_fence_languages=True, allowed_fence_languages=allowlist)
    assert_scales_linearly(
        lambda n: "```mermaid\ncode\n```\n" * n,
        _run(config),
        _SIZES,
        expected_count=lambda n: n,
        label="large-allowlist",
    )
