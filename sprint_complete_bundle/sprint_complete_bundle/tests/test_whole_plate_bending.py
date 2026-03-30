"""
tests/test_whole_plate_bending.py

Tests for Sprint WPM: whole-plate bending measurement additions to merge_and_moe.

Coverage:
  - _calculate_moe: plate-width correction factor arithmetic
  - _calculate_moe: strip mode (no correction) unchanged
  - _calculate_moe: full_plate without --poisson (no correction applied)
  - _calculate_moe: full_plate with --poisson 0.35 (0.878 factor)
  - _calculate_moe: Poisson 0.30 and 0.40 boundary values
  - _calculate_moe: output dict contains new fields
  - E_plate_corrected_Pa always <= E_corrected_Pa for full_plate
  - CLI: --specimen-type, --poisson, --grain-orientation accepted without error
  - CLI: strip default produces no plate correction
  - CLI: full_plate + --poisson writes corrected value to bending_moe.json
  - CLI: full_plate without --poisson produces no correction
  - CLI: --grain-orientation stored in geometry output
  - config/devices/manual_entry.json exists and is valid JSON
  - manual_entry.json contains all three CLI example keys
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pytest

from tap_tone_pi.bending.merge_and_moe import _calculate_moe


# ── Fixtures ──────────────────────────────────────────────────────────────────

# Realistic strip inputs — Sitka spruce along-grain, 400mm span, 20mm wide, 3.0mm thick
STRIP_KWARGS: Dict[str, Any] = {
    "method": "3point",
    "slope_N_per_mm": 23.5,   # ~11 GPa realistic
    "span_mm": 400.0,
    "width_mm": 20.0,
    "thickness_mm": 3.0,
}

# Full plate — same span, waist width 200mm
PLATE_KWARGS: Dict[str, Any] = {
    "method": "3point",
    "slope_N_per_mm": 23.5,
    "span_mm": 400.0,
    "width_mm": 200.0,
    "thickness_mm": 3.0,
}

POISSON_SPRUCE = 0.35
EXPECTED_FACTOR = 1.0 - POISSON_SPRUCE ** 2   # 0.8775


def _make_load_json(tmp: Path) -> Path:
    data = {"unit": "N", "data": [[i, i * 4.905] for i in range(6)]}
    p = tmp / "load.json"
    p.write_text(json.dumps(data))
    return p


def _make_disp_json(tmp: Path, deflection_per_step: float = 0.41) -> Path:
    data = {"unit": "mm", "data": [[i, i * deflection_per_step] for i in range(6)]}
    p = tmp / "disp.json"
    p.write_text(json.dumps(data))
    return p


# ═════════════════════════════════════════════════════════════════════════════
# _calculate_moe: plate-width correction arithmetic
# ═════════════════════════════════════════════════════════════════════════════

class TestCalculateMOEPlateCorrection:

    def test_strip_no_correction_by_default(self):
        result = _calculate_moe(**STRIP_KWARGS)
        assert result["plate_width_correction_applied"] is False
        assert result["plate_width_correction_factor"] == pytest.approx(1.0)
        assert result["poisson_ratio_used"] is None

    def test_strip_with_poisson_still_no_correction(self):
        """Strip specimen never gets plate correction even if Poisson supplied."""
        result = _calculate_moe(**STRIP_KWARGS, poisson_ratio=0.35, specimen_type="strip")
        assert result["plate_width_correction_applied"] is False

    def test_full_plate_without_poisson_no_correction(self):
        result = _calculate_moe(**PLATE_KWARGS, specimen_type="full_plate", poisson_ratio=None)
        assert result["plate_width_correction_applied"] is False
        assert result["E_plate_corrected_Pa"] == pytest.approx(result["E_corrected_Pa"])

    def test_full_plate_with_poisson_applies_correction(self):
        result = _calculate_moe(**PLATE_KWARGS, specimen_type="full_plate", poisson_ratio=POISSON_SPRUCE)
        assert result["plate_width_correction_applied"] is True
        assert result["plate_width_correction_factor"] == pytest.approx(EXPECTED_FACTOR, rel=1e-5)

    def test_correction_factor_arithmetic_0_35(self):
        result = _calculate_moe(**PLATE_KWARGS, specimen_type="full_plate", poisson_ratio=0.35)
        expected = 1.0 - 0.35 ** 2
        assert result["plate_width_correction_factor"] == pytest.approx(expected, rel=1e-6)

    def test_correction_factor_arithmetic_0_30(self):
        result = _calculate_moe(**PLATE_KWARGS, specimen_type="full_plate", poisson_ratio=0.30)
        expected = 1.0 - 0.30 ** 2   # 0.91
        assert result["plate_width_correction_factor"] == pytest.approx(expected, rel=1e-6)

    def test_correction_factor_arithmetic_0_40(self):
        result = _calculate_moe(**PLATE_KWARGS, specimen_type="full_plate", poisson_ratio=0.40)
        expected = 1.0 - 0.40 ** 2   # 0.84
        assert result["plate_width_correction_factor"] == pytest.approx(expected, rel=1e-6)

    def test_plate_corrected_less_than_apparent(self):
        """After correction E_plate_corrected < E_corrected (correction always reduces)."""
        result = _calculate_moe(**PLATE_KWARGS, specimen_type="full_plate", poisson_ratio=0.35)
        assert result["E_plate_corrected_Pa"] < result["E_corrected_Pa"]

    def test_plate_corrected_equals_apparent_times_factor(self):
        result = _calculate_moe(**PLATE_KWARGS, specimen_type="full_plate", poisson_ratio=0.35)
        expected = result["E_corrected_Pa"] * result["plate_width_correction_factor"]
        assert result["E_plate_corrected_Pa"] == pytest.approx(expected, rel=1e-9)

    def test_poisson_stored_in_output(self):
        result = _calculate_moe(**PLATE_KWARGS, specimen_type="full_plate", poisson_ratio=0.35)
        assert result["poisson_ratio_used"] == pytest.approx(0.35)

    def test_new_fields_present_in_strip_output(self):
        result = _calculate_moe(**STRIP_KWARGS)
        for key in ("E_plate_corrected_Pa", "plate_width_correction_applied",
                    "plate_width_correction_factor", "poisson_ratio_used"):
            assert key in result, f"Missing key: {key}"

    def test_existing_fields_still_present(self):
        """Regression: original output fields must survive the patch."""
        result = _calculate_moe(**STRIP_KWARGS)
        for key in ("E_euler_bernoulli_Pa", "E_corrected_Pa", "l_over_h",
                    "shear_correction_applied", "shear_correction_factor",
                    "shear_correction_percent"):
            assert key in result, f"Existing field missing: {key}"


# ═════════════════════════════════════════════════════════════════════════════
# CLI integration — subprocess tests
# ═════════════════════════════════════════════════════════════════════════════

class TestCLIWholePlate:
    """End-to-end CLI tests writing to a temp directory."""

    def _run(self, *extra_args, deflection=0.41):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            load = _make_load_json(tmp)
            disp = _make_disp_json(tmp, deflection)
            cmd = [
                sys.executable, "-m", "tap_tone_pi.bending.merge_and_moe",
                "--load", str(load),
                "--disp", str(disp),
                "--out-dir", str(tmp),
                "--method", "3point",
                "--span", "400",
                "--width", "20",
                "--thickness", "3.0",
            ] + list(extra_args)
            result = subprocess.run(cmd, capture_output=True, text=True)
            moe_path = tmp / "bending_moe.json"
            moe_data = json.loads(moe_path.read_text()) if moe_path.exists() else {}
            return result, moe_data

    def test_strip_default_exits_zero(self):
        proc, _ = self._run()
        assert proc.returncode == 0, proc.stderr

    def test_strip_no_plate_correction_in_output(self):
        _, data = self._run()
        assert data["plate_width_correction"]["applied"] is False

    def test_full_plate_with_poisson_exits_zero(self):
        proc, _ = self._run("--specimen-type", "full_plate", "--poisson", "0.35",
                             "--width", "200")
        assert proc.returncode == 0, proc.stderr

    def test_full_plate_with_poisson_correction_applied(self):
        _, data = self._run("--specimen-type", "full_plate", "--poisson", "0.35",
                             "--width", "200")
        assert data["plate_width_correction"]["applied"] is True
        factor = data["plate_width_correction"]["factor"]
        assert abs(factor - (1.0 - 0.35 ** 2)) < 1e-4

    def test_full_plate_without_poisson_no_correction(self):
        _, data = self._run("--specimen-type", "full_plate", "--width", "200")
        assert data["plate_width_correction"]["applied"] is False

    def test_grain_orientation_longitudinal_stored(self):
        _, data = self._run("--grain-orientation", "longitudinal")
        assert data["geometry"]["grain_orientation"] == "longitudinal"

    def test_grain_orientation_cross_stored(self):
        _, data = self._run("--grain-orientation", "cross")
        assert data["geometry"]["grain_orientation"] == "cross"

    def test_specimen_type_stored_in_geometry(self):
        _, data = self._run("--specimen-type", "full_plate", "--width", "200")
        assert data["geometry"]["specimen_type"] == "full_plate"

    def test_e_gpa_lower_with_plate_correction(self):
        """Primary E_GPa must be lower for full_plate than strip (same slope)."""
        _, strip_data = self._run()
        _, plate_data = self._run("--specimen-type", "full_plate",
                                  "--poisson", "0.35", "--width", "200")
        # full_plate with correction should produce lower E
        assert plate_data["E_GPa"] < strip_data["E_GPa"]

    def test_r2_present_in_output(self):
        _, data = self._run()
        assert "r2" in data["fit"]
        assert data["fit"]["r2"] > 0.0


# ═════════════════════════════════════════════════════════════════════════════
# config/devices/manual_entry.json
# ═════════════════════════════════════════════════════════════════════════════

class TestManualEntryConfig:

    CONFIG_PATH = Path("config/devices/manual_entry.json")

    def test_file_exists(self):
        assert self.CONFIG_PATH.exists(), "config/devices/manual_entry.json is missing"

    def test_valid_json(self):
        data = json.loads(self.CONFIG_PATH.read_text())
        assert isinstance(data, dict)

    def test_contains_strip_along_grain_example(self):
        data = json.loads(self.CONFIG_PATH.read_text())
        assert "cli_example_strip_along_grain" in data

    def test_contains_strip_cross_grain_example(self):
        data = json.loads(self.CONFIG_PATH.read_text())
        assert "cli_example_strip_cross_grain" in data

    def test_contains_full_plate_example(self):
        data = json.loads(self.CONFIG_PATH.read_text())
        assert "cli_example_full_plate" in data

    def test_full_plate_example_includes_poisson(self):
        data = json.loads(self.CONFIG_PATH.read_text())
        assert "--poisson" in data["cli_example_full_plate"]

    def test_full_plate_example_includes_specimen_type(self):
        data = json.loads(self.CONFIG_PATH.read_text())
        assert "full_plate" in data["cli_example_full_plate"]

    def test_load_format_has_example(self):
        data = json.loads(self.CONFIG_PATH.read_text())
        assert "example" in data["load_series_format"]
        assert data["load_series_format"]["example"]["unit"] == "N"

    def test_displacement_format_has_example(self):
        data = json.loads(self.CONFIG_PATH.read_text())
        assert "example" in data["displacement_series_format"]
        assert data["displacement_series_format"]["example"]["unit"] == "mm"
