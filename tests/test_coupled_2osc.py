"""Tests for 2-oscillator coupled model (rigid back)."""

from tap_tone_pi.design import (
    coupled_2osc_eigenfrequencies,
    back_activity_ratio,
    minimum_back_thickness_for_rigid,
    analyze_coupled_2osc,
    format_2osc_report,
    Coupled2OscResult,
    get_body_calibration,
)


class TestCoupled2OscEigenfrequencies:
    """Tests for coupled_2osc_eigenfrequencies function."""

    def test_returns_two_frequencies(self):
        """Should return exactly two eigenfrequencies."""
        freqs, modes, info = coupled_2osc_eigenfrequencies(
            E_L_top=12.0e9,
            E_C_top=0.8e9,
            rho_top=420,
            h_top=2.8e-3,
            a_top=0.50,
            b_top=0.38,
            A_eff_top=0.12,
            eta_top=1.0,
            gamma_top=0.85,
            volume=0.020,
            hole_area=0.0081,
            L_eff=0.012,
        )
        assert len(freqs) == 2

    def test_frequencies_are_sorted_ascending(self):
        """Lower frequency should be first (air-dominated)."""
        freqs, modes, info = coupled_2osc_eigenfrequencies(
            E_L_top=12.0e9,
            E_C_top=0.8e9,
            rho_top=420,
            h_top=2.8e-3,
            a_top=0.50,
            b_top=0.38,
            A_eff_top=0.12,
            eta_top=1.0,
            gamma_top=0.85,
            volume=0.020,
            hole_area=0.0081,
            L_eff=0.012,
        )
        assert freqs[0] < freqs[1]

    def test_frequencies_are_positive(self):
        """All frequencies must be positive."""
        freqs, modes, info = coupled_2osc_eigenfrequencies(
            E_L_top=12.0e9,
            E_C_top=0.8e9,
            rho_top=420,
            h_top=2.8e-3,
            a_top=0.50,
            b_top=0.38,
            A_eff_top=0.12,
            eta_top=1.0,
            gamma_top=0.85,
            volume=0.020,
            hole_area=0.0081,
            L_eff=0.012,
        )
        assert all(f > 0 for f in freqs)

    def test_info_dict_contains_required_keys(self):
        """Info dict should contain all diagnostic values."""
        freqs, modes, info = coupled_2osc_eigenfrequencies(
            E_L_top=12.0e9,
            E_C_top=0.8e9,
            rho_top=420,
            h_top=2.8e-3,
            a_top=0.50,
            b_top=0.38,
            A_eff_top=0.12,
            eta_top=1.0,
            gamma_top=0.85,
            volume=0.020,
            hole_area=0.0081,
            L_eff=0.012,
        )
        required_keys = [
            "f_top_free_Hz",
            "f_top_box_Hz",
            "f_helmholtz_Hz",
            "m_top_kg",
            "k_top_N_m",
            "C_a_m3_Pa",
            "M_h_kg_m4",
            "f_coupling_Hz",
        ]
        for key in required_keys:
            assert key in info, f"Missing key: {key}"

    def test_lower_mode_near_helmholtz(self):
        """Lower mode should be influenced by Helmholtz frequency."""
        freqs, modes, info = coupled_2osc_eigenfrequencies(
            E_L_top=12.0e9,
            E_C_top=0.8e9,
            rho_top=420,
            h_top=2.8e-3,
            a_top=0.50,
            b_top=0.38,
            A_eff_top=0.12,
            eta_top=1.0,
            gamma_top=0.85,
            volume=0.020,
            hole_area=0.0081,
            L_eff=0.012,
        )
        # Lower mode should be below Helmholtz (coupling lowers it)
        assert freqs[0] < info["f_helmholtz_Hz"]

    def test_thicker_top_raises_uncoupled_frequency(self):
        """Thicker top should raise the uncoupled top frequency.

        Note: In coupled systems, thicker plate adds both mass (lowers f)
        and stiffness (raises f). The uncoupled top frequency (f_top_box)
        should increase with thickness (stiffness wins for plates).
        """
        _, _, info_thin = coupled_2osc_eigenfrequencies(
            E_L_top=12.0e9,
            E_C_top=0.8e9,
            rho_top=420,
            h_top=2.5e-3,
            a_top=0.50,
            b_top=0.38,
            A_eff_top=0.12,
            eta_top=1.0,
            gamma_top=0.85,
            volume=0.020,
            hole_area=0.0081,
            L_eff=0.012,
        )
        _, _, info_thick = coupled_2osc_eigenfrequencies(
            E_L_top=12.0e9,
            E_C_top=0.8e9,
            rho_top=420,
            h_top=3.5e-3,
            a_top=0.50,
            b_top=0.38,
            A_eff_top=0.12,
            eta_top=1.0,
            gamma_top=0.85,
            volume=0.020,
            hole_area=0.0081,
            L_eff=0.012,
        )
        # The uncoupled top frequency should definitely increase
        assert info_thick["f_top_box_Hz"] > info_thin["f_top_box_Hz"]

    def test_larger_volume_lowers_helmholtz(self):
        """Larger cavity volume should lower air mode frequency."""
        freqs_small, _, _ = coupled_2osc_eigenfrequencies(
            E_L_top=12.0e9,
            E_C_top=0.8e9,
            rho_top=420,
            h_top=2.8e-3,
            a_top=0.50,
            b_top=0.38,
            A_eff_top=0.12,
            eta_top=1.0,
            gamma_top=0.85,
            volume=0.015,
            hole_area=0.0081,
            L_eff=0.012,
        )
        freqs_large, _, _ = coupled_2osc_eigenfrequencies(
            E_L_top=12.0e9,
            E_C_top=0.8e9,
            rho_top=420,
            h_top=2.8e-3,
            a_top=0.50,
            b_top=0.38,
            A_eff_top=0.12,
            eta_top=1.0,
            gamma_top=0.85,
            volume=0.025,
            hole_area=0.0081,
            L_eff=0.012,
        )
        assert freqs_large[0] < freqs_small[0]


class TestBackActivityRatio:
    """Tests for back_activity_ratio function."""

    def test_high_ratio_recommends_2osc(self):
        """High ratio (>1.5) should recommend 2-oscillator model."""
        # Very stiff/thick back
        ratio, rec = back_activity_ratio(
            E_L_back=15.0e9,
            E_C_back=1.0e9,
            rho_back=500,
            h_back=10.0e-3,  # 10mm - very thick
            a_back=0.55,
            b_back=0.24,
            f_coupled_max=200.0,
        )
        assert ratio > 1.5
        assert rec == "2-oscillator"

    def test_low_ratio_recommends_3osc(self):
        """Low ratio (<1.5) should recommend 3-oscillator model."""
        # Normal guitar back
        ratio, rec = back_activity_ratio(
            E_L_back=10.0e9,
            E_C_back=0.65e9,
            rho_back=540,
            h_back=2.6e-3,  # 2.6mm - typical
            a_back=0.559,
            b_back=0.241,
            f_coupled_max=200.0,
        )
        assert ratio < 1.5
        assert rec in ("3-oscillator", "strongly-coupled")

    def test_very_low_ratio_recommends_strongly_coupled(self):
        """Very low ratio (<1.0) should recommend strongly-coupled."""
        ratio, rec = back_activity_ratio(
            E_L_back=8.0e9,
            E_C_back=0.5e9,
            rho_back=600,
            h_back=2.0e-3,  # thin softwood
            a_back=0.559,
            b_back=0.241,
            f_coupled_max=150.0,
        )
        assert ratio < 1.0
        assert rec == "strongly-coupled"


class TestMinimumBackThicknessForRigid:
    """Tests for minimum_back_thickness_for_rigid function."""

    def test_returns_positive_thickness(self):
        """Should return positive thickness value."""
        h_min, info = minimum_back_thickness_for_rigid(
            E_L_back=10.0e9,
            E_C_back=0.65e9,
            rho_back=540,
            a_back=0.559,
            b_back=0.241,
            f_coupled_max=200.0,
        )
        assert h_min > 0

    def test_higher_coupled_freq_needs_thicker_back(self):
        """Higher coupled mode requires thicker back to be rigid."""
        h_low, _ = minimum_back_thickness_for_rigid(
            E_L_back=10.0e9,
            E_C_back=0.65e9,
            rho_back=540,
            a_back=0.559,
            b_back=0.241,
            f_coupled_max=150.0,
        )
        h_high, _ = minimum_back_thickness_for_rigid(
            E_L_back=10.0e9,
            E_C_back=0.65e9,
            rho_back=540,
            a_back=0.559,
            b_back=0.241,
            f_coupled_max=250.0,
        )
        assert h_high > h_low

    def test_safety_factor_increases_thickness(self):
        """Higher safety factor should require thicker back."""
        h_1_0, _ = minimum_back_thickness_for_rigid(
            E_L_back=10.0e9,
            E_C_back=0.65e9,
            rho_back=540,
            a_back=0.559,
            b_back=0.241,
            f_coupled_max=200.0,
            safety_factor=1.0,
        )
        h_1_5, _ = minimum_back_thickness_for_rigid(
            E_L_back=10.0e9,
            E_C_back=0.65e9,
            rho_back=540,
            a_back=0.559,
            b_back=0.241,
            f_coupled_max=200.0,
            safety_factor=1.5,
        )
        assert h_1_5 > h_1_0


class TestAnalyzeCoupled2Osc:
    """Tests for analyze_coupled_2osc high-level function."""

    def test_returns_coupled_2osc_result(self):
        """Should return Coupled2OscResult dataclass."""
        body = get_body_calibration("jumbo")
        result = analyze_coupled_2osc(
            body=body,
            top_E_L_GPa=12.0,
            top_E_C_GPa=0.8,
            top_rho=420,
            top_h_mm=2.8,
        )
        assert isinstance(result, Coupled2OscResult)

    def test_includes_back_assessment_when_provided(self):
        """Should assess back activity when back params given."""
        body = get_body_calibration("jumbo")
        result = analyze_coupled_2osc(
            body=body,
            top_E_L_GPa=12.0,
            top_E_C_GPa=0.8,
            top_rho=420,
            top_h_mm=2.8,
            back_E_L_GPa=10.2,
            back_E_C_GPa=0.65,
            back_rho=540,
            back_h_mm=2.6,
        )
        assert result.back_activity_ratio is not None
        assert result.back_model_recommendation is not None

    def test_generates_recommendation(self):
        """Should generate a non-empty recommendation."""
        body = get_body_calibration("jumbo")
        result = analyze_coupled_2osc(
            body=body,
            top_E_L_GPa=12.0,
            top_E_C_GPa=0.8,
            top_rho=420,
            top_h_mm=2.8,
        )
        assert len(result.recommendation) > 0


class TestFormat2OscReport:
    """Tests for format_2osc_report function."""

    def test_returns_string(self):
        """Should return formatted string report."""
        body = get_body_calibration("jumbo")
        result = analyze_coupled_2osc(
            body=body,
            top_E_L_GPa=12.0,
            top_E_C_GPa=0.8,
            top_rho=420,
            top_h_mm=2.8,
        )
        report = format_2osc_report(result)
        assert isinstance(report, str)
        assert "2-Oscillator" in report

    def test_includes_frequencies(self):
        """Report should include eigenfrequencies."""
        body = get_body_calibration("jumbo")
        result = analyze_coupled_2osc(
            body=body,
            top_E_L_GPa=12.0,
            top_E_C_GPa=0.8,
            top_rho=420,
            top_h_mm=2.8,
        )
        report = format_2osc_report(result)
        assert "f1" in report
        assert "f2" in report
        assert "Hz" in report
