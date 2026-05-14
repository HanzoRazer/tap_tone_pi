"""Tests for alpha/beta physical formulation."""

import math
import pytest

from tap_tone_pi.design import (
    compute_alpha,
    compute_beta,
    compute_gamma,
    plate_bending_stiffness,
    brace_stiffness,
    brace_mass,
    air_virtual_mass,
    analyze_alpha_beta,
    format_alpha_beta_report,
    AlphaBetaResult,
)


class TestPlateBendingStiffness:
    """Tests for plate_bending_stiffness function."""

    def test_returns_positive_value(self):
        """Bending stiffness must be positive."""
        D = plate_bending_stiffness(E_L=12e9, E_C=0.8e9, h=2.8e-3)
        assert D > 0

    def test_scales_with_h_cubed(self):
        """Stiffness should scale with h^3."""
        D1 = plate_bending_stiffness(E_L=12e9, E_C=0.8e9, h=2.0e-3)
        D2 = plate_bending_stiffness(E_L=12e9, E_C=0.8e9, h=4.0e-3)
        # D2/D1 should be (4/2)^3 = 8
        ratio = D2 / D1
        assert abs(ratio - 8.0) < 0.01

    def test_scales_with_modulus(self):
        """Stiffness should scale with sqrt(E_L * E_C)."""
        D1 = plate_bending_stiffness(E_L=10e9, E_C=1.0e9, h=3e-3)
        D2 = plate_bending_stiffness(E_L=40e9, E_C=4.0e9, h=3e-3)
        # E_eff ratio = sqrt(40*4 / 10*1) = sqrt(16) = 4
        ratio = D2 / D1
        assert abs(ratio - 4.0) < 0.01


class TestComputeAlpha:
    """Tests for compute_alpha function."""

    def test_free_boundary_gives_alpha_one(self):
        """Free boundary should give alpha = 1.0."""
        alpha, info = compute_alpha(
            E_L=12e9, E_C=0.8e9, h=2.8e-3, a=0.5, b=0.38, boundary="free"
        )
        assert alpha == 1.0

    def test_glued_boundary_greater_than_one(self):
        """Glued boundary should give alpha > 1."""
        alpha, info = compute_alpha(
            E_L=12e9, E_C=0.8e9, h=2.8e-3, a=0.5, b=0.38, boundary="glued"
        )
        assert alpha > 1.0

    def test_clamped_greater_than_glued(self):
        """Clamped boundary should give higher alpha than glued."""
        alpha_glued, _ = compute_alpha(
            E_L=12e9, E_C=0.8e9, h=2.8e-3, a=0.5, b=0.38, boundary="glued"
        )
        alpha_clamped, _ = compute_alpha(
            E_L=12e9, E_C=0.8e9, h=2.8e-3, a=0.5, b=0.38, boundary="clamped"
        )
        assert alpha_clamped > alpha_glued

    def test_braces_increase_alpha(self):
        """Adding braces should increase alpha."""
        alpha_no_brace, _ = compute_alpha(
            E_L=12e9,
            E_C=0.8e9,
            h=2.8e-3,
            a=0.5,
            b=0.38,
            boundary="glued",
            brace_count=0,
        )
        alpha_with_brace, _ = compute_alpha(
            E_L=12e9,
            E_C=0.8e9,
            h=2.8e-3,
            a=0.5,
            b=0.38,
            boundary="glued",
            brace_count=5,
        )
        assert alpha_with_brace > alpha_no_brace

    def test_alpha_in_realistic_range(self):
        """Alpha should be in typical range 1.0 - 2.0."""
        alpha, _ = compute_alpha(
            E_L=12e9,
            E_C=0.8e9,
            h=2.8e-3,
            a=0.5,
            b=0.38,
            boundary="glued",
            brace_count=5,
        )
        assert 1.0 < alpha < 2.0


class TestComputeBeta:
    """Tests for compute_beta function."""

    def test_no_air_loading_gives_beta_one(self):
        """Without air loading, beta should be close to 1."""
        beta, info = compute_beta(
            rho=420,
            h=2.8e-3,
            a=0.5,
            b=0.38,
            include_air_loading=False,
            brace_mass_total=0.0,
        )
        assert beta == 1.0

    def test_air_loading_increases_beta(self):
        """Air loading should increase beta > 1."""
        beta, info = compute_beta(
            rho=420,
            h=2.8e-3,
            a=0.5,
            b=0.38,
            include_air_loading=True,
            cavity_depth=0.10,
        )
        assert beta > 1.0

    def test_braces_increase_beta(self):
        """Adding brace mass should increase beta."""
        beta_no_brace, _ = compute_beta(
            rho=420,
            h=2.8e-3,
            a=0.5,
            b=0.38,
            include_air_loading=True,
            cavity_depth=0.10,
            brace_mass_total=0.0,
        )
        beta_with_brace, _ = compute_beta(
            rho=420,
            h=2.8e-3,
            a=0.5,
            b=0.38,
            include_air_loading=True,
            cavity_depth=0.10,
            brace_mass_total=0.020,  # 20g of braces
        )
        assert beta_with_brace > beta_no_brace

    def test_beta_in_realistic_range(self):
        """Beta should be in typical range 1.3 - 2.0 with air loading."""
        beta, _ = compute_beta(
            rho=420,
            h=2.8e-3,
            a=0.5,
            b=0.38,
            include_air_loading=True,
            cavity_depth=0.10,
        )
        assert 1.2 < beta < 2.5


class TestComputeGamma:
    """Tests for compute_gamma function."""

    def test_gamma_from_alpha_beta(self):
        """Gamma should equal sqrt(alpha/beta)."""
        alpha = 1.3
        beta = 1.6
        gamma = compute_gamma(alpha, beta)
        expected = math.sqrt(alpha / beta)
        assert abs(gamma - expected) < 1e-10

    def test_gamma_less_than_one_typical(self):
        """For typical guitar, gamma < 1 (frequency drops)."""
        # Typical values: alpha ~ 1.25, beta ~ 1.6
        gamma = compute_gamma(1.25, 1.6)
        assert gamma < 1.0

    def test_gamma_raises_for_zero_beta(self):
        """Should raise error for beta <= 0."""
        with pytest.raises(ValueError):
            compute_gamma(1.2, 0.0)


class TestAirVirtualMass:
    """Tests for air_virtual_mass function."""

    def test_returns_positive_mass(self):
        """Virtual mass must be positive."""
        m_air = air_virtual_mass(a=0.5, b=0.38)
        assert m_air > 0

    def test_larger_plate_more_mass(self):
        """Larger plate should have more air loading."""
        m_small = air_virtual_mass(a=0.3, b=0.25)
        m_large = air_virtual_mass(a=0.5, b=0.40)
        assert m_large > m_small


class TestBraceStiffnessAndMass:
    """Tests for brace_stiffness and brace_mass functions."""

    def test_brace_stiffness_positive(self):
        """Brace stiffness must be positive."""
        k = brace_stiffness(E_brace=12e9, h_brace=0.012, w_brace=0.006, L_brace=0.40)
        assert k > 0

    def test_more_braces_more_stiffness(self):
        """More braces should give more stiffness."""
        k1 = brace_stiffness(
            E_brace=12e9, h_brace=0.012, w_brace=0.006, L_brace=0.40, n_braces=1
        )
        k3 = brace_stiffness(
            E_brace=12e9, h_brace=0.012, w_brace=0.006, L_brace=0.40, n_braces=3
        )
        assert k3 == 3 * k1

    def test_brace_mass_positive(self):
        """Brace mass must be positive."""
        m = brace_mass(rho_brace=500, h_brace=0.012, w_brace=0.006, L_brace=0.40)
        assert m > 0


class TestAnalyzeAlphaBeta:
    """Tests for analyze_alpha_beta high-level function."""

    def test_returns_result_object(self):
        """Should return AlphaBetaResult dataclass."""
        result = analyze_alpha_beta(
            E_L=12e9,
            E_C=0.8e9,
            rho=420,
            h=2.8e-3,
            a=0.5,
            b=0.38,
            f_free_Hz=150.0,
        )
        assert isinstance(result, AlphaBetaResult)

    def test_predicts_lower_box_frequency(self):
        """Box frequency should typically be lower than free."""
        result = analyze_alpha_beta(
            E_L=12e9,
            E_C=0.8e9,
            rho=420,
            h=2.8e-3,
            a=0.5,
            b=0.38,
            f_free_Hz=150.0,
            boundary="glued",
            cavity_depth=0.10,
        )
        assert result.f_box_Hz < result.f_free_Hz

    def test_to_dict_works(self):
        """Result should be serializable to dict."""
        result = analyze_alpha_beta(
            E_L=12e9,
            E_C=0.8e9,
            rho=420,
            h=2.8e-3,
            a=0.5,
            b=0.38,
            f_free_Hz=150.0,
        )
        d = result.to_dict()
        assert "alpha" in d
        assert "beta" in d
        assert "gamma" in d


class TestFormatAlphaBetaReport:
    """Tests for format_alpha_beta_report function."""

    def test_returns_string(self):
        """Should return formatted string."""
        result = analyze_alpha_beta(
            E_L=12e9,
            E_C=0.8e9,
            rho=420,
            h=2.8e-3,
            a=0.5,
            b=0.38,
            f_free_Hz=150.0,
        )
        report = format_alpha_beta_report(result)
        assert isinstance(report, str)
        assert "Alpha/Beta" in report

    def test_includes_key_values(self):
        """Report should include alpha, beta, gamma."""
        result = analyze_alpha_beta(
            E_L=12e9,
            E_C=0.8e9,
            rho=420,
            h=2.8e-3,
            a=0.5,
            b=0.38,
            f_free_Hz=150.0,
        )
        report = format_alpha_beta_report(result)
        assert "alpha" in report.lower()
        assert "beta" in report.lower()
        assert "gamma" in report.lower()
