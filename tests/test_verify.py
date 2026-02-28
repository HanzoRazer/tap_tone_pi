"""
Tests for the verification test suite.
"""


import pytest

from tap_tone_pi.verify import (
    VerificationResult,
    VerificationSuite,
    run_verification_suite,
    quick_verify,
    TestOutcome,
    verify_frequency_accuracy,
    verify_amplitude_accuracy,
    verify_peak_detection,
    verify_noise_floor,
    VerificationReport,
    format_verification_report,
    save_verification_report,
)
from tap_tone_pi.verify.tests import verify_thd, verify_latency, verify_sample_rate


class TestVerifyFrequencyAccuracy:
    """Tests for frequency accuracy verification."""

    def test_exact_match_passes(self):
        """Test exact frequency match passes."""
        result = verify_frequency_accuracy(
            measured_hz=440.0,
            expected_hz=440.0,
            tolerance_cents=10.0,
        )

        assert result.passed
        assert result.outcome == TestOutcome.PASS
        assert result.details["cents_error"] == pytest.approx(0.0, abs=0.01)

    def test_within_tolerance_passes(self):
        """Test frequency within tolerance passes."""
        # 5 cents sharp of A440
        measured = 440.0 * (2 ** (5 / 1200))

        result = verify_frequency_accuracy(
            measured_hz=measured,
            expected_hz=440.0,
            tolerance_cents=10.0,
        )

        assert result.passed
        assert abs(result.details["cents_error"]) < 10.0

    def test_outside_tolerance_fails(self):
        """Test frequency outside tolerance fails."""
        # 15 cents sharp
        measured = 440.0 * (2 ** (15 / 1200))

        result = verify_frequency_accuracy(
            measured_hz=measured,
            expected_hz=440.0,
            tolerance_cents=10.0,
        )

        assert not result.passed
        assert result.outcome == TestOutcome.FAIL

    def test_invalid_frequency_errors(self):
        """Test invalid expected frequency gives error."""
        result = verify_frequency_accuracy(
            measured_hz=440.0,
            expected_hz=0.0,  # Invalid
            tolerance_cents=10.0,
        )

        assert result.outcome == TestOutcome.ERROR


class TestVerifyAmplitudeAccuracy:
    """Tests for amplitude accuracy verification."""

    def test_exact_match_passes(self):
        """Test exact amplitude match passes."""
        result = verify_amplitude_accuracy(
            measured_db=-20.0,
            expected_db=-20.0,
            tolerance_db=1.0,
        )

        assert result.passed

    def test_within_tolerance_passes(self):
        """Test amplitude within tolerance passes."""
        result = verify_amplitude_accuracy(
            measured_db=-20.5,
            expected_db=-20.0,
            tolerance_db=1.0,
        )

        assert result.passed

    def test_outside_tolerance_fails(self):
        """Test amplitude outside tolerance fails."""
        result = verify_amplitude_accuracy(
            measured_db=-22.0,
            expected_db=-20.0,
            tolerance_db=1.0,
        )

        assert not result.passed


class TestVerifyPeakDetection:
    """Tests for peak detection verification."""

    def test_all_peaks_detected_passes(self):
        """Test all peaks detected passes."""
        result = verify_peak_detection(
            detected_peaks_hz=[100.0, 200.0, 300.0],
            expected_peaks_hz=[100.0, 200.0, 300.0],
            tolerance_cents=20.0,
        )

        assert result.passed
        assert result.details["detection_rate"] == 1.0

    def test_partial_detection_passes(self):
        """Test partial detection above threshold passes."""
        result = verify_peak_detection(
            detected_peaks_hz=[100.0, 200.0],
            expected_peaks_hz=[100.0, 200.0, 300.0],
            tolerance_cents=20.0,
            min_detection_rate=0.6,
        )

        assert result.passed
        assert result.details["detection_rate"] == pytest.approx(0.667, rel=0.01)

    def test_low_detection_fails(self):
        """Test low detection rate fails."""
        result = verify_peak_detection(
            detected_peaks_hz=[100.0],
            expected_peaks_hz=[100.0, 200.0, 300.0],
            tolerance_cents=20.0,
            min_detection_rate=0.8,
        )

        assert not result.passed

    def test_empty_expected_skips(self):
        """Test empty expected peaks skips."""
        result = verify_peak_detection(
            detected_peaks_hz=[100.0, 200.0],
            expected_peaks_hz=[],
        )

        assert result.outcome == TestOutcome.SKIP


class TestVerifyNoiseFloor:
    """Tests for noise floor verification."""

    def test_below_threshold_passes(self):
        """Test noise below threshold passes."""
        result = verify_noise_floor(
            measured_noise_db=-70.0,
            max_noise_db=-60.0,
        )

        assert result.passed
        assert result.details["margin_db"] == 10.0

    def test_above_threshold_fails(self):
        """Test noise above threshold fails."""
        result = verify_noise_floor(
            measured_noise_db=-50.0,
            max_noise_db=-60.0,
        )

        assert not result.passed


class TestVerifyThd:
    """Tests for THD verification."""

    def test_low_thd_passes(self):
        """Test low THD passes."""
        result = verify_thd(
            measured_thd_percent=0.5,
            max_thd_percent=1.0,
        )

        assert result.passed

    def test_high_thd_fails(self):
        """Test high THD fails."""
        result = verify_thd(
            measured_thd_percent=2.0,
            max_thd_percent=1.0,
        )

        assert not result.passed


class TestVerifyLatency:
    """Tests for latency verification."""

    def test_low_latency_passes(self):
        """Test low latency passes."""
        result = verify_latency(
            measured_latency_ms=10.0,
            max_latency_ms=50.0,
        )

        assert result.passed

    def test_high_latency_fails(self):
        """Test high latency fails."""
        result = verify_latency(
            measured_latency_ms=100.0,
            max_latency_ms=50.0,
        )

        assert not result.passed


class TestVerifySampleRate:
    """Tests for sample rate verification."""

    def test_exact_rate_passes(self):
        """Test exact sample rate passes."""
        result = verify_sample_rate(
            measured_rate=48000.0,
            expected_rate=48000.0,
            tolerance_ppm=100.0,
        )

        assert result.passed

    def test_within_tolerance_passes(self):
        """Test rate within tolerance passes."""
        # 50 ppm error
        measured = 48000.0 * (1 + 50e-6)

        result = verify_sample_rate(
            measured_rate=measured,
            expected_rate=48000.0,
            tolerance_ppm=100.0,
        )

        assert result.passed

    def test_outside_tolerance_fails(self):
        """Test rate outside tolerance fails."""
        # 200 ppm error
        measured = 48000.0 * (1 + 200e-6)

        result = verify_sample_rate(
            measured_rate=measured,
            expected_rate=48000.0,
            tolerance_ppm=100.0,
        )

        assert not result.passed


class TestVerificationSuite:
    """Tests for the verification suite."""

    def test_run_all(self):
        """Test running all verification tests."""
        suite = VerificationSuite(sample_rate=48000)
        result = suite.run_all(verbose=False)

        assert isinstance(result, VerificationResult)
        assert result.total > 0
        assert result.passed + result.failed + result.skipped + result.errors == result.total

    def test_run_verification_suite(self):
        """Test convenience function."""
        result = run_verification_suite(sample_rate=48000, verbose=False)

        assert isinstance(result, VerificationResult)

    def test_quick_verify(self):
        """Test quick verification."""
        # Should return bool
        success = quick_verify(sample_rate=48000)
        assert isinstance(success, bool)

    def test_result_to_dict(self):
        """Test result serialization."""
        result = run_verification_suite(sample_rate=48000)
        data = result.to_dict()

        assert "timestamp" in data
        assert "duration_s" in data
        assert "tests" in data
        assert isinstance(data["tests"], list)


class TestVerificationReport:
    """Tests for verification report formatting."""

    def test_format_report(self):
        """Test report formatting."""
        result = run_verification_suite(sample_rate=48000)
        report = format_verification_report(result, verbose=True, color=False)

        assert "Verification Report" in report
        assert "Status:" in report

    def test_save_report(self, tmp_path):
        """Test saving report to file."""
        result = run_verification_suite(sample_rate=48000)
        filepath = tmp_path / "report.json"

        saved_path = save_verification_report(result, filepath)

        assert saved_path.exists()
        assert saved_path.suffix == ".json"

    def test_verification_report_class(self):
        """Test VerificationReport class."""
        result = run_verification_suite(sample_rate=48000)
        report = VerificationReport(result=result)

        data = report.to_dict()
        assert "schema_version" in data
        assert "system_info" in data
        assert "result" in data
