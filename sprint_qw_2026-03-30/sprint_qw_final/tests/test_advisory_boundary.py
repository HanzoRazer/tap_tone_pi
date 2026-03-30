"""
test_advisory_boundary.py — Tests for ci/check_advisory_boundary.py

Verifies the three check functions in isolation:
  1. check_declarations — flags missing INSTRUMENT CLASS banners
  2. check_export_isolation — flags advisory imports in export pipeline
  3. check_no_advisory_in_instrument_core — flags advisory imports in measurement modules

All tests use tmp_path for hermetic filesystem isolation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Allow running from repo root
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from ci.check_advisory_boundary import (
    BoundaryReport,
    Finding,
    check_declarations,
    check_export_isolation,
    check_no_advisory_in_instrument_core,
    DECLARATION_REQUIRED_DIRS,
    KNOWN_ADVISORY_MODULES,
    main,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _make_py(path: Path, content: str = "") -> Path:
    return _write(path, f'"""\nModule docstring.\n"""\n\n{content}\n')


# ---------------------------------------------------------------------------
# check_declarations
# ---------------------------------------------------------------------------

class TestCheckDeclarations:

    def test_measurement_declaration_passes(self, tmp_path: Path) -> None:
        src = tmp_path / "tap_tone_pi" / "core" / "analysis.py"
        _write(src, '"""\nCore analysis.\n"""\n\n# INSTRUMENT CLASS: MEASUREMENT\n\nx = 1\n')

        report = BoundaryReport()
        check_declarations(report, tmp_path)
        adry001 = [f for f in report.findings if f.code == "ADRY-001"]
        assert len(adry001) == 0

    def test_decision_support_declaration_passes(self, tmp_path: Path) -> None:
        src = tmp_path / "tap_tone_pi" / "wolf" / "wolf_advisor.py"
        _write(src, '"""\nWolf advisor.\n"""\n\n# INSTRUMENT CLASS: DECISION SUPPORT\n\nx = 1\n')

        report = BoundaryReport()
        check_declarations(report, tmp_path)
        adry001 = [f for f in report.findings if f.code == "ADRY-001"]
        assert len(adry001) == 0

    def test_missing_declaration_warns(self, tmp_path: Path) -> None:
        src = tmp_path / "tap_tone_pi" / "core" / "fft.py"
        _write(src, '"""\nFFT module.\n"""\n\ndef compute(): pass\n')

        report = BoundaryReport()
        check_declarations(report, tmp_path)
        adry001 = [f for f in report.findings if f.code == "ADRY-001"]
        assert len(adry001) == 1
        assert "tap_tone_pi/core/fft.py" in adry001[0].file or \
               "tap_tone_pi\\core\\fft.py" in adry001[0].file

    def test_unknown_class_warns(self, tmp_path: Path) -> None:
        src = tmp_path / "tap_tone_pi" / "core" / "fft.py"
        _write(src, '"""\nFFT module.\n"""\n\n# INSTRUMENT CLASS: ADVISORY\n\nx = 1\n')

        report = BoundaryReport()
        check_declarations(report, tmp_path)
        adry002 = [f for f in report.findings if f.code == "ADRY-002"]
        assert len(adry002) == 1

    def test_test_files_skipped(self, tmp_path: Path) -> None:
        """Test files should not require declarations."""
        src = tmp_path / "tap_tone_pi" / "core" / "test_fft.py"
        _write(src, "def test_something(): pass\n")

        report = BoundaryReport()
        check_declarations(report, tmp_path)
        assert len(report.findings) == 0

    def test_init_files_skipped(self, tmp_path: Path) -> None:
        """__init__.py stubs should not require declarations."""
        src = tmp_path / "tap_tone_pi" / "core" / "__init__.py"
        _write(src, "# empty\n")

        report = BoundaryReport()
        check_declarations(report, tmp_path)
        assert len(report.findings) == 0

    def test_multiple_files_multiple_warnings(self, tmp_path: Path) -> None:
        for name in ["fft.py", "peaks.py", "analysis.py"]:
            src = tmp_path / "tap_tone_pi" / "core" / name
            _make_py(src)

        report = BoundaryReport()
        check_declarations(report, tmp_path)
        adry001 = [f for f in report.findings if f.code == "ADRY-001"]
        assert len(adry001) == 3


# ---------------------------------------------------------------------------
# check_export_isolation
# ---------------------------------------------------------------------------

class TestCheckExportIsolation:

    def test_clean_export_file_passes(self, tmp_path: Path) -> None:
        export_py = tmp_path / "tap_tone_pi" / "export" / "pack.py"
        _write(export_py, (
            "import json\n"
            "from pathlib import Path\n"
            "from tap_tone_pi.core.analysis import analyze_tap\n"
        ))

        report = BoundaryReport()
        # Override EXPORT_PIPELINE_FILES to point to tmp
        import ci.check_advisory_boundary as mod
        orig = mod.EXPORT_PIPELINE_FILES
        mod.EXPORT_PIPELINE_FILES = ["tap_tone_pi/export/pack.py"]
        try:
            check_export_isolation(report, tmp_path)
        finally:
            mod.EXPORT_PIPELINE_FILES = orig

        adry010 = [f for f in report.findings if f.code == "ADRY-010"]
        assert len(adry010) == 0

    def test_advisory_import_in_export_is_error(self, tmp_path: Path) -> None:
        export_py = tmp_path / "tap_tone_pi" / "export" / "pack.py"
        _write(export_py, (
            "from tap_tone_pi.wolf.wolf_advisor import generate_wolf_directive\n"
            "from tap_tone_pi.core.analysis import analyze_tap\n"
        ))

        report = BoundaryReport()
        import ci.check_advisory_boundary as mod
        orig = mod.EXPORT_PIPELINE_FILES
        mod.EXPORT_PIPELINE_FILES = ["tap_tone_pi/export/pack.py"]
        try:
            check_export_isolation(report, tmp_path)
        finally:
            mod.EXPORT_PIPELINE_FILES = orig

        adry010 = [f for f in report.findings if f.code == "ADRY-010"]
        assert len(adry010) == 1
        assert report.errors  # Must be an error, not just a warning

    def test_wood_properties_import_in_export_is_error(self, tmp_path: Path) -> None:
        export_py = tmp_path / "scripts" / "export_pack.py"
        _write(export_py, (
            "from analyzer.analysis.wood_properties import estimate_wood_properties\n"
        ))

        report = BoundaryReport()
        import ci.check_advisory_boundary as mod
        orig = mod.EXPORT_PIPELINE_FILES
        mod.EXPORT_PIPELINE_FILES = ["scripts/export_pack.py"]
        try:
            check_export_isolation(report, tmp_path)
        finally:
            mod.EXPORT_PIPELINE_FILES = orig

        adry010 = [f for f in report.findings if f.code == "ADRY-010"]
        assert len(adry010) == 1


# ---------------------------------------------------------------------------
# check_no_advisory_in_instrument_core
# ---------------------------------------------------------------------------

class TestCheckNoAdvisoryInCore:

    def test_clean_core_passes(self, tmp_path: Path) -> None:
        core_py = tmp_path / "tap_tone_pi" / "core" / "analysis.py"
        _write(core_py, (
            "import numpy as np\n"
            "from scipy.signal import find_peaks\n"
        ))

        report = BoundaryReport()
        check_no_advisory_in_instrument_core(report, tmp_path)
        assert len(report.findings) == 0

    def test_advisory_in_core_is_error(self, tmp_path: Path) -> None:
        core_py = tmp_path / "tap_tone_pi" / "core" / "analysis.py"
        _write(core_py, (
            "import numpy as np\n"
            "from tap_tone_pi.wolf.wolf_advisor import WolfAdvisor\n"
        ))

        report = BoundaryReport()
        check_no_advisory_in_instrument_core(report, tmp_path)
        adry011 = [f for f in report.findings if f.code == "ADRY-011"]
        assert len(adry011) == 1
        assert report.errors

    def test_advisory_in_calibration_is_error(self, tmp_path: Path) -> None:
        cal_py = tmp_path / "tap_tone_pi" / "calibration" / "session.py"
        _write(cal_py, (
            "from tap_tone_pi.wolf import wolf_advisor\n"
        ))

        report = BoundaryReport()
        check_no_advisory_in_instrument_core(report, tmp_path)
        adry011 = [f for f in report.findings if f.code == "ADRY-011"]
        assert len(adry011) == 1

    def test_advisory_in_bending_is_error(self, tmp_path: Path) -> None:
        bend_py = tmp_path / "tap_tone_pi" / "bending" / "moe.py"
        _write(bend_py, (
            "import tap_tone_pi.wolf.wolf_advisor as wa\n"
        ))

        report = BoundaryReport()
        check_no_advisory_in_instrument_core(report, tmp_path)
        assert report.errors


# ---------------------------------------------------------------------------
# main() exit codes
# ---------------------------------------------------------------------------

class TestMainExitCodes:

    def test_clean_repo_exits_zero(self, tmp_path: Path) -> None:
        """Empty tmp_path has no violations — should exit 0."""
        rc = main(["--report-only"])
        # report-only always exits 0
        assert rc == 0

    def test_report_only_always_exits_zero(self, tmp_path: Path, monkeypatch) -> None:
        import ci.check_advisory_boundary as mod

        # Patch repo root to tmp_path so no real violations are found
        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(mod, "EXPORT_PIPELINE_FILES", [])

        rc = main(["--report-only"])
        assert rc == 0
