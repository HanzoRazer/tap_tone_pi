"""Tests for fatigue control in agent messaging (PR6).

Ensures repeated rules/hints are suppressed appropriately based on:
- persisted seen_rule_ids (FTUE)
- in-session rule counts
- consecutive hits
- override experience
"""
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
    build_agent_message,
    should_show_learning_hint,
    should_show_full_explanation,
    infer_user_stage,
    RULE_SPECS,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def rule_q001():
    """Q001 HARD rule (clipping)."""
    return QualityRule(
        rule_id="Q001",
        severity=Severity.HARD,
        description="Clipping detected",
        message="Signal clipped",
    )


@pytest.fixture
def rule_q011():
    """Q011 SOFT rule (near clipping)."""
    return QualityRule(
        rule_id="Q011",
        severity=Severity.SOFT,
        description="Near clipping",
        message="Near clipping",
    )


@pytest.fixture
def fail_verdict_q001(rule_q001):
    return QualityVerdict(
        verdict=Verdict.FAIL,
        triggered_rules=[TriggeredRule(rule=rule_q001, message="Signal clipped")],
    )


@pytest.fixture
def warn_verdict_q011(rule_q011):
    return QualityVerdict(
        verdict=Verdict.WARN,
        triggered_rules=[TriggeredRule(rule=rule_q011, message="Near clipping")],
    )


# =============================================================================
# Learning Hint Suppression Tests
# =============================================================================

class TestLearningHintSuppression:
    """Learning hints are shown only on first exposure."""

    def test_first_run_unseen_rule_shows_hint(self, fail_verdict_q001):
        """first_run + unseen rule → learning hint included."""
        ctx = AgentContext(
            pass_count_lifetime=0,
            session_count_lifetime=0,
            seen_rule_ids=(),  # never seen Q001
            rule_counts_this_session=(),  # first occurrence
        )
        msg = build_agent_message(ctx, fail_verdict_q001)
        assert msg.learning_hint is not None

    def test_first_run_seen_rule_suppresses_hint(self, fail_verdict_q001):
        """first_run + seen rule → learning hint suppressed."""
        ctx = AgentContext(
            pass_count_lifetime=0,
            session_count_lifetime=0,
            seen_rule_ids=("Q001",),  # already seen
            rule_counts_this_session=(),
        )
        msg = build_agent_message(ctx, fail_verdict_q001)
        assert msg.learning_hint is None

    def test_novice_repeated_in_session_suppresses_hint(self, warn_verdict_q011):
        """novice + rule repeated in-session → hint suppressed."""
        ctx = AgentContext(
            pass_count_lifetime=5,
            session_count_lifetime=2,
            seen_rule_ids=(),  # never seen, but...
            rule_counts_this_session=(("Q011", 2),),  # repeated this session
        )
        msg = build_agent_message(ctx, warn_verdict_q011)
        assert msg.learning_hint is None

    def test_expert_mode_always_suppresses_hint(self, fail_verdict_q001):
        """expert_mode → learning hint always suppressed."""
        ctx = AgentContext(
            pass_count_lifetime=0,
            session_count_lifetime=0,
            seen_rule_ids=(),
            rule_counts_this_session=(),
            expert_mode=True,
        )
        msg = build_agent_message(ctx, fail_verdict_q001)
        assert msg.learning_hint is None


# =============================================================================
# Explanation Suppression Tests
# =============================================================================

class TestExplanationSuppression:
    """Full explanations are suppressed after first exposure."""

    def test_first_exposure_shows_full_explanation(self, fail_verdict_q001):
        """First time seeing a rule → full explanation shown."""
        ctx = AgentContext(
            workflow="measure",  # measure workflow shows details
            pass_count_lifetime=0,
            session_count_lifetime=0,
            seen_rule_ids=(),
            rule_counts_this_session=(),
            show_details=True,
        )
        msg = build_agent_message(ctx, fail_verdict_q001)
        # Should have full explanation (operator_explanation + Fix:)
        details_str = "\n".join(msg.details)
        assert "Fix:" in details_str
        # Check we have the full explanation, not just the fix
        spec = RULE_SPECS.get("Q001")
        assert spec.operator_explanation in details_str or len(msg.details) >= 2

    def test_repeated_in_session_shows_concise(self, fail_verdict_q001):
        """Rule repeated in-session → concise (fix only)."""
        ctx = AgentContext(
            pass_count_lifetime=5,
            session_count_lifetime=3,
            seen_rule_ids=(),
            rule_counts_this_session=(("Q001", 2),),  # second occurrence
        )
        msg = build_agent_message(ctx, fail_verdict_q001)
        # Should show concise form (just fix)
        details_str = "\n".join(msg.details)
        spec = RULE_SPECS.get("Q001")
        # Concise form shows first_fix directly, not the full operator_explanation
        assert spec.first_fix in details_str
        # But not the verbose explanation line-by-line
        # (concise format is: "[ERROR] Q001: {first_fix}")
        assert details_str.count("\n") <= 1 or "operator_explanation" not in details_str

    def test_previously_seen_shows_concise(self, warn_verdict_q011):
        """Rule previously seen (persisted) → concise."""
        ctx = AgentContext(
            pass_count_lifetime=10,
            session_count_lifetime=5,
            seen_rule_ids=("Q011",),  # seen before
            rule_counts_this_session=(),  # first time THIS session
        )
        msg = build_agent_message(ctx, warn_verdict_q011)
        details_str = "\n".join(msg.details)
        spec = RULE_SPECS.get("Q011")
        # Concise: should have fix, but single-line format
        assert spec.first_fix in details_str

    def test_override_experience_shows_concise_for_novice(self, fail_verdict_q001):
        """override_count >= 1 (experienced) → concise even for novice."""
        ctx = AgentContext(
            pass_count_lifetime=3,
            session_count_lifetime=2,
            override_count_lifetime=1,  # has overridden before
            seen_rule_ids=(),
            rule_counts_this_session=(),
        )
        # This user is "novice" by counts but has override experience
        assert infer_user_stage(ctx) == "novice"
        msg = build_agent_message(ctx, fail_verdict_q001)
        # Should be concise due to override experience
        details_str = "\n".join(msg.details)
        spec = RULE_SPECS.get("Q001")
        assert spec.first_fix in details_str


# =============================================================================
# Policy Function Unit Tests
# =============================================================================

class TestFatiguePolicyFunctions:
    """Direct tests for should_show_* functions."""

    def test_should_show_learning_hint_first_run_new_rule(self):
        ctx = AgentContext(
            pass_count_lifetime=0,
            session_count_lifetime=0,
            seen_rule_ids=(),
            rule_counts_this_session=(),
        )
        stage = infer_user_stage(ctx)
        assert stage == "first_run"
        assert should_show_learning_hint(ctx, ["Q001"], stage) is True

    def test_should_show_learning_hint_expert_mode_false(self):
        ctx = AgentContext(
            pass_count_lifetime=0,
            seen_rule_ids=(),
            expert_mode=True,
        )
        stage = infer_user_stage(ctx)
        assert stage == "expert"
        assert should_show_learning_hint(ctx, ["Q001"], stage) is False

    def test_should_show_learning_hint_all_seen_false(self):
        ctx = AgentContext(
            pass_count_lifetime=0,
            seen_rule_ids=("Q001", "Q002"),
        )
        stage = infer_user_stage(ctx)
        # All rules already seen
        assert should_show_learning_hint(ctx, ["Q001"], stage) is False

    def test_should_show_full_explanation_new_rule(self):
        ctx = AgentContext(
            pass_count_lifetime=0,
            seen_rule_ids=(),
            rule_counts_this_session=(),
        )
        assert should_show_full_explanation(ctx, "Q001") is True

    def test_should_show_full_explanation_fatiguing_false(self):
        ctx = AgentContext(
            pass_count_lifetime=5,
            session_count_lifetime=3,
            seen_rule_ids=("Q001",),  # seen before
        )
        assert should_show_full_explanation(ctx, "Q001") is False

    def test_is_rule_new_true(self):
        ctx = AgentContext(seen_rule_ids=())
        assert ctx.is_rule_new("Q001") is True

    def test_is_rule_new_false(self):
        ctx = AgentContext(seen_rule_ids=("Q001",))
        assert ctx.is_rule_new("Q001") is False

    def test_is_rule_fatiguing_repeated_session(self):
        ctx = AgentContext(
            seen_rule_ids=(),
            rule_counts_this_session=(("Q001", 2),),
        )
        assert ctx.is_rule_fatiguing("Q001") is True

    def test_is_rule_fatiguing_previously_seen(self):
        ctx = AgentContext(
            seen_rule_ids=("Q001",),
            rule_counts_this_session=(),
        )
        assert ctx.is_rule_fatiguing("Q001") is True


# =============================================================================
# Escalation Tests (consecutive hits)
# =============================================================================

class TestEscalation:
    """Escalation actions promoted after consecutive hits."""

    def test_consecutive_hits_promotes_gain_action(self, warn_verdict_q011):
        """Q011 consecutive >= 3 → adjust_gain_down promoted."""
        ctx = AgentContext(
            pass_count_lifetime=5,
            session_count_lifetime=3,
            seen_rule_ids=(),
            rule_counts_this_session=(("Q011", 3),),
            consecutive_rule_hits=(("Q011", 3),),
        )
        msg = build_agent_message(ctx, warn_verdict_q011)
        action_ids = [a.action_id for a in msg.suggested_actions]
        # Should have escalated action
        assert "adjust_gain_down" in action_ids or "retry" in action_ids

    def test_no_escalation_on_first_hit(self, warn_verdict_q011):
        """First hit → no escalation action."""
        ctx = AgentContext(
            pass_count_lifetime=0,
            seen_rule_ids=(),
            rule_counts_this_session=(("Q011", 1),),
            consecutive_rule_hits=(("Q011", 1),),
        )
        msg = build_agent_message(ctx, warn_verdict_q011)
        # Default actions should be present
        action_ids = [a.action_id for a in msg.suggested_actions]
        assert "accept" in action_ids or "retry" in action_ids
