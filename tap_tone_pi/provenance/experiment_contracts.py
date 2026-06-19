# INSTRUMENT CLASS: MEASUREMENT
"""Experiment campaign and revision contracts (Dev Order 87, extended DO-88, DO-89, DO-89A).

Experiment campaigns group workflows, measurements, and revisions into
intentional experimental structures. This enables:
- Grouping measurements into research programs
- Tracking revision lineage between experimental iterations
- Maintaining provenance without advisory semantics
- Linking campaigns to build sessions (DO-88)
- Tracking campaign lifecycle state (DO-89)
- Linking campaigns to experiment designs (DO-89A)

Campaigns and revisions are containers for lineage, not evaluators of outcomes.
They record what was tested, not what should be done.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CampaignLifecycleState(str, Enum):
    """Procedural lifecycle state for an experiment campaign.

    These are operational states only — no quality judgment.
    A completed campaign means procedurally completed, not successful.
    """

    PLANNED = "planned"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    ABORTED = "aborted"


@dataclass(frozen=True)
class ExperimentCampaignV1:
    """Groups workflows, measurements, and revisions into an experiment.

    A campaign is a container for experimental lineage. It references
    measurements and revisions but does not modify them.

    Classification: INSTRUMENT CLASS: MEASUREMENT
    """

    campaign_id: str
    title: str

    description: str | None = None
    created_at_utc: str | None = None

    # Build session linkage (DO-88)
    build_session_id: str | None = None

    # Experiment design linkage (DO-89A)
    experiment_design_id: str | None = None

    # Campaign lifecycle (DO-89)
    lifecycle_state: str = CampaignLifecycleState.PLANNED.value
    started_at_utc: str | None = None
    completed_at_utc: str | None = None
    archived_at_utc: str | None = None

    workflow_ids: tuple[str, ...] = field(default_factory=tuple)
    revision_ids: tuple[str, ...] = field(default_factory=tuple)
    measurement_ids: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)

    epistemic_status: str = "derived"
    schema_version: str = "experiment_campaign_v1"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON export."""
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "campaign_id": self.campaign_id,
            "title": self.title,
            "epistemic_status": self.epistemic_status,
        }
        if self.description is not None:
            result["description"] = self.description
        if self.created_at_utc is not None:
            result["created_at_utc"] = self.created_at_utc
        if self.build_session_id is not None:
            result["build_session_id"] = self.build_session_id
        if self.experiment_design_id is not None:
            result["experiment_design_id"] = self.experiment_design_id
        # Lifecycle state (DO-89)
        result["lifecycle_state"] = self.lifecycle_state
        if self.started_at_utc is not None:
            result["started_at_utc"] = self.started_at_utc
        if self.completed_at_utc is not None:
            result["completed_at_utc"] = self.completed_at_utc
        if self.archived_at_utc is not None:
            result["archived_at_utc"] = self.archived_at_utc
        if self.workflow_ids:
            result["workflow_ids"] = list(self.workflow_ids)
        if self.revision_ids:
            result["revision_ids"] = list(self.revision_ids)
        if self.measurement_ids:
            result["measurement_ids"] = list(self.measurement_ids)
        if self.tags:
            result["tags"] = list(self.tags)
        return result

    def with_measurement(self, measurement_id: str) -> ExperimentCampaignV1:
        """Return a new campaign with the measurement added."""
        if measurement_id in self.measurement_ids:
            return self
        return ExperimentCampaignV1(
            campaign_id=self.campaign_id,
            title=self.title,
            description=self.description,
            created_at_utc=self.created_at_utc,
            build_session_id=self.build_session_id,
            experiment_design_id=self.experiment_design_id,
            lifecycle_state=self.lifecycle_state,
            started_at_utc=self.started_at_utc,
            completed_at_utc=self.completed_at_utc,
            archived_at_utc=self.archived_at_utc,
            workflow_ids=self.workflow_ids,
            revision_ids=self.revision_ids,
            measurement_ids=(*self.measurement_ids, measurement_id),
            tags=self.tags,
            epistemic_status=self.epistemic_status,
            schema_version=self.schema_version,
        )

    def with_revision(self, revision_id: str) -> ExperimentCampaignV1:
        """Return a new campaign with the revision added."""
        if revision_id in self.revision_ids:
            return self
        return ExperimentCampaignV1(
            campaign_id=self.campaign_id,
            title=self.title,
            description=self.description,
            created_at_utc=self.created_at_utc,
            build_session_id=self.build_session_id,
            experiment_design_id=self.experiment_design_id,
            lifecycle_state=self.lifecycle_state,
            started_at_utc=self.started_at_utc,
            completed_at_utc=self.completed_at_utc,
            archived_at_utc=self.archived_at_utc,
            workflow_ids=self.workflow_ids,
            revision_ids=(*self.revision_ids, revision_id),
            measurement_ids=self.measurement_ids,
            tags=self.tags,
            epistemic_status=self.epistemic_status,
            schema_version=self.schema_version,
        )

    def with_workflow(self, workflow_id: str) -> ExperimentCampaignV1:
        """Return a new campaign with the workflow added."""
        if workflow_id in self.workflow_ids:
            return self
        return ExperimentCampaignV1(
            campaign_id=self.campaign_id,
            title=self.title,
            description=self.description,
            created_at_utc=self.created_at_utc,
            build_session_id=self.build_session_id,
            experiment_design_id=self.experiment_design_id,
            lifecycle_state=self.lifecycle_state,
            started_at_utc=self.started_at_utc,
            completed_at_utc=self.completed_at_utc,
            archived_at_utc=self.archived_at_utc,
            workflow_ids=(*self.workflow_ids, workflow_id),
            revision_ids=self.revision_ids,
            measurement_ids=self.measurement_ids,
            tags=self.tags,
            epistemic_status=self.epistemic_status,
            schema_version=self.schema_version,
        )

    def with_build_session(self, build_session_id: str) -> ExperimentCampaignV1:
        """Return a new campaign linked to a build session."""
        return ExperimentCampaignV1(
            campaign_id=self.campaign_id,
            title=self.title,
            description=self.description,
            created_at_utc=self.created_at_utc,
            build_session_id=build_session_id,
            experiment_design_id=self.experiment_design_id,
            lifecycle_state=self.lifecycle_state,
            started_at_utc=self.started_at_utc,
            completed_at_utc=self.completed_at_utc,
            archived_at_utc=self.archived_at_utc,
            workflow_ids=self.workflow_ids,
            revision_ids=self.revision_ids,
            measurement_ids=self.measurement_ids,
            tags=self.tags,
            epistemic_status=self.epistemic_status,
            schema_version=self.schema_version,
        )

    def with_lifecycle_state(
        self,
        state: str,
        *,
        started_at_utc: str | None = None,
        completed_at_utc: str | None = None,
        archived_at_utc: str | None = None,
    ) -> ExperimentCampaignV1:
        """Return a new campaign with the lifecycle state updated."""
        return ExperimentCampaignV1(
            campaign_id=self.campaign_id,
            title=self.title,
            description=self.description,
            created_at_utc=self.created_at_utc,
            build_session_id=self.build_session_id,
            experiment_design_id=self.experiment_design_id,
            lifecycle_state=state,
            started_at_utc=started_at_utc if started_at_utc is not None else self.started_at_utc,
            completed_at_utc=completed_at_utc if completed_at_utc is not None else self.completed_at_utc,
            archived_at_utc=archived_at_utc if archived_at_utc is not None else self.archived_at_utc,
            workflow_ids=self.workflow_ids,
            revision_ids=self.revision_ids,
            measurement_ids=self.measurement_ids,
            tags=self.tags,
            epistemic_status=self.epistemic_status,
            schema_version=self.schema_version,
        )

    def with_experiment_design(self, experiment_design_id: str) -> ExperimentCampaignV1:
        """Return a new campaign linked to an experiment design (DO-89A)."""
        return ExperimentCampaignV1(
            campaign_id=self.campaign_id,
            title=self.title,
            description=self.description,
            created_at_utc=self.created_at_utc,
            build_session_id=self.build_session_id,
            experiment_design_id=experiment_design_id,
            lifecycle_state=self.lifecycle_state,
            started_at_utc=self.started_at_utc,
            completed_at_utc=self.completed_at_utc,
            archived_at_utc=self.archived_at_utc,
            workflow_ids=self.workflow_ids,
            revision_ids=self.revision_ids,
            measurement_ids=self.measurement_ids,
            tags=self.tags,
            epistemic_status=self.epistemic_status,
            schema_version=self.schema_version,
        )


@dataclass(frozen=True)
class ExperimentRevisionV1:
    """Tracks lineage between experimental iterations.

    A revision links to its parent (if any) and the measurements taken
    during that iteration. Revisions are lineage markers only — they do
    not evaluate improvement or recommend actions.

    Classification: INSTRUMENT CLASS: MEASUREMENT
    """

    revision_id: str

    parent_revision_id: str | None = None
    campaign_id: str | None = None
    notes: str | None = None
    workflow_id: str | None = None
    created_at_utc: str | None = None

    measurement_ids: tuple[str, ...] = field(default_factory=tuple)

    epistemic_status: str = "derived"
    schema_version: str = "experiment_revision_v1"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON export."""
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "revision_id": self.revision_id,
            "epistemic_status": self.epistemic_status,
        }
        if self.parent_revision_id is not None:
            result["parent_revision_id"] = self.parent_revision_id
        if self.campaign_id is not None:
            result["campaign_id"] = self.campaign_id
        if self.notes is not None:
            result["notes"] = self.notes
        if self.workflow_id is not None:
            result["workflow_id"] = self.workflow_id
        if self.created_at_utc is not None:
            result["created_at_utc"] = self.created_at_utc
        if self.measurement_ids:
            result["measurement_ids"] = list(self.measurement_ids)
        return result

    def with_measurement(self, measurement_id: str) -> ExperimentRevisionV1:
        """Return a new revision with the measurement added."""
        if measurement_id in self.measurement_ids:
            return self
        return ExperimentRevisionV1(
            revision_id=self.revision_id,
            parent_revision_id=self.parent_revision_id,
            campaign_id=self.campaign_id,
            notes=self.notes,
            workflow_id=self.workflow_id,
            created_at_utc=self.created_at_utc,
            measurement_ids=(*self.measurement_ids, measurement_id),
            epistemic_status=self.epistemic_status,
            schema_version=self.schema_version,
        )


__all__ = [
    "CampaignLifecycleState",
    "ExperimentCampaignV1",
    "ExperimentRevisionV1",
]
