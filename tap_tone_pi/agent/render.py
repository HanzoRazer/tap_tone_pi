"""Render — CLI and GUI formatting for agent messages.

The agent produces structured AgentMessage; this module formats for output.
Supports both standalone (types.py) and integrated (messages.py) AgentMessage.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Union

# Import standalone types for type hints
from .types import AgentMessage as StandaloneAgentMessage


def _get_severity(msg: Any) -> str:
    """Extract severity from AgentMessage (works with both standalone and integrated)."""
    # Standalone version has .severity property
    if hasattr(msg, 'severity'):
        return msg.severity
    # Integrated version stores in telemetry_tags
    if hasattr(msg, 'get_tag'):
        verdict = msg.get_tag("verdict")
        if verdict == "fail":
            return "error"
        elif verdict == "warn":
            return "warn"
        return "info"
    # Fallback: check telemetry_tags dict
    if hasattr(msg, 'telemetry_tags'):
        tags = msg.telemetry_tags
        if isinstance(tags, dict):
            verdict = tags.get("verdict", "pass")
        else:
            # Tuple of tuples
            verdict = "pass"
            for k, v in tags:
                if k == "verdict":
                    verdict = v
                    break
        if verdict == "fail":
            return "error"
        elif verdict == "warn":
            return "warn"
        return "info"
    return "info"


def _get_action_id(action: Any) -> str:
    """Extract action_id string from action (works with enum or string)."""
    if hasattr(action.action_id, 'value'):
        return action.action_id.value
    return str(action.action_id)


# =============================================================================
# CLI RENDERING
# =============================================================================

def render_cli(msg: AgentMessage, color: bool = True) -> str:
    """Render AgentMessage for CLI output.
    
    Args:
        msg: The agent message to render
        color: Whether to include ANSI color codes
    
    Returns:
        Formatted string for terminal display
    """
    lines: list[str] = []
    severity = _get_severity(msg)
    
    # Title with severity coloring
    title_line = msg.title
    if color:
        title_line = _colorize(msg.title, severity)
    lines.append(title_line)
    lines.append("=" * len(msg.title))
    
    # Summary
    lines.append("")
    lines.append(msg.summary)
    
    # Details (rule explanations)
    if msg.details:
        lines.append("")
        lines.append("Details:")
        for detail in msg.details:
            for line in detail.split("\n"):
                lines.append(f"  {line}")
    
    # Suggested actions
    if msg.suggested_actions:
        lines.append("")
        lines.append("Recommended actions:")
        for i, action in enumerate(msg.suggested_actions, 1):
            suffix = " *" if action.requires_input else ""
            lines.append(f"  {i}. {action.label}{suffix}")
            lines.append(f"     ({action.rationale})")
    
    # Learning hint (FTUE)
    if msg.learning_hint:
        lines.append("")
        hint = msg.learning_hint
        if color:
            hint = f"\033[36m{hint}\033[0m"  # Cyan
        lines.append(hint)
    
    return "\n".join(lines)


def _colorize(text: str, severity: str) -> str:
    """Apply ANSI color based on severity."""
    colors = {
        "error": "\033[31m",   # Red
        "warn": "\033[33m",    # Yellow
        "info": "\033[32m",    # Green
    }
    reset = "\033[0m"
    color = colors.get(severity, "")
    return f"{color}{text}{reset}"


# =============================================================================
# GUI RENDERING
# =============================================================================

def render_gui(msg: AgentMessage) -> dict:
    """Render AgentMessage for GUI consumption.
    
    Returns a dict suitable for GUI binding:
    - title_text: str
    - title_style: str (css class or style name)
    - summary_text: str
    - details_html: str (formatted for rich text display)
    - action_buttons: list of dicts with id, label, enabled, requires_input
    - hint_text: str | None
    """
    severity = _get_severity(msg)
    style_map = {
        "error": "error",
        "warn": "warning", 
        "info": "success",
    }
    
    # Build details as HTML-like formatted text
    details_parts = []
    for detail in msg.details:
        # Convert to mild HTML formatting
        formatted = detail.replace("\n", "<br>")
        formatted = formatted.replace("[ERROR]", "<b style='color:red'>[ERROR]</b>")
        formatted = formatted.replace("[WARN]", "<b style='color:orange'>[WARN]</b>")
        details_parts.append(f"<p>{formatted}</p>")
    
    return {
        "title_text": msg.title,
        "title_style": style_map.get(severity, "info"),
        "summary_text": msg.summary,
        "details_html": "".join(details_parts),
        "action_buttons": [
            {
                "id": _get_action_id(action),
                "label": action.label,
                "rationale": action.rationale,
                "enabled": True,
                "requires_input": action.requires_input,
            }
            for action in msg.suggested_actions
        ],
        "hint_text": msg.learning_hint,
    }


# =============================================================================
# COMPACT RENDERING (for logs/JSON)
# =============================================================================

def render_compact(msg: AgentMessage) -> str:
    """Render a one-line summary for logging."""
    severity = _get_severity(msg)
    action_ids = [_get_action_id(a) for a in msg.suggested_actions]
    # Handle both dict and tuple telemetry_tags
    if isinstance(msg.telemetry_tags, dict):
        rule_ids = msg.telemetry_tags.get("rule_ids", [])
    else:
        # Tuple of (key, value) pairs
        rule_ids = []
        for k, v in msg.telemetry_tags:
            if k == "rule_ids":
                rule_ids = list(v) if not isinstance(v, list) else v
                break
    return f"{severity.upper()}: {msg.title} | rules={rule_ids} | actions={action_ids}"


# =============================================================================
# SHADOW DIRECTIVE RENDERING (PR #3 — CLI co-render)
# =============================================================================

def _directive_severity(action: str | None) -> str:
    """Map advisory action to severity for ``_colorize``."""
    if action in ("ABORT", "INTERVENE"):
        return "error"
    if action in ("REVIEW", "COMPARE", "DECIDE", "CONFIRM"):
        return "warn"
    return "info"


def _render_shadow_error_path(
    error: Dict[str, Any],
    lines: list[str],
    verbose: bool,
    color: bool,
) -> str:
    """Render error path for shadow record. Returns formatted string."""
    err_type = error.get("type", "Error")
    err_msg = error.get("message", "")
    note = f"Note: {err_type}: {err_msg}".strip()
    if color:
        note = _colorize(note, "warn")
    lines.append("")
    lines.append(note)
    if verbose:
        stage = error.get("stage")
        if stage:
            lines.append("")
            lines.append("Details:")
            lines.append(f"  Stage: {stage}")
    return "\n".join(lines)


def _extract_advisory_fields(advisory: Any, moment: Dict[str, Any]) -> tuple:
    """Extract advisory fields with fallbacks.

    Returns (action, summary, focus, confidence, moment_id, moment_conf, trigger_count).
    """
    action = advisory.get("action") if isinstance(advisory, dict) else None
    summary = advisory.get("summary") if isinstance(advisory, dict) else None
    focus = advisory.get("focus") if isinstance(advisory, dict) else None
    adv_conf = advisory.get("confidence") if isinstance(advisory, dict) else None

    moment_id = moment.get("id")
    moment_conf = moment.get("confidence")
    trigger_count = moment.get("trigger_event_count")

    return action, summary, focus, adv_conf, moment_id, moment_conf, trigger_count


def _build_shadow_details(
    action: Optional[str],
    focus: Optional[Dict[str, Any]],
    confidence: Optional[float],
    verbose: bool,
    moment_id: Optional[str],
    trigger_count: Optional[int],
    commands: Dict[str, Any],
    rec: Dict[str, Any],
) -> list[str]:
    """Build details lines for shadow record."""
    detail_lines: list[str] = []

    if isinstance(action, str) and action:
        detail_lines.append(f"  Action: {action}")

    if isinstance(focus, dict):
        target_type = focus.get("target_type")
        target_id = focus.get("target_id")
        if target_type and target_id:
            detail_lines.append(f"  Focus: {target_type}:{target_id}")

    if isinstance(confidence, (int, float)):
        try:
            detail_lines.append(f"  Confidence: {float(confidence):.2f}")
        except (ValueError, TypeError):
            pass

    if verbose:
        _add_verbose_details(detail_lines, moment_id, trigger_count, commands, rec)

    return detail_lines


def _add_verbose_details(
    detail_lines: list[str],
    moment_id: Optional[str],
    trigger_count: Optional[int],
    commands: Dict[str, Any],
    rec: Dict[str, Any],
) -> None:
    """Add verbose-mode details to detail_lines (mutates in place)."""
    if isinstance(moment_id, str) and moment_id:
        detail_lines.append(f"  Moment: {moment_id}")
    if isinstance(trigger_count, int):
        detail_lines.append(f"  Triggers: {trigger_count}")
    cmd_count = commands.get("count")
    if isinstance(cmd_count, int):
        detail_lines.append(f"  Commands: {cmd_count}")
    sess = rec.get("session_id")
    run = rec.get("run_id")
    ts = rec.get("timestamp")
    if isinstance(sess, str) and sess:
        detail_lines.append(f"  Session: {sess}")
    if isinstance(run, str) and run:
        detail_lines.append(f"  Run: {run}")
    if isinstance(ts, str) and ts:
        detail_lines.append(f"  Time: {ts}")


def render_cli_shadow_record(
    rec: Dict[str, Any],
    *,
    color: bool = True,
    verbose: bool = False,
) -> Optional[str]:
    """Render a Spine Shadow Directive Record (v1) for CLI output.

    Follows the same title + ``=`` underline + Details convention as
    ``render_cli`` so the two blocks look consistent when co-rendered.

    Args:
        rec: Shadow record dict (as returned by ``load_latest_shadow_record``).
        color: Enable ANSI formatting (CLI-only).
        verbose: Print safe debug fields (trigger counts, IDs).

    Returns:
        Formatted string, or ``None`` if the record is not renderable.
    """
    if not isinstance(rec, dict):
        return None

    mode = rec.get("mode")
    moment = rec.get("moment", {}) or {}
    advisory = rec.get("advisory")
    error = rec.get("error")
    commands = rec.get("commands", {}) or {}

    # Nothing to render
    if advisory is None and moment.get("id") in (None, "NONE"):
        return None

    # ---- title + underline (matches render_cli) ----
    header_mode = mode if isinstance(mode, str) else "M0"
    title_text = f"Advisory directive ({header_mode})"
    severity = _directive_severity(
        advisory.get("action") if isinstance(advisory, dict) else None,
    )
    title_line = _colorize(title_text, severity) if color else title_text
    lines: list[str] = [title_line, "=" * len(title_text)]

    # ---- error path ----
    if error:
        return _render_shadow_error_path(error, lines, verbose, color)

    # ---- extract advisory fields ----
    action, summary, focus, adv_conf, moment_id, moment_conf, trigger_count = \
        _extract_advisory_fields(advisory, moment)

    # ---- summary ----
    if not summary:
        summary = moment_id
    if isinstance(summary, str) and summary:
        lines.append("")
        lines.append(summary)

    # ---- details section ----
    confidence = adv_conf if isinstance(adv_conf, (int, float)) else moment_conf
    detail_lines = _build_shadow_details(
        action, focus, confidence, verbose,
        moment_id, trigger_count, commands, rec,
    )

    if detail_lines:
        lines.append("")
        lines.append("Details:")
        lines.extend(detail_lines)

    return "\n".join(lines)
