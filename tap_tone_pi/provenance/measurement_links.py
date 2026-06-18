# INSTRUMENT CLASS: MEASUREMENT
"""Measurement lineage linkage (Dev Order 87, extended DO-88).

Connects measurements to their experimental context:
- measurement_id: the measurement itself
- workflow_id: which workflow produced it
- revision_id: which experimental revision it belongs to
- campaign_id: which campaign it's part of
- fixture_id: which fixture configuration was used (DO-88)
- environment_id: which environmental conditions existed (DO-88)

All fields except measurement_id are optional — orphan measurements
without experimental context are valid.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MeasurementLineageV1:
    """Links a measurement to its experimental context.

    Tracks the lineage chain:
        measurement_id → workflow_id → revision_id → campaign_id

    All fields except measurement_id are optional. A measurement may
    exist without belonging to any experiment, revision, or workflow.

    Classification: INSTRUMENT CLASS: MEASUREMENT
    """

    measurement_id: str

    workflow_id: str | None = None
    revision_id: str | None = None
    campaign_id: str | None = None

    # Context references (DO-88)
    fixture_id: str | None = None
    environment_id: str | None = None

    notes: str | None = None
    created_at_utc: str | None = None

    epistemic_status: str = "derived"
    schema_version: str = "measurement_lineage_v1"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON export."""
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "measurement_id": self.measurement_id,
            "epistemic_status": self.epistemic_status,
        }
        if self.workflow_id is not None:
            result["workflow_id"] = self.workflow_id
        if self.revision_id is not None:
            result["revision_id"] = self.revision_id
        if self.campaign_id is not None:
            result["campaign_id"] = self.campaign_id
        if self.fixture_id is not None:
            result["fixture_id"] = self.fixture_id
        if self.environment_id is not None:
            result["environment_id"] = self.environment_id
        if self.notes is not None:
            result["notes"] = self.notes
        if self.created_at_utc is not None:
            result["created_at_utc"] = self.created_at_utc
        return result

    def has_experimental_context(self) -> bool:
        """Return True if this measurement belongs to any experimental context."""
        return any([
            self.workflow_id is not None,
            self.revision_id is not None,
            self.campaign_id is not None,
            self.fixture_id is not None,
            self.environment_id is not None,
        ])

    def with_workflow(self, workflow_id: str) -> MeasurementLineageV1:
        """Return a new lineage with the workflow set."""
        return MeasurementLineageV1(
            measurement_id=self.measurement_id,
            workflow_id=workflow_id,
            revision_id=self.revision_id,
            campaign_id=self.campaign_id,
            fixture_id=self.fixture_id,
            environment_id=self.environment_id,
            notes=self.notes,
            created_at_utc=self.created_at_utc,
            epistemic_status=self.epistemic_status,
            schema_version=self.schema_version,
        )

    def with_revision(self, revision_id: str) -> MeasurementLineageV1:
        """Return a new lineage with the revision set."""
        return MeasurementLineageV1(
            measurement_id=self.measurement_id,
            workflow_id=self.workflow_id,
            revision_id=revision_id,
            campaign_id=self.campaign_id,
            fixture_id=self.fixture_id,
            environment_id=self.environment_id,
            notes=self.notes,
            created_at_utc=self.created_at_utc,
            epistemic_status=self.epistemic_status,
            schema_version=self.schema_version,
        )

    def with_campaign(self, campaign_id: str) -> MeasurementLineageV1:
        """Return a new lineage with the campaign set."""
        return MeasurementLineageV1(
            measurement_id=self.measurement_id,
            workflow_id=self.workflow_id,
            revision_id=self.revision_id,
            campaign_id=campaign_id,
            fixture_id=self.fixture_id,
            environment_id=self.environment_id,
            notes=self.notes,
            created_at_utc=self.created_at_utc,
            epistemic_status=self.epistemic_status,
            schema_version=self.schema_version,
        )

    def with_fixture(self, fixture_id: str) -> MeasurementLineageV1:
        """Return a new lineage with the fixture set."""
        return MeasurementLineageV1(
            measurement_id=self.measurement_id,
            workflow_id=self.workflow_id,
            revision_id=self.revision_id,
            campaign_id=self.campaign_id,
            fixture_id=fixture_id,
            environment_id=self.environment_id,
            notes=self.notes,
            created_at_utc=self.created_at_utc,
            epistemic_status=self.epistemic_status,
            schema_version=self.schema_version,
        )

    def with_environment(self, environment_id: str) -> MeasurementLineageV1:
        """Return a new lineage with the environment set."""
        return MeasurementLineageV1(
            measurement_id=self.measurement_id,
            workflow_id=self.workflow_id,
            revision_id=self.revision_id,
            campaign_id=self.campaign_id,
            fixture_id=self.fixture_id,
            environment_id=environment_id,
            notes=self.notes,
            created_at_utc=self.created_at_utc,
            epistemic_status=self.epistemic_status,
            schema_version=self.schema_version,
        )


__all__ = [
    "MeasurementLineageV1",
]
