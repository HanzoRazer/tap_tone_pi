# INSTRUMENT CLASS: MEASUREMENT
"""Excitation contract definitions (DO-90).

ExcitationContractV1 is the declarative specification for controlled excitation.
It describes what excitation will be performed, not the measured response.

No advisory semantics. No tone quality judgments.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ExcitationType(Enum):
    """Type of excitation signal."""

    TONE = "tone"
    STEPPED = "stepped"
    SWEEP = "sweep"


class WaveformType(Enum):
    """Waveform shape."""

    SINE = "sine"


@dataclass(frozen=True)
class ExcitationContractV1:
    """Declarative specification for controlled excitation.

    This contract defines what excitation will be performed.
    It does not store the measured response.

    Attributes:
        excitation_id: Unique identifier for this excitation specification
        excitation_type: Type of excitation (tone, stepped, sweep)
        waveform: Waveform shape (sine initially)
        frequency_hz: Frequency for tone excitation
        start_frequency_hz: Starting frequency for stepped/sweep
        stop_frequency_hz: Ending frequency for stepped/sweep
        step_frequency_hz: Step size for stepped excitation
        duration_s: Duration of excitation
        amplitude: Peak amplitude (0.0 to 1.0)
        sample_rate_hz: Sample rate
        output_device_id: Identifier for output device
        source_characterization_id: Link to source characterization record
    """

    schema_version: str = field(default="excitation_contract_v1", init=False)
    excitation_id: str = ""
    excitation_type: ExcitationType = ExcitationType.TONE
    waveform: WaveformType = WaveformType.SINE

    # Tone parameters
    frequency_hz: Optional[float] = None

    # Stepped/sweep parameters
    start_frequency_hz: Optional[float] = None
    stop_frequency_hz: Optional[float] = None
    step_frequency_hz: Optional[float] = None

    # Common parameters
    duration_s: float = 1.0
    amplitude: float = 0.2
    sample_rate_hz: int = 48000

    # Device linkage
    output_device_id: Optional[str] = None
    source_characterization_id: Optional[str] = None

    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "excitation_id": self.excitation_id,
            "excitation_type": self.excitation_type.value,
            "waveform": self.waveform.value,
            "duration_s": self.duration_s,
            "amplitude": self.amplitude,
            "sample_rate_hz": self.sample_rate_hz,
            "epistemic_status": self.epistemic_status,
        }

        if self.frequency_hz is not None:
            d["frequency_hz"] = self.frequency_hz
        if self.start_frequency_hz is not None:
            d["start_frequency_hz"] = self.start_frequency_hz
        if self.stop_frequency_hz is not None:
            d["stop_frequency_hz"] = self.stop_frequency_hz
        if self.step_frequency_hz is not None:
            d["step_frequency_hz"] = self.step_frequency_hz
        if self.output_device_id is not None:
            d["output_device_id"] = self.output_device_id
        if self.source_characterization_id is not None:
            d["source_characterization_id"] = self.source_characterization_id

        return d


class SweepType(Enum):
    """Type of frequency sweep."""

    LINEAR = "linear"
    LOGARITHMIC = "logarithmic"


@dataclass(frozen=True)
class SteppedExcitationRecordV1:
    """Provenance artifact for a stepped frequency excitation event.

    Records the parameters and timing of a stepped frequency excitation.
    Each step dwells at a fixed frequency before transitioning to the next.

    Attributes:
        record_id: Unique identifier for this emission record
        excitation_id: Link to the excitation contract
        frequencies_hz: Tuple of stepped frequencies
        step_count: Number of frequency steps
        dwell_time_s: Time at each frequency step
        transition_time_s: Ramp time between steps
        amplitude: Peak amplitude used
        total_duration_s: Total duration of emission
        sample_rate_hz: Sample rate
        output_device_id: Output device identifier
        emitted_at_utc: Timestamp of emission
        source_characterization_id: Link to source characterization
        waveform_sha256: SHA-256 hash of generated waveform
    """

    schema_version: str = field(default="stepped_excitation_record_v1", init=False)
    record_id: str = ""
    excitation_id: Optional[str] = None
    frequencies_hz: tuple[float, ...] = field(default_factory=tuple)
    step_count: int = 0
    dwell_time_s: float = 1.0
    transition_time_s: float = 0.1
    amplitude: float = 0.2
    total_duration_s: float = 0.0
    sample_rate_hz: int = 48000
    output_device_id: Optional[str] = None
    emitted_at_utc: str = ""
    source_characterization_id: Optional[str] = None
    waveform_sha256: Optional[str] = None
    epistemic_status: str = field(default="observed", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "record_id": self.record_id,
            "frequencies_hz": list(self.frequencies_hz),
            "step_count": self.step_count,
            "dwell_time_s": self.dwell_time_s,
            "transition_time_s": self.transition_time_s,
            "amplitude": self.amplitude,
            "total_duration_s": self.total_duration_s,
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
        if self.waveform_sha256 is not None:
            d["waveform_sha256"] = self.waveform_sha256

        return d


@dataclass(frozen=True)
class SweepExcitationRecordV1:
    """Provenance artifact for a frequency sweep excitation event.

    Records the parameters and timing of a frequency sweep excitation.

    Attributes:
        record_id: Unique identifier for this emission record
        excitation_id: Link to the excitation contract
        start_frequency_hz: Starting frequency
        stop_frequency_hz: Ending frequency
        sweep_type: Type of sweep (linear or logarithmic)
        duration_s: Duration of sweep
        amplitude: Peak amplitude used
        sample_rate_hz: Sample rate
        output_device_id: Output device identifier
        emitted_at_utc: Timestamp of emission
        source_characterization_id: Link to source characterization
        waveform_sha256: SHA-256 hash of generated waveform
    """

    schema_version: str = field(default="sweep_excitation_record_v1", init=False)
    record_id: str = ""
    excitation_id: Optional[str] = None
    start_frequency_hz: float = 20.0
    stop_frequency_hz: float = 20000.0
    sweep_type: str = "logarithmic"
    duration_s: float = 5.0
    amplitude: float = 0.2
    sample_rate_hz: int = 48000
    output_device_id: Optional[str] = None
    emitted_at_utc: str = ""
    source_characterization_id: Optional[str] = None
    waveform_sha256: Optional[str] = None
    epistemic_status: str = field(default="observed", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "record_id": self.record_id,
            "start_frequency_hz": self.start_frequency_hz,
            "stop_frequency_hz": self.stop_frequency_hz,
            "sweep_type": self.sweep_type,
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
        if self.waveform_sha256 is not None:
            d["waveform_sha256"] = self.waveform_sha256

        return d


def create_excitation_contract(
    excitation_id: str,
    excitation_type: ExcitationType | str,
    *,
    waveform: WaveformType | str = WaveformType.SINE,
    frequency_hz: Optional[float] = None,
    start_frequency_hz: Optional[float] = None,
    stop_frequency_hz: Optional[float] = None,
    step_frequency_hz: Optional[float] = None,
    duration_s: float = 1.0,
    amplitude: float = 0.2,
    sample_rate_hz: int = 48000,
    output_device_id: Optional[str] = None,
    source_characterization_id: Optional[str] = None,
) -> ExcitationContractV1:
    """Create an excitation contract.

    Args:
        excitation_id: Unique identifier
        excitation_type: Type of excitation
        waveform: Waveform shape
        frequency_hz: Frequency for tone excitation
        start_frequency_hz: Starting frequency for stepped/sweep
        stop_frequency_hz: Ending frequency for stepped/sweep
        step_frequency_hz: Step size for stepped excitation
        duration_s: Duration
        amplitude: Peak amplitude
        sample_rate_hz: Sample rate
        output_device_id: Output device identifier
        source_characterization_id: Link to source characterization

    Returns:
        ExcitationContractV1 instance
    """
    if isinstance(excitation_type, str):
        excitation_type = ExcitationType(excitation_type)
    if isinstance(waveform, str):
        waveform = WaveformType(waveform)

    # Validate required parameters for each type
    if excitation_type == ExcitationType.TONE:
        if frequency_hz is None:
            raise ValueError("frequency_hz required for tone excitation")
    elif excitation_type in (ExcitationType.STEPPED, ExcitationType.SWEEP):
        if start_frequency_hz is None or stop_frequency_hz is None:
            raise ValueError(
                "start_frequency_hz and stop_frequency_hz required for stepped/sweep"
            )
        if excitation_type == ExcitationType.STEPPED and step_frequency_hz is None:
            raise ValueError("step_frequency_hz required for stepped excitation")

    return ExcitationContractV1(
        excitation_id=excitation_id,
        excitation_type=excitation_type,
        waveform=waveform,
        frequency_hz=frequency_hz,
        start_frequency_hz=start_frequency_hz,
        stop_frequency_hz=stop_frequency_hz,
        step_frequency_hz=step_frequency_hz,
        duration_s=duration_s,
        amplitude=amplitude,
        sample_rate_hz=sample_rate_hz,
        output_device_id=output_device_id,
        source_characterization_id=source_characterization_id,
    )


def create_stepped_excitation_record(
    record_id: str,
    frequencies_hz: list[float] | tuple[float, ...],
    dwell_time_s: float,
    amplitude: float,
    *,
    transition_time_s: float = 0.1,
    sample_rate_hz: int = 48000,
    excitation_id: Optional[str] = None,
    output_device_id: Optional[str] = None,
    source_characterization_id: Optional[str] = None,
    waveform_sha256: Optional[str] = None,
    emitted_at_utc: Optional[str] = None,
) -> SteppedExcitationRecordV1:
    """Create a stepped excitation record.

    Args:
        record_id: Unique identifier
        frequencies_hz: List of stepped frequencies
        dwell_time_s: Time at each frequency step
        amplitude: Peak amplitude
        transition_time_s: Ramp time between steps
        sample_rate_hz: Sample rate
        excitation_id: Link to excitation contract
        output_device_id: Output device identifier
        source_characterization_id: Link to source characterization
        waveform_sha256: SHA-256 hash of waveform
        emitted_at_utc: Emission timestamp (defaults to now)

    Returns:
        SteppedExcitationRecordV1 instance
    """
    from datetime import datetime, timezone

    if emitted_at_utc is None:
        emitted_at_utc = datetime.now(timezone.utc).isoformat()

    freqs = tuple(frequencies_hz)
    step_count = len(freqs)
    total_duration_s = step_count * dwell_time_s + (step_count - 1) * transition_time_s

    return SteppedExcitationRecordV1(
        record_id=record_id,
        excitation_id=excitation_id,
        frequencies_hz=freqs,
        step_count=step_count,
        dwell_time_s=dwell_time_s,
        transition_time_s=transition_time_s,
        amplitude=amplitude,
        total_duration_s=total_duration_s,
        sample_rate_hz=sample_rate_hz,
        output_device_id=output_device_id,
        emitted_at_utc=emitted_at_utc,
        source_characterization_id=source_characterization_id,
        waveform_sha256=waveform_sha256,
    )


def create_sweep_excitation_record(
    record_id: str,
    start_frequency_hz: float,
    stop_frequency_hz: float,
    duration_s: float,
    amplitude: float,
    *,
    sweep_type: str = "logarithmic",
    sample_rate_hz: int = 48000,
    excitation_id: Optional[str] = None,
    output_device_id: Optional[str] = None,
    source_characterization_id: Optional[str] = None,
    waveform_sha256: Optional[str] = None,
    emitted_at_utc: Optional[str] = None,
) -> SweepExcitationRecordV1:
    """Create a sweep excitation record.

    Args:
        record_id: Unique identifier
        start_frequency_hz: Starting frequency
        stop_frequency_hz: Ending frequency
        duration_s: Duration of sweep
        amplitude: Peak amplitude
        sweep_type: Type of sweep ("linear" or "logarithmic")
        sample_rate_hz: Sample rate
        excitation_id: Link to excitation contract
        output_device_id: Output device identifier
        source_characterization_id: Link to source characterization
        waveform_sha256: SHA-256 hash of waveform
        emitted_at_utc: Emission timestamp (defaults to now)

    Returns:
        SweepExcitationRecordV1 instance
    """
    from datetime import datetime, timezone

    if emitted_at_utc is None:
        emitted_at_utc = datetime.now(timezone.utc).isoformat()

    return SweepExcitationRecordV1(
        record_id=record_id,
        excitation_id=excitation_id,
        start_frequency_hz=start_frequency_hz,
        stop_frequency_hz=stop_frequency_hz,
        sweep_type=sweep_type,
        duration_s=duration_s,
        amplitude=amplitude,
        sample_rate_hz=sample_rate_hz,
        output_device_id=output_device_id,
        emitted_at_utc=emitted_at_utc,
        source_characterization_id=source_characterization_id,
        waveform_sha256=waveform_sha256,
    )
