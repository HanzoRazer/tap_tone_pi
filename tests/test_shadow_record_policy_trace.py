"""Tests for PR #19 Seg 1: policy_trace in shadow record.

Validates that:
  - write_shadow_record accepts an optional policy_trace kwarg
  - The trace is persisted and round-trips via load_latest_shadow_record
  - Validation requires rule_id when trace is present
  - Extra keys inside the trace are allowed (future-proof)
  - Legacy records without policy_trace remain valid
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from tap_tone_pi.agentic.spine.shadow_record import (
    write_shadow_record,
    load_latest_shadow_record,
    _validate_shadow_record_v1,
)


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------

def _base_kwargs(session_dir: Path) -> Dict[str, Any]:
    """Minimal valid kwargs for write_shadow_record."""
    return dict(
        session_dir=session_dir,
        session_id="sess_001",
        run_id="run_001",
        mode="M1",
        moment_id="FINDING",
        moment_confidence=0.75,
        trigger_event_count=3,
    )


_SAMPLE_TRACE: Dict[str, Any] = {
    "rule_id": "POLICY_FINDING_REVIEW_v1",
    "max_directives": 2,
}


# ------------------------------------------------------------------
# 1. Existing behaviour unchanged
# ------------------------------------------------------------------

def test_write_shadow_record_without_policy_trace(tmp_path: Path) -> None:
    """Legacy call (no policy_trace kwarg) still works; field is null."""
    rec = write_shadow_record(**_base_kwargs(tmp_path))
    assert rec.get("policy_trace") is None


# ------------------------------------------------------------------
# 2. policy_trace persisted + round-trips
# ------------------------------------------------------------------

def test_write_shadow_record_with_policy_trace(tmp_path: Path) -> None:
    """Passing policy_trace persists it in the record."""
    rec = write_shadow_record(**_base_kwargs(tmp_path), policy_trace=_SAMPLE_TRACE)
    assert rec["policy_trace"] is not None
    assert rec["policy_trace"]["rule_id"] == "POLICY_FINDING_REVIEW_v1"
    assert rec["policy_trace"]["max_directives"] == 2


def test_policy_trace_roundtrip_via_loader(tmp_path: Path) -> None:
    """Written policy_trace survives load_latest_shadow_record."""
    write_shadow_record(**_base_kwargs(tmp_path), policy_trace=_SAMPLE_TRACE)
    loaded = load_latest_shadow_record(tmp_path)
    assert loaded is not None
    assert loaded["policy_trace"]["rule_id"] == "POLICY_FINDING_REVIEW_v1"


# ------------------------------------------------------------------
# 3. Validation: rule_id required when trace is present
# ------------------------------------------------------------------

def test_policy_trace_validation_requires_rule_id(tmp_path: Path) -> None:
    """A trace dict without rule_id raises ValueError."""
    with pytest.raises(ValueError, match="rule_id"):
        write_shadow_record(
            **_base_kwargs(tmp_path),
            policy_trace={"max_directives": 2},  # no rule_id
        )


# ------------------------------------------------------------------
# 4. Extra keys allowed (future-proof)
# ------------------------------------------------------------------

def test_policy_trace_allows_extra_keys(tmp_path: Path) -> None:
    """Trace with arbitrary extra fields passes validation."""
    big_trace = {
        "rule_id": "POLICY_OVERLOAD_REVIEW_v1",
        "max_directives": 1,
        "would_have_emitted": {"action": "REVIEW", "summary": "test"},
        "soft_prompt": False,
        "suppressed_due_to_initiative": False,
        "fallback_mode": None,
        "custom_future_field": 42,
    }
    rec = write_shadow_record(**_base_kwargs(tmp_path), policy_trace=big_trace)
    assert rec["policy_trace"]["custom_future_field"] == 42


# ------------------------------------------------------------------
# 5. policy_trace must be dict or None
# ------------------------------------------------------------------

def test_policy_trace_must_be_dict_or_none(tmp_path: Path) -> None:
    """Non-dict value for policy_trace raises ValueError."""
    with pytest.raises(ValueError, match="policy_trace must be null or object"):
        write_shadow_record(
            **_base_kwargs(tmp_path),
            policy_trace="not-a-dict",  # type: ignore[arg-type]
        )


# ------------------------------------------------------------------
# 6. Legacy record without policy_trace loads fine
# ------------------------------------------------------------------

def test_legacy_record_without_policy_trace_loads(tmp_path: Path) -> None:
    """A record written before PR #19 (no policy_trace key) still loads."""
    # Manually write a record without the key
    legacy = {
        "schema_id": "spine_shadow_record",
        "schema_version": 1,
        "timestamp": "2026-02-09T00:00:00.000Z",
        "session_id": "sess_legacy",
        "run_id": "run_legacy",
        "mode": "M0",
        "moment": {"id": "NONE", "confidence": 0.0, "trigger_event_count": 0},
        "advisory": None,
        "commands": {"count": 0},
        "error": None,
        # Note: NO policy_trace key at all
    }
    path = tmp_path / "spine_shadow_latest.json"
    path.write_text(json.dumps(legacy), encoding="utf-8")

    loaded = load_latest_shadow_record(tmp_path)
    assert loaded is not None
    assert loaded["session_id"] == "sess_legacy"
    # policy_trace key simply absent — not an error
    assert loaded.get("policy_trace") is None
