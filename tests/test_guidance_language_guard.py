# INSTRUMENT CLASS: MEASUREMENT
"""Tests for guidance language authority guard.

Validates:
- Clean advisory text passes
- Forbidden terms are detected in user-facing strings
- --strict exits nonzero
- Default mode exits zero with findings
- Exemption marker suppresses findings
- Missing target directory is ignored
- AST extraction focuses on strings, not comments
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


GUARD_SCRIPT = Path(__file__).parent.parent / "ci" / "check_guidance_language.py"


def run_guard(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run the guidance language guard with given arguments."""
    cmd = [sys.executable, str(GUARD_SCRIPT)] + list(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


class TestGuidanceLanguageGuard:
    """Tests for check_guidance_language.py."""

    def test_clean_file_passes(self, tmp_path: Path):
        """Clean advisory text with no forbidden terms passes."""
        module = tmp_path / "clean_module.py"
        module.write_text('''
"""Advisory module with clean language."""

def suggest_review():
    """Suggest user review a potential anomaly."""
    return {
        "summary": "Possible drift observed in frequency spectrum",
        "detail": "May indicate environmental change. Consider checking.",
    }
''')
        result = run_guard(str(module))
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_forbidden_term_detected(self, tmp_path: Path):
        """Forbidden authority term in string is detected."""
        module = tmp_path / "bad_module.py"
        module.write_text("""
def generate_directive():
    return {
        "summary": "Wolf tone confirmed at 247Hz",
    }
""")
        result = run_guard(str(module))
        assert "confirmed" in result.stdout.lower()
        assert "finding" in result.stdout.lower()

    def test_strict_mode_fails_on_finding(self, tmp_path: Path):
        """--strict mode exits 1 when findings exist."""
        module = tmp_path / "bad_module.py"
        module.write_text("""
summary = "Issue diagnosed and resolved"
""")
        result = run_guard("--strict", str(module))
        assert result.returncode == 1
        assert "FAIL" in result.stdout

    def test_default_mode_warns_but_passes(self, tmp_path: Path):
        """Default mode exits 0 even with findings."""
        module = tmp_path / "bad_module.py"
        module.write_text("""
message = "This is the optimal solution"
""")
        result = run_guard(str(module))
        assert result.returncode == 0
        assert "WARN" in result.stdout
        assert "optimal" in result.stdout.lower()

    def test_exemption_marker_suppresses_finding(self, tmp_path: Path):
        """EXEMPT marker causes file to be skipped."""
        module = tmp_path / "exempt_module.py"
        module.write_text('''
# EXEMPT: guidance_language_guard
# This file tests forbidden language detection

def test_forbidden_terms():
    """Test that 'confirmed' and 'validated' are detected."""
    forbidden = "confirmed validated optimal"
    return forbidden
''')
        result = run_guard("--strict", str(module))
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_missing_directory_ignored(self, tmp_path: Path):
        """Missing target directory does not cause error."""
        missing = tmp_path / "nonexistent_dir"
        result = run_guard(str(missing))
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_internal_comments_not_scanned(self, tmp_path: Path):
        """Internal comments are not scanned (AST extracts strings only)."""
        module = tmp_path / "commented_module.py"
        module.write_text("""
# This is the best implementation (internal comment)
# Fixed bug in previous version (internal comment)

def clean_function():
    # optimal algorithm choice (internal comment)
    return "This suggestion may indicate drift"
""")
        result = run_guard("--strict", str(module))
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_docstring_is_scanned(self, tmp_path: Path):
        """Docstrings (user-facing) are scanned."""
        module = tmp_path / "docstring_module.py"
        module.write_text('''
def advisory_function():
    """This function returns the optimal recommendation."""
    return {}
''')
        result = run_guard(str(module))
        assert "optimal" in result.stdout.lower()

    def test_markdown_file_scanned(self, tmp_path: Path):
        """Markdown files are scanned when targeted."""
        doc = tmp_path / "guidance.md"
        doc.write_text("""
# Guidance Documentation

The system has verified the acoustic signature.
""")
        result = run_guard(str(doc))
        assert "verified" in result.stdout.lower()

    def test_multiple_findings_reported(self, tmp_path: Path):
        """Multiple forbidden terms in same file are all reported."""
        module = tmp_path / "multi_bad.py"
        module.write_text("""
summary1 = "Issue confirmed"
summary2 = "Solution validated"
summary3 = "This is optimal"
""")
        result = run_guard(str(module))
        assert "confirmed" in result.stdout.lower()
        assert "validated" in result.stdout.lower()
        assert "optimal" in result.stdout.lower()
        assert "3 finding" in result.stdout.lower()

    def test_case_insensitive_detection(self, tmp_path: Path):
        """Detection is case-insensitive."""
        module = tmp_path / "case_module.py"
        module.write_text("""
msg1 = "CONFIRMED issue"
msg2 = "Validated Result"
msg3 = "OPTIMAL choice"
""")
        result = run_guard(str(module))
        assert "confirmed" in result.stdout.lower()
        assert "validated" in result.stdout.lower()
        assert "optimal" in result.stdout.lower()


class TestGuidanceLanguageGuardIntegration:
    """Integration tests against real advisory modules."""

    def test_default_targets_exist(self):
        """Default target directories should exist."""
        for target in ["tap_tone_pi/agent", "tap_tone_pi/agentic", "tap_tone_pi/wolf"]:
            assert Path(target).exists(), f"Default target {target} should exist"

    def test_default_scan_runs_without_error(self):
        """Running with defaults should not crash."""
        result = run_guard()
        # May have findings, but should not crash
        assert result.returncode in (0, 1)
        assert "guidance_language" in result.stdout.lower()
