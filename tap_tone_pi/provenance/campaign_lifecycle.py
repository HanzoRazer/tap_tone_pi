# INSTRUMENT CLASS: MEASUREMENT
"""Campaign lifecycle state transitions (Dev Order 89).

Pure functions for transitioning campaign lifecycle state.
These are deterministic, procedural transitions — no quality judgment.

A completed campaign means procedurally completed, not successful.
"""

from __future__ import annotations

from tap_tone_pi.provenance.experiment_contracts import (
    ExperimentCampaignV1,
    CampaignLifecycleState,
)

# Valid state transitions
_VALID_TRANSITIONS: dict[str, set[str]] = {
    CampaignLifecycleState.PLANNED.value: {
        CampaignLifecycleState.ACTIVE.value,
        CampaignLifecycleState.ABORTED.value,
        CampaignLifecycleState.ARCHIVED.value,
    },
    CampaignLifecycleState.ACTIVE.value: {
        CampaignLifecycleState.PAUSED.value,
        CampaignLifecycleState.COMPLETED.value,
        CampaignLifecycleState.ABORTED.value,
    },
    CampaignLifecycleState.PAUSED.value: {
        CampaignLifecycleState.ACTIVE.value,
        CampaignLifecycleState.ABORTED.value,
        CampaignLifecycleState.ARCHIVED.value,
    },
    CampaignLifecycleState.COMPLETED.value: {
        CampaignLifecycleState.ARCHIVED.value,
    },
    CampaignLifecycleState.ABORTED.value: {
        CampaignLifecycleState.ARCHIVED.value,
    },
    CampaignLifecycleState.ARCHIVED.value: set(),  # No transitions from archived
}


def _validate_transition(current_state: str, new_state: str) -> None:
    """Validate that a state transition is allowed.

    Raises:
        ValueError: If the transition is invalid
    """
    valid_states = {s.value for s in CampaignLifecycleState}

    if current_state not in valid_states:
        raise ValueError(f"Unknown current state: {current_state}")

    if new_state not in valid_states:
        raise ValueError(f"Unknown target state: {new_state}")

    allowed = _VALID_TRANSITIONS.get(current_state, set())
    if new_state not in allowed:
        raise ValueError(
            f"Invalid state transition: {current_state} -> {new_state}. "
            f"Allowed transitions from {current_state}: {sorted(allowed) or 'none'}"
        )


def transition_campaign_state(
    campaign: ExperimentCampaignV1,
    *,
    new_state: str,
    timestamp_utc: str | None = None,
) -> ExperimentCampaignV1:
    """Transition a campaign to a new lifecycle state.

    Args:
        campaign: The campaign to transition
        new_state: The target state (from CampaignLifecycleState)
        timestamp_utc: Optional timestamp for the transition

    Returns:
        New campaign with updated state

    Raises:
        ValueError: If the transition is invalid
    """
    _validate_transition(campaign.lifecycle_state, new_state)

    # Determine which timestamp to set based on the new state
    started_at = campaign.started_at_utc
    completed_at = campaign.completed_at_utc
    archived_at = campaign.archived_at_utc

    if new_state == CampaignLifecycleState.ACTIVE.value and started_at is None:
        started_at = timestamp_utc
    elif new_state == CampaignLifecycleState.COMPLETED.value:
        completed_at = timestamp_utc
    elif new_state == CampaignLifecycleState.ARCHIVED.value:
        archived_at = timestamp_utc

    return campaign.with_lifecycle_state(
        new_state,
        started_at_utc=started_at,
        completed_at_utc=completed_at,
        archived_at_utc=archived_at,
    )


def start_campaign(
    campaign: ExperimentCampaignV1,
    *,
    timestamp_utc: str | None = None,
) -> ExperimentCampaignV1:
    """Transition a campaign from planned to active.

    Args:
        campaign: The campaign to start
        timestamp_utc: Optional start timestamp

    Returns:
        New campaign in active state

    Raises:
        ValueError: If the campaign cannot be started
    """
    return transition_campaign_state(
        campaign,
        new_state=CampaignLifecycleState.ACTIVE.value,
        timestamp_utc=timestamp_utc,
    )


def pause_campaign(
    campaign: ExperimentCampaignV1,
    *,
    timestamp_utc: str | None = None,
) -> ExperimentCampaignV1:
    """Pause an active campaign.

    Args:
        campaign: The campaign to pause
        timestamp_utc: Optional pause timestamp (not stored, for logging)

    Returns:
        New campaign in paused state

    Raises:
        ValueError: If the campaign cannot be paused
    """
    return transition_campaign_state(
        campaign,
        new_state=CampaignLifecycleState.PAUSED.value,
        timestamp_utc=timestamp_utc,
    )


def complete_campaign(
    campaign: ExperimentCampaignV1,
    *,
    timestamp_utc: str | None = None,
) -> ExperimentCampaignV1:
    """Complete an active campaign.

    Args:
        campaign: The campaign to complete
        timestamp_utc: Optional completion timestamp

    Returns:
        New campaign in completed state

    Raises:
        ValueError: If the campaign cannot be completed
    """
    return transition_campaign_state(
        campaign,
        new_state=CampaignLifecycleState.COMPLETED.value,
        timestamp_utc=timestamp_utc,
    )


def archive_campaign(
    campaign: ExperimentCampaignV1,
    *,
    timestamp_utc: str | None = None,
) -> ExperimentCampaignV1:
    """Archive a campaign.

    Args:
        campaign: The campaign to archive
        timestamp_utc: Optional archive timestamp

    Returns:
        New campaign in archived state

    Raises:
        ValueError: If the campaign cannot be archived
    """
    return transition_campaign_state(
        campaign,
        new_state=CampaignLifecycleState.ARCHIVED.value,
        timestamp_utc=timestamp_utc,
    )


def abort_campaign(
    campaign: ExperimentCampaignV1,
    *,
    timestamp_utc: str | None = None,
) -> ExperimentCampaignV1:
    """Abort a campaign.

    Args:
        campaign: The campaign to abort
        timestamp_utc: Optional abort timestamp (not stored, for logging)

    Returns:
        New campaign in aborted state

    Raises:
        ValueError: If the campaign cannot be aborted
    """
    return transition_campaign_state(
        campaign,
        new_state=CampaignLifecycleState.ABORTED.value,
        timestamp_utc=timestamp_utc,
    )


__all__ = [
    "transition_campaign_state",
    "start_campaign",
    "pause_campaign",
    "complete_campaign",
    "archive_campaign",
    "abort_campaign",
]
