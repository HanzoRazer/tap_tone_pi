"""Tests for uncertainty flags module (Phase 3.2)."""

import pytest

from tap_tone_pi.core.uncertainty_flags import (
    UncertaintyFlag,
    QualityThresholds,
    FlagDetail,
    QualityAssessment,
    assess_measurement_quality,
    format_flags_for_display,
    DEFAULT_THRESHOLDS,
    FLAG_DESCRIPTIONS,
    FLAG_SEVERITY,
)


class TestUncertaintyFlag:
    """Tests for UncertaintyFlag enum."""

    def test_all_flags_have_descriptions(self):
        """Every flag should have a description."""
        for flag in UncertaintyFlag:
            assert flag in FLAG_DESCRIPTIONS
            assert len(FLAG_DESCRIPTIONS[flag]) > 0

    def test_all_flags_have_severity(self):
        """Every flag should have a severity level."""
        for flag in UncertaintyFlag:
            assert flag in FLAG_SEVERITY
            assert FLAG_SEVERITY[flag] in (0, 1, 2)


class TestQualityThresholds:
    """Tests for QualityThresholds."""

    def test_default_values(self):
        """Default thresholds should be reasonable."""
        th = QualityThresholds()

        assert th.max_relative_uncertainty == 0.02  # 2%
        assert th.min_confidence == 0.5
        assert th.min_snr_db == 15.0
        assert th.min_coherence == 0.7

    def test_custom_thresholds(self):
        """Should accept custom thresholds."""
        th = QualityThresholds(
            min_confidence=0.8,
            min_snr_db=20.0,
        )

        assert th.min_confidence == 0.8
        assert th.min_snr_db == 20.0


class TestFlagDetail:
    """Tests for FlagDetail."""

    def test_flag_id(self):
        """flag_id should return flag name."""
        detail = FlagDetail(
            flag=UncertaintyFlag.LOW_SNR,
            severity=1,
            description="Test description",
        )

        assert detail.flag_id == "LOW_SNR"

    def test_to_dict(self):
        """Should serialize to dictionary."""
        detail = FlagDetail(
            flag=UncertaintyFlag.HIGH_UNCERTAINTY,
            severity=1,
            description="Test",
            value=2.5,
            threshold=2.0,
        )

        d = detail.to_dict()
        assert d["flag_id"] == "HIGH_UNCERTAINTY"
        assert d["severity"] == 1
        assert d["value"] == 2.5
        assert d["threshold"] == 2.0


class TestQualityAssessment:
    """Tests for QualityAssessment."""

    def test_empty_assessment(self):
        """Empty assessment should be acceptable."""
        assessment = QualityAssessment()

        assert assessment.is_acceptable
        assert not assessment.has_warnings
        assert len(assessment.flags) == 0
        assert assessment.overall_quality == 1.0

    def test_add_flag(self):
        """Should add flags correctly."""
        assessment = QualityAssessment()
        assessment.add_flag(
            UncertaintyFlag.LOW_SNR,
            value=10.0,
            threshold=15.0,
        )

        assert len(assessment.flags) == 1
        assert assessment.flags[0].flag == UncertaintyFlag.LOW_SNR
        assert assessment.has_warnings

    def test_is_acceptable_with_warning(self):
        """Warning flags should still be acceptable."""
        assessment = QualityAssessment()
        assessment.add_flag(UncertaintyFlag.LOW_SNR)  # Severity 1

        assert assessment.is_acceptable
        assert assessment.has_warnings

    def test_not_acceptable_with_error(self):
        """Error flags should make assessment unacceptable."""
        assessment = QualityAssessment()
        assessment.add_flag(UncertaintyFlag.CLIPPED)  # Severity 2

        assert not assessment.is_acceptable
        assert assessment.has_warnings

    def test_overall_quality_levels(self):
        """Quality score should reflect flag severity."""
        # No flags
        clean = QualityAssessment()
        assert clean.overall_quality == 1.0

        # Info flag only
        info = QualityAssessment()
        info.add_flag(UncertaintyFlag.MISSING_REFERENCE)  # Severity 0
        assert info.overall_quality == 0.9

        # Warning flag
        warning = QualityAssessment()
        warning.add_flag(UncertaintyFlag.LOW_SNR)  # Severity 1
        assert warning.overall_quality == 0.7

        # Error flag
        error = QualityAssessment()
        error.add_flag(UncertaintyFlag.CLIPPED)  # Severity 2
        assert error.overall_quality == 0.3

    def test_flag_ids(self):
        """Should return list of flag IDs."""
        assessment = QualityAssessment()
        assessment.add_flag(UncertaintyFlag.LOW_SNR)
        assessment.add_flag(UncertaintyFlag.LOW_CONFIDENCE)

        ids = assessment.flag_ids
        assert "LOW_SNR" in ids
        assert "LOW_CONFIDENCE" in ids

    def test_max_severity(self):
        """Should return maximum severity."""
        assessment = QualityAssessment()
        assert assessment.max_severity == 0

        assessment.add_flag(UncertaintyFlag.MISSING_REFERENCE)  # Severity 0
        assert assessment.max_severity == 0

        assessment.add_flag(UncertaintyFlag.LOW_SNR)  # Severity 1
        assert assessment.max_severity == 1

        assessment.add_flag(UncertaintyFlag.CLIPPED)  # Severity 2
        assert assessment.max_severity == 2

    def test_to_dict(self):
        """Should serialize to dictionary."""
        assessment = QualityAssessment()
        assessment.add_flag(UncertaintyFlag.LOW_SNR)

        d = assessment.to_dict()
        assert "is_acceptable" in d
        assert "has_warnings" in d
        assert "overall_quality" in d
        assert "flags" in d
        assert len(d["flags"]) == 1

    def test_format_summary(self):
        """Should format one-line summary."""
        clean = QualityAssessment()
        assert clean.format_summary() == "OK"

        flagged = QualityAssessment()
        flagged.add_flag(UncertaintyFlag.LOW_SNR)
        summary = flagged.format_summary()
        assert "LOW_SNR" in summary


class TestAssessMeasurementQuality:
    """Tests for assess_measurement_quality function."""

    def test_clean_measurement(self):
        """Good measurement should have no flags."""
        assessment = assess_measurement_quality(
            dominant_hz=185.0,
            freq_uncertainty_hz=0.5,
            confidence=0.8,
            snr_db=25.0,
            rms=0.1,
            clipped=False,
        )

        assert assessment.is_acceptable
        assert len(assessment.flags) == 0

    def test_clipped_flag(self):
        """Clipped audio should trigger flag."""
        assessment = assess_measurement_quality(clipped=True)

        assert UncertaintyFlag.CLIPPED in [f.flag for f in assessment.flags]
        assert not assessment.is_acceptable

    def test_low_signal_flag(self):
        """Low RMS should trigger flag."""
        assessment = assess_measurement_quality(rms=0.001)

        assert UncertaintyFlag.LOW_SIGNAL in [f.flag for f in assessment.flags]

    def test_low_snr_flag(self):
        """Low SNR should trigger flag."""
        assessment = assess_measurement_quality(snr_db=10.0)

        assert UncertaintyFlag.LOW_SNR in [f.flag for f in assessment.flags]

    def test_low_confidence_flag(self):
        """Low confidence should trigger flag."""
        assessment = assess_measurement_quality(confidence=0.3)

        assert UncertaintyFlag.LOW_CONFIDENCE in [f.flag for f in assessment.flags]

    def test_poor_coherence_flag(self):
        """Low coherence should trigger flag."""
        assessment = assess_measurement_quality(coherence=0.5)

        assert UncertaintyFlag.POOR_COHERENCE in [f.flag for f in assessment.flags]

    def test_wide_bandwidth_flag(self):
        """Low Q-factor should trigger flag."""
        assessment = assess_measurement_quality(q_factor=3.0)

        assert UncertaintyFlag.WIDE_BANDWIDTH in [f.flag for f in assessment.flags]

    def test_high_uncertainty_flag_relative(self):
        """High relative uncertainty should trigger flag."""
        assessment = assess_measurement_quality(
            dominant_hz=100.0,
            freq_uncertainty_hz=5.0,  # 5% - above 2% threshold
        )

        assert UncertaintyFlag.HIGH_UNCERTAINTY in [f.flag for f in assessment.flags]

    def test_high_uncertainty_flag_absolute(self):
        """High absolute uncertainty should trigger flag."""
        assessment = assess_measurement_quality(
            dominant_hz=1000.0,
            freq_uncertainty_hz=3.0,  # Above 2 Hz threshold
        )

        assert UncertaintyFlag.HIGH_UNCERTAINTY in [f.flag for f in assessment.flags]

    def test_high_variation_flag(self):
        """High CV should trigger flag."""
        assessment = assess_measurement_quality(cv_pct=2.5)

        assert UncertaintyFlag.HIGH_VARIATION in [f.flag for f in assessment.flags]

    def test_outlier_flag(self):
        """Outlier measurement should trigger flag."""
        assessment = assess_measurement_quality(
            dominant_hz=195.0,
            freq_uncertainty_hz=1.0,
            reference_hz=185.0,  # 10 Hz away, >3σ
        )

        assert UncertaintyFlag.OUTLIER in [f.flag for f in assessment.flags]

    def test_custom_thresholds(self):
        """Should use custom thresholds."""
        # Default: 15 dB SNR threshold
        default_assess = assess_measurement_quality(snr_db=12.0)
        assert UncertaintyFlag.LOW_SNR in [f.flag for f in default_assess.flags]

        # Custom: 10 dB threshold
        custom_th = QualityThresholds(min_snr_db=10.0)
        custom_assess = assess_measurement_quality(
            snr_db=12.0,
            thresholds=custom_th,
        )
        assert UncertaintyFlag.LOW_SNR not in [f.flag for f in custom_assess.flags]

    def test_multiple_flags(self):
        """Multiple issues should trigger multiple flags."""
        assessment = assess_measurement_quality(
            clipped=True,
            confidence=0.3,
            snr_db=10.0,
        )

        flag_types = [f.flag for f in assessment.flags]
        assert UncertaintyFlag.CLIPPED in flag_types
        assert UncertaintyFlag.LOW_CONFIDENCE in flag_types
        assert UncertaintyFlag.LOW_SNR in flag_types


class TestFormatFlagsForDisplay:
    """Tests for format_flags_for_display function."""

    def test_no_flags(self):
        """Clean assessment should show OK."""
        assessment = QualityAssessment()
        output = format_flags_for_display(assessment)

        assert "OK" in output or "No quality flags" in output

    def test_with_flags(self):
        """Should display flag information."""
        assessment = QualityAssessment()
        assessment.add_flag(
            UncertaintyFlag.LOW_SNR,
            message="SNR 10.0 dB below minimum 15.0 dB",
        )

        output = format_flags_for_display(assessment, show_details=True)

        assert "LOW_SNR" in output
        assert "10.0" in output

    def test_severity_indicators(self):
        """Should show severity indicators."""
        assessment = QualityAssessment()
        assessment.add_flag(UncertaintyFlag.CLIPPED)  # Error

        output = format_flags_for_display(assessment)
        assert "ERROR" in output

        assessment2 = QualityAssessment()
        assessment2.add_flag(UncertaintyFlag.LOW_SNR)  # Warning

        output2 = format_flags_for_display(assessment2)
        assert "WARN" in output2


class TestRealisticScenarios:
    """Tests with realistic tap tone measurement scenarios."""

    def test_good_measurement(self):
        """Typical good tap tone measurement."""
        assessment = assess_measurement_quality(
            dominant_hz=185.2,
            freq_uncertainty_hz=0.3,
            confidence=0.85,
            snr_db=28.0,
            coherence=0.92,
            q_factor=25.0,
            rms=0.08,
            clipped=False,
        )

        assert assessment.is_acceptable
        assert not assessment.has_warnings
        assert assessment.overall_quality == 1.0

    def test_marginal_measurement(self):
        """Measurement with minor issues."""
        assessment = assess_measurement_quality(
            dominant_hz=185.2,
            freq_uncertainty_hz=0.5,
            confidence=0.55,  # Just above threshold
            snr_db=16.0,  # Just above threshold
            rms=0.05,
            clipped=False,
        )

        # Should be acceptable but close to warnings
        assert assessment.is_acceptable

    def test_poor_measurement(self):
        """Measurement with quality issues."""
        assessment = assess_measurement_quality(
            dominant_hz=185.2,
            freq_uncertainty_hz=3.0,  # High uncertainty
            confidence=0.35,  # Low confidence
            snr_db=10.0,  # Low SNR
            q_factor=3.0,  # Broad peak
            rms=0.03,
            clipped=False,
        )

        # Should have multiple warnings
        assert assessment.has_warnings
        assert len(assessment.flags) >= 3

    def test_failed_measurement(self):
        """Measurement that should be retaken."""
        assessment = assess_measurement_quality(
            clipped=True,
            rms=0.002,  # Very low signal
        )

        assert not assessment.is_acceptable
        assert UncertaintyFlag.CLIPPED in [f.flag for f in assessment.flags]
