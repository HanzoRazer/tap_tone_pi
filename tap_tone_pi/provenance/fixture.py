# INSTRUMENT CLASS: MEASUREMENT
"""Fixture provenance (Dev Order 88).

Fixture records capture the physical setup used during measurements:
- Support condition (free, clamped, supported)
- Fixture identification
- Positioning details

Fixture configuration significantly affects measured frequencies and mode shapes.
Free-free conditions differ from clamped conditions; consistent fixtures enable
repeatable measurements.

Fixture records are observational facts, not quality judgments.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FixtureRecordV1:
    """Records fixture configuration during measurement.

    Captures support condition, fixture identification, and positioning
    as first-class provenance entities.

    Classification: INSTRUMENT CLASS: MEASUREMENT
    """

    fixture_id: str

    support_condition: str | None = None  # "free", "clamped", "supported", "suspended"
    fixture_type: str | None = None  # "foam_blocks", "rubber_bands", "clamp_jig", etc.
    description: str | None = None

    mic_position: str | None = None  # "center", "off-center", "roving", etc.
    tap_position: str | None = None  # "center", "antinode", "grid", etc.
    excitation_method: str | None = None  # "tap", "impulse_hammer", "shaker", etc.

    notes: str | None = None

    epistemic_status: str = "derived"
    schema_version: str = "fixture_record_v1"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON export."""
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "fixture_id": self.fixture_id,
            "epistemic_status": self.epistemic_status,
        }
        if self.support_condition is not None:
            result["support_condition"] = self.support_condition
        if self.fixture_type is not None:
            result["fixture_type"] = self.fixture_type
        if self.description is not None:
            result["description"] = self.description
        if self.mic_position is not None:
            result["mic_position"] = self.mic_position
        if self.tap_position is not None:
            result["tap_position"] = self.tap_position
        if self.excitation_method is not None:
            result["excitation_method"] = self.excitation_method
        if self.notes is not None:
            result["notes"] = self.notes
        return result


__all__ = [
    "FixtureRecordV1",
]
