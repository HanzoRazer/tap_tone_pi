"""Tests for directive history JSONL loader (PR #14 Seg 1)."""

import json
from pathlib import Path

from tap_tone_pi.agentic.spine.directive_history import load_directive_events


def test_load_directive_events_filters_and_limits(tmp_path: Path):
    """Only directive events are returned; limit is respected; bad lines skipped."""
    sess = tmp_path / "sess"
    sess.mkdir()
    p = sess / "events.jsonl"

    lines = [
        {"event_type": "analysis_started", "timestamp": "t0"},
        {
            "event_type": "attention_requested",
            "timestamp": "t1",
            "payload": {"directive_id": "d1"},
            "source": {"component": "spine"},
        },
        "not json",
        {
            "event_type": "attention_acknowledged",
            "timestamp": "t2",
            "payload": {"directive_id": "d1"},
            "source": {"component": "cli"},
        },
        {
            "event_type": "attention_dismissed",
            "timestamp": "t3",
            "payload": {"directive_id": "d2"},
            "source": {"component": "gui"},
        },
    ]
    with open(p, "w", encoding="utf-8") as f:
        for obj in lines:
            if isinstance(obj, str):
                f.write(obj + "\n")
            else:
                f.write(json.dumps(obj) + "\n")

    rows = load_directive_events(sess, limit=2)
    # Should return the last 2 directive events in chronological order
    assert [r.timestamp for r in rows] == ["t2", "t3"]
    assert [r.event_type for r in rows] == [
        "attention_acknowledged",
        "attention_dismissed",
    ]
    assert rows[-1].directive_id == "d2"
    assert rows[-1].component == "gui"


def test_load_directive_events_returns_all_when_under_limit(tmp_path: Path):
    sess = tmp_path / "sess"
    sess.mkdir()
    p = sess / "events.jsonl"

    ev = {
        "event_type": "attention_requested",
        "timestamp": "t1",
        "payload": {"directive_id": "d1"},
        "source": {"component": "spine"},
    }
    p.write_text(json.dumps(ev) + "\n", encoding="utf-8")

    rows = load_directive_events(sess, limit=10)
    assert len(rows) == 1
    assert rows[0].event_type == "attention_requested"


def test_load_directive_events_missing_file(tmp_path: Path):
    """Missing events.jsonl → empty list, never raises."""
    assert load_directive_events(tmp_path / "nonexistent") == []


def test_load_directive_events_flat_component_fallback(tmp_path: Path):
    """Flat 'component' key (no 'source' dict) is accepted as fallback."""
    sess = tmp_path / "sess"
    sess.mkdir()
    p = sess / "events.jsonl"

    ev = {
        "event_type": "attention_acknowledged",
        "timestamp": "t1",
        "payload": {"directive_id": "d1"},
        "component": "legacy_cli",
    }
    p.write_text(json.dumps(ev) + "\n", encoding="utf-8")

    rows = load_directive_events(sess)
    assert len(rows) == 1
    assert rows[0].component == "legacy_cli"
