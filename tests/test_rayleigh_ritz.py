"""Tests for Rayleigh-Ritz modal analysis."""

import math
import pytest
import numpy as np

from tap_tone_pi.design import (
    OrthotropicPlate,
    BoundaryCondition,
    solve_rayleigh_ritz,
    RayleighRitzMode,
    RayleighRitzResult,
    format_rayleigh_ritz_report,
)


class TestOrthotropicPlate:
    """Tests for OrthotropicPlate dataclass."""

    def test_from_wood_creates_plate(self):
        """from_wood should create valid plate object."""
        plate = OrthotropicPlate.from_wood(
            E_L=12e9, E_C=0.8e9, rho=420,
            h=2.8e-3, a=0.5, b=0.38,
        )
        assert plate.E_L == 12e9
        assert plate.E_C == 0.8e9
        assert plate.rho == 420

    def test_estimates_shear_modulus(self):
        """from_wood should estimate G_LC from E_L."""
        plate = OrthotropicPlate.from_wood(
            E_L=12e9, E_C=0.8e9, rho=420,
            h=2.8e-3, a=0.5, b=0.38,
        )
        # G_LC ≈ 0.06 * E_L
        expected_G = 0.06 * 12e9
        assert abs(plate.G_LC - expected_G) < 1e6

    def test_reciprocity_relation(self):
        """Poisson ratios should satisfy reciprocity."""
        plate = OrthotropicPlate.from_wood(
            E_L=12e9, E_C=0.8e9, rho=420,
            h=2.8e-3, a=0.5, b=0.38,
            nu_LC=0.3,
        )
        # nu_CL / E_C = nu_LC / E_L
        lhs = plate.nu_CL / plate.E_C
        rhs = plate.nu_LC / plate.E_L
        assert abs(lhs - rhs) < 1e-15

    def test_bending_stiffness_D11(self):
        """D11 should be positive and scale correctly."""
        plate = OrthotropicPlate.from_wood(
            E_L=12e9, E_C=0.8e9, rho=420,
            h=2.8e-3, a=0.5, b=0.38,
        )
        assert plate.D11 > 0
        # D11 should be larger than D22 for E_L > E_C
        assert plate.D11 > plate.D22

    def test_orthotropy_ratio(self):
        """Orthotropy ratio should be E_L/E_C."""
        plate = OrthotropicPlate.from_wood(
            E_L=12e9, E_C=0.8e9, rho=420,
            h=2.8e-3, a=0.5, b=0.38,
        )
        assert abs(plate.orthotropy_ratio - 15.0) < 0.1

    def test_mass_per_area(self):
        """Mass per area should be rho * h."""
        plate = OrthotropicPlate.from_wood(
            E_L=12e9, E_C=0.8e9, rho=420,
            h=2.8e-3, a=0.5, b=0.38,
        )
        expected = 420 * 2.8e-3
        assert abs(plate.mass_per_area - expected) < 1e-6


class TestSolveRayleighRitz:
    """Tests for solve_rayleigh_ritz function."""

    def test_returns_result_object(self):
        """Should return RayleighRitzResult."""
        plate = OrthotropicPlate.from_wood(
            E_L=12e9, E_C=0.8e9, rho=420,
            h=2.8e-3, a=0.5, b=0.38,
        )
        result = solve_rayleigh_ritz(plate, n_modes_x=3, n_modes_y=3)
        assert isinstance(result, RayleighRitzResult)

    def test_returns_positive_frequencies(self):
        """All frequencies should be positive."""
        plate = OrthotropicPlate.from_wood(
            E_L=12e9, E_C=0.8e9, rho=420,
            h=2.8e-3, a=0.5, b=0.38,
        )
        result = solve_rayleigh_ritz(plate, n_modes_x=3, n_modes_y=3)
        for mode in result.modes:
            assert mode.frequency_Hz > 0

    def test_frequencies_sorted_ascending(self):
        """Frequencies should be sorted in ascending order."""
        plate = OrthotropicPlate.from_wood(
            E_L=12e9, E_C=0.8e9, rho=420,
            h=2.8e-3, a=0.5, b=0.38,
        )
        result = solve_rayleigh_ritz(plate, n_modes_x=3, n_modes_y=3)
        freqs = result.frequencies_Hz
        for i in range(len(freqs) - 1):
            assert freqs[i] <= freqs[i + 1]

    def test_fundamental_mode_lowest(self):
        """Mode 1 should be the fundamental (lowest frequency)."""
        plate = OrthotropicPlate.from_wood(
            E_L=12e9, E_C=0.8e9, rho=420,
            h=2.8e-3, a=0.5, b=0.38,
        )
        result = solve_rayleigh_ritz(plate, n_modes_x=4, n_modes_y=4)
        assert result.modes[0].mode_number == 1
        assert result.modes[0].frequency_Hz == min(result.frequencies_Hz)

    def test_thicker_plate_higher_frequency(self):
        """Thicker plate should have higher fundamental frequency."""
        plate_thin = OrthotropicPlate.from_wood(
            E_L=12e9, E_C=0.8e9, rho=420,
            h=2.0e-3, a=0.5, b=0.38,
        )
        plate_thick = OrthotropicPlate.from_wood(
            E_L=12e9, E_C=0.8e9, rho=420,
            h=4.0e-3, a=0.5, b=0.38,
        )
        result_thin = solve_rayleigh_ritz(plate_thin, n_modes_x=3, n_modes_y=3)
        result_thick = solve_rayleigh_ritz(plate_thick, n_modes_x=3, n_modes_y=3)

        assert result_thick.modes[0].frequency_Hz > result_thin.modes[0].frequency_Hz

    def test_clamped_higher_than_simply_supported(self):
        """Clamped BC should give higher frequencies than SS."""
        plate = OrthotropicPlate.from_wood(
            E_L=12e9, E_C=0.8e9, rho=420,
            h=2.8e-3, a=0.5, b=0.38,
        )
        result_ss = solve_rayleigh_ritz(
            plate, n_modes_x=3, n_modes_y=3,
            bc_x=BoundaryCondition.SIMPLY_SUPPORTED,
            bc_y=BoundaryCondition.SIMPLY_SUPPORTED,
        )
        result_clamped = solve_rayleigh_ritz(
            plate, n_modes_x=3, n_modes_y=3,
            bc_x=BoundaryCondition.CLAMPED,
            bc_y=BoundaryCondition.CLAMPED,
        )
        # Clamped fundamental should be higher
        assert result_clamped.modes[0].frequency_Hz > result_ss.modes[0].frequency_Hz

    def test_mode_has_coefficients(self):
        """Each mode should have expansion coefficients."""
        plate = OrthotropicPlate.from_wood(
            E_L=12e9, E_C=0.8e9, rho=420,
            h=2.8e-3, a=0.5, b=0.38,
        )
        result = solve_rayleigh_ritz(plate, n_modes_x=3, n_modes_y=3)
        for mode in result.modes:
            assert len(mode.coefficients) == 9  # 3x3

    def test_stiffness_matrix_symmetric(self):
        """Stiffness matrix should be symmetric."""
        plate = OrthotropicPlate.from_wood(
            E_L=12e9, E_C=0.8e9, rho=420,
            h=2.8e-3, a=0.5, b=0.38,
        )
        result = solve_rayleigh_ritz(plate, n_modes_x=3, n_modes_y=3)
        # Check symmetry
        diff = np.abs(result.K - result.K.T)
        assert np.max(diff) < 1e-10

    def test_mass_matrix_symmetric(self):
        """Mass matrix should be symmetric."""
        plate = OrthotropicPlate.from_wood(
            E_L=12e9, E_C=0.8e9, rho=420,
            h=2.8e-3, a=0.5, b=0.38,
        )
        result = solve_rayleigh_ritz(plate, n_modes_x=3, n_modes_y=3)
        # Check symmetry
        diff = np.abs(result.M - result.M.T)
        assert np.max(diff) < 1e-10

    def test_frequency_in_realistic_range(self):
        """Fundamental frequency should be in realistic range for guitar."""
        # Typical guitar top: ~80-200 Hz fundamental
        plate = OrthotropicPlate.from_wood(
            E_L=12e9, E_C=0.8e9, rho=420,
            h=2.8e-3, a=0.45, b=0.35,
        )
        result = solve_rayleigh_ritz(
            plate, n_modes_x=4, n_modes_y=4,
            bc_x=BoundaryCondition.SIMPLY_SUPPORTED,
            bc_y=BoundaryCondition.SIMPLY_SUPPORTED,
        )
        f1 = result.modes[0].frequency_Hz
        assert 20 < f1 < 300  # Broad reasonable range


class TestRayleighRitzMode:
    """Tests for RayleighRitzMode dataclass."""

    def test_omega_property(self):
        """omega_rad_s should be 2*pi*f."""
        mode = RayleighRitzMode(
            mode_number=1,
            frequency_Hz=100.0,
            mode_indices=(1, 1),
            coefficients=np.array([1.0]),
        )
        expected = 2 * math.pi * 100.0
        assert abs(mode.omega_rad_s - expected) < 1e-10


class TestFormatRayleighRitzReport:
    """Tests for format_rayleigh_ritz_report function."""

    def test_returns_string(self):
        """Should return formatted string."""
        plate = OrthotropicPlate.from_wood(
            E_L=12e9, E_C=0.8e9, rho=420,
            h=2.8e-3, a=0.5, b=0.38,
        )
        result = solve_rayleigh_ritz(plate, n_modes_x=3, n_modes_y=3)
        report = format_rayleigh_ritz_report(result)
        assert isinstance(report, str)

    def test_includes_frequencies(self):
        """Report should include mode frequencies."""
        plate = OrthotropicPlate.from_wood(
            E_L=12e9, E_C=0.8e9, rho=420,
            h=2.8e-3, a=0.5, b=0.38,
        )
        result = solve_rayleigh_ritz(plate, n_modes_x=3, n_modes_y=3)
        report = format_rayleigh_ritz_report(result)
        assert "Hz" in report
        assert "Mode" in report

    def test_includes_boundary_conditions(self):
        """Report should show boundary conditions."""
        plate = OrthotropicPlate.from_wood(
            E_L=12e9, E_C=0.8e9, rho=420,
            h=2.8e-3, a=0.5, b=0.38,
        )
        result = solve_rayleigh_ritz(
            plate, n_modes_x=3, n_modes_y=3,
            bc_x=BoundaryCondition.CLAMPED,
            bc_y=BoundaryCondition.SIMPLY_SUPPORTED,
        )
        report = format_rayleigh_ritz_report(result)
        assert "clamped" in report.lower() or "simply" in report.lower()
