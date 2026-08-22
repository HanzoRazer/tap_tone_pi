# INSTRUMENT CLASS: MEASUREMENT
"""Descriptive repeatability statistics for grant evidence (DO-102).

This module computes almost nothing. Mean, sample standard deviation,
coefficient of variation, and range are delegated to
:func:`tap_tone_pi.core.statistics.compute_repeatability`, which DO-085 already
established and which the rest of the repository already reports against. What
is added here is only what that helper does not provide: median, median absolute
deviation, explicit minimum and maximum, and the link back to the runs each
number came from.

Two things are deliberately *not* carried across.

**The acceptance verdict.** ``compute_repeatability`` returns ``is_acceptable``
and ``acceptance_threshold_pct``. Those belong to DO-085's workflow policy and
are not NSF success criteria; DO-102 §4.11 forbids inventing a target
repeatability figure. :class:`~..contracts.RepeatabilityMetricV1` has no field
they could be written into.

**The zero-mean sentinel.** For a mean of zero the DO-085 helper reports a
coefficient of variation of ``0.0``, which reads as perfect repeatability when
the quantity is in fact undefined. This module refuses to publish that value and
raises ``NSF-304`` instead.

Standard-deviation convention: sample standard deviation with Bessel's
correction (``n-1``), inherited from ``compute_repeatability`` and stated in
every generated report.
"""

from __future__ import annotations

import math
from typing import Sequence

from tap_tone_pi.core.statistics import compute_repeatability
from tap_tone_pi.grant_readiness.contracts import (
    GroupSpreadV1,
    PreliminaryExperimentRunV1,
    RepeatabilityMetricV1,
)
from tap_tone_pi.grant_readiness.errors import (
    GrantReadinessErrorCode,
    RepeatabilityStatisticsError,
)

# Below this magnitude a mean cannot scale a coefficient of variation without
# the result being dominated by floating-point noise. Matches the guard in
# tap_tone_pi.core.statistics, which returns 0.0 at that point; here it raises.
ZERO_MEAN_EPSILON = 1e-10

# Fewer than two observations have no spread to describe.
MINIMUM_SAMPLE_COUNT = 2


def _require_finite(values: Sequence[float], *, quantity: str) -> list[float]:
    numbers: list[float] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RepeatabilityStatisticsError(
                GrantReadinessErrorCode.NON_FINITE_STATISTIC,
                f"{quantity} observation is not a number",
                {"quantity": quantity},
            )
        number = float(value)
        if not math.isfinite(number):
            raise RepeatabilityStatisticsError(
                GrantReadinessErrorCode.NON_FINITE_STATISTIC,
                f"{quantity} observation is not finite",
                {"quantity": quantity},
            )
        numbers.append(number)
    return numbers


def calculate_median(values: Sequence[float]) -> float:
    """Return the median, averaging the middle pair for an even count."""
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        raise RepeatabilityStatisticsError(
            GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS,
            "median requires at least one observation",
            {"sample_count": 0},
        )
    middle = n // 2
    if n % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def calculate_median_absolute_deviation(values: Sequence[float]) -> float:
    """Return the median of absolute deviations from the median.

    Unscaled: no 1.4826 consistency factor is applied, because that factor
    assumes normality this evidence has not established.
    """
    center = calculate_median(values)
    return calculate_median([abs(value - center) for value in values])


def calculate_coefficient_of_variation(values: Sequence[float]) -> float:
    """Return CV% via the DO-085 helper, refusing the undefined zero-mean case."""
    numbers = _require_finite(values, quantity="value")
    if len(numbers) < MINIMUM_SAMPLE_COUNT:
        raise RepeatabilityStatisticsError(
            GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS,
            (
                "coefficient of variation requires at least "
                f"{MINIMUM_SAMPLE_COUNT} observations, got {len(numbers)}"
            ),
            {"sample_count": len(numbers)},
        )
    mean = sum(numbers) / len(numbers)
    if abs(mean) < ZERO_MEAN_EPSILON:
        raise RepeatabilityStatisticsError(
            GrantReadinessErrorCode.UNDEFINED_COEFFICIENT_OF_VARIATION,
            (
                "coefficient of variation is undefined for a mean of zero; the "
                "underlying helper reports 0.0, which would read as perfect "
                "repeatability"
            ),
            {"mean": mean},
        )
    return compute_repeatability(numbers).coefficient_of_variation_pct


def summarize_repeatability(
    values: Sequence[float],
    *,
    quantity: str,
    unit: str,
    source_run_ids: Sequence[str],
    metric_id: str | None = None,
) -> RepeatabilityMetricV1:
    """Summarize repeated observations of one quantity.

    Args:
        values: One observation per valid run, in the same order as
            ``source_run_ids``.
        quantity: What was observed, e.g. ``dominant_frequency``.
        unit: The unit of ``values``, e.g. ``Hz``.
        source_run_ids: The valid runs that produced ``values``. Every number in
            the returned metric is traceable to these.
        metric_id: Optional identifier; defaults to ``metric-{quantity}``.

    Returns:
        A :class:`RepeatabilityMetricV1` describing observed spread. It carries
        no acceptance flag and supports no accuracy claim.

    Raises:
        RepeatabilityStatisticsError: ``NSF-301`` for fewer than two
            observations or a run-count mismatch, ``NSF-302`` for a blank unit,
            ``NSF-303`` for a non-finite observation, ``NSF-304`` for a mean of
            zero.
    """
    numbers = _require_finite(values, quantity=quantity)
    run_ids = tuple(source_run_ids)

    if len(numbers) < MINIMUM_SAMPLE_COUNT:
        raise RepeatabilityStatisticsError(
            GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS,
            (
                f"{quantity} needs at least {MINIMUM_SAMPLE_COUNT} valid "
                f"observations to summarize, got {len(numbers)}"
            ),
            {"quantity": quantity, "sample_count": len(numbers)},
        )

    if len(run_ids) != len(numbers):
        raise RepeatabilityStatisticsError(
            GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS,
            (
                f"{quantity} has {len(numbers)} observations but "
                f"{len(run_ids)} source runs; every number must name its run"
            ),
            {"quantity": quantity, "observations": len(numbers), "runs": len(run_ids)},
        )

    if len(set(run_ids)) != len(run_ids):
        raise RepeatabilityStatisticsError(
            GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS,
            f"{quantity} cites the same run more than once",
            {"quantity": quantity},
        )

    if not unit or not unit.strip():
        raise RepeatabilityStatisticsError(
            GrantReadinessErrorCode.INCOMPATIBLE_MEASUREMENT_UNITS,
            f"{quantity} must declare a unit",
            {"quantity": quantity},
        )

    mean = sum(numbers) / len(numbers)
    if abs(mean) < ZERO_MEAN_EPSILON:
        raise RepeatabilityStatisticsError(
            GrantReadinessErrorCode.UNDEFINED_COEFFICIENT_OF_VARIATION,
            (
                f"{quantity} has a mean of zero, so its coefficient of "
                "variation is undefined and cannot be reported"
            ),
            {"quantity": quantity, "mean": mean},
        )

    # Delegate the four quantities DO-085 already owns.
    delegated = compute_repeatability(numbers)

    return RepeatabilityMetricV1(
        metric_id=metric_id or f"metric-{quantity}",
        quantity=quantity,
        unit=unit,
        sample_count=delegated.n_measurements,
        mean=delegated.mean,
        median=calculate_median(numbers),
        standard_deviation=delegated.repeatability_std_dev,
        coefficient_of_variation_pct=delegated.coefficient_of_variation_pct,
        minimum=min(numbers),
        maximum=max(numbers),
        range_value=delegated.range_value,
        median_absolute_deviation=calculate_median_absolute_deviation(numbers),
        source_run_ids=run_ids,
    )


def summarize_runs(
    runs: Sequence[PreliminaryExperimentRunV1],
    *,
    quantity: str,
    unit: str,
    metric_id: str | None = None,
) -> RepeatabilityMetricV1 | None:
    """Summarize one quantity across the valid runs of a collection.

    Rejected runs are skipped, as are valid runs that did not observe
    ``quantity`` — a run may legitimately yield a frequency but no usable SNR.
    Returns ``None`` when fewer than two valid runs observed the quantity, so a
    caller can report the absence rather than a statistic built on one number.
    """
    values: list[float] = []
    run_ids: list[str] = []
    for run in runs:
        if not run.valid:
            continue
        observed = run.feature(quantity)
        if observed is None:
            continue
        if observed.unit != unit:
            raise RepeatabilityStatisticsError(
                GrantReadinessErrorCode.INCOMPATIBLE_MEASUREMENT_UNITS,
                (f"run {run.run_id} reports {quantity} in {observed.unit}, not {unit}"),
                {"quantity": quantity, "run_id": run.run_id, "unit": observed.unit},
            )
        values.append(observed.value)
        run_ids.append(run.run_id)

    if len(values) < MINIMUM_SAMPLE_COUNT:
        return None

    return summarize_repeatability(
        values,
        quantity=quantity,
        unit=unit,
        source_run_ids=run_ids,
        metric_id=metric_id,
    )


def summarize_group_spread(
    values: Sequence[float],
    *,
    group_kind: str,
    group_ids: Sequence[str],
    quantity: str,
    unit: str,
) -> GroupSpreadV1:
    """Summarize one quantity across groups, where each sample is a group.

    Between-attachment variation (DO-103 E3) is the spread of per-attachment
    means, not of runs. The arithmetic is identical to
    :func:`summarize_repeatability` and is delegated to the same DO-085 helper;
    what differs is what a sample *is*, and the returned record says so rather
    than leaving ``source_run_ids`` naming things that are not runs.

    Args:
        values: One value per group, in the same order as ``group_ids``.
            Typically each is that group's own mean.
        group_kind: What the groups are, e.g. ``attachment``.
        group_ids: The group identifiers the values came from.
        quantity: What was observed, e.g. ``acoustic_transfer_magnitude``.
        unit: The unit of ``values``.

    Returns:
        A :class:`GroupSpreadV1`. Like every other record in this package it
        carries no acceptance flag: it reports how much the groups differed and
        says nothing about whether that difference is tolerable.

    Raises:
        RepeatabilityStatisticsError: ``NSF-301`` for fewer than two groups, a
            group-count mismatch, or a repeated group identifier, ``NSF-302``
            for a blank unit, ``NSF-303`` for a non-finite value, ``NSF-304``
            for a mean of zero.
    """
    numbers = _require_finite(values, quantity=quantity)
    ids = tuple(group_ids)

    if len(numbers) < MINIMUM_SAMPLE_COUNT:
        raise RepeatabilityStatisticsError(
            GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS,
            (
                f"{quantity} needs at least {MINIMUM_SAMPLE_COUNT} {group_kind} "
                f"groups to summarize, got {len(numbers)}"
            ),
            {
                "quantity": quantity,
                "group_kind": group_kind,
                "group_count": len(numbers),
            },
        )

    if len(ids) != len(numbers):
        raise RepeatabilityStatisticsError(
            GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS,
            (
                f"{quantity} has {len(numbers)} group values but {len(ids)} "
                f"{group_kind} identifiers; every number must name its group"
            ),
            {"quantity": quantity, "values": len(numbers), "groups": len(ids)},
        )

    if len(set(ids)) != len(ids):
        raise RepeatabilityStatisticsError(
            GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS,
            f"{quantity} cites the same {group_kind} more than once",
            {"quantity": quantity, "group_kind": group_kind},
        )

    if not unit or not unit.strip():
        raise RepeatabilityStatisticsError(
            GrantReadinessErrorCode.INCOMPATIBLE_MEASUREMENT_UNITS,
            f"{quantity} must declare a unit",
            {"quantity": quantity},
        )

    mean = sum(numbers) / len(numbers)
    if abs(mean) < ZERO_MEAN_EPSILON:
        raise RepeatabilityStatisticsError(
            GrantReadinessErrorCode.UNDEFINED_COEFFICIENT_OF_VARIATION,
            (
                f"{quantity} has a mean of zero across {group_kind} groups, so "
                "its coefficient of variation is undefined and cannot be reported"
            ),
            {"quantity": quantity, "mean": mean},
        )

    delegated = compute_repeatability(numbers)

    return GroupSpreadV1(
        group_kind=group_kind,
        quantity=quantity,
        unit=unit,
        group_count=delegated.n_measurements,
        group_ids=ids,
        group_values=tuple(numbers),
        mean=delegated.mean,
        median=calculate_median(numbers),
        standard_deviation=delegated.repeatability_std_dev,
        coefficient_of_variation_pct=delegated.coefficient_of_variation_pct,
        minimum=min(numbers),
        maximum=max(numbers),
        range_value=delegated.range_value,
        median_absolute_deviation=calculate_median_absolute_deviation(numbers),
    )


__all__ = [
    "ZERO_MEAN_EPSILON",
    "MINIMUM_SAMPLE_COUNT",
    "calculate_median",
    "calculate_median_absolute_deviation",
    "calculate_coefficient_of_variation",
    "summarize_repeatability",
    "summarize_runs",
    "summarize_group_spread",
]
