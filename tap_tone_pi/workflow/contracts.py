# INSTRUMENT CLASS: MEASUREMENT
"""Measurement workflow contracts and execution evidence (Dev Order 86).

A workflow contract defines the procedural requirements for a legitimate
measurement session. It specifies:
  - required repetitions for repeatability evidence
  - sample rate and FFT parameters
  - minimum signal quality thresholds
  - calibration requirements
  - fixture and environment requirements

Workflow execution evidence records what actually happened during a
measurement session, enabling procedural provenance and auditability.

Workflow contracts are measurement governance, not UI presets.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class WorkflowExecutionState(str, Enum):
    """Procedural execution state for a workflow.

    These are observational states only — no quality judgment.
    """

    NOT_STARTED = "not_started"
    PARTIAL = "partial"
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"  # Started but cannot complete (e.g., missing data)
    ABORTED = "aborted"


class CalibrationState(str, Enum):
    """Calibration validity state.

    Observational only — describes calibration presence and validity.
    """

    VALID = "valid"  # Calibration exists and within age limit
    STALE = "stale"  # Calibration exists but expired
    MISSING = "missing"  # No calibration found
    FAILED = "failed"  # Calibration attempted but failed
    NOT_REQUIRED = "not_required"  # Workflow doesn't require calibration


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

    # Transfer function requirements (optional)
    minimum_coherence: float | None = None  # For transfer function workflows

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
        result = {
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
        if self.minimum_coherence is not None:
            result["minimum_coherence"] = self.minimum_coherence
        return result

    def validate(self) -> list[str]:
        """Validate contract invariants. Returns list of error messages."""
        errors: list[str] = []
        if self.required_repetitions < 1:
            errors.append("required_repetitions must be >= 1")
        if self.sample_rate_hz < 8000:
            errors.append("sample_rate_hz must be >= 8000")
        if self.fft_window not in ("hann", "hamming", "blackman", "boxcar"):
            errors.append(
                f"fft_window must be hann|hamming|blackman|boxcar, got {self.fft_window}"
            )
        if self.fft_size < 256 or (self.fft_size & (self.fft_size - 1)) != 0:
            errors.append("fft_size must be a power of 2 >= 256")
        if self.min_snr_db < 0:
            errors.append("min_snr_db must be >= 0")
        if self.max_frequency_variance_pct < 0:
            errors.append("max_frequency_variance_pct must be >= 0")
        if self.max_calibration_age_days < 1:
            errors.append("max_calibration_age_days must be >= 1")
        if self.minimum_coherence is not None and not (
            0.0 <= self.minimum_coherence <= 1.0
        ):
            errors.append("minimum_coherence must be in [0.0, 1.0]")
        return errors


@dataclass(frozen=True)
class WorkflowExecutionEvidenceV1:
    """Records what actually happened during a measurement workflow.

    This is a governance artifact for procedural provenance. It captures
    execution state without quality judgment — only observational facts.

    Classification: INSTRUMENT CLASS: MEASUREMENT
    """

    # Required fields (no defaults)
    workflow_id: str
    repetitions_completed: int
    execution_state: str  # WorkflowExecutionState value
    calibration_state: str  # CalibrationState value

    # Optional fields (with defaults)
    repetitions_rejected: int = 0
    capture_geometry_present: bool = False
    workflow_complete: bool = False
    required_repetitions_completed: bool = False
    started_at_utc: str | None = None
    completed_at_utc: str | None = None
    duration_seconds: float | None = None
    epistemic_status: str = "derived"
    schema_version: str = "workflow_execution_evidence_v1"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON export."""
        result = {
            "schema_version": self.schema_version,
            "workflow_id": self.workflow_id,
            "repetitions_completed": self.repetitions_completed,
            "repetitions_rejected": self.repetitions_rejected,
            "execution_state": self.execution_state,
            "calibration_state": self.calibration_state,
            "capture_geometry_present": self.capture_geometry_present,
            "workflow_complete": self.workflow_complete,
            "required_repetitions_completed": self.required_repetitions_completed,
            "epistemic_status": self.epistemic_status,
        }
        if self.started_at_utc is not None:
            result["started_at_utc"] = self.started_at_utc
        if self.completed_at_utc is not None:
            result["completed_at_utc"] = self.completed_at_utc
        if self.duration_seconds is not None:
            result["duration_seconds"] = self.duration_seconds
        return result
