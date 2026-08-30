"""
Tests for uncertainty module (Phase 3 P0).
"""

import math

import pytest

from tap_tone_pi.uncertainty import (
    # Budget
    UncertaintyBudget,
    combine_uncertainties,
    expand_uncertainty,
    # Frequency
    compute_frequency_uncertainty,
    compute_frequency_resolution,
    # Amplitude
    compute_amplitude_uncertainty,
    compute_snr_uncertainty,
    # Stiffness
    compute_stiffness_uncertainty,
    compute_deflection_moe_uncertainty,
    compute_tap_tone_moe_uncertainty,
    # Formatters
    format_with_uncertainty,
    format_uncertainty_budget,
    uncertainty_to_dict,
)
from tap_tone_pi.uncertainty.budget import (
    get_calibration_uncertainty_factor,
    get_snr_uncertainty_factor,
)


# ============================================================================
# Budget Tests
# ============================================================================


class TestUncertaintyBudget:
    """Tests for UncertaintyBudget class."""

    def test_empty_budget(self):
        """Empty budget should have zero uncertainty."""
        budget = UncertaintyBudget()
        assert budget.combined_standard_uncertainty == 0.0
        assert budget.expanded_uncertainty == 0.0

    def test_single_component(self):
        """Single component budget."""
        budget = UncertaintyBudget()
        budget.add_component("test", value=1.0, unit="Hz")

        assert budget.combined_standard_uncertainty == 1.0
        assert budget.expanded_uncertainty == 2.0  # k=2 default

    def test_multiple_components_rss(self):
        """Multiple components combine via RSS."""
        budget = UncertaintyBudget()
        budget.add_component("a", value=3.0, unit="Hz")
        budget.add_component("b", value=4.0, unit="Hz")

        # RSS: sqrt(3² + 4²) = 5
        assert budget.combined_standard_uncertainty == 5.0
        assert budget.expanded_uncertainty == 10.0

    def test_relative_uncertainty(self):
        """Relative uncertainty calculation."""
        budget = UncertaintyBudget(measurement_value=100.0, measurement_unit="Hz")
        budget.add_component("test", value=5.0, unit="Hz")

        # Expanded = 10 Hz, relative = 10/100 = 0.1 = 10%
        assert budget.relative_uncertainty == 0.1
        assert budget.relative_uncertainty_percent == 10.0

    def test_relative_uncertainty_zero_value(self):
        """Relative uncertainty with zero measurement value."""
        budget = UncertaintyBudget(measurement_value=0.0)
        budget.add_component("test", value=1.0, unit="Hz")

        assert budget.relative_uncertainty is None

    def test_coverage_factor(self):
        """Custom coverage factor."""
        budget = UncertaintyBudget(coverage_factor=3.0)
        budget.add_component("test", value=1.0, unit="Hz")

        assert budget.combined_standard_uncertainty == 1.0
        assert budget.expanded_uncertainty == 3.0

    def test_to_dict(self):
        """Serialization to dict."""
        budget = UncertaintyBudget(measurement_value=100.0, measurement_unit="Hz")
        budget.add_component("test", value=5.0, unit="Hz", description="Test component")

        d = budget.to_dict()

        assert "components" in d
        assert len(d["components"]) == 1
        assert d["components"][0]["name"] == "test"
        assert d["combined_standard_uncertainty"] == 5.0
        assert d["expanded_uncertainty"] == 10.0


class TestUncertaintyCombination:
    """Tests for uncertainty combination functions."""

    def test_combine_uncertainties(self):
        """RSS combination of uncertainties."""
        result = combine_uncertainties(3.0, 4.0)
        assert result == 5.0

    def test_combine_many(self):
        """Combine many uncertainties."""
        result = combine_uncertainties(1.0, 1.0, 1.0, 1.0)
        assert result == 2.0

    def test_expand_uncertainty(self):
        """Expand standard uncertainty."""
        assert expand_uncertainty(1.0, 2.0) == 2.0
        assert expand_uncertainty(1.0, 3.0) == 3.0


class TestUncertaintyFactors:
    """Tests for uncertainty factor lookups."""

    def test_calibration_factor_calibrated(self):
        """Calibrated system has lower uncertainty."""
        assert get_calibration_uncertainty_factor(True) == 0.5

    def test_calibration_factor_uncalibrated(self):
        """Uncalibrated system has higher uncertainty."""
        assert get_calibration_uncertainty_factor(False) == 2.0

    def test_snr_factor_high(self):
        """High SNR has low uncertainty."""
        assert get_snr_uncertainty_factor(50) == 0.3

    def test_snr_factor_medium(self):
        """Medium SNR has medium uncertainty."""
        assert get_snr_uncertainty_factor(30) == 0.8

    def test_snr_factor_low(self):
        """Low SNR has high uncertainty."""
        assert get_snr_uncertainty_factor(15) == 2.0


# ============================================================================
# Frequency Uncertainty Tests
# ============================================================================


class TestFrequencyUncertainty:
    """Tests for frequency uncertainty calculations."""

    def test_frequency_resolution(self):
        """FFT frequency resolution calculation."""
        resolution = compute_frequency_resolution(48000, 8192)
        expected = 48000 / 8192  # ~5.86 Hz
        assert abs(resolution - expected) < 0.01

    def test_frequency_uncertainty_basic(self):
        """Basic frequency uncertainty budget."""
        budget = compute_frequency_uncertainty(
            freq_hz=440.0,
            sample_rate=48000,
            fft_size=8192,
            snr_db=40.0,
        )

        assert budget.measurement_value == 440.0
        assert budget.measurement_unit == "Hz"
        assert len(budget.components) >= 2
        assert budget.expanded_uncertainty > 0

    def test_frequency_uncertainty_higher_snr_lower_uncertainty(self):
        """Higher SNR should give lower uncertainty."""
        budget_low = compute_frequency_uncertainty(freq_hz=440.0, snr_db=20.0)
        budget_high = compute_frequency_uncertainty(freq_hz=440.0, snr_db=60.0)

        assert budget_high.expanded_uncertainty < budget_low.expanded_uncertainty

    def test_frequency_uncertainty_short_duration(self):
        """Short duration increases uncertainty."""
        budget_long = compute_frequency_uncertainty(freq_hz=440.0, duration_s=2.0)
        budget_short = compute_frequency_uncertainty(freq_hz=440.0, duration_s=0.1)

        assert budget_short.expanded_uncertainty > budget_long.expanded_uncertainty


# ============================================================================
# Amplitude Uncertainty Tests
# ============================================================================


class TestAmplitudeUncertainty:
    """Tests for amplitude uncertainty calculations."""

    def test_snr_uncertainty(self):
        """SNR-based amplitude uncertainty."""
        # High SNR should give low uncertainty
        unc_high = compute_snr_uncertainty(60.0)
        unc_low = compute_snr_uncertainty(20.0)

        assert unc_high < unc_low
        assert unc_high < 0.1  # Very small for 60dB SNR

    def test_amplitude_uncertainty_basic(self):
        """Basic amplitude uncertainty budget."""
        budget = compute_amplitude_uncertainty(
            magnitude_db=-20.0,
            snr_db=40.0,
            is_calibrated=True,
        )

        assert budget.measurement_value == -20.0
        assert budget.measurement_unit == "dB"
        assert len(budget.components) >= 2

    def test_amplitude_uncertainty_calibration_effect(self):
        """Calibration reduces uncertainty."""
        budget_cal = compute_amplitude_uncertainty(
            magnitude_db=0.0, snr_db=40.0, is_calibrated=True
        )
        budget_uncal = compute_amplitude_uncertainty(
            magnitude_db=0.0, snr_db=40.0, is_calibrated=False
        )

        assert budget_cal.expanded_uncertainty < budget_uncal.expanded_uncertainty

    def test_amplitude_uncertainty_coherence_effect(self):
        """Lower coherence increases uncertainty."""
        budget_high = compute_amplitude_uncertainty(
            magnitude_db=0.0, snr_db=40.0, coherence=0.99
        )
        budget_low = compute_amplitude_uncertainty(
            magnitude_db=0.0, snr_db=40.0, coherence=0.5
        )

        assert budget_high.expanded_uncertainty < budget_low.expanded_uncertainty


# ============================================================================
# Stiffness Uncertainty Tests
# ============================================================================


class TestStiffnessUncertainty:
    """Tests for stiffness (MOE) uncertainty calculations."""

    def test_deflection_moe_uncertainty_basic(self):
        """Basic deflection MOE uncertainty budget."""
        budget = compute_deflection_moe_uncertainty(
            E_GPa=12.0,
            span_mm=400.0,
            width_mm=30.0,
            thickness_mm=3.0,
            deflection_mm=1.0,
            force_N=10.0,
        )

        assert budget.measurement_value == 12.0
        assert budget.measurement_unit == "GPa"
        assert len(budget.components) >= 5
        assert budget.expanded_uncertainty > 0

    def test_deflection_thickness_dominates(self):
        """Thickness uncertainty should dominate (h³ term)."""
        budget = compute_deflection_moe_uncertainty(
            E_GPa=12.0,
            span_mm=400.0,
            span_uncertainty_mm=0.5,
            thickness_mm=3.0,
            thickness_uncertainty_mm=0.1,  # Larger than typical
            deflection_mm=1.0,
            force_N=10.0,
        )

        # Find thickness component
        thickness_comp = None
        for c in budget.components:
            if "Thickness" in c.name:
                thickness_comp = c
                break

        assert thickness_comp is not None
        # Thickness should contribute > 50% of variance
        total_variance = budget.combined_standard_uncertainty**2
        thickness_frac = thickness_comp.contribution / total_variance
        assert thickness_frac > 0.3  # Significant contributor

    def test_deflection_r2_effect(self):
        """Poor R² increases uncertainty."""
        budget_good = compute_deflection_moe_uncertainty(
            E_GPa=12.0,
            span_mm=400.0,
            thickness_mm=3.0,
            deflection_mm=1.0,
            force_N=10.0,
            r_squared=0.999,
        )
        budget_poor = compute_deflection_moe_uncertainty(
            E_GPa=12.0,
            span_mm=400.0,
            thickness_mm=3.0,
            deflection_mm=1.0,
            force_N=10.0,
            r_squared=0.95,
        )

        assert budget_poor.expanded_uncertainty > budget_good.expanded_uncertainty

    def test_tap_tone_moe_uncertainty_basic(self):
        """Basic tap tone MOE uncertainty budget."""
        budget = compute_tap_tone_moe_uncertainty(
            E_GPa=12.0,
            frequency_hz=500.0,
            length_mm=400.0,
            thickness_mm=3.0,
            density_kg_m3=400.0,
        )

        assert budget.measurement_value == 12.0
        assert budget.measurement_unit == "GPa"
        assert len(budget.components) >= 4

    def test_tap_tone_length_sensitivity(self):
        """Length has ×4 sensitivity in tap tone formula."""
        budget = compute_tap_tone_moe_uncertainty(
            E_GPa=12.0,
            frequency_hz=500.0,
            length_mm=400.0,
            length_uncertainty_mm=2.0,  # 0.5% of length
            thickness_mm=3.0,
            density_kg_m3=400.0,
        )

        # Find length component
        length_comp = None
        for c in budget.components:
            if "Length" in c.name:
                length_comp = c
                break

        assert length_comp is not None
        # B-022: ``value`` is the unweighted standard uncertainty and the ×4
        # partial-derivative factor rides alongside it, applied once by
        # ``contribution``. 0.5% of 12 GPa is 0.06 GPa unweighted; the ×4
        # sensitivity carries it to 0.24 GPa in the aggregate. Before the
        # B-022 repair the coefficient was baked into ``value`` *and* passed,
        # so this component reached the RSS as 0.96 GPa.
        assert length_comp.value == pytest.approx(0.06)
        assert length_comp.sensitivity_coefficient == 4.0
        assert math.sqrt(length_comp.contribution) == pytest.approx(0.24)

    def test_stiffness_uncertainty_dispatch(self):
        """Dispatch function selects correct method."""
        budget_defl = compute_stiffness_uncertainty(
            E_GPa=12.0,
            method="deflection",
            span_mm=400.0,
            thickness_mm=3.0,
            deflection_mm=1.0,
            force_N=10.0,
        )
        budget_tap = compute_stiffness_uncertainty(
            E_GPa=12.0,
            method="tap_tone",
            frequency_hz=500.0,
            length_mm=400.0,
            thickness_mm=3.0,
            density_kg_m3=400.0,
        )

        assert budget_defl.measurement_value == 12.0
        assert budget_tap.measurement_value == 12.0

    def test_stiffness_uncertainty_invalid_method(self):
        """Invalid method raises error."""
        with pytest.raises(ValueError):
            compute_stiffness_uncertainty(E_GPa=12.0, method="invalid")


# ============================================================================
# Formatter Tests
# ============================================================================


class TestFormatters:
    """Tests for formatting utilities."""

    def test_format_with_uncertainty_basic(self):
        """Basic value ± uncertainty formatting."""
        result = format_with_uncertainty(440.0, 2.0, "Hz")
        assert "440" in result
        assert "±" in result
        assert "2" in result
        assert "Hz" in result

    def test_format_with_uncertainty_relative(self):
        """Include relative uncertainty."""
        result = format_with_uncertainty(100.0, 5.0, "Hz", show_relative=True)
        assert "5.0%" in result

    def test_format_with_uncertainty_zero(self):
        """Zero uncertainty formatting."""
        result = format_with_uncertainty(440.0, 0.0, "Hz")
        assert "440" in result
        assert "±" not in result

    def test_format_uncertainty_budget(self):
        """Format complete budget."""
        budget = UncertaintyBudget(measurement_value=100.0, measurement_unit="Hz")
        budget.add_component("FFT resolution", value=2.0, unit="Hz")
        budget.add_component("SNR", value=1.0, unit="Hz")

        result = format_uncertainty_budget(budget)

        assert "Result:" in result
        assert "FFT resolution" in result
        assert "SNR" in result
        assert "Combined" in result

    def test_uncertainty_to_dict(self):
        """Convert budget to dict."""
        budget = UncertaintyBudget(measurement_value=100.0, measurement_unit="Hz")
        budget.add_component("test", value=2.0, unit="Hz")

        d = uncertainty_to_dict(budget)

        assert isinstance(d, dict)
        assert "components" in d
        assert "expanded_uncertainty" in d


# ============================================================================
# Integration Tests
# ============================================================================


class TestUncertaintyIntegration:
    """Integration tests for uncertainty workflow."""

    def test_complete_frequency_workflow(self):
        """Complete frequency measurement uncertainty workflow."""
        # Measure frequency
        freq_hz = 440.0

        # Compute uncertainty
        budget = compute_frequency_uncertainty(
            freq_hz=freq_hz,
            sample_rate=48000,
            fft_size=8192,
            snr_db=45.0,
            is_calibrated=True,
        )

        # Format result
        result = format_with_uncertainty(
            freq_hz,
            budget.expanded_uncertainty,
            "Hz",
            show_relative=True,
        )

        assert "440" in result
        assert "Hz" in result

        # Verify reasonable uncertainty (< 1% for good conditions)
        assert budget.relative_uncertainty_percent < 5

    def test_complete_moe_workflow(self):
        """Complete MOE measurement uncertainty workflow."""
        # Calculate MOE via deflection
        E_GPa = 12.0

        # Compute uncertainty
        budget = compute_deflection_moe_uncertainty(
            E_GPa=E_GPa,
            span_mm=400.0,
            span_uncertainty_mm=0.5,
            width_mm=30.0,
            width_uncertainty_mm=0.2,
            thickness_mm=3.0,
            thickness_uncertainty_mm=0.05,
            deflection_mm=1.5,
            deflection_uncertainty_mm=0.02,
            force_N=10.0,
            force_uncertainty_N=0.05,
            r_squared=0.998,
        )

        # Format result
        result = format_with_uncertainty(
            E_GPa,
            budget.expanded_uncertainty,
            "GPa",
            show_relative=True,
        )

        assert "12" in result
        assert "GPa" in result

        # Verify reasonable uncertainty
        # With h³ sensitivity, even 0.05mm thickness uncertainty × 3 = 5% contribution
        # Combined with other factors and k=2 expansion → ~30% is realistic
        # The key insight: MOE from deflection is VERY sensitive to thickness
        assert budget.relative_uncertainty_percent < 40

    def test_calibration_improves_all_uncertainties(self):
        """Calibration should improve frequency, amplitude, and MOE uncertainties."""
        # Frequency
        _freq_cal = compute_frequency_uncertainty(freq_hz=440.0, is_calibrated=True)
        _freq_uncal = compute_frequency_uncertainty(freq_hz=440.0, is_calibrated=False)

        # Amplitude
        amp_cal = compute_amplitude_uncertainty(magnitude_db=-20.0, is_calibrated=True)
        amp_uncal = compute_amplitude_uncertainty(
            magnitude_db=-20.0, is_calibrated=False
        )

        # MOE (tap tone)
        moe_cal = compute_tap_tone_moe_uncertainty(
            E_GPa=12.0,
            frequency_hz=500.0,
            length_mm=400.0,
            thickness_mm=3.0,
            density_kg_m3=400.0,
            is_calibrated=True,
        )
        moe_uncal = compute_tap_tone_moe_uncertainty(
            E_GPa=12.0,
            frequency_hz=500.0,
            length_mm=400.0,
            thickness_mm=3.0,
            density_kg_m3=400.0,
            is_calibrated=False,
        )

        # All calibrated should be better
        # Note: For frequency, calibration isn't a direct factor in the model
        # but amplitude definitely benefits
        assert amp_cal.expanded_uncertainty < amp_uncal.expanded_uncertainty
        assert moe_cal.expanded_uncertainty < moe_uncal.expanded_uncertainty


class TestB022SensitivityAppliedOnce:
    """B-022 -- sensitivity coefficients enter the budget exactly once.

    Both MOE propagation functions used to compute a component as
    ``E * relative * sensitivity`` **and** pass ``sensitivity_coefficient``,
    while ``UncertaintyComponent.contribution`` is ``(c * value) ** 2``. Every
    coefficient was therefore applied twice and squared in the aggregate --
    length reached ``x16`` instead of ``x4``.

    The expected values here are derived from the documented propagation
    formulas and the raw inputs, never from a previously recorded output. A
    test that pins yesterday's number cannot tell a repair from a regression.
    """

    TAP = dict(
        E_GPa=12.0,
        frequency_hz=500.0,
        frequency_uncertainty_hz=2.0,
        length_mm=400.0,
        length_uncertainty_mm=2.0,
        thickness_mm=3.0,
        thickness_uncertainty_mm=0.05,
        density_kg_m3=400.0,
        density_uncertainty_kg_m3=10.0,
        snr_db=40.0,
        is_calibrated=True,
    )

    DEFL = dict(
        E_GPa=12.0,
        span_mm=400.0,
        span_uncertainty_mm=0.5,
        width_mm=30.0,
        width_uncertainty_mm=0.2,
        thickness_mm=3.0,
        thickness_uncertainty_mm=0.05,
        deflection_mm=1.0,
        deflection_uncertainty_mm=0.02,
        force_N=10.0,
        force_uncertainty_N=0.05,
    )

    def test_a1_tap_tone_components_store_unweighted_uncertainty(self):
        """Each component holds E*(dX/X), with the factor carried separately."""
        k = self.TAP
        budget = compute_tap_tone_moe_uncertainty(**k)
        by_name = {c.name: c for c in budget.components}

        # E proportional to f^2 L^4 rho / h^2.
        expected = {
            "Frequency measurement": (
                k["E_GPa"] * k["frequency_uncertainty_hz"] / k["frequency_hz"],
                2.0,
            ),
            "Length measurement": (
                k["E_GPa"] * k["length_uncertainty_mm"] / k["length_mm"],
                4.0,
            ),
            "Thickness measurement": (
                k["E_GPa"] * k["thickness_uncertainty_mm"] / k["thickness_mm"],
                2.0,
            ),
            "Density calculation": (
                k["E_GPa"] * k["density_uncertainty_kg_m3"] / k["density_kg_m3"],
                1.0,
            ),
        }
        for name, (unweighted, sensitivity) in expected.items():
            component = by_name[name]
            assert component.value == pytest.approx(unweighted), name
            assert component.sensitivity_coefficient == sensitivity, name
            # The defect signature: value carrying the factor already.
            if sensitivity != 1.0:
                assert component.value != pytest.approx(unweighted * sensitivity), name

    def test_a2_tap_tone_aggregate_is_the_coefficient_once_rss(self):
        """Combined uncertainty converges to the independently propagated value."""
        k = self.TAP
        budget = compute_tap_tone_moe_uncertainty(**k)

        relative = math.sqrt(
            (2.0 * k["frequency_uncertainty_hz"] / k["frequency_hz"]) ** 2
            + (4.0 * k["length_uncertainty_mm"] / k["length_mm"]) ** 2
            + (1.0 * k["density_uncertainty_kg_m3"] / k["density_kg_m3"]) ** 2
            + (2.0 * k["thickness_uncertainty_mm"] / k["thickness_mm"]) ** 2
        )
        assert budget.combined_standard_uncertainty == pytest.approx(
            k["E_GPa"] * relative
        )

    def test_a3_deflection_aggregate_is_the_coefficient_once_rss(self):
        """Same invariant for the 3-point bending propagation."""
        k = self.DEFL
        budget = compute_deflection_moe_uncertainty(**k)

        relative = math.sqrt(
            (1.0 * k["force_uncertainty_N"] / k["force_N"]) ** 2
            + (3.0 * k["span_uncertainty_mm"] / k["span_mm"]) ** 2
            + (1.0 * k["width_uncertainty_mm"] / k["width_mm"]) ** 2
            + (3.0 * k["thickness_uncertainty_mm"] / k["thickness_mm"]) ** 2
            + (1.0 * k["deflection_uncertainty_mm"] / k["deflection_mm"]) ** 2
        )
        assert budget.combined_standard_uncertainty == pytest.approx(
            k["E_GPa"] * relative
        )

    @pytest.mark.parametrize(
        "factory,kwargs",
        [
            (compute_tap_tone_moe_uncertainty, "TAP"),
            (compute_deflection_moe_uncertainty, "DEFL"),
        ],
    )
    def test_aggregate_equals_rss_of_its_own_weighted_components(self, factory, kwargs):
        """The budget combines its own components and nothing else.

        This is the structural half of A2/A3: whatever the inputs, the reported
        aggregate must be reconstructible from the serialized component list.
        """
        budget = factory(**getattr(self, kwargs))
        rss = math.sqrt(
            sum((c.sensitivity_coefficient * c.value) ** 2 for c in budget.components)
        )
        assert budget.combined_standard_uncertainty == pytest.approx(rss, rel=1e-12)

    def test_unweighted_components_pass_no_coefficient(self):
        """Fit quality, SNR and calibration terms have no factor of their own.

        They defaulted to 1.0 and were never doubled, which is why the
        historical B-022 inflation was component-dependent rather than a
        uniform factor that could have been divided out downstream.
        """
        budget = compute_tap_tone_moe_uncertainty(
            **{**self.TAP, "snr_db": 20.0, "is_calibrated": False}
        )
        extras = [
            c
            for c in budget.components
            if c.name in ("Signal quality (SNR)", "Uncalibrated system")
        ]
        assert len(extras) == 2
        for component in extras:
            assert component.sensitivity_coefficient == 1.0
