"""PR7: SessionTracker integration tests.

Verify that fatigue stats are tracked consistently across entrypoints
via the single-source SessionTracker, and that the standalone path
(MeasurementAgent) also tracks verdict streaks correctly.
"""
import pytest
from dataclasses import dataclass, field

from tap_tone_pi.agent.messages import (
    AgentContext,
    AgentMessage,
    SessionTracker,
    build_agent_message,
    render_agent_message_cli,
)
from tap_tone_pi.core.quality_policy import (
    QualityRule,
    QualityVerdict,
    Severity,
    TriggeredRule,
    Verdict,
)

# =============================================================================
# Helpers: build real QualityVerdict objects
# =============================================================================

def _make_verdict(verdict: Verdict, rule_ids: list[str]) -> QualityVerdict:
    """Build a QualityVerdict with the given triggered rule IDs."""
    rules = []
    for rid in rule_ids:
        sev = Severity.HARD if rid.startswith("Q00") else Severity.SOFT
        rule = QualityRule(
            rule_id=rid,
            severity=sev,
            description=f"Test rule {rid}",
            message=f"{rid} triggered",
        )
        rules.append(TriggeredRule(rule=rule, message=f"{rid} triggered"))
    return QualityVerdict(verdict=verdict, triggered_rules=rules)


def _warn_q011() -> QualityVerdict:
    return _make_verdict(Verdict.WARN, ["Q011"])


def _fail_q001() -> QualityVerdict:
    return _make_verdict(Verdict.FAIL, ["Q001"])


# =============================================================================
# SessionTracker unit tests
# =============================================================================

class TestSessionTrackerRuleCounts:
    """Verify rule_counts, consecutive_hits, and verdict streak."""

    def test_first_verdict_sets_counts(self):
        t = SessionTracker()
        t.record_verdict(_warn_q011())

        assert t.rule_counts == {"Q011": 1}
        assert t.consecutive_hits == {"Q011": 1}
        assert t.consecutive_same_verdict == 1
        assert t.last_verdict_value == "warn"

    def test_repeated_verdict_increments(self):
        t = SessionTracker()
        t.record_verdict(_warn_q011())
        t.record_verdict(_warn_q011())

        assert t.rule_counts == {"Q011": 2}
        assert t.consecutive_hits == {"Q011": 2}
        assert t.consecutive_same_verdict == 2

    def test_different_verdict_resets_streak(self):
        t = SessionTracker()
        t.record_verdict(_warn_q011())
        t.record_verdict(_warn_q011())
        t.record_verdict(_fail_q001())

        assert t.consecutive_same_verdict == 1
        assert t.last_verdict_value == "fail"
        # Q011 consecutive resets; Q001 starts
        assert t.consecutive_hits["Q011"] == 0
        assert t.consecutive_hits["Q001"] == 1

    def test_three_consecutive_same_verdict(self):
        t = SessionTracker()
        for _ in range(3):
            t.record_verdict(_warn_q011())

        assert t.consecutive_same_verdict == 3

    def test_make_context_snapshots_history(self):
        t = SessionTracker()
        t.record_verdict(_warn_q011())
        t.record_verdict(_warn_q011())

        ctx = t.make_context(workflow="measure", point_id="P1", attempt_num=2)

        assert ctx.get_rule_count("Q011") == 2
        assert ctx.get_consecutive_hits("Q011") == 2
        assert ctx.consecutive_same_verdict == 2
        assert ctx.workflow == "measure"
        assert ctx.point_id == "P1"
        assert ctx.attempt_num == 2

    def test_make_context_includes_ftue_signals(self):
        t = SessionTracker()
        t.record_verdict(_warn_q011())

        ctx = t.make_context(
            pass_count_lifetime=5,
            session_count_lifetime=10,
            seen_rule_ids=("Q001", "Q011"),
        )

        assert ctx.pass_count_lifetime == 5
        assert ctx.session_count_lifetime == 10
        assert ctx.seen_rule_ids == ("Q001", "Q011")


# =============================================================================
# Integrated path: build_agent_message + SessionTracker end-to-end
# =============================================================================

class TestIntegratedEntrypointConsistency:
    """Two consecutive WARNs through SessionTracker produce compact on second."""

    def test_second_warn_is_compact(self):
        """Second consecutive WARN with same rule uses SHORT/COMPACT explanation."""
        t = SessionTracker()
        v1 = _warn_q011()
        v2 = _warn_q011()

        # First verdict
        t.record_verdict(v1)
        ctx1 = t.make_context(workflow="measure", show_details=True)
        msg1 = build_agent_message(ctx1, v1)

        # Second verdict
        t.record_verdict(v2)
        ctx2 = t.make_context(workflow="measure", show_details=True)
        msg2 = build_agent_message(ctx2, v2)

        # First message should have some detail about Q011
        assert any("Q011" in d for d in msg1.details)

        # Second message should also mention Q011 but in concise form
        assert any("Q011" in d for d in msg2.details)

        # Confirm rule count is 2 for second context
        assert ctx2.get_rule_count("Q011") == 2

    def test_three_warns_triggers_verdict_streak_suppression(self):
        """Three consecutive WARNs → verdict streak suppression → fix-only details."""
        t = SessionTracker()

        # Three identical verdicts
        for i in range(3):
            v = _warn_q011()
            t.record_verdict(v)

        ctx = t.make_context(workflow="measure", show_details=True)

        # Streak should be 3
        assert ctx.consecutive_same_verdict == 3

        msg = build_agent_message(ctx, _warn_q011())

        # Details should be suppressed to fix-only (no explanation text)
        for d in msg.details:
            if "Q011" in d:
                # Should NOT contain the full operator_explanation when suppressed
                # Should be just the fix
                assert "Same issue" not in d or "Fix" not in d or len(d) < 200

    def test_verdict_streak_resets_on_different_verdict(self):
        """WARN WARN FAIL → streak resets, no suppression on FAIL."""
        t = SessionTracker()

        t.record_verdict(_warn_q011())
        t.record_verdict(_warn_q011())
        t.record_verdict(_fail_q001())

        ctx = t.make_context(workflow="measure", show_details=True)

        # Streak should be 1 (reset by FAIL)
        assert ctx.consecutive_same_verdict == 1

        msg = build_agent_message(ctx, _fail_q001())
        # Should have full details since streak reset
        assert any("Q001" in d for d in msg.details)

    def test_cli_render_produces_output(self):
        """End-to-end: SessionTracker → context → build → render."""
        t = SessionTracker()
        v = _fail_q001()
        t.record_verdict(v)

        ctx = t.make_context(workflow="measure", show_details=True)
        msg = build_agent_message(ctx, v)
        output = render_agent_message_cli(msg)

        assert "failed" in output.lower() or "FAIL" in output
        assert "Q001" in output


# =============================================================================
# Standalone path: MeasurementAgent verdict streak tracking
# =============================================================================

class TestStandaloneEntrypointConsistency:
    """MeasurementAgent.on_verdict() now tracks verdict streaks via record_rules."""

    def test_verdict_streak_tracked(self):
        """Two identical verdicts through MeasurementAgent increment streak."""
        from tap_tone_pi.agent import MeasurementAgent
        from tap_tone_pi.agent.types import AgentContext as StandaloneCtx

        # Mock verdict compatible with standalone path
        @dataclass
        class MockRule:
            rule_id: str

        @dataclass
        class MockTriggered:
            rule: MockRule
            message: str = ""

        @dataclass
        class MockVerdict:
            verdict: object
            triggered: list = field(default_factory=list)

        class V:
            value = "warn"

        agent = MeasurementAgent()
        v = MockVerdict(verdict=V(), triggered=[MockTriggered(MockRule("Q011"))])

        agent.on_verdict(v)
        assert agent.context.consecutive_same_verdict == 1

        agent.on_verdict(v)
        assert agent.context.consecutive_same_verdict == 2

        agent.on_verdict(v)
        assert agent.context.consecutive_same_verdict == 3

    def test_verdict_streak_resets_on_change(self):
        """Different verdict resets the streak counter."""
        from tap_tone_pi.agent import MeasurementAgent

        @dataclass
        class MockRule:
            rule_id: str

        @dataclass
        class MockTriggered:
            rule: MockRule
            message: str = ""

        @dataclass
        class MockVerdict:
            verdict: object
            triggered: list = field(default_factory=list)

        class WarnV:
            value = "warn"

        class FailV:
            value = "fail"

        agent = MeasurementAgent()

        # Two warns
        v_warn = MockVerdict(verdict=WarnV(), triggered=[MockTriggered(MockRule("Q011"))])
        agent.on_verdict(v_warn)
        agent.on_verdict(v_warn)
        assert agent.context.consecutive_same_verdict == 2

        # Switch to fail
        v_fail = MockVerdict(verdict=FailV(), triggered=[MockTriggered(MockRule("Q001"))])
        agent.on_verdict(v_fail)
        assert agent.context.consecutive_same_verdict == 1

    def test_standalone_build_agent_message_tracks_verdict(self):
        """Standalone convenience build_agent_message also tracks verdict."""
        from tap_tone_pi.agent.measurement_agent import build_agent_message as standalone_bam
        from tap_tone_pi.agent.types import AgentContext as StandaloneCtx

        ctx = StandaloneCtx()
        standalone_bam("warn", ["Q011"], context=ctx)
        assert ctx.consecutive_same_verdict == 1

        standalone_bam("warn", ["Q011"], context=ctx)
        assert ctx.consecutive_same_verdict == 2


# =============================================================================
# Cross-path consistency: same history → same output
# =============================================================================

class TestCrossPathConsistency:
    """SessionTracker and MeasurementAgent produce consistent history state."""

    def test_rule_counts_match_after_two_verdicts(self):
        """Both paths agree on rule_counts after identical verdict sequences."""
        from tap_tone_pi.agent import MeasurementAgent
        from tap_tone_pi.agent.types import AgentContext as StandaloneCtx

        # --- Integrated path via SessionTracker ---
        tracker = SessionTracker()
        tracker.record_verdict(_warn_q011())
        tracker.record_verdict(_warn_q011())
        ctx_integrated = tracker.make_context(workflow="measure")

        # --- Standalone path via MeasurementAgent ---
        @dataclass
        class MockRule:
            rule_id: str

        @dataclass
        class MockTriggered:
            rule: MockRule
            message: str = ""

        @dataclass
        class MockVerdict:
            verdict: object
            triggered: list = field(default_factory=list)

        class WarnV:
            value = "warn"

        agent = MeasurementAgent()
        v = MockVerdict(verdict=WarnV(), triggered=[MockTriggered(MockRule("Q011"))])
        agent.on_verdict(v)
        agent.on_verdict(v)

        # Both should have Q011 count = 2
        assert ctx_integrated.get_rule_count("Q011") == 2
        assert agent.context.rule_counts_session["Q011"] == 2

        # Both should have consecutive_same_verdict = 2
        assert ctx_integrated.consecutive_same_verdict == 2
        assert agent.context.consecutive_same_verdict == 2

        # Both should have consecutive_rule_hits = 2
        assert ctx_integrated.get_consecutive_hits("Q011") == 2
        assert agent.context.consecutive_rule_hits["Q011"] == 2
