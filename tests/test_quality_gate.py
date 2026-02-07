"""Tests for quality gate enforcement.

Verifies that quality rules are correctly applied to AnalysisResult
and produce the expected verdicts.
"""
from __future__ import annotations

import numpy as np
import pytest

from tap_tone_pi.core.analysis import AnalysisResult, Peak
from tap_tone_pi.core.quality_gate import (
    check_quality,
    format_verdict_summary,
    can_proceed,
)
from tap_tone_pi.core.quality_policy import (
    Verdict,
    Severity,
    QualityThresholds,
    DEFAULT_THRESHOLDS,
)


# =============================================================================
# Fixtures
# =============================================================================

def _make_analysis(
    *,
    dominant_hz: float | None = 440.0,
    peaks: list[Peak] | None = None,
    clipped: bool = False,
    rms: float = 0.05,
    confidence: float = 0.8,
) -> AnalysisResult:
    """Create a fake AnalysisResult for testing."""
    if peaks is None:
        peaks = [
            Peak(freq_hz=440.0, magnitude=1.0),
            Peak(freq_hz=880.0, magnitude=0.5),
            Peak(freq_hz=1320.0, magnitude=0.25),
        ]
    return AnalysisResult(
        dominant_hz=dominant_hz,
        peaks=peaks,
        clipped=clipped,
        rms=rms,
        confidence=confidence,
        spectrum_freq_hz=np.array([100.0, 200.0, 300.0]),
        spectrum_mag=np.array([0.1, 0.2, 0.3]),
    )


def _make_audio(peak_level: float = 0.5) -> np.ndarray:
    """Create fake audio array with given peak level."""
    return np.array([0.0, peak_level, -peak_level * 0.5, 0.0], dtype=np.float32)


# =============================================================================
# PASS Cases
# =============================================================================

class TestQualityGatePass:
    """Test cases that should produce PASS verdict."""

    def test_good_measurement_passes(self):
        """Clean measurement with good values passes."""
        analysis = _make_analysis()
        verdict = check_quality(analysis, sample_rate=48000)

        assert verdict.verdict == Verdict.PASS
        assert verdict.passed is True
        assert verdict.failed is False
        assert len(verdict.triggered_rules) == 0

    def test_passes_with_all_valid_sample_rates(self):
        """All valid sample rates pass Q005."""
        analysis = _make_analysis()

        for sr in [44100, 48000, 96000]:
            verdict = check_quality(analysis, sample_rate=sr)
            assert verdict.verdict == Verdict.PASS
            assert not any(r.rule.rule_id == "Q005" for r in verdict.triggered_rules)


# =============================================================================
# HARD FAIL Cases (Q001-Q005)
# =============================================================================

class TestHardFailRules:
    """Test hard rules that MUST produce FAIL verdict."""

    def test_q001_clipping_is_hard_fail(self):
        """Q001: Clipped audio must fail."""
        analysis = _make_analysis(clipped=True)
        verdict = check_quality(analysis, sample_rate=48000)

        assert verdict.verdict == Verdict.FAIL
        assert verdict.failed is True
        assert any(r.rule.rule_id == "Q001" for r in verdict.triggered_rules)
        assert len(verdict.errors) >= 1

    def test_q002_silent_is_hard_fail(self):
        """Q002: Silent signal (RMS < 0.001) must fail."""
        analysis = _make_analysis(rms=0.0005)
        verdict = check_quality(analysis, sample_rate=48000)

        assert verdict.verdict == Verdict.FAIL
        assert any(r.rule.rule_id == "Q002" for r in verdict.triggered_rules)

    def test_q003_no_dominant_hz_is_hard_fail(self):
        """Q003: No dominant frequency must fail."""
        analysis = _make_analysis(dominant_hz=None)
        verdict = check_quality(analysis, sample_rate=48000)

        assert verdict.verdict == Verdict.FAIL
        assert any(r.rule.rule_id == "Q003" for r in verdict.triggered_rules)

    def test_q004_low_confidence_is_hard_fail(self):
        """Q004: Confidence < 0.3 must fail."""
        analysis = _make_analysis(confidence=0.2)
        verdict = check_quality(analysis, sample_rate=48000)

        assert verdict.verdict == Verdict.FAIL
        assert any(r.rule.rule_id == "Q004" for r in verdict.triggered_rules)

    def test_q005_invalid_sample_rate_is_hard_fail(self):
        """Q005: Non-standard sample rate must fail."""
        analysis = _make_analysis()
        verdict = check_quality(analysis, sample_rate=22050)

        assert verdict.verdict == Verdict.FAIL
        assert any(r.rule.rule_id == "Q005" for r in verdict.triggered_rules)

    def test_multiple_hard_fails_all_reported(self):
        """Multiple hard failures are all reported."""
        analysis = _make_analysis(
            clipped=True,
            rms=0.0001,
            dominant_hz=None,
            confidence=0.1,
        )
        verdict = check_quality(analysis, sample_rate=22050)

        assert verdict.verdict == Verdict.FAIL
        rule_ids = {r.rule.rule_id for r in verdict.triggered_rules}
        assert "Q001" in rule_ids  # clipped
        assert "Q002" in rule_ids  # silent
        assert "Q003" in rule_ids  # no peaks
        assert "Q004" in rule_ids  # low confidence
        assert "Q005" in rule_ids  # invalid sample rate


# =============================================================================
# SOFT WARN Cases (Q010-Q013)
# =============================================================================

class TestSoftWarnRules:
    """Test soft rules that produce WARN verdict (not FAIL)."""

    def test_q010_quiet_signal_is_warn(self):
        """Q010: Quiet signal (0.001 <= RMS < 0.01) warns."""
        analysis = _make_analysis(rms=0.005)
        verdict = check_quality(analysis, sample_rate=48000)

        assert verdict.verdict == Verdict.WARN
        assert any(r.rule.rule_id == "Q010" for r in verdict.triggered_rules)
        assert len(verdict.warnings) >= 1

    def test_q011_near_clipping_is_warn(self):
        """Q011: Peak level > 0.9 (not clipped) warns."""
        analysis = _make_analysis(clipped=False)
        audio = _make_audio(peak_level=0.95)
        verdict = check_quality(analysis, sample_rate=48000, audio=audio)

        assert verdict.verdict == Verdict.WARN
        assert any(r.rule.rule_id == "Q011" for r in verdict.triggered_rules)

    def test_q011_not_triggered_if_clipped(self):
        """Q011 is not triggered if already clipped (Q001 takes precedence)."""
        analysis = _make_analysis(clipped=True)
        audio = _make_audio(peak_level=1.0)
        verdict = check_quality(analysis, sample_rate=48000, audio=audio)

        # Should have Q001 (FAIL), not Q011
        assert verdict.verdict == Verdict.FAIL
        assert any(r.rule.rule_id == "Q001" for r in verdict.triggered_rules)
        assert not any(r.rule.rule_id == "Q011" for r in verdict.triggered_rules)

    def test_q012_marginal_confidence_is_warn(self):
        """Q012: Marginal confidence (0.3 <= conf < 0.5) warns."""
        analysis = _make_analysis(confidence=0.4)
        verdict = check_quality(analysis, sample_rate=48000)

        assert verdict.verdict == Verdict.WARN
        assert any(r.rule.rule_id == "Q012" for r in verdict.triggered_rules)

    def test_q012_not_triggered_below_fail_threshold(self):
        """Q012 not triggered if confidence is below fail threshold (Q004 handles it)."""
        analysis = _make_analysis(confidence=0.2)
        verdict = check_quality(analysis, sample_rate=48000)

        # Should have Q004 (FAIL), not Q012
        assert verdict.verdict == Verdict.FAIL
        assert any(r.rule.rule_id == "Q004" for r in verdict.triggered_rules)
        assert not any(r.rule.rule_id == "Q012" for r in verdict.triggered_rules)

    def test_q013_few_peaks_is_warn(self):
        """Q013: Fewer than 3 peaks warns."""
        analysis = _make_analysis(
            peaks=[Peak(freq_hz=440.0, magnitude=1.0)],  # Only 1 peak
        )
        verdict = check_quality(analysis, sample_rate=48000)

        assert verdict.verdict == Verdict.WARN
        assert any(r.rule.rule_id == "Q013" for r in verdict.triggered_rules)

    def test_q013_not_triggered_with_no_peaks(self):
        """Q013 requires at least 1 peak (0 peaks handled by Q003)."""
        analysis = _make_analysis(peaks=[], dominant_hz=None)
        verdict = check_quality(analysis, sample_rate=48000)

        # Q003 should trigger (no dominant), Q013 should not
        assert any(r.rule.rule_id == "Q003" for r in verdict.triggered_rules)
        assert not any(r.rule.rule_id == "Q013" for r in verdict.triggered_rules)


# =============================================================================
# Threshold Customization
# =============================================================================

class TestCustomThresholds:
    """Test that custom thresholds are respected."""

    def test_custom_rms_silent_threshold(self):
        """Custom rms_silent threshold is applied."""
        analysis = _make_analysis(rms=0.0005)
        
        # Default: should fail (rms < 0.001)
        default_verdict = check_quality(analysis, sample_rate=48000)
        assert default_verdict.verdict == Verdict.FAIL

        # Custom: lower threshold, should pass
        custom = QualityThresholds(rms_silent=0.0001)
        custom_verdict = check_quality(analysis, sample_rate=48000, thresholds=custom)
        # Still may warn (Q010) but not fail Q002
        assert not any(r.rule.rule_id == "Q002" for r in custom_verdict.triggered_rules)

    def test_custom_confidence_fail_threshold(self):
        """Custom confidence_fail threshold is applied."""
        analysis = _make_analysis(confidence=0.25)

        # Default: should fail (conf < 0.3)
        default_verdict = check_quality(analysis, sample_rate=48000)
        assert any(r.rule.rule_id == "Q004" for r in default_verdict.triggered_rules)

        # Custom: lower threshold
        custom = QualityThresholds(confidence_fail=0.2)
        custom_verdict = check_quality(analysis, sample_rate=48000, thresholds=custom)
        assert not any(r.rule.rule_id == "Q004" for r in custom_verdict.triggered_rules)

    def test_custom_valid_sample_rates(self):
        """Custom valid_sample_rates are respected."""
        analysis = _make_analysis()

        # 22050 fails by default
        default_verdict = check_quality(analysis, sample_rate=22050)
        assert any(r.rule.rule_id == "Q005" for r in default_verdict.triggered_rules)

        # Custom: allow 22050
        custom = QualityThresholds(valid_sample_rates=(22050, 44100, 48000))
        custom_verdict = check_quality(analysis, sample_rate=22050, thresholds=custom)
        assert not any(r.rule.rule_id == "Q005" for r in custom_verdict.triggered_rules)


# =============================================================================
# Verdict Helpers
# =============================================================================

class TestVerdictHelpers:
    """Test format_verdict_summary and can_proceed helpers."""

    def test_format_verdict_pass(self):
        """PASS verdict formats correctly."""
        analysis = _make_analysis()
        verdict = check_quality(analysis, sample_rate=48000)
        summary = format_verdict_summary(verdict)

        assert "[PASS]" in summary
        assert "OK" in summary

    def test_format_verdict_warn(self):
        """WARN verdict formats with warning count."""
        analysis = _make_analysis(confidence=0.4)
        verdict = check_quality(analysis, sample_rate=48000)
        summary = format_verdict_summary(verdict)

        assert "[WARN]" in summary
        assert "Q012" in summary

    def test_format_verdict_fail(self):
        """FAIL verdict formats with error count."""
        analysis = _make_analysis(clipped=True)
        verdict = check_quality(analysis, sample_rate=48000)
        summary = format_verdict_summary(verdict)

        assert "[FAIL]" in summary
        assert "Q001" in summary

    def test_can_proceed_pass(self):
        """PASS verdict can always proceed."""
        analysis = _make_analysis()
        verdict = check_quality(analysis, sample_rate=48000)

        assert can_proceed(verdict) is True
        assert can_proceed(verdict, allow_warnings=False) is True

    def test_can_proceed_warn_default(self):
        """WARN verdict can proceed by default."""
        analysis = _make_analysis(confidence=0.4)
        verdict = check_quality(analysis, sample_rate=48000)

        assert can_proceed(verdict) is True

    def test_can_proceed_warn_strict(self):
        """WARN verdict cannot proceed in strict mode."""
        analysis = _make_analysis(confidence=0.4)
        verdict = check_quality(analysis, sample_rate=48000)

        assert can_proceed(verdict, allow_warnings=False) is False

    def test_can_proceed_fail(self):
        """FAIL verdict cannot proceed."""
        analysis = _make_analysis(clipped=True)
        verdict = check_quality(analysis, sample_rate=48000)

        assert can_proceed(verdict) is False
        assert can_proceed(verdict, allow_warnings=True) is False


# =============================================================================
# QualityVerdict Serialization
# =============================================================================

class TestVerdictSerialization:
    """Test QualityVerdict.to_dict() output."""

    def test_to_dict_pass(self):
        """PASS verdict serializes correctly."""
        analysis = _make_analysis()
        verdict = check_quality(analysis, sample_rate=48000)
        d = verdict.to_dict()

        assert d["verdict"] == "pass"
        assert d["error_count"] == 0
        assert d["warning_count"] == 0
        assert "policy_version" in d

    def test_to_dict_fail(self):
        """FAIL verdict includes triggered rules."""
        analysis = _make_analysis(clipped=True)
        verdict = check_quality(analysis, sample_rate=48000)
        d = verdict.to_dict()

        assert d["verdict"] == "fail"
        assert d["error_count"] >= 1
        assert len(d["triggered_rules"]) >= 1
        assert d["triggered_rules"][0]["rule_id"] == "Q001"
        assert d["triggered_rules"][0]["severity"] == "hard"

    def test_to_dict_includes_policy_version(self):
        """Serialized verdict includes policy version."""
        analysis = _make_analysis()
        verdict = check_quality(analysis, sample_rate=48000)
        d = verdict.to_dict()

        assert "policy_version" in d
        assert d["policy_version"] == verdict.policy_version


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Edge case and boundary condition tests."""

    def test_rms_exactly_at_silent_boundary(self):
        """RMS exactly at 0.001 should not trigger Q002."""
        analysis = _make_analysis(rms=0.001)
        verdict = check_quality(analysis, sample_rate=48000)

        # 0.001 is NOT < 0.001, so Q002 should not trigger
        assert not any(r.rule.rule_id == "Q002" for r in verdict.triggered_rules)

    def test_confidence_exactly_at_fail_boundary(self):
        """Confidence exactly at 0.3 should not trigger Q004."""
        analysis = _make_analysis(confidence=0.3)
        verdict = check_quality(analysis, sample_rate=48000)

        # 0.3 is NOT < 0.3, so Q004 should not trigger
        assert not any(r.rule.rule_id == "Q004" for r in verdict.triggered_rules)
        # But it IS < 0.5, so Q012 should trigger (WARN)
        assert any(r.rule.rule_id == "Q012" for r in verdict.triggered_rules)
        assert verdict.verdict == Verdict.WARN

    def test_audio_none_skips_peak_check(self):
        """When audio=None, Q011 peak check is skipped."""
        analysis = _make_analysis()
        verdict = check_quality(analysis, sample_rate=48000, audio=None)

        # Q011 should not be triggered without audio
        assert not any(r.rule.rule_id == "Q011" for r in verdict.triggered_rules)

    def test_empty_peaks_with_valid_dominant_hz(self):
        """Edge case: dominant_hz set but peaks list empty."""
        # This is an unusual state but should be handled
        analysis = _make_analysis(dominant_hz=440.0, peaks=[])
        verdict = check_quality(analysis, sample_rate=48000)

        # Q003 checks dominant_hz, not peaks length
        assert not any(r.rule.rule_id == "Q003" for r in verdict.triggered_rules)
        # But Q013 should not trigger (requires peak_count > 0)
        assert not any(r.rule.rule_id == "Q013" for r in verdict.triggered_rules)
