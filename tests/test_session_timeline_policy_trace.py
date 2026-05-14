"""Tests for PR #19 Seg 2: policy trace in session timeline.

Validates that:
  - export_session_timeline includes latest_policy_trace from shadow record
  - The field is null when shadow record has no trace
  - The schema v2 validates docs with and without policy_trace
  - The timeline viewer renders the trace section
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tap_tone_pi.core.session_timeline import export_session_timeline
from tap_tone_pi.agentic.spine.shadow_record import write_shadow_record

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
                "source": {"component": "spine"},
                "payload": {"directive_id": "d1"},
            }
        ),
    ]
    (session_dir / "events.jsonl").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def _write_shadow_with_trace(session_dir: Path) -> None:
    """Write a shadow record that includes a policy_trace."""
    write_shadow_record(
        session_dir=session_dir,
        session_id=session_dir.name,
        run_id="run_001",
        mode="M1",
        moment_id="FINDING",
        moment_confidence=0.75,
        trigger_event_count=3,
        advisory_action="REVIEW",
        advisory_summary="Potential resonance at 247 Hz",
        advisory_confidence=0.75,
        policy_trace={
            "rule_id": "POLICY_FINDING_REVIEW_v1",
            "max_directives": 2,
        },
    )


# ------------------------------------------------------------------
# 1. Timeline includes latest_policy_trace
# ------------------------------------------------------------------


def test_timeline_includes_latest_policy_trace(tmp_path: Path) -> None:
    """Exported timeline has latest_policy_trace from shadow record."""
    sess = tmp_path / "sess_trace"
    sess.mkdir()
    _write_events(sess)
    _write_shadow_with_trace(sess)

    out = export_session_timeline(sess)
    assert out is not None
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["latest_policy_trace"] is not None
    assert data["latest_policy_trace"]["rule_id"] == "POLICY_FINDING_REVIEW_v1"
    assert data["latest_policy_trace"]["max_directives"] == 2


def test_timeline_null_policy_trace_when_missing(tmp_path: Path) -> None:
    """No shadow record → latest_policy_trace is null."""
    sess = tmp_path / "sess_no_trace"
    sess.mkdir()
    _write_events(sess)

    out = export_session_timeline(sess)
    assert out is not None
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["latest_policy_trace"] is None


# ------------------------------------------------------------------
# 2. Schema v2 validation
# ------------------------------------------------------------------


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
def test_schema_v2_validates_with_policy_trace(tmp_path: Path) -> None:
    """Full doc with policy_trace passes schema validation."""
    sess = tmp_path / "sess_v2_with"
    sess.mkdir()
    _write_events(sess)
    _write_shadow_with_trace(sess)

    out = export_session_timeline(sess)
    assert out is not None
    payload = json.loads(out.read_text(encoding="utf-8"))

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=payload, schema=schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
def test_schema_v2_validates_without_policy_trace(tmp_path: Path) -> None:
    """Doc with null latest_policy_trace still passes schema."""
    sess = tmp_path / "sess_v2_without"
    sess.mkdir()
    _write_events(sess)

    out = export_session_timeline(sess)
    assert out is not None
    payload = json.loads(out.read_text(encoding="utf-8"))

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=payload, schema=schema)


# ------------------------------------------------------------------
# 3. Schema version bumped to 2
# ------------------------------------------------------------------


def test_exported_schema_version_is_2(tmp_path: Path) -> None:
    """Exporter emits schema_version: 2 after PR #19."""
    sess = tmp_path / "sess_v2_check"
    sess.mkdir()

    out = export_session_timeline(sess)
    assert out is not None
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["schema_version"] == 2


# ------------------------------------------------------------------
# 4. load_timeline renders policy trace data
# ------------------------------------------------------------------


def test_load_timeline_includes_policy_trace(tmp_path: Path) -> None:
    """load_timeline returns the latest_policy_trace field."""
    from tap_tone_pi.gui.timeline_viewer import load_timeline

    sess = tmp_path / "sess_load_trace"
    sess.mkdir()
    _write_events(sess)
    _write_shadow_with_trace(sess)

    # Export first so the file exists
    export_session_timeline(sess)
    data = load_timeline(sess, allow_export=False)
    assert data is not None
    assert data["latest_policy_trace"]["rule_id"] == "POLICY_FINDING_REVIEW_v1"
