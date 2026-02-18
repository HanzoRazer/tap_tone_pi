"""Tests for core statistics module (Phase 3.2)."""

import math
import pytest

from tap_tone_pi.core.statistics import (
    COVERAGE_FACTOR_95,
    COVERAGE_FACTOR_99,
    COVERAGE_FACTOR_68,
    TypeAResult,
    RepeatabilityMetrics,
    UncertaintyBudget,
    compute_type_a_uncertainty,
    compute_repeatability,
    combine_uncertainties,
    propagate_uncertainty_linear,
    propagate_uncertainty_relative,
    is_measurement_outlier,
    compute_weighted_mean,
)


class TestTypeAUncertainty:
    """Tests for Type A uncertainty evaluation."""

    def test_basic_computation(self):
        """Should compute mean, std dev, and uncertainty correctly."""
        measurements = [10.0, 10.0, 10.0, 10.0, 10.0]
        result = compute_type_a_uncertainty(measurements)

        assert result.mean == 10.0
        assert result.std_dev == 0.0
        assert result.std_uncertainty == 0.0
        assert result.n_measurements == 5

    def test_with_variation(self):
        """Should compute correct statistics with variation."""
        # Known values: mean=10, std_dev=1
        measurements = [9.0, 10.0, 11.0]
        result = compute_type_a_uncertainty(measurements)

        assert abs(result.mean - 10.0) < 1e-10
        assert abs(result.std_dev - 1.0) < 1e-10
        # std_uncertainty = std_dev / sqrt(n) = 1 / sqrt(3) ≈ 0.577
        assert abs(result.std_uncertainty - 1.0 / math.sqrt(3)) < 1e-10

    def test_expanded_uncertainty(self):
        """Should compute expanded uncertainty with coverage factor."""
        measurements = [9.0, 10.0, 11.0]
        result = compute_type_a_uncertainty(measurements, coverage_factor=2.0)

        expected_u = 1.0 / math.sqrt(3)
        expected_U = 2.0 * expected_u
        assert abs(result.expanded_uncertainty - expected_U) < 1e-10

    def test_custom_coverage_factor(self):
        """Should accept custom coverage factor."""
        measurements = [9.0, 10.0, 11.0]
        result = compute_type_a_uncertainty(measurements, coverage_factor=3.0)

        assert result.coverage_factor == 3.0
        expected_U = 3.0 * result.std_uncertainty
        assert abs(result.expanded_uncertainty - expected_U) < 1e-10

    def test_degrees_of_freedom(self):
        """Degrees of freedom should be n-1."""
        measurements = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = compute_type_a_uncertainty(measurements)

        assert result.degrees_of_freedom == 4

    def test_min_max_range(self):
        """Should compute min, max, and range correctly."""
        measurements = [5.0, 10.0, 15.0]
        result = compute_type_a_uncertainty(measurements)

        assert result.min_value == 5.0
        assert result.max_value == 15.0
        assert result.range_value == 10.0

    def test_confidence_interval(self):
        """Should compute correct confidence interval."""
        measurements = [9.0, 10.0, 11.0]
        result = compute_type_a_uncertainty(measurements)

        lower, upper = result.confidence_interval
        assert lower < result.mean
        assert upper > result.mean
        assert abs((lower + upper) / 2 - result.mean) < 1e-10

    def test_relative_std_dev(self):
        """Should compute coefficient of variation correctly."""
        measurements = [100.0, 101.0, 99.0]
        result = compute_type_a_uncertainty(measurements)

        expected_cv = result.std_dev / result.mean
        assert abs(result.relative_std_dev - expected_cv) < 1e-10

    def test_format_value(self):
        """Should format as 'mean ± uncertainty' string."""
        measurements = [10.0, 10.1, 9.9]
        result = compute_type_a_uncertainty(measurements)
        formatted = result.format_value(precision=2)

        assert "±" in formatted
        assert "10." in formatted

    def test_to_dict_serialization(self):
        """Should serialize to dictionary."""
        measurements = [10.0, 10.1, 9.9]
        result = compute_type_a_uncertainty(measurements)
        d = result.to_dict()

        assert "mean" in d
        assert "std_dev" in d
        assert "std_uncertainty" in d
        assert "expanded_uncertainty" in d
        assert "confidence_interval" in d

    def test_rejects_single_measurement(self):
        """Should reject single measurement."""
        with pytest.raises(ValueError, match="at least 2"):
            compute_type_a_uncertainty([10.0])

    def test_rejects_empty_list(self):
        """Should reject empty list."""
        with pytest.raises(ValueError, match="at least 2"):
            compute_type_a_uncertainty([])


class TestRepeatability:
    """Tests for repeatability metrics."""

    def test_basic_computation(self):
        """Should compute repeatability metrics correctly."""
        measurements = [10.0, 10.0, 10.0, 10.0, 10.0]
        result = compute_repeatability(measurements)

        assert result.mean == 10.0
        assert result.repeatability_std_dev == 0.0
        assert result.coefficient_of_variation_pct == 0.0

    def test_repeatability_limit(self):
        """Repeatability limit should be 2.8 × std_dev (ISO 5725-2)."""
        measurements = [9.0, 10.0, 11.0]
        result = compute_repeatability(measurements)

        expected_r = 2.8 * result.repeatability_std_dev
        assert abs(result.repeatability_limit - expected_r) < 1e-10

    def test_coefficient_of_variation(self):
        """CV should be 100% × std/mean."""
        measurements = [100.0, 101.0, 99.0, 100.0]
        result = compute_repeatability(measurements)

        expected_cv = 100.0 * result.repeatability_std_dev / result.mean
        assert abs(result.coefficient_of_variation_pct - expected_cv) < 1e-10

    def test_acceptable_threshold(self):
        """Should flag measurements as acceptable based on CV threshold."""
        # Low variation - should be acceptable
        low_var = [100.0, 100.1, 99.9, 100.0]
        result_low = compute_repeatability(low_var, acceptance_threshold_pct=1.0)
        assert result_low.is_acceptable

        # High variation - should not be acceptable
        high_var = [100.0, 110.0, 90.0, 100.0]
        result_high = compute_repeatability(high_var, acceptance_threshold_pct=1.0)
        assert not result_high.is_acceptable

    def test_to_dict(self):
        """Should serialize to dictionary."""
        measurements = [10.0, 10.1, 9.9]
        result = compute_repeatability(measurements)
        d = result.to_dict()

        assert "repeatability_std_dev" in d
        assert "repeatability_limit" in d
        assert "coefficient_of_variation_pct" in d
        assert "is_acceptable" in d


class TestCombineUncertainties:
    """Tests for uncertainty combination."""

    def test_root_sum_of_squares(self):
        """Should combine using root-sum-of-squares."""
        u1, u2, u3 = 3.0, 4.0, 0.0
        result = combine_uncertainties(u1, u2, u3)

        # 3² + 4² = 25, sqrt(25) = 5
        assert abs(result - 5.0) < 1e-10

    def test_single_uncertainty(self):
        """Single uncertainty should return itself."""
        result = combine_uncertainties(5.0)
        assert abs(result - 5.0) < 1e-10

    def test_empty_input(self):
        """Empty input should return zero."""
        result = combine_uncertainties()
        assert result == 0.0

    def test_correlated_uncertainties(self):
        """Should handle correlated uncertainties for n=2."""
        u1, u2 = 3.0, 4.0

        # Positive correlation increases combined uncertainty
        result_pos = combine_uncertainties(u1, u2, correlation=0.5)
        result_uncorr = combine_uncertainties(u1, u2, correlation=0.0)
        result_neg = combine_uncertainties(u1, u2, correlation=-0.5)

        assert result_pos > result_uncorr
        assert result_neg < result_uncorr

    def test_correlation_requires_two_inputs(self):
        """Correlation only valid for exactly 2 inputs."""
        with pytest.raises(ValueError, match="2 inputs"):
            combine_uncertainties(1.0, 2.0, 3.0, correlation=0.5)


class TestPropagateUncertainty:
    """Tests for uncertainty propagation."""

    def test_linear_propagation(self):
        """Should propagate through linear function."""
        # y = 2*a + 3*b, with u(a)=0.1, u(b)=0.2
        coeffs = [2, 3]
        uncs = [0.1, 0.2]
        result = propagate_uncertainty_linear(coeffs, uncs)

        # u(y) = sqrt((2*0.1)² + (3*0.2)²) = sqrt(0.04 + 0.36) = sqrt(0.4)
        expected = math.sqrt(0.04 + 0.36)
        assert abs(result - expected) < 1e-10

    def test_linear_propagation_length_mismatch(self):
        """Should reject mismatched lengths."""
        with pytest.raises(ValueError, match="Length mismatch"):
            propagate_uncertainty_linear([1, 2, 3], [0.1, 0.2])

    def test_relative_propagation(self):
        """Should propagate relative uncertainties for products."""
        value = 100.0
        rel_uncs = [0.01, 0.02]  # 1% and 2%

        result = propagate_uncertainty_relative(value, rel_uncs)

        # u_rel = sqrt(0.01² + 0.02²) = sqrt(0.0005) ≈ 0.0224
        # u_abs = 100 * 0.0224 ≈ 2.24
        expected_rel = math.sqrt(0.01**2 + 0.02**2)
        expected_abs = 100.0 * expected_rel
        assert abs(result - expected_abs) < 1e-10


class TestUncertaintyBudget:
    """Tests for uncertainty budget tracking."""

    def test_add_components(self):
        """Should add components to budget."""
        budget = UncertaintyBudget()
        budget.add_component("Repeatability", 0.3, "Hz", "Type A")
        budget.add_component("Calibration", 0.4, "Hz", "Type B")

        assert len(budget.components) == 2

    def test_combined_uncertainty(self):
        """Should compute combined uncertainty correctly."""
        budget = UncertaintyBudget()
        budget.add_component("u1", 3.0, "Hz")
        budget.add_component("u2", 4.0, "Hz")

        # sqrt(3² + 4²) = 5
        assert abs(budget.combined_uncertainty - 5.0) < 1e-10

    def test_expanded_uncertainty(self):
        """Should compute expanded uncertainty with coverage factor."""
        budget = UncertaintyBudget()
        budget.add_component("u1", 3.0, "Hz")
        budget.add_component("u2", 4.0, "Hz")

        U = budget.expanded_uncertainty(2.0)
        assert abs(U - 10.0) < 1e-10  # 2 × 5 = 10

    def test_contribution_percentages(self):
        """Should compute contribution percentages."""
        budget = UncertaintyBudget()
        budget.add_component("u1", 3.0, "Hz")  # 9/25 = 36%
        budget.add_component("u2", 4.0, "Hz")  # 16/25 = 64%

        budget.compute_contributions()

        contrib_1 = budget.components[0]["contribution_pct"]
        contrib_2 = budget.components[1]["contribution_pct"]

        assert abs(contrib_1 - 36.0) < 0.1
        assert abs(contrib_2 - 64.0) < 0.1

    def test_to_dict(self):
        """Should serialize to dictionary."""
        budget = UncertaintyBudget()
        budget.add_component("Repeatability", 0.3, "Hz")
        d = budget.to_dict()

        assert "components" in d
        assert "combined_uncertainty" in d
        assert "expanded_uncertainty_k2" in d

    def test_format_report(self):
        """Should format human-readable report."""
        budget = UncertaintyBudget()
        budget.add_component("Repeatability", 0.3, "Hz", "Type A")
        budget.add_component("Calibration", 0.4, "Hz", "Type B")

        report = budget.format_report(result_value=185.0, unit="Hz")

        assert "Uncertainty Budget" in report
        assert "Repeatability" in report
        assert "Calibration" in report
        assert "185" in report


class TestOutlierDetection:
    """Tests for outlier detection."""

    def test_non_outlier(self):
        """Values within threshold should not be outliers."""
        assert not is_measurement_outlier(10.0, 10.0, 1.0, threshold_sigma=3.0)
        assert not is_measurement_outlier(12.0, 10.0, 1.0, threshold_sigma=3.0)  # 2σ

    def test_outlier(self):
        """Values beyond threshold should be outliers."""
        # 4σ away - should be flagged at 3σ threshold
        assert is_measurement_outlier(14.0, 10.0, 1.0, threshold_sigma=3.0)

    def test_boundary_case(self):
        """Test behavior at exactly threshold."""
        # Exactly 3σ - should NOT be outlier (> threshold, not >=)
        # 10 + 3*1 = 13, so 13.0 is exactly at boundary
        result = is_measurement_outlier(13.0, 10.0, 1.0, threshold_sigma=3.0)
        # Should be False since |13-10| = 3 is not > 3
        assert not result

        # Just beyond threshold
        assert is_measurement_outlier(13.01, 10.0, 1.0, threshold_sigma=3.0)

    def test_zero_uncertainty(self):
        """Should handle zero uncertainty gracefully."""
        result = is_measurement_outlier(10.0, 10.0, 0.0)
        assert not result  # Can't determine outlier with zero uncertainty


class TestWeightedMean:
    """Tests for uncertainty-weighted mean."""

    def test_equal_weights(self):
        """Equal uncertainties should give arithmetic mean."""
        values = [10.0, 20.0]
        uncertainties = [1.0, 1.0]
        mean, u_mean = compute_weighted_mean(values, uncertainties)

        assert abs(mean - 15.0) < 1e-10

    def test_unequal_weights(self):
        """Lower uncertainty should have more weight."""
        values = [10.0, 20.0]
        uncertainties = [1.0, 2.0]  # First is more precise
        mean, u_mean = compute_weighted_mean(values, uncertainties)

        # Weighted toward 10.0
        assert mean < 15.0
        # w1 = 1/1 = 1, w2 = 1/4 = 0.25
        # mean = (1*10 + 0.25*20) / 1.25 = 15 / 1.25 = 12
        assert abs(mean - 12.0) < 1e-10

    def test_uncertainty_of_mean(self):
        """Should compute uncertainty of weighted mean correctly."""
        values = [10.0, 20.0]
        uncertainties = [1.0, 1.0]
        mean, u_mean = compute_weighted_mean(values, uncertainties)

        # u(mean) = 1 / sqrt(w1 + w2) = 1 / sqrt(2) ≈ 0.707
        expected = 1.0 / math.sqrt(2)
        assert abs(u_mean - expected) < 1e-10

    def test_length_mismatch_raises(self):
        """Should reject mismatched lengths."""
        with pytest.raises(ValueError, match="Length mismatch"):
            compute_weighted_mean([1.0, 2.0], [0.1])

    def test_zero_uncertainty_raises(self):
        """Should reject zero uncertainties."""
        with pytest.raises(ValueError, match="positive"):
            compute_weighted_mean([1.0, 2.0], [0.1, 0.0])


class TestCoverageFactors:
    """Tests for coverage factor constants."""

    def test_coverage_factor_values(self):
        """Coverage factors should have correct values."""
        assert COVERAGE_FACTOR_68 == 1.0
        assert COVERAGE_FACTOR_95 == 2.0
        assert COVERAGE_FACTOR_99 == 2.58


class TestRealisticScenarios:
    """Tests with realistic tap tone measurement scenarios."""

    def test_frequency_repeatability(self):
        """Realistic frequency repeatability assessment."""
        # Typical tap tone frequency measurements
        freq_readings = [185.2, 185.4, 185.1, 185.3, 185.2]

        result = compute_type_a_uncertainty(freq_readings)

        # Mean should be around 185.24 Hz
        assert abs(result.mean - 185.24) < 0.01
        # Uncertainty should be small (< 0.2 Hz for k=2)
        assert result.expanded_uncertainty < 0.2

    def test_amplitude_uncertainty_budget(self):
        """Build uncertainty budget for amplitude measurement."""
        budget = UncertaintyBudget()

        # Type A: Repeatability from multiple taps
        budget.add_component("Repeatability", 0.02, "V", "Type A", degrees_of_freedom=4)

        # Type B: Calibration uncertainty
        budget.add_component("Microphone cal", 0.01, "V", "Type B")

        # Type B: ADC resolution
        budget.add_component("ADC resolution", 0.005, "V", "Type B")

        # Combined should be reasonable
        u_c = budget.combined_uncertainty
        assert u_c > 0.02  # At least as large as biggest component
        assert u_c < 0.03  # But not too large

    def test_session_comparison_uncertainty(self):
        """Combine uncertainties for before/after comparison."""
        # Before measurement
        freq_before = 185.0
        u_before = 0.3

        # After measurement
        freq_after = 183.5
        u_after = 0.25

        # Combined uncertainty for difference
        u_diff = combine_uncertainties(u_before, u_after)

        # Difference
        delta = freq_after - freq_before  # -1.5 Hz

        # Significance: |delta| > k × u_diff for k=2?
        is_significant = abs(delta) > 2.0 * u_diff

        # 1.5 > 2 × 0.39 ≈ 0.78? Yes, significant
        assert is_significant
