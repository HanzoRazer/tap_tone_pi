"""Tests for PR #20 Seg 2: ViewAdapter wired into OperatorLoop.

Validates:
  - OperatorLoop accepts view_adapter and spine_mode kwargs
  - M2 + adapter dispatches commands through the adapter
  - M2 without adapter falls back to M1
  - M0 mode writes shadow records with mode="M0"
  - commands_count in shadow record reflects dispatched count
  - Invalid spine_mode defaults to M1
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch, MagicMock

import pytest

from tap_tone_pi.agentic.spine.view_adapter import NullViewAdapter
from tap_tone_pi.workflow.operator_loop import OperatorLoop
from tap_tone_pi.agentic.spine.shadow_record import load_latest_shadow_record


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------

def _write_events_with_overload(session_dir: Path) -> None:
    """Write events that trigger OVERLOAD moment (3+ undos in 60s)."""
    events = []
    for i in range(4):
        events.append({
            "event_type": "user_action",
            "occurred_at": f"2026-02-09T10:00:0{i}Z",
            "source": {"component": "gui"},
            "payload": {"action": "undo"},
        })
    (session_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events),
        encoding="utf-8",
    )


def _write_events_with_finding(session_dir: Path) -> None:
    """Write events that trigger FINDING moment."""
    events = [
        {
            "event_type": "attention_requested",
            "occurred_at": "2026-02-09T10:00:00Z",
            "source": {"component": "wolf_detector"},
            "payload": {"directive_id": "d1"},
        },
    ]
    (session_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events),
        encoding="utf-8",
    )


# ------------------------------------------------------------------
# 1. Constructor accepts new kwargs
# ------------------------------------------------------------------

def test_operator_loop_accepts_view_adapter(tmp_path: Path) -> None:
    """OperatorLoop constructor accepts view_adapter kwarg."""
    adapter = NullViewAdapter()
    loop = OperatorLoop(
        session_dir=tmp_path,
        view_adapter=adapter,
        spine_mode="M2",
    )
    assert loop._view_adapter is adapter
    assert loop._spine_mode == "M2"


def test_operator_loop_defaults_to_m1(tmp_path: Path) -> None:
    """Without explicit spine_mode, defaults to M1."""
    loop = OperatorLoop(session_dir=tmp_path)
    assert loop._spine_mode == "M1"
    assert loop._view_adapter is None


def test_m2_without_adapter_falls_back_to_m1(tmp_path: Path) -> None:
    """M2 without a view_adapter silently falls back to M1."""
    loop = OperatorLoop(
        session_dir=tmp_path,
        spine_mode="M2",
        view_adapter=None,
    )
    assert loop._spine_mode == "M1"


def test_invalid_spine_mode_defaults_to_m1(tmp_path: Path) -> None:
    """Invalid mode string defaults to M1."""
    loop = OperatorLoop(
        session_dir=tmp_path,
        spine_mode="M99",
    )
    assert loop._spine_mode == "M1"


# ------------------------------------------------------------------
# 2. Shadow hook uses spine_mode
# ------------------------------------------------------------------

def test_shadow_record_reflects_spine_mode_m0(tmp_path: Path) -> None:
    """Shadow record mode field reflects spine_mode M0."""
    adapter = NullViewAdapter()
    loop = OperatorLoop(
        session_dir=tmp_path,
        spine_mode="M0",
        view_adapter=adapter,
    )
    # Write events so _run_shadow_hook_inner has something to process
    _write_events_with_finding(tmp_path)

    # Create a mock attempt
    attempt = MagicMock()
    attempt.attempt_id = "test_001"
    attempt.point_id = "P1"

    loop._run_shadow_hook(attempt)

    rec = load_latest_shadow_record(tmp_path)
    assert rec is not None
    assert rec["mode"] == "M0"


def test_shadow_record_reflects_spine_mode_m1(tmp_path: Path) -> None:
    """Shadow record mode field reflects spine_mode M1 (default)."""
    loop = OperatorLoop(session_dir=tmp_path)
    _write_events_with_finding(tmp_path)

    attempt = MagicMock()
    attempt.attempt_id = "test_002"
    attempt.point_id = "P2"

    loop._run_shadow_hook(attempt)

    rec = load_latest_shadow_record(tmp_path)
    assert rec is not None
    assert rec["mode"] == "M1"


# ------------------------------------------------------------------
# 3. M2 + OVERLOAD dispatches reset_view via adapter
# ------------------------------------------------------------------

def test_m2_overload_dispatches_reset_view(tmp_path: Path) -> None:
    """M2 with OVERLOAD moment dispatches reset_view through adapter."""
    adapter = NullViewAdapter()
    loop = OperatorLoop(
        session_dir=tmp_path,
        spine_mode="M2",
        view_adapter=adapter,
    )
    _write_events_with_overload(tmp_path)

    attempt = MagicMock()
    attempt.attempt_id = "test_003"
    attempt.point_id = "P3"

    loop._run_shadow_hook(attempt)

    # Check adapter received reset_view
    reset_cmds = [c for c in adapter.commands if c["name"] == "reset_view"]
    assert len(reset_cmds) >= 1, (
        f"Expected reset_view in adapter commands: {adapter.commands}"
    )

    # Shadow record should show commands_count > 0
    rec = load_latest_shadow_record(tmp_path)
    assert rec is not None
    assert rec["commands"]["count"] >= 1
    assert rec["mode"] == "M2"


# ------------------------------------------------------------------
# 4. M1 mode does not dispatch commands even with OVERLOAD
# ------------------------------------------------------------------

def test_m1_overload_does_not_dispatch(tmp_path: Path) -> None:
    """M1 mode should not dispatch view commands even for OVERLOAD."""
    adapter = NullViewAdapter()
    loop = OperatorLoop(
        session_dir=tmp_path,
        spine_mode="M1",
        view_adapter=adapter,
    )
    _write_events_with_overload(tmp_path)

    attempt = MagicMock()
    attempt.attempt_id = "test_004"
    attempt.point_id = "P4"

    loop._run_shadow_hook(attempt)

    # M1 produces no issue_commands so adapter should be empty
    assert adapter.commands == []


# ------------------------------------------------------------------
# 5. No events = NONE moment, no commands
# ------------------------------------------------------------------

def test_no_events_no_commands(tmp_path: Path) -> None:
    """No events → NONE moment, zero commands, no adapter interaction."""
    adapter = NullViewAdapter()
    loop = OperatorLoop(
        session_dir=tmp_path,
        spine_mode="M2",
        view_adapter=adapter,
    )
    # No events.jsonl written

    attempt = MagicMock()
    attempt.attempt_id = "test_005"
    attempt.point_id = "P5"

    loop._run_shadow_hook(attempt)

    assert adapter.commands == []
    rec = load_latest_shadow_record(tmp_path)
    assert rec is not None
    assert rec["commands"]["count"] == 0
