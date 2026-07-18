# INSTRUMENT CLASS: MEASUREMENT
"""Tests for campaign lifecycle state transitions (Dev Order 89).

Tests cover:
- Campaign default state
- Valid state transitions
- Invalid state transitions
- Timestamp handling
- Constitutional semantics (no advisory states)
"""

import pytest

from tap_tone_pi.provenance import (
    CampaignLifecycleState,
    create_campaign,
    transition_campaign_state,
    start_campaign,
    pause_campaign,
    complete_campaign,
    archive_campaign,
    abort_campaign,
)


class TestCampaignDefaultState:
    """Tests for default campaign state."""

    def test_campaign_default_state_is_planned(self):
        """New campaigns should default to planned state."""
        campaign = create_campaign("test_001", "Test Campaign")

        assert campaign.lifecycle_state == CampaignLifecycleState.PLANNED.value
        assert campaign.lifecycle_state == "planned"

    def test_campaign_serializes_lifecycle_state(self):
        """Campaign to_dict should include lifecycle_state."""
        campaign = create_campaign("test_001", "Test Campaign")
        d = campaign.to_dict()

        assert "lifecycle_state" in d
        assert d["lifecycle_state"] == "planned"


class TestValidStateTransitions:
    """Tests for valid state transitions."""

    def test_planned_campaign_can_start(self):
        """Planned campaign can transition to active."""
        campaign = create_campaign("test_001", "Test")
        updated = start_campaign(campaign, timestamp_utc="2026-06-12T10:00:00Z")

        assert updated.lifecycle_state == "active"
        assert updated.started_at_utc == "2026-06-12T10:00:00Z"

    def test_active_campaign_can_pause(self):
        """Active campaign can transition to paused."""
        campaign = create_campaign("test_001", "Test")
        campaign = start_campaign(campaign)
        updated = pause_campaign(campaign)

        assert updated.lifecycle_state == "paused"

    def test_active_campaign_can_complete(self):
        """Active campaign can transition to completed."""
        campaign = create_campaign("test_001", "Test")
        campaign = start_campaign(campaign, timestamp_utc="2026-06-12T10:00:00Z")
        updated = complete_campaign(campaign, timestamp_utc="2026-06-12T12:00:00Z")

        assert updated.lifecycle_state == "completed"
        assert updated.completed_at_utc == "2026-06-12T12:00:00Z"
        assert updated.started_at_utc == "2026-06-12T10:00:00Z"

    def test_completed_campaign_can_archive(self):
        """Completed campaign can transition to archived."""
        campaign = create_campaign("test_001", "Test")
        campaign = start_campaign(campaign)
        campaign = complete_campaign(campaign)
        updated = archive_campaign(campaign, timestamp_utc="2026-06-12T14:00:00Z")

        assert updated.lifecycle_state == "archived"
        assert updated.archived_at_utc == "2026-06-12T14:00:00Z"

    def test_paused_campaign_can_resume(self):
        """Paused campaign can transition back to active."""
        campaign = create_campaign("test_001", "Test")
        campaign = start_campaign(campaign)
        campaign = pause_campaign(campaign)
        updated = start_campaign(campaign)

        assert updated.lifecycle_state == "active"

    def test_active_campaign_can_abort(self):
        """Active campaign can transition to aborted."""
        campaign = create_campaign("test_001", "Test")
        campaign = start_campaign(campaign)
        updated = abort_campaign(campaign)

        assert updated.lifecycle_state == "aborted"

    def test_aborted_campaign_can_archive(self):
        """Aborted campaign can transition to archived."""
        campaign = create_campaign("test_001", "Test")
        campaign = start_campaign(campaign)
        campaign = abort_campaign(campaign)
        updated = archive_campaign(campaign)

        assert updated.lifecycle_state == "archived"


class TestInvalidStateTransitions:
    """Tests for invalid state transitions."""

    def test_archived_campaign_cannot_transition(self):
        """Archived campaign cannot transition to any other state."""
        campaign = create_campaign("test_001", "Test")
        campaign = start_campaign(campaign)
        campaign = complete_campaign(campaign)
        campaign = archive_campaign(campaign)

        with pytest.raises(ValueError) as exc_info:
            start_campaign(campaign)

        assert "Invalid state transition" in str(exc_info.value)
        assert "archived" in str(exc_info.value)

    def test_planned_campaign_cannot_complete(self):
        """Planned campaign cannot transition directly to completed."""
        campaign = create_campaign("test_001", "Test")

        with pytest.raises(ValueError) as exc_info:
            complete_campaign(campaign)

        assert "Invalid state transition" in str(exc_info.value)

    def test_completed_campaign_cannot_pause(self):
        """Completed campaign cannot transition to paused."""
        campaign = create_campaign("test_001", "Test")
        campaign = start_campaign(campaign)
        campaign = complete_campaign(campaign)

        with pytest.raises(ValueError) as exc_info:
            pause_campaign(campaign)

        assert "Invalid state transition" in str(exc_info.value)

    def test_invalid_state_rejected(self):
        """Unknown state should raise ValueError."""
        campaign = create_campaign("test_001", "Test")

        with pytest.raises(ValueError) as exc_info:
            transition_campaign_state(campaign, new_state="invalid_state")

        assert "Unknown target state" in str(exc_info.value)


class TestTimestampHandling:
    """Tests for timestamp handling in transitions."""

    def test_start_sets_started_at(self):
        """Starting a campaign should set started_at_utc."""
        campaign = create_campaign("test_001", "Test")
        updated = start_campaign(campaign, timestamp_utc="2026-06-12T10:00:00Z")

        assert updated.started_at_utc == "2026-06-12T10:00:00Z"

    def test_start_preserves_existing_started_at(self):
        """Resuming from paused should not overwrite started_at."""
        campaign = create_campaign("test_001", "Test")
        campaign = start_campaign(campaign, timestamp_utc="2026-06-12T10:00:00Z")
        campaign = pause_campaign(campaign)
        updated = start_campaign(campaign, timestamp_utc="2026-06-12T14:00:00Z")

        assert updated.started_at_utc == "2026-06-12T10:00:00Z"

    def test_complete_sets_completed_at(self):
        """Completing a campaign should set completed_at_utc."""
        campaign = create_campaign("test_001", "Test")
        campaign = start_campaign(campaign)
        updated = complete_campaign(campaign, timestamp_utc="2026-06-12T12:00:00Z")

        assert updated.completed_at_utc == "2026-06-12T12:00:00Z"

    def test_archive_sets_archived_at(self):
        """Archiving a campaign should set archived_at_utc."""
        campaign = create_campaign("test_001", "Test")
        campaign = start_campaign(campaign)
        campaign = complete_campaign(campaign)
        updated = archive_campaign(campaign, timestamp_utc="2026-06-12T14:00:00Z")

        assert updated.archived_at_utc == "2026-06-12T14:00:00Z"


class TestConstitutionalSemantics:
    """Tests ensuring lifecycle states are procedural, not advisory."""

    FORBIDDEN_ADVISORY_TERMS = {
        "successful",
        "failed",
        "approved",
        "validated",
        "optimal",
        "preferred",
        "best",
        "good",
        "bad",
        "quality",
        "grade",
        "verdict",
    }

    def test_lifecycle_states_are_procedural_not_advisory(self):
        """Lifecycle state values should be procedural, not advisory."""
        for state in CampaignLifecycleState:
            state_lower = state.value.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in state_lower, (
                    f"Lifecycle state '{state.value}' contains advisory term '{term}'"
                )

    def test_transition_does_not_imply_success_or_approval(self):
        """Completed state is procedural, not evaluative."""
        campaign = create_campaign("test_001", "Test")
        campaign = start_campaign(campaign)
        updated = complete_campaign(campaign)

        assert updated.lifecycle_state == "completed"
        d = updated.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in key_lower, (
                    f"Key '{key}' contains advisory term '{term}'"
                )

    def test_with_lifecycle_state_preserves_other_fields(self):
        """with_lifecycle_state should preserve all other campaign fields."""
        campaign = create_campaign(
            "test_001",
            "Test Campaign",
            description="Test description",
            tags=["test", "development"],
        )
        campaign = campaign.with_measurement("m001")
        campaign = campaign.with_revision("rev_001")

        updated = campaign.with_lifecycle_state("active")

        assert updated.campaign_id == "test_001"
        assert updated.title == "Test Campaign"
        assert updated.description == "Test description"
        assert "m001" in updated.measurement_ids
        assert "rev_001" in updated.revision_ids
        assert "test" in updated.tags
