# INSTRUMENT CLASS: MEASUREMENT
"""Measurement workflow contracts.

A workflow contract defines the procedural requirements for a legitimate
measurement session. It specifies:
  - required repetitions for repeatability evidence
  - sample rate and FFT parameters
  - minimum signal quality thresholds
  - calibration requirements
  - fixture and environment requirements

Workflow contracts are measurement governance, not UI presets.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class FixtureRequirements:
    """Physical fixture requirements for a measurement workflow."""

    fixture_id: str | None = None
    support_condition: str | None = None  # "free", "clamped", "supported"
    mic_position: str | None = None  # "center", "off-center", "roving"
    tap_position: str | None = None  # "center", "antinode", "grid"
    reference_mic_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass(frozen=True)
class EnvironmentRequirements:
    """Environmental requirements for a measurement workflow."""

    min_temperature_c: float | None = None
    max_temperature_c: float | None = None
    min_humidity_pct: float | None = None
    max_humidity_pct: float | None = None
    max_ambient_noise_dbfs: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass(frozen=True)
class MeasurementWorkflowContractV1:
    """Defines procedural requirements for a measurement workflow.

    This is a governance artifact, not a UI convenience. A measurement
    that does not satisfy its workflow contract cannot be considered
    legitimate for comparison or analysis.
    """

    workflow_id: str
    display_name: str
    description: str

    # Repeatability requirements
    required_repetitions: int
    max_frequency_variance_pct: float

    # Capture parameters
    sample_rate_hz: int
    fft_window: str  # "hann", "hamming", "blackman", "boxcar"
    min_snr_db: float  # Minimum signal-to-noise ratio in dB

    # Optional parameters with defaults
    fft_size: int = 4096
    min_peak_prominence_db: float = 6.0
    max_clipping_samples: int = 0

    # Calibration
    requires_calibration: bool = True
    max_calibration_age_days: int = 30

    # Fixture and environment
    fixture_requirements: FixtureRequirements = field(
        default_factory=FixtureRequirements
    )
    environment_requirements: EnvironmentRequirements = field(
        default_factory=EnvironmentRequirements
    )

    # Schema version for serialization
    schema_version: str = "measurement_workflow_contract_v1"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON export."""
        return {
            "schema_version": self.schema_version,
            "workflow_id": self.workflow_id,
            "display_name": self.display_name,
            "description": self.description,
            "required_repetitions": self.required_repetitions,
            "max_frequency_variance_pct": self.max_frequency_variance_pct,
            "sample_rate_hz": self.sample_rate_hz,
            "fft_window": self.fft_window,
            "fft_size": self.fft_size,
            "min_snr_db": self.min_snr_db,
            "min_peak_prominence_db": self.min_peak_prominence_db,
            "max_clipping_samples": self.max_clipping_samples,
            "requires_calibration": self.requires_calibration,
            "max_calibration_age_days": self.max_calibration_age_days,
            "fixture_requirements": self.fixture_requirements.to_dict(),
            "environment_requirements": self.environment_requirements.to_dict(),
        }

    def validate(self) -> list[str]:
        """Validate contract invariants. Returns list of error messages."""
        errors: list[str] = []
        if self.required_repetitions < 1:
            errors.append("required_repetitions must be >= 1")
        if self.sample_rate_hz < 8000:
            errors.append("sample_rate_hz must be >= 8000")
        if self.fft_window not in ("hann", "hamming", "blackman", "boxcar"):
            errors.append(f"fft_window must be hann|hamming|blackman|boxcar, got {self.fft_window}")
        if self.fft_size < 256 or (self.fft_size & (self.fft_size - 1)) != 0:
            errors.append("fft_size must be a power of 2 >= 256")
        if self.min_snr_db < 0:
            errors.append("min_snr_db must be >= 0")
        if self.max_frequency_variance_pct < 0:
            errors.append("max_frequency_variance_pct must be >= 0")
        if self.max_calibration_age_days < 1:
            errors.append("max_calibration_age_days must be >= 1")
        return errors
