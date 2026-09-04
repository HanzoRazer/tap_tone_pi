"""Exciter drive-budget arithmetic (DO-108P).

The utility does two divisions. What these tests actually hold is the boundary
around them: a number in newtons produced by ``BL x Irms`` is a motor-force
scale, not force delivered to the specimen, and the commercial excitation path
has no force channel to make it one. A calculator that let that distinction slip
would be the shortest route to a force claim nobody measured.

The second thing held here is that a missing value stays missing. VISATON does
not publish a BL for the EX 30 S, and the honest output for that is
``UNAVAILABLE`` — never zero, and never a figure derived from the parameters
that happen to be printed.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_budget():
    path = REPO_ROOT / "scripts" / "exciter_drive_budget.py"
    spec = importlib.util.spec_from_file_location("exciter_drive_budget", path)
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def budget():
    return load_budget()


class TestArithmetic:
    def test_one_volt_into_four_ohms(self, budget):
        result = budget.drive_budget(load_ohm=4.0, vrms=1.0)
        assert result["irms_a"] == pytest.approx(0.25)
        assert result["electrical_power_w"] == pytest.approx(0.25)

    def test_two_volts_into_four_ohms(self, budget):
        result = budget.drive_budget(load_ohm=4.0, vrms=2.0)
        assert result["irms_a"] == pytest.approx(0.5)
        assert result["electrical_power_w"] == pytest.approx(1.0)

    def test_the_visaton_load_is_supported_too(self, budget):
        # 8 ohm nominal. The requirement covers both candidate loads, so the
        # calculator must not be written around 4 ohms.
        result = budget.drive_budget(load_ohm=8.0, vrms=2.0)
        assert result["irms_a"] == pytest.approx(0.25)
        assert result["electrical_power_w"] == pytest.approx(0.5)

    def test_zero_output_is_a_legitimate_condition(self, budget):
        result = budget.drive_budget(load_ohm=4.0, vrms=0.0)
        assert result["irms_a"] == 0.0
        assert result["electrical_power_w"] == 0.0


class TestMotorForceScale:
    def test_the_coin_exciter_at_half_an_amp(self, budget):
        # DAEX25CT-4, BL 1.54 Tm (manufacturer). 2 Vrms into 4 ohms is 0.5 A.
        result = budget.drive_budget(load_ohm=4.0, vrms=2.0, bl_tm=1.54)
        assert result["irms_a"] == pytest.approx(0.5)
        assert result["motor_force_scale_n"] == pytest.approx(0.77)

    def test_the_framed_exciter_at_half_an_amp(self, budget):
        # DAEX25FHE-4, BL 3.63 Tm (manufacturer).
        result = budget.drive_budget(load_ohm=4.0, vrms=2.0, bl_tm=3.63)
        assert result["motor_force_scale_n"] == pytest.approx(1.815)

    def test_the_higher_bl_candidate_develops_more_motor_force(self, budget):
        # True of the motor, and deliberately not a conclusion about plates.
        ct = budget.drive_budget(load_ohm=4.0, vrms=2.0, bl_tm=1.54)
        fhe = budget.drive_budget(load_ohm=4.0, vrms=2.0, bl_tm=3.63)
        assert fhe["motor_force_scale_n"] > ct["motor_force_scale_n"]

    def test_the_output_never_calls_it_specimen_force(self, budget):
        result = budget.drive_budget(load_ohm=4.0, vrms=2.0, bl_tm=1.54)
        assert result["specimen_force_n"] == "NOT_MEASURED"
        assert "not force delivered to the specimen" in result["caveat"]

    def test_the_text_output_carries_the_caveat(self, budget):
        text = budget.format_text(
            budget.drive_budget(load_ohm=4.0, vrms=2.0, bl_tm=1.54)
        )
        assert "motor-force scale" in text
        assert "Motor-force scale is not force delivered to the specimen" in text
        assert "force at the plate    NOT_MEASURED" in text

    def test_the_caveat_survives_when_bl_is_absent(self, budget):
        # The caveat is not conditional on there being a number to qualify.
        text = budget.format_text(budget.drive_budget(load_ohm=8.0, vrms=2.0))
        assert "Motor-force scale is not force delivered to the specimen" in text

    def test_no_acceleration_is_derived_from_moving_mass(self, budget):
        # BL*I/Mms would be the acceleration of an exciter driving nothing, and
        # this one is coupled to a plate whose impedance is unknown.
        result = budget.drive_budget(
            load_ohm=4.0, vrms=2.0, bl_tm=1.54, moving_mass_g=1.29
        )
        assert result["moving_mass_g"] == pytest.approx(1.29)
        assert result["acceleration_scale"] == "NOT_DERIVED"


class TestMissingValuesStayMissing:
    def test_absent_bl_yields_unavailable_not_zero(self, budget):
        # The VISATON case: 8 ohms, 10 W, and no published BL.
        result = budget.drive_budget(load_ohm=8.0, vrms=2.0)
        assert result["motor_force_scale_n"] == "UNAVAILABLE"
        assert result["motor_force_scale_n"] != 0
        assert result["bl_tm"] is None

    def test_absent_bl_still_reports_the_electrical_quantities(self, budget):
        # The drive-side arithmetic does not depend on BL, and withholding it
        # would make an unpublished motor parameter hide a known current.
        result = budget.drive_budget(load_ohm=8.0, vrms=2.0)
        assert result["irms_a"] == pytest.approx(0.25)
        assert result["electrical_power_w"] == pytest.approx(0.5)

    def test_a_zero_bl_is_refused_rather_than_used(self, budget):
        with pytest.raises(budget.InvalidDrive, match="not a measurement"):
            budget.drive_budget(load_ohm=4.0, vrms=2.0, bl_tm=0.0)


class TestRejectedInputs:
    def test_negative_resistance_is_rejected(self, budget):
        with pytest.raises(budget.InvalidDrive, match="greater than zero"):
            budget.drive_budget(load_ohm=-4.0, vrms=2.0)

    def test_zero_resistance_is_rejected(self, budget):
        with pytest.raises(budget.InvalidDrive, match="greater than zero"):
            budget.drive_budget(load_ohm=0.0, vrms=2.0)

    def test_negative_voltage_is_rejected(self, budget):
        with pytest.raises(budget.InvalidDrive, match="magnitude"):
            budget.drive_budget(load_ohm=4.0, vrms=-2.0)

    def test_negative_moving_mass_is_rejected(self, budget):
        with pytest.raises(budget.InvalidDrive):
            budget.drive_budget(load_ohm=4.0, vrms=2.0, moving_mass_g=-1.0)

    def test_the_cli_reports_a_bad_input_rather_than_a_traceback(self, budget, capsys):
        code = budget.main(["--load-ohm", "0", "--vrms", "2"])
        assert code == 2
        assert "invalid drive condition" in capsys.readouterr().err


class TestOutputIsDeterministic:
    def test_repeated_json_output_is_identical(self, budget, capsys):
        argv = ["--load-ohm", "4", "--vrms", "2", "--bl", "1.54", "--json"]
        budget.main(argv)
        first = capsys.readouterr().out
        budget.main(argv)
        second = capsys.readouterr().out
        assert first == second

    def test_the_json_carries_no_timestamp_or_environment(self, budget, capsys):
        budget.main(["--load-ohm", "4", "--vrms", "2", "--json"])
        payload = json.loads(capsys.readouterr().out)
        for volatile in ("timestamp", "generated_at", "utc", "host", "user"):
            assert not any(volatile in key.lower() for key in payload)

    def test_the_json_carries_the_caveat(self, budget, capsys):
        budget.main(["--load-ohm", "4", "--vrms", "2", "--bl", "1.54", "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert "not force delivered to the specimen" in payload["caveat"]
        assert payload["specimen_force_n"] == "NOT_MEASURED"

    def test_the_json_reports_unavailable_as_a_string_not_null(self, budget, capsys):
        # null would invite a downstream reader to coalesce it to 0.
        budget.main(["--load-ohm", "8", "--vrms", "2", "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["motor_force_scale_n"] == "UNAVAILABLE"


class TestTheUtilityIsNotEvidence:
    def test_it_writes_nothing(self):
        source = (REPO_ROOT / "scripts" / "exciter_drive_budget.py").read_text(
            encoding="utf-8"
        )
        for marker in ("write_text(", "mkdir(", "unlink(", "open("):
            assert marker not in source

    def test_it_recommends_and_infers_nothing(self, budget):
        source = (REPO_ROOT / "scripts" / "exciter_drive_budget.py").read_text(
            encoding="utf-8"
        )
        for marker in ("def recommend", "def suggest", "def infer", "def select"):
            assert marker not in source
