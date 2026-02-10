"""Tests for PR #20 Seg 1: ViewAdapter protocol + NullViewAdapter + dispatch.

Validates:
  - ViewAdapter is a runtime-checkable Protocol
  - NullViewAdapter implements ViewAdapter and records commands
  - dispatch_commands dispatches all 4 command types
  - dispatch_commands is fail-closed (swallows errors)
  - dispatch_commands returns correct count
  - Policy M2 OVERLOAD issues reset_view command
  - Policy M2 FIRST_SIGNAL + FTUE issues hide_all_except + focus_trace
  - Policy M2 commands integrate with dispatch_commands
  - Spine __init__ exports ViewAdapter, NullViewAdapter, dispatch_commands
"""
from __future__ import annotations

from typing import Any, Dict, List

import pytest

from tap_tone_pi.agentic.spine.view_adapter import (
    ViewAdapter,
    NullViewAdapter,
    dispatch_commands,
)


# ------------------------------------------------------------------
# 1. Protocol conformance
# ------------------------------------------------------------------

def test_null_adapter_is_view_adapter() -> None:
    """NullViewAdapter satisfies the ViewAdapter protocol."""
    adapter = NullViewAdapter()
    assert isinstance(adapter, ViewAdapter)


def test_protocol_is_runtime_checkable() -> None:
    """ViewAdapter can be checked at runtime via isinstance."""

    class CustomAdapter:
        def focus_trace(self, trace_id: str) -> None: ...
        def hide_all_except(self, panel_id: str) -> None: ...
        def highlight_delta(self, from_state_id: str, to_state_id: str) -> None: ...
        def reset_view(self) -> None: ...

    adapter = CustomAdapter()
    assert isinstance(adapter, ViewAdapter)


def test_non_conformant_class_fails_protocol() -> None:
    """Class missing a method is not a ViewAdapter."""

    class Incomplete:
        def focus_trace(self, trace_id: str) -> None: ...
        # missing hide_all_except, highlight_delta, reset_view

    assert not isinstance(Incomplete(), ViewAdapter)


# ------------------------------------------------------------------
# 2. NullViewAdapter records commands
# ------------------------------------------------------------------

def test_null_adapter_focus_trace() -> None:
    adapter = NullViewAdapter()
    adapter.focus_trace("main")
    assert len(adapter.commands) == 1
    assert adapter.commands[0] == {
        "name": "focus_trace",
        "parameters": {"trace_id": "main"},
    }


def test_null_adapter_hide_all_except() -> None:
    adapter = NullViewAdapter()
    adapter.hide_all_except("spectrum")
    assert len(adapter.commands) == 1
    assert adapter.commands[0] == {
        "name": "hide_all_except",
        "parameters": {"panel_id": "spectrum"},
    }


def test_null_adapter_highlight_delta() -> None:
    adapter = NullViewAdapter()
    adapter.highlight_delta("state_a", "state_b")
    assert len(adapter.commands) == 1
    assert adapter.commands[0] == {
        "name": "highlight_delta",
        "parameters": {"from_state_id": "state_a", "to_state_id": "state_b"},
    }


def test_null_adapter_reset_view() -> None:
    adapter = NullViewAdapter()
    adapter.reset_view()
    assert len(adapter.commands) == 1
    assert adapter.commands[0] == {
        "name": "reset_view",
        "parameters": {},
    }


def test_null_adapter_multiple_commands() -> None:
    adapter = NullViewAdapter()
    adapter.hide_all_except("spectrum")
    adapter.focus_trace("main")
    adapter.reset_view()
    assert len(adapter.commands) == 3
    assert adapter.commands[0]["name"] == "hide_all_except"
    assert adapter.commands[1]["name"] == "focus_trace"
    assert adapter.commands[2]["name"] == "reset_view"


# ------------------------------------------------------------------
# 3. dispatch_commands
# ------------------------------------------------------------------

def test_dispatch_focus_trace() -> None:
    adapter = NullViewAdapter()
    count = dispatch_commands(adapter, [
        {"name": "focus_trace", "parameters": {"trace_id": "main"}},
    ])
    assert count == 1
    assert adapter.commands[0]["name"] == "focus_trace"


def test_dispatch_hide_all_except() -> None:
    adapter = NullViewAdapter()
    count = dispatch_commands(adapter, [
        {"name": "hide_all_except", "parameters": {"panel_id": "spectrum"}},
    ])
    assert count == 1
    assert adapter.commands[0]["name"] == "hide_all_except"


def test_dispatch_highlight_delta() -> None:
    adapter = NullViewAdapter()
    count = dispatch_commands(adapter, [
        {"name": "highlight_delta", "parameters": {"from_state_id": "a", "to_state_id": "b"}},
    ])
    assert count == 1
    assert adapter.commands[0]["name"] == "highlight_delta"


def test_dispatch_reset_view() -> None:
    adapter = NullViewAdapter()
    count = dispatch_commands(adapter, [
        {"name": "reset_view", "parameters": {}},
    ])
    assert count == 1
    assert adapter.commands[0]["name"] == "reset_view"


def test_dispatch_multiple_commands() -> None:
    adapter = NullViewAdapter()
    cmds = [
        {"name": "hide_all_except", "parameters": {"panel_id": "spectrum"}},
        {"name": "focus_trace", "parameters": {"trace_id": "main"}},
    ]
    count = dispatch_commands(adapter, cmds)
    assert count == 2
    assert len(adapter.commands) == 2


def test_dispatch_returns_zero_for_none_adapter() -> None:
    count = dispatch_commands(None, [
        {"name": "reset_view", "parameters": {}},
    ])
    assert count == 0


def test_dispatch_returns_zero_for_empty_commands() -> None:
    adapter = NullViewAdapter()
    count = dispatch_commands(adapter, [])
    assert count == 0
    assert adapter.commands == []


def test_dispatch_skips_unknown_commands() -> None:
    adapter = NullViewAdapter()
    count = dispatch_commands(adapter, [
        {"name": "unknown_command", "parameters": {}},
    ])
    assert count == 0
    assert adapter.commands == []


def test_dispatch_fail_closed_on_error() -> None:
    """Adapter that raises should not crash dispatch."""

    class BrokenAdapter:
        def focus_trace(self, trace_id: str) -> None:
            raise RuntimeError("broken")
        def hide_all_except(self, panel_id: str) -> None: ...
        def highlight_delta(self, from_state_id: str, to_state_id: str) -> None: ...
        def reset_view(self) -> None: ...

    adapter = BrokenAdapter()
    # Should not raise
    count = dispatch_commands(adapter, [
        {"name": "focus_trace", "parameters": {"trace_id": "main"}},
        {"name": "reset_view", "parameters": {}},
    ])
    # focus_trace failed, reset_view succeeded
    assert count == 1


def test_dispatch_missing_parameters_key() -> None:
    """Command dict without 'parameters' key uses empty dict."""
    adapter = NullViewAdapter()
    count = dispatch_commands(adapter, [
        {"name": "reset_view"},
    ])
    assert count == 1
    assert adapter.commands[0]["name"] == "reset_view"


# ------------------------------------------------------------------
# 4. Policy M2 OVERLOAD → reset_view
# ------------------------------------------------------------------

def test_policy_m2_overload_issues_reset_view() -> None:
    """M2 OVERLOAD with view access should issue reset_view."""
    from tap_tone_pi.agentic.spine.policy import decide

    out = decide(
        moment={"moment": "OVERLOAD"},
        uwsm={
            "dimensions": {
                "guidance_density": {"value": "medium", "confidence": 0.6},
                "initiative_tolerance": {"value": "shared_control", "confidence": 0.6},
                "cognitive_load_sensitivity": {"value": "medium", "confidence": 0.6},
            }
        },
        mode="M2",
        capability={"automation_limits": {"agent_can_adjust_view": True}},
    )
    cmds = out.get("issue_commands", [])
    assert any(c.get("name") == "reset_view" for c in cmds), (
        f"Expected reset_view in commands: {cmds}"
    )


def test_policy_m2_overload_no_commands_when_denied() -> None:
    """M2 OVERLOAD without view access falls back to M1 (no commands)."""
    from tap_tone_pi.agentic.spine.policy import decide

    out = decide(
        moment={"moment": "OVERLOAD"},
        uwsm={
            "dimensions": {
                "guidance_density": {"value": "medium", "confidence": 0.6},
                "initiative_tolerance": {"value": "shared_control", "confidence": 0.6},
                "cognitive_load_sensitivity": {"value": "medium", "confidence": 0.6},
            }
        },
        mode="M2",
        capability={"automation_limits": {"agent_can_adjust_view": False}},
    )
    assert out.get("issue_commands", []) == []
    assert out.get("diagnostic", {}).get("fallback_mode") == "M1"


# ------------------------------------------------------------------
# 5. Policy M2 FIRST_SIGNAL + dispatch integration
# ------------------------------------------------------------------

def test_policy_m2_first_signal_dispatches_via_adapter() -> None:
    """Commands from M2 FIRST_SIGNAL dispatch through NullViewAdapter."""
    from tap_tone_pi.agentic.spine.policy import decide

    out = decide(
        moment={"moment": "FIRST_SIGNAL"},
        uwsm={
            "dimensions": {
                "guidance_density": {"value": "medium", "confidence": 0.6},
                "initiative_tolerance": {"value": "shared_control", "confidence": 0.6},
                "cognitive_load_sensitivity": {"value": "medium", "confidence": 0.6},
            }
        },
        mode="M2",
        capability={"automation_limits": {"agent_can_adjust_view": True}},
        context={"first_time_user": True, "primary_panel": "spectrum", "primary_trace": "main"},
    )
    cmds = out.get("issue_commands", [])

    adapter = NullViewAdapter()
    count = dispatch_commands(adapter, cmds)
    assert count == 2
    assert adapter.commands[0]["name"] == "hide_all_except"
    assert adapter.commands[0]["parameters"]["panel_id"] == "spectrum"
    assert adapter.commands[1]["name"] == "focus_trace"
    assert adapter.commands[1]["parameters"]["trace_id"] == "main"


def test_policy_m2_overload_dispatches_via_adapter() -> None:
    """Commands from M2 OVERLOAD dispatch through NullViewAdapter."""
    from tap_tone_pi.agentic.spine.policy import decide

    out = decide(
        moment={"moment": "OVERLOAD"},
        uwsm={
            "dimensions": {
                "guidance_density": {"value": "medium", "confidence": 0.6},
                "initiative_tolerance": {"value": "shared_control", "confidence": 0.6},
                "cognitive_load_sensitivity": {"value": "medium", "confidence": 0.6},
            }
        },
        mode="M2",
        capability={"automation_limits": {"agent_can_adjust_view": True}},
    )
    cmds = out.get("issue_commands", [])

    adapter = NullViewAdapter()
    count = dispatch_commands(adapter, cmds)
    assert count == 1
    assert adapter.commands[0]["name"] == "reset_view"


# ------------------------------------------------------------------
# 6. Spine __init__ exports
# ------------------------------------------------------------------

def test_spine_exports_view_adapter() -> None:
    """ViewAdapter, NullViewAdapter, dispatch_commands are importable from spine."""
    from tap_tone_pi.agentic.spine import (
        ViewAdapter as VA,
        NullViewAdapter as NVA,
        dispatch_commands as dc,
    )
    assert VA is ViewAdapter
    assert NVA is NullViewAdapter
    assert dc is dispatch_commands
