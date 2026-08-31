"""The read-only E0 acquisition report (DO-107B §15, §16).

The command reports; it decides nothing. Two properties are load-bearing and are
asserted rather than assumed.

**Not evidence-grade is not a failure.** The current TTP budget cannot be
evidence-grade while B-020 and B-021 are open, and a command that exited non-zero
for that would be reporting a verdict on the mathematics as though it were a
defect in the run.

**The reader can tell the five states apart.** Measured inputs, non-measured
inputs, unavailable sections, blocking conditions and advisories are different
things, and a report that ran them together would be the same collapse the
budget's own vocabulary exists to prevent.

No hardware, no device enumeration, no audio dependency.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "ttp_e0_acquisition.py"
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from ttp_e0_acquisition import main  # noqa: E402

from tap_tone_pi.uncertainty.acquisition import (  # noqa: E402
    build_acquisition_budget_from_e0,
)

from tests.test_e0_acquisition_adapter import (  # noqa: E402
    POINT,
    base_budget,
    executed,
)

ARGS = ["--sample-rate", "48000", "--pga-db", "-12", "--input-path", "unbalanced"]


@pytest.fixture
def record_path(tmp_path):
    path = tmp_path / "e0_adc_characterization.json"
    path.write_text(json.dumps(executed().to_dict(), indent=2), encoding="utf-8")
    return path


@pytest.fixture
def baseline_path(tmp_path):
    path = tmp_path / "baseline_acquisition_budget.json"
    path.write_text(
        json.dumps(base_budget().computed().as_dict(), indent=2), encoding="utf-8"
    )
    return path


class TestMappingReport:
    def test_it_reports_what_the_record_supplies(self, record_path, capsys):
        assert main([str(record_path), *ARGS]) == 0
        out = capsys.readouterr().out
        assert "MEASURED INPUTS" in out
        assert "converter.hp_corner_hz" in out
        assert "e0:E0-107B-A/T3/coupling#measured_corner_hz" in out

    def test_it_says_what_it_deliberately_did_not_consume(self, record_path, capsys):
        assert main([str(record_path), *ARGS]) == 0
        out = capsys.readouterr().out
        assert "E0 EVIDENCE THAT IS NOT A BUDGET INPUT" in out
        assert "T7 loopback" in out
        assert "T4 out_of_band" in out

    def test_json_mode_emits_the_mapping_audit(self, record_path, capsys):
        assert main([str(record_path), *ARGS, "--json"]) == 0
        audit = json.loads(capsys.readouterr().out)
        assert audit["characterization_id"] == "E0-107B-A"
        assert len([o for o in audit["outcomes"] if o["status"] == "consumed"]) == 3


class TestBudgetReport:
    def test_the_five_states_are_reported_apart(
        self, record_path, baseline_path, capsys
    ):
        assert main([str(record_path), *ARGS, "--budget", str(baseline_path)]) == 0
        out = capsys.readouterr().out
        for heading in (
            "MEASURED INPUTS",
            "NON-MEASURED INPUTS",
            "UNAVAILABLE SECTIONS",
            "BLOCKING CONDITIONS",
            "ADVISORIES",
        ):
            assert heading in out, heading

    def test_b020_and_b021_stay_visible(self, record_path, baseline_path, capsys):
        assert main([str(record_path), *ARGS, "--budget", str(baseline_path)]) == 0
        out = capsys.readouterr().out
        blocking = out.split("BLOCKING CONDITIONS", 1)[1].split("ADVISORIES", 1)[0]
        assert "[B-020]" in blocking
        assert "[B-021]" in blocking
        assert "evidence grade     false" in out

    def test_a_non_evidence_grade_budget_is_not_an_error(
        self, record_path, baseline_path, capsys
    ):
        code = main([str(record_path), *ARGS, "--budget", str(baseline_path)])
        capsys.readouterr()
        assert code == 0

    def test_it_reports_what_characterization_changed(
        self, record_path, baseline_path, capsys
    ):
        assert main([str(record_path), *ARGS, "--budget", str(baseline_path)]) == 0
        out = capsys.readouterr().out
        changed = out.split("WHAT CHARACTERIZATION CHANGED", 1)[1]
        assert "converter.thermal_snr_db" in changed
        assert "datasheet" in changed and "measured" in changed

    def test_json_mode_emits_the_canonical_budget(
        self, record_path, baseline_path, capsys
    ):
        assert (
            main([str(record_path), *ARGS, "--budget", str(baseline_path), "--json"])
            == 0
        )
        payload = json.loads(capsys.readouterr().out)
        expected = build_acquisition_budget_from_e0(
            base_budget(), executed(), POINT
        ).budget
        assert payload == expected.as_dict()
        assert payload["schema_version"] == "acquisition_budget_v1"

    def test_the_baseline_file_is_not_modified(
        self, record_path, baseline_path, capsys
    ):
        before = baseline_path.read_bytes()
        main([str(record_path), *ARGS, "--budget", str(baseline_path)])
        capsys.readouterr()
        assert baseline_path.read_bytes() == before


class TestRefusals:
    def test_an_unreadable_record_exits_one(self, tmp_path, capsys):
        path = tmp_path / "broken.json"
        path.write_text("{ not json", encoding="utf-8")
        assert main([str(path), *ARGS]) == 1
        assert "cannot read" in capsys.readouterr().err

    def test_a_record_that_fails_its_contract_exits_one(self, tmp_path, capsys):
        payload = executed().to_dict()
        payload["coupling"]["points"][0].pop("phase_deg")
        path = tmp_path / "e0.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        assert main([str(path), *ARGS]) == 1
        assert "contract:" in capsys.readouterr().err

    def test_a_prepared_record_is_refused_with_a_reason(self, tmp_path, capsys):
        from tap_tone_pi.grant_readiness.e0_characterization import (
            E0AdcCharacterizationV1,
            E0DeviceIdentityV1,
            E0ProvenanceV1,
        )

        prepared = E0AdcCharacterizationV1(
            characterization_id="E0-PREPARED",
            device=E0DeviceIdentityV1("ADC-001", "HiFiBerry", "DAC+ ADC Pro"),
            provenance=E0ProvenanceV1("2026-09-01T12:00:00Z", "Ross Echols"),
        )
        path = tmp_path / "e0.json"
        path.write_text(json.dumps(prepared.to_dict()), encoding="utf-8")
        assert main([str(path), *ARGS]) == 1
        assert "PREPARED" in capsys.readouterr().err

    def test_a_self_contradicting_baseline_is_refused(
        self, record_path, tmp_path, capsys
    ):
        payload = base_budget().computed().as_dict()
        payload["evidence"]["evidence_grade"] = True
        path = tmp_path / "baseline.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        assert main([str(record_path), *ARGS, "--budget", str(path)]) == 1
        assert "baseline:" in capsys.readouterr().err


class TestNoHardware:
    def test_the_command_enumerates_no_audio_device(self, record_path):
        """§29. Nothing on this path may touch PortAudio."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys, runpy\n"
                f"sys.argv = ['ttp_e0_acquisition.py', {str(record_path)!r}, "
                "'--sample-rate', '48000', '--pga-db', '-12']\n"
                f"runpy.run_path({str(SCRIPT)!r}, run_name='__main__')\n",
            ],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        assert result.returncode == 0, result.stderr
        assert "MEASURED INPUTS" in result.stdout

    def test_the_command_claims_no_authority_it_does_not_have(self):
        source = SCRIPT.read_text(encoding="utf-8")
        # No verb that would read as a decision about the hardware.
        for verb in ("--approve", "--certify", "--qualify", "--validate-hardware"):
            assert verb not in source
        assert "has no pass" in source
