#!/usr/bin/env python3
"""
Tests for Gore-style stiffness index calculations.
"""

import pytest

from tap_tone_pi.bending.gore_stiffness import (
    InstrumentType,
    SI_PRESETS,
    stiffness_index,
    thickness_for_target_SI,
    orthotropic_ratio,
    get_preset,
    list_presets,
    analyze_single_direction,
    analyze_orthotropic,
    SingleDirectionResult,
    OrthotropicResult,
)


class TestStiffnessIndexCalculations:
    """Test core SI calculations."""

    def test_stiffness_index_basic(self):
        """SI = E × h³ should compute correctly."""
        E = 12.0  # GPa
        h = 3.0  # mm
        SI = stiffness_index(E, h)
        assert SI == pytest.approx(12.0 * 27.0, rel=1e-6)  # 324 GPa·mm³

    def test_stiffness_index_typical_sitka(self):
        """Typical Sitka spruce values should give expected SI."""
        # Typical Sitka: E_L ≈ 12 GPa, h ≈ 3 mm → SI ≈ 324
        SI = stiffness_index(12.0, 3.0)
        assert 300 < SI < 400  # Reasonable range for dreadnought

    def test_thickness_for_target_SI(self):
        """h = (SI_target / E)^(1/3) should invert correctly."""
        E = 12.0
        SI_target = 320.0
        h = thickness_for_target_SI(SI_target, E)
        # Verify by computing SI back
        SI_back = stiffness_index(E, h)
        assert SI_back == pytest.approx(SI_target, rel=1e-6)

    def test_thickness_for_target_SI_edge_cases(self):
        """Edge cases for thickness calculation."""
        # Very high E → thinner needed
        h_high = thickness_for_target_SI(320, 20.0)
        h_low = thickness_for_target_SI(320, 8.0)
        assert h_high < h_low  # Higher E needs less thickness

    def test_thickness_for_target_SI_zero_E_raises(self):
        """Zero modulus should raise ValueError."""
        with pytest.raises(ValueError, match="E must be positive"):
            thickness_for_target_SI(320, 0)

    def test_orthotropic_ratio(self):
        """E_L / E_C ratio should compute correctly."""
        E_L = 12.0
        E_C = 0.8
        ratio = orthotropic_ratio(E_L, E_C)
        assert ratio == pytest.approx(15.0, rel=1e-6)

    def test_orthotropic_ratio_zero_divisor(self):
        """E_C = 0 should return inf."""
        ratio = orthotropic_ratio(12.0, 0)
        assert ratio == float("inf")


class TestPresets:
    """Test instrument presets."""

    def test_all_presets_have_required_fields(self):
        """All presets should have required fields."""
        for preset in SI_PRESETS.values():
            assert preset.instrument is not None
            assert preset.SI_L_min > 0
            assert preset.SI_L_typical > 0
            assert preset.SI_L_max > 0
            assert preset.SI_L_min < preset.SI_L_typical < preset.SI_L_max

    def test_get_preset_by_enum(self):
        """get_preset should work with enum."""
        preset = get_preset(InstrumentType.CLASSICAL_GUITAR)
        assert preset is not None
        assert preset.instrument == InstrumentType.CLASSICAL_GUITAR
        assert preset.SI_L_typical == 320

    def test_get_preset_by_string(self):
        """get_preset should work with string."""
        preset = get_preset("dreadnought")
        assert preset is not None
        assert preset.instrument == InstrumentType.STEEL_STRING_DREADNOUGHT

    def test_get_preset_invalid_returns_none(self):
        """Invalid instrument should return None."""
        preset = get_preset("nonexistent_guitar")
        assert preset is None

    def test_list_presets_returns_all(self):
        """list_presets should return all presets."""
        presets = list_presets()
        assert len(presets) == len(SI_PRESETS)
        assert all("instrument" in p for p in presets)

    def test_presets_have_realistic_values(self):
        """Preset values should be physically reasonable."""
        for preset in SI_PRESETS.values():
            # SI_L should be reasonable (50-700 GPa·mm³)
            assert 50 < preset.SI_L_typical < 700, f"{preset.instrument} has unrealistic SI_L"
            # Thickness should be reasonable (1-5 mm)
            assert 1.0 < preset.h_typical_mm < 5.0, f"{preset.instrument} has unrealistic h"


class TestSingleDirectionAnalysis:
    """Test single-direction analysis."""

    def test_analyze_single_direction_basic(self):
        """Basic single-direction analysis should compute SI."""
        result = analyze_single_direction(E_GPa=12.0, h_mm=3.0, direction="L")
        assert isinstance(result, SingleDirectionResult)
        assert result.direction == "L"
        assert result.E_GPa == pytest.approx(12.0, rel=1e-3)
        assert result.h_mm == pytest.approx(3.0, rel=1e-3)
        assert result.SI == pytest.approx(324.0, rel=1e-2)

    def test_analyze_single_direction_with_target(self):
        """Analysis with SI target should compute h_target."""
        result = analyze_single_direction(
            E_GPa=12.0, h_mm=3.5, direction="L", SI_target=320.0
        )
        assert result.SI_target == 320.0
        assert result.h_target_mm is not None
        assert result.h_target_mm < result.h_mm  # Need to remove material

    def test_analyze_single_direction_with_density(self):
        """Analysis with density should compute specific stiffness."""
        result = analyze_single_direction(
            E_GPa=12.0, h_mm=3.0, direction="L", density_kg_m3=420.0
        )
        assert result.density_kg_m3 == pytest.approx(420.0, rel=1e-2)
        assert result.specific_stiffness is not None
        assert result.wave_speed_m_s is not None
        # Specific stiffness should be E/ρ ≈ 12e9 / 420 ≈ 2.86e7
        assert result.specific_stiffness == pytest.approx(12e9 / 420, rel=0.01)

    def test_analyze_single_direction_warning_for_excessive_thinning(self):
        """Warning should appear if target requires >40% material removal."""
        result = analyze_single_direction(
            E_GPa=12.0, h_mm=5.0, direction="L", SI_target=100.0  # Very low target
        )
        assert any("<60%" in w for w in result.warnings)


class TestOrthotropicAnalysis:
    """Test orthotropic (dual-direction) analysis."""

    def test_analyze_orthotropic_basic(self):
        """Basic orthotropic analysis should compute both directions."""
        result = analyze_orthotropic(
            E_L_GPa=12.0, E_C_GPa=0.8, h_mm=3.0
        )
        assert isinstance(result, OrthotropicResult)
        assert result.E_L_GPa == pytest.approx(12.0, rel=1e-3)
        assert result.E_C_GPa == pytest.approx(0.8, rel=1e-3)
        assert result.E_ratio_L_C == pytest.approx(15.0, rel=1e-2)
        assert result.SI_L == pytest.approx(324.0, rel=1e-2)
        assert result.SI_C == pytest.approx(21.6, rel=1e-2)

    def test_analyze_orthotropic_ratio_warnings(self):
        """Unusual E_L/E_C ratios should trigger warnings."""
        # Very low ratio
        result_low = analyze_orthotropic(E_L_GPa=8.0, E_C_GPa=2.0, h_mm=3.0)
        assert any("low" in w.lower() for w in result_low.warnings)

        # Very high ratio
        result_high = analyze_orthotropic(E_L_GPa=24.0, E_C_GPa=0.5, h_mm=3.0)
        assert any("high" in w.lower() for w in result_high.warnings)

    def test_analyze_orthotropic_with_instrument(self):
        """Analysis with instrument should include preset comparison."""
        result = analyze_orthotropic(
            E_L_GPa=12.0, E_C_GPa=0.8, h_mm=2.8, match_instrument="dreadnought"
        )
        assert result.instrument_match == "dreadnought"
        assert result.preset_comparison is not None
        assert "SI_L_status" in result.preset_comparison

    def test_analyze_orthotropic_with_density(self):
        """Analysis with density should compute wave speeds for both directions."""
        result = analyze_orthotropic(
            E_L_GPa=12.0, E_C_GPa=0.8, h_mm=3.0, density_kg_m3=420.0
        )
        assert result.wave_speed_L_m_s is not None
        assert result.wave_speed_C_m_s is not None
        # L wave speed should be much higher than C
        assert result.wave_speed_L_m_s > result.wave_speed_C_m_s * 2


class TestResultSerialization:
    """Test result serialization."""

    def test_single_result_to_dict(self):
        """SingleDirectionResult should serialize correctly."""
        result = analyze_single_direction(E_GPa=12.0, h_mm=3.0, direction="L")
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["direction"] == "L"
        assert "SI" in d

    def test_orthotropic_result_to_dict(self):
        """OrthotropicResult should serialize correctly."""
        result = analyze_orthotropic(E_L_GPa=12.0, E_C_GPa=0.8, h_mm=3.0)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "E_L_GPa" in d
        assert "E_ratio_L_C" in d

    def test_to_dict_omits_none_values(self):
        """to_dict should not include None values."""
        result = analyze_single_direction(E_GPa=12.0, h_mm=3.0, direction="L")
        d = result.to_dict()
        # SI_target wasn't provided, so it should be None and not in dict
        assert "SI_target" not in d or d.get("SI_target") is not None


class TestPhysicalRealism:
    """Test that calculations match physical expectations."""

    def test_doubling_thickness_multiplies_SI_by_8(self):
        """SI ∝ h³, so doubling h should multiply SI by 8."""
        SI_1 = stiffness_index(12.0, 2.0)
        SI_2 = stiffness_index(12.0, 4.0)
        assert SI_2 == pytest.approx(SI_1 * 8, rel=1e-6)

    def test_wave_speed_sitka_spruce_realistic(self):
        """Wave speed in Sitka spruce should be ~5000-6000 m/s."""
        result = analyze_single_direction(
            E_GPa=12.0, h_mm=3.0, direction="L", density_kg_m3=420.0
        )
        # c = √(E/ρ) ≈ √(12e9/420) ≈ 5345 m/s
        assert 5000 < result.wave_speed_m_s < 6000

    def test_typical_dreadnought_matches_preset(self):
        """Typical dreadnought values should match preset range."""
        _preset = get_preset(InstrumentType.STEEL_STRING_DREADNOUGHT)  # noqa: F841
        # For E=13 GPa to hit dreadnought SI range (350-500):
        # h = (420/13)^(1/3) ≈ 3.18 mm
        result = analyze_orthotropic(
            E_L_GPa=13.0, E_C_GPa=0.9, h_mm=3.2, match_instrument="dreadnought"
        )
        # SI = 13 × 3.2³ = 13 × 32.77 = 426 GPa·mm³ (in range 350-500)
        assert result.preset_comparison["SI_L_status"] == "good"
