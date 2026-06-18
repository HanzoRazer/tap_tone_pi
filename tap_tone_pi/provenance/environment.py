# INSTRUMENT CLASS: MEASUREMENT
"""Environmental provenance (Dev Order 88).

Environment records capture the physical conditions under which measurements
were taken. Environmental factors affect acoustic measurements significantly:
- Temperature affects wood stiffness and resonant frequencies
- Humidity affects wood moisture content and damping
- Ambient noise affects signal-to-noise ratio

Environment records are observational facts, not quality judgments.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EnvironmentRecordV1:
    """Records environmental conditions during measurement.

    Captures temperature, humidity, room identification, and ambient noise
    level as first-class provenance entities.

    Classification: INSTRUMENT CLASS: MEASUREMENT
    """

    environment_id: str
    recorded_at_utc: str

    temperature_c: float | None = None
    humidity_pct: float | None = None
    room_id: str | None = None
    ambient_noise_dbfs: float | None = None

    notes: str | None = None

    epistemic_status: str = "derived"
    schema_version: str = "environment_record_v1"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON export."""
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "environment_id": self.environment_id,
            "recorded_at_utc": self.recorded_at_utc,
            "epistemic_status": self.epistemic_status,
        }
        if self.temperature_c is not None:
            result["temperature_c"] = self.temperature_c
        if self.humidity_pct is not None:
            result["humidity_pct"] = self.humidity_pct
        if self.room_id is not None:
            result["room_id"] = self.room_id
        if self.ambient_noise_dbfs is not None:
            result["ambient_noise_dbfs"] = self.ambient_noise_dbfs
        if self.notes is not None:
            result["notes"] = self.notes
        return result


__all__ = [
    "EnvironmentRecordV1",
]
