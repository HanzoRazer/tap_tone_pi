# INSTRUMENT CLASS: MEASUREMENT
"""Tests for experiment campaign and revision contracts (Dev Order 87).

Tests cover:
- Campaign serialization
- Revision lineage
- Immutable updates
- Constitutional semantics (no advisory fields)
"""

import json

from tap_tone_pi.provenance.experiment_contracts import (
    ExperimentCampaignV1,
    ExperimentRevisionV1,
)


class TestExperimentCampaignSerialization:
    """Tests for ExperimentCampaignV1 serialization."""

    def test_campaign_serializes_to_dict(self):
        """Campaign should serialize to dict for JSON export."""
        campaign = ExperimentCampaignV1(
            campaign_id="brace_study_001",
            title="X-Brace Development Study",
            description="Testing asymmetric X-brace configurations",
            created_at_utc="2026-05-29T10:00:00Z",
        )
        d = campaign.to_dict()

        assert d["schema_version"] == "experiment_campaign_v1"
        assert d["campaign_id"] == "brace_study_001"
        assert d["title"] == "X-Brace Development Study"
        assert d["epistemic_status"] == "derived"

    def test_campaign_serializes_to_json(self):
        """Campaign dict should be JSON-serializable."""
        campaign = ExperimentCampaignV1(
            campaign_id="test_001",
            title="Test Campaign",
        )
        d = campaign.to_dict()
        json_str = json.dumps(d)

        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["campaign_id"] == "test_001"

    def test_empty_lists_excluded_from_dict(self):
        """Empty lists should not appear in serialized dict."""
        campaign = ExperimentCampaignV1(
            campaign_id="test",
            title="Test",
        )
        d = campaign.to_dict()

        assert "workflow_ids" not in d
        assert "revision_ids" not in d
        assert "measurement_ids" not in d
        assert "tags" not in d

    def test_populated_lists_included_in_dict(self):
        """Populated lists should appear in serialized dict."""
        campaign = ExperimentCampaignV1(
            campaign_id="test",
            title="Test",
            workflow_ids=("free_plate_tap_v1",),
            measurement_ids=("m001", "m002"),
            tags=("brace", "development"),
        )
        d = campaign.to_dict()

        assert d["workflow_ids"] == ["free_plate_tap_v1"]
        assert d["measurement_ids"] == ["m001", "m002"]
        assert d["tags"] == ["brace", "development"]


class TestExperimentCampaignImmutableUpdates:
    """Tests for immutable campaign updates."""

    def test_with_measurement_adds_measurement(self):
        """with_measurement should return new campaign with measurement added."""
        campaign = ExperimentCampaignV1(
            campaign_id="test",
            title="Test",
        )
        updated = campaign.with_measurement("m001")

        assert "m001" in updated.measurement_ids
        assert "m001" not in campaign.measurement_ids

    def test_with_measurement_is_idempotent(self):
        """Adding same measurement twice should not duplicate."""
        campaign = ExperimentCampaignV1(
            campaign_id="test",
            title="Test",
            measurement_ids=("m001",),
        )
        updated = campaign.with_measurement("m001")

        assert updated.measurement_ids == ("m001",)

    def test_with_revision_adds_revision(self):
        """with_revision should return new campaign with revision added."""
        campaign = ExperimentCampaignV1(
            campaign_id="test",
            title="Test",
        )
        updated = campaign.with_revision("rev_001")

        assert "rev_001" in updated.revision_ids

    def test_with_workflow_adds_workflow(self):
        """with_workflow should return new campaign with workflow added."""
        campaign = ExperimentCampaignV1(
            campaign_id="test",
            title="Test",
        )
        updated = campaign.with_workflow("free_plate_tap_v1")

        assert "free_plate_tap_v1" in updated.workflow_ids


class TestExperimentRevisionSerialization:
    """Tests for ExperimentRevisionV1 serialization."""

    def test_revision_serializes_to_dict(self):
        """Revision should serialize to dict for JSON export."""
        revision = ExperimentRevisionV1(
            revision_id="rev_002",
            parent_revision_id="rev_001",
            campaign_id="brace_study_001",
            notes="Increased scallop depth by 2mm",
        )
        d = revision.to_dict()

        assert d["schema_version"] == "experiment_revision_v1"
        assert d["revision_id"] == "rev_002"
        assert d["parent_revision_id"] == "rev_001"
        assert d["epistemic_status"] == "derived"

    def test_revision_serializes_to_json(self):
        """Revision dict should be JSON-serializable."""
        revision = ExperimentRevisionV1(revision_id="rev_001")
        d = revision.to_dict()
        json_str = json.dumps(d)

        assert len(json_str) > 0

    def test_optional_fields_excluded_when_none(self):
        """Optional fields should not appear when None."""
        revision = ExperimentRevisionV1(revision_id="rev_001")
        d = revision.to_dict()

        assert "parent_revision_id" not in d
        assert "campaign_id" not in d
        assert "notes" not in d
        assert "workflow_id" not in d


class TestExperimentRevisionLineage:
    """Tests for revision lineage tracking."""

    def test_revision_links_to_parent(self):
        """Revision should correctly link to parent."""
        parent = ExperimentRevisionV1(revision_id="rev_001")
        child = ExperimentRevisionV1(
            revision_id="rev_002",
            parent_revision_id="rev_001",
        )

        assert child.parent_revision_id == parent.revision_id

    def test_root_revision_has_no_parent(self):
        """Root revision should have no parent."""
        root = ExperimentRevisionV1(revision_id="rev_001")

        assert root.parent_revision_id is None

    def test_with_measurement_adds_to_revision(self):
        """with_measurement should add measurement to revision."""
        revision = ExperimentRevisionV1(revision_id="rev_001")
        updated = revision.with_measurement("m001")

        assert "m001" in updated.measurement_ids
        assert "m001" not in revision.measurement_ids


class TestConstitutionalSemantics:
    """Tests ensuring experimental structures contain no advisory semantics."""

    FORBIDDEN_ADVISORY_TERMS = {
        "best",
        "optimal",
        "recommended",
        "approved",
        "winner",
        "preferred",
        "improved",
        "better",
        "worse",
        "good",
        "bad",
        "acceptable",
        "unacceptable",
        "quality",
        "grade",
        "verdict",
        "pass",
        "fail",
    }

    def test_campaign_fields_are_advisory_free(self):
        """Campaign field names should not contain advisory terms."""
        campaign = ExperimentCampaignV1(
            campaign_id="test",
            title="Test",
        )
        d = campaign.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in key_lower, (
                    f"Campaign key '{key}' contains advisory term '{term}'"
                )

    def test_revision_fields_are_advisory_free(self):
        """Revision field names should not contain advisory terms."""
        revision = ExperimentRevisionV1(
            revision_id="rev_001",
            parent_revision_id="rev_000",
        )
        d = revision.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in key_lower, (
                    f"Revision key '{key}' contains advisory term '{term}'"
                )

    def test_epistemic_status_is_derived(self):
        """Both campaign and revision epistemic_status should be 'derived'."""
        campaign = ExperimentCampaignV1(campaign_id="test", title="Test")
        revision = ExperimentRevisionV1(revision_id="rev_001")

        assert campaign.epistemic_status == "derived"
        assert revision.epistemic_status == "derived"

    def test_schema_versions_are_present(self):
        """Both campaign and revision must include schema_version."""
        campaign = ExperimentCampaignV1(campaign_id="test", title="Test")
        revision = ExperimentRevisionV1(revision_id="rev_001")

        assert campaign.schema_version == "experiment_campaign_v1"
        assert revision.schema_version == "experiment_revision_v1"
