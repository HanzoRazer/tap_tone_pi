# INSTRUMENT CLASS: MEASUREMENT
"""Experiment lineage helpers (Dev Order 87, extended DO-88).

Pure functions for creating and manipulating experimental lineage.
These are in-memory operations — persistence is the caller's responsibility.

All helpers are deterministic and side-effect free.
"""

from __future__ import annotations

from tap_tone_pi.provenance.experiment_contracts import (
    ExperimentCampaignV1,
    ExperimentRevisionV1,
)
from tap_tone_pi.provenance.measurement_links import MeasurementLineageV1
from tap_tone_pi.provenance.build_session import BuildSessionV1
from tap_tone_pi.provenance.environment import EnvironmentRecordV1
from tap_tone_pi.provenance.fixture import FixtureRecordV1


def create_campaign(
    campaign_id: str,
    title: str,
    *,
    description: str | None = None,
    created_at_utc: str | None = None,
    tags: tuple[str, ...] | list[str] | None = None,
) -> ExperimentCampaignV1:
    """Create a new experiment campaign.

    Args:
        campaign_id: Unique identifier for the campaign (caller-provided)
        title: Display title for the campaign
        description: Optional description
        created_at_utc: ISO timestamp when campaign was created
        tags: Optional tags for categorization

    Returns:
        New ExperimentCampaignV1 instance
    """
    return ExperimentCampaignV1(
        campaign_id=campaign_id,
        title=title,
        description=description,
        created_at_utc=created_at_utc,
        tags=tuple(tags) if tags else (),
    )


def create_revision(
    revision_id: str,
    *,
    parent_revision_id: str | None = None,
    campaign_id: str | None = None,
    workflow_id: str | None = None,
    notes: str | None = None,
    created_at_utc: str | None = None,
) -> ExperimentRevisionV1:
    """Create a new experiment revision.

    Args:
        revision_id: Unique identifier for the revision (caller-provided)
        parent_revision_id: ID of the parent revision (lineage)
        campaign_id: ID of the campaign this revision belongs to
        workflow_id: ID of the workflow used for this revision
        notes: Optional notes about this revision
        created_at_utc: ISO timestamp when revision was created

    Returns:
        New ExperimentRevisionV1 instance
    """
    return ExperimentRevisionV1(
        revision_id=revision_id,
        parent_revision_id=parent_revision_id,
        campaign_id=campaign_id,
        workflow_id=workflow_id,
        notes=notes,
        created_at_utc=created_at_utc,
    )


def create_measurement_lineage(
    measurement_id: str,
    *,
    workflow_id: str | None = None,
    revision_id: str | None = None,
    campaign_id: str | None = None,
    fixture_id: str | None = None,
    environment_id: str | None = None,
    notes: str | None = None,
    created_at_utc: str | None = None,
) -> MeasurementLineageV1:
    """Create a measurement lineage record.

    Args:
        measurement_id: The measurement identifier (required)
        workflow_id: ID of the workflow that produced this measurement
        revision_id: ID of the revision this measurement belongs to
        campaign_id: ID of the campaign this measurement is part of
        fixture_id: ID of the fixture configuration used (DO-88)
        environment_id: ID of the environment record (DO-88)
        notes: Optional notes
        created_at_utc: ISO timestamp when lineage was recorded

    Returns:
        New MeasurementLineageV1 instance
    """
    return MeasurementLineageV1(
        measurement_id=measurement_id,
        workflow_id=workflow_id,
        revision_id=revision_id,
        campaign_id=campaign_id,
        fixture_id=fixture_id,
        environment_id=environment_id,
        notes=notes,
        created_at_utc=created_at_utc,
    )


def add_measurement_to_campaign(
    campaign: ExperimentCampaignV1,
    measurement_id: str,
) -> ExperimentCampaignV1:
    """Add a measurement to a campaign.

    Args:
        campaign: The campaign to add to
        measurement_id: The measurement to add

    Returns:
        New campaign with the measurement added (immutable update)
    """
    return campaign.with_measurement(measurement_id)


def add_revision_to_campaign(
    campaign: ExperimentCampaignV1,
    revision_id: str,
) -> ExperimentCampaignV1:
    """Add a revision to a campaign.

    Args:
        campaign: The campaign to add to
        revision_id: The revision to add

    Returns:
        New campaign with the revision added (immutable update)
    """
    return campaign.with_revision(revision_id)


def add_workflow_to_campaign(
    campaign: ExperimentCampaignV1,
    workflow_id: str,
) -> ExperimentCampaignV1:
    """Add a workflow to a campaign.

    Args:
        campaign: The campaign to add to
        workflow_id: The workflow to add

    Returns:
        New campaign with the workflow added (immutable update)
    """
    return campaign.with_workflow(workflow_id)


def add_measurement_to_revision(
    revision: ExperimentRevisionV1,
    measurement_id: str,
) -> ExperimentRevisionV1:
    """Add a measurement to a revision.

    Args:
        revision: The revision to add to
        measurement_id: The measurement to add

    Returns:
        New revision with the measurement added (immutable update)
    """
    return revision.with_measurement(measurement_id)


def get_campaign_measurements(campaign: ExperimentCampaignV1) -> tuple[str, ...]:
    """Get all measurement IDs in a campaign.

    Args:
        campaign: The campaign to query

    Returns:
        Tuple of measurement IDs
    """
    return campaign.measurement_ids


def get_revision_chain(
    revision: ExperimentRevisionV1,
    revision_lookup: dict[str, ExperimentRevisionV1],
) -> list[ExperimentRevisionV1]:
    """Get the chain of revisions from the given revision back to the root.

    Args:
        revision: The revision to start from
        revision_lookup: Dictionary mapping revision_id to revision

    Returns:
        List of revisions from current back to root (oldest last)
    """
    chain = [revision]
    current = revision

    while current.parent_revision_id is not None:
        parent = revision_lookup.get(current.parent_revision_id)
        if parent is None:
            break
        chain.append(parent)
        current = parent

    return chain


def link_measurement_to_context(
    measurement_id: str,
    *,
    workflow_id: str | None = None,
    revision: ExperimentRevisionV1 | None = None,
    campaign: ExperimentCampaignV1 | None = None,
    fixture: FixtureRecordV1 | None = None,
    environment: EnvironmentRecordV1 | None = None,
    created_at_utc: str | None = None,
) -> MeasurementLineageV1:
    """Create a measurement lineage from experimental context objects.

    Convenience function that extracts IDs from context objects.

    Args:
        measurement_id: The measurement identifier
        workflow_id: Optional workflow ID
        revision: Optional revision (extracts revision_id and campaign_id)
        campaign: Optional campaign (extracts campaign_id)
        fixture: Optional fixture record (extracts fixture_id)
        environment: Optional environment record (extracts environment_id)
        created_at_utc: ISO timestamp

    Returns:
        New MeasurementLineageV1 with extracted context
    """
    revision_id = revision.revision_id if revision else None
    campaign_id = (
        campaign.campaign_id if campaign else revision.campaign_id if revision else None
    )
    fixture_id = fixture.fixture_id if fixture else None
    environment_id = environment.environment_id if environment else None

    return MeasurementLineageV1(
        measurement_id=measurement_id,
        workflow_id=workflow_id,
        revision_id=revision_id,
        campaign_id=campaign_id,
        fixture_id=fixture_id,
        environment_id=environment_id,
        created_at_utc=created_at_utc,
    )


# --- DO-88 Build Session Helpers ---


def create_build_session(
    build_session_id: str,
    specimen_id: str,
    *,
    specimen_type: str | None = None,
    description: str | None = None,
    created_at_utc: str | None = None,
    tags: tuple[str, ...] | list[str] | None = None,
) -> BuildSessionV1:
    """Create a new build session.

    Args:
        build_session_id: Unique identifier for the session (caller-provided)
        specimen_id: Identifier for the specimen being built
        specimen_type: Type of specimen (guitar_top, back, etc.)
        description: Optional description
        created_at_utc: ISO timestamp when session was created
        tags: Optional tags for categorization

    Returns:
        New BuildSessionV1 instance
    """
    return BuildSessionV1(
        build_session_id=build_session_id,
        specimen_id=specimen_id,
        specimen_type=specimen_type,
        description=description,
        created_at_utc=created_at_utc,
        tags=tuple(tags) if tags else (),
    )


def create_environment_record(
    environment_id: str,
    recorded_at_utc: str,
    *,
    temperature_c: float | None = None,
    humidity_pct: float | None = None,
    room_id: str | None = None,
    ambient_noise_dbfs: float | None = None,
    notes: str | None = None,
) -> EnvironmentRecordV1:
    """Create an environment record.

    Args:
        environment_id: Unique identifier (caller-provided)
        recorded_at_utc: ISO timestamp when recorded
        temperature_c: Temperature in Celsius
        humidity_pct: Relative humidity percentage
        room_id: Room/location identifier
        ambient_noise_dbfs: Ambient noise level in dBFS
        notes: Optional notes

    Returns:
        New EnvironmentRecordV1 instance
    """
    return EnvironmentRecordV1(
        environment_id=environment_id,
        recorded_at_utc=recorded_at_utc,
        temperature_c=temperature_c,
        humidity_pct=humidity_pct,
        room_id=room_id,
        ambient_noise_dbfs=ambient_noise_dbfs,
        notes=notes,
    )


def create_fixture_record(
    fixture_id: str,
    *,
    support_condition: str | None = None,
    fixture_type: str | None = None,
    description: str | None = None,
    mic_position: str | None = None,
    tap_position: str | None = None,
    excitation_method: str | None = None,
    notes: str | None = None,
) -> FixtureRecordV1:
    """Create a fixture record.

    Args:
        fixture_id: Unique identifier (caller-provided)
        support_condition: free, clamped, supported, suspended
        fixture_type: Type of fixture (foam_blocks, rubber_bands, etc.)
        description: Optional description
        mic_position: Microphone position
        tap_position: Tap/excitation position
        excitation_method: tap, impulse_hammer, shaker, etc.
        notes: Optional notes

    Returns:
        New FixtureRecordV1 instance
    """
    return FixtureRecordV1(
        fixture_id=fixture_id,
        support_condition=support_condition,
        fixture_type=fixture_type,
        description=description,
        mic_position=mic_position,
        tap_position=tap_position,
        excitation_method=excitation_method,
        notes=notes,
    )


def add_campaign_to_build_session(
    build_session: BuildSessionV1,
    campaign_id: str,
) -> BuildSessionV1:
    """Add a campaign to a build session.

    Args:
        build_session: The build session to add to
        campaign_id: The campaign to add

    Returns:
        New build session with the campaign added (immutable update)
    """
    return build_session.with_campaign(campaign_id)


__all__ = [
    # DO-87 helpers
    "create_campaign",
    "create_revision",
    "create_measurement_lineage",
    "add_measurement_to_campaign",
    "add_revision_to_campaign",
    "add_workflow_to_campaign",
    "add_measurement_to_revision",
    "get_campaign_measurements",
    "get_revision_chain",
    "link_measurement_to_context",
    # DO-88 helpers
    "create_build_session",
    "create_environment_record",
    "create_fixture_record",
    "add_campaign_to_build_session",
]
