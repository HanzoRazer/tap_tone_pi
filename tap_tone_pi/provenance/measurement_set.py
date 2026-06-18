# INSTRUMENT CLASS: MEASUREMENT
"""Measurement set contracts (Dev Order 89).

Measurement sets group measurements by campaign, revision, or workflow.
They enable aggregation without advisory semantics.

Measurement sets record what was measured and computed statistics.
They do not evaluate quality, success, or recommend actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MeasurementSetV1:
    """Groups measurements by campaign, revision, or workflow.

    A measurement set is a collection of measurement IDs with optional
    grouping context. It does not contain measurement data itself.

    Classification: INSTRUMENT CLASS: MEASUREMENT
    """

    measurement_set_id: str

    campaign_id: str | None = None
    revision_id: str | None = None
    workflow_id: str | None = None

    measurement_ids: tuple[str, ...] = field(default_factory=tuple)

    notes: str | None = None

    epistemic_status: str = "derived"
    schema_version: str = "measurement_set_v1"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON export."""
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "measurement_set_id": self.measurement_set_id,
            "epistemic_status": self.epistemic_status,
        }
        if self.campaign_id is not None:
            result["campaign_id"] = self.campaign_id
        if self.revision_id is not None:
            result["revision_id"] = self.revision_id
        if self.workflow_id is not None:
            result["workflow_id"] = self.workflow_id
        if self.measurement_ids:
            result["measurement_ids"] = list(self.measurement_ids)
        if self.notes is not None:
            result["notes"] = self.notes
        return result

    @property
    def measurement_count(self) -> int:
        """Return the number of measurements in this set."""
        return len(self.measurement_ids)

    def with_measurement(self, measurement_id: str) -> MeasurementSetV1:
        """Return a new set with the measurement added."""
        if measurement_id in self.measurement_ids:
            return self
        return MeasurementSetV1(
            measurement_set_id=self.measurement_set_id,
            campaign_id=self.campaign_id,
            revision_id=self.revision_id,
            workflow_id=self.workflow_id,
            measurement_ids=(*self.measurement_ids, measurement_id),
            notes=self.notes,
            epistemic_status=self.epistemic_status,
            schema_version=self.schema_version,
        )


@dataclass(frozen=True)
class MeasurementSetSummaryV1:
    """Aggregate statistics for a measurement set.

    Contains computed statistics: counts, means, standard deviations,
    min/max values. Does not evaluate quality or recommend actions.

    Classification: INSTRUMENT CLASS: MEASUREMENT
    """

    measurement_count: int

    campaign_id: str | None = None
    revision_id: str | None = None
    workflow_id: str | None = None

    # Frequency statistics
    dominant_frequency_mean_hz: float | None = None
    dominant_frequency_std_hz: float | None = None
    dominant_frequency_min_hz: float | None = None
    dominant_frequency_max_hz: float | None = None

    # Repeatability score statistics
    repeatability_score_mean: float | None = None
    repeatability_score_std: float | None = None
    repeatability_score_min: float | None = None
    repeatability_score_max: float | None = None

    notes: str | None = None

    epistemic_status: str = "derived"
    schema_version: str = "measurement_set_summary_v1"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON export."""
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "measurement_count": self.measurement_count,
            "epistemic_status": self.epistemic_status,
        }
        if self.campaign_id is not None:
            result["campaign_id"] = self.campaign_id
        if self.revision_id is not None:
            result["revision_id"] = self.revision_id
        if self.workflow_id is not None:
            result["workflow_id"] = self.workflow_id
        if self.dominant_frequency_mean_hz is not None:
            result["dominant_frequency_mean_hz"] = self.dominant_frequency_mean_hz
        if self.dominant_frequency_std_hz is not None:
            result["dominant_frequency_std_hz"] = self.dominant_frequency_std_hz
        if self.dominant_frequency_min_hz is not None:
            result["dominant_frequency_min_hz"] = self.dominant_frequency_min_hz
        if self.dominant_frequency_max_hz is not None:
            result["dominant_frequency_max_hz"] = self.dominant_frequency_max_hz
        if self.repeatability_score_mean is not None:
            result["repeatability_score_mean"] = self.repeatability_score_mean
        if self.repeatability_score_std is not None:
            result["repeatability_score_std"] = self.repeatability_score_std
        if self.repeatability_score_min is not None:
            result["repeatability_score_min"] = self.repeatability_score_min
        if self.repeatability_score_max is not None:
            result["repeatability_score_max"] = self.repeatability_score_max
        if self.notes is not None:
            result["notes"] = self.notes
        return result


@dataclass(frozen=True)
class CampaignLifecycleExportV1:
    """Lifecycle-only export block for campaigns (Dev Order 89).

    A smaller export object containing just lifecycle fields,
    separate from the full ExperimentCampaignV1.

    Classification: INSTRUMENT CLASS: MEASUREMENT
    """

    campaign_id: str
    lifecycle_state: str

    started_at_utc: str | None = None
    completed_at_utc: str | None = None
    archived_at_utc: str | None = None

    epistemic_status: str = "derived"
    schema_version: str = "campaign_lifecycle_v1"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON export."""
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "campaign_id": self.campaign_id,
            "lifecycle_state": self.lifecycle_state,
            "epistemic_status": self.epistemic_status,
        }
        if self.started_at_utc is not None:
            result["started_at_utc"] = self.started_at_utc
        if self.completed_at_utc is not None:
            result["completed_at_utc"] = self.completed_at_utc
        if self.archived_at_utc is not None:
            result["archived_at_utc"] = self.archived_at_utc
        return result

    @classmethod
    def from_campaign(cls, campaign) -> CampaignLifecycleExportV1:
        """Create a lifecycle export from a campaign."""
        return cls(
            campaign_id=campaign.campaign_id,
            lifecycle_state=campaign.lifecycle_state,
            started_at_utc=campaign.started_at_utc,
            completed_at_utc=campaign.completed_at_utc,
            archived_at_utc=campaign.archived_at_utc,
        )


__all__ = [
    "MeasurementSetV1",
    "MeasurementSetSummaryV1",
    "CampaignLifecycleExportV1",
]
