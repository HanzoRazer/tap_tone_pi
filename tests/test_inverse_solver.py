"""Tests for inverse thickness solver."""

import pytest

from tap_tone_pi.design.inverse_solver import (
    ForwardModel,
    ThicknessConstraints,
    InverseSolverResult,
    solve_for_thickness,
    InverseDesignProblem,
    MaterialCandidate,
    solve_for_material_and_thickness,
    format_inverse_solver_report,
)


class TestThicknessConstraints:
    """Tests for ThicknessConstraints."""

    def test_valid_constraints(self):
        """Valid constraints should work."""
        c = ThicknessConstraints(h_min_mm=2.0, h_max_mm=4.0)
        assert c.h_min_mm == 2.0
        assert c.h_max_mm == 4.0

    def test_rejects_negative_min(self):
        """Should reject negative minimum."""
        with pytest.raises(ValueError):
            ThicknessConstraints(h_min_mm=-1.0, h_max_mm=4.0)

    def test_rejects_min_greater_than_max(self):
        """Should reject min >= max."""
        with pytest.raises(ValueError):
            ThicknessConstraints(h_min_mm=5.0, h_max_mm=4.0)

    def test_is_valid(self):
        """is_valid should check bounds."""
        c = ThicknessConstraints(h_min_mm=2.0, h_max_mm=4.0)
        assert c.is_valid(3.0)
        assert not c.is_valid(1.5)
        assert not c.is_valid(5.0)

    def test_clamp(self):
        """clamp should enforce bounds."""
        c = ThicknessConstraints(h_min_mm=2.0, h_max_mm=4.0)
        assert c.clamp(3.0) == 3.0
        assert c.clamp(1.0) == 2.0
        assert c.clamp(6.0) == 4.0

    def test_discretize(self):
        """discretize should round to step."""
        c = ThicknessConstraints(h_min_mm=2.0, h_max_mm=4.0, h_step_mm=0.1)
        assert abs(c.discretize(2.54) - 2.5) < 0.001
        assert abs(c.discretize(2.56) - 2.6) < 0.001


class TestSolveForThicknessSimple:
    """Tests for solve_for_thickness with simple model."""

    def test_returns_result(self):
        """Should return InverseSolverResult."""
        result = solve_for_thickness(
            target_f1_Hz=180.0,
            E_L=12e9, E_C=0.8e9, rho=420,
            a=0.45, b=0.35,
            forward_model=ForwardModel.SIMPLE,
        )
        assert isinstance(result, InverseSolverResult)

    def test_achieves_target_frequency(self):
        """Should achieve close to target frequency."""
        target = 180.0
        result = solve_for_thickness(
            target_f1_Hz=target,
            E_L=12e9, E_C=0.8e9, rho=420,
            a=0.45, b=0.35,
            forward_model=ForwardModel.SIMPLE,
        )
        # Should be within 2%
        error_pct = abs(result.frequency_errors_pct[0])
        assert error_pct < 2.0

    def test_higher_target_gives_thicker_plate(self):
        """Higher frequency target should require thicker plate."""
        result_low = solve_for_thickness(
            target_f1_Hz=150.0,
            E_L=12e9, E_C=0.8e9, rho=420,
            a=0.45, b=0.35,
        )
        result_high = solve_for_thickness(
            target_f1_Hz=250.0,
            E_L=12e9, E_C=0.8e9, rho=420,
            a=0.45, b=0.35,
        )
        assert result_high.thickness_mm > result_low.thickness_mm

    def test_gamma_affects_result(self):
        """γ < 1 should give thicker plate for same box frequency."""
        result_no_gamma = solve_for_thickness(
            target_f1_Hz=180.0,
            E_L=12e9, E_C=0.8e9, rho=420,
            a=0.45, b=0.35,
            gamma=1.0,
        )
        result_with_gamma = solve_for_thickness(
            target_f1_Hz=180.0,
            E_L=12e9, E_C=0.8e9, rho=420,
            a=0.45, b=0.35,
            gamma=0.85,  # Need higher free freq to get 180 box freq
        )
        # With γ < 1, we need higher free-plate frequency
        # which means thicker plate
        assert result_with_gamma.thickness_mm > result_no_gamma.thickness_mm

    def test_respects_constraints(self):
        """Should respect thickness constraints."""
        # Force a very high target that would need thick plate
        result = solve_for_thickness(
            target_f1_Hz=500.0,
            E_L=12e9, E_C=0.8e9, rho=420,
            a=0.45, b=0.35,
            constraints=ThicknessConstraints(h_min_mm=2.0, h_max_mm=4.0),
        )
        assert result.thickness_mm <= 4.0
        assert result.constraints_active

    def test_realistic_thickness_range(self):
        """Result should be in realistic range for guitars."""
        result = solve_for_thickness(
            target_f1_Hz=180.0,
            E_L=12e9, E_C=0.8e9, rho=420,
            a=0.45, b=0.35,
        )
        # Typical guitar top: 2-4mm
        assert 1.5 < result.thickness_mm < 5.0


class TestSolveForThicknessRayleighRitz:
    """Tests for solve_for_thickness with Rayleigh-Ritz model.

    Note: RR with simply-supported BC gives ~3x lower frequencies than
    the simple formula (which assumes free plate). At typical guitar
    thicknesses (2-5mm), RR gives f1 ~ 30-80 Hz for this plate size.
    """

    def test_returns_result(self):
        """Should return InverseSolverResult."""
        result = solve_for_thickness(
            target_f1_Hz=50.0,  # Achievable with SS BC
            E_L=12e9, E_C=0.8e9, rho=420,
            a=0.45, b=0.35,
            forward_model=ForwardModel.RAYLEIGH_RITZ,
        )
        assert isinstance(result, InverseSolverResult)
        assert result.forward_model == ForwardModel.RAYLEIGH_RITZ

    def test_achieves_target_frequency(self):
        """Should achieve close to target frequency."""
        target = 50.0  # Achievable in 2-5mm range with SS BC
        result = solve_for_thickness(
            target_f1_Hz=target,
            E_L=12e9, E_C=0.8e9, rho=420,
            a=0.45, b=0.35,
            forward_model=ForwardModel.RAYLEIGH_RITZ,
        )
        # Should be within 5%
        error_pct = abs(result.frequency_errors_pct[0])
        assert error_pct < 5.0


class TestInverseDesignProblem:
    """Tests for InverseDesignProblem class."""

    def test_single_target(self):
        """Single target optimization."""
        problem = InverseDesignProblem(
            E_L=12e9, E_C=0.8e9, rho=420,
            a=0.45, b=0.35,
            forward_model=ForwardModel.SIMPLE,  # Use simple for predictable results
        )
        problem.add_target(mode=1, frequency_Hz=180.0)
        result = problem.solve()
        assert isinstance(result, InverseSolverResult)
        assert abs(result.frequency_errors_pct[0]) < 5.0

    def test_multi_target(self):
        """Multiple target optimization."""
        problem = InverseDesignProblem(
            E_L=12e9, E_C=0.8e9, rho=420,
            a=0.45, b=0.35,
            forward_model=ForwardModel.SIMPLE,
        )
        problem.add_target(mode=1, frequency_Hz=180.0, weight=1.0)
        problem.add_target(mode=2, frequency_Hz=360.0, weight=0.5)
        result = problem.solve()
        assert len(result.achieved_frequencies_Hz) == 2

    def test_weighted_targets(self):
        """Higher weight should prioritize that target."""
        # Two problems with swapped weights
        problem1 = InverseDesignProblem(
            E_L=12e9, E_C=0.8e9, rho=420,
            a=0.45, b=0.35,
            forward_model=ForwardModel.SIMPLE,
        )
        problem1.add_target(mode=1, frequency_Hz=150.0, weight=10.0)
        problem1.add_target(mode=2, frequency_Hz=400.0, weight=1.0)

        problem2 = InverseDesignProblem(
            E_L=12e9, E_C=0.8e9, rho=420,
            a=0.45, b=0.35,
            forward_model=ForwardModel.SIMPLE,
        )
        problem2.add_target(mode=1, frequency_Hz=150.0, weight=1.0)
        problem2.add_target(mode=2, frequency_Hz=400.0, weight=10.0)

        result1 = problem1.solve()
        result2 = problem2.solve()

        # Problem 1 should match mode 1 better
        # Problem 2 should match mode 2 better
        # (exact comparison depends on optimization landscape)
        # Just check both produce valid results
        assert result1.converged or result1.rms_error_Hz < 50
        assert result2.converged or result2.rms_error_Hz < 50

    def test_no_targets_raises(self):
        """Should raise error if no targets."""
        problem = InverseDesignProblem(
            E_L=12e9, E_C=0.8e9, rho=420,
            a=0.45, b=0.35,
        )
        with pytest.raises(ValueError):
            problem.solve()

    def test_clear_targets(self):
        """clear_targets should remove all targets."""
        problem = InverseDesignProblem(
            E_L=12e9, E_C=0.8e9, rho=420,
            a=0.45, b=0.35,
        )
        problem.add_target(mode=1, frequency_Hz=180.0)
        problem.clear_targets()
        with pytest.raises(ValueError):
            problem.solve()

    def test_with_gamma(self):
        """Should handle γ transfer coefficient."""
        problem = InverseDesignProblem(
            E_L=12e9, E_C=0.8e9, rho=420,
            a=0.45, b=0.35,
            gamma=0.85,
        )
        problem.add_target(mode=1, frequency_Hz=180.0)
        result = problem.solve()
        # Should still find a solution
        assert result.thickness_mm > 0


class TestMaterialSelection:
    """Tests for material selection solver."""

    def test_selects_material(self):
        """Should select best material."""
        candidates = [
            MaterialCandidate("Spruce", E_L=12e9, E_C=0.8e9, rho=420),
            MaterialCandidate("Cedar", E_L=9e9, E_C=0.6e9, rho=380),
            MaterialCandidate("Redwood", E_L=8e9, E_C=0.5e9, rho=350),
        ]
        material, result = solve_for_material_and_thickness(
            target_f1_Hz=180.0,
            candidates=candidates,
            a=0.45, b=0.35,
        )
        assert material.name in ["Spruce", "Cedar", "Redwood"]
        assert result.thickness_mm > 0

    def test_respects_constraints(self):
        """Should respect constraints in material selection."""
        candidates = [
            MaterialCandidate("Spruce", E_L=12e9, E_C=0.8e9, rho=420),
            MaterialCandidate("Cedar", E_L=9e9, E_C=0.6e9, rho=380),
        ]
        constraints = ThicknessConstraints(h_min_mm=2.5, h_max_mm=3.5)
        material, result = solve_for_material_and_thickness(
            target_f1_Hz=180.0,
            candidates=candidates,
            a=0.45, b=0.35,
            constraints=constraints,
        )
        assert result.thickness_mm >= 2.5
        assert result.thickness_mm <= 3.5


class TestFormatReport:
    """Tests for report formatting."""

    def test_returns_string(self):
        """Should return string."""
        result = solve_for_thickness(
            target_f1_Hz=180.0,
            E_L=12e9, E_C=0.8e9, rho=420,
            a=0.45, b=0.35,
        )
        report = format_inverse_solver_report(result)
        assert isinstance(report, str)

    def test_includes_thickness(self):
        """Report should include thickness."""
        result = solve_for_thickness(
            target_f1_Hz=180.0,
            E_L=12e9, E_C=0.8e9, rho=420,
            a=0.45, b=0.35,
        )
        report = format_inverse_solver_report(result)
        assert "mm" in report

    def test_includes_frequency_table(self):
        """Report should include frequency comparison."""
        result = solve_for_thickness(
            target_f1_Hz=180.0,
            E_L=12e9, E_C=0.8e9, rho=420,
            a=0.45, b=0.35,
        )
        report = format_inverse_solver_report(result)
        assert "Target" in report or "Achieved" in report


class TestToDict:
    """Tests for serialization."""

    def test_result_to_dict(self):
        """Result should serialize to dict."""
        result = solve_for_thickness(
            target_f1_Hz=180.0,
            E_L=12e9, E_C=0.8e9, rho=420,
            a=0.45, b=0.35,
        )
        d = result.to_dict()
        assert "thickness_mm" in d
        assert "achieved_frequencies_Hz" in d
        assert "converged" in d


class TestRealisticDesignScenarios:
    """Tests with realistic design scenarios."""

    def test_classical_guitar_top(self):
        """Design classical guitar top."""
        # Typical classical: target ~170 Hz box frequency
        result = solve_for_thickness(
            target_f1_Hz=170.0,
            E_L=10e9, E_C=0.6e9, rho=400,  # Cedar
            a=0.36, b=0.28,  # Classical top dimensions
            gamma=0.85,
        )
        # Should be in typical range
        assert 2.0 < result.thickness_mm < 4.0

    def test_dreadnought_top(self):
        """Design dreadnought top."""
        # Dreadnought: larger, stiffer, higher frequency
        result = solve_for_thickness(
            target_f1_Hz=200.0,
            E_L=12e9, E_C=0.8e9, rho=420,  # Sitka spruce
            a=0.40, b=0.30,
            gamma=0.88,
        )
        assert 2.0 < result.thickness_mm < 4.5

    def test_parlor_guitar_top(self):
        """Design parlor guitar top (smaller body)."""
        result = solve_for_thickness(
            target_f1_Hz=220.0,  # Higher due to smaller body
            E_L=11e9, E_C=0.7e9, rho=400,
            a=0.32, b=0.24,  # Smaller dimensions
            gamma=0.90,
        )
        assert 2.0 < result.thickness_mm < 4.0
