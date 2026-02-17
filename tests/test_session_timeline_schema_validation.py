"""Session timeline schema validation tests.

Validates that export_session_timeline() output conforms to the
contracts/schemas/session_timeline_v1.schema.json contract, and that
the schema itself is well-formed and registered.
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
REGISTRY_PATH = REPO_ROOT / "contracts" / "schema_registry.json"


# ------------------------------------------------------------------
# 1. Schema file existence & parse
# ------------------------------------------------------------------


def test_schema_file_exists() -> None:
    """session_timeline_v1.schema.json must exist in contracts/schemas/."""
    assert SCHEMA_PATH.is_file(), f"Missing schema: {SCHEMA_PATH}"


def test_schema_is_valid_json() -> None:
    """Schema must parse as valid JSON."""
    raw = SCHEMA_PATH.read_text(encoding="utf-8")
    schema = json.loads(raw)
    assert isinstance(schema, dict)
    assert schema.get("$id") == "session_timeline_v1.schema.json"


# ------------------------------------------------------------------
# 2. Schema is registered in the registry
# ------------------------------------------------------------------


def test_schema_registered_in_registry() -> None:
    """session_timeline must appear in schema_registry.json."""
    reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    schemas = reg.get("schemas", {})
    assert (
        "session_timeline" in schemas
    ), f"session_timeline not found in registry keys: {list(schemas.keys())}"
    entry = schemas["session_timeline"]
    assert entry["path"] == "contracts/schemas/session_timeline_v1.schema.json"
    assert entry["schema_version_const"] == "session_timeline_v1"


# ------------------------------------------------------------------
# 3. Exported timeline validates against schema
# ------------------------------------------------------------------


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
def test_empty_session_validates(tmp_path: Path) -> None:
    """An empty session must produce valid output (zero events, null moment)."""
    sess = tmp_path / "session_empty"
    sess.mkdir()

    out = export_session_timeline(sess)
    assert out is not None

    payload = json.loads(out.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=payload, schema=schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
def test_session_with_events_validates(tmp_path: Path) -> None:
    """Session with directive events must validate against schema."""
    sess = tmp_path / "session_events"
    sess.mkdir()

    # Write a few directive events
    lines = [
        json.dumps(
            {
                "event_type": "attention_requested",
                "occurred_at": "2026-02-08T10:00:00Z",
                "source": {"component": "wolf_detector"},
                "payload": {"directive_id": "d1"},
            }
        ),
        json.dumps(
            {
                "event_type": "attention_acknowledged",
                "occurred_at": "2026-02-08T10:01:00Z",
                "source": {"component": "gui"},
                "payload": {"directive_id": "d1"},
            }
        ),
    ]
    (sess / "events.jsonl").write_text("\n".join(lines), encoding="utf-8")

    out = export_session_timeline(sess)
    assert out is not None

    payload = json.loads(out.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=payload, schema=schema)

    # Verify counts are consistent
    assert payload["counts"]["attention_requested"] == 1
    assert payload["counts"]["attention_acknowledged"] == 1
    assert payload["counts"]["attention_dismissed"] == 0


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
def test_session_with_shadow_validates(tmp_path: Path) -> None:
    """Session with a shadow record must embed moment_latest and validate."""
    sess = tmp_path / "session_shadow"
    sess.mkdir()

    shadow = {
        "moment": {
            "id": "TRUST_EROSION",
            "confidence": 0.85,
            "trigger_event_count": 3,
        },
        "advisory": {"action": "REVIEW", "summary": "Test"},
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

    assert payload["moment_latest"]["id"] == "TRUST_EROSION"
    assert payload["moment_latest"]["confidence"] == 0.85


# ------------------------------------------------------------------
# 4. Required fields & types
# ------------------------------------------------------------------


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
def test_missing_required_field_fails_validation() -> None:
    """Payload without schema_id must fail validation."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    bad_payload = {
        # "schema_id" intentionally omitted
        "schema_version": 2,
        "session_id": "test",
        "paths": {
            "events_jsonl": "events.jsonl",
            "shadow_latest": "spine_shadow_latest.json",
            "advisory_state": "meta/advisory_state.json",
        },
        "moment_latest": None,
        "directive_events": [],
        "counts": {
            "attention_requested": 0,
            "attention_acknowledged": 0,
            "attention_dismissed": 0,
        },
        "ui_state": {},
        "latest_policy_trace": None,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad_payload, schema=schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
def test_extra_top_level_field_fails_validation() -> None:
    """additionalProperties: false must reject unknown top-level keys."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    bad_payload = {
        "schema_id": "session_timeline_v1",
        "schema_version": 2,
        "session_id": "test",
        "paths": {
            "events_jsonl": "events.jsonl",
            "shadow_latest": "spine_shadow_latest.json",
            "advisory_state": "meta/advisory_state.json",
        },
        "moment_latest": None,
        "directive_events": [],
        "counts": {
            "attention_requested": 0,
            "attention_acknowledged": 0,
            "attention_dismissed": 0,
        },
        "ui_state": {},
        "latest_policy_trace": None,
        "rogue_field": True,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad_payload, schema=schema)


def test_exported_paths_field_present(tmp_path: Path) -> None:
    """Exporter must emit the 'paths' object with canonical source paths."""
    sess = tmp_path / "session_paths"
    sess.mkdir()

    out = export_session_timeline(sess)
    assert out is not None

    payload = json.loads(out.read_text(encoding="utf-8"))
    paths = payload["paths"]
    assert paths["events_jsonl"] == "events.jsonl"
    assert paths["shadow_latest"] == "spine_shadow_latest.json"
    assert paths["advisory_state"] == "meta/advisory_state.json"


# ------------------------------------------------------------------
# 5. Registry ↔ payload alignment
# ------------------------------------------------------------------


def test_registry_schema_version_const_matches_payload_schema_id(
    tmp_path: Path,
) -> None:
    """schema_version_const in registry must equal schema_id in exported payload."""
    reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    entry = reg["schemas"]["session_timeline"]
    registry_const = entry["schema_version_const"]

    sess = tmp_path / "session_align"
    sess.mkdir()
    out = export_session_timeline(sess)
    assert out is not None
    payload = json.loads(out.read_text(encoding="utf-8"))

    assert payload["schema_id"] == registry_const, (
        f"Drift: exporter emits schema_id={payload['schema_id']!r} "
        f"but registry has schema_version_const={registry_const!r}"
    )


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
def test_registry_driven_validation(tmp_path: Path) -> None:
    """Resolve schema via registry path and validate an exported payload."""
    reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    entry = reg["schemas"]["session_timeline"]
    schema_file = REPO_ROOT / entry["path"]
    assert schema_file.is_file(), f"Registry points to missing file: {schema_file}"

    schema = json.loads(schema_file.read_text(encoding="utf-8"))

    sess = tmp_path / "session_reg"
    sess.mkdir()
    out = export_session_timeline(sess)
    assert out is not None

    payload = json.loads(out.read_text(encoding="utf-8"))
    jsonschema.validate(instance=payload, schema=schema)


# ------------------------------------------------------------------
# 6. Future-proofing: extensible sub-objects
# ------------------------------------------------------------------


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
def test_directive_event_with_extra_field_validates() -> None:
    """directive_events items allow additional properties for forward compat."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    payload = {
        "schema_id": "session_timeline_v1",
        "schema_version": 2,
        "session_id": "test",
        "paths": {
            "events_jsonl": "events.jsonl",
            "shadow_latest": "spine_shadow_latest.json",
            "advisory_state": "meta/advisory_state.json",
        },
        "moment_latest": None,
        "directive_events": [
            {
                "timestamp": "2026-02-09T00:00:00Z",
                "event_type": "attention_requested",
                "directive_id": "d1",
                "component": "spine",
                "future_field": "should not break",
            }
        ],
        "counts": {
            "attention_requested": 1,
            "attention_acknowledged": 0,
            "attention_dismissed": 0,
        },
        "ui_state": {},
        "latest_policy_trace": None,
    }
    jsonschema.validate(instance=payload, schema=schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
def test_paths_with_extra_key_validates() -> None:
    """paths object allows additional keys for forward compat."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    payload = {
        "schema_id": "session_timeline_v1",
        "schema_version": 2,
        "session_id": "test",
        "paths": {
            "events_jsonl": "events.jsonl",
            "shadow_latest": "spine_shadow_latest.json",
            "advisory_state": "meta/advisory_state.json",
            "future_path": "meta/something_new.json",
        },
        "moment_latest": None,
        "directive_events": [],
        "counts": {
            "attention_requested": 0,
            "attention_acknowledged": 0,
            "attention_dismissed": 0,
        },
        "ui_state": {},
        "latest_policy_trace": None,
    }
    jsonschema.validate(instance=payload, schema=schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
def test_ui_state_with_arbitrary_keys_validates() -> None:
    """ui_state allows arbitrary keys (no additionalProperties constraint)."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    payload = {
        "schema_id": "session_timeline_v1",
        "schema_version": 2,
        "session_id": "test",
        "paths": {
            "events_jsonl": "events.jsonl",
            "shadow_latest": "spine_shadow_latest.json",
            "advisory_state": "meta/advisory_state.json",
        },
        "moment_latest": None,
        "directive_events": [],
        "counts": {
            "attention_requested": 0,
            "attention_acknowledged": 0,
            "attention_dismissed": 0,
        },
        "ui_state": {
            "show_directive_history": True,
            "custom_pref": {"nested": 42},
        },
        "latest_policy_trace": None,
    }
    jsonschema.validate(instance=payload, schema=schema)
