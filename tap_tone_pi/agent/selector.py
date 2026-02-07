"""Selector — rule ordering, action selection, and escalation logic.

Determines what to show and in what order based on context and history.
"""
from __future__ import annotations

from .types import ActionId, AgentContext, SuggestedAction, UserStage
from .message_spec import RuleSpec, get_rule_spec


# =============================================================================
# RULE ORDERING
# =============================================================================

def order_rules(rule_ids: list[str]) -> list[str]:
    """Order rules by priority for display.
    
    Priority:
    1. HARD rules first (Q001–Q005)
    2. Within HARD: likely-fixable causes first (clipping, silent, device)
    3. SOFT rules after (Q010–Q013)
    """
    hard_priority = ["Q001", "Q002", "Q005", "Q003", "Q004"]
    soft_priority = ["Q010", "Q011", "Q012", "Q013"]
    
    def sort_key(rule_id: str) -> tuple[int, int]:
        if rule_id in hard_priority:
            return (0, hard_priority.index(rule_id))
        elif rule_id in soft_priority:
            return (1, soft_priority.index(rule_id))
        return (2, 0)  # Unknown rules last
    
    return sorted(rule_ids, key=sort_key)


# =============================================================================
# ACTION SELECTION
# =============================================================================

def select_actions_for_verdict(
    verdict: str,
    triggered_rules: list[str],
    context: AgentContext,
) -> list[SuggestedAction]:
    """Select appropriate actions based on verdict and context.
    
    Rules:
    - FAIL: Retry + fix hint → abort/override on later attempts
    - WARN: Accept primary for experienced users, retry for novice
    - PASS: Always advance
    """
    actions: list[SuggestedAction] = []
    
    if verdict == "pass":
        actions.append(SuggestedAction(
            ActionId.ADVANCE, "Next point", "Proceed in workflow"
        ))
        return actions
    
    if verdict == "fail":
        return _select_fail_actions(triggered_rules, context)
    
    if verdict == "warn":
        return _select_warn_actions(triggered_rules, context)
    
    return actions


def _select_fail_actions(
    triggered_rules: list[str],
    context: AgentContext,
) -> list[SuggestedAction]:
    """Select actions for FAIL verdict with escalation."""
    actions: list[SuggestedAction] = []
    ordered_rules = order_rules(triggered_rules)
    
    # Get the primary rule's actions
    if ordered_rules:
        primary_spec = get_rule_spec(ordered_rules[0])
        if primary_spec:
            # Check for repeat-trigger escalation
            consecutive = context.consecutive_rule_hits.get(ordered_rules[0], 0)
            
            if consecutive >= 2:
                # Escalate to more specific fix
                actions.extend(_escalate_actions(primary_spec, consecutive))
            else:
                # Use default actions from spec
                actions.extend(primary_spec.agent_actions[:2])
    
    # On attempt 3+, promote abort/override
    if context.attempt_num >= 3:
        if not any(a.action_id == ActionId.ABORT for a in actions):
            actions.append(SuggestedAction(
                ActionId.ABORT, "Abort", "Stop and troubleshoot"
            ))
        actions.append(SuggestedAction(
            ActionId.OVERRIDE, "Override (requires reason)",
            "Log exception explicitly", requires_input=True
        ))
    
    return actions


def _select_warn_actions(
    triggered_rules: list[str],
    context: AgentContext,
) -> list[SuggestedAction]:
    """Select actions for WARN verdict based on user stage."""
    actions: list[SuggestedAction] = []
    
    # Novice/first_run: recommend retry first
    if context.user_stage in (UserStage.FIRST_RUN, UserStage.NOVICE):
        actions.append(SuggestedAction(
            ActionId.RETRY, "Retry", "Try for cleaner capture"
        ))
        actions.append(SuggestedAction(
            ActionId.ACCEPT, "Accept with warning", "Proceed with warning noted"
        ))
    else:
        # Regular/expert: accept is primary
        actions.append(SuggestedAction(
            ActionId.ACCEPT, "Accept", "Proceed with warning noted"
        ))
        actions.append(SuggestedAction(
            ActionId.RETRY, "Retry", "Try for cleaner capture"
        ))
    
    return actions


def _escalate_actions(spec: RuleSpec, consecutive_hits: int) -> list[SuggestedAction]:
    """Escalate actions for repeated rule triggers."""
    escalated: list[SuggestedAction] = []
    
    # Map rule IDs to escalated actions
    escalation_map: dict[str, SuggestedAction] = {
        "Q001": SuggestedAction(
            ActionId.ADJUST_GAIN_DOWN,
            "Lower gain (repeated clipping)",
            "Clipping persists—reduce input gain"
        ),
        "Q002": SuggestedAction(
            ActionId.RUN_SETUP,
            "Run setup wizard (repeated silence)",
            "Likely wrong device—reconfigure"
        ),
        "Q011": SuggestedAction(
            ActionId.ADJUST_GAIN_DOWN,
            "Lower gain (repeated near-clipping)",
            f"Near-clipping {consecutive_hits}× in a row"
        ),
        "Q004": SuggestedAction(
            ActionId.CHECK_ENVIRONMENT,
            "Check environment (repeated low confidence)",
            "Noise or coupling issue"
        ),
    }
    
    escalated_action = escalation_map.get(spec.rule_id)
    if escalated_action:
        escalated.append(escalated_action)
    
    # Always include retry as fallback
    escalated.append(SuggestedAction(
        ActionId.RETRY, "Retry", "Attempt again after adjustment"
    ))
    
    return escalated


# =============================================================================
# EXPLANATION BUILDING
# =============================================================================

def build_rule_detail(
    spec: RuleSpec,
    context: AgentContext,
    include_why: bool = True,
    include_fix: bool = True,
) -> str:
    """Build a single rule's detail line for display."""
    severity_tag = "[ERROR]" if spec.severity == "HARD" else "[WARN]"
    
    parts = [f"{severity_tag} {spec.rule_id}: {spec.operator_explanation}"]
    
    if include_why:
        parts.append(f"  → {spec.why_it_matters}")
    
    if include_fix:
        # Check for consecutive hits → show fallback fix
        consecutive = context.consecutive_rule_hits.get(spec.rule_id, 0)
        if consecutive >= 2:
            parts.append(f"  Fix: {spec.fallback_fix}")
        else:
            parts.append(f"  Fix: {spec.first_fix}")
    
    return "\n".join(parts)
