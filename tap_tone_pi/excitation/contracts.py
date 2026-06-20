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
