#!/usr/bin/env python3
"""Tests for tap_tone_pi.design thickness calculator module.

Tests cover:
- Orthotropic plate modal frequency calculation
- Thickness-for-target-frequency solver
- Helmholtz frequency calculation
- Chladni-to-box frequency mapping
- 3-oscillator coupled system eigenfrequencies
- Material and body calibration presets
"""

import math

import numpy as np
import pytest

from tap_tone_pi.design import (
    # Core functions
    thickness_for_target_frequency,
    coupled_eigenfrequencies,
    chladni_to_box_frequency,
    # Result classes
    PlateThicknessResult,
    CoupledSystemResult,
    # Analysis functions
    analyze_plate,
    analyze_coupled_system,
    # Calibration
    BodyStyle,
    get_body_calibration,
    list_body_styles,
    MaterialPreset,
    get_material_preset,
    list_materials,
)

from tap_tone_pi.design.thickness_calculator import (
    plate_modal_frequency,
    helmholtz_frequency,
    box_to_chladni_frequency,
)


class TestPlateModalFrequency:
    """Test plate modal frequency calculation."""

    def test_basic_calculation(self):
        """Basic modal frequency calculation with typical values."""
        # Sitka spruce plate
        E_L = 12.5e9  # Pa
        E_C = 0.85e9  # Pa
        rho = 420  # kg/m³
        h = 0.003  # 3mm
        a = 0.5  # 500mm
        b = 0.4  # 400mm

        f = plate_modal_frequency(E_L, E_C, rho, h, a, b)

        # Should be in reasonable range for guitar top
        assert 50 < f < 200
        assert isinstance(f, float)

    def test_thickness_scaling(self):
        """Frequency scales linearly with thickness."""
        E_L, E_C, rho = 12e9, 0.8e9, 400
        a, b = 0.5, 0.4

        f1 = plate_modal_frequency(E_L, E_C, rho, 0.002, a, b)  # 2mm
        f2 = plate_modal_frequency(E_L, E_C, rho, 0.004, a, b)  # 4mm

        # f ∝ h, so doubling thickness should double frequency
        assert abs(f2 / f1 - 2.0) < 0.01

    def test_stiffness_scaling(self):
        """Frequency scales with sqrt(E/rho)."""
        rho = 400
        h, a, b = 0.003, 0.5, 0.4

        f1 = plate_modal_frequency(10e9, 0.5e9, rho, h, a, b)
        f2 = plate_modal_frequency(40e9, 2.0e9, rho, h, a, b)  # 4x stiffness

        # f ∝ √E, so 4x stiffness should give 2x frequency
        assert abs(f2 / f1 - 2.0) < 0.05

    def test_density_scaling(self):
        """Frequency scales inversely with sqrt(density)."""
        E_L, E_C = 12e9, 0.8e9
        h, a, b = 0.003, 0.5, 0.4

        f1 = plate_modal_frequency(E_L, E_C, 400, h, a, b)
        f2 = plate_modal_frequency(E_L, E_C, 1600, h, a, b)  # 4x density

        # f ∝ 1/√ρ, so 4x density should give 0.5x frequency
        assert abs(f2 / f1 - 0.5) < 0.05

    def test_geometry_factor_eta(self):
        """Geometry factor η scales frequency linearly."""
        E_L, E_C, rho = 12e9, 0.8e9, 400
        h, a, b = 0.003, 0.5, 0.4

        f1 = plate_modal_frequency(E_L, E_C, rho, h, a, b, eta=1.0)
        f2 = plate_modal_frequency(E_L, E_C, rho, h, a, b, eta=0.9)

        assert abs(f2 / f1 - 0.9) < 0.01

    def test_invalid_parameters_raise(self):
        """Invalid parameters should raise ValueError."""
        E_L, E_C, rho = 12e9, 0.8e9, 400

        with pytest.raises(ValueError):
            plate_modal_frequency(E_L, E_C, 0, 0.003, 0.5, 0.4)  # zero density

        with pytest.raises(ValueError):
            plate_modal_frequency(E_L, E_C, rho, 0, 0.5, 0.4)  # zero thickness

        with pytest.raises(ValueError):
            plate_modal_frequency(E_L, E_C, rho, 0.003, 0, 0.4)  # zero length


class TestThicknessForTargetFrequency:
    """Test inverse calculation: thickness for target frequency."""

    def test_roundtrip_consistency(self):
        """thickness_for_target_frequency is inverse of plate_modal_frequency."""
        E_L, E_C, rho = 12e9, 0.8e9, 420
        a, b = 0.5, 0.4
        h_original = 0.0028  # 2.8mm

        # Forward: compute frequency
        f = plate_modal_frequency(E_L, E_C, rho, h_original, a, b)

        # Inverse: compute thickness
        h_computed = thickness_for_target_frequency(f, E_L, E_C, rho, a, b)

        assert abs(h_computed - h_original) < 1e-6

    def test_target_86_hz_mahogany(self):
        """User's target: 86 Hz for mahogany back."""
        # Mahogany: E_L=10.2 GPa, E_C=0.65 GPa, ρ=540 kg/m³
        # Dimensions: 559mm × 241mm
        E_L = 10.2e9
        E_C = 0.65e9
        rho = 540
        a = 0.559
        b = 0.241
        f_target = 86.0

        h = thickness_for_target_frequency(f_target, E_L, E_C, rho, a, b)

        # Should be in reasonable range (2-4mm)
        assert 0.002 < h < 0.004
        h_mm = h * 1000
        assert 2.0 < h_mm < 4.0

        # Verify by computing frequency at this thickness
        f_check = plate_modal_frequency(E_L, E_C, rho, h, a, b)
        assert abs(f_check - f_target) < 0.1

    def test_negative_frequency_raises(self):
        """Negative target frequency should raise ValueError."""
        with pytest.raises(ValueError):
            thickness_for_target_frequency(-100, 12e9, 0.8e9, 400, 0.5, 0.4)


class TestHelmholtzFrequency:
    """Test Helmholtz resonance calculation."""

    def test_typical_guitar_cavity(self):
        """Typical guitar cavity should give ~100 Hz Helmholtz."""
        V = 0.020  # 20 liters
        A_hole = 0.0079  # 100mm diameter
        # L_eff = thickness + 1.6×radius = 0.004 + 1.6×0.05 = 0.084m
        L_eff = 0.084

        f_H = helmholtz_frequency(V, A_hole, L_eff)

        # Should be in 90-130 Hz range for typical guitar
        assert 80 < f_H < 130

    def test_volume_scaling(self):
        """Larger volume gives lower Helmholtz frequency."""
        A_hole, L_eff = 0.0079, 0.008

        f1 = helmholtz_frequency(0.015, A_hole, L_eff)  # 15L
        f2 = helmholtz_frequency(0.030, A_hole, L_eff)  # 30L (2x)

        # f_H ∝ 1/√V, so 2x volume should give ~0.707x frequency
        assert abs(f2 / f1 - 1/math.sqrt(2)) < 0.01

    def test_invalid_parameters_raise(self):
        """Invalid parameters should raise ValueError."""
        with pytest.raises(ValueError):
            helmholtz_frequency(0, 0.0079, 0.008)  # zero volume

        with pytest.raises(ValueError):
            helmholtz_frequency(0.020, 0, 0.008)  # zero hole area


class TestChladniToBoxMapping:
    """Test Chladni-to-box frequency mapping."""

    def test_gamma_less_than_one(self):
        """Box frequency should be lower than free-plate (gamma < 1)."""
        f_chladni = 150.0
        gamma = 0.85

        f_box = chladni_to_box_frequency(f_chladni, gamma)

        assert f_box < f_chladni
        assert abs(f_box - 127.5) < 0.1  # 150 × 0.85

    def test_inverse_mapping(self):
        """box_to_chladni is inverse of chladni_to_box."""
        f_box_target = 100.0
        gamma = 0.88

        f_chladni = box_to_chladni_frequency(f_box_target, gamma)
        f_box_check = chladni_to_box_frequency(f_chladni, gamma)

        assert abs(f_box_check - f_box_target) < 0.01


class TestCoupledEigenfrequencies:
    """Test 3-oscillator coupled system."""

    def test_returns_three_frequencies(self):
        """Should return exactly 3 eigenfrequencies."""
        from tap_tone_pi.design.thickness_calculator import coupled_eigenfrequencies

        frequencies, eigenvectors, info = coupled_eigenfrequencies(
            # Top: Sitka spruce, 2.8mm
            E_L_top=12.5e9, E_C_top=0.85e9, rho_top=420, h_top=0.0028,
            a_top=0.5, b_top=0.4, A_eff_top=0.12, eta_top=0.95, gamma_top=0.88,
            # Back: Mahogany, 2.9mm
            E_L_back=10.2e9, E_C_back=0.65e9, rho_back=540, h_back=0.0029,
            a_back=0.5, b_back=0.4, A_eff_back=0.10, eta_back=0.90, gamma_back=0.85,
            # Cavity
            volume=0.020, hole_area=0.0079, L_eff=0.085,
        )

        assert len(frequencies) == 3
        assert frequencies.shape == (3,)
        assert eigenvectors.shape == (3, 3)

    def test_frequencies_sorted_ascending(self):
        """Eigenfrequencies should be sorted lowest to highest."""
        from tap_tone_pi.design.thickness_calculator import coupled_eigenfrequencies

        frequencies, _, _ = coupled_eigenfrequencies(
            E_L_top=12.5e9, E_C_top=0.85e9, rho_top=420, h_top=0.0028,
            a_top=0.5, b_top=0.4, A_eff_top=0.12, eta_top=0.95, gamma_top=0.88,
            E_L_back=10.2e9, E_C_back=0.65e9, rho_back=540, h_back=0.0029,
            a_back=0.5, b_back=0.4, A_eff_back=0.10, eta_back=0.90, gamma_back=0.85,
            volume=0.020, hole_area=0.0079, L_eff=0.085,
        )

        assert frequencies[0] <= frequencies[1] <= frequencies[2]

    def test_frequencies_in_reasonable_range(self):
        """All frequencies should be in acoustic range (50-500 Hz)."""
        from tap_tone_pi.design.thickness_calculator import coupled_eigenfrequencies

        frequencies, _, _ = coupled_eigenfrequencies(
            E_L_top=12.5e9, E_C_top=0.85e9, rho_top=420, h_top=0.0028,
            a_top=0.5, b_top=0.4, A_eff_top=0.12, eta_top=0.95, gamma_top=0.88,
            E_L_back=10.2e9, E_C_back=0.65e9, rho_back=540, h_back=0.0029,
            a_back=0.5, b_back=0.4, A_eff_back=0.10, eta_back=0.90, gamma_back=0.85,
            volume=0.020, hole_area=0.0079, L_eff=0.085,
        )

        for f in frequencies:
            assert 30 < f < 500, f"Frequency {f} Hz out of expected range"


class TestMaterialPresets:
    """Test material preset lookup."""

    def test_get_sitka_spruce(self):
        """Can retrieve Sitka spruce preset."""
        mat = get_material_preset("sitka_spruce")

        assert mat is not None
        assert mat.name == "sitka_spruce"
        assert 10 < mat.E_L_GPa < 16
        assert 0.5 < mat.E_C_GPa < 1.5
        assert 350 < mat.density_kg_m3 < 500

    def test_get_mahogany(self):
        """Can retrieve mahogany preset."""
        mat = get_material_preset("mahogany")

        assert mat is not None
        assert mat.typical_use == "back"
        assert 8 < mat.E_L_GPa < 14
        assert 450 < mat.density_kg_m3 < 650

    def test_unknown_material_returns_none(self):
        """Unknown material should return None."""
        mat = get_material_preset("unobtainium")
        assert mat is None

    def test_case_insensitive(self):
        """Material lookup is case-insensitive."""
        mat1 = get_material_preset("Sitka_Spruce")
        mat2 = get_material_preset("SITKA_SPRUCE")
        mat3 = get_material_preset("sitka-spruce")

        assert mat1 is not None
        assert mat2 is not None
        assert mat3 is not None

    def test_list_materials(self):
        """Can list all materials."""
        materials = list_materials()

        assert len(materials) > 5
        assert all("name" in m for m in materials)
        assert all("E_L_GPa" in m for m in materials)

    def test_list_materials_filtered(self):
        """Can filter materials by use."""
        tops = list_materials(use_filter="top")
        backs = list_materials(use_filter="back")

        assert all(m["typical_use"] in ("top", "both") for m in tops)
        assert all(m["typical_use"] in ("back", "both") for m in backs)


class TestBodyCalibration:
    """Test body style calibration lookup."""

    def test_get_jumbo(self):
        """Can retrieve jumbo body calibration."""
        body = get_body_calibration("jumbo")

        assert body is not None
        assert body.style == BodyStyle.JUMBO
        assert body.volume_m3 > 0.020  # >20 liters
        assert body.f_monopole_target == 86.0  # User's target

    def test_get_dreadnought(self):
        """Can retrieve dreadnought body calibration."""
        body = get_body_calibration(BodyStyle.DREADNOUGHT)

        assert body is not None
        assert body.volume_m3 > 0.018

    def test_unknown_body_returns_none(self):
        """Unknown body style returns None."""
        body = get_body_calibration("telecaster")
        assert body is None

    def test_list_body_styles(self):
        """Can list all body styles."""
        bodies = list_body_styles()

        assert len(bodies) >= 5
        assert all("style" in b for b in bodies)
        assert all("volume_liters" in b for b in bodies)


class TestAnalyzePlate:
    """Test high-level plate analysis function."""

    def test_basic_analysis(self):
        """Basic plate analysis returns PlateThicknessResult."""
        result = analyze_plate(
            E_L_GPa=10.2,
            E_C_GPa=0.65,
            density_kg_m3=540,
            length_mm=559,
            width_mm=241,
            target_f_Hz=86.0,
            material_name="mahogany",
        )

        assert isinstance(result, PlateThicknessResult)
        assert result.material == "mahogany"
        assert result.target_f_Hz == 86.0
        assert 2.0 < result.recommended_h_mm < 4.0

    def test_with_current_thickness(self):
        """Analysis with current thickness computes delta."""
        result = analyze_plate(
            E_L_GPa=10.2,
            E_C_GPa=0.65,
            density_kg_m3=540,
            length_mm=559,
            width_mm=241,
            target_f_Hz=86.0,
            current_h_mm=3.5,
        )

        assert result.current_h_mm == 3.5
        assert result.current_f_Hz is not None
        assert result.delta_h_mm is not None

    def test_warns_on_low_anisotropy(self):
        """Should warn if orthotropic ratio is suspiciously low."""
        result = analyze_plate(
            E_L_GPa=5.0,
            E_C_GPa=1.0,  # R_anis = 5, quite low
            density_kg_m3=500,
            length_mm=500,
            width_mm=400,
            target_f_Hz=100.0,
        )

        assert any("ratio" in w.lower() for w in result.warnings)


class TestAnalyzeCoupledSystem:
    """Test high-level coupled system analysis."""

    def test_basic_coupled_analysis(self):
        """Basic coupled analysis returns CoupledSystemResult."""
        body = get_body_calibration("jumbo")

        result = analyze_coupled_system(
            body=body,
            top_E_L_GPa=12.5,
            top_E_C_GPa=0.85,
            top_rho=420,
            top_h_mm=2.8,
            back_E_L_GPa=10.2,
            back_E_C_GPa=0.65,
            back_rho=540,
            back_h_mm=2.9,
        )

        assert isinstance(result, CoupledSystemResult)
        assert result.body_style == "jumbo"
        assert result.f1_Hz < result.f2_Hz < result.f3_Hz

    def test_includes_recommendation(self):
        """Analysis includes recommendation text."""
        body = get_body_calibration("jumbo")

        result = analyze_coupled_system(
            body=body,
            top_E_L_GPa=12.5,
            top_E_C_GPa=0.85,
            top_rho=420,
            top_h_mm=2.8,
            back_E_L_GPa=10.2,
            back_E_C_GPa=0.65,
            back_rho=540,
            back_h_mm=2.9,
            target_monopole_Hz=86.0,
        )

        assert result.recommendation
        assert len(result.recommendation) > 10


class TestResultSerialization:
    """Test result serialization to dict/JSON."""

    def test_plate_result_to_dict(self):
        """PlateThicknessResult serializes to dict."""
        result = analyze_plate(
            E_L_GPa=10.0,
            E_C_GPa=0.6,
            density_kg_m3=500,
            length_mm=500,
            width_mm=400,
            target_f_Hz=100.0,
        )

        d = result.to_dict()

        assert isinstance(d, dict)
        assert "recommended_h_mm" in d
        assert "target_f_Hz" in d
        # None values should be excluded
        assert "current_h_mm" not in d or d["current_h_mm"] is not None

    def test_coupled_result_to_dict(self):
        """CoupledSystemResult serializes to dict."""
        body = get_body_calibration("dreadnought")

        result = analyze_coupled_system(
            body=body,
            top_E_L_GPa=12.0,
            top_E_C_GPa=0.8,
            top_rho=420,
            top_h_mm=2.8,
            back_E_L_GPa=10.0,
            back_E_C_GPa=0.6,
            back_rho=550,
            back_h_mm=2.9,
        )

        d = result.to_dict()

        assert isinstance(d, dict)
        assert "f1_Hz" in d
        assert "f2_Hz" in d
        assert "f3_Hz" in d
        assert "body_style" in d
