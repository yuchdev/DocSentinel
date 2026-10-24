"""Shared complexity-regression helper for DocSentinel's timing tests.

Roughly a dozen adversarial tests used to carry their own copy of a wall-clock
doubling-ratio assertion (``later <= max(earlier, X) * K + slack``). Those copies
flaked under machine load -- a different shape failed on each noisy run, the
signature of timer noise rather than a real regression -- and they were slow. This
module centralises the measurement into one assertion, :func:`assert_scales_linearly`,
and fixes the two root causes:

* **CPU time, not wall-clock.** Every measurement uses :func:`time.process_time`,
  which counts only CPU time spent in this process. A busy host that steals
  wall-clock seconds from the test no longer inflates the measured time, so the
  ratio is stable under contention (it still inflates a little through cache and
  SMT effects, which the floor and the best-of-N absorb).
* **Best-of-N with a floored baseline.** Each size is run ``repeats`` times
  (default 3) and the *shortest* run is kept, discarding scheduler/GC spikes. The
  baseline of each ratio is floored at ``floor_seconds`` so a sub-millisecond first
  measurement cannot manufacture a huge ratio out of timer granularity.

Criterion (why these numbers separate a regression from noise)
--------------------------------------------------------------
The inputs are a geometric doubling series of sizes. For an algorithm of cost
``O(n**p)`` the time ratio between two sizes that differ by ``2x`` is ``2**p``:

===================  =====================  =================
Algorithm            per-doubling ratio      log-log slope p
===================  =====================  =================
linear ``O(n)``      ``2.0``                 ``1.0``
``O(n**1.5)``        ``2.83``                ``1.5``
quadratic ``O(n^2)`` ``4.0``                 ``2.0``
===================  =====================  =================

The real historical bug this guards against -- the backtick matcher that rescanned
the line tail from every unmatched opener -- was ``O(n**1.5)`` and produced ~2.8x
per doubling. Two independent criteria must both hold, which is why a single noisy
step can no longer fail the suite:

1. **Per-doubling ratio (a pathology ceiling only).** Every consecutive (floored)
   ratio must stay at or under ``max_ratio`` (default ``6.0``). A single step is the
   noisiest statistic there is, and it cannot tell the classes apart anyway: a true
   quadratic gives ~4.0x per step, yet a perfectly linear algorithm can measure ~3.8x
   on one step when the timings are only a few hundredths of a second (observed in the
   suite with a fitted slope of 1.003). A ceiling tight enough to catch a quadratic
   therefore false-trips on linear code, so this bound is set well above any plausible
   noise and only has to catch a cliff or exponential blow-up. It does NOT discriminate
   ``O(n**1.5)`` or quadratic; the slope below does.
2. **Log-log slope (the precise guard).** The least-squares slope of ``log(time)``
   against ``log(size)`` over *all* sizes must stay under ``slope_limit`` (default
   ``1.4``). A slope fitted over four or more points is far less noisy than any
   single ratio: linear sits near ``1.0``, the ``O(n**1.5)`` class at ``1.5`` and
   quadratic at ``2.0``. ``1.4`` is below ``1.5`` (so the ``O(n**1.5)`` class is
   caught) with ``0.4`` of headroom above a linear ``1.0`` (so noise does not
   false-trip it). This is the bound that catches the 2.8x-class historical bug.

For either criterion to catch a super-linear bug, that bug's time at the *smallest*
size must already exceed ``floor_seconds`` (otherwise flooring damps its slope). A
genuinely quadratic algorithm is dramatically slower than a linear one even at small
sizes, so this holds whenever the smallest size is chosen so the linear baseline is
near the floor while the bug is well above it. Flooring is deliberately asymmetric:
it can only *reduce* a measured slope/ratio, so it can never turn a linear run into a
false failure -- it only ever risks a false pass, which the self-tests in
``tests/unit/test_timing_helpers.py`` pin against a real quadratic oracle.

The result is asserted on every size (via ``expected_count``) so a detector that
silently returns nothing -- or explodes -- can never make the timing bound pass
vacuously.
"""

from __future__ import annotations

import gc
import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Optional, TypeVar, Union

#: Default per-doubling ratio ceiling: a pathology-only bound (a cliff or exponential
#: blow-up). It is deliberately far above the ~4x of a quadratic because a single step is
#: too noisy to separate a quadratic from a linear run with a lucky/unlucky step; that
#: ``O(n**1.5)``/quadratic discrimination is the slope bound's job.
DEFAULT_MAX_RATIO = 6.0

#: Default log-log slope ceiling: below the ``1.5`` of the ``O(n**1.5)`` class and
#: well above a linear ``1.0``, so it catches the bug class without noise false-trips.
DEFAULT_SLOPE_LIMIT = 1.4

#: Default baseline floor in CPU seconds: a measurement at or below this is treated
#: as timer noise, so it cannot manufacture a large ratio or slope.
DEFAULT_FLOOR_SECONDS = 0.02

#: Default best-of-N repeat count; the shortest run of each size is kept.
DEFAULT_REPEATS = 3

Payload = TypeVar("Payload")
Result = TypeVar("Result")

#: An expected result size: either a constant, or a function of the input size.
ExpectedCount = Union[int, Callable[[int], int]]


@dataclass(frozen=True)
class ScalingReport:
    """The measurement behind one :func:`assert_scales_linearly` call.

    :ivar sizes: The input sizes in the order measured.
    :ivar times: Best-of-N CPU seconds, one per size.
    :ivar ratios: Floored per-doubling time ratios between consecutive sizes.
    :ivar slope: Least-squares slope of ``log(time)`` against ``log(size)``.
    :ivar counts: The measured result size (``len``) at each input size.
    """

    sizes: tuple[int, ...]
    times: tuple[float, ...]
    ratios: tuple[float, ...]
    slope: float
    counts: tuple[int, ...]

    def describe(self) -> str:
        """Return a one-line human-readable summary of sizes, times, ratios and slope."""
        times = ", ".join(f"{value:.4f}" for value in self.times)
        ratios = ", ".join(f"{value:.2f}" for value in self.ratios)
        return f"sizes={self.sizes} times=[{times}]s ratios=[{ratios}] slope={self.slope:.3f} counts={self.counts}"


def _expected_for(expected_count: ExpectedCount, size: int) -> int:
    """Resolve ``expected_count`` to a concrete count for one input size.

    :param expected_count: A constant count or a ``size -> count`` callable.
    :param size: The input size being measured.
    :returns: The exact result length the run must produce at ``size``.
    """
    if callable(expected_count):
        return expected_count(size)
    return expected_count


def _best_cpu_time(run: Callable[[Payload], Result], payload: Payload, repeats: int) -> tuple[float, Result]:
    """Return the shortest of ``repeats`` CPU-timed runs and the last result.

    Only the ``run`` call is timed; building the payload happens in the caller,
    outside the timed region. The shortest run discards scheduler spikes.

    The cyclic garbage collector is disabled for the timed runs (after one collection
    beforehand), as :mod:`timeit` does. A collection costs time proportional to the size of
    the live heap, not to the input being measured, and it is triggered by allocation
    counts; in a large process (the full test suite keeps spaCy and scikit-learn loaded)
    that adds a heap-sized, roughly linear cost to every size, which flattens the fitted
    slope and lets a genuinely super-linear workload slip under the bound. The previous
    collector state is restored afterwards.

    :param run: The callable under test, invoked as ``run(payload)``.
    :param payload: The pre-built input for this size.
    :param repeats: Number of times to run; the minimum CPU time is kept.
    :returns: A ``(best_cpu_seconds, result)`` pair.
    """
    best = float("inf")
    captured: list[Result] = []
    collector_was_enabled = gc.isenabled()
    gc.collect()
    gc.disable()
    try:
        for _ in range(repeats):
            start = time.process_time()
            outcome = run(payload)
            best = min(best, time.process_time() - start)
            if not captured:
                captured.append(outcome)
    finally:
        if collector_was_enabled:
            gc.enable()
    return best, captured[0]


def _loglog_slope(sizes: Sequence[int], times: Sequence[float], floor: float) -> float:
    """Return the least-squares slope of ``log(time)`` against ``log(size)``.

    Times are floored at ``floor`` before the log so a sub-floor measurement reads as
    the floor rather than as a spuriously fast (hence steep) point. Flooring can only
    reduce the slope, so it never turns a linear series into a false failure.

    :param sizes: Input sizes (must be strictly increasing and length >= 2).
    :param times: Best CPU seconds, aligned with ``sizes``.
    :param floor: Lower bound applied to each time before taking its log.
    :returns: The fitted slope ``p`` in the ``time ~ size**p`` model.
    """
    xs = [math.log(size) for size in sizes]
    ys = [math.log(max(value, floor)) for value in times]
    count = len(xs)
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    denominator = sum((x - mean_x) ** 2 for x in xs)
    return numerator / denominator


def measure_scaling(
    build: Callable[[int], Payload],
    run: Callable[[Payload], Result],
    sizes: Sequence[int],
    *,
    expected_count: Optional[ExpectedCount] = None,
    floor_seconds: float = DEFAULT_FLOOR_SECONDS,
    repeats: int = DEFAULT_REPEATS,
) -> ScalingReport:
    """Build, run and CPU-time ``run`` across ``sizes`` and return a :class:`ScalingReport`.

    The payload for each size is built via ``build(size)`` *outside* the timed region;
    only ``run(payload)`` is timed, best-of-``repeats``. When ``expected_count`` is given
    the result length is asserted at every size so the measurement can never be vacuous.

    :param build: Builds the input for a size; not timed.
    :param run: The callable under test; timed as ``run(payload)``.
    :param sizes: A strictly increasing geometric (doubling) series, length >= 2.
    :param expected_count: Required ``len(result)`` per size (constant or ``size -> int``).
    :param floor_seconds: Baseline floor for the slope fit.
    :param repeats: Best-of-N repeat count.
    :returns: The populated scaling report.
    :raises AssertionError: If a measured result length differs from ``expected_count``.
    """
    ordered = tuple(sizes)
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    if len(ordered) < 2:
        raise ValueError("assert_scales_linearly needs at least two sizes")
    if any(later <= earlier for earlier, later in zip(ordered[:-1], ordered[1:], strict=True)):
        raise ValueError(f"sizes must be strictly increasing: {ordered}")

    times: list[float] = []
    counts: list[int] = []
    for size in ordered:
        payload = build(size)
        best, result = _best_cpu_time(run, payload, repeats)
        measured = len(result)  # type: ignore[arg-type]
        if expected_count is not None:
            expected = _expected_for(expected_count, size)
            assert measured == expected, f"size={size}: result length {measured} != expected {expected}"
        times.append(best)
        counts.append(measured)

    ratios = tuple(later / max(earlier, floor_seconds) for earlier, later in zip(times[:-1], times[1:], strict=True))
    slope = _loglog_slope(ordered, times, floor_seconds)
    return ScalingReport(
        sizes=ordered,
        times=tuple(times),
        ratios=ratios,
        slope=slope,
        counts=tuple(counts),
    )


def assert_scales_linearly(
    build: Callable[[int], Payload],
    run: Callable[[Payload], Result],
    sizes: Sequence[int],
    *,
    expected_count: Optional[ExpectedCount] = None,
    max_ratio: float = DEFAULT_MAX_RATIO,
    floor_seconds: float = DEFAULT_FLOOR_SECONDS,
    slope_limit: float = DEFAULT_SLOPE_LIMIT,
    repeats: int = DEFAULT_REPEATS,
    label: str = "",
) -> ScalingReport:
    """Assert ``run`` scales near-linearly across a doubling series of ``sizes``.

    The payload per size is built via ``build(size)`` outside the timed region; only
    ``run(payload)`` is CPU-timed, best-of-``repeats``. The result length is asserted
    against ``expected_count`` at every size (so a dead or exploding callable cannot pass
    vacuously), then two criteria must both hold: every floored per-doubling ratio stays
    at or under ``max_ratio`` and the log-log slope over all sizes stays under
    ``slope_limit``. See the module docstring for why these separate an ``O(n**1.5)`` or
    quadratic regression from timer noise.

    :param build: Builds the input for a size; not timed.
    :param run: The callable under test; timed as ``run(payload)``.
    :param sizes: A strictly increasing geometric (doubling) series, length >= 2.
    :param expected_count: Required ``len(result)`` per size (constant or ``size -> int``).
    :param max_ratio: Ceiling on each floored per-doubling time ratio.
    :param floor_seconds: Baseline floor for both the ratio and the slope fit.
    :param slope_limit: Ceiling on the fitted ``log(time)``/``log(size)`` slope.
    :param repeats: Best-of-N repeat count.
    :param label: Identifier echoed into any failure message.
    :returns: The scaling report (useful for callers that want to inspect it).
    :raises AssertionError: If the count, a per-doubling ratio, or the slope bound fails.
    """
    report = measure_scaling(
        build,
        run,
        sizes,
        expected_count=expected_count,
        floor_seconds=floor_seconds,
        repeats=repeats,
    )
    tag = f"{label}: " if label else ""
    for earlier, later, ratio in zip(report.times[:-1], report.times[1:], report.ratios, strict=True):
        assert ratio <= max_ratio, (
            f"{tag}per-doubling ratio {ratio:.2f} exceeds {max_ratio} "
            f"(earlier={earlier:.4f}s later={later:.4f}s); {report.describe()}"
        )
    assert report.slope <= slope_limit, (
        f"{tag}log-log slope {report.slope:.3f} exceeds {slope_limit}; {report.describe()}"
    )
    return report
