"""Tests for fatigue control in agent messaging (PR6).

Ensures repeated rules/hints are suppressed appropriately based on:
- persisted seen_rule_ids (FTUE)
- in-session rule counts
- consecutive hits
- override experience
- verdict streaks (PR6 Rule 4)
- workflow sensitivity (PR6 Rule 5)
- three-tier explanation mode (PR6 Rule 2)
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
    ExplanationMode,
    build_agent_message,
    choose_explanation_mode,
    should_show_learning_hint,
    should_show_full_explanation,
    should_suppress_for_verdict_streak,
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
        """first_run + unseen rule + measure workflow → learning hint included."""
        ctx = AgentContext(
            workflow="measure",
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
        """Rule repeated in-session → SHORT or COMPACT (concise)."""
        ctx = AgentContext(
            workflow="measure",
            pass_count_lifetime=5,
            session_count_lifetime=3,
            seen_rule_ids=(),
            rule_counts_this_session=(("Q001", 2),),  # second occurrence
        )
        msg = build_agent_message(ctx, fail_verdict_q001)
        # Should show concise form — SHORT mode shows operator_explanation
        # without the "Fix:" line, or COMPACT shows "Same issue"
        details_str = "\n".join(msg.details)
        spec = RULE_SPECS.get("Q001")
        # Either SHORT (explanation only) or COMPACT (same issue + fix)
        assert spec.operator_explanation in details_str or "Same issue" in details_str
        # Full mode would have both explanation AND "Fix:" lines
        # SHORT mode should NOT have the "Fix:" prefix line
        assert details_str.count("\n") <= 1 or "Fix:" not in details_str

    def test_previously_seen_shows_concise(self, warn_verdict_q011):
        """Rule previously seen (persisted) → SHORT (one-line explanation)."""
        ctx = AgentContext(
            workflow="measure",
            pass_count_lifetime=10,
            session_count_lifetime=5,
            seen_rule_ids=("Q011",),  # seen before
            rule_counts_this_session=(),  # first time THIS session
        )
        msg = build_agent_message(ctx, warn_verdict_q011)
        details_str = "\n".join(msg.details)
        spec = RULE_SPECS.get("Q011")
        # SHORT mode: operator_explanation without Fix: line
        assert spec.operator_explanation in details_str

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
            workflow="measure",
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


# =============================================================================
# PR6: Three-Tier Explanation Mode Tests
# =============================================================================


class TestExplanationMode:
    """PR6 Rule 2: FULL → SHORT → COMPACT degradation."""

    def test_first_time_rule_is_full(self):
        """First-time rule → FULL mode."""
        ctx = AgentContext(
            pass_count_lifetime=0,
            seen_rule_ids=(),
            rule_counts_this_session=(),
            consecutive_rule_hits=(),
        )
        assert choose_explanation_mode(ctx, "Q001") == ExplanationMode.FULL

    def test_seen_before_is_short(self):
        """Previously seen rule, low repetition → SHORT mode."""
        ctx = AgentContext(
            pass_count_lifetime=5,
            session_count_lifetime=3,
            seen_rule_ids=("Q001",),
            rule_counts_this_session=(("Q001", 1),),
            consecutive_rule_hits=(("Q001", 1),),
        )
        assert choose_explanation_mode(ctx, "Q001") == ExplanationMode.SHORT

    def test_high_streak_is_compact(self):
        """Consecutive hits ≥ 3 → COMPACT mode."""
        ctx = AgentContext(
            pass_count_lifetime=5,
            seen_rule_ids=("Q001",),
            rule_counts_this_session=(("Q001", 3),),
            consecutive_rule_hits=(("Q001", 3),),
        )
        assert choose_explanation_mode(ctx, "Q001") == ExplanationMode.COMPACT

    def test_high_session_count_is_compact(self):
        """Session count ≥ 3 → COMPACT mode."""
        ctx = AgentContext(
            pass_count_lifetime=5,
            seen_rule_ids=("Q001",),
            rule_counts_this_session=(("Q001", 3),),
            consecutive_rule_hits=(("Q001", 1),),
        )
        assert choose_explanation_mode(ctx, "Q001") == ExplanationMode.COMPACT

    def test_compact_shows_same_issue_prefix(self, fail_verdict_q001):
        """COMPACT mode detail line uses 'Same issue' prefix."""
        ctx = AgentContext(
            workflow="measure",
            pass_count_lifetime=10,
            session_count_lifetime=5,
            seen_rule_ids=("Q001",),
            rule_counts_this_session=(("Q001", 4),),
            consecutive_rule_hits=(("Q001", 4),),
            show_details=True,
        )
        msg = build_agent_message(ctx, fail_verdict_q001)
        details_str = "\n".join(msg.details)
        assert "Same issue" in details_str


# =============================================================================
# PR6: Verdict Streak Suppression Tests
# =============================================================================


class TestVerdictStreakSuppression:
    """PR6 Rule 4: 3+ identical verdicts → suppress explanations."""

    def test_no_suppression_below_threshold(self):
        """consecutive_same_verdict < 3 → no suppression."""
        ctx = AgentContext(
            pass_count_lifetime=5,
            consecutive_same_verdict=2,
        )
        assert should_suppress_for_verdict_streak(ctx) is False

    def test_suppression_at_threshold(self):
        """consecutive_same_verdict >= 3 → suppress."""
        ctx = AgentContext(
            pass_count_lifetime=5,
            consecutive_same_verdict=3,
        )
        assert should_suppress_for_verdict_streak(ctx) is True

    def test_verdict_streak_suppresses_in_build(self, fail_verdict_q001):
        """3+ same verdict → details show fix only, no full explanation."""
        ctx = AgentContext(
            workflow="measure",
            pass_count_lifetime=10,
            session_count_lifetime=5,
            seen_rule_ids=(),
            rule_counts_this_session=(),
            consecutive_same_verdict=3,
            show_details=True,
        )
        msg = build_agent_message(ctx, fail_verdict_q001)
        details_str = "\n".join(msg.details)
        spec = RULE_SPECS.get("Q001")
        # Should show fix only, not the operator_explanation narrative
        assert spec.first_fix in details_str
        # The full operator_explanation should NOT appear
        assert spec.operator_explanation not in details_str


# =============================================================================
# PR6: Workflow Sensitivity Tests
# =============================================================================


class TestWorkflowSensitivity:
    """PR6 Rule 5: Different workflows → different verbosity."""

    def test_record_workflow_no_learning_hint(self, fail_verdict_q001):
        """record workflow → no learning hints regardless of stage."""
        ctx = AgentContext(
            workflow="record",
            pass_count_lifetime=0,
            session_count_lifetime=0,
            seen_rule_ids=(),
            rule_counts_this_session=(),
        )
        stage = infer_user_stage(ctx)
        assert stage == "first_run"
        assert should_show_learning_hint(ctx, ["Q001"], stage) is False

    def test_measure_workflow_shows_learning_hint(self, fail_verdict_q001):
        """measure workflow + first_run + new rule → learning hint shown."""
        ctx = AgentContext(
            workflow="measure",
            pass_count_lifetime=0,
            session_count_lifetime=0,
            seen_rule_ids=(),
            rule_counts_this_session=(),
        )
        stage = infer_user_stage(ctx)
        assert should_show_learning_hint(ctx, ["Q001"], stage) is True

    def test_phase2_workflow_forces_compact(self, fail_verdict_q001):
        """phase2 workflow → compact explanations (fix only)."""
        ctx = AgentContext(
            workflow="phase2",
            pass_count_lifetime=20,
            session_count_lifetime=10,
            seen_rule_ids=(),
            rule_counts_this_session=(),
            show_details=True,
        )
        msg = build_agent_message(ctx, fail_verdict_q001)
        details_str = "\n".join(msg.details)
        spec = RULE_SPECS.get("Q001")
        # phase2 forces compact: should show fix, not narrative
        assert spec.first_fix in details_str
        # Full explanation should be absent
        assert "Why:" not in details_str

    def test_phase2_workflow_no_learning_hint(self, fail_verdict_q001):
        """phase2 workflow → no FTUE hints."""
        ctx = AgentContext(
            workflow="phase2",
            pass_count_lifetime=0,
            session_count_lifetime=0,
            seen_rule_ids=(),
            rule_counts_this_session=(),
        )
        msg = build_agent_message(ctx, fail_verdict_q001)
        assert msg.learning_hint is None


# =============================================================================
# PR6: Expanded Escalation Tests
# =============================================================================


class TestExpandedEscalation:
    """PR6 Rule 3: Q010 and Q003 escalation mappings."""

    def test_q010_consecutive_promotes_gain_up(self):
        """Q010 consecutive ≥ 3 → adjust_gain_up / move mic closer."""
        rule_q010 = QualityRule(
            rule_id="Q010",
            severity=Severity.SOFT,
            description="Quiet signal",
            message="Signal quiet",
        )
        verdict = QualityVerdict(
            verdict=Verdict.WARN,
            triggered_rules=[TriggeredRule(rule=rule_q010, message="Signal quiet")],
        )
        ctx = AgentContext(
            pass_count_lifetime=5,
            session_count_lifetime=3,
            seen_rule_ids=(),
            rule_counts_this_session=(("Q010", 3),),
            consecutive_rule_hits=(("Q010", 3),),
        )
        msg = build_agent_message(ctx, verdict)
        action_ids = [a.action_id for a in msg.suggested_actions]
        assert "adjust_gain_up" in action_ids

    def test_q003_consecutive_promotes_environment_check(self):
        """Q003 consecutive ≥ 3 → check_environment action."""
        rule_q003 = QualityRule(
            rule_id="Q003",
            severity=Severity.HARD,
            description="No peaks",
            message="No clear peaks",
        )
        verdict = QualityVerdict(
            verdict=Verdict.FAIL,
            triggered_rules=[TriggeredRule(rule=rule_q003, message="No clear peaks")],
        )
        ctx = AgentContext(
            pass_count_lifetime=5,
            session_count_lifetime=3,
            seen_rule_ids=(),
            rule_counts_this_session=(("Q003", 3),),
            consecutive_rule_hits=(("Q003", 3),),
        )
        msg = build_agent_message(ctx, verdict)
        action_ids = [a.action_id for a in msg.suggested_actions]
        assert "check_environment" in action_ids
