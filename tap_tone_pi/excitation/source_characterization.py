# INSTRUMENT CLASS: MEASUREMENT
"""Source characterization record (DO-90).

SourceCharacterizationRecordV1 records the emit chain:
- DAC/output device
- Amplifier/transducer/speaker
- Reference microphone or loopback method
- Measured frequency response summary
- Harmonic distortion summary (if available)

This is output-side calibration for controlled excitation.

No advisory semantics. No quality judgments.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple


@dataclass(frozen=True)
class FrequencyResponsePointV1:
    """Single point in a frequency response measurement."""

    frequency_hz: float
    magnitude_db: float
    phase_deg: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "frequency_hz": self.frequency_hz,
            "magnitude_db": self.magnitude_db,
        }
        if self.phase_deg is not None:
            d["phase_deg"] = self.phase_deg
        return d


@dataclass(frozen=True)
class SourceCharacterizationRecordV1:
    """Output-side calibration record for excitation source.

    Records the characteristics of the emit chain so that
    excitation can be compensated or its limitations understood.

    Attributes:
        characterization_id: Unique identifier
        output_device_name: Name of the DAC/output device
        amplifier_model: Amplifier/driver model (if applicable)
        transducer_model: Transducer/speaker model
        measurement_method: How characterization was performed
        reference_microphone_id: Microphone used for measurement
        frequency_response: List of frequency response points
        usable_frequency_range_hz: Tuple of (low, high) usable frequencies
        thd_percent: Total harmonic distortion percentage (if measured)
        characterized_at_utc: Timestamp of characterization
        notes: Additional notes
    """

    schema_version: str = field(
        default="source_characterization_record_v1", init=False
    )
    characterization_id: str = ""
    output_device_name: str = ""
    amplifier_model: Optional[str] = None
    transducer_model: Optional[str] = None
    measurement_method: str = ""
    reference_microphone_id: Optional[str] = None
    frequency_response: Tuple[FrequencyResponsePointV1, ...] = ()
    usable_frequency_range_hz: Optional[Tuple[float, float]] = None
    thd_percent: Optional[float] = None
    characterized_at_utc: str = ""
    notes: Optional[str] = None
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "characterization_id": self.characterization_id,
            "output_device_name": self.output_device_name,
            "measurement_method": self.measurement_method,
            "characterized_at_utc": self.characterized_at_utc,
            "epistemic_status": self.epistemic_status,
        }

        if self.amplifier_model is not None:
            d["amplifier_model"] = self.amplifier_model
        if self.transducer_model is not None:
            d["transducer_model"] = self.transducer_model
        if self.reference_microphone_id is not None:
            d["reference_microphone_id"] = self.reference_microphone_id
        if self.frequency_response:
            d["frequency_response"] = [p.to_dict() for p in self.frequency_response]
        if self.usable_frequency_range_hz is not None:
            d["usable_frequency_range_hz"] = list(self.usable_frequency_range_hz)
        if self.thd_percent is not None:
            d["thd_percent"] = self.thd_percent
        if self.notes is not None:
            d["notes"] = self.notes

        return d


def create_source_characterization(
    characterization_id: str,
    output_device_name: str,
    measurement_method: str,
    *,
    amplifier_model: Optional[str] = None,
    transducer_model: Optional[str] = None,
    reference_microphone_id: Optional[str] = None,
    frequency_response: Optional[List[Tuple[float, float]]] = None,
    usable_frequency_range_hz: Optional[Tuple[float, float]] = None,
    thd_percent: Optional[float] = None,
    notes: Optional[str] = None,
    characterized_at_utc: Optional[str] = None,
) -> SourceCharacterizationRecordV1:
    """Create a source characterization record.

    Args:
        characterization_id: Unique identifier
        output_device_name: Name of output device
        measurement_method: How characterization was performed
        amplifier_model: Amplifier model
        transducer_model: Transducer/speaker model
        reference_microphone_id: Microphone used for measurement
        frequency_response: List of (frequency_hz, magnitude_db) tuples
        usable_frequency_range_hz: Tuple of (low, high) usable frequencies
        thd_percent: Total harmonic distortion percentage
        notes: Additional notes
        characterized_at_utc: Timestamp (defaults to now)

    Returns:
        SourceCharacterizationRecordV1 instance
    """
    if characterized_at_utc is None:
        characterized_at_utc = datetime.now(timezone.utc).isoformat()

    # Convert frequency response tuples to dataclass instances
    fr_points: Tuple[FrequencyResponsePointV1, ...] = ()
    if frequency_response:
        fr_points = tuple(
            FrequencyResponsePointV1(frequency_hz=f, magnitude_db=m)
            for f, m in frequency_response
        )

    return SourceCharacterizationRecordV1(
        characterization_id=characterization_id,
        output_device_name=output_device_name,
        amplifier_model=amplifier_model,
        transducer_model=transducer_model,
        measurement_method=measurement_method,
        reference_microphone_id=reference_microphone_id,
        frequency_response=fr_points,
        usable_frequency_range_hz=usable_frequency_range_hz,
        thd_percent=thd_percent,
        characterized_at_utc=characterized_at_utc,
        notes=notes,
    )
