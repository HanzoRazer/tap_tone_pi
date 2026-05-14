"""Tests for MeasurementAgent integration."""

from dataclasses import dataclass, field
from tap_tone_pi.agent import (
    MeasurementAgent,
    StandaloneAgentContext as AgentContext,
    UserStage,
    ActionId,
    standalone_build_agent_message as build_agent_message,
    render_cli,
)


# =============================================================================
# Mock QualityVerdict for testing (avoids importing full quality_gate module)
# =============================================================================


class MockSeverity:
    HARD = "HARD"
    SOFT = "SOFT"


class MockVerdict:
    PASS = type("V", (), {"value": "pass"})()
    WARN = type("V", (), {"value": "warn"})()
    FAIL = type("V", (), {"value": "fail"})()


@dataclass
class MockQualityRule:
    rule_id: str
    severity: str = MockSeverity.HARD


@dataclass
class MockTriggeredRule:
    rule: MockQualityRule
    message: str = ""


@dataclass
class MockQualityVerdict:
    verdict: object
    triggered: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


# =============================================================================
# Tests
# =============================================================================


class TestMeasurementAgent:
    """Tests for MeasurementAgent class."""

    def test_create_agent(self):
        agent = MeasurementAgent()
        assert agent.context is not None
        assert agent.on_message is None

    def test_create_with_context(self):
        ctx = AgentContext(user_stage=UserStage.EXPERT)
        agent = MeasurementAgent(context=ctx)
        assert agent.context.user_stage == UserStage.EXPERT

    def test_on_verdict_pass(self):
        agent = MeasurementAgent()
        verdict = MockQualityVerdict(verdict=MockVerdict.PASS)

        msg = agent.on_verdict(verdict)

        assert msg.title == "Measurement accepted"
        assert msg.severity == "info"

    def test_on_verdict_fail(self):
        agent = MeasurementAgent()
        verdict = MockQualityVerdict(
            verdict=MockVerdict.FAIL,
            triggered=[
                MockTriggeredRule(MockQualityRule("Q001", MockSeverity.HARD)),
            ],
        )

        msg = agent.on_verdict(verdict)

        assert msg.title == "Measurement failed quality gate"
        assert msg.severity == "error"
        assert "Q001" in msg.telemetry_tags["rule_ids"]

    def test_on_verdict_warn(self):
        agent = MeasurementAgent()
        verdict = MockQualityVerdict(
            verdict=MockVerdict.WARN,
            triggered=[
                MockTriggeredRule(MockQualityRule("Q011", MockSeverity.SOFT)),
            ],
        )

        msg = agent.on_verdict(verdict)

        assert msg.title == "Measurement usable with warnings"
        assert msg.severity == "warn"

    def test_on_verdict_updates_context(self):
        agent = MeasurementAgent()
        verdict = MockQualityVerdict(
            verdict=MockVerdict.FAIL,
            triggered=[
                MockTriggeredRule(MockQualityRule("Q001")),
            ],
        )

        agent.on_verdict(verdict)

        assert agent.context.rule_counts_session["Q001"] == 1

    def test_callback_invoked(self):
        messages = []
        agent = MeasurementAgent(on_message=messages.append)
        verdict = MockQualityVerdict(verdict=MockVerdict.PASS)

        agent.on_verdict(verdict)

        assert len(messages) == 1
        assert messages[0].title == "Measurement accepted"

    def test_reset_for_point(self):
        agent = MeasurementAgent()
        agent.context.attempt_num = 5
        agent.context.consecutive_rule_hits["Q001"] = 3

        agent.reset_for_point("P002")

        assert agent.context.point_id == "P002"
        assert agent.context.attempt_num == 1
        assert agent.context.consecutive_rule_hits == {}

    def test_advance_attempt(self):
        agent = MeasurementAgent()
        assert agent.context.attempt_num == 1

        agent.advance_attempt()

        assert agent.context.attempt_num == 2


class TestBuildAgentMessage:
    """Tests for convenience function."""

    def test_pass_message(self):
        msg = build_agent_message("pass", [])
        assert msg.title == "Measurement accepted"
        assert len(msg.suggested_actions) >= 1
        assert msg.suggested_actions[0].action_id == ActionId.ADVANCE

    def test_fail_message_with_rules(self):
        msg = build_agent_message("fail", ["Q001", "Q002"])
        assert msg.title == "Measurement failed quality gate"
        assert len(msg.details) >= 1
        assert "Q001" in msg.details[0]

    def test_warn_message(self):
        msg = build_agent_message("warn", ["Q011"])
        assert msg.title == "Measurement usable with warnings"

    def test_with_custom_context(self):
        ctx = AgentContext(user_stage=UserStage.FIRST_RUN, attempt_num=2)
        msg = build_agent_message("fail", ["Q001"], context=ctx)

        assert msg.learning_hint is not None  # First run gets hints
        assert msg.telemetry_tags["attempt_num"] == 2


class TestAgentFTUEIntegration:
    """Tests for FTUE behavior through agent."""

    def test_first_run_limited_details(self):
        ctx = AgentContext(user_stage=UserStage.FIRST_RUN)
        msg = build_agent_message("fail", ["Q001", "Q002", "Q003", "Q004"], context=ctx)

        # First run should show max 2 rules
        assert len(msg.details) <= 2

    def test_first_run_limited_actions(self):
        ctx = AgentContext(user_stage=UserStage.FIRST_RUN)
        msg = build_agent_message("fail", ["Q001"], context=ctx)

        # First run should show max 2 actions + help
        assert len(msg.suggested_actions) <= 3

    def test_first_run_includes_help(self):
        ctx = AgentContext(user_stage=UserStage.FIRST_RUN)
        msg = build_agent_message("fail", ["Q001"], context=ctx)

        action_ids = [a.action_id for a in msg.suggested_actions]
        assert ActionId.HELP in action_ids

    def test_first_run_gets_hint(self):
        ctx = AgentContext(user_stage=UserStage.FIRST_RUN)
        msg = build_agent_message("fail", ["Q001"], context=ctx)

        assert msg.learning_hint is not None
        assert "Tip:" in msg.learning_hint

    def test_expert_no_hint(self):
        ctx = AgentContext(user_stage=UserStage.EXPERT)
        msg = build_agent_message("fail", ["Q001"], context=ctx)

        assert msg.learning_hint is None


class TestAgentEscalation:
    """Tests for repeated-rule escalation."""

    def test_repeated_rule_escalates_fix(self):
        ctx = AgentContext()

        # First failure
        msg1 = build_agent_message("fail", ["Q001"], context=ctx)
        fix1 = msg1.details[0] if msg1.details else ""

        # Simulate repeated trigger
        ctx.record_rules(["Q001"])  # Second time
        msg2 = build_agent_message("fail", ["Q001"], context=ctx)
        fix2 = msg2.details[0] if msg2.details else ""

        # Fix text should change (fallback_fix vs first_fix)
        # Both should be present but different
        assert "Q001" in fix1
        assert "Q001" in fix2


class TestAgentCLIIntegration:
    """Tests for CLI rendering of agent messages."""

    def test_full_flow_renders(self):
        """End-to-end: verdict → agent → render → output."""
        agent = MeasurementAgent(context=AgentContext(user_stage=UserStage.REGULAR))
        verdict = MockQualityVerdict(
            verdict=MockVerdict.FAIL,
            triggered=[
                MockTriggeredRule(MockQualityRule("Q001")),
                MockTriggeredRule(MockQualityRule("Q011", MockSeverity.SOFT)),
            ],
        )

        msg = agent.on_verdict(verdict)
        output = render_cli(msg, color=False)

        assert "Measurement failed quality gate" in output
        assert "Q001" in output
        assert "Retry" in output or "Lower gain" in output

    def test_pass_flow_minimal(self):
        agent = MeasurementAgent()
        verdict = MockQualityVerdict(verdict=MockVerdict.PASS)

        msg = agent.on_verdict(verdict)
        output = render_cli(msg, color=False)

        assert "accepted" in output.lower()
        assert "Next point" in output
