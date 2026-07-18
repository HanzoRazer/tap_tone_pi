# INSTRUMENT CLASS: MEASUREMENT
"""Excitation-response pair contracts (DO-91).

ExcitationResponsePairV1 is the provenance pair that captures both
the excitation event and the response measurement together, enabling
transfer function computation with full traceability.

No advisory semantics. No quality judgments.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(frozen=True)
class ExcitationResponsePairV1:
    """Provenance pair: excitation event + response capture.

    This contract bundles the excitation and response together,
    providing a single artifact that captures the paired measurement
    for transfer function computation.

    Attributes:
        pair_id: Unique identifier for this pair
        excitation_id: ID of the excitation contract
        excitation_record_id: ID of the emission record (tone/sweep/stepped)
        response_measurement_id: ID of the response measurement
        response_wav_path: Path to response WAV file
        excitation_type: Type of excitation (tone/sweep/stepped)
        frequency_hz: Frequency for tone (None for sweep/stepped)
        start_frequency_hz: Start frequency for sweep/stepped
        stop_frequency_hz: Stop frequency for sweep/stepped
        duration_s: Duration of excitation
        sample_rate_hz: Sample rate
        captured_at_utc: Timestamp of capture
        source_characterization_id: Link to source calibration
        environment_temp_c: Environment temperature
        environment_rh_pct: Environment relative humidity
    """

    schema_version: str = field(default="excitation_response_pair_v1", init=False)
    pair_id: str = ""
    excitation_id: str = ""
    excitation_record_id: str = ""
    response_measurement_id: str = ""
    response_wav_path: Optional[str] = None
    excitation_type: str = "tone"
    frequency_hz: Optional[float] = None
    start_frequency_hz: Optional[float] = None
    stop_frequency_hz: Optional[float] = None
    duration_s: float = 1.0
    sample_rate_hz: int = 48000
    captured_at_utc: str = ""
    source_characterization_id: Optional[str] = None
    environment_temp_c: Optional[float] = None
    environment_rh_pct: Optional[float] = None
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "pair_id": self.pair_id,
            "excitation_id": self.excitation_id,
            "excitation_record_id": self.excitation_record_id,
            "response_measurement_id": self.response_measurement_id,
            "excitation_type": self.excitation_type,
            "duration_s": self.duration_s,
            "sample_rate_hz": self.sample_rate_hz,
            "captured_at_utc": self.captured_at_utc,
            "epistemic_status": self.epistemic_status,
        }

        if self.response_wav_path is not None:
            d["response_wav_path"] = self.response_wav_path
        if self.frequency_hz is not None:
            d["frequency_hz"] = self.frequency_hz
        if self.start_frequency_hz is not None:
            d["start_frequency_hz"] = self.start_frequency_hz
        if self.stop_frequency_hz is not None:
            d["stop_frequency_hz"] = self.stop_frequency_hz
        if self.source_characterization_id is not None:
            d["source_characterization_id"] = self.source_characterization_id
        if self.environment_temp_c is not None:
            d["environment_temp_c"] = self.environment_temp_c
        if self.environment_rh_pct is not None:
            d["environment_rh_pct"] = self.environment_rh_pct

        return d


def create_excitation_response_pair(
    pair_id: str,
    excitation_id: str,
    excitation_record_id: str,
    response_measurement_id: str,
    excitation_type: str,
    duration_s: float,
    sample_rate_hz: int = 48000,
    *,
    response_wav_path: Optional[str] = None,
    frequency_hz: Optional[float] = None,
    start_frequency_hz: Optional[float] = None,
    stop_frequency_hz: Optional[float] = None,
    source_characterization_id: Optional[str] = None,
    environment_temp_c: Optional[float] = None,
    environment_rh_pct: Optional[float] = None,
    captured_at_utc: Optional[str] = None,
) -> ExcitationResponsePairV1:
    """Create an excitation-response pair.

    Args:
        pair_id: Unique identifier
        excitation_id: ID of the excitation contract
        excitation_record_id: ID of the emission record
        response_measurement_id: ID of the response measurement
        excitation_type: Type of excitation
        duration_s: Duration of excitation
        sample_rate_hz: Sample rate
        response_wav_path: Path to response WAV
        frequency_hz: Frequency for tone
        start_frequency_hz: Start frequency for sweep/stepped
        stop_frequency_hz: Stop frequency for sweep/stepped
        source_characterization_id: Source calibration ID
        environment_temp_c: Temperature
        environment_rh_pct: Relative humidity
        captured_at_utc: Capture timestamp (defaults to now)

    Returns:
        ExcitationResponsePairV1 instance
    """
    if captured_at_utc is None:
        captured_at_utc = datetime.now(timezone.utc).isoformat()

    return ExcitationResponsePairV1(
        pair_id=pair_id,
        excitation_id=excitation_id,
        excitation_record_id=excitation_record_id,
        response_measurement_id=response_measurement_id,
        response_wav_path=response_wav_path,
        excitation_type=excitation_type,
        frequency_hz=frequency_hz,
        start_frequency_hz=start_frequency_hz,
        stop_frequency_hz=stop_frequency_hz,
        duration_s=duration_s,
        sample_rate_hz=sample_rate_hz,
        captured_at_utc=captured_at_utc,
        source_characterization_id=source_characterization_id,
        environment_temp_c=environment_temp_c,
        environment_rh_pct=environment_rh_pct,
    )
