"""Schema + registry contract tests for secondary_peak_analysis_v1.

Checks the artifact shape (required fields, optional-field absence, positivity,
digest format, status enum, no unknown fields) and that the schema is registered
additively under measurement-team with a matching version const and file.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    REPO_ROOT / "contracts" / "schemas" / "secondary_peak_analysis_v1.schema.json"
)
REGISTRY_PATH = REPO_ROOT / "contracts" / "schema_registry.json"
SCHEMA_VERSION = "secondary_peak_analysis_v1"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _minimal() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "source_wav_sha256": "a" * 64,
        "peak_id": "p1",
        "peak_frequency_hz": 196.5,
        "status": "NOT_RESOLVED",
    }


def _full() -> dict:
    rec = _minimal()
    rec.update(
        status="RESOLVED",
        peak_magnitude_db=-1.2,
        bandwidth_3db_hz=6.4,
        q_from_bandwidth=30.7,
        decay_tau_s=0.051,
        q_from_decay=31.2,
        log_decrement=0.09,
        q_agreement_pct=98.4,
        confidence=0.82,
        confidence_components={"snr": 0.9, "bandwidth": 1.0, "decay_r2": 0.98},
        fit_window_s=0.3,
        noise_floor_db=-48.0,
        snr_db=46.8,
        method_flags=["bandwidth_halfpower", "decay_curvefit", "logdec_cross_check"],
        blocked_fields=[],
    )
    return rec


class TestSchemaShape:
    def test_schema_is_valid_draft_2020_12(self):
        jsonschema.Draft202012Validator.check_schema(_schema())

    def test_version_const(self):
        assert _schema()["properties"]["schema_version"]["const"] == SCHEMA_VERSION

    def test_minimal_validates(self):
        jsonschema.validate(_minimal(), _schema())

    def test_full_validates(self):
        jsonschema.validate(_full(), _schema())

    def test_missing_optional_q_is_accepted(self):
        rec = _full()
        del rec["q_from_decay"]
        del rec["q_from_bandwidth"]
        del rec["q_agreement_pct"]
        jsonschema.validate(rec, _schema())

    @pytest.mark.parametrize(
        "field", ["bandwidth_3db_hz", "q_from_bandwidth", "decay_tau_s", "q_from_decay"]
    )
    def test_negative_or_zero_metric_rejected(self, field):
        rec = _full()
        rec[field] = 0
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(rec, _schema())

    def test_nonpositive_frequency_rejected(self):
        rec = _minimal()
        rec["peak_frequency_hz"] = 0
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(rec, _schema())

    def test_bad_sha256_rejected(self):
        rec = _minimal()
        rec["source_wav_sha256"] = "not-a-digest"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(rec, _schema())

    def test_bad_status_rejected(self):
        rec = _minimal()
        rec["status"] = "MAYBE"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(rec, _schema())

    def test_confidence_out_of_range_rejected(self):
        rec = _full()
        rec["confidence"] = 1.5
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(rec, _schema())

    def test_unknown_field_rejected(self):
        rec = _minimal()
        rec["wood_quality"] = "excellent"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(rec, _schema())

    def test_unknown_confidence_component_rejected(self):
        rec = _full()
        rec["confidence_components"]["magic"] = 1.0
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(rec, _schema())


class TestRegistryWiring:
    @staticmethod
    def _registry() -> dict:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    def test_registered_with_matching_const_and_file(self):
        entry = self._registry()["schemas"]["secondary_peak_analysis"]
        assert entry["schema_version_const"] == SCHEMA_VERSION
        assert entry["file"] == SCHEMA_PATH.name
        assert (REPO_ROOT / entry["path"]).exists()

    def test_owner_lists_the_schema(self):
        registry = self._registry()
        owner = registry["schemas"]["secondary_peak_analysis"]["owner"]
        assert owner == "measurement-team"
        assert "secondary_peak_analysis" in registry["owners"][owner]["schemas"]
