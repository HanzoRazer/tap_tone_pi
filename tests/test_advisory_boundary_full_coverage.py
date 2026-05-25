# INSTRUMENT CLASS: MEASUREMENT
"""
Regression lock test for advisory boundary full coverage.

Ensures all modules have INSTRUMENT CLASS declarations and no
advisory vocabulary violations, preventing backlog regrowth.

Run with: pytest tests/test_advisory_boundary_full_coverage.py -v
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


class TestAdvisoryBoundaryFullCoverage:
    """Regression tests for advisory boundary compliance."""

    def test_strict_mode_passes(self) -> None:
        """Verify check_advisory_boundary.py --strict exits 0.

        This test locks in full declaration coverage and prevents
        backlog regrowth. If a new module is added without an
        INSTRUMENT CLASS declaration, this test will fail.
        """
        project_root = Path(__file__).resolve().parents[1]
        check_script = project_root / "ci" / "check_advisory_boundary.py"

        result = subprocess.run(
            [sys.executable, str(check_script), "--strict"],
            capture_output=True,
            text=True,
            cwd=project_root,
        )

        # Assert exit code 0 (no warnings or errors)
        assert result.returncode == 0, (
            f"Advisory boundary check failed in strict mode.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}\n"
            f"\n"
            f"To fix: Add '# INSTRUMENT CLASS: MEASUREMENT' or "
            f"'# INSTRUMENT CLASS: DECISION SUPPORT' to each flagged module.\n"
            f"See docs/ADR-0009-advisory-boundary.md for classification guidance."
        )

    def test_no_undeclared_modules(self) -> None:
        """Verify no ADRY-001 warnings (missing declarations)."""
        project_root = Path(__file__).resolve().parents[1]
        check_script = project_root / "ci" / "check_advisory_boundary.py"

        result = subprocess.run(
            [sys.executable, str(check_script), "--strict"],
            capture_output=True,
            text=True,
            cwd=project_root,
        )

        # Check for ADRY-001 in output
        output = result.stdout + result.stderr
        adry001_count = output.count("ADRY-001")

        assert adry001_count == 0, (
            f"Found {adry001_count} module(s) missing INSTRUMENT CLASS declaration.\n"
            f"Run: python ci/check_advisory_boundary.py --strict\n"
            f"to see which modules need declarations."
        )

    def test_no_advisory_vocabulary_violations(self) -> None:
        """Verify no ADRY-002 errors (advisory vocabulary in MEASUREMENT modules)."""
        project_root = Path(__file__).resolve().parents[1]
        check_script = project_root / "ci" / "check_advisory_boundary.py"

        result = subprocess.run(
            [sys.executable, str(check_script), "--strict"],
            capture_output=True,
            text=True,
            cwd=project_root,
        )

        # Check for ADRY-002 in output
        output = result.stdout + result.stderr
        adry002_count = output.count("ADRY-002")

        assert adry002_count == 0, (
            f"Found {adry002_count} advisory vocabulary violation(s) in MEASUREMENT modules.\n"
            f"Run: python ci/check_advisory_boundary.py --strict\n"
            f"to see which modules have violations.\n"
            f"Either remove advisory vocabulary or reclassify as DECISION SUPPORT."
        )
