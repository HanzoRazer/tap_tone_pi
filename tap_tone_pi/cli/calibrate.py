# INSTRUMENT CLASS: MEASUREMENT
"""
CLI commands for self-calibration workflow.

Usage:
    ttp calibrate loopback    # Measure system frequency response
    ttp calibrate verify      # Verify with 1 kHz reference tone
    ttp calibrate status      # Show current calibration state
    ttp calibrate clear       # Remove stored calibration
"""

from __future__ import annotations

import argparse
from datetime import datetime


def cmd_calibrate_status(args: argparse.Namespace) -> int:
    """Show calibration status for device."""
    from tap_tone_pi.calibration import (
        get_calibration_status,
        load_calibration,
        is_calibration_stale,
        CalibrationStatus,
        CALIBRATION_EXPIRY_DAYS,
    )
    from tap_tone_pi.core.user_config import get_saved_device

    # Get device index
    device_index = args.device
    if device_index is None:
        saved = get_saved_device()
        if saved:
            device_index = saved.index
            print(f"Using saved device: [{device_index}] {saved.name}")
        else:
            print("No device specified and no saved device configuration.")
            print("Run 'ttp setup' first or specify --device.")
            return 1

    # Get status
    status = get_calibration_status(device_index)
    data = load_calibration(device_index)

    # Status display
    status_colors = {
        CalibrationStatus.VALID: "\033[92m",  # Green
        CalibrationStatus.STALE: "\033[93m",  # Yellow
        CalibrationStatus.UNCALIBRATED: "\033[91m",  # Red
        CalibrationStatus.FAILED: "\033[91m",  # Red
    }
    reset = "\033[0m"
    color = status_colors.get(status, "")

    print(f"\nCalibration Status: {color}{status.value.upper()}{reset}")

    if data:
        print(f"\nDevice: [{data.device_index}] {data.device_name}")
        print(f"Calibrated: {data.calibrated_at}")

        # Loopback test
        if data.loopback_completed:
            print("\nLoopback Test: PASSED")
            if data.loopback_latency_ms:
                print(f"  Latency: {data.loopback_latency_ms:.1f} ms")
            if data.loopback_snr_db:
                print(f"  SNR: {data.loopback_snr_db:.1f} dB")
            if data.frequency_response:
                print(f"  Frequency response: {len(data.frequency_response)} points")
        else:
            print("\nLoopback Test: NOT COMPLETED")

        # Reference tone test
        if data.reference_tone_completed:
            print("\nReference Tone Test: PASSED")
            if data.amplitude_error_db is not None:
                print(f"  Amplitude error: {data.amplitude_error_db:+.2f} dB")
        else:
            print("\nReference Tone Test: NOT COMPLETED")

        # Stale warning
        if is_calibration_stale(data):
            print(
                f"\n\033[93mWarning: Calibration is older than {CALIBRATION_EXPIRY_DAYS} days."
            )
            print(f"Consider re-running calibration for best accuracy.{reset}")

        if data.notes:
            print(f"\nNotes: {data.notes}")
    else:
        print("\nNo calibration data found for this device.")
        print("\nTo calibrate, run:")
        print("  ttp calibrate loopback    # Measure system response")
        print("  ttp calibrate verify      # Verify amplitude accuracy")

    print()
    return 0


def cmd_calibrate_loopback(args: argparse.Namespace) -> int:
    """Run loopback calibration test."""
    from tap_tone_pi.calibration import (
        LoopbackConfig,
        run_loopback_test,
        load_calibration,
        save_calibration,
        CalibrationData,
    )
    from tap_tone_pi.calibration.storage import FrequencyResponsePoint
    from tap_tone_pi.core.user_config import get_saved_device

    # Get device info
    device_index = args.device
    device_name = "Unknown"
    sample_rate = args.sample_rate or 48000

    if device_index is None:
        saved = get_saved_device()
        if saved:
            device_index = saved.index
            device_name = saved.name
            sample_rate = saved.sample_rate
            print(f"Using saved device: [{device_index}] {device_name}")
        else:
            print("No device specified and no saved device configuration.")
            print("Run 'ttp setup' first or specify --device.")
            return 1

    # Get device name if not from saved config
    if device_name == "Unknown":
        from tap_tone_pi.capture import list_devices

        devices = list_devices()
        for d in devices:
            if d["index"] == device_index:
                device_name = d["name"]
                break

    print("\n" + "=" * 60)
    print("LOOPBACK CALIBRATION TEST")
    print("=" * 60)
    print("\nThis test measures your system's frequency response.")
    print("Connect your output to your input using a loopback cable,")
    print("or use your existing setup if output feeds back to input.")

    if not args.yes:
        print("\nPress Enter to start, or Ctrl+C to cancel...")
        try:
            input()
        except KeyboardInterrupt:
            print("\nCancelled.")
            return 1

    # Configure test
    config = LoopbackConfig(
        sample_rate=sample_rate,
        duration_s=args.duration or 2.0,
    )

    print("\nRunning loopback test...")
    print(f"  Duration: {config.duration_s}s")
    print(f"  Frequency range: {config.freq_start_hz}-{config.freq_end_hz} Hz")

    # Create play_and_record function using audio subsystem
    play_and_record_fn = None

    if not args.simulate:
        try:
            from tap_tone_pi.capture import play_and_record

            def _play_record(signal, sr):
                return play_and_record(
                    signal, device_index, sr, timeout=config.duration_s + 1.0
                )

            play_and_record_fn = _play_record
        except ImportError:
            print("\nWarning: Audio capture not available. Running in simulation mode.")

    # Run test
    result = run_loopback_test(config, play_and_record_fn)

    if not result.success:
        print(f"\n\033[91mLoopback test FAILED: {result.error_message}\033[0m")
        return 1

    print("\n\033[92mLoopback test PASSED\033[0m")
    print(f"  Latency: {result.latency_ms:.1f} ms")
    print(f"  SNR: {result.snr_db:.1f} dB")
    print(f"  Frequency response: {len(result.frequency_response)} points")
    print(f"  Flatness (100-10kHz): {result.get_flatness_db(100, 10000):.1f} dB")

    # Load or create calibration data
    data = load_calibration(device_index)
    if data is None:
        data = CalibrationData(
            device_index=device_index,
            device_name=device_name,
            calibrated_at=datetime.now().isoformat(),
        )

    # Update with loopback results
    data.loopback_completed = True
    data.loopback_latency_ms = result.latency_ms
    data.loopback_snr_db = result.snr_db
    data.frequency_response = [
        FrequencyResponsePoint(
            freq_hz=p.freq_hz, magnitude_db=p.magnitude_db, phase_deg=p.phase_deg
        )
        for p in result.frequency_response
    ]
    data.calibrated_at = datetime.now().isoformat()

    if data.is_complete():
        data.status = "valid"
    else:
        data.status = "uncalibrated"

    # Save
    path = save_calibration(data)
    print(f"\nCalibration data saved to: {path}")

    if not data.reference_tone_completed:
        print("\nNext step: Run 'ttp calibrate verify' for amplitude verification.")

    return 0


def cmd_calibrate_verify(args: argparse.Namespace) -> int:
    """Run reference tone verification test."""
    from tap_tone_pi.calibration import (
        ReferenceToneConfig,
        run_reference_tone_test,
        load_calibration,
        save_calibration,
        CalibrationData,
    )
    from tap_tone_pi.core.user_config import get_saved_device

    # Get device info
    device_index = args.device
    device_name = "Unknown"
    sample_rate = args.sample_rate or 48000

    if device_index is None:
        saved = get_saved_device()
        if saved:
            device_index = saved.index
            device_name = saved.name
            sample_rate = saved.sample_rate
            print(f"Using saved device: [{device_index}] {device_name}")
        else:
            print("No device specified and no saved device configuration.")
            print("Run 'ttp setup' first or specify --device.")
            return 1

    # Get device name if not from saved config
    if device_name == "Unknown":
        from tap_tone_pi.capture import list_devices

        devices = list_devices()
        for d in devices:
            if d["index"] == device_index:
                device_name = d["name"]
                break

    print("\n" + "=" * 60)
    print("REFERENCE TONE VERIFICATION TEST")
    print("=" * 60)
    print("\nThis test verifies amplitude accuracy using a 1 kHz reference tone.")
    print("Connect your output to your input using a loopback cable,")
    print("or use your existing setup if output feeds back to input.")

    if not args.yes:
        print("\nPress Enter to start, or Ctrl+C to cancel...")
        try:
            input()
        except KeyboardInterrupt:
            print("\nCancelled.")
            return 1

    # Configure test
    config = ReferenceToneConfig(
        sample_rate=sample_rate,
        duration_s=args.duration or 2.0,
        amplitude_dbfs=args.level or -20.0,
    )

    print("\nRunning reference tone test...")
    print(f"  Frequency: {config.frequency_hz} Hz")
    print(f"  Level: {config.amplitude_dbfs} dBFS")
    print(f"  Duration: {config.duration_s}s")

    # Create play_and_record function
    play_and_record_fn = None

    if not args.simulate:
        try:
            from tap_tone_pi.capture import play_and_record

            def _play_record(signal, sr):
                return play_and_record(
                    signal, device_index, sr, timeout=config.duration_s + 1.0
                )

            play_and_record_fn = _play_record
        except ImportError:
            print("\nWarning: Audio capture not available. Running in simulation mode.")

    # Run test
    result = run_reference_tone_test(config, play_and_record_fn)

    if not result.success:
        print(f"\n\033[91mReference tone test FAILED: {result.error_message}\033[0m")
        return 1

    print("\n\033[92mReference tone test PASSED\033[0m")
    print(f"  Amplitude error: {result.amplitude_error_db:+.2f} dB")
    print(f"  Frequency error: {result.frequency_error_hz:+.2f} Hz")
    print(f"  THD: {result.thd_db:.1f} dB ({result.thd_percent:.3f}%)")
    print(f"  SNR: {result.snr_db:.1f} dB")

    # Load or create calibration data
    data = load_calibration(device_index)
    if data is None:
        data = CalibrationData(
            device_index=device_index,
            device_name=device_name,
            calibrated_at=datetime.now().isoformat(),
        )

    # Update with reference tone results
    data.reference_tone_completed = True
    data.reference_freq_hz = config.frequency_hz
    data.reference_amplitude_dbfs = config.amplitude_dbfs
    data.measured_amplitude_dbfs = result.measured_amplitude_dbfs
    data.amplitude_error_db = result.amplitude_error_db
    data.calibrated_at = datetime.now().isoformat()

    if data.is_complete():
        data.status = "valid"
    else:
        data.status = "uncalibrated"

    # Save
    path = save_calibration(data)
    print(f"\nCalibration data saved to: {path}")

    if not data.loopback_completed:
        print(
            "\nNote: Loopback test not completed. Run 'ttp calibrate loopback' for full calibration."
        )
    elif data.is_complete():
        print("\n\033[92mCalibration complete! Your device is now calibrated.\033[0m")

    return 0


def cmd_calibrate_clear(args: argparse.Namespace) -> int:
    """Clear calibration data for device."""
    from tap_tone_pi.calibration import clear_calibration
    from tap_tone_pi.core.user_config import get_saved_device

    device_index = args.device
    if device_index is None:
        saved = get_saved_device()
        if saved:
            device_index = saved.index
            print(f"Using saved device: [{device_index}] {saved.name}")
        else:
            print("No device specified and no saved device configuration.")
            return 1

    if not args.yes:
        print(f"\nThis will remove all calibration data for device {device_index}.")
        print("Press Enter to confirm, or Ctrl+C to cancel...")
        try:
            input()
        except KeyboardInterrupt:
            print("\nCancelled.")
            return 1

    if clear_calibration(device_index):
        print(f"\nCalibration data cleared for device {device_index}.")
    else:
        print(f"\nNo calibration data found for device {device_index}.")

    return 0


def cmd_calibrate_summary(args: argparse.Namespace) -> int:
    """Show summary of all calibrated devices."""
    from tap_tone_pi.calibration.storage import get_calibration_summary

    summary = get_calibration_summary()

    if not summary:
        print("\nNo calibrated devices found.")
        print("\nTo calibrate a device, run:")
        print("  ttp calibrate loopback --device <index>")
        return 0

    print("\nCalibrated Devices:\n")
    print(f"{'Device':<6} {'Name':<30} {'Status':<12} {'Calibrated':<20}")
    print("-" * 70)

    for device_idx, info in sorted(summary.items()):
        status = info["status"].upper()
        if info["stale"]:
            status += " (stale)"

        # Color coding
        if info["status"] == "valid" and not info["stale"]:
            color = "\033[92m"  # Green
        elif info["stale"]:
            color = "\033[93m"  # Yellow
        else:
            color = "\033[91m"  # Red
        reset = "\033[0m"

        cal_date = info["calibrated_at"][:10] if info["calibrated_at"] else "N/A"

        print(
            f"[{device_idx:>3}]  {info['device_name'][:28]:<30} "
            f"{color}{status:<12}{reset} {cal_date}"
        )

    print()
    return 0


def add_calibrate_subcommand(subparsers) -> None:
    """Add calibrate subcommand and its sub-subcommands."""
    p_cal = subparsers.add_parser(
        "calibrate",
        help="Self-calibration workflow",
        description="Commands for calibrating the measurement chain.",
    )

    cal_sub = p_cal.add_subparsers(dest="cal_cmd", required=True)

    # status
    p_status = cal_sub.add_parser("status", help="Show calibration status")
    p_status.add_argument("--device", "-d", type=int, help="Device index")
    p_status.set_defaults(fn=cmd_calibrate_status)

    # loopback
    p_loopback = cal_sub.add_parser(
        "loopback", help="Run loopback frequency response test"
    )
    p_loopback.add_argument("--device", "-d", type=int, help="Device index")
    p_loopback.add_argument("--sample-rate", "-r", type=int, help="Sample rate (Hz)")
    p_loopback.add_argument("--duration", type=float, help="Test duration (seconds)")
    p_loopback.add_argument(
        "--simulate", action="store_true", help="Run in simulation mode"
    )
    p_loopback.add_argument(
        "-y", "--yes", action="store_true", help="Skip confirmation"
    )
    p_loopback.set_defaults(fn=cmd_calibrate_loopback)

    # verify
    p_verify = cal_sub.add_parser(
        "verify", help="Run reference tone amplitude verification"
    )
    p_verify.add_argument("--device", "-d", type=int, help="Device index")
    p_verify.add_argument("--sample-rate", "-r", type=int, help="Sample rate (Hz)")
    p_verify.add_argument("--duration", type=float, help="Test duration (seconds)")
    p_verify.add_argument(
        "--level", type=float, help="Reference level in dBFS (default: -20)"
    )
    p_verify.add_argument(
        "--simulate", action="store_true", help="Run in simulation mode"
    )
    p_verify.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")
    p_verify.set_defaults(fn=cmd_calibrate_verify)

    # clear
    p_clear = cal_sub.add_parser("clear", help="Clear calibration data")
    p_clear.add_argument("--device", "-d", type=int, help="Device index")
    p_clear.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")
    p_clear.set_defaults(fn=cmd_calibrate_clear)

    # summary (list all)
    p_summary = cal_sub.add_parser("summary", help="Show all calibrated devices")
    p_summary.set_defaults(fn=cmd_calibrate_summary)
