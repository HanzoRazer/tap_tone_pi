"""Preliminary repeatability statistics (DO-102, Commit 4).

Every expected value below is hand-checkable. The suite also pins the two
things the grant layer refuses to inherit from DO-085: the acceptance verdict,
and the zero-mean coefficient-of-variation sentinel.
"""

from __future__ import annotations

import math

import pytest

from tap_tone_pi.core.statistics import compute_repeatability
from tap_tone_pi.grant_readiness import (
    EvidenceOrigin,
    GrantReadinessErrorCode,
    ObservedFeatureV1,
    PreliminaryExperimentRunV1,
    RejectionReason,
    RepeatabilityMetricV1,
)
from tap_tone_pi.grant_readiness.errors import RepeatabilityStatisticsError
from tap_tone_pi.grant_readiness.statistics import (
    MINIMUM_SAMPLE_COUNT,
    calculate_coefficient_of_variation,
    calculate_median,
    calculate_median_absolute_deviation,
    summarize_repeatability,
    summarize_runs,
)

UTC_NOW = "2026-08-09T12:00:00+00:00"

# A hand-checkable sample. n=5, sum=1225, mean=245.0.
# Deviations: -2, -1, 0, +1, +2 -> sum of squares 10 -> sample variance 10/4
# = 2.5 -> sample SD = sqrt(2.5) = 1.5811388300841898.
SAMPLE = [243.0, 244.0, 245.0, 246.0, 247.0]
SAMPLE_MEAN = 245.0
SAMPLE_SD = math.sqrt(2.5)
SAMPLE_CV_PCT = 100.0 * SAMPLE_SD / SAMPLE_MEAN
SAMPLE_RUN_IDS = ("run-001", "run-002", "run-003", "run-004", "run-005")


def make_run(
    run_id: str, *, valid: bool = True, **features
) -> PreliminaryExperimentRunV1:
    observed = tuple(
        ObservedFeatureV1(quantity, unit, value)
        for quantity, (unit, value) in features.items()
    )
    return PreliminaryExperimentRunV1(
        run_id=run_id,
        experiment_id="exp-001",
        captured_at=UTC_NOW,
        evidence_origin=EvidenceOrigin.FIXTURE,
        valid=valid,
        rejection_reason=None if valid else RejectionReason.CLIPPING,
        source_artifact_ids=(f"wav-{run_id}",),
        observed_features=observed,
    )


# ---------------------------------------------------------------------------
# Median and MAD
# ---------------------------------------------------------------------------


class TestMedian:
    def test_odd_count(self):
        assert calculate_median([3.0, 1.0, 2.0]) == 2.0

    def test_even_count_averages_the_middle_pair(self):
        assert calculate_median([1.0, 2.0, 3.0, 4.0]) == 2.5

    def test_single_value(self):
        assert calculate_median([7.0]) == 7.0

    def test_empty_rejected(self):
        with pytest.raises(RepeatabilityStatisticsError) as exc:
            calculate_median([])
        assert exc.value.code is GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS

    def test_sample_median(self):
        assert calculate_median(SAMPLE) == 245.0


class TestMedianAbsoluteDeviation:
    def test_hand_checked(self):
        # median 3; deviations 2,1,0,1,2; median of those is 1.
        assert calculate_median_absolute_deviation([1.0, 2.0, 3.0, 4.0, 5.0]) == 1.0

    def test_all_equal_is_zero(self):
        assert calculate_median_absolute_deviation([5.0, 5.0, 5.0]) == 0.0

    def test_is_unscaled(self):
        # No 1.4826 normality factor: that assumption is not established here.
        assert calculate_median_absolute_deviation([1.0, 2.0, 3.0, 4.0, 5.0]) != (
            pytest.approx(1.4826)
        )

    def test_resists_a_single_outlier(self):
        assert calculate_median_absolute_deviation([1.0, 2.0, 3.0, 4.0, 500.0]) == 1.0


# ---------------------------------------------------------------------------
# Coefficient of variation
# ---------------------------------------------------------------------------


class TestCoefficientOfVariation:
    def test_matches_hand_calculation(self):
        assert calculate_coefficient_of_variation(SAMPLE) == pytest.approx(
            SAMPLE_CV_PCT, rel=1e-12
        )

    def test_all_equal_values_give_zero(self):
        assert calculate_coefficient_of_variation([5.0, 5.0, 5.0]) == 0.0

    def test_zero_mean_rejected(self):
        with pytest.raises(RepeatabilityStatisticsError) as exc:
            calculate_coefficient_of_variation([-1.0, 0.0, 1.0])
        assert exc.value.code is (
            GrantReadinessErrorCode.UNDEFINED_COEFFICIENT_OF_VARIATION
        )

    def test_zero_mean_sentinel_is_not_passed_through(self):
        # The DO-085 helper reports 0.0 here, which is indistinguishable from
        # perfect repeatability. The grant layer must not publish that.
        assert (
            compute_repeatability([-1.0, 0.0, 1.0]).coefficient_of_variation_pct == 0.0
        )
        with pytest.raises(RepeatabilityStatisticsError):
            calculate_coefficient_of_variation([-1.0, 0.0, 1.0])

    def test_single_value_rejected(self):
        with pytest.raises(RepeatabilityStatisticsError) as exc:
            calculate_coefficient_of_variation([245.0])
        assert exc.value.code is GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_rejected(self, bad):
        with pytest.raises(RepeatabilityStatisticsError) as exc:
            calculate_coefficient_of_variation([1.0, bad])
        assert exc.value.code is GrantReadinessErrorCode.NON_FINITE_STATISTIC

    def test_negative_mean_uses_magnitude(self):
        # CV scales by |mean|, so a sign flip must not change it.
        positive = calculate_coefficient_of_variation([10.0, 12.0])
        negative = calculate_coefficient_of_variation([-10.0, -12.0])
        assert positive == pytest.approx(negative)


# ---------------------------------------------------------------------------
# summarize_repeatability
# ---------------------------------------------------------------------------


class TestSummarizeRepeatability:
    def _metric(self, **overrides) -> RepeatabilityMetricV1:
        kwargs = {
            "quantity": "dominant_frequency",
            "unit": "Hz",
            "source_run_ids": SAMPLE_RUN_IDS,
        }
        kwargs.update(overrides)
        return summarize_repeatability(SAMPLE, **kwargs)

    def test_every_statistic_is_hand_checkable(self):
        metric = self._metric()
        assert metric.sample_count == 5
        assert metric.mean == pytest.approx(245.0, abs=1e-12)
        assert metric.median == 245.0
        assert metric.standard_deviation == pytest.approx(SAMPLE_SD, rel=1e-12)
        assert metric.coefficient_of_variation_pct == pytest.approx(
            SAMPLE_CV_PCT, rel=1e-12
        )
        assert metric.minimum == 243.0
        assert metric.maximum == 247.0
        assert metric.range_value == pytest.approx(4.0, abs=1e-12)
        # Deviations from the median are 2,1,0,1,2 -> MAD 1.
        assert metric.median_absolute_deviation == 1.0

    def test_delegates_to_do085_for_the_four_shared_quantities(self):
        metric = self._metric()
        delegated = compute_repeatability(SAMPLE)
        assert metric.mean == delegated.mean
        assert metric.standard_deviation == delegated.repeatability_std_dev
        assert metric.coefficient_of_variation_pct == (
            delegated.coefficient_of_variation_pct
        )
        assert metric.range_value == delegated.range_value

    def test_standard_deviation_is_bessel_corrected(self):
        metric = summarize_repeatability(
            [1.0, 2.0, 3.0],
            quantity="q",
            unit="u",
            source_run_ids=("a", "b", "c"),
        )
        # Sample SD of [1,2,3] is exactly 1.0; the population SD is 0.8165.
        assert metric.standard_deviation == pytest.approx(1.0, abs=1e-12)

    def test_carries_no_acceptance_verdict(self):
        metric = self._metric()
        assert not hasattr(metric, "is_acceptable")
        assert not hasattr(metric, "acceptance_threshold_pct")
        assert "is_acceptable" not in metric.to_dict()

    def test_names_every_source_run(self):
        metric = self._metric()
        assert metric.source_run_ids == SAMPLE_RUN_IDS
        assert metric.sample_count == len(metric.source_run_ids)

    def test_default_metric_id_derives_from_quantity(self):
        assert self._metric().metric_id == "metric-dominant_frequency"

    def test_explicit_metric_id_is_used(self):
        assert self._metric(metric_id="m-9").metric_id == "m-9"

    def test_two_observations_is_enough(self):
        assert MINIMUM_SAMPLE_COUNT == 2
        metric = summarize_repeatability(
            [10.0, 12.0], quantity="q", unit="u", source_run_ids=("a", "b")
        )
        assert metric.sample_count == 2
        assert metric.mean == 11.0
        assert metric.median == 11.0

    def test_all_equal_values_give_zero_spread(self):
        metric = summarize_repeatability(
            [5.0, 5.0, 5.0], quantity="q", unit="u", source_run_ids=("a", "b", "c")
        )
        assert metric.standard_deviation == 0.0
        assert metric.coefficient_of_variation_pct == 0.0
        assert metric.range_value == 0.0
        assert metric.median_absolute_deviation == 0.0

    def test_single_observation_rejected(self):
        with pytest.raises(RepeatabilityStatisticsError) as exc:
            summarize_repeatability(
                [245.0], quantity="q", unit="Hz", source_run_ids=("a",)
            )
        assert exc.value.code is GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS

    def test_run_count_mismatch_rejected(self):
        with pytest.raises(RepeatabilityStatisticsError) as exc:
            summarize_repeatability(
                SAMPLE, quantity="q", unit="Hz", source_run_ids=("a", "b")
            )
        assert exc.value.code is GrantReadinessErrorCode.INSUFFICIENT_VALID_MEASUREMENTS

    def test_duplicate_source_run_rejected(self):
        with pytest.raises(RepeatabilityStatisticsError):
            summarize_repeatability(
                [1.0, 2.0], quantity="q", unit="Hz", source_run_ids=("a", "a")
            )

    def test_missing_unit_rejected(self):
        with pytest.raises(RepeatabilityStatisticsError) as exc:
            summarize_repeatability(
                [1.0, 2.0], quantity="q", unit="  ", source_run_ids=("a", "b")
            )
        assert exc.value.code is GrantReadinessErrorCode.INCOMPATIBLE_MEASUREMENT_UNITS

    def test_non_finite_observation_rejected(self):
        with pytest.raises(RepeatabilityStatisticsError) as exc:
            summarize_repeatability(
                [1.0, float("nan")], quantity="q", unit="Hz", source_run_ids=("a", "b")
            )
        assert exc.value.code is GrantReadinessErrorCode.NON_FINITE_STATISTIC

    def test_boolean_observation_rejected(self):
        with pytest.raises(RepeatabilityStatisticsError):
            summarize_repeatability(
                [1.0, True], quantity="q", unit="Hz", source_run_ids=("a", "b")
            )

    def test_zero_mean_rejected(self):
        with pytest.raises(RepeatabilityStatisticsError) as exc:
            summarize_repeatability(
                [-1.0, 1.0], quantity="q", unit="Hz", source_run_ids=("a", "b")
            )
        assert exc.value.code is (
            GrantReadinessErrorCode.UNDEFINED_COEFFICIENT_OF_VARIATION
        )

    def test_every_statistic_is_finite(self):
        metric = self._metric()
        for key, value in metric.to_dict().items():
            if isinstance(value, float):
                assert math.isfinite(value), key


# ---------------------------------------------------------------------------
# summarize_runs
# ---------------------------------------------------------------------------


class TestSummarizeRuns:
    def _runs(self):
        return (
            make_run("run-001", dominant_frequency=("Hz", 244.0), snr=("dB", 30.0)),
            make_run("run-002", dominant_frequency=("Hz", 246.0), snr=("dB", 32.0)),
            make_run("run-003", valid=False, dominant_frequency=("Hz", 999.0)),
        )

    def test_rejected_runs_are_excluded(self):
        metric = summarize_runs(self._runs(), quantity="dominant_frequency", unit="Hz")
        assert metric.sample_count == 2
        assert metric.source_run_ids == ("run-001", "run-002")
        assert metric.mean == 245.0

    def test_a_rejected_run_cannot_move_a_statistic(self):
        with_rejected = summarize_runs(
            self._runs(), quantity="dominant_frequency", unit="Hz"
        )
        without = summarize_runs(
            self._runs()[:2], quantity="dominant_frequency", unit="Hz"
        )
        assert with_rejected.mean == without.mean
        assert with_rejected.standard_deviation == without.standard_deviation

    def test_second_quantity_summarized_independently(self):
        metric = summarize_runs(self._runs(), quantity="snr", unit="dB")
        assert metric.mean == 31.0
        assert metric.unit == "dB"

    def test_absent_quantity_returns_none(self):
        assert summarize_runs(self._runs(), quantity="coherence", unit="") is None

    def test_runs_missing_the_quantity_are_skipped(self):
        runs = (
            make_run("run-001", dominant_frequency=("Hz", 244.0)),
            make_run("run-002"),
            make_run("run-003", dominant_frequency=("Hz", 246.0)),
        )
        metric = summarize_runs(runs, quantity="dominant_frequency", unit="Hz")
        assert metric.source_run_ids == ("run-001", "run-003")

    def test_one_valid_observation_returns_none(self):
        runs = (
            make_run("run-001", dominant_frequency=("Hz", 244.0)),
            make_run("run-002", valid=False, dominant_frequency=("Hz", 246.0)),
        )
        assert summarize_runs(runs, quantity="dominant_frequency", unit="Hz") is None

    def test_no_valid_runs_returns_none(self):
        runs = (make_run("run-001", valid=False, dominant_frequency=("Hz", 244.0)),)
        assert summarize_runs(runs, quantity="dominant_frequency", unit="Hz") is None

    def test_incompatible_units_rejected(self):
        runs = (
            make_run("run-001", dominant_frequency=("Hz", 244.0)),
            make_run("run-002", dominant_frequency=("kHz", 0.246)),
        )
        with pytest.raises(RepeatabilityStatisticsError) as exc:
            summarize_runs(runs, quantity="dominant_frequency", unit="Hz")
        assert exc.value.code is GrantReadinessErrorCode.INCOMPATIBLE_MEASUREMENT_UNITS
