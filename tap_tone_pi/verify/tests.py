# INSTRUMENT CLASS: MEASUREMENT
"""
Individual verification tests for the analysis pipeline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any


class TestOutcome(Enum):
    """Outcome of a verification test."""

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"


@dataclass
class VerificationTest:
    """Result of a single verification test."""

    name: str
    outcome: TestOutcome
    expected: Any
    actual: Any
    tolerance: Optional[float] = None
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Check if test passed."""
        return self.outcome == TestOutcome.PASS

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "outcome": self.outcome.value,
            "expected": self.expected,
            "actual": self.actual,
            "tolerance": self.tolerance,
            "message": self.message,
            "details": self.details,
        }


def verify_frequency_accuracy(
    measured_hz: float,
    expected_hz: float,
    tolerance_cents: float = 10.0,
) -> VerificationTest:
    """
    Verify frequency measurement accuracy.

    Args:
        measured_hz: Measured frequency in Hz
        expected_hz: Expected frequency in Hz
        tolerance_cents: Tolerance in cents (100 cents = 1 semitone)

    Returns:
        VerificationTest result
    """
    if expected_hz <= 0:
        return VerificationTest(
            name="frequency_accuracy",
            outcome=TestOutcome.ERROR,
            expected=expected_hz,
            actual=measured_hz,
            message="Invalid expected frequency",
        )

    # Calculate error in cents
    if measured_hz > 0:
        cents_error = 1200 * math.log2(measured_hz / expected_hz)
    else:
        cents_error = float("inf")

    passed = abs(cents_error) <= tolerance_cents

    return VerificationTest(
        name="frequency_accuracy",
        outcome=TestOutcome.PASS if passed else TestOutcome.FAIL,
        expected=expected_hz,
        actual=measured_hz,
        tolerance=tolerance_cents,
        message=f"Error: {cents_error:.1f} cents"
        if passed
        else f"Error {cents_error:.1f} cents exceeds {tolerance_cents:.1f} cents tolerance",
        details={
            "cents_error": cents_error,
            "tolerance_cents": tolerance_cents,
        },
    )


def verify_amplitude_accuracy(
    measured_db: float,
    expected_db: float,
    tolerance_db: float = 1.0,
) -> VerificationTest:
    """
    Verify amplitude measurement accuracy.

    Args:
        measured_db: Measured amplitude in dB
        expected_db: Expected amplitude in dB
        tolerance_db: Tolerance in dB

    Returns:
        VerificationTest result
    """
    error_db = abs(measured_db - expected_db)
    passed = error_db <= tolerance_db

    return VerificationTest(
        name="amplitude_accuracy",
        outcome=TestOutcome.PASS if passed else TestOutcome.FAIL,
        expected=expected_db,
        actual=measured_db,
        tolerance=tolerance_db,
        message=f"Error: {error_db:.2f} dB"
        if passed
        else f"Error {error_db:.2f} dB exceeds {tolerance_db:.1f} dB tolerance",
        details={
            "error_db": error_db,
        },
    )


def verify_snr_measurement(
    measured_snr_db: float,
    expected_snr_db: float,
    tolerance_db: float = 3.0,
) -> VerificationTest:
    """
    Verify SNR measurement accuracy.

    Args:
        measured_snr_db: Measured SNR in dB
        expected_snr_db: Expected SNR in dB
        tolerance_db: Tolerance in dB

    Returns:
        VerificationTest result
    """
    error_db = abs(measured_snr_db - expected_snr_db)
    passed = error_db <= tolerance_db

    return VerificationTest(
        name="snr_measurement",
        outcome=TestOutcome.PASS if passed else TestOutcome.FAIL,
        expected=expected_snr_db,
        actual=measured_snr_db,
        tolerance=tolerance_db,
        message=f"SNR error: {error_db:.1f} dB"
        if passed
        else f"SNR error {error_db:.1f} dB exceeds {tolerance_db:.1f} dB tolerance",
        details={
            "error_db": error_db,
        },
    )


def verify_peak_detection(
    detected_peaks_hz: List[float],
    expected_peaks_hz: List[float],
    tolerance_cents: float = 20.0,
    min_detection_rate: float = 0.8,
) -> VerificationTest:
    """
    Verify peak detection accuracy.

    Args:
        detected_peaks_hz: List of detected peak frequencies
        expected_peaks_hz: List of expected peak frequencies
        tolerance_cents: Frequency tolerance in cents
        min_detection_rate: Minimum fraction of peaks that must be detected

    Returns:
        VerificationTest result
    """
    if not expected_peaks_hz:
        return VerificationTest(
            name="peak_detection",
            outcome=TestOutcome.SKIP,
            expected=expected_peaks_hz,
            actual=detected_peaks_hz,
            message="No expected peaks specified",
        )

    # Match detected peaks to expected peaks
    matched = 0
    matches = []

    for expected in expected_peaks_hz:
        best_match = None
        best_error = float("inf")

        for detected in detected_peaks_hz:
            if detected > 0 and expected > 0:
                cents_error = abs(1200 * math.log2(detected / expected))
                if cents_error < best_error and cents_error <= tolerance_cents:
                    best_error = cents_error
                    best_match = detected

        if best_match is not None:
            matched += 1
            matches.append(
                {
                    "expected": expected,
                    "detected": best_match,
                    "error_cents": best_error,
                }
            )
        else:
            matches.append(
                {
                    "expected": expected,
                    "detected": None,
                    "error_cents": None,
                }
            )

    detection_rate = matched / len(expected_peaks_hz)
    passed = detection_rate >= min_detection_rate

    return VerificationTest(
        name="peak_detection",
        outcome=TestOutcome.PASS if passed else TestOutcome.FAIL,
        expected=len(expected_peaks_hz),
        actual=matched,
        tolerance=min_detection_rate,
        message=f"Detected {matched}/{len(expected_peaks_hz)} peaks ({detection_rate:.0%})",
        details={
            "detection_rate": detection_rate,
            "matches": matches,
            "expected_peaks": expected_peaks_hz,
            "detected_peaks": detected_peaks_hz,
        },
    )


def verify_noise_floor(
    measured_noise_db: float,
    max_noise_db: float = -60.0,
) -> VerificationTest:
    """
    Verify noise floor is below threshold.

    Args:
        measured_noise_db: Measured noise floor in dB
        max_noise_db: Maximum acceptable noise floor in dB

    Returns:
        VerificationTest result
    """
    passed = measured_noise_db <= max_noise_db

    return VerificationTest(
        name="noise_floor",
        outcome=TestOutcome.PASS if passed else TestOutcome.FAIL,
        expected=max_noise_db,
        actual=measured_noise_db,
        message=f"Noise floor: {measured_noise_db:.1f} dB"
        if passed
        else f"Noise floor {measured_noise_db:.1f} dB exceeds {max_noise_db:.1f} dB threshold",
        details={
            "margin_db": max_noise_db - measured_noise_db,
        },
    )


def verify_thd(
    measured_thd_percent: float,
    max_thd_percent: float = 1.0,
) -> VerificationTest:
    """
    Verify THD is below threshold.

    Args:
        measured_thd_percent: Measured THD in percent
        max_thd_percent: Maximum acceptable THD in percent

    Returns:
        VerificationTest result
    """
    passed = measured_thd_percent <= max_thd_percent

    return VerificationTest(
        name="thd",
        outcome=TestOutcome.PASS if passed else TestOutcome.FAIL,
        expected=max_thd_percent,
        actual=measured_thd_percent,
        message=f"THD: {measured_thd_percent:.3f}%"
        if passed
        else f"THD {measured_thd_percent:.3f}% exceeds {max_thd_percent:.1f}% threshold",
        details={
            "margin_percent": max_thd_percent - measured_thd_percent,
        },
    )


def verify_latency(
    measured_latency_ms: float,
    max_latency_ms: float = 50.0,
) -> VerificationTest:
    """
    Verify latency is below threshold.

    Args:
        measured_latency_ms: Measured latency in ms
        max_latency_ms: Maximum acceptable latency in ms

    Returns:
        VerificationTest result
    """
    passed = measured_latency_ms <= max_latency_ms

    return VerificationTest(
        name="latency",
        outcome=TestOutcome.PASS if passed else TestOutcome.FAIL,
        expected=max_latency_ms,
        actual=measured_latency_ms,
        message=f"Latency: {measured_latency_ms:.1f} ms"
        if passed
        else f"Latency {measured_latency_ms:.1f} ms exceeds {max_latency_ms:.1f} ms threshold",
        details={
            "margin_ms": max_latency_ms - measured_latency_ms,
        },
    )


def verify_sample_rate(
    measured_rate: float,
    expected_rate: float,
    tolerance_ppm: float = 100.0,
) -> VerificationTest:
    """
    Verify sample rate accuracy.

    Args:
        measured_rate: Measured sample rate in Hz
        expected_rate: Expected sample rate in Hz
        tolerance_ppm: Tolerance in parts per million

    Returns:
        VerificationTest result
    """
    if expected_rate <= 0:
        return VerificationTest(
            name="sample_rate",
            outcome=TestOutcome.ERROR,
            expected=expected_rate,
            actual=measured_rate,
            message="Invalid expected sample rate",
        )

    error_ppm = abs((measured_rate - expected_rate) / expected_rate) * 1e6
    passed = error_ppm <= tolerance_ppm

    return VerificationTest(
        name="sample_rate",
        outcome=TestOutcome.PASS if passed else TestOutcome.FAIL,
        expected=expected_rate,
        actual=measured_rate,
        tolerance=tolerance_ppm,
        message=f"Rate error: {error_ppm:.1f} ppm"
        if passed
        else f"Rate error {error_ppm:.1f} ppm exceeds {tolerance_ppm:.1f} ppm tolerance",
        details={
            "error_ppm": error_ppm,
        },
    )
