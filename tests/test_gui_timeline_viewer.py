"""Tests for PR #18: TimelineViewerDialog + load_timeline helper.

Tests the ``load_timeline`` loader and ``TimelineViewerDialog`` rendering
logic.  Because Tkinter is not available in CI headless environments,
all tests exercise the data-loading and formatting helpers directly
rather than instantiating Toplevel windows.

Measurement-boundary compliant: no quality or interpretation language.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from tap_tone_pi.gui.timeline_viewer import (
    TimelineViewerDialog,
    load_timeline,
    _fmt_bool,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_MINIMAL_TIMELINE: Dict[str, Any] = {
    "schema_id": "session_timeline_v1",
    "schema_version": 2,
    "session_id": "test_session_001",
    "paths": {
        "events_jsonl": "events.jsonl",
        "shadow_latest": "spine_shadow_latest.json",
        "advisory_state": "meta/advisory_state.json",
    },
    "moment_latest": {
        "id": "TRUST_EROSION",
        "confidence": 0.8,
        "trigger_event_count": 5,
    },
    "directive_events": [
        {
            "timestamp": "2026-02-09T10:00:00Z",
            "event_type": "attention_requested",
            "directive_id": "d1",
            "component": "spine",
        },
        {
            "timestamp": "2026-02-09T10:01:00Z",
            "event_type": "attention_acknowledged",
            "directive_id": "d1",
            "component": "gui",
        },
    ],
    "counts": {
        "attention_requested": 1,
        "attention_acknowledged": 1,
        "attention_dismissed": 0,
    },
    "ui_state": {
        "responded": True,
        "trust_banner_dismissed": False,
        "show_directive_history": True,
    },
    "latest_policy_trace": None,
}


def _write_timeline(base: Path, data: Dict[str, Any] | None = None) -> Path:
    """Write a timeline JSON file at the canonical pack location."""
    d = data if data is not None else _MINIMAL_TIMELINE
    out = base / "meta" / "session_timeline_v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(d, indent=2), encoding="utf-8")
    return out


def _write_events_jsonl(session_dir: Path) -> None:
    """Write an events.jsonl file that export_session_timeline can read."""
    lines = [
        json.dumps({
            "event_type": "attention_requested",
            "occurred_at": "2026-02-09T10:00:00Z",
            "source": {"component": "wolf_detector"},
            "payload": {"directive_id": "d1"},
        }),
        json.dumps({
            "event_type": "attention_dismissed",
            "occurred_at": "2026-02-09T10:02:00Z",
            "source": {"component": "gui"},
            "payload": {"directive_id": "d1"},
        }),
    ]
    (session_dir / "events.jsonl").write_text(
        "\n".join(lines), encoding="utf-8",
    )


# ------------------------------------------------------------------
# 1. load_timeline — pre-exported pack
# ------------------------------------------------------------------

def test_load_timeline_from_pack(tmp_path: Path) -> None:
    """load_timeline reads a pre-exported session_timeline_v1.json."""
    _write_timeline(tmp_path)
    data = load_timeline(tmp_path, allow_export=False)
    assert data is not None
    assert data["schema_id"] == "session_timeline_v1"
    assert data["session_id"] == "test_session_001"


def test_load_timeline_returns_none_when_missing(tmp_path: Path) -> None:
    """load_timeline returns None when no file exists and export disabled."""
    data = load_timeline(tmp_path, allow_export=False)
    assert data is None


# ------------------------------------------------------------------
# 2. load_timeline — live session (on-the-fly export)
# ------------------------------------------------------------------

def test_load_timeline_exports_on_the_fly(tmp_path: Path) -> None:
    """load_timeline calls export_session_timeline when file is absent."""
    sess = tmp_path / "live_session"
    sess.mkdir()
    _write_events_jsonl(sess)

    data = load_timeline(sess, allow_export=True)
    assert data is not None
    assert data["schema_id"] == "session_timeline_v1"
    assert len(data["directive_events"]) == 2


# ------------------------------------------------------------------
# 3. Data rendering correctness (no Tk required)
# ------------------------------------------------------------------

def test_events_match_input(tmp_path: Path) -> None:
    """Loaded directive_events match what was written."""
    _write_timeline(tmp_path)
    data = load_timeline(tmp_path, allow_export=False)
    assert data is not None
    assert len(data["directive_events"]) == 2
    types = [e["event_type"] for e in data["directive_events"]]
    assert "attention_requested" in types
    assert "attention_acknowledged" in types


def test_counts_display(tmp_path: Path) -> None:
    """Counts section contains all three attention counters."""
    _write_timeline(tmp_path)
    data = load_timeline(tmp_path, allow_export=False)
    assert data is not None
    counts = data["counts"]
    assert "attention_requested" in counts
    assert "attention_acknowledged" in counts
    assert "attention_dismissed" in counts


def test_moment_latest_populated(tmp_path: Path) -> None:
    """moment_latest shows id, confidence, trigger_event_count."""
    _write_timeline(tmp_path)
    data = load_timeline(tmp_path, allow_export=False)
    assert data is not None
    moment = data["moment_latest"]
    assert moment["id"] == "TRUST_EROSION"
    assert moment["confidence"] == 0.8
    assert moment["trigger_event_count"] == 5


def test_moment_latest_null(tmp_path: Path) -> None:
    """When moment_latest is null, data loads cleanly."""
    payload = {**_MINIMAL_TIMELINE, "moment_latest": None}
    _write_timeline(tmp_path, payload)
    data = load_timeline(tmp_path, allow_export=False)
    assert data is not None
    assert data["moment_latest"] is None


def test_empty_directive_events(tmp_path: Path) -> None:
    """Empty directive_events list loads without error."""
    payload = {**_MINIMAL_TIMELINE, "directive_events": []}
    _write_timeline(tmp_path, payload)
    data = load_timeline(tmp_path, allow_export=False)
    assert data is not None
    assert data["directive_events"] == []


def test_ui_state_booleans(tmp_path: Path) -> None:
    """UI state boolean flags are preserved as True/False."""
    _write_timeline(tmp_path)
    data = load_timeline(tmp_path, allow_export=False)
    assert data is not None
    ui = data["ui_state"]
    assert ui["responded"] is True
    assert ui["trust_banner_dismissed"] is False
    assert ui["show_directive_history"] is True


# ------------------------------------------------------------------
# 4. _fmt_bool helper
# ------------------------------------------------------------------

def test_fmt_bool_true():
    assert _fmt_bool(True) == "✓"


def test_fmt_bool_false():
    assert _fmt_bool(False) == "✗"


def test_fmt_bool_none():
    assert _fmt_bool(None) == "—"


def test_fmt_bool_string():
    assert _fmt_bool("yes") == "yes"


# ------------------------------------------------------------------
# 5. No quality / interpretation language
# ------------------------------------------------------------------

# Forbidden words from EVIDENCE_PACK_CONTRACT_v1 and MEASUREMENT_BOUNDARY
_FORBIDDEN = {
    "good", "bad", "optimal", "problem", "worst", "dominant",
    "strongest", "fix", "thin", "stiffen", "remove", "wolf tone",
    "dead spot", "recommendation", "should",
}


def test_no_quality_language_in_timeline_data(tmp_path: Path) -> None:
    """Timeline payload must contain no interpretation or quality words."""
    _write_timeline(tmp_path)
    data = load_timeline(tmp_path, allow_export=False)
    assert data is not None
    serialised = json.dumps(data).lower()
    for word in _FORBIDDEN:
        assert word not in serialised, f"Forbidden word '{word}' found in timeline"


# ------------------------------------------------------------------
# 6. Corrupt / invalid file handling
# ------------------------------------------------------------------

def test_corrupt_json_returns_none(tmp_path: Path) -> None:
    """Corrupt JSON file → load_timeline returns None, no crash."""
    out = tmp_path / "meta" / "session_timeline_v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("{{{bad json", encoding="utf-8")
    data = load_timeline(tmp_path, allow_export=False)
    assert data is None


def test_non_dict_json_returns_none(tmp_path: Path) -> None:
    """A JSON array instead of object → load_timeline returns None."""
    out = tmp_path / "meta" / "session_timeline_v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("[1, 2, 3]", encoding="utf-8")
    data = load_timeline(tmp_path, allow_export=False)
    assert data is None
