# INSTRUMENT CLASS: MEASUREMENT
"""Experimental provenance and measurement campaign lineage (Dev Order 87, 88, 89).

This package provides contracts and helpers for tracking experimental lineage:
- Build sessions contain all measurements for a specimen (DO-88)
- Experiment campaigns group workflows, measurements, and revisions
- Revisions track lineage between experimental iterations
- Measurement linkage connects measurements to their experimental context
- Environment records capture physical conditions (DO-88)
- Fixture records capture measurement setup (DO-88)
- Campaign lifecycle state tracking (DO-89)
- Measurement set aggregation (DO-89)

All artifacts are observational — they record what was tested, not what should
be done. No advisory semantics, rankings, or recommendations.
"""

from tap_tone_pi.provenance.experiment_contracts import (
    CampaignLifecycleState,
    ExperimentCampaignV1,
    ExperimentRevisionV1,
)
from tap_tone_pi.provenance.measurement_links import MeasurementLineageV1
from tap_tone_pi.provenance.build_session import BuildSessionV1
from tap_tone_pi.provenance.environment import EnvironmentRecordV1
from tap_tone_pi.provenance.fixture import FixtureRecordV1
from tap_tone_pi.provenance.measurement_set import (
    MeasurementSetV1,
    MeasurementSetSummaryV1,
    CampaignLifecycleExportV1,
)
from tap_tone_pi.provenance.campaign_lifecycle import (
    transition_campaign_state,
    start_campaign,
    pause_campaign,
    complete_campaign,
    archive_campaign,
    abort_campaign,
)
from tap_tone_pi.provenance.aggregation import (
    collect_measurements_for_campaign,
    collect_measurements_for_revision,
    collect_measurements_for_workflow,
    summarize_measurement_set,
    create_measurement_set,
)
from tap_tone_pi.provenance.lineage import (
    create_campaign,
    create_revision,
    create_measurement_lineage,
    create_build_session,
    create_environment_record,
    create_fixture_record,
    add_measurement_to_campaign,
    add_revision_to_campaign,
    add_workflow_to_campaign,
    add_measurement_to_revision,
    add_campaign_to_build_session,
    get_campaign_measurements,
    get_revision_chain,
    link_measurement_to_context,
)

__all__ = [
    # Contracts (DO-87)
    "ExperimentCampaignV1",
    "ExperimentRevisionV1",
    "MeasurementLineageV1",
    # Contracts (DO-88)
    "BuildSessionV1",
    "EnvironmentRecordV1",
    "FixtureRecordV1",
    # Contracts (DO-89)
    "CampaignLifecycleState",
    "MeasurementSetV1",
    "MeasurementSetSummaryV1",
    "CampaignLifecycleExportV1",
    # Lifecycle helpers (DO-89)
    "transition_campaign_state",
    "start_campaign",
    "pause_campaign",
    "complete_campaign",
    "archive_campaign",
    "abort_campaign",
    # Aggregation helpers (DO-89)
    "collect_measurements_for_campaign",
    "collect_measurements_for_revision",
    "collect_measurements_for_workflow",
    "summarize_measurement_set",
    "create_measurement_set",
    # Lineage helpers (DO-87, DO-88)
    "create_campaign",
    "create_revision",
    "create_measurement_lineage",
    "create_build_session",
    "create_environment_record",
    "create_fixture_record",
    "add_measurement_to_campaign",
    "add_revision_to_campaign",
    "add_workflow_to_campaign",
    "add_measurement_to_revision",
    "add_campaign_to_build_session",
    "get_campaign_measurements",
    "get_revision_chain",
    "link_measurement_to_context",
]
