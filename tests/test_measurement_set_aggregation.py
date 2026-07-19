# INSTRUMENT CLASS: MEASUREMENT
"""Tests for measurement set aggregation (Dev Order 89).

Tests cover:
- Measurement set creation
- Collection by campaign/revision/workflow
- Summary statistics computation
- Empty set handling
- Constitutional semantics (no advisory fields)
"""

import pytest
import json

from tap_tone_pi.provenance import (
    MeasurementSetV1,
    CampaignLifecycleExportV1,
    create_campaign,
    create_measurement_lineage,
    create_measurement_set,
    collect_measurements_for_campaign,
    collect_measurements_for_revision,
    collect_measurements_for_workflow,
    summarize_measurement_set,
    start_campaign,
    complete_campaign,
)


class TestMeasurementSetCreation:
    """Tests for MeasurementSetV1 creation."""

    def test_create_measurement_set_minimal(self):
        """create_measurement_set with minimal args should work."""
        mset = create_measurement_set("set_001", ["m001", "m002"])

        assert mset.measurement_set_id == "set_001"
        assert mset.measurement_count == 2
        assert "m001" in mset.measurement_ids

    def test_create_measurement_set_full(self):
        """create_measurement_set with all args should work."""
        mset = create_measurement_set(
            "set_001",
            ["m001", "m002", "m003"],
            campaign_id="brace_study_001",
            revision_id="rev_002",
            workflow_id="free_plate_tap_v1",
            notes="Test measurement set",
        )

        assert mset.measurement_set_id == "set_001"
        assert mset.campaign_id == "brace_study_001"
        assert mset.revision_id == "rev_002"
        assert mset.workflow_id == "free_plate_tap_v1"
        assert mset.measurement_count == 3

    def test_measurement_set_serializes_to_dict(self):
        """MeasurementSetV1 should serialize to dict."""
        mset = create_measurement_set(
            "set_001",
            ["m001", "m002"],
            campaign_id="test",
        )
        d = mset.to_dict()

        assert d["schema_version"] == "measurement_set_v1"
        assert d["measurement_set_id"] == "set_001"
        assert d["epistemic_status"] == "derived"

    def test_measurement_set_serializes_to_json(self):
        """MeasurementSetV1 dict should be JSON-serializable."""
        mset = create_measurement_set("set_001", ["m001"])
        d = mset.to_dict()
        json_str = json.dumps(d)

        assert len(json_str) > 0

    def test_with_measurement_adds_measurement(self):
        """with_measurement should add to measurement set."""
        mset = MeasurementSetV1(measurement_set_id="set_001")
        updated = mset.with_measurement("m001")

        assert "m001" in updated.measurement_ids
        assert updated.measurement_count == 1


class TestCollectMeasurements:
    """Tests for measurement collection helpers."""

    def test_collect_measurements_for_campaign(self):
        """collect_measurements_for_campaign should filter by campaign_id."""
        lineages = [
            create_measurement_lineage("m001", campaign_id="campaign_a"),
            create_measurement_lineage("m002", campaign_id="campaign_a"),
            create_measurement_lineage("m003", campaign_id="campaign_b"),
            create_measurement_lineage("m004"),  # No campaign
        ]

        mset = collect_measurements_for_campaign(lineages, "campaign_a")

        assert mset.measurement_count == 2
        assert "m001" in mset.measurement_ids
        assert "m002" in mset.measurement_ids
        assert "m003" not in mset.measurement_ids

    def test_collect_measurements_for_revision(self):
        """collect_measurements_for_revision should filter by revision_id."""
        lineages = [
            create_measurement_lineage("m001", revision_id="rev_001", campaign_id="c1"),
            create_measurement_lineage("m002", revision_id="rev_001"),
            create_measurement_lineage("m003", revision_id="rev_002"),
        ]

        mset = collect_measurements_for_revision(lineages, "rev_001")

        assert mset.measurement_count == 2
        assert mset.revision_id == "rev_001"
        assert mset.campaign_id == "c1"

    def test_collect_measurements_for_workflow(self):
        """collect_measurements_for_workflow should filter by workflow_id."""
        lineages = [
            create_measurement_lineage("m001", workflow_id="free_plate_tap_v1"),
            create_measurement_lineage("m002", workflow_id="free_plate_tap_v1"),
            create_measurement_lineage("m003", workflow_id="transfer_function_v1"),
        ]

        mset = collect_measurements_for_workflow(lineages, "free_plate_tap_v1")

        assert mset.measurement_count == 2
        assert mset.workflow_id == "free_plate_tap_v1"


class TestEmptyMeasurementSet:
    """Tests for empty measurement set handling."""

    def test_empty_measurement_set_is_valid(self):
        """Empty measurement set should be valid."""
        mset = create_measurement_set("set_empty", [])

        assert mset.measurement_count == 0
        assert mset.measurement_ids == ()

    def test_collect_returns_empty_set_when_no_matches(self):
        """Collection with no matches should return empty set."""
        lineages = [
            create_measurement_lineage("m001", campaign_id="other"),
        ]

        mset = collect_measurements_for_campaign(lineages, "nonexistent")

        assert mset.measurement_count == 0

    def test_summarize_empty_set_no_stats(self):
        """Summarizing empty set should have no stats."""
        mset = create_measurement_set("set_empty", [])
        summary = summarize_measurement_set(mset)

        assert summary.measurement_count == 0
        assert summary.dominant_frequency_mean_hz is None
        assert summary.repeatability_score_mean is None


class TestMeasurementSetSummary:
    """Tests for MeasurementSetSummaryV1 computation."""

    def test_summary_computes_frequency_stats(self):
        """summarize_measurement_set should compute frequency statistics."""
        mset = create_measurement_set("set_001", ["m001", "m002", "m003"])
        summary = summarize_measurement_set(
            mset,
            dominant_frequencies_hz=[220.0, 222.0, 224.0],
        )

        assert summary.measurement_count == 3
        assert summary.dominant_frequency_mean_hz == pytest.approx(222.0, rel=0.01)
        assert summary.dominant_frequency_std_hz == pytest.approx(2.0, rel=0.01)
        assert summary.dominant_frequency_min_hz == 220.0
        assert summary.dominant_frequency_max_hz == 224.0

    def test_summary_computes_repeatability_stats(self):
        """summarize_measurement_set should compute repeatability statistics."""
        mset = create_measurement_set("set_001", ["m001", "m002", "m003"])
        summary = summarize_measurement_set(
            mset,
            repeatability_scores=[0.9, 0.85, 0.95],
        )

        assert summary.repeatability_score_mean == pytest.approx(0.9, rel=0.01)
        assert summary.repeatability_score_min == 0.85
        assert summary.repeatability_score_max == 0.95

    def test_summary_serializes_to_dict(self):
        """MeasurementSetSummaryV1 should serialize to dict."""
        mset = create_measurement_set("set_001", ["m001"])
        summary = summarize_measurement_set(
            mset,
            dominant_frequencies_hz=[220.0],
        )
        d = summary.to_dict()

        assert d["schema_version"] == "measurement_set_summary_v1"
        assert d["measurement_count"] == 1
        assert "dominant_frequency_mean_hz" in d

    def test_summary_serializes_to_json(self):
        """MeasurementSetSummaryV1 dict should be JSON-serializable."""
        mset = create_measurement_set("set_001", ["m001"])
        summary = summarize_measurement_set(mset)
        d = summary.to_dict()
        json_str = json.dumps(d)

        assert len(json_str) > 0


class TestCampaignLifecycleExport:
    """Tests for CampaignLifecycleExportV1."""

    def test_lifecycle_export_from_campaign(self):
        """CampaignLifecycleExportV1.from_campaign should extract lifecycle."""
        campaign = create_campaign("test_001", "Test")
        campaign = start_campaign(campaign, timestamp_utc="2026-06-12T10:00:00Z")
        campaign = complete_campaign(campaign, timestamp_utc="2026-06-12T12:00:00Z")

        export = CampaignLifecycleExportV1.from_campaign(campaign)

        assert export.campaign_id == "test_001"
        assert export.lifecycle_state == "completed"
        assert export.started_at_utc == "2026-06-12T10:00:00Z"
        assert export.completed_at_utc == "2026-06-12T12:00:00Z"

    def test_lifecycle_export_serializes_to_dict(self):
        """CampaignLifecycleExportV1 should serialize to dict."""
        export = CampaignLifecycleExportV1(
            campaign_id="test_001",
            lifecycle_state="active",
            started_at_utc="2026-06-12T10:00:00Z",
        )
        d = export.to_dict()

        assert d["schema_version"] == "campaign_lifecycle_v1"
        assert d["campaign_id"] == "test_001"
        assert d["lifecycle_state"] == "active"

    def test_lifecycle_export_omits_none_timestamps(self):
        """CampaignLifecycleExportV1 should omit None timestamps."""
        export = CampaignLifecycleExportV1(
            campaign_id="test_001",
            lifecycle_state="planned",
        )
        d = export.to_dict()

        assert "started_at_utc" not in d
        assert "completed_at_utc" not in d
        assert "archived_at_utc" not in d


class TestConstitutionalSemantics:
    """Tests ensuring aggregation contains no advisory semantics."""

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
        "success",
    }

    def test_measurement_set_fields_are_advisory_free(self):
        """MeasurementSetV1 field names should not contain advisory terms."""
        mset = create_measurement_set(
            "set_001",
            ["m001", "m002"],
            campaign_id="test",
            notes="Test notes",
        )
        d = mset.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in key_lower, (
                    f"MeasurementSetV1 key '{key}' contains advisory term '{term}'"
                )

    def test_measurement_set_summary_contains_no_advisory_fields(self):
        """MeasurementSetSummaryV1 should not contain advisory fields."""
        mset = create_measurement_set("set_001", ["m001"])
        summary = summarize_measurement_set(
            mset,
            dominant_frequencies_hz=[220.0],
            repeatability_scores=[0.9],
        )
        d = summary.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in key_lower, (
                    f"Summary key '{key}' contains advisory term '{term}'"
                )

    def test_lifecycle_export_fields_are_advisory_free(self):
        """CampaignLifecycleExportV1 should not contain advisory fields."""
        export = CampaignLifecycleExportV1(
            campaign_id="test",
            lifecycle_state="completed",
        )
        d = export.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in key_lower, (
                    f"Lifecycle export key '{key}' contains advisory term '{term}'"
                )

    def test_all_epistemic_status_are_derived(self):
        """All DO-89 types epistemic_status should be 'derived'."""
        mset = create_measurement_set("set_001", [])
        summary = summarize_measurement_set(mset)
        export = CampaignLifecycleExportV1(
            campaign_id="test", lifecycle_state="planned"
        )

        assert mset.epistemic_status == "derived"
        assert summary.epistemic_status == "derived"
        assert export.epistemic_status == "derived"
