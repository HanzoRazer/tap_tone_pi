"""Tests for PR #17: session_timeline_v1.json inclusion in viewer packs.

Validates that:
  - export_session_timeline writes to the canonical meta/ path
  - the timeline file is in the location both exporters copy from
  - kind detection classifies it as session_meta
  - the exported payload validates against the registry schema
  - timeline export failure does not prevent pack operations (fail-closed)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tap_tone_pi.core.session_timeline import export_session_timeline

try:
    import jsonschema

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    jsonschema = None  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / "session_timeline_v1.schema.json"


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------


def _write_events(session_dir: Path) -> None:
    lines = [
        json.dumps(
            {
                "event_type": "attention_requested",
                "occurred_at": "2026-02-09T10:00:00Z",
                "source": {"component": "wolf_detector"},
                "payload": {"directive_id": "d1"},
            }
        ),
        json.dumps(
            {
                "event_type": "attention_acknowledged",
                "occurred_at": "2026-02-09T10:01:00Z",
                "source": {"component": "gui"},
                "payload": {"directive_id": "d1"},
            }
        ),
    ]
    (session_dir / "events.jsonl").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


# ------------------------------------------------------------------
# 1. Timeline lands at the canonical meta/ path
# ------------------------------------------------------------------


def test_timeline_writes_to_meta_dir(tmp_path: Path) -> None:
    """export_session_timeline must create meta/session_timeline_v1.json."""
    sess = tmp_path / "session_pack"
    sess.mkdir()
    _write_events(sess)

    out = export_session_timeline(sess)
    assert out is not None
    assert out == sess / "meta" / "session_timeline_v1.json"
    assert out.is_file()


def test_timeline_includes_events_in_payload(tmp_path: Path) -> None:
    """Exported payload must contain the directive events."""
    sess = tmp_path / "session_events"
    sess.mkdir()
    _write_events(sess)

    out = export_session_timeline(sess)
    assert out is not None
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["schema_id"] == "session_timeline_v1"
    assert len(data["directive_events"]) == 2
    assert data["counts"]["attention_requested"] == 1
    assert data["counts"]["attention_acknowledged"] == 1


# ------------------------------------------------------------------
# 2. Kind detection classifies timeline as session_meta
# ------------------------------------------------------------------


def test_phase2_kind_detects_timeline_as_session_meta() -> None:
    """meta/session_timeline_v1.json must map to 'session_meta' kind."""
    # Import the phase2 exporter kind detection
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from phase2.export_viewer_pack_v1 import detect_kind

    kind = detect_kind("meta/session_timeline_v1.json")
    assert kind == "session_meta"


def test_export_kind_detects_timeline_as_session_meta() -> None:
    """meta/session_timeline_v1.json must map to 'session_meta' in export exporter."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from export.viewer_pack_v1_export import _get_kind

    kind = _get_kind("meta/session_timeline_v1.json", "session_timeline_v1.json")
    assert kind == "session_meta"


# ------------------------------------------------------------------
# 3. Schema validation of included timeline
# ------------------------------------------------------------------


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
def test_included_timeline_validates_against_schema(tmp_path: Path) -> None:
    """Timeline written by the exporter must pass schema validation."""
    sess = tmp_path / "session_schema"
    sess.mkdir()
    _write_events(sess)

    # Also add a shadow record
    shadow = {
        "moment": {
            "id": "FINDING",
            "confidence": 0.72,
            "trigger_event_count": 2,
        },
    }
    (sess / "spine_shadow_latest.json").write_text(
        json.dumps(shadow),
        encoding="utf-8",
    )

    out = export_session_timeline(sess)
    assert out is not None

    payload = json.loads(out.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=payload, schema=schema)

    # Verify moment is included
    assert payload["moment_latest"]["id"] == "FINDING"


# ------------------------------------------------------------------
# 4. Fail-closed: timeline failure must not crash pack export
# ------------------------------------------------------------------


def test_timeline_export_returns_none_for_missing_dir(tmp_path: Path) -> None:
    """export_session_timeline must return None for non-existent dir."""
    result = export_session_timeline(tmp_path / "nonexistent")
    assert result is None


def test_timeline_export_succeeds_with_empty_session(tmp_path: Path) -> None:
    """An empty session dir must still produce a valid timeline."""
    sess = tmp_path / "session_empty"
    sess.mkdir()

    out = export_session_timeline(sess)
    assert out is not None

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["directive_events"] == []
    assert data["moment_latest"] is None
    assert data["counts"]["attention_requested"] == 0
