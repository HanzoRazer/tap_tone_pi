# INSTRUMENT CLASS: DECISION SUPPORT
"""Selector — rule ordering, action selection, and escalation logic.

Determines what to show and in what order based on context and history.

PR6 additions:
- Three-tier explanation mode (FULL / SHORT / COMPACT)
- Verdict-streak suppression (3+ identical verdicts → action-only)
- Workflow-sensitive hint gating (record=minimal, phase2=compact)
- Expanded escalation mappings (Q010, Q003)
"""

from __future__ import annotations

from enum import Enum

from .types import ActionId, AgentContext, SuggestedAction, UserStage
from .message_spec import RuleSpec, get_rule_spec


# =============================================================================
# EXPLANATION MODE (PR6)
# =============================================================================


class ExplanationMode(str, Enum):
    """Three-tier explanation verbosity.

    FULL: What happened + why it matters + common causes (FTUE / first exposure).
    SHORT: One-sentence explanation + immediate fix (seen before, low repetition).
    COMPACT: No explanation — "Same issue recurring, focus on fix" (heavy repetition).
    """

    FULL = "full"
    SHORT = "short"
    COMPACT = "compact"


def choose_explanation_mode(
    rule_id: str,
    context: AgentContext,
) -> ExplanationMode:
    """Determine explanation verbosity for a rule based on context.

    Rules (PR6):
    - First time (not in first_time_seen_rules AND session count ≤1) → FULL
    - Consecutive hits ≥3 OR session count ≥2 → COMPACT
    - Otherwise → SHORT
    """
    is_first_time = rule_id in context.first_time_seen_rules
    session_count = context.rule_counts_session.get(rule_id, 0)
    streak = context.consecutive_rule_hits.get(rule_id, 0)

    if is_first_time and session_count <= 1:
        return ExplanationMode.FULL
    if streak >= 3 or session_count >= 2:
        return ExplanationMode.COMPACT
    return ExplanationMode.SHORT


def should_suppress_for_verdict_streak(context: AgentContext) -> bool:
    """True if 3+ identical verdicts in a row — suppress explanations entirely."""
    return context.consecutive_same_verdict >= 3


def should_show_learning_hint_standalone(
    context: AgentContext,
    rule_ids: list[str],
) -> bool:
    """Learning hints shown only on genuine first exposure.

    All must be true:
    - user_stage in {FIRST_RUN, NOVICE}
    - at least one rule is first-time
    - no rule fatiguing in-session (count ≤1)
    - workflow is 'measure' (record=minimal, phase2=experienced)
    """
    if context.user_stage not in (UserStage.FIRST_RUN, UserStage.NOVICE):
        return False
    if context.workflow != "measure":
        return False
    if not rule_ids:
        return False
    any_new = any(rid in context.first_time_seen_rules for rid in rule_ids)
    if not any_new:
        return False
    any_fatiguing = any(
        context.rule_counts_session.get(rid, 0) >= 2 for rid in rule_ids
    )
    return not any_fatiguing


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
        actions.append(
            SuggestedAction(ActionId.ADVANCE, "Next point", "Proceed in workflow")
        )
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
            actions.append(
                SuggestedAction(ActionId.ABORT, "Abort", "Stop and troubleshoot")
            )
        actions.append(
            SuggestedAction(
                ActionId.OVERRIDE,
                "Override (requires reason)",
                "Log exception explicitly",
                requires_input=True,
            )
        )

    return actions


def _select_warn_actions(
    triggered_rules: list[str],
    context: AgentContext,
) -> list[SuggestedAction]:
    """Select actions for WARN verdict based on user stage."""
    actions: list[SuggestedAction] = []

    # Novice/first_run: recommend retry first
    if context.user_stage in (UserStage.FIRST_RUN, UserStage.NOVICE):
        actions.append(
            SuggestedAction(ActionId.RETRY, "Retry", "Try for cleaner capture")
        )
        actions.append(
            SuggestedAction(
                ActionId.ACCEPT, "Accept with warning", "Proceed with warning noted"
            )
        )
    else:
        # Regular/expert: accept is primary
        actions.append(
            SuggestedAction(ActionId.ACCEPT, "Accept", "Proceed with warning noted")
        )
        actions.append(
            SuggestedAction(ActionId.RETRY, "Retry", "Try for cleaner capture")
        )

    return actions


def _escalate_actions(spec: RuleSpec, consecutive_hits: int) -> list[SuggestedAction]:
    """Escalate actions for repeated rule triggers."""
    escalated: list[SuggestedAction] = []

    # Map rule IDs to escalated actions (expanded in PR6)
    escalation_map: dict[str, SuggestedAction] = {
        "Q001": SuggestedAction(
            ActionId.ADJUST_GAIN_DOWN,
            "Lower gain (repeated clipping)",
            "Clipping persists—reduce input gain",
        ),
        "Q002": SuggestedAction(
            ActionId.RUN_SETUP,
            "Run setup wizard (repeated silence)",
            "Likely wrong device—reconfigure",
        ),
        "Q003": SuggestedAction(
            ActionId.CHECK_ENVIRONMENT,
            "Retap with firmer coupling; confirm mic placement",
            f"No peaks {consecutive_hits}× in a row—coupling or environment issue",
        ),
        "Q011": SuggestedAction(
            ActionId.ADJUST_GAIN_DOWN,
            "Lower gain (repeated near-clipping)",
            f"Near-clipping {consecutive_hits}× in a row",
        ),
        "Q010": SuggestedAction(
            ActionId.ADJUST_GAIN_UP,
            "Move mic closer and increase gain",
            f"Quiet signal {consecutive_hits}× in a row—need stronger input",
        ),
        "Q004": SuggestedAction(
            ActionId.CHECK_ENVIRONMENT,
            "Check environment (repeated low confidence)",
            "Noise or coupling issue",
        ),
    }

    escalated_action = escalation_map.get(spec.rule_id)
    if escalated_action:
        escalated.append(escalated_action)

    # Always include retry as fallback
    escalated.append(
        SuggestedAction(ActionId.RETRY, "Retry", "Attempt again after adjustment")
    )

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
    """Build a single rule's detail line for display.

    Uses three-tier explanation mode (PR6):
    - FULL: explanation + why + fix
    - SHORT: explanation + fix (no why)
    - COMPACT: "Same issue recurring" + fix only

    If verdict streak ≥3, returns action-only regardless.
    """
    severity_tag = "[ERROR]" if spec.severity == "HARD" else "[WARN]"

    # Verdict streak override: suppress explanations entirely
    if should_suppress_for_verdict_streak(context):
        consecutive = context.consecutive_rule_hits.get(spec.rule_id, 0)
        fix = spec.fallback_fix if consecutive >= 2 else spec.first_fix
        return f"{severity_tag} {spec.rule_id}: {fix}"

    mode = choose_explanation_mode(spec.rule_id, context)

    if mode == ExplanationMode.COMPACT:
        # No explanation paragraph — focus on fix
        consecutive = context.consecutive_rule_hits.get(spec.rule_id, 0)
        fix = spec.fallback_fix if consecutive >= 2 else spec.first_fix
        return f"{severity_tag} {spec.rule_id}: Same issue — {fix}"

    parts = [f"{severity_tag} {spec.rule_id}: {spec.operator_explanation}"]

    if mode == ExplanationMode.FULL and include_why:
        parts.append(f"  → {spec.why_it_matters}")

    if include_fix:
        consecutive = context.consecutive_rule_hits.get(spec.rule_id, 0)
        if consecutive >= 2:
            parts.append(f"  Fix: {spec.fallback_fix}")
        else:
            parts.append(f"  Fix: {spec.first_fix}")

    return "\n".join(parts)
