"""
Unit tests for tap_tone_pi agentic contracts.

Tests contract creation, serialization, and cross-repo compatibility.
"""

import json
import tempfile
from pathlib import Path

import pytest

from tap_tone_pi.agentic import (
    # Contracts
    ToolCapabilityV1,
    CapabilityAction,
    SafeDefaults,
    AttentionDirectiveV1,
    AttentionAction,
    FocusTarget,
    AgentEventV1,
    EventType,
    EventSource,
    # Capabilities
    get_capabilities,
    get_capability_by_id,
    TAP_TONE_ANALYZER,
    WOLF_DETECTOR,
    # Events
    emit_event,
    emit_analysis_started,
    emit_analysis_completed,
    emit_analysis_failed,
    emit_attention_requested,
)
from tap_tone_pi.agentic.events import (
    create_wolf_tone_directive,
    create_mode_identified_directive,
)


# -----------------------------------------------------------------------------
# ToolCapabilityV1 Tests
# -----------------------------------------------------------------------------


class TestToolCapabilityV1:
    """Tests for ToolCapabilityV1 contract."""

    def test_create_capability(self):
        """Test creating a valid capability."""
        cap = ToolCapabilityV1(
            tool_id="test_tool",
            version="1.0.0",
            display_name="Test Tool",
            actions=[CapabilityAction.ANALYZE_AUDIO],
        )
        assert cap.tool_id == "test_tool"
        assert cap.version == "1.0.0"
        assert CapabilityAction.ANALYZE_AUDIO in cap.actions

    def test_safe_defaults(self):
        """Test that safe defaults are applied."""
        cap = ToolCapabilityV1(
            tool_id="test_tool",
            version="1.0.0",
            display_name="Test",
            actions=[CapabilityAction.ANALYZE_AUDIO],
        )
        assert cap.safe_defaults.dry_run is True
        assert cap.safe_defaults.pii_scrub_enabled is True

    def test_to_dict(self):
        """Test JSON serialization."""
        cap = ToolCapabilityV1(
            tool_id="test_tool",
            version="1.0.0",
            display_name="Test Tool",
            actions=[CapabilityAction.ANALYZE_AUDIO],
            tags=["test"],
        )
        d = cap.to_dict()
        assert d["tool_id"] == "test_tool"
        assert d["actions"] == ["analyze_audio"]
        assert d["tags"] == ["test"]
        # Should be JSON-serializable
        json.dumps(d)


# -----------------------------------------------------------------------------
# AttentionDirectiveV1 Tests
# -----------------------------------------------------------------------------


class TestAttentionDirectiveV1:
    """Tests for AttentionDirectiveV1 contract."""

    def test_create_directive(self):
        """Test creating a valid attention directive."""
        directive = AttentionDirectiveV1(
            directive_id="attn_001",
            action=AttentionAction.REVIEW,
            summary="Please review this",
            focus=FocusTarget(
                target_type="spectrum",
                target_id="peak_1",
            ),
        )
        assert directive.action == AttentionAction.REVIEW
        assert directive.urgency == 0.5  # Default

    def test_default_timestamps(self):
        """Test that timestamps are auto-generated."""
        directive = AttentionDirectiveV1(
            directive_id="attn_001",
            action=AttentionAction.INSPECT,
            summary="FYI",
            focus=FocusTarget(target_type="test", target_id="1"),
        )
        assert directive.created_at  # Not empty
        assert "T" in directive.created_at  # ISO format

    def test_to_dict(self):
        """Test JSON serialization."""
        directive = AttentionDirectiveV1(
            directive_id="attn_001",
            action=AttentionAction.REVIEW,
            summary="Test",
            focus=FocusTarget(
                target_type="spectrum",
                target_id="peak_1",
                highlight_region={"freq_hz": 247},
            ),
        )
        d = directive.to_dict()
        assert d["action"] == "review"
        assert d["focus"]["highlight_region"]["freq_hz"] == 247
        json.dumps(d)


# -----------------------------------------------------------------------------
# AgentEventV1 Tests
# -----------------------------------------------------------------------------


class TestAgentEventV1:
    """Tests for AgentEventV1 contract."""

    def test_create_event(self):
        """Test creating a valid event."""
        event = AgentEventV1(
            event_id="evt_001",
            event_type=EventType.ANALYSIS_COMPLETED,
            source=EventSource(
                repo="tap_tone_pi",
                component="wolf_detector",
            ),
        )
        assert event.event_type == EventType.ANALYSIS_COMPLETED
        assert event.source.repo == "tap_tone_pi"

    def test_privacy_layer_default(self):
        """Test that privacy layer defaults to 3."""
        event = AgentEventV1(
            event_id="evt_001",
            event_type=EventType.ANALYSIS_STARTED,
            source=EventSource(repo="test", component="test"),
        )
        assert event.privacy_layer == 3

    def test_to_dict(self):
        """Test JSON serialization."""
        event = AgentEventV1(
            event_id="evt_001",
            event_type=EventType.ANALYSIS_COMPLETED,
            source=EventSource(repo="tap_tone_pi", component="test"),
            payload={"count": 5},
        )
        d = event.to_dict()
        assert d["event_type"] == "analysis_completed"
        assert d["payload"]["count"] == 5
        json.dumps(d)


# -----------------------------------------------------------------------------
# Capability Registry Tests
# -----------------------------------------------------------------------------


class TestCapabilityRegistry:
    """Tests for capability registry."""

    def test_get_capabilities(self):
        """Test that registry returns all capabilities."""
        caps = get_capabilities()
        assert len(caps) >= 1
        tool_ids = [c.tool_id for c in caps]
        assert "tap_tone_analyzer" in tool_ids

    def test_get_capability_by_id(self):
        """Test looking up capability by ID."""
        cap = get_capability_by_id("tap_tone_analyzer")
        assert cap is not None
        assert cap.tool_id == "tap_tone_analyzer"
        assert cap.source_repo == "tap_tone_pi"

    def test_tap_tone_analyzer(self):
        """Test TAP_TONE_ANALYZER has expected capabilities."""
        assert CapabilityAction.ANALYZE_AUDIO in TAP_TONE_ANALYZER.actions
        assert CapabilityAction.ANALYZE_SPECTRUM in TAP_TONE_ANALYZER.actions
        assert "wolf_candidates_v1" in TAP_TONE_ANALYZER.output_schemas

    def test_wolf_detector(self):
        """Test WOLF_DETECTOR capability."""
        assert WOLF_DETECTOR.tool_id == "tap_tone_wolf_detector"
        assert CapabilityAction.ANALYZE_SPECTRUM in WOLF_DETECTOR.actions

    def test_capability_not_found(self):
        """Test that unknown capability returns None."""
        cap = get_capability_by_id("nonexistent")
        assert cap is None


# -----------------------------------------------------------------------------
# Event Emission Tests
# -----------------------------------------------------------------------------


class TestEventEmission:
    """Tests for event emission utilities."""

    def test_emit_event(self):
        """Test basic event emission."""
        event = emit_event(
            EventType.ANALYSIS_STARTED,
            "test_component",
            payload={"run_id": "run_123"},
        )
        assert event.event_type == EventType.ANALYSIS_STARTED
        assert event.source.component == "test_component"
        assert event.payload["run_id"] == "run_123"

    def test_emit_analysis_started(self):
        """Test ANALYSIS_STARTED convenience emitter."""
        event = emit_analysis_started("wolf_detector", "run_abc")
        assert event.event_type == EventType.ANALYSIS_STARTED
        assert event.payload["run_id"] == "run_abc"
        assert event.correlation_id == "run_abc"

    def test_emit_analysis_completed(self):
        """Test ANALYSIS_COMPLETED convenience emitter."""
        event = emit_analysis_completed(
            "phase2_pipeline",
            "run_xyz",
            artifacts_created=["wolf_candidates.json", "ods_snapshot.json"],
            metrics={"peak_count": 12},
        )
        assert event.event_type == EventType.ANALYSIS_COMPLETED
        assert len(event.payload["artifacts_created"]) == 2
        assert event.payload["metrics"]["peak_count"] == 12

    def test_emit_analysis_failed(self):
        """Test ANALYSIS_FAILED convenience emitter."""
        event = emit_analysis_failed(
            "wolf_detector",
            "run_fail",
            error="No audio data found",
            error_type="ValueError",
        )
        assert event.event_type == EventType.ANALYSIS_FAILED
        assert "No audio" in event.payload["error"]
        assert "error" in event.tags

    def test_event_log_to_file(self):
        """Test writing events to JSONL log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "events.jsonl"

            emit_event(
                EventType.ANALYSIS_STARTED,
                "test",
                event_log_path=log_path,
            )
            emit_event(
                EventType.ANALYSIS_COMPLETED,
                "test",
                event_log_path=log_path,
            )

            assert log_path.exists()
            lines = log_path.read_text().strip().split("\n")
            assert len(lines) == 2

            event1 = json.loads(lines[0])
            event2 = json.loads(lines[1])
            assert event1["event_type"] == "analysis_started"
            assert event2["event_type"] == "analysis_completed"


# -----------------------------------------------------------------------------
# Attention Directive Helper Tests
# -----------------------------------------------------------------------------


class TestAttentionDirectiveHelpers:
    """Tests for attention directive helper functions."""

    def test_create_wolf_tone_directive(self):
        """Test wolf tone directive creation."""
        directive = create_wolf_tone_directive(
            freq_hz=247.0,
            confidence=0.87,
            peak_id="peak_3",
            bundle_sha256="abc123",
        )
        assert directive.action == AttentionAction.REVIEW
        assert "247Hz" in directive.summary
        assert directive.confidence == 0.87
        assert directive.urgency == 0.7  # High confidence → higher urgency
        assert len(directive.evidence_refs) == 1

    def test_create_mode_identified_directive(self):
        """Test mode identification directive creation."""
        directive = create_mode_identified_directive(
            mode_name="T(1,1)",
            freq_hz=180.0,
            mode_id="mode_t11",
        )
        assert directive.action == AttentionAction.INSPECT
        assert "T(1,1)" in directive.summary
        assert directive.urgency == 0.3  # Informational

    def test_mode_directive_out_of_range(self):
        """Test that out-of-range modes have higher urgency."""
        directive = create_mode_identified_directive(
            mode_name="T(1,1)",
            freq_hz=250.0,  # Outside typical range
            mode_id="mode_t11",
            expected_range=(160, 200),
        )
        assert directive.urgency == 0.6  # Higher urgency
        assert "Outside typical range" in directive.detail


# -----------------------------------------------------------------------------
# Cross-Repo Compatibility Tests
# -----------------------------------------------------------------------------


class TestCrossRepoCompatibility:
    """Tests for cross-repo contract compatibility."""

    def test_event_serialization_matches_toolbox(self):
        """Test that serialized event matches ToolBox expected format."""
        event = AgentEventV1(
            event_id="evt_tap_001",
            event_type=EventType.ANALYSIS_COMPLETED,
            source=EventSource(
                repo="tap_tone_pi",
                component="wolf_detector",
                version="2.0.0",
            ),
            payload={"candidates_found": 3},
            privacy_layer=2,
        )
        d = event.to_dict()

        # These fields are required by luthiers-toolbox
        assert "event_id" in d
        assert "event_type" in d
        assert "source" in d
        assert "payload" in d
        assert "privacy_layer" in d
        assert "occurred_at" in d
        assert "schema_version" in d

        # Source must have repo and component
        assert d["source"]["repo"] == "tap_tone_pi"
        assert d["source"]["component"] == "wolf_detector"

    def test_capability_serialization_matches_toolbox(self):
        """Test that serialized capability matches ToolBox expected format."""
        d = TAP_TONE_ANALYZER.to_dict()

        # Required fields
        assert "tool_id" in d
        assert "version" in d
        assert "display_name" in d
        assert "actions" in d
        assert "safe_defaults" in d
        assert "source_repo" in d

        # Actions should be string values
        assert all(isinstance(a, str) for a in d["actions"])

        # Safe defaults must have these fields
        sd = d["safe_defaults"]
        assert "redaction_layer" in sd
        assert "dry_run" in sd
        assert "timeout_seconds" in sd
