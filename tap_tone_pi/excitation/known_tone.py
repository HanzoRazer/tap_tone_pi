# INSTRUMENT CLASS: MEASUREMENT
"""Known tone record and emission (DO-90).

KnownToneRecordV1 is the provenance artifact for a single emitted tone event.
emit_tone() generates and plays a tone, returning the provenance record.

No advisory semantics. No tone quality judgments.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np

from tap_tone_pi.excitation.amplitude import (
    AmplitudeGuardrail,
    validate_amplitude,
    DEFAULT_AMPLITUDE,
)
from tap_tone_pi.signal_gen.generators import generate_sine


@dataclass(frozen=True)
class KnownToneRecordV1:
    """Provenance artifact for a single emitted tone event.

    Records what tone was emitted, when, and on what device.
    This is evidence that a known excitation occurred.

    Attributes:
        record_id: Unique identifier for this emission record
        excitation_id: Link to the excitation contract
        frequency_hz: Frequency of the emitted tone
        duration_s: Duration of emission
        amplitude: Peak amplitude used
        sample_rate_hz: Sample rate
        output_device_id: Output device identifier
        emitted_at_utc: Timestamp of emission
        source_characterization_id: Link to source characterization
    """

    schema_version: str = field(default="known_tone_record_v1", init=False)
    record_id: str = ""
    excitation_id: Optional[str] = None
    frequency_hz: float = 440.0
    duration_s: float = 1.0
    amplitude: float = DEFAULT_AMPLITUDE
    sample_rate_hz: int = 48000
    output_device_id: Optional[str] = None
    emitted_at_utc: str = ""
    source_characterization_id: Optional[str] = None
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "record_id": self.record_id,
            "frequency_hz": self.frequency_hz,
            "duration_s": self.duration_s,
            "amplitude": self.amplitude,
            "sample_rate_hz": self.sample_rate_hz,
            "emitted_at_utc": self.emitted_at_utc,
            "epistemic_status": self.epistemic_status,
        }

        if self.excitation_id is not None:
            d["excitation_id"] = self.excitation_id
        if self.output_device_id is not None:
            d["output_device_id"] = self.output_device_id
        if self.source_characterization_id is not None:
            d["source_characterization_id"] = self.source_characterization_id

        return d


def create_known_tone_record(
    record_id: str,
    frequency_hz: float,
    duration_s: float,
    amplitude: float,
    sample_rate_hz: int = 48000,
    *,
    excitation_id: Optional[str] = None,
    output_device_id: Optional[str] = None,
    source_characterization_id: Optional[str] = None,
    emitted_at_utc: Optional[str] = None,
) -> KnownToneRecordV1:
    """Create a known tone record.

    Args:
        record_id: Unique identifier
        frequency_hz: Frequency of the tone
        duration_s: Duration of emission
        amplitude: Peak amplitude
        sample_rate_hz: Sample rate
        excitation_id: Link to excitation contract
        output_device_id: Output device identifier
        source_characterization_id: Link to source characterization
        emitted_at_utc: Emission timestamp (defaults to now)

    Returns:
        KnownToneRecordV1 instance
    """
    if emitted_at_utc is None:
        emitted_at_utc = datetime.now(timezone.utc).isoformat()

    return KnownToneRecordV1(
        record_id=record_id,
        excitation_id=excitation_id,
        frequency_hz=frequency_hz,
        duration_s=duration_s,
        amplitude=amplitude,
        sample_rate_hz=sample_rate_hz,
        output_device_id=output_device_id,
        emitted_at_utc=emitted_at_utc,
        source_characterization_id=source_characterization_id,
    )


def emit_tone(
    frequency_hz: float,
    duration_s: float = 1.0,
    amplitude: float = DEFAULT_AMPLITUDE,
    sample_rate_hz: int = 48000,
    *,
    output_device_id: Optional[str] = None,
    excitation_id: Optional[str] = None,
    source_characterization_id: Optional[str] = None,
    record_id: Optional[str] = None,
    blocking: bool = True,
) -> KnownToneRecordV1:
    """Generate and emit a tone, returning provenance record.

    Args:
        frequency_hz: Frequency of the tone
        duration_s: Duration of emission
        amplitude: Peak amplitude (0.0 to 1.0)
        sample_rate_hz: Sample rate
        output_device_id: Output device identifier (None = default)
        excitation_id: Link to excitation contract
        source_characterization_id: Link to source characterization
        record_id: Unique identifier for the record (auto-generated if None)
        blocking: If True, wait for playback to complete

    Returns:
        KnownToneRecordV1 with emission provenance

    Raises:
        ValueError: If amplitude exceeds guardrail limits
    """
    import sounddevice as sd
    import uuid

    # Validate amplitude
    validation = validate_amplitude(amplitude)
    if validation.guardrail == AmplitudeGuardrail.REJECTED:
        raise ValueError(validation.message)

    # Generate record ID if not provided
    if record_id is None:
        record_id = f"tone_{uuid.uuid4().hex[:8]}"

    # Get device ID string
    if output_device_id is None:
        device_info = sd.query_devices(sd.default.device[1], "output")
        output_device_id = str(device_info.get("name", "default"))

    # Generate the tone
    signal = generate_sine(
        frequency_hz=frequency_hz,
        duration_s=duration_s,
        sample_rate=sample_rate_hz,
        amplitude=amplitude,
    )

    # Record emission timestamp
    emitted_at_utc = datetime.now(timezone.utc).isoformat()

    # Play the tone
    sd.play(signal.astype(np.float32), samplerate=sample_rate_hz)

    if blocking:
        sd.wait()

    # Create and return provenance record
    return KnownToneRecordV1(
        record_id=record_id,
        excitation_id=excitation_id,
        frequency_hz=frequency_hz,
        duration_s=duration_s,
        amplitude=amplitude,
        sample_rate_hz=sample_rate_hz,
        output_device_id=output_device_id,
        emitted_at_utc=emitted_at_utc,
        source_characterization_id=source_characterization_id,
    )
