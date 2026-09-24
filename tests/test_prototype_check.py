"""P01-P10 invariant tests for the TTP-PROTOTYPE-001 prototype-run checker.

The invariants are the claim boundary of the prototype track: what a run may
say against what it carries. Each test drives the real validator
(:func:`validate_prototype_run`) on a well-formed base record perturbed one way,
and one test drives the read-only ``scripts/ttp_prototype_check.py`` end to end.

None of this judges a physical quantity — no resonance, no "enough" movement,
no force magnitude. TTP-PROTOTYPE-001 forbids inventing those thresholds; these
checks only hold a record to what it is entitled to claim.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tap_tone_pi.prototype import (
    promotion_notes,
    validate_prototype_run,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKER = REPO_ROOT / "scripts" / "ttp_prototype_check.py"


def _codes(run: dict) -> list[str]:
    return [finding.code for finding in validate_prototype_run(run)]


def _r0() -> dict:
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
        "limitations": ["prototype"],
    }


def _r1() -> dict:
    run = _r0()
    run.update(run_id="r1-001", stage="R1")
    run["added_mass"] = {"mass_challenge_id": "m1", "added_mass_g": 1.98}
    return run


def _r2() -> dict:
    run = _r0()
    run.update(run_id="r2-001", stage="R2")
    run["excitation"] = {
        "excitation_mode": "COMMANDED",
        "excitation_method": "stepped_sine_sweep",
        "commanded_amplitude": 0.5,
        "output_device_id": "pulse-out",
        "amplifier_id": "AMP-CAND",
        "exciter_id": "EX-CAND",
        "emission_provenance": {"emitted_signal_id": "sig-1"},
    }
    return run


class TestValidBaselines:
    def test_r0_r1_r2_baselines_are_clean(self) -> None:
        assert _codes(_r0()) == []
        assert _codes(_r1()) == []
        assert _codes(_r2()) == []


class TestP01_R0_CannotClaimControlledExcitation:
    def test_commanded_mode_on_r0_is_a_finding(self) -> None:
        run = _r0()
        run["excitation"]["excitation_mode"] = "COMMANDED"
        assert "PROTO_STAGE_EXCITATION_CONFLICT" in _codes(run)

    def test_commanded_amplitude_on_r0_is_a_finding(self) -> None:
        run = _r0()
        run["excitation"]["commanded_amplitude"] = 0.5
        assert "PROTO_STAGE_EXCITATION_CONFLICT" in _codes(run)

    def test_controlled_chain_on_r0_is_a_finding(self) -> None:
        run = _r0()
        run["excitation"]["exciter_id"] = "EX-CAND"
        assert "PROTO_STAGE_EXCITATION_CONFLICT" in _codes(run)

    def test_emission_provenance_on_r0_is_a_finding(self) -> None:
        run = _r0()
        run["excitation"]["emission_provenance"] = {"emitted_signal_id": "sig-x"}
        assert "PROTO_STAGE_EXCITATION_CONFLICT" in _codes(run)


class TestP02_R1_RequiresActualAddedMass:
    def test_missing_added_mass_is_a_finding(self) -> None:
        run = _r1()
        run.pop("added_mass")
        assert "PROTO_ADDED_MASS_MISSING" in _codes(run)

    def test_nonpositive_added_mass_is_a_finding(self) -> None:
        run = _r1()
        run["added_mass"]["added_mass_g"] = 0
        assert "PROTO_ADDED_MASS_MISSING" in _codes(run)

    def test_measured_added_mass_is_accepted(self) -> None:
        assert _codes(_r1()) == []


class TestP03_R2_RequiresEmissionProvenance:
    def test_missing_emission_provenance_is_a_finding(self) -> None:
        run = _r2()
        run["excitation"].pop("emission_provenance")
        assert "PROTO_EMISSION_PROVENANCE_MISSING" in _codes(run)

    def test_missing_output_device_is_a_finding(self) -> None:
        run = _r2()
        run["excitation"]["output_device_id"] = None
        assert "PROTO_EMISSION_PROVENANCE_MISSING" in _codes(run)

    def test_manual_mode_on_r2_is_a_finding(self) -> None:
        run = _r2()
        run["excitation"]["excitation_mode"] = "MANUAL"
        assert "PROTO_STAGE_EXCITATION_CONFLICT" in _codes(run)


class TestP04_NoMeasuredForceWithoutForceChain:
    def test_force_claim_without_chain_is_a_finding(self) -> None:
        run = _r2()
        run["force"] = {"measured_force_claimed": True, "force_chain": None}
        assert "PROTO_FORCE_CLAIM_UNSUBSTANTIATED" in _codes(run)

    def test_commanded_amplitude_is_not_a_force_claim(self) -> None:
        # A commanded electrical amplitude must never, by itself, read as force.
        assert _codes(_r2()) == []
        assert _r2()["force"]["measured_force_claimed"] is False

    def test_traceable_chain_without_reference_is_a_finding(self) -> None:
        run = _r2()
        run["force"] = {
            "measured_force_claimed": True,
            "force_chain": {
                "force_sensor_id": "FORCE-1",
                "calibration_traceability": "TRACEABLE",
                "calibration_reference": None,
            },
        }
        assert "PROTO_FORCE_CLAIM_UNSUBSTANTIATED" in _codes(run)

    def test_force_claim_with_complete_chain_is_accepted(self) -> None:
        run = _r2()
        run["force"] = {
            "measured_force_claimed": True,
            "force_chain": {
                "force_sensor_id": "FORCE-1",
                "calibration_traceability": "NOMINAL",
                "calibration_reference": None,
            },
        }
        assert _codes(run) == []


class TestP05_CandidateIsNotQualified:
    def test_checker_notes_never_qualify_a_component(self) -> None:
        notes = " ".join(promotion_notes()).lower()
        assert "does not qualify" in notes
        # The validator has no code that grants qualification.
        for run in (_r0(), _r1(), _r2()):
            assert not any("QUALIF" in code.upper() for code in _codes(run))


class TestP06_FixtureOrSyntheticIsNotWitnessed:
    def test_witnessed_over_fixture_is_a_finding(self) -> None:
        run = _r0()
        run["evidence_origin"] = "FIXTURE"
        assert "PROTO_WITNESS_WITHOUT_HARDWARE" in _codes(run)

    def test_witnessed_over_synthetic_is_a_finding(self) -> None:
        run = _r0()
        run["evidence_origin"] = "SYNTHETIC"
        assert "PROTO_WITNESS_WITHOUT_HARDWARE" in _codes(run)

    def test_unwitnessed_fixture_run_is_accepted(self) -> None:
        run = _r0()
        run["evidence_origin"] = "FIXTURE"
        run["witnessed"] = False
        run["artifacts"] = []  # a fixture run need not retain hardware artifacts
        assert _codes(run) == []


class TestP07_GuidanceDoesNotChangeResult:
    def test_notes_do_not_change_findings(self) -> None:
        clean = _r0()
        annotated = _r0()
        annotated["notes"] = ["operator felt this was a great tap", "sounds resonant"]
        assert _codes(clean) == _codes(annotated)

    def test_notes_do_not_rescue_a_failing_run(self) -> None:
        run = _r0()
        run["evidence_origin"] = "FIXTURE"  # witnessed over fixture -> P06 finding
        run["notes"] = ["operator attests this is really hardware"]
        assert "PROTO_WITNESS_WITHOUT_HARDWARE" in _codes(run)


class TestP08_FailedRunIsRecorded:
    def test_halted_without_reason_is_a_finding(self) -> None:
        run = _r0()
        run["status"] = "HALTED_AT_GATE"
        run["evidence_origin"] = None
        run["witnessed"] = False
        run["artifacts"] = []
        assert "PROTO_HALT_WITHOUT_REASON" in _codes(run)

    def test_halted_with_reason_is_a_complete_record(self) -> None:
        run = _r0()
        run["status"] = "HALTED_AT_GATE"
        run["evidence_origin"] = None
        run["witnessed"] = False
        run["artifacts"] = []
        run["halt_reason"] = "amplifier overheated; stopped per bench protocol"
        assert _codes(run) == []


class TestP09_HardwareRunRetainsArtifacts:
    def test_hardware_run_without_artifact_is_a_finding(self) -> None:
        run = _r0()
        run["artifacts"] = []
        assert "PROTO_HARDWARE_WITHOUT_ARTIFACT" in _codes(run)

    def test_malformed_artifact_is_a_finding(self) -> None:
        run = _r0()
        run["artifacts"][0]["sha256"] = "short"
        assert any(code.startswith("PROTO_") for code in _codes(run))
        assert _codes(run) != []


class TestP10_NoAutomaticPromotion:
    def test_promotion_notes_state_non_promotion(self) -> None:
        notes = " ".join(promotion_notes()).lower()
        assert "does not promote" in notes
        assert "pcb" in notes or "production" in notes

    def test_no_finding_code_grants_readiness(self) -> None:
        for run in (_r0(), _r1(), _r2()):
            for code in _codes(run):
                assert "PROMOTE" not in code.upper()
                assert "READY" not in code.upper()


class TestExecutedRunNeedsOrigin:
    def test_executed_without_origin_is_a_finding(self) -> None:
        run = _r0()
        run["evidence_origin"] = None
        run["witnessed"] = False
        assert "PROTO_EXECUTED_WITHOUT_ORIGIN" in _codes(run)

    def test_not_executed_with_origin_is_a_finding(self) -> None:
        run = _r0()
        run["status"] = "NOT_EXECUTED"
        run["witnessed"] = False
        assert "PROTO_NOT_EXECUTED_CLAIMS_ORIGIN" in _codes(run)


class TestCheckerCli:
    def _run(self, tmp_path: Path, record: dict) -> subprocess.CompletedProcess:
        path = tmp_path / "ttp_prototype_run.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(CHECKER), str(path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    def test_cli_accepts_a_clean_run(self, tmp_path: Path) -> None:
        result = self._run(tmp_path, _r2())
        assert result.returncode == 0, result.stderr
        assert "internally consistent" in result.stdout

    def test_cli_rejects_a_bad_run_and_reports_it(self, tmp_path: Path) -> None:
        bad = _r0()
        bad["evidence_origin"] = "FIXTURE"  # witnessed over fixture
        result = self._run(tmp_path, bad)
        assert result.returncode == 1
        assert "PROTO_WITNESS_WITHOUT_HARDWARE" in result.stderr

    def test_cli_reads_a_directory(self, tmp_path: Path) -> None:
        (tmp_path / "ttp_prototype_run.json").write_text(
            json.dumps(_r1()), encoding="utf-8"
        )
        result = subprocess.run(
            [sys.executable, str(CHECKER), str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, result.stderr
