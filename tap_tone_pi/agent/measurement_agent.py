"""Measurement Agent — the orchestration layer that coordinates without altering facts.

The agent:
- Observes system state
- Sequences actions
- Explains outcomes
- Guides operators
- Enforces rules

It NEVER:
- Modifies DSP results
- Invents interpretations
- Auto-adjusts parameters
- Makes silent decisions
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from .types import ActionId, AgentContext, AgentMessage, SuggestedAction, UserStage
from .message_spec import get_rule_spec, get_verdict_template
from .selector import order_rules, select_actions_for_verdict, build_rule_detail
from .ftue import (
    get_ftue_hint,
    max_rules_to_show,
    max_actions_to_show,
    show_why_it_matters,
)

if TYPE_CHECKING:
    from tap_tone_pi.core.quality_policy import QualityVerdict


@dataclass
class MeasurementAgent:
    """Stateful conductor for measurement workflows.
    
    The agent wraps the quality gate and workflow components,
    providing structured explanations and action guidance
    without modifying measurement facts.
    """
    context: AgentContext = field(default_factory=AgentContext)
    on_message: Callable[[AgentMessage], None] | None = None
    
    def on_verdict(self, verdict: "QualityVerdict") -> AgentMessage:
        """Process a quality verdict and generate operator guidance.
        
        This is the main entry point after a quality check completes.
        
        Args:
            verdict: The QualityVerdict from check_quality()
        
        Returns:
            AgentMessage with title, summary, details, and suggested actions
        """
        # Extract rule IDs from triggered rules
        rule_ids = [r.rule.rule_id for r in verdict.triggered]
        verdict_str = verdict.verdict.value.lower()  # "pass", "warn", "fail"
        
        # Update context history
        self.context.record_rules(rule_ids)
        
        # Build the message
        message = self._build_message(verdict_str, rule_ids)
        
        # Emit if callback registered
        if self.on_message:
            self.on_message(message)
        
        return message
    
    def _build_message(
        self,
        verdict: str,
        rule_ids: list[str],
    ) -> AgentMessage:
        """Build an AgentMessage from verdict and rules."""
        template = get_verdict_template(verdict)
        stage = self.context.user_stage
        
        # Order and limit rules based on FTUE stage
        ordered_rules = order_rules(rule_ids)
        max_rules = max_rules_to_show(stage)
        display_rules = ordered_rules[:max_rules]
        
        # Build detail lines for each rule
        details: list[str] = []
        for rule_id in display_rules:
            spec = get_rule_spec(rule_id)
            if spec:
                include_why = show_why_it_matters(stage, spec.severity)
                detail = build_rule_detail(spec, self.context, include_why=include_why)
                details.append(detail)
        
        # Select actions
        actions = select_actions_for_verdict(verdict, rule_ids, self.context)
        max_actions = max_actions_to_show(stage)
        display_actions = actions[:max_actions]
        
        # Always include Help for first_run/novice if not already present
        if stage in (UserStage.FIRST_RUN, UserStage.NOVICE):
            if not any(a.action_id == ActionId.HELP for a in display_actions):
                display_actions.append(SuggestedAction(
                    ActionId.HELP, "Help", "Show guidance"
                ))
        
        # Get FTUE hint
        hint = get_ftue_hint(stage, self.context.attempt_num)
        
        return AgentMessage(
            title=template.title,
            summary=template.summary,
            details=details,
            suggested_actions=display_actions,
            learning_hint=hint,
            telemetry_tags={
                "verdict": verdict,
                "rule_ids": rule_ids,
                "user_stage": stage.value,
                "attempt_num": self.context.attempt_num,
                "point_id": self.context.point_id,
            },
        )
    
    def suggest_next_action(self) -> SuggestedAction | None:
        """Get the primary recommended action based on current state.
        
        Returns the first action from the most recent message,
        or None if no actions available.
        """
        # This would typically look at the last message generated
        # For now, return None (caller should use on_verdict result)
        return None
    
    def reset_for_point(self, point_id: str) -> None:
        """Reset attempt-level context for a new point."""
        self.context.point_id = point_id
        self.context.attempt_num = 1
        self.context.consecutive_rule_hits.clear()
    
    def advance_attempt(self) -> None:
        """Increment attempt counter (on retry)."""
        self.context.attempt_num += 1


def build_agent_message(
    verdict: str,
    rule_ids: list[str],
    context: AgentContext | None = None,
) -> AgentMessage:
    """Convenience function to build an agent message without instantiating agent.
    
    Use this in existing code paths that just need message generation.
    
    Args:
        verdict: "pass", "warn", or "fail"
        rule_ids: List of triggered rule IDs (e.g., ["Q001", "Q011"])
        context: Optional AgentContext; uses defaults if not provided
    
    Returns:
        AgentMessage ready for CLI/GUI rendering
    """
    ctx = context or AgentContext()
    ctx.record_rules(rule_ids)
    
    agent = MeasurementAgent(context=ctx)
    return agent._build_message(verdict, rule_ids)
