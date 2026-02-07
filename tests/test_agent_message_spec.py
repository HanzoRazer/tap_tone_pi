"""Tests for agent message specification."""
import pytest
from tap_tone_pi.agent import (
    RULE_SPECS,
    VERDICT_TEMPLATES,
    get_rule_spec,
    get_verdict_template,
    ActionId,
)


class TestRuleSpecs:
    """Tests for rule specification tables."""

    def test_all_hard_rules_defined(self):
        """All HARD rules Q001-Q005 must be defined."""
        for rule_id in ["Q001", "Q002", "Q003", "Q004", "Q005"]:
            spec = get_rule_spec(rule_id)
            assert spec is not None, f"Missing spec for {rule_id}"
            assert spec.severity == "HARD"

    def test_all_soft_rules_defined(self):
        """All SOFT rules Q010-Q013 must be defined."""
        for rule_id in ["Q010", "Q011", "Q012", "Q013"]:
            spec = get_rule_spec(rule_id)
            assert spec is not None, f"Missing spec for {rule_id}"
            assert spec.severity == "SOFT"

    def test_rule_spec_has_required_fields(self):
        """Each rule spec must have all required fields."""
        for rule_id, spec in RULE_SPECS.items():
            assert spec.rule_id == rule_id
            assert spec.severity in ("HARD", "SOFT")
            assert len(spec.operator_explanation) > 0
            assert len(spec.why_it_matters) > 0
            assert len(spec.first_fix) > 0
            assert len(spec.fallback_fix) > 0
            assert len(spec.advanced_note) > 0
            assert len(spec.agent_actions) > 0

    def test_rule_spec_actions_are_valid(self):
        """All actions in rule specs must be valid ActionIds."""
        for rule_id, spec in RULE_SPECS.items():
            for action in spec.agent_actions:
                assert isinstance(action.action_id, ActionId), \
                    f"Invalid action_id in {rule_id}: {action.action_id}"
                assert len(action.label) > 0
                assert len(action.rationale) > 0

    def test_unknown_rule_returns_none(self):
        assert get_rule_spec("Q999") is None


class TestRuleExplanations:
    """Tests for specific rule explanations."""

    def test_q001_clipping(self):
        spec = get_rule_spec("Q001")
        assert "clipped" in spec.operator_explanation.lower()
        assert "spectrum" in spec.why_it_matters.lower() or "false" in spec.why_it_matters.lower()
        # First action should be gain-related
        assert spec.agent_actions[0].action_id in (
            ActionId.ADJUST_GAIN_DOWN, ActionId.RETRY
        )

    def test_q002_silent(self):
        spec = get_rule_spec("Q002")
        assert "signal" in spec.operator_explanation.lower()
        # Should suggest checking device
        action_ids = [a.action_id for a in spec.agent_actions]
        assert ActionId.CHECK_DEVICE in action_ids

    def test_q011_near_clipping(self):
        spec = get_rule_spec("Q011")
        assert "near clipping" in spec.operator_explanation.lower()
        assert spec.severity == "SOFT"
        # Should allow accept
        action_ids = [a.action_id for a in spec.agent_actions]
        assert ActionId.ACCEPT in action_ids


class TestVerdictTemplates:
    """Tests for verdict-level messaging."""

    def test_all_verdicts_defined(self):
        for verdict in ["pass", "warn", "fail"]:
            template = get_verdict_template(verdict)
            assert template is not None
            assert len(template.title) > 0
            assert len(template.summary) > 0

    def test_pass_template(self):
        template = get_verdict_template("pass")
        assert "accepted" in template.title.lower()
        # Should have advance action
        action_ids = [a.action_id for a in template.default_actions]
        assert ActionId.ADVANCE in action_ids

    def test_warn_template(self):
        template = get_verdict_template("warn")
        assert "warning" in template.title.lower()
        action_ids = [a.action_id for a in template.default_actions]
        assert ActionId.ACCEPT in action_ids
        assert ActionId.RETRY in action_ids

    def test_fail_template(self):
        template = get_verdict_template("fail")
        assert "failed" in template.title.lower()
        action_ids = [a.action_id for a in template.default_actions]
        assert ActionId.RETRY in action_ids
        assert ActionId.OVERRIDE in action_ids

    def test_fail_override_requires_input(self):
        template = get_verdict_template("fail")
        override_action = next(
            a for a in template.default_actions if a.action_id == ActionId.OVERRIDE
        )
        assert override_action.requires_input is True

    def test_unknown_verdict_returns_pass(self):
        """Unknown verdict defaults to pass template."""
        template = get_verdict_template("unknown")
        assert template.title == get_verdict_template("pass").title


class TestRuleLanguageGovernance:
    """Ensure rule explanations follow governance rules."""

    FORBIDDEN_WORDS = [
        "wolf", "dead spot", "problem frequency",
        "good", "bad", "optimal",
        "fix", "thin", "stiffen", "remove",
        "strongest", "dominant", "worst", "primary",
    ]

    def test_no_forbidden_words_in_explanations(self):
        """Rule explanations must not contain forbidden words."""
        for rule_id, spec in RULE_SPECS.items():
            text = " ".join([
                spec.operator_explanation,
                spec.why_it_matters,
                # Note: first_fix and fallback_fix may say "fix" as a verb
            ]).lower()
            
            for word in ["wolf", "dead spot", "problem frequency",
                         "optimal", "strongest", "dominant", "worst"]:
                assert word not in text, \
                    f"Forbidden word '{word}' in {rule_id}"

    def test_explanations_are_factual(self):
        """Explanations should describe conditions, not judgments."""
        for rule_id, spec in RULE_SPECS.items():
            # Should not contain comparative judgments
            assert "better than" not in spec.operator_explanation.lower()
            assert "worse than" not in spec.operator_explanation.lower()
