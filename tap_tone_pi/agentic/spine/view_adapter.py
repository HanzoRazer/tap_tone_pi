"""View Adapter Protocol — M2 Actuation Interface.

Defines the ``ViewAdapter`` protocol that any visual surface must
implement to accept M2 analyzer attention commands from the spine.

Available commands (per AGENT_DECISION_POLICY_V1.md §1.4):
  - ``focus_trace(trace_id)``
  - ``hide_all_except(panel_id)``
  - ``highlight_delta(from_state_id, to_state_id)``
  - ``reset_view()``

Implementations:
  - ``NullViewAdapter`` — no-op (used in M0/M1 and testing)
  - Future: Tkinter adapter, web adapter, etc.

Safety rules (Appendix F of the spec):
  - Never emit more than one critical directive at once
  - Never override explicit user dismissal
  - Never escalate urgency without new evidence
  - Never act without capability confirmation
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class ViewAdapter(Protocol):
    """Protocol for M2 analyzer attention command dispatch.

    Any visual surface (GUI, web viewer, etc.) that wants to accept
    M2 actuation commands must implement this protocol.

    All methods MUST be fail-closed: swallow exceptions internally,
    never raise into the spine pipeline.
    """

    def focus_trace(self, trace_id: str) -> None:
        """Highlight a single trace in the active panel."""
        ...

    def hide_all_except(self, panel_id: str) -> None:
        """Hide all panels except the named one."""
        ...

    def highlight_delta(
        self, from_state_id: str, to_state_id: str,
    ) -> None:
        """Show visual diff between two analysis states."""
        ...

    def reset_view(self) -> None:
        """Reset the analyzer view to defaults."""
        ...


class NullViewAdapter:
    """No-op view adapter for M0/M1 and testing.

    Records dispatched commands for assertion in tests but performs
    no actual view mutations.
    """

    def __init__(self) -> None:
        self.commands: List[Dict[str, Any]] = []

    def focus_trace(self, trace_id: str) -> None:
        self.commands.append({"name": "focus_trace", "parameters": {"trace_id": trace_id}})

    def hide_all_except(self, panel_id: str) -> None:
        self.commands.append({"name": "hide_all_except", "parameters": {"panel_id": panel_id}})

    def highlight_delta(
        self, from_state_id: str, to_state_id: str,
    ) -> None:
        self.commands.append({
            "name": "highlight_delta",
            "parameters": {"from_state_id": from_state_id, "to_state_id": to_state_id},
        })

    def reset_view(self) -> None:
        self.commands.append({"name": "reset_view", "parameters": {}})


def dispatch_commands(
    adapter: Optional[ViewAdapter],
    commands: List[Dict[str, Any]],
) -> int:
    """Dispatch a list of command dicts through a ViewAdapter.

    Each command dict is expected to have:
      - ``name``: one of ``focus_trace``, ``hide_all_except``,
        ``highlight_delta``, ``reset_view``
      - ``parameters``: dict of kwargs for the method

    Returns the number of commands successfully dispatched.
    Fail-closed: individual command errors are swallowed.
    """
    if adapter is None or not commands:
        return 0

    dispatched = 0
    for cmd in commands:
        name = cmd.get("name", "")
        params = cmd.get("parameters", {})
        try:
            if name == "focus_trace":
                adapter.focus_trace(params.get("trace_id", ""))
            elif name == "hide_all_except":
                adapter.hide_all_except(params.get("panel_id", ""))
            elif name == "highlight_delta":
                adapter.highlight_delta(
                    params.get("from_state_id", ""),
                    params.get("to_state_id", ""),
                )
            elif name == "reset_view":
                adapter.reset_view()
            else:
                continue  # unknown command — skip silently
            dispatched += 1
        except Exception:
            pass  # fail-closed

    return dispatched


__all__ = [
    "ViewAdapter",
    "NullViewAdapter",
    "dispatch_commands",
]
