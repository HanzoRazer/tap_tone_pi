# INSTRUMENT CLASS: MEASUREMENT
"""Tests for build session, environment, and fixture provenance (Dev Order 88).

Tests cover:
- BuildSessionV1 serialization and lineage
- EnvironmentRecordV1 serialization
- FixtureRecordV1 serialization
- MeasurementLineageV1 fixture/environment extensions
- Constitutional semantics (no advisory fields)
"""

import pytest
import json

from tap_tone_pi.provenance import (
    BuildSessionV1,
    EnvironmentRecordV1,
    FixtureRecordV1,
    MeasurementLineageV1,
    ExperimentCampaignV1,
    create_build_session,
    create_environment_record,
    create_fixture_record,
    create_measurement_lineage,
    add_campaign_to_build_session,
    link_measurement_to_context,
)


class TestBuildSessionSerialization:
    """Tests for BuildSessionV1 serialization."""

    def test_build_session_serializes_to_dict(self):
        """Build session should serialize to dict for JSON export."""
        session = BuildSessionV1(
            build_session_id="guitar_47",
            specimen_id="SPRUCE_TOP_001",
            specimen_type="guitar_top",
            description="Engelmann spruce top for classical build",
            created_at_utc="2026-06-01T10:00:00Z",
        )
        d = session.to_dict()

        assert d["schema_version"] == "build_session_v1"
        assert d["build_session_id"] == "guitar_47"
        assert d["specimen_id"] == "SPRUCE_TOP_001"
        assert d["epistemic_status"] == "derived"

    def test_build_session_serializes_to_json(self):
        """Build session dict should be JSON-serializable."""
        session = create_build_session("test_001", "SPECIMEN_001")
        d = session.to_dict()
        json_str = json.dumps(d)

        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["build_session_id"] == "test_001"

    def test_empty_lists_excluded_from_dict(self):
        """Empty lists should not appear in serialized dict."""
        session = create_build_session("test", "SPECIMEN")
        d = session.to_dict()

        assert "campaign_ids" not in d
        assert "tags" not in d

    def test_with_campaign_adds_campaign(self):
        """with_campaign should return new session with campaign added."""
        session = create_build_session("test", "SPECIMEN")
        updated = session.with_campaign("brace_study_001")

        assert "brace_study_001" in updated.campaign_ids
        assert "brace_study_001" not in session.campaign_ids

    def test_add_campaign_helper(self):
        """add_campaign_to_build_session helper should work."""
        session = create_build_session("test", "SPECIMEN")
        updated = add_campaign_to_build_session(session, "brace_study_001")

        assert "brace_study_001" in updated.campaign_ids


class TestEnvironmentRecordSerialization:
    """Tests for EnvironmentRecordV1 serialization."""

    def test_environment_serializes_to_dict(self):
        """Environment record should serialize to dict."""
        env = EnvironmentRecordV1(
            environment_id="env_001",
            recorded_at_utc="2026-06-01T10:00:00Z",
            temperature_c=22.5,
            humidity_pct=45.0,
            room_id="shop_main",
            ambient_noise_dbfs=-40.0,
        )
        d = env.to_dict()

        assert d["schema_version"] == "environment_record_v1"
        assert d["environment_id"] == "env_001"
        assert d["temperature_c"] == 22.5
        assert d["humidity_pct"] == 45.0
        assert d["room_id"] == "shop_main"
        assert d["ambient_noise_dbfs"] == -40.0

    def test_environment_serializes_to_json(self):
        """Environment dict should be JSON-serializable."""
        env = create_environment_record(
            "env_001",
            "2026-06-01T10:00:00Z",
            temperature_c=22.5,
        )
        d = env.to_dict()
        json_str = json.dumps(d)

        assert len(json_str) > 0

    def test_optional_fields_excluded_when_none(self):
        """Optional fields should not appear when None."""
        env = create_environment_record("env_001", "2026-06-01T10:00:00Z")
        d = env.to_dict()

        assert "temperature_c" not in d
        assert "humidity_pct" not in d
        assert "room_id" not in d
        assert "ambient_noise_dbfs" not in d


class TestFixtureRecordSerialization:
    """Tests for FixtureRecordV1 serialization."""

    def test_fixture_serializes_to_dict(self):
        """Fixture record should serialize to dict."""
        fixture = FixtureRecordV1(
            fixture_id="free_plate_jig_001",
            support_condition="free",
            fixture_type="foam_blocks",
            mic_position="center",
            tap_position="antinode",
            excitation_method="tap",
        )
        d = fixture.to_dict()

        assert d["schema_version"] == "fixture_record_v1"
        assert d["fixture_id"] == "free_plate_jig_001"
        assert d["support_condition"] == "free"
        assert d["fixture_type"] == "foam_blocks"

    def test_fixture_serializes_to_json(self):
        """Fixture dict should be JSON-serializable."""
        fixture = create_fixture_record(
            "fixture_001",
            support_condition="clamped",
        )
        d = fixture.to_dict()
        json_str = json.dumps(d)

        assert len(json_str) > 0

    def test_optional_fields_excluded_when_none(self):
        """Optional fields should not appear when None."""
        fixture = create_fixture_record("fixture_001")
        d = fixture.to_dict()

        assert "support_condition" not in d
        assert "fixture_type" not in d
        assert "mic_position" not in d


class TestMeasurementLineageExtensions:
    """Tests for DO-88 extensions to MeasurementLineageV1."""

    def test_lineage_includes_fixture_id(self):
        """MeasurementLineageV1 should support fixture_id."""
        lineage = create_measurement_lineage(
            "m001",
            fixture_id="fixture_001",
        )

        assert lineage.fixture_id == "fixture_001"
        assert lineage.to_dict()["fixture_id"] == "fixture_001"

    def test_lineage_includes_environment_id(self):
        """MeasurementLineageV1 should support environment_id."""
        lineage = create_measurement_lineage(
            "m001",
            environment_id="env_001",
        )

        assert lineage.environment_id == "env_001"
        assert lineage.to_dict()["environment_id"] == "env_001"

    def test_with_fixture_helper(self):
        """with_fixture should set fixture_id."""
        lineage = MeasurementLineageV1(measurement_id="m001")
        updated = lineage.with_fixture("fixture_001")

        assert updated.fixture_id == "fixture_001"

    def test_with_environment_helper(self):
        """with_environment should set environment_id."""
        lineage = MeasurementLineageV1(measurement_id="m001")
        updated = lineage.with_environment("env_001")

        assert updated.environment_id == "env_001"

    def test_has_experimental_context_includes_fixture(self):
        """has_experimental_context should include fixture_id."""
        orphan = MeasurementLineageV1(measurement_id="m001")
        with_fixture = MeasurementLineageV1(
            measurement_id="m002",
            fixture_id="fixture_001",
        )

        assert orphan.has_experimental_context() is False
        assert with_fixture.has_experimental_context() is True

    def test_has_experimental_context_includes_environment(self):
        """has_experimental_context should include environment_id."""
        with_env = MeasurementLineageV1(
            measurement_id="m001",
            environment_id="env_001",
        )

        assert with_env.has_experimental_context() is True

    def test_link_measurement_with_fixture_and_environment(self):
        """link_measurement_to_context should support fixture and environment."""
        fixture = create_fixture_record("fixture_001", support_condition="free")
        environment = create_environment_record(
            "env_001",
            "2026-06-01T10:00:00Z",
            temperature_c=22.5,
        )

        lineage = link_measurement_to_context(
            "m001",
            fixture=fixture,
            environment=environment,
        )

        assert lineage.fixture_id == "fixture_001"
        assert lineage.environment_id == "env_001"


class TestCampaignBuildSessionLink:
    """Tests for campaign-to-build-session linkage."""

    def test_campaign_includes_build_session_id(self):
        """ExperimentCampaignV1 should support build_session_id."""
        campaign = ExperimentCampaignV1(
            campaign_id="brace_study_001",
            title="X-Brace Study",
            build_session_id="guitar_47",
        )

        assert campaign.build_session_id == "guitar_47"
        assert campaign.to_dict()["build_session_id"] == "guitar_47"

    def test_with_build_session_helper(self):
        """with_build_session should link campaign to build session."""
        campaign = ExperimentCampaignV1(
            campaign_id="brace_study_001",
            title="X-Brace Study",
        )
        updated = campaign.with_build_session("guitar_47")

        assert updated.build_session_id == "guitar_47"
        assert campaign.build_session_id is None


class TestConstitutionalSemantics:
    """Tests ensuring DO-88 structures contain no advisory semantics."""

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

    def test_build_session_fields_are_advisory_free(self):
        """Build session field names should not contain advisory terms."""
        session = create_build_session(
            "test",
            "SPECIMEN",
            specimen_type="guitar_top",
            tags=["development"],
        )
        d = session.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in key_lower, (
                    f"Build session key '{key}' contains advisory term '{term}'"
                )

    def test_environment_fields_are_advisory_free(self):
        """Environment record field names should not contain advisory terms."""
        env = create_environment_record(
            "env_001",
            "2026-06-01T10:00:00Z",
            temperature_c=22.5,
            humidity_pct=45.0,
            room_id="shop",
            ambient_noise_dbfs=-40.0,
        )
        d = env.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in key_lower, (
                    f"Environment key '{key}' contains advisory term '{term}'"
                )

    def test_fixture_fields_are_advisory_free(self):
        """Fixture record field names should not contain advisory terms."""
        fixture = create_fixture_record(
            "fixture_001",
            support_condition="free",
            fixture_type="foam_blocks",
            mic_position="center",
            tap_position="antinode",
            excitation_method="tap",
        )
        d = fixture.to_dict()

        for key in d.keys():
            key_lower = key.lower()
            for term in self.FORBIDDEN_ADVISORY_TERMS:
                assert term not in key_lower, (
                    f"Fixture key '{key}' contains advisory term '{term}'"
                )

    def test_all_epistemic_status_are_derived(self):
        """All DO-88 types epistemic_status should be 'derived'."""
        session = create_build_session("test", "SPECIMEN")
        env = create_environment_record("env", "2026-06-01T10:00:00Z")
        fixture = create_fixture_record("fixture")

        assert session.epistemic_status == "derived"
        assert env.epistemic_status == "derived"
        assert fixture.epistemic_status == "derived"

    def test_schema_versions_are_present(self):
        """All DO-88 types must include schema_version."""
        session = create_build_session("test", "SPECIMEN")
        env = create_environment_record("env", "2026-06-01T10:00:00Z")
        fixture = create_fixture_record("fixture")

        assert session.schema_version == "build_session_v1"
        assert env.schema_version == "environment_record_v1"
        assert fixture.schema_version == "fixture_record_v1"
