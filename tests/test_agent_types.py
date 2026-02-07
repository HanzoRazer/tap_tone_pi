"""Tests for agent types and context."""
import pytest
from tap_tone_pi.agent import (
    ActionId,
    StandaloneAgentContext as AgentContext,
    StandaloneAgentMessage as AgentMessage,
    StandaloneSuggestedAction as SuggestedAction,
    UserStage,
)


class TestSuggestedAction:
    """Tests for SuggestedAction dataclass."""

    def test_basic_action(self):
        action = SuggestedAction(
            action_id=ActionId.RETRY,
            label="Retry capture",
            rationale="Need an unclipped waveform",
        )
        assert action.action_id == ActionId.RETRY
        assert action.label == "Retry capture"
        assert action.requires_input is False

    def test_action_requiring_input(self):
        action = SuggestedAction(
            action_id=ActionId.OVERRIDE,
            label="Override",
            rationale="Log exception",
            requires_input=True,
        )
        assert action.requires_input is True

    def test_to_dict(self):
        action = SuggestedAction(
            action_id=ActionId.ACCEPT,
            label="Accept",
            rationale="Proceed",
        )
        d = action.to_dict()
        assert d["action_id"] == "accept"
        assert d["label"] == "Accept"
        assert d["requires_input"] is False


class TestAgentMessage:
    """Tests for AgentMessage dataclass."""

    def test_pass_severity(self):
        msg = AgentMessage(
            title="Measurement accepted",
            summary="Quality checks passed.",
            telemetry_tags={"verdict": "pass"},
        )
        assert msg.severity == "info"

    def test_warn_severity(self):
        msg = AgentMessage(
            title="Usable with warnings",
            summary="Conditions may reduce repeatability.",
            telemetry_tags={"verdict": "warn"},
        )
        assert msg.severity == "warn"

    def test_fail_severity(self):
        msg = AgentMessage(
            title="Failed quality gate",
            summary="Capture not acceptable.",
            telemetry_tags={"verdict": "fail"},
        )
        assert msg.severity == "error"

    def test_to_dict_full(self):
        msg = AgentMessage(
            title="Test",
            summary="Summary",
            details=["Detail 1", "Detail 2"],
            suggested_actions=[
                SuggestedAction(ActionId.RETRY, "Retry", "Try again"),
            ],
            learning_hint="Tip: test",
            telemetry_tags={"verdict": "warn", "rule_ids": ["Q011"]},
        )
        d = msg.to_dict()
        assert d["title"] == "Test"
        assert d["severity"] == "warn"
        assert len(d["details"]) == 2
        assert len(d["suggested_actions"]) == 1
        assert d["learning_hint"] == "Tip: test"


class TestAgentContext:
    """Tests for AgentContext tracking."""

    def test_defaults(self):
        ctx = AgentContext()
        assert ctx.user_stage == UserStage.REGULAR
        assert ctx.attempt_num == 1
        assert ctx.workflow == "measure"

    def test_record_rules_increments_counts(self):
        ctx = AgentContext()
        ctx.record_rules(["Q001", "Q011"])
        assert ctx.rule_counts_session["Q001"] == 1
        assert ctx.rule_counts_session["Q011"] == 1
        assert ctx.consecutive_rule_hits["Q001"] == 1

    def test_record_rules_tracks_consecutive(self):
        ctx = AgentContext()
        ctx.record_rules(["Q011"])
        ctx.record_rules(["Q011"])
        ctx.record_rules(["Q011"])
        assert ctx.consecutive_rule_hits["Q011"] == 3
        assert ctx.rule_counts_session["Q011"] == 3

    def test_record_rules_resets_non_triggered(self):
        ctx = AgentContext()
        ctx.record_rules(["Q001"])
        ctx.record_rules(["Q001"])
        assert ctx.consecutive_rule_hits["Q001"] == 2
        
        # Different rule triggered
        ctx.record_rules(["Q011"])
        assert ctx.consecutive_rule_hits["Q001"] == 0
        assert ctx.consecutive_rule_hits["Q011"] == 1


class TestUserStage:
    """Tests for UserStage enum."""

    def test_values(self):
        assert UserStage.FIRST_RUN.value == "first_run"
        assert UserStage.NOVICE.value == "novice"
        assert UserStage.REGULAR.value == "regular"
        assert UserStage.EXPERT.value == "expert"


class TestActionId:
    """Tests for ActionId enum."""

    def test_core_actions_exist(self):
        assert ActionId.RETRY.value == "retry"
        assert ActionId.ACCEPT.value == "accept"
        assert ActionId.ADVANCE.value == "advance"
        assert ActionId.ABORT.value == "abort"
        assert ActionId.OVERRIDE.value == "override"
        assert ActionId.HELP.value == "help"

    def test_adjustment_actions_exist(self):
        assert ActionId.ADJUST_GAIN_DOWN.value == "adjust_gain_down"
        assert ActionId.ADJUST_GAIN_UP.value == "adjust_gain_up"
        assert ActionId.CHECK_DEVICE.value == "check_device"
        assert ActionId.RUN_SETUP.value == "run_setup"
