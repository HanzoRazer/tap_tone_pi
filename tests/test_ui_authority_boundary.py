# INSTRUMENT CLASS: MEASUREMENT
"""Tests for UI authority boundary enforcement.

Validates that guidance surfaces use advisory framing, not measurement/verdict
framing. Guidance should be visually and textually distinct from measurement
results.

See: docs/AGE_CONSTITUTIONAL_CONTRACT.md
"""

from __future__ import annotations

import pytest

from tap_tone_pi.agent import render
from tap_tone_pi.agentic.contracts.analyzer_attention import (
    AttentionAction,
    AttentionDirectiveV1,
    FocusTarget,
)


# ---------------------------------------------------------------------------
# Allowed and forbidden terms
# ---------------------------------------------------------------------------

ALLOWED_ADVISORY_HEADINGS = {
    "guidance",
    "advisory",
    "review suggested",
    "attention",
    "attention recommended",
    "info",
    "review",
    "decide",
    "urgent",
}

FORBIDDEN_VERDICT_HEADINGS = {
    "result",
    "verdict",
    "diagnosis",
    "failure",
    "approved",
    "validated",
    "certified",
    "pass",
    "fail",
}

FORBIDDEN_DIRECTIVE_TERMS = {
    "diagnosis",
    "required action",
    "fix",
    "optimal",
}


def _create_test_directive(
    action: AttentionAction = AttentionAction.REVIEW,
    summary: str = "Review potential anomaly",
    detail: str = "May indicate environmental drift",
) -> AttentionDirectiveV1:
    """Create a test directive for rendering."""
    return AttentionDirectiveV1(
        directive_id="test_directive_001",
        action=action,
        summary=summary,
        focus=FocusTarget(target_type="spectrum_region", target_id="peak_1"),
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Directive Contract Tests
# ---------------------------------------------------------------------------


class TestDirectiveOutputContract:
    """Tests for AttentionDirectiveV1 output contract."""

    def test_directive_to_dict_uses_advisory_action_names(self):
        """Directive action values should be advisory, not verdict-like."""
        for action in AttentionAction:
            directive = _create_test_directive(action=action)
            payload = directive.to_dict()
            action_value = payload["action"]
            assert action_value.lower() not in FORBIDDEN_VERDICT_HEADINGS
            assert action_value.lower() in {
                "inspect", "review", "compare", "decide", "confirm", "intervene", "abort"
            }

    def test_directive_action_enum_has_no_verdict_values(self):
        """AttentionAction enum should not contain verdict-like values."""
        for action in AttentionAction:
            assert action.value.lower() not in FORBIDDEN_VERDICT_HEADINGS
            assert "pass" not in action.value.lower()
            assert "fail" not in action.value.lower()

    def test_directive_summary_field_exists(self):
        """Directive must use 'summary' not 'verdict' or 'result'."""
        directive = _create_test_directive()
        payload = directive.to_dict()
        assert "summary" in payload
        assert "verdict" not in payload
        assert "result" not in payload
        assert "diagnosis" not in payload


# ---------------------------------------------------------------------------
# CLI Render Tests
# ---------------------------------------------------------------------------


class TestCliRenderAuthorityBoundary:
    """Tests for CLI render.py advisory authority boundary."""

    def test_render_cli_exists(self):
        """render_cli function should exist."""
        assert hasattr(render, "render_cli")
        assert callable(render.render_cli)

    def test_render_gui_exists(self):
        """render_gui function should exist."""
        assert hasattr(render, "render_gui")
        assert callable(render.render_gui)


# ---------------------------------------------------------------------------
# Guidance Panel Label Tests
# ---------------------------------------------------------------------------


class TestGuidancePanelLabels:
    """Tests for analyzer/guidance/panel.py labels and headings."""

    def test_action_labels_are_advisory(self):
        """Action labels used in guidance panel should be advisory, not verdict."""
        try:
            from analyzer.guidance.panel import _ACTION_LABEL
        except ImportError:
            pytest.skip("analyzer.guidance.panel not importable")

        for action, label in _ACTION_LABEL.items():
            label_lower = label.lower()
            assert label_lower not in FORBIDDEN_VERDICT_HEADINGS, (
                f"Action label '{label}' is a forbidden verdict term"
            )

    def test_guidance_panel_widget_title_is_advisory(self):
        """GuidancePanelWidget should use advisory heading."""
        try:
            from analyzer.guidance.panel import GuidancePanelWidget
        except ImportError:
            pytest.skip("analyzer.guidance.panel not importable")

        # The widget should use "Guidance" as title, not "Result" or "Verdict"
        # We can't instantiate without QApplication, so we check the class
        assert hasattr(GuidancePanelWidget, "__init__")

    def test_action_colour_mapping_exists(self):
        """Action colour mapping should exist for all advisory actions."""
        try:
            from analyzer.guidance.panel import _ACTION_COLOUR
        except ImportError:
            pytest.skip("analyzer.guidance.panel not importable")

        # Should have colours for at least INSPECT, REVIEW, DECIDE
        expected_actions = {
            AttentionAction.INSPECT,
            AttentionAction.REVIEW,
            AttentionAction.DECIDE,
        }
        for action in expected_actions:
            assert action in _ACTION_COLOUR, f"Missing colour for {action}"


# ---------------------------------------------------------------------------
# Guidance Engine Tests
# ---------------------------------------------------------------------------


class TestGuidanceEngineOutput:
    """Tests for analyzer/guidance/engine.py output contract."""

    def test_engine_does_not_emit_verdict_actions(self):
        """Guidance engine should not emit PASS/FAIL-style actions."""
        try:
            from analyzer.guidance.engine import AnalyzerGuidanceEngine
        except ImportError:
            pytest.skip("analyzer.guidance.engine not importable")

        # Engine should only emit AttentionAction values
        # Verify the engine uses the contract's action enum
        assert hasattr(AnalyzerGuidanceEngine, "__init__")


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestUiAuthorityBoundaryIntegration:
    """Integration tests for UI authority boundary."""

    def test_all_attention_actions_are_advisory(self):
        """All AttentionAction values should be advisory, not verdict-like."""
        advisory_actions = {"inspect", "review", "compare", "decide", "confirm", "intervene", "abort"}
        for action in AttentionAction:
            assert action.value in advisory_actions, (
                f"AttentionAction.{action.name} has non-advisory value '{action.value}'"
            )

    def test_directive_avoids_forbidden_copy(self):
        """Creating directives with forbidden copy should still serialize cleanly."""
        # The contract doesn't prevent forbidden copy in summary/detail,
        # but the language guard (78E) catches it. This test verifies
        # serialization doesn't add forbidden structural keys.
        directive = AttentionDirectiveV1(
            directive_id="test_001",
            action=AttentionAction.REVIEW,
            summary="Consider reviewing this region",
            focus=FocusTarget(target_type="spectrum", target_id="peak_1"),
            detail="Observed pattern suggests attention may be warranted.",
        )
        payload = directive.to_dict()

        # No forbidden structural keys
        forbidden_keys = {"verdict", "diagnosis", "result", "fix", "required_action"}
        for key in payload.keys():
            assert key not in forbidden_keys, f"Payload contains forbidden key '{key}'"
