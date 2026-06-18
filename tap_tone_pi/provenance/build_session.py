# INSTRUMENT CLASS: MEASUREMENT
"""Build session provenance (Dev Order 88).

A build session represents the complete measurement lifecycle of a specimen
(instrument, top, back, brace set, etc.) during construction. It serves as
the top-level container linking all experimental campaigns, revisions, and
measurements taken during the build process.

Build sessions are containers for lineage, not evaluators of build quality.
They record what was built and measured, not whether it was good.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BuildSessionV1:
    """Container for all measurements during construction of one specimen.

    A build session represents the instrument/specimen lifecycle, linking
    all experimental campaigns conducted during its construction.

    Classification: INSTRUMENT CLASS: MEASUREMENT
    """

    build_session_id: str
    specimen_id: str

    specimen_type: str | None = None  # "guitar_top", "back", "brace_set", etc.
    description: str | None = None
    created_at_utc: str | None = None
    completed_at_utc: str | None = None

    campaign_ids: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)

    notes: str | None = None

    epistemic_status: str = "derived"
    schema_version: str = "build_session_v1"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON export."""
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "build_session_id": self.build_session_id,
            "specimen_id": self.specimen_id,
            "epistemic_status": self.epistemic_status,
        }
        if self.specimen_type is not None:
            result["specimen_type"] = self.specimen_type
        if self.description is not None:
            result["description"] = self.description
        if self.created_at_utc is not None:
            result["created_at_utc"] = self.created_at_utc
        if self.completed_at_utc is not None:
            result["completed_at_utc"] = self.completed_at_utc
        if self.campaign_ids:
            result["campaign_ids"] = list(self.campaign_ids)
        if self.tags:
            result["tags"] = list(self.tags)
        if self.notes is not None:
            result["notes"] = self.notes
        return result

    def with_campaign(self, campaign_id: str) -> BuildSessionV1:
        """Return a new build session with the campaign added."""
        if campaign_id in self.campaign_ids:
            return self
        return BuildSessionV1(
            build_session_id=self.build_session_id,
            specimen_id=self.specimen_id,
            specimen_type=self.specimen_type,
            description=self.description,
            created_at_utc=self.created_at_utc,
            completed_at_utc=self.completed_at_utc,
            campaign_ids=(*self.campaign_ids, campaign_id),
            tags=self.tags,
            notes=self.notes,
            epistemic_status=self.epistemic_status,
            schema_version=self.schema_version,
        )


__all__ = [
    "BuildSessionV1",
]
