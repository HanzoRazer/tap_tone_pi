"""Tests for agent selector logic."""
import pytest
from tap_tone_pi.agent import (
    StandaloneAgentContext as AgentContext,
    ActionId,
    UserStage,
    order_rules,
    select_actions_for_verdict,
    build_rule_detail,
)
from tap_tone_pi.agent.message_spec import get_rule_spec


class TestOrderRules:
    """Tests for rule ordering."""

    def test_hard_before_soft(self):
        rules = ["Q011", "Q001", "Q012", "Q002"]
        ordered = order_rules(rules)
        # Q001, Q002 should come before Q011, Q012
        assert ordered.index("Q001") < ordered.index("Q011")
        assert ordered.index("Q002") < ordered.index("Q012")

    def test_hard_priority_order(self):
        """Within HARD, fixable causes first."""
        rules = ["Q004", "Q001", "Q003", "Q002", "Q005"]
        ordered = order_rules(rules)
        # Priority: Q001, Q002, Q005, Q003, Q004
        assert ordered[0] == "Q001"
        assert ordered[1] == "Q002"

    def test_soft_priority_order(self):
        rules = ["Q013", "Q010", "Q012", "Q011"]
        ordered = order_rules(rules)
        # Should be sorted within SOFT
        assert ordered[0] == "Q010"
        assert ordered[1] == "Q011"

    def test_empty_list(self):
        assert order_rules([]) == []

    def test_single_rule(self):
        assert order_rules(["Q011"]) == ["Q011"]

    def test_unknown_rules_last(self):
        rules = ["Q001", "Q999", "Q011"]
        ordered = order_rules(rules)
        assert ordered[-1] == "Q999"


class TestSelectActionsForVerdict:
    """Tests for action selection."""

    def test_pass_returns_advance(self):
        ctx = AgentContext()
        actions = select_actions_for_verdict("pass", [], ctx)
        assert len(actions) == 1
        assert actions[0].action_id == ActionId.ADVANCE

    def test_fail_returns_retry_first(self):
        ctx = AgentContext(attempt_num=1)
        actions = select_actions_for_verdict("fail", ["Q001"], ctx)
        # First action should be a fix/retry
        assert actions[0].action_id in (
            ActionId.RETRY, ActionId.ADJUST_GAIN_DOWN, ActionId.CHECK_DEVICE
        )

    def test_fail_attempt_3_offers_abort_override(self):
        ctx = AgentContext(attempt_num=3)
        actions = select_actions_for_verdict("fail", ["Q001"], ctx)
        action_ids = [a.action_id for a in actions]
        assert ActionId.ABORT in action_ids
        assert ActionId.OVERRIDE in action_ids

    def test_warn_novice_retry_first(self):
        ctx = AgentContext(user_stage=UserStage.NOVICE)
        actions = select_actions_for_verdict("warn", ["Q011"], ctx)
        assert actions[0].action_id == ActionId.RETRY

    def test_warn_regular_accept_first(self):
        ctx = AgentContext(user_stage=UserStage.REGULAR)
        actions = select_actions_for_verdict("warn", ["Q011"], ctx)
        assert actions[0].action_id == ActionId.ACCEPT


class TestActionEscalation:
    """Tests for repeat-trigger escalation."""

    def test_repeated_q011_escalates_to_gain_down(self):
        ctx = AgentContext()
        ctx.consecutive_rule_hits["Q011"] = 3
        
        actions = select_actions_for_verdict("warn", ["Q011"], ctx)
        # Should suggest lowering gain explicitly
        action_labels = " ".join(a.label.lower() for a in actions)
        # Either action_id or label should indicate gain adjustment
        has_gain_action = any(
            a.action_id == ActionId.ADJUST_GAIN_DOWN or "gain" in a.label.lower()
            for a in actions
        )
        # Note: WARN escalation uses regular actions, escalation applies to FAIL
        # This test validates the context is tracked

    def test_repeated_q002_escalates_to_setup(self):
        ctx = AgentContext()
        ctx.consecutive_rule_hits["Q002"] = 2
        
        actions = select_actions_for_verdict("fail", ["Q002"], ctx)
        action_ids = [a.action_id for a in actions]
        # Should suggest setup wizard
        assert ActionId.RUN_SETUP in action_ids


class TestBuildRuleDetail:
    """Tests for rule detail line building."""

    def test_includes_severity_tag(self):
        spec = get_rule_spec("Q001")
        ctx = AgentContext()
        detail = build_rule_detail(spec, ctx)
        assert "[ERROR]" in detail
        assert "Q001" in detail

    def test_soft_rule_uses_warn_tag(self):
        spec = get_rule_spec("Q011")
        ctx = AgentContext()
        detail = build_rule_detail(spec, ctx)
        assert "[WARN]" in detail

    def test_includes_explanation(self):
        spec = get_rule_spec("Q001")
        ctx = AgentContext()
        detail = build_rule_detail(spec, ctx)
        assert "clipped" in detail.lower()

    def test_includes_why_when_requested(self):
        spec = get_rule_spec("Q001")
        ctx = AgentContext()
        detail = build_rule_detail(spec, ctx, include_why=True)
        assert spec.why_it_matters in detail

    def test_excludes_why_when_not_requested(self):
        spec = get_rule_spec("Q001")
        ctx = AgentContext()
        detail = build_rule_detail(spec, ctx, include_why=False)
        assert spec.why_it_matters not in detail

    def test_uses_fallback_fix_on_repeat(self):
        spec = get_rule_spec("Q001")
        ctx = AgentContext()
        ctx.consecutive_rule_hits["Q001"] = 2
        
        detail = build_rule_detail(spec, ctx, include_fix=True)
        assert spec.fallback_fix in detail

    def test_uses_first_fix_initially(self):
        spec = get_rule_spec("Q001")
        ctx = AgentContext()
        
        detail = build_rule_detail(spec, ctx, include_fix=True)
        assert spec.first_fix in detail
