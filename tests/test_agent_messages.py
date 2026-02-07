"""Tests for integrated agent messages module (uses real quality_policy types)."""
import pytest
from tap_tone_pi.core.quality_policy import (
    QualityRule,
    QualityVerdict,
    TriggeredRule,
    Verdict,
    Severity,
)
from tap_tone_pi.agent.messages import (
    AgentContext,
    AgentMessage,
    SuggestedAction,
    RULE_SPECS,
    VERDICT_TEMPLATES,
    FTUE_HINTS,
    infer_user_stage,
    sort_triggered_rules,
    build_agent_message,
    render_agent_message_cli,
    format_verdict_summary_agent,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def rule_q001():
    """Real Q001 rule from policy."""
    return QualityRule(
        rule_id="Q001",
        severity=Severity.HARD,
        description="Clipping detected",
        message="Signal clipped",
    )


@pytest.fixture
def rule_q011():
    """Real Q011 rule from policy."""
    return QualityRule(
        rule_id="Q011",
        severity=Severity.SOFT,
        description="Near clipping",
        message="Near clipping",
    )


@pytest.fixture
def pass_verdict():
    return QualityVerdict(verdict=Verdict.PASS, triggered_rules=[])


@pytest.fixture
def fail_verdict(rule_q001):
    return QualityVerdict(
        verdict=Verdict.FAIL,
        triggered_rules=[TriggeredRule(rule=rule_q001, message="Signal clipped")],
    )


@pytest.fixture
def warn_verdict(rule_q011):
    return QualityVerdict(
        verdict=Verdict.WARN,
        triggered_rules=[TriggeredRule(rule=rule_q011, message="Near clipping")],
    )


# =============================================================================
# AgentContext Tests
# =============================================================================

class TestAgentContext:
    """Tests for frozen AgentContext."""

    def test_defaults(self):
        ctx = AgentContext()
        assert ctx.workflow == "record"
        assert ctx.attempt_num == 1
        assert ctx.user_stage is None

    def test_is_frozen(self):
        ctx = AgentContext()
        with pytest.raises(AttributeError):
            ctx.attempt_num = 5  # type: ignore

    def test_get_rule_count_empty(self):
        ctx = AgentContext()
        assert ctx.get_rule_count("Q001") == 0

    def test_get_rule_count_with_data(self):
        ctx = AgentContext(
            rule_counts_this_session=(("Q001", 3), ("Q011", 1))
        )
        assert ctx.get_rule_count("Q001") == 3
        assert ctx.get_rule_count("Q011") == 1
        assert ctx.get_rule_count("Q999") == 0

    def test_get_consecutive_hits(self):
        ctx = AgentContext(
            consecutive_rule_hits=(("Q011", 2),)
        )
        assert ctx.get_consecutive_hits("Q011") == 2
        assert ctx.get_consecutive_hits("Q001") == 0


# =============================================================================
# AgentMessage Tests
# =============================================================================

class TestAgentMessage:
    """Tests for frozen AgentMessage."""

    def test_basic_message(self):
        msg = AgentMessage(
            title="Test",
            summary="Summary",
        )
        assert msg.title == "Test"
        assert msg.details == ()
        assert msg.suggested_actions == ()

    def test_is_frozen(self):
        msg = AgentMessage(title="T", summary="S")
        with pytest.raises(AttributeError):
            msg.title = "New"  # type: ignore

    def test_get_tag(self):
        msg = AgentMessage(
            title="T",
            summary="S",
            telemetry_tags=(("verdict", "fail"), ("rule_ids", ("Q001",))),
        )
        assert msg.get_tag("verdict") == "fail"
        assert msg.get_tag("rule_ids") == ("Q001",)
        assert msg.get_tag("missing") is None


# =============================================================================
# FTUE Stage Inference Tests
# =============================================================================

class TestInferUserStage:
    """Tests for user stage inference."""

    def test_expert_mode_wins(self):
        ctx = AgentContext(expert_mode=True)
        assert infer_user_stage(ctx) == "expert"

    def test_explicit_stage_wins(self):
        ctx = AgentContext(user_stage="novice")
        assert infer_user_stage(ctx) == "novice"

    def test_no_passes_is_first_run(self):
        ctx = AgentContext(pass_count_lifetime=0, session_count_lifetime=5)
        assert infer_user_stage(ctx) == "first_run"

    def test_few_passes_is_novice(self):
        ctx = AgentContext(pass_count_lifetime=5, session_count_lifetime=3)
        assert infer_user_stage(ctx) == "novice"

    def test_many_passes_is_regular(self):
        ctx = AgentContext(pass_count_lifetime=50, session_count_lifetime=10)
        assert infer_user_stage(ctx) == "regular"


# =============================================================================
# Rule Sorting Tests
# =============================================================================

class TestSortTriggeredRules:
    """Tests for rule ordering."""

    def test_hard_before_soft(self, rule_q001, rule_q011):
        triggered = [
            TriggeredRule(rule=rule_q011, message="soft"),
            TriggeredRule(rule=rule_q001, message="hard"),
        ]
        sorted_rules = sort_triggered_rules(triggered)
        assert sorted_rules[0].rule.rule_id == "Q001"
        assert sorted_rules[1].rule.rule_id == "Q011"

    def test_stable_within_severity(self):
        rules = [
            TriggeredRule(
                rule=QualityRule("Q003", Severity.HARD, "", ""),
                message=""
            ),
            TriggeredRule(
                rule=QualityRule("Q001", Severity.HARD, "", ""),
                message=""
            ),
        ]
        sorted_rules = sort_triggered_rules(rules)
        # Should be sorted by rule_id within same severity
        assert sorted_rules[0].rule.rule_id == "Q001"
        assert sorted_rules[1].rule.rule_id == "Q003"


# =============================================================================
# Build Agent Message Tests
# =============================================================================

class TestBuildAgentMessage:
    """Tests for build_agent_message with real QualityVerdict."""

    def test_pass_message(self, pass_verdict):
        ctx = AgentContext()
        msg = build_agent_message(ctx, pass_verdict)
        
        assert msg.title == "Measurement accepted"
        assert "passed" in msg.summary.lower()
        assert any(a.action_id == "advance" for a in msg.suggested_actions)

    def test_fail_message(self, fail_verdict):
        ctx = AgentContext(workflow="measure", show_details=True)
        msg = build_agent_message(ctx, fail_verdict)
        
        assert msg.title == "Measurement failed quality gate"
        assert "not acceptable" in msg.summary.lower()
        # Should have retry action
        assert any(a.action_id == "retry" for a in msg.suggested_actions)

    def test_warn_message(self, warn_verdict):
        ctx = AgentContext(workflow="measure", show_details=True)
        msg = build_agent_message(ctx, warn_verdict)
        
        assert msg.title == "Measurement usable with warnings"
        # Should have accept and retry
        action_ids = [a.action_id for a in msg.suggested_actions]
        assert "accept" in action_ids or "retry" in action_ids

    def test_includes_point_in_summary(self, pass_verdict):
        ctx = AgentContext(point_id="P001", attempt_num=2, max_attempts=5)
        msg = build_agent_message(ctx, pass_verdict)
        
        assert "P001" in msg.summary
        assert "2/5" in msg.summary

    def test_includes_attempt_in_summary(self, pass_verdict):
        ctx = AgentContext(attempt_num=3, max_attempts=5)
        msg = build_agent_message(ctx, pass_verdict)
        
        assert "3/5" in msg.summary

    def test_first_run_gets_hint(self, fail_verdict):
        ctx = AgentContext(
            pass_count_lifetime=0,
            show_details=True,
        )
        msg = build_agent_message(ctx, fail_verdict)
        
        assert msg.learning_hint is not None
        assert "Tip:" in msg.learning_hint

    def test_regular_no_hint(self, fail_verdict):
        ctx = AgentContext(
            pass_count_lifetime=100,
            session_count_lifetime=20,
        )
        msg = build_agent_message(ctx, fail_verdict)
        
        assert msg.learning_hint is None

    def test_details_include_rule_explanation(self, fail_verdict):
        ctx = AgentContext(workflow="measure", show_details=True, user_stage="regular")
        msg = build_agent_message(ctx, fail_verdict)
        
        # Should have details with Q001 explanation
        assert len(msg.details) > 0
        assert any("Q001" in d for d in msg.details)

    def test_first_run_hides_details_on_record(self, fail_verdict):
        ctx = AgentContext(
            workflow="record",
            pass_count_lifetime=0,
            show_details=False,  # Default for first_run in record mode
        )
        msg = build_agent_message(ctx, fail_verdict)
        
        assert len(msg.details) == 0

    def test_telemetry_tags(self, fail_verdict):
        ctx = AgentContext(
            workflow="measure",
            device_name="UMIK-1",
            sample_rate=48000,
        )
        msg = build_agent_message(ctx, fail_verdict)
        
        assert msg.get_tag("verdict") == "fail"
        assert msg.get_tag("workflow") == "measure"
        assert msg.get_tag("device_name") == "UMIK-1"
        assert msg.get_tag("sample_rate") == 48000


# =============================================================================
# Action Selection Tests
# =============================================================================

class TestActionSelection:
    """Tests for action selection logic."""

    def test_fail_includes_override_for_measure(self, fail_verdict):
        ctx = AgentContext(workflow="measure", user_stage="regular")
        msg = build_agent_message(ctx, fail_verdict)
        
        # Override should be available (requires input)
        override = next(
            (a for a in msg.suggested_actions if a.action_id == "override"),
            None
        )
        assert override is not None
        assert override.requires_input is True

    def test_first_run_fail_hides_override(self, fail_verdict):
        ctx = AgentContext(
            workflow="measure",
            pass_count_lifetime=0,
        )
        msg = build_agent_message(ctx, fail_verdict)
        
        # Override should NOT be in actions for first_run
        action_ids = [a.action_id for a in msg.suggested_actions]
        assert "override" not in action_ids

    def test_first_run_includes_help(self, fail_verdict):
        ctx = AgentContext(pass_count_lifetime=0)
        msg = build_agent_message(ctx, fail_verdict)
        
        action_ids = [a.action_id for a in msg.suggested_actions]
        assert "help" in action_ids

    def test_warn_novice_retry_first(self, warn_verdict):
        ctx = AgentContext(user_stage="novice")
        msg = build_agent_message(ctx, warn_verdict)
        
        # First action should be retry for novice
        assert msg.suggested_actions[0].action_id == "retry"

    def test_warn_regular_accept_first(self, warn_verdict):
        ctx = AgentContext(user_stage="regular")
        msg = build_agent_message(ctx, warn_verdict)
        
        # First action should be accept for regular
        assert msg.suggested_actions[0].action_id == "accept"


# =============================================================================
# Escalation Tests
# =============================================================================

class TestEscalation:
    """Tests for repeat-trigger escalation."""

    def test_repeated_q002_escalates_to_setup(self):
        rule = QualityRule("Q002", Severity.HARD, "Silent", "No signal")
        verdict = QualityVerdict(
            verdict=Verdict.FAIL,
            triggered_rules=[TriggeredRule(rule=rule, message="No signal")],
        )
        ctx = AgentContext(
            consecutive_rule_hits=(("Q002", 2),),
        )
        msg = build_agent_message(ctx, verdict)
        
        # Should have setup wizard action
        action_ids = [a.action_id for a in msg.suggested_actions]
        assert "run_setup" in action_ids

    def test_repeated_q011_escalates_to_gain_down(self):
        rule = QualityRule("Q011", Severity.SOFT, "Near clip", "Near clipping")
        verdict = QualityVerdict(
            verdict=Verdict.WARN,
            triggered_rules=[TriggeredRule(rule=rule, message="Near clipping")],
        )
        ctx = AgentContext(
            consecutive_rule_hits=(("Q011", 3),),
        )
        msg = build_agent_message(ctx, verdict)
        
        # Should have adjust_gain_down action
        action_ids = [a.action_id for a in msg.suggested_actions]
        assert "adjust_gain_down" in action_ids


# =============================================================================
# Render Tests
# =============================================================================

class TestRenderAgentMessageCLI:
    """Tests for CLI rendering."""

    def test_includes_title(self, pass_verdict):
        ctx = AgentContext()
        msg = build_agent_message(ctx, pass_verdict)
        output = render_agent_message_cli(msg)
        
        assert "Measurement accepted" in output

    def test_includes_summary(self, pass_verdict):
        ctx = AgentContext()
        msg = build_agent_message(ctx, pass_verdict)
        output = render_agent_message_cli(msg)
        
        assert "passed" in output.lower()

    def test_includes_actions(self, pass_verdict):
        ctx = AgentContext()
        msg = build_agent_message(ctx, pass_verdict)
        output = render_agent_message_cli(msg)
        
        assert "Suggested actions:" in output
        assert "Next point" in output

    def test_includes_hint(self, fail_verdict):
        ctx = AgentContext(pass_count_lifetime=0)
        msg = build_agent_message(ctx, fail_verdict)
        output = render_agent_message_cli(msg)
        
        if msg.learning_hint:
            assert msg.learning_hint in output

    def test_no_color_by_default(self, pass_verdict):
        ctx = AgentContext()
        msg = build_agent_message(ctx, pass_verdict)
        output = render_agent_message_cli(msg)
        
        assert "\033[" not in output  # No ANSI codes

    def test_color_mode(self, pass_verdict):
        ctx = AgentContext()
        msg = build_agent_message(ctx, pass_verdict)
        output = render_agent_message_cli(msg, color=True)
        
        assert "\033[32m" in output  # Green for pass


# =============================================================================
# Format Verdict Summary Agent Tests
# =============================================================================

class TestFormatVerdictSummaryAgent:
    """Tests for drop-in format_verdict_summary replacement."""

    def test_returns_string(self, pass_verdict):
        ctx = AgentContext()
        output = format_verdict_summary_agent(ctx, pass_verdict)
        
        assert isinstance(output, str)
        assert len(output) > 0

    def test_includes_verdict_info(self, fail_verdict):
        ctx = AgentContext()
        output = format_verdict_summary_agent(ctx, fail_verdict)
        
        assert "failed" in output.lower()
        assert "Suggested actions:" in output


# =============================================================================
# Rule Spec Validation Tests
# =============================================================================

class TestRuleSpecsComplete:
    """Validate all expected rules are defined."""

    def test_all_hard_rules_defined(self):
        for rid in ["Q001", "Q002", "Q003", "Q004", "Q005"]:
            assert rid in RULE_SPECS
            assert RULE_SPECS[rid].severity == Severity.HARD

    def test_all_soft_rules_defined(self):
        for rid in ["Q010", "Q011", "Q012", "Q013"]:
            assert rid in RULE_SPECS
            assert RULE_SPECS[rid].severity == Severity.SOFT

    def test_all_verdicts_defined(self):
        for v in [Verdict.PASS, Verdict.WARN, Verdict.FAIL]:
            assert v in VERDICT_TEMPLATES

    def test_ftue_hints_defined(self):
        assert "first_run" in FTUE_HINTS
        assert len(FTUE_HINTS["first_run"]) > 0
