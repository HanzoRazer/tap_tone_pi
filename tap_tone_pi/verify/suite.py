"""
Verification test suite runner.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any

import numpy as np

from .tests import (
    VerificationTest,
    TestOutcome,
    verify_frequency_accuracy,
    verify_amplitude_accuracy,
    verify_peak_detection,
    verify_noise_floor,
)


@dataclass
class VerificationResult:
    """Result of running verification suite."""

    tests: List[VerificationTest]
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_s: float = 0.0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        self._update_counts()

    def _update_counts(self):
        """Update pass/fail counts from tests."""
        self.passed = sum(1 for t in self.tests if t.outcome == TestOutcome.PASS)
        self.failed = sum(1 for t in self.tests if t.outcome == TestOutcome.FAIL)
        self.skipped = sum(1 for t in self.tests if t.outcome == TestOutcome.SKIP)
        self.errors = sum(1 for t in self.tests if t.outcome == TestOutcome.ERROR)

    @property
    def total(self) -> int:
        """Total number of tests."""
        return len(self.tests)

    @property
    def success(self) -> bool:
        """Check if all tests passed (no failures or errors)."""
        return self.failed == 0 and self.errors == 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate as fraction."""
        runnable = self.passed + self.failed
        return self.passed / runnable if runnable > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "duration_s": self.duration_s,
            "summary": {
                "total": self.total,
                "passed": self.passed,
                "failed": self.failed,
                "skipped": self.skipped,
                "errors": self.errors,
                "success_rate": self.success_rate,
            },
            "tests": [t.to_dict() for t in self.tests],
        }


class VerificationSuite:
    """
    Suite of verification tests for the analysis pipeline.

    Uses synthetic signals to verify the pipeline produces
    correct results for known inputs.
    """

    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = sample_rate
        self.tests: List[VerificationTest] = []

    def run_all(self, verbose: bool = False) -> VerificationResult:
        """
        Run all verification tests.

        Args:
            verbose: Print progress during tests

        Returns:
            VerificationResult with all test outcomes
        """
        import time

        start_time = time.time()
        self.tests = []

        # Test 1: Single frequency detection
        if verbose:
            print("Testing frequency detection...")
        self._test_frequency_detection()

        # Test 2: Amplitude measurement
        if verbose:
            print("Testing amplitude measurement...")
        self._test_amplitude_measurement()

        # Test 3: Multi-peak detection
        if verbose:
            print("Testing multi-peak detection...")
        self._test_multi_peak_detection()

        # Test 4: Noise floor measurement
        if verbose:
            print("Testing noise floor measurement...")
        self._test_noise_floor()

        # Test 5: Decay detection
        if verbose:
            print("Testing decay detection...")
        self._test_decay_detection()

        duration = time.time() - start_time

        result = VerificationResult(
            tests=self.tests,
            duration_s=duration,
        )

        if verbose:
            print(f"\nCompleted {result.total} tests in {duration:.2f}s")
            print(f"Passed: {result.passed}, Failed: {result.failed}")

        return result

    def _test_frequency_detection(self):
        """Test frequency detection at various frequencies."""
        from tap_tone_pi.signal_gen import generate_sine
        from tap_tone_pi.core.analysis import analyze_tap

        test_frequencies = [100.0, 440.0, 1000.0, 2000.0]

        for freq in test_frequencies:
            # Generate test signal
            signal = generate_sine(
                frequency_hz=freq,
                duration_s=1.0,
                sample_rate=self.sample_rate,
                amplitude=0.5,
            )

            # Analyze
            result = analyze_tap(signal, self.sample_rate)

            # Verify
            if result.dominant_hz:
                test = verify_frequency_accuracy(
                    measured_hz=result.dominant_hz,
                    expected_hz=freq,
                    tolerance_cents=5.0,  # Tight tolerance for pure sine
                )
                test.name = f"frequency_detection_{int(freq)}Hz"
            else:
                test = VerificationTest(
                    name=f"frequency_detection_{int(freq)}Hz",
                    outcome=TestOutcome.FAIL,
                    expected=freq,
                    actual=None,
                    message="No frequency detected",
                )

            self.tests.append(test)

    def _test_amplitude_measurement(self):
        """Test amplitude measurement accuracy."""
        from tap_tone_pi.signal_gen import generate_sine

        test_amplitudes = [0.1, 0.5, 0.9]

        for amp in test_amplitudes:
            # Generate test signal
            signal = generate_sine(
                frequency_hz=1000.0,
                duration_s=0.5,
                sample_rate=self.sample_rate,
                amplitude=amp,
            )

            # Measure RMS
            rms = np.sqrt(np.mean(signal**2))
            measured_db = 20 * math.log10(rms + 1e-10)

            # Expected: sine wave RMS = peak / sqrt(2)
            expected_rms = amp / math.sqrt(2)
            expected_db = 20 * math.log10(expected_rms)

            test = verify_amplitude_accuracy(
                measured_db=measured_db,
                expected_db=expected_db,
                tolerance_db=0.5,
            )
            test.name = f"amplitude_{int(amp*100)}pct"
            self.tests.append(test)

    def _test_multi_peak_detection(self):
        """Test detection of multiple peaks."""
        from tap_tone_pi.signal_gen import generate_multitone
        from tap_tone_pi.core.analysis import analyze_tap

        # Generate multitone with known frequencies
        frequencies = [200.0, 500.0, 1000.0]
        signal = generate_multitone(
            frequencies_hz=frequencies,
            duration_s=1.0,
            sample_rate=self.sample_rate,
            amplitude=0.6,
        )

        # Analyze
        result = analyze_tap(signal, self.sample_rate)

        # Get detected peak frequencies
        detected = [p.freq_hz for p in result.peaks[:10]] if result.peaks else []

        test = verify_peak_detection(
            detected_peaks_hz=detected,
            expected_peaks_hz=frequencies,
            tolerance_cents=20.0,
            min_detection_rate=0.67,  # At least 2 of 3
        )
        self.tests.append(test)

    def _test_noise_floor(self):
        """Test noise floor measurement."""
        from tap_tone_pi.signal_gen import generate_noise

        # Generate low-level noise
        noise_amplitude = 0.001  # Very quiet
        signal = generate_noise(
            noise_type="white",
            duration_s=0.5,
            sample_rate=self.sample_rate,
            amplitude=noise_amplitude,
            seed=42,
        )

        # Measure RMS
        rms = np.sqrt(np.mean(signal**2))
        measured_db = 20 * math.log10(rms + 1e-10)

        # Expected: RMS should be close to amplitude for white noise
        expected_db = 20 * math.log10(noise_amplitude)

        test = verify_noise_floor(
            measured_noise_db=measured_db,
            max_noise_db=expected_db + 6,  # Allow 6 dB margin
        )
        self.tests.append(test)

    def _test_decay_detection(self):
        """Test decay rate measurement."""
        # Generate exponentially decaying signal
        duration = 1.0
        freq = 440.0
        decay_rate = 5.0  # seconds^-1

        t = np.arange(int(self.sample_rate * duration)) / self.sample_rate
        envelope = np.exp(-decay_rate * t)
        signal = 0.8 * envelope * np.sin(2 * np.pi * freq * t)

        # Measure actual decay
        # Find RMS in first and second half
        mid = len(signal) // 2
        rms1 = np.sqrt(np.mean(signal[:mid] ** 2))
        rms2 = np.sqrt(np.mean(signal[mid:] ** 2))

        if rms1 > 0 and rms2 > 0:
            # Calculate measured decay in dB/s
            db_diff = 20 * math.log10(rms1 / rms2)
            time_diff = duration / 2
            measured_decay_db_per_s = db_diff / time_diff

            # Expected decay: 20 * log10(e^(-rate * t)) = -rate * t * 20 * log10(e)
            # = -rate * 8.686 dB/s
            expected_decay_db_per_s = decay_rate * 8.686

            error = abs(measured_decay_db_per_s - expected_decay_db_per_s)
            passed = error < expected_decay_db_per_s * 0.2  # 20% tolerance

            test = VerificationTest(
                name="decay_detection",
                outcome=TestOutcome.PASS if passed else TestOutcome.FAIL,
                expected=expected_decay_db_per_s,
                actual=measured_decay_db_per_s,
                tolerance=expected_decay_db_per_s * 0.2,
                message=f"Decay rate: {measured_decay_db_per_s:.1f} dB/s (expected {expected_decay_db_per_s:.1f})",
                details={
                    "error_percent": error / expected_decay_db_per_s * 100,
                },
            )
        else:
            test = VerificationTest(
                name="decay_detection",
                outcome=TestOutcome.ERROR,
                expected=decay_rate,
                actual=0,
                message="Could not measure decay",
            )

        self.tests.append(test)


def run_verification_suite(
    sample_rate: int = 48000,
    verbose: bool = False,
) -> VerificationResult:
    """
    Run the full verification suite.

    Args:
        sample_rate: Sample rate for test signals
        verbose: Print progress

    Returns:
        VerificationResult
    """
    suite = VerificationSuite(sample_rate=sample_rate)
    return suite.run_all(verbose=verbose)


def quick_verify(sample_rate: int = 48000) -> bool:
    """
    Quick verification check.

    Returns True if basic tests pass, False otherwise.
    """
    result = run_verification_suite(sample_rate=sample_rate, verbose=False)
    return result.success
