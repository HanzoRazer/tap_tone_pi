"""
Verification test suite for Tap Tone Pi.

Provides synthetic signal tests to verify the analysis pipeline
works correctly. Used for:
- System self-test after installation
- Regression testing after updates
- Calibration verification
"""

from .suite import (
    VerificationResult,
    VerificationSuite,
    run_verification_suite,
    quick_verify,
)
from .tests import (
    VerificationTest,
    TestOutcome,
    verify_frequency_accuracy,
    verify_amplitude_accuracy,
    verify_snr_measurement,
    verify_peak_detection,
    verify_noise_floor,
)
from .report import (
    VerificationReport,
    format_verification_report,
    save_verification_report,
)

__all__ = [
    # Suite
    "VerificationResult",
    "VerificationSuite",
    "run_verification_suite",
    "quick_verify",
    # Tests
    "VerificationTest",
    "TestOutcome",
    "verify_frequency_accuracy",
    "verify_amplitude_accuracy",
    "verify_snr_measurement",
    "verify_peak_detection",
    "verify_noise_floor",
    # Report
    "VerificationReport",
    "format_verification_report",
    "save_verification_report",
]
