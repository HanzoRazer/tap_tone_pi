# INSTRUMENT CLASS: MEASUREMENT
"""Excitation-measurement linkage contracts (DO-91).

ExcitationMeasurementLinkV1 links an excitation event to a measurement,
enabling provenance tracing from response back to known excitation.

No advisory semantics. No quality judgments.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(frozen=True)
class ExcitationMeasurementLinkV1:
    """Links an excitation event to a measurement.

    This contract traces provenance: which excitation produced which
    measurement response. It enables transfer function computation
    with full lineage.

    Attributes:
        link_id: Unique identifier for this link
        measurement_id: ID of the response measurement
        excitation_id: ID of the excitation contract
        known_tone_record_id: ID of tone emission record (if tone)
        sweep_record_id: ID of sweep emission record (if sweep)
        stepped_record_id: ID of stepped emission record (if stepped)
        source_characterization_id: ID of source calibration record
        linked_at_utc: Timestamp when link was established
    """

    schema_version: str = field(default="excitation_measurement_link_v1", init=False)
    link_id: str = ""
    measurement_id: str = ""
    excitation_id: str = ""
    known_tone_record_id: Optional[str] = None
    sweep_record_id: Optional[str] = None
    stepped_record_id: Optional[str] = None
    source_characterization_id: Optional[str] = None
    linked_at_utc: str = ""
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "link_id": self.link_id,
            "measurement_id": self.measurement_id,
            "excitation_id": self.excitation_id,
            "linked_at_utc": self.linked_at_utc,
            "epistemic_status": self.epistemic_status,
        }

        if self.known_tone_record_id is not None:
            d["known_tone_record_id"] = self.known_tone_record_id
        if self.sweep_record_id is not None:
            d["sweep_record_id"] = self.sweep_record_id
        if self.stepped_record_id is not None:
            d["stepped_record_id"] = self.stepped_record_id
        if self.source_characterization_id is not None:
            d["source_characterization_id"] = self.source_characterization_id

        return d


def create_excitation_measurement_link(
    link_id: str,
    measurement_id: str,
    excitation_id: str,
    *,
    known_tone_record_id: Optional[str] = None,
    sweep_record_id: Optional[str] = None,
    stepped_record_id: Optional[str] = None,
    source_characterization_id: Optional[str] = None,
    linked_at_utc: Optional[str] = None,
) -> ExcitationMeasurementLinkV1:
    """Create an excitation-measurement link.

    Args:
        link_id: Unique identifier
        measurement_id: ID of the response measurement
        excitation_id: ID of the excitation contract
        known_tone_record_id: ID of tone emission record
        sweep_record_id: ID of sweep emission record
        stepped_record_id: ID of stepped emission record
        source_characterization_id: ID of source calibration
        linked_at_utc: Timestamp (defaults to now)

    Returns:
        ExcitationMeasurementLinkV1 instance
    """
    if linked_at_utc is None:
        linked_at_utc = datetime.now(timezone.utc).isoformat()

    return ExcitationMeasurementLinkV1(
        link_id=link_id,
        measurement_id=measurement_id,
        excitation_id=excitation_id,
        known_tone_record_id=known_tone_record_id,
        sweep_record_id=sweep_record_id,
        stepped_record_id=stepped_record_id,
        source_characterization_id=source_characterization_id,
        linked_at_utc=linked_at_utc,
    )
