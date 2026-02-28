"""
Verification report formatting and export.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from .tests import TestOutcome, VerificationTest
from .suite import VerificationResult


@dataclass
class VerificationReport:
    """
    Complete verification report with system information.
    """

    result: VerificationResult
    system_info: Dict[str, Any] = field(default_factory=dict)
    calibration_status: Optional[str] = None
    notes: str = ""

    def __post_init__(self):
        if not self.system_info:
            self.system_info = _get_system_info()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "schema_version": "verification_report_v1",
            "generated_at": datetime.now().isoformat(),
            "system_info": self.system_info,
            "calibration_status": self.calibration_status,
            "notes": self.notes,
            "result": self.result.to_dict(),
        }


def _get_system_info() -> Dict[str, Any]:
    """Gather system information for the report."""
    import platform
    import sys

    info = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "python_version": sys.version.split()[0],
        "machine": platform.machine(),
    }

    # Try to get tap_tone_pi version
    try:
        import tap_tone_pi

        info["tap_tone_pi_version"] = getattr(tap_tone_pi, "__version__", "unknown")
    except (ImportError, AttributeError):
        info["tap_tone_pi_version"] = "unknown"

    # Try to get numpy version
    try:
        import numpy

        info["numpy_version"] = numpy.__version__
    except (ImportError, AttributeError):
        pass

    # Try to get scipy version
    try:
        import scipy

        info["scipy_version"] = scipy.__version__
    except (ImportError, AttributeError):
        pass

    return info


def format_verification_report(
    result: VerificationResult,
    verbose: bool = False,
    color: bool = True,
) -> str:
    """
    Format verification result as human-readable text.

    Args:
        result: VerificationResult to format
        verbose: Include detailed test information
        color: Use ANSI color codes

    Returns:
        Formatted string
    """
    lines = []

    # Header
    lines.append("=" * 60)
    lines.append("Tap Tone Pi Verification Report")
    lines.append("=" * 60)
    lines.append("")

    # Summary
    status = "PASS" if result.success else "FAIL"
    if color:
        status_colored = f"\033[92m{status}\033[0m" if result.success else f"\033[91m{status}\033[0m"
    else:
        status_colored = status

    lines.append(f"Status: {status_colored}")
    lines.append(f"Timestamp: {result.timestamp}")
    lines.append(f"Duration: {result.duration_s:.2f}s")
    lines.append("")

    # Test counts
    lines.append(f"Tests: {result.total}")
    lines.append(f"  Passed:  {result.passed}")
    lines.append(f"  Failed:  {result.failed}")
    if result.skipped:
        lines.append(f"  Skipped: {result.skipped}")
    if result.errors:
        lines.append(f"  Errors:  {result.errors}")
    lines.append(f"  Success: {result.success_rate:.0%}")
    lines.append("")

    # Individual tests
    lines.append("-" * 60)
    lines.append("Test Results:")
    lines.append("-" * 60)

    for test in result.tests:
        # Format outcome with color
        outcome_str = test.outcome.value.upper()
        if color:
            if test.outcome == TestOutcome.PASS:
                outcome_colored = f"\033[92m{outcome_str:5}\033[0m"
            elif test.outcome == TestOutcome.FAIL:
                outcome_colored = f"\033[91m{outcome_str:5}\033[0m"
            elif test.outcome == TestOutcome.SKIP:
                outcome_colored = f"\033[93m{outcome_str:5}\033[0m"
            else:
                outcome_colored = f"\033[91m{outcome_str:5}\033[0m"
        else:
            outcome_colored = f"{outcome_str:5}"

        lines.append(f"  [{outcome_colored}] {test.name}")

        if verbose or test.outcome in (TestOutcome.FAIL, TestOutcome.ERROR):
            if test.message:
                lines.append(f"          {test.message}")
            if test.expected is not None:
                lines.append(f"          Expected: {test.expected}")
            if test.actual is not None:
                lines.append(f"          Actual:   {test.actual}")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


def save_verification_report(
    result: VerificationResult,
    filepath: Path | str,
    include_system_info: bool = True,
) -> Path:
    """
    Save verification report to JSON file.

    Args:
        result: VerificationResult to save
        filepath: Output file path
        include_system_info: Include system information

    Returns:
        Path to saved file
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if include_system_info:
        report = VerificationReport(result=result)
        data = report.to_dict()
    else:
        data = result.to_dict()

    # Atomic write
    tmp_path = filepath.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(data, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    tmp_path.replace(filepath)

    return filepath


def load_verification_report(filepath: Path | str) -> VerificationResult:
    """
    Load verification result from JSON file.

    Args:
        filepath: Path to JSON file

    Returns:
        VerificationResult
    """
    filepath = Path(filepath)
    data = json.loads(filepath.read_text(encoding="utf-8"))

    # Handle both report format and raw result format
    if "result" in data:
        result_data = data["result"]
    else:
        result_data = data

    # Reconstruct tests
    tests = []
    for t_data in result_data.get("tests", []):
        tests.append(
            VerificationTest(
                name=t_data["name"],
                outcome=TestOutcome(t_data["outcome"]),
                expected=t_data.get("expected"),
                actual=t_data.get("actual"),
                tolerance=t_data.get("tolerance"),
                message=t_data.get("message", ""),
                details=t_data.get("details", {}),
            )
        )

    return VerificationResult(
        tests=tests,
        duration_s=result_data.get("duration_s", 0),
        timestamp=result_data.get("timestamp", ""),
    )
