"""Self-tests for the shared complexity-regression helper.

These prove the criterion in :func:`tests.timing_helpers.assert_scales_linearly`
actually discriminates: a linear workload passes, while a quadratic one, an
``O(n**1.5)`` one, and a vacuous (wrong-count) run each fail. The final test uses
the *real* historical oracle -- the pre-fix quadratic backtick matcher kept in
``tests/unit/test_markdown_blocks_code_span_parity.py`` -- on the increasing-length
backtick line to show the helper would have caught the shipped HIGH-severity bug
while the current linear :func:`docsentinel.markdown_blocks.find_code_spans` passes.

Every test here keeps its own sizes small and uses a low floor so the whole module
runs in a few seconds of CPU while still letting each super-linear workload rise
clearly above the floor at its smallest size.
"""

from __future__ import annotations

from math import isqrt

import pytest

from docsentinel import markdown_blocks as mb
from tests.timing_helpers import assert_scales_linearly, measure_scaling
from tests.unit.test_markdown_blocks_code_span_parity import _increasing_backtick_line, _oracle_code_spans

#: A low floor for the self-tests so the deliberately small super-linear workloads
#: still sit above it at their smallest size (the shipped suite uses the larger default).
_SELF_FLOOR = 0.002


def _linear_build(size: int) -> list[int]:
    """Return a list of ``size`` integers as the linear workload's input (built untimed)."""
    return list(range(size))


def _linear_run(data: list[int]) -> list[int]:
    """Do one linear pass over ``data`` and return a list of the same length."""
    return [value & 7 for value in data]


def _quadratic_run(data: list[int]) -> list[int]:
    """Do ``O(n**2)`` work over ``data`` and return a one-element result.

    The nested pass over ``data`` is the classic quadratic trap the helper must catch.

    :param data: The pre-built input list of length ``n``.
    :returns: A single-element list, so the expected result length is always ``1``.
    """
    total = 0
    for _ in data:
        for value in data:
            total += value & 1
    return [total]


def _root_times_n_run(data: list[int]) -> list[int]:
    """Do ``O(n**1.5)`` work (``sqrt(n)`` outer passes over all ``n``) and return one element.

    This mirrors the shape of the real backtick bug: an outer loop bounded by
    ``sqrt(n)`` wrapping a full ``O(n)`` inner scan.

    :param data: The pre-built input list of length ``n``.
    :returns: A single-element list, so the expected result length is always ``1``.
    """
    total = 0
    for _ in range(isqrt(len(data))):
        for value in data:
            total += value & 1
    return [total]


def test_linear_workload_passes():
    """
    [Unit] timing helpers: verifies a genuinely linear workload satisfies the criterion.

    Scenario:
        Given a workload whose cost grows linearly with the input size
        When assert_scales_linearly measures it across a doubling series with exact counts
        Then both the per-doubling ratio and the log-log slope bounds hold, so it passes and
            returns a report whose slope is comfortably near 1.0.

    Boundaries:
        - Focus: the helper does not false-trip on a linear algorithm
        - Fixtures/params: none

    On failure, first check:
        - Whether the slope ceiling is too tight for timer noise on this host
        - Whether best-of-N and the floor still damp scheduler spikes
    """
    report = assert_scales_linearly(
        _linear_build,
        _linear_run,
        (20_000, 40_000, 80_000, 160_000),
        expected_count=lambda size: size,
        floor_seconds=_SELF_FLOOR,
        label="linear",
    )
    assert report.slope < 1.4


def test_quadratic_workload_fails():
    """
    [Unit] timing helpers: verifies a quadratic workload is rejected.

    Scenario:
        Given a workload whose cost grows with the square of the input size
        When assert_scales_linearly measures it across a doubling series
        Then the ~2.0 log-log slope breaches the slope bound (the per-doubling ratio is only a
            pathology ceiling and no longer decides) and the assertion raises, proving a genuine
            quadratic regression is caught.

    Boundaries:
        - Focus: the helper trips on the quadratic bug class
        - Fixtures/params: none

    On failure, first check:
        - Whether the smallest size still rises above the floor for this workload
        - Whether slope_limit drifted above the quadratic signature
    """
    with pytest.raises(AssertionError):
        assert_scales_linearly(
            _linear_build,
            _quadratic_run,
            (400, 800, 1_600, 3_200),
            expected_count=1,
            floor_seconds=_SELF_FLOOR,
            repeats=2,
            label="quadratic",
        )


def test_root_times_n_workload_fails():
    """
    [Unit] timing helpers: verifies an O(n**1.5) workload is rejected.

    Scenario:
        Given a workload whose cost grows as n**1.5 (sqrt(n) passes over all n), the exact
            shape of the real backtick bug
        When assert_scales_linearly measures it across a doubling series
        Then the ~1.5 log-log slope breaches the slope bound (the loose per-step ratio alone
            would let a 2.83x step pass) and the assertion raises, proving the slope guard
            catches the 2.8x-class bug at these sizes.

    Boundaries:
        - Focus: the helper trips on the O(n**1.5) class, not just full quadratic
        - Fixtures/params: none

    On failure, first check:
        - Whether slope_limit crept to or above 1.5 (which would admit this class)
        - Whether the smallest size still rises above the floor
    """
    with pytest.raises(AssertionError):
        assert_scales_linearly(
            _linear_build,
            _root_times_n_run,
            (8_000, 16_000, 32_000, 64_000, 128_000),
            expected_count=1,
            floor_seconds=_SELF_FLOOR,
            repeats=2,
            label="root-times-n",
        )


def test_wrong_expected_count_fails_before_timing_bound():
    """
    [Unit] timing helpers: verifies a vacuous (wrong-count) run is rejected.

    Scenario:
        Given a linear workload but an expected_count that does not match its real result length
        When measure_scaling runs it
        Then it raises AssertionError on the count mismatch, proving the timing bound can never
            pass vacuously over a detector that silently produced the wrong number of results.

    Boundaries:
        - Focus: the non-vacuity guard fires independently of the timing criterion
        - Fixtures/params: none

    On failure, first check:
        - Whether expected_count is still asserted at every size
        - Whether len(result) is compared against the resolved expected value
    """
    with pytest.raises(AssertionError, match="expected"):
        measure_scaling(
            _linear_build,
            _linear_run,
            (1_000, 2_000),
            expected_count=lambda size: size + 1,
            floor_seconds=_SELF_FLOOR,
            repeats=1,
        )


def test_catches_real_quadratic_backtick_oracle_while_shipped_matcher_passes():
    """
    [Unit] timing helpers: verifies the helper catches the historical bug but clears the fix.

    Scenario:
        Given the pre-fix quadratic backtick-matcher oracle and the shipped linear
            find_code_spans, both driven over the increasing-length backtick line
        When assert_scales_linearly measures each across a doubling series of line sizes
        Then the oracle breaches the bound (the real O(n**1.5) HIGH-severity bug is caught) while
            the shipped matcher passes, both returning zero spans (the line never closes a run).

    Boundaries:
        - Focus: the helper would have caught the real shipped regression, not just synthetic loops
        - Fixtures/params: none

    On failure, first check:
        - Whether find_code_spans reintroduced a tail rescan from every opener
        - Whether the oracle or the increasing-backtick builder was altered
    """
    # The series starts at 8KB and spans four doublings (five points) up to 128KB. A short or tiny series is
    # fragile: at 4KB the oracle takes ~2ms (one blip drags the fitted slope under the 1.4
    # limit) and even 8-64KB leaves only ~0.1 of margin between the oracle's ~1.5 slope and
    # the limit. Five points over a 16x span make the slope estimate far tighter (the oracle
    # fits 1.49-1.52 against ~0.6 for the shipped matcher), and the timing helper disables the
    # cyclic GC during timed runs, whose heap-sized cost otherwise flattens the slope in the
    # large full-suite process.
    sizes = (8 * 1024, 16 * 1024, 32 * 1024, 64 * 1024, 128 * 1024)

    with pytest.raises(AssertionError):
        assert_scales_linearly(
            _increasing_backtick_line,
            _oracle_code_spans,
            sizes,
            expected_count=0,
            floor_seconds=_SELF_FLOOR,
            repeats=3,
            label="quadratic-oracle",
        )

    report = assert_scales_linearly(
        _increasing_backtick_line,
        mb.find_code_spans,
        sizes,
        expected_count=0,
        floor_seconds=_SELF_FLOOR,
        repeats=3,
        label="shipped-find-code-spans",
    )
    assert report.slope < 1.4


def test_explicit_max_ratio_is_still_honoured():
    """
    [Unit] timing helpers: verifies a caller-supplied per-doubling ceiling is enforced.

    Scenario:
        Given a perfectly linear workload whose per-doubling time ratio is about 2
        When assert_scales_linearly is called with an explicit max_ratio of 1.2 (and a lax
            slope bound, so only the ratio can fail)
        Then the assertion raises, while the same workload passes under the default ceiling,
            proving the ratio ceiling is a real, tunable bound and merely no longer the
            quadratic detector.

    Boundaries:
        - Focus: the max_ratio parameter is wired through and the default is pathology-only
        - Fixtures/params: none

    On failure, first check:
        - Whether max_ratio is still compared against every floored per-doubling ratio
        - Whether the workload's smallest size still rises above the floor
    """
    sizes = (200_000, 400_000, 800_000, 1_600_000)

    with pytest.raises(AssertionError, match="per-doubling ratio"):
        assert_scales_linearly(
            _linear_build,
            _linear_run,
            sizes,
            expected_count=lambda size: size,
            max_ratio=1.2,
            slope_limit=5.0,
            floor_seconds=_SELF_FLOOR,
            repeats=2,
            label="explicit-ratio",
        )

    assert_scales_linearly(
        _linear_build,
        _linear_run,
        sizes,
        expected_count=lambda size: size,
        floor_seconds=_SELF_FLOOR,
        repeats=2,
        label="default-ratio",
    )
