# INSTRUMENT CLASS: MEASUREMENT
"""Tests for experiment lineage helpers and measurement links (Dev Order 87).

Tests cover:
- Campaign creation and manipulation
- Revision creation and lineage chains
- Measurement lineage linkage
- Constitutional semantics
"""

import pytest
import json

from tap_tone_pi.provenance.experiment_contracts import (
    ExperimentCampaignV1,
    ExperimentRevisionV1,
)
from tap_tone_pi.provenance.measurement_links import MeasurementLineageV1
from tap_tone_pi.provenance.lineage import (
    create_campaign,
    create_revision,
    create_measurement_lineage,
    add_measurement_to_campaign,
    add_revision_to_campaign,
    add_workflow_to_campaign,
    add_measurement_to_revision,
    get_campaign_measurements,
    get_revision_chain,
    link_measurement_to_context,
)


class TestCampaignHelpers:
    """Tests for campaign creation and manipulation helpers."""

    def test_create_campaign_minimal(self):
        """create_campaign with minimal args should work."""
        campaign = create_campaign("test_001", "Test Campaign")

        assert campaign.campaign_id == "test_001"
        assert campaign.title == "Test Campaign"
        assert campaign.description is None

    def test_create_campaign_full(self):
        """create_campaign with all args should work."""
        campaign = create_campaign(
            "brace_study_001",
            "X-Brace Development",
            description="Testing asymmetric configurations",
            created_at_utc="2026-05-29T10:00:00Z",
            tags=["brace", "development"],
        )

        assert campaign.campaign_id == "brace_study_001"
        assert campaign.title == "X-Brace Development"
        assert campaign.description == "Testing asymmetric configurations"
        assert "brace" in campaign.tags

    def test_add_measurement_to_campaign(self):
        """add_measurement_to_campaign should return updated campaign."""
        campaign = create_campaign("test", "Test")
        updated = add_measurement_to_campaign(campaign, "m001")

        assert "m001" in updated.measurement_ids
        assert "m001" not in campaign.measurement_ids

    def test_add_revision_to_campaign(self):
        """add_revision_to_campaign should return updated campaign."""
        campaign = create_campaign("test", "Test")
        updated = add_revision_to_campaign(campaign, "rev_001")

        assert "rev_001" in updated.revision_ids

    def test_add_workflow_to_campaign(self):
        """add_workflow_to_campaign should return updated campaign."""
        campaign = create_campaign("test", "Test")
        updated = add_workflow_to_campaign(campaign, "free_plate_tap_v1")

        assert "free_plate_tap_v1" in updated.workflow_ids

    def test_get_campaign_measurements(self):
        """get_campaign_measurements should return measurement IDs."""
        campaign = create_campaign("test", "Test")
        campaign = add_measurement_to_campaign(campaign, "m001")
        campaign = add_measurement_to_campaign(campaign, "m002")

        measurements = get_campaign_measurements(campaign)

        assert measurements == ("m001", "m002")


class TestRevisionHelpers:
    """Tests for revision creation and lineage helpers."""

    def test_create_revision_minimal(self):
        """create_revision with minimal args should work."""
        revision = create_revision("rev_001")

        assert revision.revision_id == "rev_001"
        assert revision.parent_revision_id is None

    def test_create_revision_with_parent(self):
        """create_revision with parent should link correctly."""
        revision = create_revision(
            "rev_002",
            parent_revision_id="rev_001",
        )

        assert revision.revision_id == "rev_002"
        assert revision.parent_revision_id == "rev_001"

    def test_create_revision_full(self):
        """create_revision with all args should work."""
        revision = create_revision(
            "rev_002",
            parent_revision_id="rev_001",
            campaign_id="brace_study_001",
            workflow_id="free_plate_tap_v1",
            notes="Increased scallop depth",
            created_at_utc="2026-05-29T11:00:00Z",
        )

        assert revision.revision_id == "rev_002"
        assert revision.parent_revision_id == "rev_001"
        assert revision.campaign_id == "brace_study_001"
        assert revision.workflow_id == "free_plate_tap_v1"
        assert revision.notes == "Increased scallop depth"

    def test_add_measurement_to_revision(self):
        """add_measurement_to_revision should return updated revision."""
        revision = create_revision("rev_001")
        updated = add_measurement_to_revision(revision, "m001")

        assert "m001" in updated.measurement_ids

    def test_get_revision_chain(self):
        """get_revision_chain should return lineage back to root."""
        rev1 = create_revision("rev_001")
        rev2 = create_revision("rev_002", parent_revision_id="rev_001")
        rev3 = create_revision("rev_003", parent_revision_id="rev_002")

        lookup = {
            "rev_001": rev1,
            "rev_002": rev2,
            "rev_003": rev3,
        }

        chain = get_revision_chain(rev3, lookup)

        assert len(chain) == 3
        assert chain[0].revision_id == "rev_003"
        assert chain[1].revision_id == "rev_002"
        assert chain[2].revision_id == "rev_001"

    def test_get_revision_chain_single(self):
        """get_revision_chain for root revision should return single item."""
        rev1 = create_revision("rev_001")
        lookup = {"rev_001": rev1}

        chain = get_revision_chain(rev1, lookup)

        assert len(chain) == 1
        assert chain[0].revision_id == "rev_001"


class TestMeasurementLineage:
    """Tests for measurement lineage linkage."""

    def test_create_measurement_lineage_minimal(self):
        """create_measurement_lineage with minimal args should work."""
        lineage = create_measurement_lineage("m001")

        assert lineage.measurement_id == "m001"
        assert lineage.workflow_id is None
        assert lineage.revision_id is None
        assert lineage.campaign_id is None

    def test_create_measurement_lineage_full(self):
        """create_measurement_lineage with all args should work."""
        lineage = create_measurement_lineage(
            "m001",
            workflow_id="free_plate_tap_v1",
            revision_id="rev_002",
            campaign_id="brace_study_001",
            notes="Top plate measurement",
            created_at_utc="2026-05-29T12:00:00Z",
        )

        assert lineage.measurement_id == "m001"
        assert lineage.workflow_id == "free_plate_tap_v1"
        assert lineage.revision_id == "rev_002"
        assert lineage.campaign_id == "brace_study_001"

    def test_measurement_lineage_has_context(self):
        """has_experimental_context should detect context."""
        orphan = MeasurementLineageV1(measurement_id="m001")
        with_workflow = MeasurementLineageV1(
            measurement_id="m002",
            workflow_id="free_plate_tap_v1",
        )

        assert orphan.has_experimental_context() is False
        assert with_workflow.has_experimental_context() is True

    def test_measurement_lineage_with_helpers(self):
        """Lineage with_ helpers should work."""
        lineage = MeasurementLineageV1(measurement_id="m001")

        lineage = lineage.with_workflow("free_plate_tap_v1")
        lineage = lineage.with_revision("rev_001")
        lineage = lineage.with_campaign("brace_study_001")

        assert lineage.workflow_id == "free_plate_tap_v1"
        assert lineage.revision_id == "rev_001"
        assert lineage.campaign_id == "brace_study_001"

    def test_measurement_lineage_serializes(self):
        """MeasurementLineageV1 should serialize to JSON."""
        lineage = create_measurement_lineage(
            "m001",
            workflow_id="free_plate_tap_v1",
            campaign_id="brace_study_001",
        )
        d = lineage.to_dict()
        json_str = json.dumps(d)

        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["measurement_id"] == "m001"
        assert parsed["schema_version"] == "measurement_lineage_v1"


class TestLinkMeasurementToContext:
    """Tests for link_measurement_to_context convenience function."""

    def test_link_from_revision(self):
        """link_measurement_to_context should extract from revision."""
        revision = create_revision(
            "rev_002",
            campaign_id="brace_study_001",
        )
        lineage = link_measurement_to_context(
            "m001",
            revision=revision,
        )

        assert lineage.measurement_id == "m001"
        assert lineage.revision_id == "rev_002"
        assert lineage.campaign_id == "brace_study_001"

    def test_link_from_campaign(self):
        """link_measurement_to_context should extract from campaign."""
        campaign = create_campaign("brace_study_001", "Brace Study")
        lineage = link_measurement_to_context(
            "m001",
            campaign=campaign,
        )

        assert lineage.measurement_id == "m001"
        assert lineage.campaign_id == "brace_study_001"

    def test_link_with_workflow(self):
        """link_measurement_to_context should include workflow."""
        lineage = link_measurement_to_context(
            "m001",
            workflow_id="free_plate_tap_v1",
        )

        assert lineage.workflow_id == "free_plate_tap_v1"


class TestMeasurementLineageConstitutionalSemantics:
    """Tests for measurement lineage constitutional compliance."""

    FORBIDDEN_ADVISORY_TERMS = {
        "best",
        "optimal",
        "recommended",
        "approved",
        "winner",
        "preferred",
        "improved",
        "good",
        "bad",
        "quality",
        "grade",
        "verdict",
        "pass",
        "fail",
    }

    def test_lineage_fields_are_advisory_free(self):
        """Lineage field names should not contain advisory terms."""
        lineage = create_measurement_lineage(
            "m001",
            workflow_id="free_plate_tap_v1",
            revision_id="rev_001",
            campaign_id="brace_study_001",
        )
        d = lineage.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in key_lower, (
                    f"Lineage key '{key}' contains advisory term '{term}'"
                )

    def test_lineage_epistemic_status_is_derived(self):
        """Measurement lineage epistemic_status should be 'derived'."""
        lineage = create_measurement_lineage("m001")

        assert lineage.epistemic_status == "derived"

    def test_lineage_schema_version_present(self):
        """Measurement lineage must include schema_version."""
        lineage = create_measurement_lineage("m001")

        assert lineage.schema_version == "measurement_lineage_v1"
