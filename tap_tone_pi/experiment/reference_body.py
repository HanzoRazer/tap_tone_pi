# INSTRUMENT CLASS: MEASUREMENT
"""Reference body contracts for metrology standards (Dev Order 89B).

A reference body is a kept physical specimen used to isolate σ_measurement
from σ_build. By measuring the same body repeatedly, measurement variance
can be separated from build variance.

The reference body is a metrology standard, not merely a flagged measurement.

No advisory semantics. No quality judgments.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class ReferenceBodyRecordV1:
    """A kept reference body for metrology/variance decomposition.

    The reference body is a physical specimen measured repeatedly to
    isolate σ_measurement. It is the maximally repeatable relaxed
    assembled state: complete body with neck attached, no strings,
    no tuning keys.

    Attributes:
        reference_body_id: Unique identifier
        specimen_id: Link to specimen/instrument record
        body_style: Style (e.g., "dreadnought", "OM", "OOO", "jumbo")
        description: Description of the reference body
        state: Physical state (e.g., "unstrung_assembled")
        created_at_utc: When the reference was established
        measurement_ids: Measurements taken on this reference
        wood_species_top: Top wood species
        wood_species_back_sides: Back/sides wood species
        notes: Additional notes
    """

    schema_version: str = field(default="reference_body_record_v1", init=False)
    reference_body_id: str = ""
    specimen_id: str | None = None
    body_style: str = ""
    description: str | None = None
    state: str = "unstrung_assembled"
    created_at_utc: str | None = None
    measurement_ids: tuple[str, ...] = ()
    wood_species_top: str | None = None
    wood_species_back_sides: str | None = None
    notes: str | None = None
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "reference_body_id": self.reference_body_id,
            "body_style": self.body_style,
            "state": self.state,
            "epistemic_status": self.epistemic_status,
        }
        if self.specimen_id is not None:
            d["specimen_id"] = self.specimen_id
        if self.description is not None:
            d["description"] = self.description
        if self.created_at_utc is not None:
            d["created_at_utc"] = self.created_at_utc
        if self.measurement_ids:
            d["measurement_ids"] = list(self.measurement_ids)
        if self.wood_species_top is not None:
            d["wood_species_top"] = self.wood_species_top
        if self.wood_species_back_sides is not None:
            d["wood_species_back_sides"] = self.wood_species_back_sides
        if self.notes is not None:
            d["notes"] = self.notes
        return d

    def with_measurement(self, measurement_id: str) -> "ReferenceBodyRecordV1":
        """Return a new record with the measurement added."""
        if measurement_id in self.measurement_ids:
            return self
        return ReferenceBodyRecordV1(
            reference_body_id=self.reference_body_id,
            specimen_id=self.specimen_id,
            body_style=self.body_style,
            description=self.description,
            state=self.state,
            created_at_utc=self.created_at_utc,
            measurement_ids=(*self.measurement_ids, measurement_id),
            wood_species_top=self.wood_species_top,
            wood_species_back_sides=self.wood_species_back_sides,
            notes=self.notes,
        )


def create_reference_body(
    reference_body_id: str,
    body_style: str,
    *,
    specimen_id: str | None = None,
    description: str | None = None,
    state: str = "unstrung_assembled",
    wood_species_top: str | None = None,
    wood_species_back_sides: str | None = None,
    notes: str | None = None,
    timestamp_utc: str | None = None,
) -> ReferenceBodyRecordV1:
    """Create a reference body record.

    Args:
        reference_body_id: Unique identifier
        body_style: Style (e.g., "dreadnought", "OM")
        specimen_id: Link to specimen/instrument record
        description: Description
        state: Physical state
        wood_species_top: Top wood species
        wood_species_back_sides: Back/sides wood species
        notes: Additional notes
        timestamp_utc: Creation timestamp (defaults to now)

    Returns:
        ReferenceBodyRecordV1 instance
    """
    if timestamp_utc is None:
        timestamp_utc = datetime.now(timezone.utc).isoformat()

    return ReferenceBodyRecordV1(
        reference_body_id=reference_body_id,
        specimen_id=specimen_id,
        body_style=body_style,
        description=description,
        state=state,
        created_at_utc=timestamp_utc,
        wood_species_top=wood_species_top,
        wood_species_back_sides=wood_species_back_sides,
        notes=notes,
    )
