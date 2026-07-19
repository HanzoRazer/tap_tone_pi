# INSTRUMENT CLASS: MEASUREMENT
"""Tests for advisory authority leakage prevention.

Validates that advisory/guidance fields do not leak into canonical
measurement artifacts (analysis.json, quality_check.json, manifest.json).

Advisory data is allowed only in designated locations:
- meta/session_timeline_v1.json
- meta/advisory*
- agentic/*

See: docs/AGE_CONSTITUTIONAL_CONTRACT.md
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FORBIDDEN_EXPORT_KEYS = {
    "recommendation",
    "recommended_action",
    "guidance",
    "authority_scope",
    "can_establish_truth",
    "can_modify_measurement",
    "can_enter_measurement_export",
    "interpretive_confidence",
    "recommendation_confidence",
    "typed_confidence",
    "advisory",
    "directive",
    "attention_action",
}

ALLOWED_ADVISORY_PATHS = {
    "session_timeline_v1.json",
    "advisory",
    "agentic",
}


def _contains_forbidden_key(obj: Any, forbidden: set[str]) -> str | None:
    """Recursively check if object contains any forbidden keys.

    Returns the first forbidden key found, or None if clean.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in forbidden:
                return k
            found = _contains_forbidden_key(v, forbidden)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _contains_forbidden_key(item, forbidden)
            if found:
                return found
    return None


def _is_allowed_advisory_path(path: Path) -> bool:
    """Check if path is an allowed location for advisory data."""
    path_str = str(path)
    for allowed in ALLOWED_ADVISORY_PATHS:
        if allowed in path_str:
            return True
    return False


def _create_clean_analysis_json() -> dict:
    """Create a clean analysis.json fixture."""
    return {
        "schema_version": "1.0.0",
        "session_id": "test_session_001",
        "peaks": [
            {"frequency_hz": 247.5, "amplitude_db": -12.3, "q_factor": 45.2},
            {"frequency_hz": 432.0, "amplitude_db": -18.1, "q_factor": 32.8},
        ],
        "metadata": {
            "sample_rate": 48000,
            "fft_size": 8192,
            "window": "hann",
        },
    }


def _create_clean_quality_check_json() -> dict:
    """Create a clean quality_check.json fixture."""
    return {
        "schema_version": "1.0.0",
        "checks": [
            {"name": "snr_threshold", "passed": True, "value": 42.5, "threshold": 30.0},
            {
                "name": "repeatability",
                "passed": True,
                "variance_pct": 1.2,
                "threshold_pct": 5.0,
            },
        ],
        "overall_status": "passed",
    }


def _create_clean_manifest_json() -> dict:
    """Create a clean manifest.json fixture."""
    return {
        "schema_version": "1.0.0",
        "artifacts": [
            {"path": "analysis.json", "sha256": "abc123", "type": "measurement"},
            {"path": "audio/tap_001.wav", "sha256": "def456", "type": "capture"},
        ],
        "created_at": "2026-05-23T12:00:00Z",
    }


def _create_session_timeline_json() -> dict:
    """Create a session_timeline_v1.json with advisory data (allowed)."""
    return {
        "schema_version": "1.0.0",
        "events": [
            {"timestamp": "2026-05-23T12:00:00Z", "type": "capture_started"},
            {"timestamp": "2026-05-23T12:00:05Z", "type": "capture_completed"},
        ],
        "advisory": {
            "directives_emitted": 1,
            "authority_scope": "attention_guidance",
            "can_establish_truth": False,
        },
        "guidance": {
            "directive": {
                "action": "review",
                "summary": "Review potential anomaly",
            },
        },
    }


class TestCleanMeasurementExports:
    """Tests verifying clean measurement artifacts pass validation."""

    def test_clean_analysis_json_has_no_forbidden_keys(self):
        """Clean analysis.json should not contain forbidden keys."""
        data = _create_clean_analysis_json()
        found = _contains_forbidden_key(data, FORBIDDEN_EXPORT_KEYS)
        assert found is None

    def test_clean_quality_check_has_no_forbidden_keys(self):
        """Clean quality_check.json should not contain forbidden keys."""
        data = _create_clean_quality_check_json()
        found = _contains_forbidden_key(data, FORBIDDEN_EXPORT_KEYS)
        assert found is None

    def test_clean_manifest_has_no_forbidden_keys(self):
        """Clean manifest.json should not contain forbidden keys."""
        data = _create_clean_manifest_json()
        found = _contains_forbidden_key(data, FORBIDDEN_EXPORT_KEYS)
        assert found is None


class TestAdvisoryAllowedLocations:
    """Tests verifying advisory data is allowed in designated locations."""

    def test_session_timeline_may_contain_advisory_authority(self):
        """session_timeline_v1.json may contain advisory fields."""
        path = Path("meta/session_timeline_v1.json")
        assert _is_allowed_advisory_path(path)

        data = _create_session_timeline_json()
        found = _contains_forbidden_key(data, FORBIDDEN_EXPORT_KEYS)
        # Would find keys, but path is allowed
        assert found is not None  # Keys exist
        assert _is_allowed_advisory_path(path)  # But path is allowed

    def test_advisory_directory_is_allowed(self):
        """meta/advisory/ directory is allowed for advisory data."""
        assert _is_allowed_advisory_path(Path("meta/advisory/directives.json"))
        assert _is_allowed_advisory_path(Path("meta/advisory_history.json"))

    def test_agentic_directory_is_allowed(self):
        """agentic/ directory is allowed for advisory data."""
        assert _is_allowed_advisory_path(Path("agentic/events.json"))
        assert _is_allowed_advisory_path(Path("agentic/policy_log.json"))


class TestForbiddenKeyDetection:
    """Tests verifying forbidden keys are detected in wrong locations."""

    def test_analysis_json_rejects_advisory_authority_key(self):
        """analysis.json must not contain authority_scope."""
        data = _create_clean_analysis_json()
        data["authority_scope"] = "attention_guidance"  # Inject forbidden key

        found = _contains_forbidden_key(data, FORBIDDEN_EXPORT_KEYS)
        assert found == "authority_scope"

    def test_analysis_json_rejects_recommendation_key(self):
        """analysis.json must not contain recommendation."""
        data = _create_clean_analysis_json()
        data["recommendation"] = "adjust bass bar"  # Inject forbidden key

        found = _contains_forbidden_key(data, FORBIDDEN_EXPORT_KEYS)
        assert found == "recommendation"

    def test_quality_check_rejects_guidance_key(self):
        """quality_check.json must not contain guidance."""
        data = _create_clean_quality_check_json()
        data["guidance"] = {"directive": "review"}  # Inject forbidden key

        found = _contains_forbidden_key(data, FORBIDDEN_EXPORT_KEYS)
        assert found == "guidance"

    def test_quality_check_rejects_can_establish_truth(self):
        """quality_check.json must not contain can_establish_truth."""
        data = _create_clean_quality_check_json()
        data["authority"] = {"can_establish_truth": False}  # Inject nested

        found = _contains_forbidden_key(data, FORBIDDEN_EXPORT_KEYS)
        assert found == "can_establish_truth"

    def test_manifest_rejects_directive_key(self):
        """manifest.json must not contain directive."""
        data = _create_clean_manifest_json()
        data["directive"] = {"action": "review"}  # Inject forbidden key

        found = _contains_forbidden_key(data, FORBIDDEN_EXPORT_KEYS)
        assert found == "directive"

    def test_nested_forbidden_key_detected(self):
        """Deeply nested forbidden keys are detected."""
        data = _create_clean_analysis_json()
        data["nested"] = {
            "level1": {"level2": {"level3": {"recommendation": "hidden advisory"}}}
        }

        found = _contains_forbidden_key(data, FORBIDDEN_EXPORT_KEYS)
        assert found == "recommendation"

    def test_forbidden_key_in_list_detected(self):
        """Forbidden keys inside list items are detected."""
        data = _create_clean_analysis_json()
        data["items"] = [
            {"name": "item1"},
            {"name": "item2", "advisory": "should not be here"},
        ]

        found = _contains_forbidden_key(data, FORBIDDEN_EXPORT_KEYS)
        assert found == "advisory"


class TestExportBoundaryIntegration:
    """Integration tests for export boundary validation."""

    def test_full_export_structure_validation(self, tmp_path: Path):
        """Validate a complete export directory structure."""
        # Create export structure
        export_dir = tmp_path / "session_export"
        export_dir.mkdir()
        (export_dir / "meta").mkdir()

        # Write clean measurement artifacts
        (export_dir / "analysis.json").write_text(
            json.dumps(_create_clean_analysis_json())
        )
        (export_dir / "quality_check.json").write_text(
            json.dumps(_create_clean_quality_check_json())
        )
        (export_dir / "manifest.json").write_text(
            json.dumps(_create_clean_manifest_json())
        )

        # Write advisory data in allowed location
        (export_dir / "meta" / "session_timeline_v1.json").write_text(
            json.dumps(_create_session_timeline_json())
        )

        # Validate measurement artifacts
        measurement_files = ["analysis.json", "quality_check.json", "manifest.json"]
        for filename in measurement_files:
            path = export_dir / filename
            data = json.loads(path.read_text())
            found = _contains_forbidden_key(data, FORBIDDEN_EXPORT_KEYS)
            assert found is None, f"{filename} contains forbidden key: {found}"

        # Advisory data is allowed in meta/session_timeline_v1.json
        timeline_path = export_dir / "meta" / "session_timeline_v1.json"
        assert _is_allowed_advisory_path(timeline_path)

    def test_contaminated_export_fails_validation(self, tmp_path: Path):
        """Export with advisory leakage in measurement artifact fails."""
        export_dir = tmp_path / "bad_export"
        export_dir.mkdir()

        # Create contaminated analysis.json
        contaminated = _create_clean_analysis_json()
        contaminated["guidance"] = {
            "directive": {"action": "review", "summary": "Check this"},
            "authority_scope": "attention_guidance",
        }

        (export_dir / "analysis.json").write_text(json.dumps(contaminated))

        # Validation should find forbidden keys
        data = json.loads((export_dir / "analysis.json").read_text())
        found = _contains_forbidden_key(data, FORBIDDEN_EXPORT_KEYS)
        assert found is not None
        assert found in {"guidance", "directive", "authority_scope"}
