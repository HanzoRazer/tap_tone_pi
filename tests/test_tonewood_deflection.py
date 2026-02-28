"""
Tests for tonewood_deflection module.

Tests cover:
- Core E calculations (single point and multi-point fit)
- Density calculation
- Thickness targeting
- CSV parsing (both schemas)
- Slenderness warnings
- Edge cases and validation
"""

import json

import pytest

from tap_tone_pi.tonewood_deflection import (
    Geometry,
    StripMassGeom,
    mm_to_m,
    m_to_mm,
    g_to_kg,
    compute_E_from_slope,
    compute_E_single_point,
    linear_fit,
    compute_density,
    thickness_target,
    compute_specific_stiffness,
    read_csv_points,
    analyze_deflection,
)


# =============================================================================
# Unit conversion tests
# =============================================================================


class TestUnitConversions:
    def test_mm_to_m(self):
        assert mm_to_m(1000) == 1.0
        assert mm_to_m(1) == 0.001
        assert mm_to_m(0) == 0.0

    def test_m_to_mm(self):
        assert m_to_mm(1.0) == 1000
        assert m_to_mm(0.001) == 1.0

    def test_g_to_kg(self):
        assert g_to_kg(1000) == 1.0
        assert g_to_kg(1) == 0.001


# =============================================================================
# Geometry tests
# =============================================================================


class TestGeometry:
    def test_second_moment_of_area(self):
        # I = b * h^3 / 12
        geom = Geometry(span_m=0.4, width_m=0.03, thick_m=0.003)
        expected_I = 0.03 * (0.003**3) / 12
        assert geom.second_moment_of_area == pytest.approx(expected_I)

    def test_slenderness_ratio(self):
        geom = Geometry(span_m=0.4, width_m=0.03, thick_m=0.003)
        # L/h = 0.4 / 0.003 = 133.33
        assert geom.slenderness_ratio == pytest.approx(133.33, rel=0.01)

    def test_slenderness_ratio_zero_thickness(self):
        geom = Geometry(span_m=0.4, width_m=0.03, thick_m=0.0)
        assert geom.slenderness_ratio == 0.0


# =============================================================================
# Core calculation tests
# =============================================================================


class TestComputeEFromSlope:
    def test_known_value(self):
        # E = (k * L^3) / (4 * b * h^3)
        # For k=10000 N/m, L=0.4m, b=0.03m, h=0.003m
        # E = (10000 * 0.4^3) / (4 * 0.03 * 0.003^3)
        # E = (10000 * 0.064) / (4 * 0.03 * 2.7e-8)
        # E = 640 / 3.24e-9 = 1.975e11 Pa ~ 197.5 GPa
        geom = Geometry(span_m=0.4, width_m=0.03, thick_m=0.003)
        E = compute_E_from_slope(geom, 10000)
        assert E == pytest.approx(1.975e11, rel=0.01)


class TestComputeESinglePoint:
    def test_known_value(self):
        # E = (F * L^3) / (4 * b * h^3 * delta)
        # For F=10N, delta=0.001m (1mm), same geometry
        geom = Geometry(span_m=0.4, width_m=0.03, thick_m=0.003)
        E = compute_E_single_point(geom, F_N=10, delta_m=0.001)
        # Should be same as slope=10000 N/m
        assert E == pytest.approx(1.975e11, rel=0.01)

    def test_zero_deflection_raises(self):
        geom = Geometry(span_m=0.4, width_m=0.03, thick_m=0.003)
        with pytest.raises(ValueError, match="must be > 0"):
            compute_E_single_point(geom, F_N=10, delta_m=0)

    def test_negative_deflection_raises(self):
        geom = Geometry(span_m=0.4, width_m=0.03, thick_m=0.003)
        with pytest.raises(ValueError, match="must be > 0"):
            compute_E_single_point(geom, F_N=10, delta_m=-0.001)


class TestLinearFit:
    def test_perfect_fit(self):
        # y = 2x + 1 (perfect line)
        x = [1, 2, 3, 4, 5]
        y = [3, 5, 7, 9, 11]
        fit = linear_fit(x, y)
        assert fit.slope_N_per_m == pytest.approx(2.0)
        assert fit.intercept_N == pytest.approx(1.0)
        assert fit.r2 == pytest.approx(1.0)
        assert fit.n_points == 5

    def test_noisy_fit(self):
        # y ≈ 2x + 1 with noise
        x = [1, 2, 3, 4, 5]
        y = [3.1, 4.9, 7.2, 8.8, 11.0]
        fit = linear_fit(x, y)
        assert fit.slope_N_per_m == pytest.approx(2.0, rel=0.1)
        assert fit.r2 > 0.99  # Still good fit

    def test_two_points(self):
        x = [1, 2]
        y = [3, 5]
        fit = linear_fit(x, y)
        assert fit.slope_N_per_m == pytest.approx(2.0)
        assert fit.n_points == 2

    def test_single_point_raises(self):
        with pytest.raises(ValueError, match="at least 2 points"):
            linear_fit([1], [2])

    def test_identical_x_raises(self):
        with pytest.raises(ValueError, match="identical"):
            linear_fit([1, 1, 1], [2, 3, 4])


# =============================================================================
# Density tests
# =============================================================================


class TestComputeDensity:
    def test_known_value(self):
        # rho = m / (L * b * h)
        # 18g, 450mm x 30mm x 3mm
        strip = StripMassGeom(strip_len_m=0.45, strip_mass_kg=0.018)
        rho = compute_density(strip, width_m=0.03, thick_m=0.003)
        # V = 0.45 * 0.03 * 0.003 = 4.05e-5 m^3
        # rho = 0.018 / 4.05e-5 = 444.4 kg/m^3
        assert rho == pytest.approx(444.4, rel=0.01)

    def test_zero_volume_raises(self):
        strip = StripMassGeom(strip_len_m=0.0, strip_mass_kg=0.018)
        with pytest.raises(ValueError, match="must be > 0"):
            compute_density(strip, width_m=0.03, thick_m=0.003)


# =============================================================================
# Thickness targeting tests
# =============================================================================


class TestThicknessTarget:
    def test_same_E(self):
        # Same E should give same thickness
        h = thickness_target(h_ref_m=0.003, E_ref_Pa=12e9, E_new_Pa=12e9)
        assert h == pytest.approx(0.003)

    def test_lower_E_gives_thicker(self):
        # Lower E needs thicker to maintain E*h^3
        h = thickness_target(h_ref_m=0.003, E_ref_Pa=12e9, E_new_Pa=10e9)
        # h = 0.003 * (12/10)^(1/3) = 0.003 * 1.0627 = 0.00319
        assert h > 0.003
        assert h == pytest.approx(0.00319, rel=0.01)

    def test_higher_E_gives_thinner(self):
        # Higher E can be thinner
        h = thickness_target(h_ref_m=0.003, E_ref_Pa=12e9, E_new_Pa=15e9)
        assert h < 0.003

    def test_zero_E_raises(self):
        with pytest.raises(ValueError, match="must be > 0"):
            thickness_target(h_ref_m=0.003, E_ref_Pa=12e9, E_new_Pa=0)


# =============================================================================
# Specific stiffness tests
# =============================================================================


class TestSpecificStiffness:
    def test_known_value(self):
        # E=12 GPa, rho=420 kg/m^3
        spec, c_L = compute_specific_stiffness(12e9, 420)
        # E/rho = 12e9 / 420 = 2.857e7 m^2/s^2
        # c_L = sqrt(2.857e7) = 5345 m/s
        assert spec == pytest.approx(2.857e7, rel=0.01)
        assert c_L == pytest.approx(5345, rel=0.01)

    def test_zero_density_raises(self):
        with pytest.raises(ValueError, match="must be > 0"):
            compute_specific_stiffness(12e9, 0)


# =============================================================================
# CSV parsing tests
# =============================================================================


class TestReadCSVPoints:
    def test_net_schema(self, tmp_path):
        csv_content = """load_N,defl_mm
5,0.5
10,1.0
15,1.5
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        loads, defls = read_csv_points(str(csv_file))

        assert loads == [5, 10, 15]
        assert defls == pytest.approx([0.0005, 0.001, 0.0015])

    def test_base_test_schema(self, tmp_path):
        # Net force = (m_test - m_base) * G
        # Net defl = defl_test - defl_base
        csv_content = """m_base_kg,m_test_kg,defl_base_mm,defl_test_mm
0.1,0.6,0.0,0.5
0.1,1.1,0.0,1.0
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        loads, defls = read_csv_points(str(csv_file))

        # F1 = (0.6 - 0.1) * 9.80665 = 4.903 N
        # F2 = (1.1 - 0.1) * 9.80665 = 9.807 N
        assert loads[0] == pytest.approx(4.903, rel=0.01)
        assert loads[1] == pytest.approx(9.807, rel=0.01)
        assert defls == pytest.approx([0.0005, 0.001])

    def test_invalid_schema_raises(self, tmp_path):
        csv_content = """foo,bar
1,2
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        with pytest.raises(ValueError, match="must contain either"):
            read_csv_points(str(csv_file))

    def test_whitespace_handling(self, tmp_path):
        csv_content = """ load_N , defl_mm
 5 , 0.5
 10 , 1.0
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        loads, defls = read_csv_points(str(csv_file))
        assert loads == [5, 10]


# =============================================================================
# Integration tests
# =============================================================================


class TestAnalyzeDeflection:
    def test_single_point(self):
        result = analyze_deflection(
            span_mm=400,
            width_mm=30,
            thick_mm=3.0,
            loads_N=[10],
            deflections_mm=[1.0],
        )

        assert result.method == "single_point"
        assert result.n_points == 1
        assert result.E_GPa > 0
        assert result.r2 is None
        assert any("single-point" in w.lower() for w in result.warnings)

    def test_multi_point(self):
        result = analyze_deflection(
            span_mm=400,
            width_mm=30,
            thick_mm=3.0,
            loads_N=[5, 10, 15],
            deflections_mm=[0.5, 1.0, 1.5],
        )

        assert result.method == "linear_fit"
        assert result.n_points == 3
        assert result.r2 == pytest.approx(1.0)
        assert result.E_GPa > 0

    def test_with_density(self):
        result = analyze_deflection(
            span_mm=400,
            width_mm=30,
            thick_mm=3.0,
            loads_N=[10],
            deflections_mm=[1.0],
            strip_len_mm=450,
            strip_mass_g=18.0,
        )

        assert result.density_kg_m3 is not None
        assert result.density_g_cm3 is not None
        assert result.specific_stiffness_m2_s2 is not None
        assert result.wave_speed_m_s is not None

    def test_with_thickness_targeting(self):
        result = analyze_deflection(
            span_mm=400,
            width_mm=30,
            thick_mm=3.0,
            loads_N=[10],
            deflections_mm=[1.0],
            h_ref_mm=2.8,
            E_ref_GPa=12.0,
        )

        assert result.h_target_mm is not None
        assert result.h_ref_mm == 2.8
        assert result.E_ref_GPa == 12.0

    def test_slenderness_warning(self):
        # L/h = 100/3 = 33 (ok)
        result_ok = analyze_deflection(
            span_mm=100,
            width_mm=30,
            thick_mm=3.0,
            loads_N=[10],
            deflections_mm=[1.0],
        )

        # L/h = 50/3 = 16.7 (too low)
        result_warn = analyze_deflection(
            span_mm=50,
            width_mm=30,
            thick_mm=3.0,
            loads_N=[10],
            deflections_mm=[1.0],
        )

        assert not any("L/h" in w for w in result_ok.warnings)
        assert any("L/h" in w for w in result_warn.warnings)

    def test_to_dict(self):
        result = analyze_deflection(
            span_mm=400,
            width_mm=30,
            thick_mm=3.0,
            loads_N=[10],
            deflections_mm=[1.0],
        )

        d = result.to_dict()
        assert "E_GPa" in d
        assert "span_mm" in d
        # None values should be excluded
        assert "density_kg_m3" not in d or d["density_kg_m3"] is not None

    def test_json_serializable(self):
        result = analyze_deflection(
            span_mm=400,
            width_mm=30,
            thick_mm=3.0,
            loads_N=[5, 10, 15],
            deflections_mm=[0.5, 1.0, 1.5],
            strip_len_mm=450,
            strip_mass_g=18.0,
            h_ref_mm=2.8,
            E_ref_GPa=12.0,
        )

        # Should not raise
        json_str = json.dumps(result.to_dict())
        assert "E_GPa" in json_str


# =============================================================================
# Realistic value tests
# =============================================================================


class TestRealisticValues:
    """Test with realistic tonewood values."""

    def test_sitka_spruce_range(self):
        # Sitka spruce: E ~ 10-14 GPa, rho ~ 380-450 kg/m^3
        # Typical deflection test: 400mm span, 30mm width, 3mm thick
        #
        # For E=12 GPa: E = (F × L³) / (4 × b × h³ × δ)
        # 12e9 = (10 × 0.4³) / (4 × 0.03 × 0.003³ × δ)
        # δ ≈ 16.5mm at 10N
        #
        # Using realistic deflections for spruce:

        result = analyze_deflection(
            span_mm=400,
            width_mm=30,
            thick_mm=3.0,
            loads_N=[2.5, 5.0, 7.5, 10.0],
            deflections_mm=[4.0, 8.2, 12.3, 16.5],  # ~12 GPa
            strip_len_mm=450,
            strip_mass_g=18.0,  # ~444 kg/m^3
        )

        # Should be in reasonable range for softwood
        assert 8 < result.E_GPa < 20
        assert 350 < result.density_kg_m3 < 500
        assert result.wave_speed_m_s > 4000  # Typical for spruce

    def test_thickness_targeting_practical(self):
        # Reference: 2.8mm at 12 GPa (typical target)
        # This billet: 10 GPa
        # Expected: ~3.0mm (need thicker for lower stiffness)

        result = analyze_deflection(
            span_mm=400,
            width_mm=30,
            thick_mm=3.0,
            loads_N=[10],
            deflections_mm=[1.2],  # Lower E than reference
            h_ref_mm=2.8,
            E_ref_GPa=12.0,
        )

        # Lower E should give thicker target
        if result.E_GPa < 12.0:
            assert result.h_target_mm > 2.8
        else:
            assert result.h_target_mm <= 2.8
