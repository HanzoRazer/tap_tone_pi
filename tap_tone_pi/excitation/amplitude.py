# INSTRUMENT CLASS: MEASUREMENT
"""Amplitude guardrails for controlled excitation (DO-90).

Enforces safe amplitude limits to prevent speaker/transducer damage
and ensure consistent excitation levels.

Amplitude scale: 0.0 to 1.0 (full scale)
- Default: 0.2 (safe, recommended)
- Normal range: 0.1 to 0.25
- Warning above: 0.5
- Hard reject above: 1.0
"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


DEFAULT_AMPLITUDE = 0.2
WARNING_AMPLITUDE = 0.5
MAX_SAFE_AMPLITUDE = 1.0


class AmplitudeGuardrail(Enum):
    """Amplitude validation result."""

    NORMAL = "normal"
    WARNING = "warning"
    REJECTED = "rejected"


@dataclass(frozen=True)
class AmplitudeValidationResult:
    """Result of amplitude validation."""

    guardrail: AmplitudeGuardrail
    amplitude: float
    message: str

    def to_dict(self) -> dict:
        return {
            "guardrail": self.guardrail.value,
            "amplitude": self.amplitude,
            "message": self.message,
        }


def validate_amplitude(
    amplitude: float,
    *,
    normal_max: float = 0.25,
    warning_max: float = WARNING_AMPLITUDE,
    reject_above: float = MAX_SAFE_AMPLITUDE,
) -> AmplitudeValidationResult:
    """Validate amplitude against guardrails.

    Args:
        amplitude: Requested amplitude (0.0 to 1.0)
        normal_max: Upper bound for normal range
        warning_max: Upper bound for warning range
        reject_above: Hard reject threshold

    Returns:
        AmplitudeValidationResult with guardrail status
    """
    if amplitude < 0.0:
        return AmplitudeValidationResult(
            guardrail=AmplitudeGuardrail.REJECTED,
            amplitude=amplitude,
            message="Amplitude cannot be negative",
        )

    if amplitude > reject_above:
        return AmplitudeValidationResult(
            guardrail=AmplitudeGuardrail.REJECTED,
            amplitude=amplitude,
            message=f"Amplitude {amplitude:.2f} exceeds maximum {reject_above:.2f}",
        )

    if amplitude > warning_max:
        return AmplitudeValidationResult(
            guardrail=AmplitudeGuardrail.WARNING,
            amplitude=amplitude,
            message=f"Amplitude {amplitude:.2f} exceeds warning threshold {warning_max:.2f}",
        )

    if amplitude > normal_max:
        return AmplitudeValidationResult(
            guardrail=AmplitudeGuardrail.WARNING,
            amplitude=amplitude,
            message=f"Amplitude {amplitude:.2f} above normal range (0.1-{normal_max:.2f})",
        )

    return AmplitudeValidationResult(
        guardrail=AmplitudeGuardrail.NORMAL,
        amplitude=amplitude,
        message="Amplitude within normal range",
    )


def clamp_amplitude(amplitude: float) -> Tuple[float, AmplitudeGuardrail]:
    """Clamp amplitude to safe range.

    Args:
        amplitude: Requested amplitude

    Returns:
        Tuple of (clamped amplitude, guardrail status)
    """
    if amplitude < 0.0:
        return 0.0, AmplitudeGuardrail.REJECTED
    if amplitude > MAX_SAFE_AMPLITUDE:
        return MAX_SAFE_AMPLITUDE, AmplitudeGuardrail.REJECTED
    if amplitude > WARNING_AMPLITUDE:
        return amplitude, AmplitudeGuardrail.WARNING
    return amplitude, AmplitudeGuardrail.NORMAL
