# INSTRUMENT CLASS: MEASUREMENT
"""Export anchor test for experiment provenance (Dev Order 87, PR 87G).

Validates that experiment_campaign, experiment_revision, and measurement_lineage
blocks serialize correctly and contain no advisory semantics.
"""

import json

from tap_tone_pi.provenance import (
    create_campaign,
    create_revision,
    create_measurement_lineage,
)


class TestExperimentExportAnchor:
    """Validates experiment provenance exports are well-formed and advisory-free."""

    FORBIDDEN_ADVISORY_KEYS = {
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

    def test_campaign_dict_is_json_serializable(self):
        """Campaign.to_dict() must produce valid JSON."""
        campaign = create_campaign(
            "brace_study_001",
            "X-Brace Development Study",
            description="Testing asymmetric configurations",
            created_at_utc="2026-05-29T10:00:00Z",
            tags=["brace", "development"],
        )
        d = campaign.to_dict()

        json_str = json.dumps(d)
        parsed = json.loads(json_str)

        assert parsed["schema_version"] == "experiment_campaign_v1"
        assert parsed["campaign_id"] == "brace_study_001"

    def test_revision_dict_is_json_serializable(self):
        """Revision.to_dict() must produce valid JSON."""
        revision = create_revision(
            "rev_002",
            parent_revision_id="rev_001",
            campaign_id="brace_study_001",
            notes="Increased scallop depth by 2mm",
        )
        d = revision.to_dict()

        json_str = json.dumps(d)
        parsed = json.loads(json_str)

        assert parsed["schema_version"] == "experiment_revision_v1"
        assert parsed["revision_id"] == "rev_002"
        assert parsed["parent_revision_id"] == "rev_001"

    def test_lineage_dict_is_json_serializable(self):
        """Lineage.to_dict() must produce valid JSON."""
        lineage = create_measurement_lineage(
            "m001",
            workflow_id="free_plate_tap_v1",
            revision_id="rev_002",
            campaign_id="brace_study_001",
        )
        d = lineage.to_dict()

        json_str = json.dumps(d)
        parsed = json.loads(json_str)

        assert parsed["schema_version"] == "measurement_lineage_v1"
        assert parsed["measurement_id"] == "m001"

    def test_campaign_keys_are_advisory_free(self):
        """Campaign dict keys must not contain advisory terminology."""
        campaign = create_campaign(
            "test",
            "Test",
            tags=["test"],
        )
        campaign = campaign.with_measurement("m001")
        campaign = campaign.with_revision("rev_001")
        d = campaign.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_KEYS:
                assert term not in key_lower, (
                    f"Campaign key '{key}' contains advisory term '{term}'"
                )

    def test_revision_keys_are_advisory_free(self):
        """Revision dict keys must not contain advisory terminology."""
        revision = create_revision(
            "rev_002",
            parent_revision_id="rev_001",
            campaign_id="test",
            workflow_id="free_plate_tap_v1",
            notes="Test notes",
        )
        d = revision.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_KEYS:
                assert term not in key_lower, (
                    f"Revision key '{key}' contains advisory term '{term}'"
                )

    def test_lineage_keys_are_advisory_free(self):
        """Lineage dict keys must not contain advisory terminology."""
        lineage = create_measurement_lineage(
            "m001",
            workflow_id="free_plate_tap_v1",
            revision_id="rev_001",
            campaign_id="test",
            notes="Test notes",
        )
        d = lineage.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_KEYS:
                assert term not in key_lower, (
                    f"Lineage key '{key}' contains advisory term '{term}'"
                )

    def test_all_epistemic_status_are_derived(self):
        """All experiment provenance epistemic_status must be 'derived'."""
        campaign = create_campaign("test", "Test")
        revision = create_revision("rev_001")
        lineage = create_measurement_lineage("m001")

        assert campaign.epistemic_status == "derived"
        assert revision.epistemic_status == "derived"
        assert lineage.epistemic_status == "derived"

        assert campaign.to_dict()["epistemic_status"] == "derived"
        assert revision.to_dict()["epistemic_status"] == "derived"
        assert lineage.to_dict()["epistemic_status"] == "derived"

    def test_schema_versions_are_present(self):
        """All experiment provenance must include schema_version."""
        campaign = create_campaign("test", "Test")
        revision = create_revision("rev_001")
        lineage = create_measurement_lineage("m001")

        assert "schema_version" in campaign.to_dict()
        assert "schema_version" in revision.to_dict()
        assert "schema_version" in lineage.to_dict()

        assert campaign.to_dict()["schema_version"] == "experiment_campaign_v1"
        assert revision.to_dict()["schema_version"] == "experiment_revision_v1"
        assert lineage.to_dict()["schema_version"] == "measurement_lineage_v1"

    def test_optional_blocks_are_additive(self):
        """Export blocks should be optional and additive."""
        campaign = create_campaign("test", "Test")
        revision = create_revision("rev_001")
        lineage = create_measurement_lineage("m001")

        campaign_dict = campaign.to_dict()
        revision_dict = revision.to_dict()
        lineage_dict = lineage.to_dict()

        assert "workflow_ids" not in campaign_dict
        assert "measurement_ids" not in campaign_dict
        assert "parent_revision_id" not in revision_dict
        assert "workflow_id" not in lineage_dict
