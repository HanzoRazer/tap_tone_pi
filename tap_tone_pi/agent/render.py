"""Render — CLI and GUI formatting for agent messages.

The agent produces structured AgentMessage; this module formats for output.
"""
from __future__ import annotations

from .types import AgentMessage, UserStage


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
    
    # Title with severity coloring
    title_line = msg.title
    if color:
        title_line = _colorize(msg.title, msg.severity)
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
        "title_style": style_map.get(msg.severity, "info"),
        "summary_text": msg.summary,
        "details_html": "".join(details_parts),
        "action_buttons": [
            {
                "id": action.action_id.value,
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
    action_ids = [a.action_id.value for a in msg.suggested_actions]
    rule_ids = msg.telemetry_tags.get("rule_ids", [])
    return f"{msg.severity.upper()}: {msg.title} | rules={rule_ids} | actions={action_ids}"
