"""Tests for session_timeline_v1 exporter (PR #16 Seg 1)."""
import json
from pathlib import Path

from tap_tone_pi.core.session_timeline import export_session_timeline


def _write_events(session_dir: Path) -> None:
    p = session_dir / "events.jsonl"
    lines = [
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
        for x in lines:
            if isinstance(x, str):
                f.write(x + "\n")
            else:
                f.write(json.dumps(x) + "\n")


def test_export_writes_payload(tmp_path: Path):
    sess = tmp_path / "session_001"
    sess.mkdir()
    _write_events(sess)

    out = export_session_timeline(sess)
    assert out is not None
    assert out.name == "session_timeline_v1.json"

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["schema_id"] == "session_timeline_v1"
    assert data["schema_version"] == 2
    assert data["session_id"] == "session_001"
    assert data["counts"]["attention_requested"] == 1
    assert data["counts"]["attention_acknowledged"] == 1
    assert data["counts"]["attention_dismissed"] == 1
    assert len(data["directive_events"]) == 3


def test_export_handles_missing_optional_files(tmp_path: Path):
    sess = tmp_path / "session_002"
    sess.mkdir()
    # No events, no shadow, no meta — should still produce a valid file
    out = export_session_timeline(sess)
    assert out is not None

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["directive_events"] == []
    assert data["moment_latest"] is None
    assert isinstance(data["ui_state"], dict)
    assert data["counts"]["attention_requested"] == 0


def test_export_handles_malformed_lines(tmp_path: Path):
    sess = tmp_path / "session_003"
    sess.mkdir()
    _write_events(sess)  # includes a "not json" line

    out = export_session_timeline(sess)
    assert out is not None
    data = json.loads(out.read_text(encoding="utf-8"))
    # Bad line is silently skipped; 3 valid directive events remain
    assert len(data["directive_events"]) == 3


def test_export_returns_none_for_missing_dir(tmp_path: Path):
    assert export_session_timeline(tmp_path / "nonexistent") is None


def test_export_includes_moment_snapshot(tmp_path: Path):
    sess = tmp_path / "session_004"
    sess.mkdir()

    shadow = {
        "moment": {
            "id": "TRUST_EROSION",
            "confidence": 0.85,
            "trigger_event_count": 5,
        }
    }
    (sess / "spine_shadow_latest.json").write_text(
        json.dumps(shadow), encoding="utf-8",
    )

    out = export_session_timeline(sess)
    assert out is not None
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["moment_latest"]["id"] == "TRUST_EROSION"
    assert data["moment_latest"]["confidence"] == 0.85


def test_export_custom_out_path(tmp_path: Path):
    sess = tmp_path / "session_005"
    sess.mkdir()
    custom = tmp_path / "custom_out" / "timeline.json"

    out = export_session_timeline(sess, out_path=custom)
    assert out is not None
    assert out == custom
    assert custom.is_file()
