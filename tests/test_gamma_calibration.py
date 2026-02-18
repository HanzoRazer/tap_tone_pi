"""Tests for γ calibration tool."""

import math
import pytest

from tap_tone_pi.design.gamma_calibration import (
    ModeMeasurement,
    SpecimenData,
    GammaCalibration,
    GammaCalibrationResult,
    calibrate_gamma_from_pairs,
    calibrate_gamma_multi_specimen,
    format_gamma_calibration_report,
)


class TestModeMeasurement:
    """Tests for ModeMeasurement dataclass."""

    def test_gamma_calculation(self):
        """γ should be f_box / f_free."""
        m = ModeMeasurement("1,1", f_free_Hz=200.0, f_box_Hz=170.0)
        assert abs(m.gamma - 0.85) < 0.001

    def test_gamma_less_than_one_typical(self):
        """Typical guitar γ should be < 1."""
        m = ModeMeasurement("1,1", f_free_Hz=185.0, f_box_Hz=158.0)
        assert m.gamma < 1.0

    def test_rejects_non_positive_frequencies(self):
        """Should reject zero or negative frequencies."""
        with pytest.raises(ValueError):
            ModeMeasurement("1,1", f_free_Hz=0.0, f_box_Hz=170.0)
        with pytest.raises(ValueError):
            ModeMeasurement("1,1", f_free_Hz=200.0, f_box_Hz=-10.0)

    def test_uncertainty_propagation(self):
        """Uncertainty should propagate correctly."""
        m = ModeMeasurement(
            "1,1",
            f_free_Hz=200.0,
            f_box_Hz=170.0,
            uncertainty_free_Hz=2.0,
            uncertainty_box_Hz=2.0,
        )
        # Relative uncertainty propagation
        assert m.gamma_uncertainty > 0
        assert m.gamma_uncertainty < 0.05  # Should be small

    def test_zero_uncertainty_gives_zero(self):
        """No uncertainty input should give zero uncertainty output."""
        m = ModeMeasurement("1,1", f_free_Hz=200.0, f_box_Hz=170.0)
        assert m.gamma_uncertainty == 0.0


class TestSpecimenData:
    """Tests for SpecimenData dataclass."""

    def test_add_mode(self):
        """Should add modes correctly."""
        spec = SpecimenData("guitar_001")
        spec.add_mode("1,1", 185.0, 158.0)
        spec.add_mode("2,1", 312.0, 275.0)
        assert len(spec.modes) == 2

    def test_get_gamma_values(self):
        """Should return list of γ values."""
        spec = SpecimenData("guitar_001")
        spec.add_mode("1,1", 200.0, 170.0)
        spec.add_mode("2,1", 300.0, 270.0)
        gammas = spec.get_gamma_values()
        assert len(gammas) == 2
        assert abs(gammas[0] - 0.85) < 0.001
        assert abs(gammas[1] - 0.90) < 0.001

    def test_get_mode_ids(self):
        """Should return mode IDs."""
        spec = SpecimenData("guitar_001")
        spec.add_mode("1,1", 200.0, 170.0)
        spec.add_mode("2,1", 300.0, 270.0)
        ids = spec.get_mode_ids()
        assert ids == ["1,1", "2,1"]


class TestGammaCalibration:
    """Tests for GammaCalibration engine."""

    def test_single_mode_calibration(self):
        """Single mode should give exact γ."""
        cal = GammaCalibration()
        cal.add_mode("1,1", 200.0, 170.0)
        result = cal.compute()
        assert abs(result.gamma_mean - 0.85) < 0.001
        assert result.gamma_std == 0.0  # Single measurement

    def test_multiple_modes_mean(self):
        """Multiple modes should give correct mean."""
        cal = GammaCalibration()
        cal.add_mode("1,1", 200.0, 170.0)  # γ = 0.85
        cal.add_mode("2,1", 300.0, 270.0)  # γ = 0.90
        result = cal.compute()
        expected_mean = (0.85 + 0.90) / 2
        assert abs(result.gamma_mean - expected_mean) < 0.001

    def test_multiple_modes_std(self):
        """Should compute correct standard deviation."""
        cal = GammaCalibration()
        cal.add_mode("1,1", 200.0, 170.0)  # γ = 0.85
        cal.add_mode("2,1", 300.0, 270.0)  # γ = 0.90
        result = cal.compute()
        assert result.gamma_std > 0

    def test_confidence_interval(self):
        """Should compute 95% CI."""
        cal = GammaCalibration()
        cal.add_mode("1,1", 200.0, 170.0)
        cal.add_mode("2,1", 300.0, 270.0)
        cal.add_mode("1,2", 400.0, 360.0)
        result = cal.compute()
        assert result.gamma_ci_95[0] < result.gamma_mean
        assert result.gamma_ci_95[1] > result.gamma_mean

    def test_multi_specimen(self):
        """Should handle multiple specimens."""
        cal = GammaCalibration()
        cal.add_specimen("guitar_001", [
            ModeMeasurement("1,1", 185.0, 158.0),
            ModeMeasurement("2,1", 312.0, 275.0),
        ])
        cal.add_specimen("guitar_002", [
            ModeMeasurement("1,1", 178.0, 152.0),
            ModeMeasurement("2,1", 298.0, 262.0),
        ])
        result = cal.compute()
        assert result.n_specimens == 2
        assert result.n_measurements == 4

    def test_per_mode_statistics(self):
        """Should compute per-mode statistics."""
        cal = GammaCalibration()
        cal.add_specimen("g1", [ModeMeasurement("1,1", 185.0, 158.0)])
        cal.add_specimen("g2", [ModeMeasurement("1,1", 178.0, 152.0)])
        result = cal.compute()
        assert "1,1" in result.mode_gammas

    def test_per_specimen_statistics(self):
        """Should compute per-specimen mean γ."""
        cal = GammaCalibration()
        cal.add_specimen("guitar_001", [
            ModeMeasurement("1,1", 200.0, 170.0),
            ModeMeasurement("2,1", 300.0, 270.0),
        ])
        result = cal.compute()
        assert "guitar_001" in result.specimen_gammas

    def test_empty_raises_error(self):
        """Should raise error if no measurements."""
        cal = GammaCalibration()
        with pytest.raises(ValueError):
            cal.compute()

    def test_clear(self):
        """Clear should remove all measurements."""
        cal = GammaCalibration()
        cal.add_mode("1,1", 200.0, 170.0)
        cal.clear()
        with pytest.raises(ValueError):
            cal.compute()

    def test_to_dict(self):
        """Result should be serializable to dict."""
        cal = GammaCalibration()
        cal.add_mode("1,1", 200.0, 170.0)
        cal.add_mode("2,1", 300.0, 270.0)
        result = cal.compute()
        d = result.to_dict()
        assert "gamma_mean" in d
        assert "gamma_std" in d


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_calibrate_from_pairs(self):
        """Quick calibration from pairs."""
        result = calibrate_gamma_from_pairs([
            (200.0, 170.0),
            (300.0, 270.0),
        ])
        assert result.n_measurements == 2
        assert result.gamma_mean > 0

    def test_calibrate_multi_specimen(self):
        """Multi-specimen convenience function."""
        result = calibrate_gamma_multi_specimen({
            "g1": [(200, 170), (300, 270)],
            "g2": [(190, 162), (290, 261)],
        })
        assert result.n_specimens == 2


class TestFormatReport:
    """Tests for report formatting."""

    def test_returns_string(self):
        """Should return string."""
        cal = GammaCalibration()
        cal.add_mode("1,1", 200.0, 170.0)
        cal.add_mode("2,1", 300.0, 270.0)
        result = cal.compute()
        report = format_gamma_calibration_report(result)
        assert isinstance(report, str)

    def test_includes_gamma_value(self):
        """Report should include γ value."""
        cal = GammaCalibration()
        cal.add_mode("1,1", 200.0, 170.0)
        result = cal.compute()
        report = format_gamma_calibration_report(result)
        assert "0.85" in report or "γ" in report.lower() or "gamma" in report.lower()


class TestRealisticCalibration:
    """Tests with realistic guitar data."""

    def test_typical_classical_guitar(self):
        """Typical classical guitar calibration."""
        cal = GammaCalibration()
        # Realistic values for classical guitar top
        cal.add_mode("1,1", 185.0, 158.0)  # γ ≈ 0.854
        cal.add_mode("2,1", 312.0, 275.0)  # γ ≈ 0.881
        cal.add_mode("1,2", 425.0, 382.0)  # γ ≈ 0.899
        result = cal.compute()

        # γ should be in typical range
        assert 0.80 < result.gamma_mean < 0.95
        assert result.n_measurements == 3

    def test_typical_steel_string(self):
        """Typical steel-string guitar calibration."""
        cal = GammaCalibration()
        # Steel string with X-bracing (stiffer, γ closer to 1)
        cal.add_mode("1,1", 220.0, 195.0)  # γ ≈ 0.886
        cal.add_mode("2,1", 380.0, 340.0)  # γ ≈ 0.895
        result = cal.compute()

        assert 0.85 < result.gamma_mean < 0.95
