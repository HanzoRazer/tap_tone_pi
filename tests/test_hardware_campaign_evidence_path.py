"""The whole evidence path, end to end, with a rejected run in it.

This exists because contract and unit tests were twice insufficient for this
part of the system. `sequence_index` reached the contract, the schema, the
validator, and the report — and was silently dropped by the ingestion function
on both the valid and the rejected path, because every test built its runs
directly instead of going through ingestion. A manifest would have recorded an
acquisition order that never reached the evidence, with no error anywhere.

DO-104 makes this a pre-merge gate for every hardware-facing increment. The path
under test is the real one:

    input manifest → ingestion → run record → study → campaign → report → checker

**At least one rejected run must traverse it**, because that is the branch where
the dropped field would otherwise disappear again: a rejected run takes a
different construction path than a valid one, and it is exactly the run whose
place in the sequence matters most.

Nothing here is hardware. The origin is FIXTURE throughout, and the assertions
below include that the documents say so.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")

REPO_ROOT = Path(__file__).resolve().parents[1]
UTC = "2026-09-01T14:00:00+00:00"
FREQUENCIES = [100.0, 200.0, 300.0, 400.0]


def load_script(name: str):
    """Import a campaign script by path, the way an operator runs it."""
    path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def transfer_document(magnitude: float, *, schema_version: str | None = None) -> dict:
    return {
        "schema_version": schema_version or "phase2_ods_snapshot_v2",
        "capdir": "runs_phase2/2026-09-01",
        "freqs_hz": list(FREQUENCIES),
        "points": [
            {
                "point_id": "P1",
                "x_mm": 0.0,
                "y_mm": 0.0,
                "H_mag": [0.001, magnitude, 0.002, 0.0015],
                "H_phase_deg": [-5.0, -30.0, -120.0, -160.0],
                "coherence": [0.80, 0.97, 0.95, 0.60],
                "n_averages": 8,
            }
        ],
    }


def at(minute: int) -> str:
    return f"2026-09-01T14:{minute:02d}:00+00:00"


@pytest.fixture
def campaign(tmp_path) -> dict:
    """A campaign laid out the way an operator would lay one out on disk."""
    transfers = tmp_path / "transfers"
    transfers.mkdir()

    # Three captures that the document supports, and one that it does not: the
    # fourth carries a foreign contract version and becomes a rejected run.
    for index, magnitude in enumerate([0.0040, 0.0041, 0.0039], start=1):
        (transfers / f"t{index}.json").write_text(
            json.dumps(transfer_document(magnitude)), encoding="utf-8"
        )
    (transfers / "t4.json").write_text(
        json.dumps(transfer_document(0.0042, schema_version="phase2_ods_snapshot_v1")),
        encoding="utf-8",
    )

    config = {
        "campaign_id": "camp-path",
        "created_at": UTC,
        "operator_id": "operator-1",
        "interface_id": "iface-2ch",
        "sample_rate_hz": 48000,
        "excitation": {
            "excitation_method": "shaker_stinger",
            "excitation_device_id": "shaker-TBD",
            "stinger_id": "stinger-TBD",
            "contact_tip_id": "tip-TBD",
            "rig_configuration_id": "rig-path",
            "stinger_mass_g": 1.42,
            "contact_tip_mass_g": 0.31,
            "combined_contact_mass_g": 0.90,
        },
        "support_condition": "free-free on foam",
        "channels": [
            {
                "channel_index": 0,
                "role": "EXCITATION",
                "quantity": "force",
                "unit": "N",
                "sensor_id": "force-TBD",
            },
            {
                "channel_index": 1,
                "role": "RESPONSE",
                "quantity": "acoustic_pressure",
                "unit": "Pa",
                "sensor_id": "mic-TBD",
            },
        ],
        "environmental_context": {
            "temp_c": None,
            "rh_pct": None,
            "specimen_moisture_pct": None,
            "ambient_noise_note": None,
        },
        "experiments": [
            {
                "experiment_id": "e2-path",
                "kind": "FIXED_POINT",
                "instrument_id": "ref-plate-1",
                "measurement_point_id": "P1",
                "planned_repeat_count": 4,
                "evaluation_frequency_hz": 205.0,
            }
        ],
        "notes": ["Fixture rehearsal. No hardware exists."],
    }
    (tmp_path / "campaign.json").write_text(json.dumps(config), encoding="utf-8")

    manifest = {
        "experiment_id": "e2-path",
        "runs": [
            {
                "run_id": f"e2-{index:03d}",
                "sequence_index": index - 1,
                "transfer": f"transfers/t{index}.json",
                "captured_at": at(index),
                "measurement_point_id": "P1",
                "evaluation_frequency_hz": 205.0,
                "session_id": "sess-path",
                "acquisition_id": f"acq-{index:03d}",
                "raw_artifact_ids": [f"art-e2-{index:03d}"],
            }
            for index in (1, 2, 3, 4)
        ],
    }
    (tmp_path / "runs.json").write_text(json.dumps(manifest), encoding="utf-8")

    artifacts = {
        "artifacts": [
            {
                "artifact_id": f"art-e2-{index:03d}",
                "kind": "raw_audio",
                "sha256": f"{index:064d}",
                "byte_count": 1234,
                "media_type": "audio/wav",
                "storage_locator": f"campaigns/camp-path/raw/e2-{index:03d}.wav",
                "capture_run_id": f"e2-{index:03d}",
                "repository_tracked": False,
                "local_path_hint": None,
            }
            for index in (1, 2, 3, 4)
        ]
    }
    (tmp_path / "artifacts.json").write_text(json.dumps(artifacts), encoding="utf-8")

    out = tmp_path / "out"
    campaign_script = load_script("ttp_hardware_campaign")

    assert (
        campaign_script.main(
            [
                "fixed-point",
                "--config",
                str(tmp_path / "campaign.json"),
                "--experiment",
                "e2-path",
                "--runs",
                str(tmp_path / "runs.json"),
                "--evidence-origin",
                "FIXTURE",
                "--output-dir",
                str(out),
                "--write",
            ]
        )
        == 0
    )
    assert (
        campaign_script.main(
            [
                "report",
                "--config",
                str(tmp_path / "campaign.json"),
                "--studies",
                str(out),
                "--artifacts",
                str(tmp_path / "artifacts.json"),
                "--output-dir",
                str(out),
                "--write",
            ]
        )
        == 0
    )

    return {
        "dir": out,
        "study": json.loads((out / "study-e2-path.json").read_text(encoding="utf-8")),
        "study_md": (out / "study-e2-path.md").read_text(encoding="utf-8"),
        "campaign": json.loads(
            (out / "ttp_hardware_campaign.json").read_text(encoding="utf-8")
        ),
        "campaign_md": (out / "ttp_hardware_campaign.md").read_text(encoding="utf-8"),
    }


class TestThePathRuns:
    def test_the_checker_accepts_what_the_scripts_wrote(self, campaign):
        checker = load_script("ttp_hardware_campaign_check")
        assert checker.main([str(campaign["dir"])]) == 0

    def test_every_attempt_reached_the_study(self, campaign):
        study = campaign["study"]["study"]
        assert len(study["runs"]) == 4
        assert study["valid_run_count"] == 3
        assert study["rejected_run_count"] == 1

    def test_the_rejected_run_names_its_reason(self, campaign):
        rejected = [r for r in campaign["study"]["study"]["runs"] if not r["valid"]]
        assert len(rejected) == 1
        assert rejected[0]["rejection_reason"] == "INVALID_METADATA"


class TestNothingIsLostInTransit:
    def test_the_acquisition_order_survives_every_stage(self, campaign):
        runs = campaign["study"]["study"]["runs"]
        assert [r["sequence_index"] for r in runs] == [0, 1, 2, 3]

    def test_the_rejected_run_keeps_its_place_in_the_order(self, campaign):
        # The branch that lost it before. A failed attempt still happened, and
        # it happened somewhere in the sequence.
        rejected = next(r for r in campaign["study"]["study"]["runs"] if not r["valid"])
        assert rejected["sequence_index"] == 3

    def test_the_order_reaches_the_rendered_report(self, campaign):
        assert "## Acquisition sequence" in campaign["study_md"]
        assert "| 3 | `e2-004` | no |" in campaign["study_md"]

    def test_the_frequency_asked_for_survives_every_stage(self, campaign):
        valid = next(r for r in campaign["study"]["study"]["runs"] if r["valid"])
        features = {f["quantity"]: f["value"] for f in valid["observed_features"]}
        assert features["nominal_evaluation_frequency"] == 205.0
        assert features["evaluation_frequency"] == 200.0
        assert features["frequency_offset"] == pytest.approx(-5.0)

    def test_the_rig_masses_survive_every_stage(self, campaign):
        excitation = campaign["study"]["study"]["experiment_definition"]["excitation"]
        assert excitation["stinger_mass_g"] == 1.42
        assert excitation["contact_tip_mass_g"] == 0.31
        # Lower than the sum of the parts, and accepted: the combined figure is
        # the effective mass at the interface, not their arithmetic sum.
        assert excitation["combined_contact_mass_g"] == 0.90

    def test_the_raw_artifacts_survive_into_the_campaign(self, campaign):
        artifacts = campaign["campaign"]["campaign"]["artifacts"]
        assert {a["artifact_id"] for a in artifacts} == {
            f"art-e2-{i:03d}" for i in (1, 2, 3, 4)
        }


class TestThePathCannotOverstate:
    def test_the_campaign_says_it_ran_against_fixture_data(self, campaign):
        assert campaign["campaign"]["execution_status"] == "FIXTURE_EXECUTED"
        assert campaign["campaign"]["is_hardware_evidence"] is False

    def test_the_report_says_it_is_not_hardware_evidence(self, campaign):
        assert "**No hardware evidence.**" in campaign["campaign_md"]
        assert "not hardware" in campaign["campaign_md"].lower()

    def test_no_capability_is_promoted(self, campaign):
        assert "This report promotes nothing" in campaign["campaign_md"]
        assert campaign["campaign"]["witnessed_experiment_ids"] == []

    def test_the_documents_validate_against_their_contracts(self, campaign):
        for name, payload in (
            ("ttp_preliminary_repeatability_study_v1", campaign["study"]["study"]),
            ("ttp_hardware_campaign_v1", campaign["campaign"]["campaign"]),
        ):
            schema = json.loads(
                (REPO_ROOT / "contracts" / f"{name}.schema.json").read_text(
                    encoding="utf-8"
                )
            )
            jsonschema.validate(payload, schema)


class TestTheCheckerStillCatchesTampering:
    def test_a_relabelled_campaign_is_refused(self, campaign):
        # The path being green must not mean the checker stopped looking.
        path = campaign["dir"] / "ttp_hardware_campaign.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["campaign"]["outcomes"][0]["evidence_origin"] = "HARDWARE"
        document["campaign"]["outcomes"][0]["witnessed"] = True
        path.write_text(json.dumps(document), encoding="utf-8")

        checker = load_script("ttp_hardware_campaign_check")
        assert checker.main([str(campaign["dir"])]) == 1
