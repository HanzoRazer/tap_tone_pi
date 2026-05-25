# INSTRUMENT CLASS: MEASUREMENT
"""
CLI integration for limit/mask testing.

Phase 3.5: Adds --limits and --limits-preset flags to analysis commands.

Usage:
    ttp record --out ./s1 --limits-preset tonewood_tap
    ttp measure --out ./s1 --limits my_limits.json
    ttp quick --limits-preset speaker_response
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from tap_tone_pi.core.analysis import AnalysisResult


def add_limits_args(parser: argparse.ArgumentParser) -> None:
    """
    Add --limits and --limits-preset arguments to a parser.

    Args:
        parser: ArgumentParser to add arguments to
    """
    limits_group = parser.add_argument_group("limit testing")
    limits_group.add_argument(
        "--limits",
        type=str,
        default=None,
        metavar="FILE",
        help="JSON file with limit curves to test against",
    )
    limits_group.add_argument(
        "--limits-preset",
        type=str,
        default=None,
        metavar="NAME",
        choices=["tonewood_tap", "speaker_response", "noise_floor"],
        help="Built-in limit preset (tonewood_tap, speaker_response, noise_floor)",
    )
    limits_group.add_argument(
        "--limits-fail",
        action="store_true",
        dest="limits_fail",
        help="Exit with error if limits are violated (default: warn only)",
    )
    limits_group.add_argument(
        "--limits-json",
        action="store_true",
        dest="limits_json",
        help="Output limit test results as JSON",
    )


def load_limits_config(args: argparse.Namespace) -> dict | None:
    """
    Load limits configuration from args.

    Args:
        args: Parsed arguments with --limits or --limits-preset

    Returns:
        Limits config dict or None if no limits specified
    """
    from tap_tone_pi.limits.presets import BUILTIN_PRESETS

    # Check for preset first
    if getattr(args, "limits_preset", None):
        preset_name = args.limits_preset
        if preset_name not in BUILTIN_PRESETS:
            raise ValueError(f"Unknown preset: {preset_name}")
        # Return raw dict, not parsed objects
        return BUILTIN_PRESETS[preset_name]

    # Check for custom limits file
    if getattr(args, "limits", None):
        limits_path = Path(args.limits)
        if not limits_path.exists():
            raise FileNotFoundError(f"Limits file not found: {limits_path}")
        return json.loads(limits_path.read_text(encoding="utf-8"))

    return None


def run_limit_test(
    analysis: "AnalysisResult",
    limits_config: dict,
    verbose: bool = True,
    as_json: bool = False,
) -> tuple[bool, str]:
    """
    Run limit test on analysis result.

    Args:
        analysis: AnalysisResult with spectrum data
        limits_config: Limits configuration dict
        verbose: Print detailed output
        as_json: Return JSON instead of formatted text

    Returns:
        Tuple of (passed, output_string)
    """
    from tap_tone_pi.limits import (
        LimitCurve,
        FrequencyMask,
        MaskRegion,
        check_against_limits,
    )

    # Build limit curves from config
    limits = []
    for limit_data in limits_config.get("limits", []):
        limits.append(LimitCurve.from_dict(limit_data))

    # Build mask if present
    mask = None
    mask_data = limits_config.get("mask")
    if mask_data:
        regions = [
            MaskRegion(
                freq_min_hz=r["freq_min_hz"],
                freq_max_hz=r["freq_max_hz"],
                reason=r.get("reason", "masked"),
            )
            for r in mask_data.get("regions", [])
        ]
        mask = FrequencyMask(
            name=mask_data.get("name", "custom_mask"),
            regions=regions,
        )

    # Get spectrum data
    if analysis.spectrum_freq_hz is None or analysis.spectrum_mag is None:
        return True, "No spectrum data available for limit testing."

    frequencies = np.array(analysis.spectrum_freq_hz)
    # Convert magnitude to dB
    magnitudes_db = 20 * np.log10(np.array(analysis.spectrum_mag) + 1e-10)

    # Run limit test
    result = check_against_limits(
        frequencies_hz=frequencies,
        values_db=magnitudes_db,
        limits=limits,
        mask=mask,
    )

    # Format output
    if as_json:
        output = json.dumps(result.to_dict(), indent=2)
    else:
        output = format_limit_test_cli(result, limits_config, verbose)

    return result.passed, output


def format_limit_test_cli(
    result,
    limits_config: dict,
    verbose: bool = True,
) -> str:
    """
    Format limit test result for CLI output.

    Args:
        result: LimitTestResult
        limits_config: Original config for context
        verbose: Include detailed violation list

    Returns:
        Formatted string
    """
    lines = []

    # Header
    preset_name = limits_config.get("name", "Custom Limits")
    lines.append(f"\n{'─' * 50}")
    lines.append(f"Limit Test: {preset_name}")
    lines.append(f"{'─' * 50}")

    # Verdict with color hint
    verdict = result.verdict.value.upper()
    if result.passed:
        lines.append(f"Result: ✓ {verdict}")
    else:
        lines.append(f"Result: ✗ {verdict}")

    # Summary stats
    lines.append(f"Points tested: {result.points_tested}")
    if result.points_masked > 0:
        lines.append(f"Points masked: {result.points_masked}")

    if result.worst_margin_db != float("inf"):
        margin_str = f"{result.worst_margin_db:+.1f} dB"
        lines.append(f"Worst margin: {margin_str}")

    # Violations
    if result.violations:
        lines.append(f"\nViolations: {len(result.violations)}")
        if verbose:
            for v in result.violations[:10]:  # Show first 10
                lines.append(
                    f"  {v.frequency_hz:7.1f} Hz: {v.measured_db:+.1f} dB "
                    f"(limit: {v.limit_db:+.1f} dB, {v.limit_type.value})"
                )
            if len(result.violations) > 10:
                lines.append(f"  ... and {len(result.violations) - 10} more")

    lines.append(f"{'─' * 50}\n")

    return "\n".join(lines)


def handle_limit_test_result(
    passed: bool,
    output: str,
    fail_on_violation: bool = False,
) -> int:
    """
    Handle limit test result - print output and return exit code.

    Args:
        passed: Whether test passed
        output: Formatted output string
        fail_on_violation: Return non-zero exit code on failure

    Returns:
        Exit code (0 = pass, 1 = fail if fail_on_violation)
    """
    print(output)

    if not passed and fail_on_violation:
        return 1
    return 0


__all__ = [
    "add_limits_args",
    "load_limits_config",
    "run_limit_test",
    "format_limit_test_cli",
    "handle_limit_test_result",
]
