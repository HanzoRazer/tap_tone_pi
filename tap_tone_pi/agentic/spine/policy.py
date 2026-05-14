# app/agentic/spine/policy.py
"""
Decision Policy Engine — Reference Implementation

Applies decision policy based on detected moments, UWSM state, and operating mode.
This is a conservative implementation designed to:
1. Pass the test suite
2. Work correctly in shadow mode (M0)
3. Provide reasonable defaults for M1/M2

For full specification, see: docs/AGENT_DECISION_POLICY_V1.md
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Any, List, Optional

from tap_tone_pi.agentic.contracts.analyzer_attention import (
    AttentionAction,
    AttentionDirectiveV1,
    FocusTarget,
)


def _coerce_directive(obj: Any) -> Optional[AttentionDirectiveV1]:
    """
    PR #8 seam hardening: ensure policy always returns AttentionDirectiveV1
    (or None) even if some branch still constructs a plain dict.
    """
    if obj is None:
        return None
    if isinstance(obj, AttentionDirectiveV1):
        return obj
    if isinstance(obj, dict):
        # Best-effort coercion; fail-closed to None so policy never throws here.
        try:
            action_raw = obj.get("action") or "inspect"
            if isinstance(action_raw, AttentionAction):
                action_enum = action_raw
            else:
                action_enum = AttentionAction(str(action_raw).lower())
            focus = obj.get("focus")
            focus_obj = None
            if isinstance(focus, FocusTarget):
                focus_obj = focus
            elif isinstance(focus, dict):
                focus_obj = FocusTarget(
                    target_type=str(focus.get("target_type") or ""),
                    target_id=str(focus.get("target_id") or ""),
                    highlight_region=focus.get("highlight_region"),
                )
            if focus_obj is None:
                focus_obj = FocusTarget(target_type="session", target_id="current")
            return AttentionDirectiveV1(
                directive_id=str(
                    obj.get("directive_id") or f"policy_{uuid.uuid4().hex[:8]}"
                ),
                action=action_enum,
                summary=str(obj.get("summary") or ""),
                focus=focus_obj,
                detail=str(obj.get("detail") or ""),
            )
        except (ImportError, OSError, ValueError, KeyError, AttributeError):
            return None
    return None


def _dim(uwsm: dict, name: str, default_value: str = "medium") -> str:
    return (uwsm or {}).get("dimensions", {}).get(name, {}).get("value", default_value)


def _capability_allows_view_adjustment(capability: Any) -> bool:
    if capability is None:
        return False
    # Dict-style (used in tests and inline capabilities)
    if isinstance(capability, dict):
        return bool(
            capability.get("automation_limits", {}).get("agent_can_adjust_view", False)
        )
    # Dataclass-style (ToolCapabilityV1)
    limits = getattr(capability, "automation_limits", None)
    if limits is None:
        return False
    if isinstance(limits, dict):
        return bool(limits.get("agent_can_adjust_view", False))
    return bool(getattr(limits, "agent_can_adjust_view", False))


def _max_directives_for_load(load_value: str) -> int:
    # "very_high" sensitivity => max 1 directive (per spec)
    return 1 if load_value in ("high", "very_high") else 2


def decide(
    *,
    moment: dict,
    uwsm: dict,
    mode: str,
    capability: dict,
    context: Optional[dict] = None,
) -> dict:
    """
    Minimal reference policy engine.

    Returns dict with keys used by tests:
      - attention_action: str
      - emit_directive: bool
      - directive: dict (optional)
      - directives: list (optional)
      - issue_commands: list[dict]
      - diagnostic: dict

    This implementation is conservative and designed to pass bootstrap tests.
    """
    context = context or {}
    moment_name = (moment or {}).get("moment", "UNKNOWN")

    guidance = _dim(uwsm, "guidance_density", "medium")
    initiative = _dim(uwsm, "initiative_tolerance", "shared_control")
    load = _dim(uwsm, "cognitive_load_sensitivity", "medium")

    max_directives = _max_directives_for_load(load)

    # Default mapping (spec)
    mapping = {
        "FIRST_SIGNAL": "INSPECT",
        "HESITATION": "INSPECT",
        "OVERLOAD": "REVIEW",
        "DECISION_REQUIRED": "DECIDE",
        "FINDING": "REVIEW",
        "ERROR": "REVIEW",
        "CONFIDENCE_CLIMB": "INSPECT",
        "TRUST_EROSION": "REVIEW",
    }
    action = mapping.get(moment_name, "NONE")

    diagnostic: dict = {
        "rule_id": f"POLICY_{moment_name}_{action}_v1",
        "max_directives": max_directives,
    }

    # Initiative gate: user_led suppresses proactive suggestions
    soft_prompt = False
    if initiative == "user_led" and moment_name in (
        "HESITATION",
        "FINDING",
        "FIRST_SIGNAL",
    ):
        # Allow either no directive or a very soft INSPECT with a "Want a suggestion?" prompt.
        if moment_name == "HESITATION":
            action = "INSPECT"
            soft_prompt = True
            diagnostic["soft_prompt"] = True
        else:
            action = "NONE"
            diagnostic["suppressed_due_to_initiative"] = True

    # Mode behavior
    issue_commands: List[dict] = []

    if mode == "M0":
        # Shadow: never emit directive; instead produce diagnostic "would_have_emitted"
        would = _build_directive(action, guidance=guidance, soft_prompt=soft_prompt)
        diagnostic["would_have_emitted"] = would.to_dict()
        return {
            "attention_action": action,
            "emit_directive": False,
            "issue_commands": [],
            "diagnostic": diagnostic,
        }

    # In M1/M2: emit directive unless action == NONE
    emit_directive = action != "NONE"
    directive = (
        _build_directive(action, guidance=guidance, soft_prompt=soft_prompt)
        if emit_directive
        else None
    )
    directive = _coerce_directive(directive)

    # Guidance density gate: summary-only when very_low
    if guidance in ("very_low", "low") and directive is not None:
        # keep detail empty or very short (replace keeps frozen-dataclass compatibility)
        directive = replace(directive, detail="")

    # M2: analyzer attention commands if allowed + moment-specific rules
    if mode == "M2":
        if _capability_allows_view_adjustment(capability):
            # One-Trace onboarding for FIRST_SIGNAL + FTUE
            if moment_name == "FIRST_SIGNAL" and bool(
                context.get("first_time_user", False)
            ):
                primary_panel = context.get("primary_panel", "spectrum")
                primary_trace = context.get("primary_trace", "main")
                issue_commands = [
                    {
                        "name": "hide_all_except",
                        "parameters": {"panel_id": primary_panel},
                    },
                    {"name": "focus_trace", "parameters": {"trace_id": primary_trace}},
                ]
            # OVERLOAD recovery: reset view to defaults
            elif moment_name == "OVERLOAD":
                issue_commands = [
                    {"name": "reset_view", "parameters": {}},
                ]
        else:
            # Fallback to M1 behavior
            diagnostic["fallback_mode"] = "M1"
            issue_commands = []

    out = {
        "attention_action": action,
        "emit_directive": emit_directive,
        "directive": directive,
        "directives": [directive] if directive is not None else [],
        "issue_commands": issue_commands,
        "diagnostic": diagnostic,
    }
    return out


def _build_directive(
    action: str, *, guidance: str, soft_prompt: bool
) -> AttentionDirectiveV1:
    """
    Build an AttentionDirectiveV1 dataclass for the given action.
    """
    title = {
        "INSPECT": "Inspect this",
        "REVIEW": "Review this",
        "COMPARE": "Compare options",
        "DECIDE": "Make a choice",
        "CONFIRM": "Confirm",
        "INTERVENE": "Stop and check",
        "ABORT": "Abort",
        "NONE": "",
    }.get(action, "Next step")

    detail = ""
    if action == "INSPECT":
        detail = "Focus on one signal and make a small change."
    elif action == "REVIEW":
        detail = "Let's simplify and confirm what changed."
    elif action == "DECIDE":
        detail = "Choose one option to proceed."

    if soft_prompt:
        detail = "Want a suggestion for what to try next?"

    # Map uppercase action string to AttentionAction enum (lowercase values)
    action_enum = (
        AttentionAction(action.lower()) if action != "NONE" else AttentionAction.INSPECT
    )

    return AttentionDirectiveV1(
        directive_id=f"policy_{uuid.uuid4().hex[:8]}",
        action=action_enum,
        summary=title,
        focus=FocusTarget(target_type="session", target_id="current"),
        detail=detail,
    )
