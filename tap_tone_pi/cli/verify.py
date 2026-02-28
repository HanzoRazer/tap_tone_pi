"""
CLI commands for verification testing.

Usage:
    ttp verify                  # Run full verification suite
    ttp verify --quick          # Quick pass/fail check
    ttp verify --verbose        # Detailed output
    ttp verify --output report.json  # Save report to file
"""

from __future__ import annotations

import argparse
from pathlib import Path


def cmd_verify(args) -> int:
    """Run verification suite."""
    from tap_tone_pi.verify import (
        run_verification_suite,
        quick_verify,
        format_verification_report,
        save_verification_report,
    )

    # Quick mode
    if args.quick:
        print("Running quick verification...")
        success = quick_verify(sample_rate=args.sample_rate)
        if success:
            print("Verification: PASS")
            return 0
        else:
            print("Verification: FAIL")
            return 1

    # Full suite
    print("Running verification suite...")
    print("")

    result = run_verification_suite(
        sample_rate=args.sample_rate,
        verbose=args.verbose,
    )

    # Print formatted report
    report = format_verification_report(
        result,
        verbose=args.verbose,
        color=not args.no_color,
    )
    print(report)

    # Save to file if requested
    if args.output:
        output_path = Path(args.output)
        saved = save_verification_report(result, output_path)
        print(f"Report saved: {saved}")

    # JSON output mode
    if args.json:
        import json

        print(json.dumps(result.to_dict(), indent=2))

    return 0 if result.success else 1


def cmd_verify_frequency(args) -> int:
    """Verify frequency measurement at specific frequency."""
    from tap_tone_pi.signal_gen import generate_sine
    from tap_tone_pi.core.analysis import analyze_tap
    from tap_tone_pi.verify import verify_frequency_accuracy

    print(f"Generating {args.frequency:.1f} Hz test tone...")

    signal = generate_sine(
        frequency_hz=args.frequency,
        duration_s=args.duration,
        sample_rate=args.sample_rate,
        amplitude=0.7,
    )

    print("Analyzing...")
    result = analyze_tap(signal, args.sample_rate)

    if result.dominant_hz:
        test = verify_frequency_accuracy(
            measured_hz=result.dominant_hz,
            expected_hz=args.frequency,
            tolerance_cents=args.tolerance,
        )

        print(f"\nExpected: {args.frequency:.2f} Hz")
        print(f"Measured: {result.dominant_hz:.2f} Hz")
        print(f"Error: {test.details['cents_error']:.1f} cents")
        print(f"Result: {test.outcome.value.upper()}")

        return 0 if test.passed else 1
    else:
        print("No frequency detected!")
        return 1


def cmd_verify_amplitude(args) -> int:
    """Verify amplitude measurement."""
    import math
    import numpy as np
    from tap_tone_pi.signal_gen import generate_sine
    from tap_tone_pi.verify import verify_amplitude_accuracy

    print(f"Generating test tone at {args.amplitude:.2f} amplitude...")

    signal = generate_sine(
        frequency_hz=1000.0,
        duration_s=args.duration,
        sample_rate=args.sample_rate,
        amplitude=args.amplitude,
    )

    # Measure RMS
    rms = np.sqrt(np.mean(signal**2))
    measured_db = 20 * math.log10(rms + 1e-10)

    # Expected RMS for sine wave
    expected_rms = args.amplitude / math.sqrt(2)
    expected_db = 20 * math.log10(expected_rms)

    test = verify_amplitude_accuracy(
        measured_db=measured_db,
        expected_db=expected_db,
        tolerance_db=args.tolerance,
    )

    print(f"\nExpected: {expected_db:.2f} dB")
    print(f"Measured: {measured_db:.2f} dB")
    print(f"Error: {test.details['error_db']:.3f} dB")
    print(f"Result: {test.outcome.value.upper()}")

    return 0 if test.passed else 1


def add_verify_subcommand(subparsers) -> None:
    """Add the verify subcommand and its sub-subcommands."""
    verify_parser = subparsers.add_parser(
        "verify",
        help="Run verification tests",
        description="Run synthetic signal tests to verify the analysis pipeline.",
        epilog="""Examples:
  ttp verify                    # Run full suite
  ttp verify --quick            # Quick pass/fail
  ttp verify --verbose          # Detailed output
  ttp verify --output report.json  # Save report
  ttp verify frequency --freq 440  # Test specific frequency
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Main verify subcommands
    verify_sub = verify_parser.add_subparsers(dest="verify_cmd", help="Verify command")

    # Default behavior (no subcommand) - run full suite
    verify_parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick pass/fail check only",
    )
    verify_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output with details",
    )
    verify_parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Save report to JSON file",
    )
    verify_parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    verify_parser.add_argument(
        "-r",
        "--sample-rate",
        type=int,
        default=48000,
        help="Sample rate for test signals (default: 48000)",
    )
    verify_parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )
    verify_parser.set_defaults(func=cmd_verify)

    # Frequency subcommand
    freq_parser = verify_sub.add_parser(
        "frequency",
        help="Verify frequency measurement",
    )
    freq_parser.add_argument(
        "-f",
        "--frequency",
        type=float,
        default=440.0,
        help="Test frequency in Hz (default: 440)",
    )
    freq_parser.add_argument(
        "-t",
        "--tolerance",
        type=float,
        default=5.0,
        help="Tolerance in cents (default: 5)",
    )
    freq_parser.add_argument(
        "-d",
        "--duration",
        type=float,
        default=1.0,
        help="Signal duration in seconds (default: 1.0)",
    )
    freq_parser.add_argument(
        "-r",
        "--sample-rate",
        type=int,
        default=48000,
        help="Sample rate (default: 48000)",
    )
    freq_parser.set_defaults(func=cmd_verify_frequency)

    # Amplitude subcommand
    amp_parser = verify_sub.add_parser(
        "amplitude",
        help="Verify amplitude measurement",
    )
    amp_parser.add_argument(
        "-a",
        "--amplitude",
        type=float,
        default=0.5,
        help="Test amplitude 0-1 (default: 0.5)",
    )
    amp_parser.add_argument(
        "-t",
        "--tolerance",
        type=float,
        default=0.5,
        help="Tolerance in dB (default: 0.5)",
    )
    amp_parser.add_argument(
        "-d",
        "--duration",
        type=float,
        default=0.5,
        help="Signal duration in seconds (default: 0.5)",
    )
    amp_parser.add_argument(
        "-r",
        "--sample-rate",
        type=int,
        default=48000,
        help="Sample rate (default: 48000)",
    )
    amp_parser.set_defaults(func=cmd_verify_amplitude)
