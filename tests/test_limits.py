"""
Tests for the limit/mask testing module.
"""

import math

import numpy as np
import pytest

from tap_tone_pi.limits import (
    LimitPoint,
    LimitCurve,
    LimitType,
    create_limit_curve,
    create_flat_limit,
    create_sloped_limit,
    MaskRegion,
    FrequencyMask,
    apply_mask,
    LimitTestResult,
    LimitViolation,
    check_against_limits,
    calculate_margin,
    find_violations,
    get_preset_names,
    load_preset,
    save_preset,
)
from tap_tone_pi.limits.masks import (
    create_ac_hum_mask,
    create_subsonic_mask,
    create_ultrasonic_mask,
    combine_masks,
)
from tap_tone_pi.limits.testing import TestVerdict, format_test_result


class TestLimitPoint:
    """Tests for LimitPoint."""

    def test_basic_point(self):
        """Test basic point creation."""
        point = LimitPoint(frequency_hz=1000.0, value_db=-20.0)

        assert point.frequency_hz == 1000.0
        assert point.value_db == -20.0

    def test_invalid_frequency_raises(self):
        """Test invalid frequency raises error."""
        with pytest.raises(ValueError):
            LimitPoint(frequency_hz=-100.0, value_db=-20.0)

        with pytest.raises(ValueError):
            LimitPoint(frequency_hz=0.0, value_db=-20.0)


class TestLimitCurve:
    """Tests for LimitCurve."""

    def test_basic_curve(self):
        """Test basic curve creation."""
        curve = LimitCurve(
            name="test",
            limit_type=LimitType.UPPER,
            points=[
                LimitPoint(100.0, -10.0),
                LimitPoint(1000.0, -20.0),
                LimitPoint(10000.0, -30.0),
            ],
        )

        assert curve.name == "test"
        assert curve.limit_type == LimitType.UPPER
        assert len(curve.points) == 3

    def test_points_sorted(self):
        """Test points are sorted by frequency."""
        curve = LimitCurve(
            name="test",
            limit_type=LimitType.UPPER,
            points=[
                LimitPoint(1000.0, -20.0),
                LimitPoint(100.0, -10.0),
                LimitPoint(10000.0, -30.0),
            ],
        )

        assert curve.points[0].frequency_hz == 100.0
        assert curve.points[1].frequency_hz == 1000.0
        assert curve.points[2].frequency_hz == 10000.0

    def test_freq_range(self):
        """Test frequency range property."""
        curve = create_limit_curve(
            name="test",
            limit_type=LimitType.UPPER,
            frequencies_hz=[100.0, 1000.0, 10000.0],
            values_db=[-10.0, -20.0, -30.0],
        )

        assert curve.freq_range == (100.0, 10000.0)

    def test_get_limit_at_freq_exact(self):
        """Test getting limit at exact point."""
        curve = create_limit_curve(
            name="test",
            limit_type=LimitType.UPPER,
            frequencies_hz=[100.0, 1000.0],
            values_db=[-10.0, -20.0],
        )

        assert curve.get_limit_at_freq(100.0) == -10.0
        assert curve.get_limit_at_freq(1000.0) == -20.0

    def test_get_limit_at_freq_interpolated(self):
        """Test getting interpolated limit."""
        curve = create_limit_curve(
            name="test",
            limit_type=LimitType.UPPER,
            frequencies_hz=[100.0, 1000.0],
            values_db=[-10.0, -20.0],
        )

        # Geometric mean frequency (log-linear interpolation)
        # sqrt(100 * 1000) = ~316 Hz should give midpoint
        mid_freq = math.sqrt(100.0 * 1000.0)
        limit = curve.get_limit_at_freq(mid_freq)

        assert limit == pytest.approx(-15.0, rel=0.01)

    def test_get_limit_outside_range(self):
        """Test limit outside range returns None."""
        curve = create_limit_curve(
            name="test",
            limit_type=LimitType.UPPER,
            frequencies_hz=[100.0, 1000.0],
            values_db=[-10.0, -20.0],
        )

        assert curve.get_limit_at_freq(50.0) is None
        assert curve.get_limit_at_freq(2000.0) is None

    def test_to_arrays(self):
        """Test conversion to arrays."""
        curve = create_limit_curve(
            name="test",
            limit_type=LimitType.UPPER,
            frequencies_hz=[100.0, 1000.0],
            values_db=[-10.0, -20.0],
        )

        freqs, values = curve.to_arrays(n_points=10)

        assert len(freqs) == 10
        assert len(values) == 10
        assert not np.any(np.isnan(values))

    def test_to_dict_from_dict(self):
        """Test serialization roundtrip."""
        original = create_limit_curve(
            name="test",
            limit_type=LimitType.LOWER,
            frequencies_hz=[100.0, 1000.0],
            values_db=[-50.0, -60.0],
            description="Test curve",
        )

        data = original.to_dict()
        restored = LimitCurve.from_dict(data)

        assert restored.name == original.name
        assert restored.limit_type == original.limit_type
        assert len(restored.points) == len(original.points)


class TestCreateLimitCurve:
    """Tests for limit curve factory functions."""

    def test_create_flat_limit(self):
        """Test flat limit creation."""
        curve = create_flat_limit(
            name="noise_floor",
            limit_type=LimitType.UPPER,
            value_db=-60.0,
            freq_min=20.0,
            freq_max=20000.0,
        )

        assert curve.get_limit_at_freq(100.0) == -60.0
        assert curve.get_limit_at_freq(1000.0) == -60.0
        assert curve.get_limit_at_freq(10000.0) == -60.0

    def test_create_sloped_limit(self):
        """Test sloped limit creation."""
        curve = create_sloped_limit(
            name="pink_noise",
            limit_type=LimitType.UPPER,
            value_at_1khz_db=0.0,
            slope_db_per_octave=-3.0,  # -3 dB/octave (pink)
        )

        # At 1kHz should be 0 dB
        assert curve.get_limit_at_freq(1000.0) == pytest.approx(0.0, abs=0.1)

        # At 2kHz (1 octave up) should be -3 dB
        assert curve.get_limit_at_freq(2000.0) == pytest.approx(-3.0, abs=0.5)

        # At 500Hz (1 octave down) should be +3 dB
        assert curve.get_limit_at_freq(500.0) == pytest.approx(3.0, abs=0.5)


class TestMaskRegion:
    """Tests for MaskRegion."""

    def test_basic_region(self):
        """Test basic region creation."""
        region = MaskRegion(
            freq_min_hz=50.0,
            freq_max_hz=70.0,
            reason="60 Hz hum",
        )

        assert region.freq_min_hz == 50.0
        assert region.freq_max_hz == 70.0

    def test_contains(self):
        """Test frequency containment check."""
        region = MaskRegion(freq_min_hz=50.0, freq_max_hz=70.0)

        assert region.contains(60.0)
        assert region.contains(50.0)
        assert region.contains(70.0)
        assert not region.contains(49.0)
        assert not region.contains(71.0)

    def test_auto_swap_bounds(self):
        """Test bounds are auto-swapped if reversed."""
        region = MaskRegion(freq_min_hz=100.0, freq_max_hz=50.0)

        assert region.freq_min_hz == 50.0
        assert region.freq_max_hz == 100.0


class TestFrequencyMask:
    """Tests for FrequencyMask."""

    def test_basic_mask(self):
        """Test basic mask creation."""
        mask = FrequencyMask(name="test")
        mask.add_region(50.0, 70.0, "60 Hz hum")
        mask.add_region(100.0, 140.0, "120 Hz harmonic")

        assert len(mask.regions) == 2

    def test_is_masked(self):
        """Test masked frequency detection."""
        mask = FrequencyMask(
            name="test",
            regions=[MaskRegion(50.0, 70.0, "hum")],
        )

        assert mask.is_masked(60.0)
        assert not mask.is_masked(100.0)

    def test_get_mask_reason(self):
        """Test getting mask reason."""
        mask = FrequencyMask(
            name="test",
            regions=[MaskRegion(50.0, 70.0, "60 Hz hum")],
        )

        assert mask.get_mask_reason(60.0) == "60 Hz hum"
        assert mask.get_mask_reason(100.0) is None


class TestApplyMask:
    """Tests for mask application."""

    def test_apply_mask(self):
        """Test applying mask to data."""
        frequencies = np.array([50.0, 60.0, 70.0, 100.0, 200.0])
        values = np.array([-10.0, -20.0, -30.0, -40.0, -50.0])

        mask = FrequencyMask(
            name="test",
            regions=[MaskRegion(55.0, 75.0)],
        )

        unmasked_freq, unmasked_val = apply_mask(frequencies, values, mask)

        assert len(unmasked_freq) == 3
        assert 60.0 not in unmasked_freq
        assert 70.0 not in unmasked_freq


class TestMaskFactories:
    """Tests for mask factory functions."""

    def test_create_ac_hum_mask(self):
        """Test AC hum mask creation."""
        mask = create_ac_hum_mask(include_50hz=True, include_60hz=True, harmonics=2)

        assert mask.is_masked(50.0)
        assert mask.is_masked(60.0)
        assert mask.is_masked(100.0)  # 50 Hz harmonic
        assert mask.is_masked(120.0)  # 60 Hz harmonic
        assert not mask.is_masked(200.0)

    def test_create_subsonic_mask(self):
        """Test subsonic mask creation."""
        mask = create_subsonic_mask(cutoff_hz=20.0)

        assert mask.is_masked(10.0)
        assert mask.is_masked(15.0)
        assert not mask.is_masked(25.0)

    def test_create_ultrasonic_mask(self):
        """Test ultrasonic mask creation."""
        mask = create_ultrasonic_mask(cutoff_hz=20000.0, sample_rate=48000)

        assert not mask.is_masked(10000.0)
        assert mask.is_masked(21000.0)

    def test_combine_masks(self):
        """Test combining masks."""
        mask1 = create_subsonic_mask(cutoff_hz=20.0)
        mask2 = create_ultrasonic_mask(cutoff_hz=20000.0)

        combined = combine_masks(mask1, mask2, name="audible_only")

        assert combined.is_masked(10.0)
        assert combined.is_masked(21000.0)
        assert not combined.is_masked(1000.0)


class TestLimitTesting:
    """Tests for limit testing."""

    def test_all_pass(self):
        """Test all values within limits."""
        frequencies = np.array([100.0, 500.0, 1000.0, 5000.0])
        values = np.array([-30.0, -30.0, -30.0, -30.0])

        upper = create_flat_limit("upper", LimitType.UPPER, -20.0)
        lower = create_flat_limit("lower", LimitType.LOWER, -40.0)

        result = check_against_limits(frequencies, values, [upper, lower])

        assert result.verdict == TestVerdict.PASS
        assert result.violation_count == 0

    def test_upper_violation(self):
        """Test upper limit violation."""
        frequencies = np.array([100.0, 500.0, 1000.0])
        values = np.array([-30.0, -10.0, -30.0])  # -10 violates -20

        upper = create_flat_limit("upper", LimitType.UPPER, -20.0)

        result = check_against_limits(frequencies, values, [upper])

        assert result.verdict == TestVerdict.FAIL
        assert result.violation_count == 1
        assert result.violations[0].frequency_hz == 500.0

    def test_lower_violation(self):
        """Test lower limit violation."""
        frequencies = np.array([100.0, 500.0, 1000.0])
        values = np.array([-30.0, -50.0, -30.0])  # -50 violates -40

        lower = create_flat_limit("lower", LimitType.LOWER, -40.0)

        result = check_against_limits(frequencies, values, [lower])

        assert result.verdict == TestVerdict.FAIL
        assert result.violation_count == 1

    def test_warn_within_margin(self):
        """Test warning when violation within margin."""
        frequencies = np.array([1000.0])
        values = np.array([-18.0])  # 2 dB over -20 limit

        upper = create_flat_limit("upper", LimitType.UPPER, -20.0)

        result = check_against_limits(
            frequencies, values, [upper],
            warn_margin_db=3.0,  # 3 dB margin
        )

        assert result.verdict == TestVerdict.WARN

    def test_masked_points_excluded(self):
        """Test masked points are excluded."""
        frequencies = np.array([50.0, 60.0, 1000.0])
        values = np.array([0.0, 0.0, -30.0])  # 60 Hz would violate but is masked

        upper = create_flat_limit("upper", LimitType.UPPER, -20.0)
        mask = create_ac_hum_mask(include_60hz=True, harmonics=1)

        result = check_against_limits(frequencies, values, [upper], mask=mask)

        # Only 1000 Hz should be tested
        assert result.points_tested == 1
        assert result.points_masked == 2
        assert result.verdict == TestVerdict.PASS


class TestCalculateMargin:
    """Tests for margin calculation."""

    def test_positive_margin(self):
        """Test positive margin (within limits)."""
        frequencies = np.array([1000.0])
        values = np.array([-30.0])

        upper = create_flat_limit("upper", LimitType.UPPER, -20.0)

        freqs, margins = calculate_margin(frequencies, values, [upper])

        assert margins[0] == 10.0  # 10 dB below limit


class TestFindViolations:
    """Tests for violation finding."""

    def test_find_violations(self):
        """Test finding violations."""
        frequencies = np.array([100.0, 500.0, 1000.0])
        values = np.array([-10.0, -30.0, -5.0])

        upper = create_flat_limit("upper", LimitType.UPPER, -20.0)

        violations = find_violations(frequencies, values, [upper])

        assert len(violations) == 2
        assert violations[0].frequency_hz == 100.0
        assert violations[1].frequency_hz == 1000.0


class TestLimitPresets:
    """Tests for limit presets."""

    def test_get_preset_names(self):
        """Test getting preset names."""
        names = get_preset_names()

        assert isinstance(names, list)
        assert len(names) > 0
        assert "tonewood_tap" in names

    def test_load_preset(self):
        """Test loading a preset."""
        limits, mask = load_preset("tonewood_tap")

        assert isinstance(limits, list)
        assert len(limits) > 0
        assert all(isinstance(lim, LimitCurve) for lim in limits)

    def test_load_unknown_preset_raises(self):
        """Test loading unknown preset raises error."""
        with pytest.raises(KeyError):
            load_preset("nonexistent_preset")

    def test_save_and_load_preset(self, tmp_path):
        """Test saving and loading custom preset."""
        limits = [create_flat_limit("test", LimitType.UPPER, -30.0)]
        mask = FrequencyMask(name="test_mask")

        filepath = tmp_path / "test_preset.json"
        save_preset(filepath, limits, mask, name="custom", description="Test")

        assert filepath.exists()


class TestFormatTestResult:
    """Tests for result formatting."""

    def test_format_pass(self):
        """Test formatting passing result."""
        result = LimitTestResult(
            verdict=TestVerdict.PASS,
            violations=[],
            worst_margin_db=10.0,
            points_tested=100,
        )

        formatted = format_test_result(result)

        assert "PASS" in formatted
        assert "Points tested: 100" in formatted

    def test_format_fail_with_violations(self):
        """Test formatting failing result with violations."""
        result = LimitTestResult(
            verdict=TestVerdict.FAIL,
            violations=[
                LimitViolation(
                    frequency_hz=1000.0,
                    measured_db=-10.0,
                    limit_db=-20.0,
                    limit_type=LimitType.UPPER,
                    limit_name="upper",
                    margin_db=-10.0,
                )
            ],
            worst_margin_db=-10.0,
            points_tested=100,
        )

        formatted = format_test_result(result, verbose=True)

        assert "FAIL" in formatted
        assert "1000" in formatted
