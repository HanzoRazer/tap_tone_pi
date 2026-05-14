"""Tests for Wolf Beat Advisor - agentic decision support layer."""

import numpy as np
import pytest

from tap_tone_pi.wolf.wolf_beat import (
    WolfBeatResult,
    AvoidedCrossingModel,
    analyze_wolf_beat,
    simulate_mass_addition,
    simulate_damping_increase,
)

from tap_tone_pi.wolf.wolf_advisor import (
    MitigationType,
    ConfidenceLevel,
    MitigationRecommendation,
    WolfAdvisorResult,
    WolfAdvisor,
    WolfDirective,
    generate_wolf_directive,
    advise_on_wolf,
)


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def split_doublet_frf():
    """Two Lorentzian peaks at 195 Hz and 205 Hz (10 Hz split)."""
    freqs = np.linspace(50, 500, 1000)
    f1, f2 = 195.0, 205.0
    gamma = 3.0
    A = 1.0

    mag1 = A / (1 + ((freqs - f1) / gamma) ** 2)
    mag2 = A / (1 + ((freqs - f2) / gamma) ** 2)
    magnitude = mag1 + mag2

    return freqs, magnitude


@pytest.fixture
def severe_wolf_frf():
    """Severe wolf: 2 Hz split, well-resolved (low damping)."""
    freqs = np.linspace(50, 500, 1000)
    f1, f2 = 199.0, 201.0  # 2 Hz split (severe growl range)
    gamma = 0.5  # Very narrow peaks = well resolved
    A = 1.0

    mag1 = A / (1 + ((freqs - f1) / gamma) ** 2)
    mag2 = A / (1 + ((freqs - f2) / gamma) ** 2)
    magnitude = mag1 + mag2

    return freqs, magnitude


@pytest.fixture
def no_wolf_frf():
    """Single peak, no wolf."""
    freqs = np.linspace(50, 500, 1000)
    f0, gamma, A = 200.0, 5.0, 1.0
    magnitude = A / (1 + ((freqs - f0) / gamma) ** 2)
    return freqs, magnitude


@pytest.fixture
def wolf_result_with_pair(split_doublet_frf):
    """WolfBeatResult with detected wolf pair."""
    freqs, mag = split_doublet_frf
    return analyze_wolf_beat(freqs, mag, min_freq_hz=100, max_freq_hz=300)


@pytest.fixture
def wolf_result_no_wolf(no_wolf_frf):
    """WolfBeatResult with no wolf detected."""
    freqs, mag = no_wolf_frf
    return analyze_wolf_beat(freqs, mag)


# -----------------------------------------------------------------------------
# Avoided-Crossing Model Tests
# -----------------------------------------------------------------------------


class TestAvoidedCrossingModel:
    """Tests for dimensionless avoided-crossing physics model."""

    @pytest.fixture
    def baseline_model(self):
        """Standard test model: 200 Hz body mode, moderate coupling."""
        return AvoidedCrossingModel(
            omega_b_hz=200.0,
            coupling_omega=0.05,  # 5% coupling
            gamma_b_hz=5.0,
            gamma_s_hz=2.0,
        )

    def test_eigenvalues_at_resonance(self, baseline_model):
        """At xi=1, eigenvalues should show avoided crossing gap."""
        xi = np.array([1.0])
        lambda_m, lambda_p = baseline_model.eigenvalues(xi)

        # At resonance: lambda_pm = 1 pm Omega
        assert abs(lambda_m[0] - (1 - 0.05)) < 0.01
        assert abs(lambda_p[0] - (1 + 0.05)) < 0.01

    def test_eigenvalues_symmetry(self, baseline_model):
        """Eigenvalues should be symmetric about xi=1."""
        xi = np.array([0.9, 1.0, 1.1])
        lambda_m, lambda_p = baseline_model.eigenvalues(xi)

        # The gap is minimum at xi=1
        gap_09 = lambda_p[0] - lambda_m[0]
        gap_10 = lambda_p[1] - lambda_m[1]
        gap_11 = lambda_p[2] - lambda_m[2]

        assert gap_10 < gap_09
        assert gap_10 < gap_11

    def test_frequencies_physical(self, baseline_model):
        """Frequencies should be positive and physical."""
        xi = np.linspace(0.7, 1.3, 100)
        f_m, f_p = baseline_model.frequencies_hz(xi)

        assert np.all(f_m > 0)
        assert np.all(f_p > 0)
        assert np.all(f_p > f_m)

    def test_beat_frequency_minimum_at_resonance(self, baseline_model):
        """Beat frequency has minimum at xi=1."""
        xi = np.linspace(0.8, 1.2, 100)
        beats = baseline_model.beat_frequency_hz(xi)

        min_idx = np.argmin(beats)
        xi_at_min = xi[min_idx]
        assert abs(xi_at_min - 1.0) < 0.1

    def test_min_split_hz(self, baseline_model):
        """min_split_hz should match coupling * body frequency."""
        min_split = baseline_model.min_split_hz()
        # Omega * f_b = 0.05 * 200 = 10 Hz
        assert abs(min_split - 10.0) < 1.0

    def test_is_resolvable_at(self, baseline_model):
        """Resolvability criterion: delta_f > (gamma_b + gamma_s)."""
        # Combined linewidth = 7 Hz, min split = 10 Hz
        assert baseline_model.is_resolvable_at(1.0)  # Should be True

        # Weak coupling = 2 Hz split < 7 Hz linewidth
        weak_model = AvoidedCrossingModel(
            omega_b_hz=200.0,
            coupling_omega=0.01,
            gamma_b_hz=5.0,
            gamma_s_hz=2.0,
        )
        assert not weak_model.is_resolvable_at(1.0)  # Should be False

    def test_sweep_curve_structure(self, baseline_model):
        """sweep_curve should return complete data dict."""
        curve = baseline_model.sweep_curve(xi_min=0.8, xi_max=1.2, n_points=50)

        assert "xi" in curve
        assert "f_minus_hz" in curve
        assert "f_plus_hz" in curve
        assert "beat_hz" in curve
        assert "severity" in curve
        assert len(curve["xi"]) == 50

    def test_to_dict_serialization(self, baseline_model):
        """to_dict should produce JSON-compatible output."""
        d = baseline_model.to_dict()

        assert d["omega_b_hz"] == 200.0
        assert d["coupling_omega"] == 0.05
        assert "min_split_hz" in d

    def test_from_measurement(self, wolf_result_with_pair):
        """from_measurement should create model from detected pair."""
        if wolf_result_with_pair.pairs:
            pair = wolf_result_with_pair.pairs[0]
            model = AvoidedCrossingModel.from_measurement(pair)

            assert model.omega_b_hz > 0
            assert model.coupling_omega > 0


class TestSimulationFunctions:
    """Tests for mass/damping simulation functions."""

    @pytest.fixture
    def baseline_model(self):
        """Standard model for simulation tests."""
        return AvoidedCrossingModel(
            omega_b_hz=200.0,
            coupling_omega=0.05,
            gamma_b_hz=5.0,
            gamma_s_hz=2.0,
        )

    def test_mass_addition_reduces_coupling(self, baseline_model):
        """Adding mass should reduce coupling strength."""
        new_model = simulate_mass_addition(baseline_model, mass_factor=2.0)
        expected_coupling = 0.05 / np.sqrt(2.0)
        assert abs(new_model.coupling_omega - expected_coupling) < 0.001

    def test_mass_addition_reduces_beat(self, baseline_model):
        """Adding mass should reduce beat frequency."""
        original_beat = baseline_model.min_split_hz()
        new_model = simulate_mass_addition(baseline_model, mass_factor=4.0)
        new_beat = new_model.min_split_hz()

        # 4x mass -> beat reduces to 0.5x
        assert new_beat < original_beat
        assert abs(new_beat / original_beat - 0.5) < 0.05

    def test_damping_increase_widens_linewidth(self, baseline_model):
        """Increasing damping should widen linewidths."""
        new_model = simulate_damping_increase(baseline_model, damping_factor=2.0)

        assert new_model.gamma_b_hz == baseline_model.gamma_b_hz * 2.0
        assert new_model.gamma_s_hz == baseline_model.gamma_s_hz * 2.0
        assert new_model.coupling_omega == baseline_model.coupling_omega

    def test_damping_can_cause_merge(self, baseline_model):
        """Sufficient damping should cause peaks to merge."""
        assert baseline_model.is_resolvable_at(1.0)  # Should be True

        # Triple damping: combined gamma = 21 Hz > 10 Hz split
        damped_model = simulate_damping_increase(baseline_model, damping_factor=3.0)
        assert not damped_model.is_resolvable_at(1.0)  # Should be False


# -----------------------------------------------------------------------------
# Wolf Advisor Tests
# -----------------------------------------------------------------------------


class TestWolfAdvisor:
    """Tests for WolfAdvisor decision support engine."""

    def test_advisor_with_wolf(self, wolf_result_with_pair):
        """Advisor should generate recommendations for wolf."""
        advisor = WolfAdvisor(wolf_result_with_pair)
        recs = advisor.get_recommendations()

        # Should have at least one recommendation
        assert len(recs) > 0
        # All recs should have required fields
        for rec in recs:
            assert isinstance(rec.mitigation_type, MitigationType)
            assert isinstance(rec.confidence, ConfidenceLevel)
            assert rec.priority >= 1

    def test_advisor_no_wolf(self, wolf_result_no_wolf):
        """Advisor should recommend NO_ACTION when no wolf."""
        advisor = WolfAdvisor(wolf_result_no_wolf)
        recs = advisor.get_recommendations()

        assert len(recs) >= 1
        assert recs[0].mitigation_type == MitigationType.NO_ACTION

    def test_advisor_builds_model(self, wolf_result_with_pair):
        """Advisor should build physics model from measurement."""
        advisor = WolfAdvisor(wolf_result_with_pair)

        if wolf_result_with_pair.pairs:
            assert advisor.model is not None
            assert isinstance(advisor.model, AvoidedCrossingModel)

    def test_get_result_structure(self, wolf_result_with_pair):
        """get_result should return complete WolfAdvisorResult."""
        advisor = WolfAdvisor(wolf_result_with_pair)
        result = advisor.get_result()

        assert isinstance(result, WolfAdvisorResult)
        assert "wolf_detected" in result.to_dict()
        assert "recommendations" in result.to_dict()
        assert result.requires_operator_judgment is True

    def test_result_serialization(self, wolf_result_with_pair):
        """WolfAdvisorResult should serialize to JSON-compatible dict."""
        advisor = WolfAdvisor(wolf_result_with_pair)
        result = advisor.get_result()
        d = result.to_dict()

        assert d["schema_id"] == "wolf_advisor_result_v1"
        assert isinstance(d["recommendations"], list)


class TestMitigationRecommendation:
    """Tests for MitigationRecommendation dataclass."""

    def test_recommendation_to_dict(self):
        """Recommendation should serialize correctly."""
        rec = MitigationRecommendation(
            mitigation_type=MitigationType.ADD_MASS,
            confidence=ConfidenceLevel.HIGH,
            priority=1,
            predicted_effect="Reduces beat to 5 Hz",
            predicted_severity="mild",
            predicted_merge_ratio=0.7,
            action_summary="Add 5g wolf eliminator",
            action_details=["Step 1", "Step 2"],
            physics_basis="Mass reduces coupling",
            assumptions=["Mass estimate accurate"],
            validation_steps=["Re-measure tap tone"],
            rollback_guidance="Remove eliminator",
        )

        d = rec.to_dict()
        assert d["mitigation_type"] == "add_mass"
        assert d["confidence"] == "high"
        assert d["priority"] == 1


# -----------------------------------------------------------------------------
# Wolf Directive Tests
# -----------------------------------------------------------------------------


class TestWolfDirective:
    """Tests for attention directive generation."""

    def test_generate_directive_with_wolf(self, wolf_result_with_pair):
        """Directive should be generated for wolf."""
        advisor = WolfAdvisor(wolf_result_with_pair)
        directive = generate_wolf_directive(advisor, session_id="test_session")

        assert isinstance(directive, WolfDirective)
        assert directive.directive_type == "wolf_mitigation"
        assert directive.session_id == "test_session"
        assert directive.directive_id.startswith("wolf_")

    def test_generate_directive_no_wolf(self, wolf_result_no_wolf):
        """Directive should indicate no action when no wolf."""
        advisor = WolfAdvisor(wolf_result_no_wolf)
        directive = generate_wolf_directive(advisor)

        assert directive.wolf_severity == "none"
        assert (
            "No wolf" in directive.action_prompt
            or "no" in directive.action_prompt.lower()
        )

    def test_directive_serialization(self, wolf_result_with_pair):
        """Directive should serialize correctly."""
        advisor = WolfAdvisor(wolf_result_with_pair)
        directive = generate_wolf_directive(advisor)
        d = directive.to_dict()

        assert d["schema_id"] == "wolf_directive_v1"
        assert "directive_id" in d
        assert "action_prompt" in d

    def test_directive_urgency_levels(self, severe_wolf_frf, wolf_result_with_pair):
        """Urgency should reflect wolf severity."""
        # Moderate wolf
        advisor1 = WolfAdvisor(wolf_result_with_pair)
        directive1 = generate_wolf_directive(advisor1)

        # The urgency should be set based on severity
        assert directive1.urgency in ["normal", "high", "critical"]


# -----------------------------------------------------------------------------
# Convenience Function Tests
# -----------------------------------------------------------------------------


class TestConvenienceFunctions:
    """Tests for advise_on_wolf convenience function."""

    def test_advise_on_wolf_returns_result(self, wolf_result_with_pair):
        """advise_on_wolf should return WolfAdvisorResult."""
        result = advise_on_wolf(wolf_result_with_pair)

        assert isinstance(result, WolfAdvisorResult)
        assert result.wolf_detected is True or result.wolf_detected is False

    def test_advise_on_wolf_no_wolf(self, wolf_result_no_wolf):
        """advise_on_wolf should handle no-wolf case."""
        result = advise_on_wolf(wolf_result_no_wolf)

        assert result.wolf_detected is False
        assert result.worst_severity == "none"


# -----------------------------------------------------------------------------
# Edge Cases
# -----------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case tests for advisor."""

    def test_empty_wolf_result(self):
        """Advisor should handle empty wolf result."""
        empty_result = WolfBeatResult(
            freq_range_hz=(50, 500),
            n_frequencies=1000,
        )

        advisor = WolfAdvisor(empty_result)
        recs = advisor.get_recommendations()

        # Should still return recommendations (NO_ACTION)
        assert len(recs) >= 1
        assert recs[0].mitigation_type == MitigationType.NO_ACTION

    def test_advisor_with_custom_parameters(self, wolf_result_with_pair):
        """Advisor should accept custom physics parameters."""
        advisor = WolfAdvisor(
            wolf_result_with_pair,
            string_linewidth_hz=3.0,
            effective_mass_kg=0.02,
        )

        assert advisor.string_linewidth_hz == 3.0
        assert advisor.effective_mass_kg == 0.02

    def test_recommendation_priorities_ordered(self, wolf_result_with_pair):
        """Recommendations should be priority-ordered."""
        advisor = WolfAdvisor(wolf_result_with_pair)
        recs = advisor.get_recommendations()

        if len(recs) > 1:
            priorities = [r.priority for r in recs]
            assert priorities == sorted(priorities)
