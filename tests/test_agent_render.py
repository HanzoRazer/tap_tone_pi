"""Tests for agent render functions."""

import pytest
from tap_tone_pi.agent import (
    StandaloneAgentMessage as AgentMessage,
    StandaloneSuggestedAction as SuggestedAction,
    ActionId,
    render_cli,
    render_gui,
    render_compact,
)


@pytest.fixture
def sample_message():
    """Create a sample AgentMessage for testing."""
    return AgentMessage(
        title="Measurement failed quality gate",
        summary="Capture is not acceptable under policy.",
        details=[
            "[ERROR] Q001: The signal clipped.\n  → Clipping changes the spectrum.",
            "[WARN] Q011: Signal near clipping.",
        ],
        suggested_actions=[
            SuggestedAction(
                ActionId.ADJUST_GAIN_DOWN, "Lower gain", "Prevents distortion"
            ),
            SuggestedAction(ActionId.RETRY, "Retry", "Try again"),
            SuggestedAction(
                ActionId.OVERRIDE, "Override", "Log exception", requires_input=True
            ),
        ],
        learning_hint="Tip: Run 'ttp setup' to configure your device.",
        telemetry_tags={
            "verdict": "fail",
            "rule_ids": ["Q001", "Q011"],
            "user_stage": "first_run",
        },
    )


class TestRenderCLI:
    """Tests for CLI rendering."""

    def test_includes_title(self, sample_message):
        output = render_cli(sample_message, color=False)
        assert "Measurement failed quality gate" in output

    def test_includes_summary(self, sample_message):
        output = render_cli(sample_message, color=False)
        assert "Capture is not acceptable under policy." in output

    def test_includes_details(self, sample_message):
        output = render_cli(sample_message, color=False)
        assert "[ERROR] Q001" in output
        assert "[WARN] Q011" in output

    def test_includes_actions(self, sample_message):
        output = render_cli(sample_message, color=False)
        assert "Lower gain" in output
        assert "Retry" in output
        assert "Override" in output

    def test_marks_requires_input(self, sample_message):
        output = render_cli(sample_message, color=False)
        # Override requires input, should have marker
        lines = output.split("\n")
        override_line = [line for line in lines if "Override" in l][0]
        assert "*" in override_line

    def test_includes_learning_hint(self, sample_message):
        output = render_cli(sample_message, color=False)
        assert "Tip: Run 'ttp setup'" in output

    def test_color_mode(self, sample_message):
        output = render_cli(sample_message, color=True)
        # Should contain ANSI escape codes
        assert "\033[" in output

    def test_no_color_mode(self, sample_message):
        output = render_cli(sample_message, color=False)
        # Should not contain ANSI escape codes (except in hint)
        lines = output.split("\n")
        title_line = lines[0]
        assert "\033[" not in title_line


class TestRenderGUI:
    """Tests for GUI rendering."""

    def test_returns_dict(self, sample_message):
        result = render_gui(sample_message)
        assert isinstance(result, dict)

    def test_includes_title(self, sample_message):
        result = render_gui(sample_message)
        assert result["title_text"] == "Measurement failed quality gate"

    def test_includes_style(self, sample_message):
        result = render_gui(sample_message)
        assert result["title_style"] == "error"

    def test_warn_style(self):
        msg = AgentMessage(
            title="Warning",
            summary="Test",
            telemetry_tags={"verdict": "warn"},
        )
        result = render_gui(msg)
        assert result["title_style"] == "warning"

    def test_pass_style(self):
        msg = AgentMessage(
            title="Passed",
            summary="Test",
            telemetry_tags={"verdict": "pass"},
        )
        result = render_gui(msg)
        assert result["title_style"] == "success"

    def test_details_formatted_html(self, sample_message):
        result = render_gui(sample_message)
        html = result["details_html"]
        assert "<p>" in html
        assert "[ERROR]" in html or "color:red" in html

    def test_action_buttons(self, sample_message):
        result = render_gui(sample_message)
        buttons = result["action_buttons"]
        assert len(buttons) == 3

        # Check structure
        first = buttons[0]
        assert "id" in first
        assert "label" in first
        assert "enabled" in first
        assert "requires_input" in first

    def test_override_requires_input(self, sample_message):
        result = render_gui(sample_message)
        override_btn = [b for b in result["action_buttons"] if b["id"] == "override"][0]
        assert override_btn["requires_input"] is True

    def test_hint_text(self, sample_message):
        result = render_gui(sample_message)
        assert result["hint_text"] == "Tip: Run 'ttp setup' to configure your device."

    def test_hint_text_none(self):
        msg = AgentMessage(
            title="Test",
            summary="Test",
            telemetry_tags={"verdict": "pass"},
        )
        result = render_gui(msg)
        assert result["hint_text"] is None


class TestRenderCompact:
    """Tests for compact/log rendering."""

    def test_one_line(self, sample_message):
        output = render_compact(sample_message)
        assert "\n" not in output

    def test_includes_severity(self, sample_message):
        output = render_compact(sample_message)
        assert "ERROR:" in output

    def test_includes_title(self, sample_message):
        output = render_compact(sample_message)
        assert "Measurement failed quality gate" in output

    def test_includes_rule_ids(self, sample_message):
        output = render_compact(sample_message)
        assert "Q001" in output
        assert "Q011" in output

    def test_includes_action_ids(self, sample_message):
        output = render_compact(sample_message)
        assert "adjust_gain_down" in output
        assert "retry" in output
