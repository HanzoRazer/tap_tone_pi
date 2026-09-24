"""Contract tests for ttp_prototype_run_v1 (TTP-PROTOTYPE-001).

These check the *shape* of a prototype-commissioning run: that the additive
schema exists, is registered, validates a well-formed run at each stage, and —
crucially for P05/P10 — offers no field through which a run could promote a
component to qualified or declare PCB/production readiness. The cross-field
behavioural invariants (P01-P10) live in test_prototype_check.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "contracts" / "ttp_prototype_run_v1.schema.json"
REGISTRY_PATH = REPO_ROOT / "contracts" / "schema_registry.json"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _valid_r0() -> dict:
    return {
        "schema_version": "ttp_prototype_run_v1",
        "run_id": "r0-001",
        "generated_at": "2026-09-24T00:00:00Z",
        "stage": "R0",
        "specimen_id": "plate-A",
        "status": "EXECUTED",
        "evidence_origin": "HARDWARE",
        "witnessed": True,
        "excitation": {"excitation_mode": "MANUAL", "excitation_method": "manual_tap"},
        "response": {
            "response_path": "MICROPHONE",
            "input_device_id": "pulse",
            "sample_rate_hz": 48000,
            "microphone_id": "MIC-CAND-1",
        },
        "force": {"measured_force_claimed": False, "force_chain": None},
        "artifacts": [
            {
                "artifact_id": "a1",
                "kind": "wav",
                "sha256": "a" * 64,
                "byte_count": 10,
                "media_type": "audio/wav",
                "storage_locator": "s3://bucket/a1.wav",
                "repository_tracked": False,
            }
        ],
        "limitations": ["prototype, not reference-grade"],
    }


def _valid_r1() -> dict:
    run = _valid_r0()
    run.update(run_id="r1-001", stage="R1")
    run["added_mass"] = {"mass_challenge_id": "m1", "added_mass_g": 1.98}
    return run


def _valid_r2() -> dict:
    run = _valid_r0()
    run.update(run_id="r2-001", stage="R2")
    run["excitation"] = {
        "excitation_mode": "COMMANDED",
        "excitation_method": "stepped_sine_sweep",
        "commanded_amplitude": 0.5,
        "commanded_amplitude_unit": "dbfs",
        "output_device_id": "pulse-out",
        "amplifier_id": "AMP-CAND",
        "exciter_id": "EX-CAND",
        "coupling_id": "COUP-CAND",
        "emission_provenance": {"emitted_signal_id": "sig-1", "waveform_kind": "sweep"},
    }
    return run


class TestSchemaShape:
    def test_schema_is_valid_draft_2020_12(self) -> None:
        jsonschema.Draft202012Validator.check_schema(_schema())

    def test_schema_version_const(self) -> None:
        assert (
            _schema()["properties"]["schema_version"]["const"] == "ttp_prototype_run_v1"
        )

    @pytest.mark.parametrize("run", [_valid_r0(), _valid_r1(), _valid_r2()])
    def test_valid_runs_validate(self, run: dict) -> None:
        jsonschema.validate(run, _schema())

    def test_unknown_top_level_field_is_rejected(self) -> None:
        run = _valid_r0()
        run["unexpected"] = "x"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(run, _schema())

    def test_bad_sha256_is_rejected(self) -> None:
        run = _valid_r0()
        run["artifacts"][0]["sha256"] = "not-a-digest"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(run, _schema())

    def test_zero_added_mass_is_rejected(self) -> None:
        run = _valid_r1()
        run["added_mass"]["added_mass_g"] = 0
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(run, _schema())


class TestNoQualificationOrPromotionField:
    """P05/P10 at the schema level: the record cannot express qualification.

    additionalProperties:false everywhere means there is no field a run could
    set to promote a component to qualified or to declare PCB/production
    readiness. The absence is the guarantee.
    """

    @pytest.mark.parametrize(
        "field",
        [
            "qualified",
            "hardware_qualified",
            "pcb_ready",
            "production_ready",
            "capability_promoted",
        ],
    )
    def test_promotion_fields_are_unrepresentable(self, field: str) -> None:
        run = _valid_r0()
        run[field] = True
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(run, _schema())


class TestRegistryWiring:
    def test_registered_with_matching_const_and_file(self) -> None:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        entry = registry["schemas"]["ttp_prototype_run"]
        assert entry["schema_version_const"] == "ttp_prototype_run_v1"
        assert (REPO_ROOT / entry["path"]).exists()
        assert entry["file"] == SCHEMA_PATH.name

    def test_owner_lists_the_schema(self) -> None:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        owner = registry["schemas"]["ttp_prototype_run"]["owner"]
        assert "ttp_prototype_run" in registry["owners"][owner]["schemas"]
