"""Tests for GUI directive outcome recording (ACK/DISMISS).

Validates:
- ACK writes attention_acknowledged event to events.jsonl
- DISMISS writes attention_dismissed event to events.jsonl
- Returns False gracefully when no shadow file exists
- Falls back to run_id when advisory has no directive_id
"""

from __future__ import annotations

import json
from pathlib import Path


from tap_tone_pi.gui.directive_outcomes import record_latest_directive_outcome


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_shadow_latest(
    session_dir: Path,
    *,
    directive_id: str | None = None,
    run_id: str = "run_001",
) -> None:
    """Write a minimal valid spine_shadow_latest.json."""
    advisory: dict | None = {
        "action": "REVIEW",
        "summary": "Review this",
        "focus": None,
        "confidence": 0.5,
    }
    if directive_id is not None:
        advisory["directive_id"] = directive_id

    rec = {
        "schema_id": "spine_shadow_record",
        "schema_version": 1,
        "timestamp": "2026-02-09T12:00:00.000Z",
        "session_id": session_dir.name,
        "run_id": run_id,
        "mode": "M1",
        "moment": {
            "id": "MOMENT_FINDING",
            "confidence": 0.5,
            "trigger_event_count": 1,
        },
        "advisory": advisory,
        "commands": {"count": 0},
        "error": None,
    }
    p = session_dir / "spine_shadow_latest.json"
    p.write_text(json.dumps(rec), encoding="utf-8")


def _read_last_event(session_dir: Path) -> dict:
    lines = (
        (session_dir / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
    )
    assert len(lines) >= 1, "events.jsonl has no lines"
    return json.loads(lines[-1])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRecordAck:
    def test_ack_appends_event(self, tmp_path: Path):
        sess = tmp_path / "sess"
        sess.mkdir()
        _write_shadow_latest(sess, directive_id="dir_ack_001")

        ok = record_latest_directive_outcome(
            session_dir=sess, outcome="ack", component="gui"
        )
        assert ok is True

        ev = _read_last_event(sess)
        assert ev["event_type"] == "attention_acknowledged"
        assert ev["payload"]["directive_id"] == "dir_ack_001"
        assert ev["source"]["component"] == "gui"

    def test_ack_falls_back_to_run_id(self, tmp_path: Path):
        """When advisory has no directive_id, run_id is used."""
        sess = tmp_path / "sess"
        sess.mkdir()
        _write_shadow_latest(sess, run_id="run_fallback_42")

        ok = record_latest_directive_outcome(session_dir=sess, outcome="ack")
        assert ok is True

        ev = _read_last_event(sess)
        assert ev["payload"]["directive_id"] == "run_fallback_42"


class TestRecordDismiss:
    def test_dismiss_appends_event(self, tmp_path: Path):
        sess = tmp_path / "sess"
        sess.mkdir()
        _write_shadow_latest(sess, directive_id="dir_dis_001")

        ok = record_latest_directive_outcome(
            session_dir=sess, outcome="dismiss", component="gui"
        )
        assert ok is True

        ev = _read_last_event(sess)
        assert ev["event_type"] == "attention_dismissed"
        assert ev["payload"]["directive_id"] == "dir_dis_001"
        assert ev["source"]["component"] == "gui"


class TestGracefulFailure:
    def test_returns_false_when_no_shadow_file(self, tmp_path: Path):
        sess = tmp_path / "sess"
        sess.mkdir()
        ok = record_latest_directive_outcome(session_dir=sess, outcome="ack")
        assert ok is False

    def test_returns_false_when_no_session_dir(self, tmp_path: Path):
        ok = record_latest_directive_outcome(
            session_dir=tmp_path / "nonexistent",
            outcome="dismiss",
        )
        assert ok is False
