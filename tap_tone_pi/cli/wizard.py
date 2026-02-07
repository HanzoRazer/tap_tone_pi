"""Hardware Setup Wizard for tap_tone_pi.

Interactive CLI wizard that:
1. Lists available audio devices
2. Lets user select a device
3. Performs a test recording
4. Validates audio levels (too quiet, clipping, good)
5. Saves configuration to ~/.tap_tone_pi/config.json

Usage:
    ttp setup              # Run the wizard
    ttp setup --reset      # Clear saved config and re-run
    ttp setup --show       # Show current saved config
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np


def run_wizard(args: argparse.Namespace) -> int:
    """Run the hardware setup wizard."""
    from tap_tone_pi.capture import list_devices, record_audio
    from tap_tone_pi.core.analysis import analyze_tap
    from tap_tone_pi.core.user_config import (
        AudioDeviceConfig,
        UserConfig,
        load_config,
        save_config,
        clear_config,
        CONFIG_FILE,
    )

    # Handle --show flag
    if getattr(args, "show", False):
        return _show_config()

    # Handle --reset flag
    if getattr(args, "reset", False):
        if clear_config():
            print("Cleared saved configuration.")
        else:
            print("No saved configuration to clear.")

    print()
    print("=" * 60)
    print("  tap_tone_pi — Hardware Setup Wizard")
    print("=" * 60)
    print()

    # Check for existing config
    existing = load_config()
    if existing and existing.audio_device and not getattr(args, "reset", False):
        print(f"Existing configuration found:")
        print(f"  Device: [{existing.audio_device.index}] {existing.audio_device.name}")
        print(f"  Sample rate: {existing.audio_device.sample_rate} Hz")
        print(f"  Validated: {existing.audio_device.validated_at}")
        print()

        response = _prompt("Re-run wizard? [y/N]: ").strip().lower()
        if response not in ("y", "yes"):
            print("Keeping existing configuration.")
            return 0
        print()

    # Step 1: List devices
    print("Step 1: Detecting audio devices...")
    print("-" * 40)

    devices = list_devices()
    input_devices = [d for d in devices if d["max_input_channels"] > 0]

    if not input_devices:
        print("ERROR: No audio input devices found!")
        print("Please connect a microphone and try again.")
        return 1

    print(f"Found {len(input_devices)} input device(s):\n")
    for d in input_devices:
        rate = int(d["default_samplerate"]) if d["default_samplerate"] else "?"
        print(f"  [{d['index']:2d}] {d['name']}")
        print(f"       Channels: {d['max_input_channels']}, Default rate: {rate} Hz")
    print()

    # Step 2: Select device
    print("Step 2: Select audio device")
    print("-" * 40)

    # Suggest USB device if available
    usb_device = None
    for d in input_devices:
        if "USB" in (d["name"] or "").upper():
            usb_device = d
            break

    if usb_device:
        print(f"Recommended: [{usb_device['index']}] {usb_device['name']} (USB)")

    default_idx = usb_device["index"] if usb_device else input_devices[0]["index"]

    while True:
        response = _prompt(f"Enter device number [{default_idx}]: ").strip()
        if not response:
            selected_idx = default_idx
            break
        try:
            selected_idx = int(response)
            if any(d["index"] == selected_idx for d in input_devices):
                break
            print(f"Invalid device number. Choose from: {[d['index'] for d in input_devices]}")
        except ValueError:
            print("Please enter a number.")

    selected_device = next(d for d in input_devices if d["index"] == selected_idx)
    print(f"\nSelected: [{selected_idx}] {selected_device['name']}")
    print()

    # Step 3: Select sample rate
    print("Step 3: Sample rate")
    print("-" * 40)

    default_rate = int(selected_device["default_samplerate"]) if selected_device["default_samplerate"] else 48000
    common_rates = [44100, 48000, 96000]

    print(f"Common rates: {common_rates}")
    response = _prompt(f"Enter sample rate [{default_rate}]: ").strip()

    if response:
        try:
            sample_rate = int(response)
        except ValueError:
            sample_rate = default_rate
    else:
        sample_rate = default_rate

    print(f"Using: {sample_rate} Hz")
    print()

    # Step 4: Test recording
    print("Step 4: Test recording")
    print("-" * 40)
    print("We'll do a 2-second test capture.")
    print("Please tap your specimen when prompted.")
    print()

    _prompt("Press ENTER when ready...")
    print()

    # Countdown
    for i in [3, 2, 1]:
        print(f"  {i}...")
        time.sleep(0.7)
    print("  TAP NOW!")
    print()

    try:
        result = record_audio(
            device=selected_idx,
            sample_rate=sample_rate,
            channels=1,
            seconds=2.0,
        )
    except Exception as e:
        print(f"ERROR: Recording failed: {e}")
        print("Please check your device connection and try again.")
        return 1

    print("Recording complete. Analyzing...")
    print()

    # Step 5: Analyze and validate
    print("Step 5: Audio validation")
    print("-" * 40)

    analysis = analyze_tap(result.audio, result.sample_rate)

    # Level assessment
    peak_level = float(np.max(np.abs(result.audio)))
    rms_db = 20 * np.log10(analysis.rms + 1e-10)

    print(f"  Peak level:  {peak_level:.3f} ({_level_bar(peak_level)})")
    print(f"  RMS level:   {analysis.rms:.4f} ({rms_db:.1f} dB)")
    print(f"  Clipped:     {'YES - TOO LOUD!' if analysis.clipped else 'No'}")
    print(f"  Confidence:  {analysis.confidence:.2f}")
    print()

    # Verdict
    status = _assess_levels(peak_level, analysis.rms, analysis.clipped, analysis.confidence)

    if status == "good":
        print("  [OK] Audio levels look good!")
    elif status == "quiet":
        print("  [WARNING] Audio is quite quiet.")
        print("           Consider increasing microphone gain or tapping harder.")
    elif status == "loud":
        print("  [WARNING] Audio is very loud (near clipping).")
        print("           Consider reducing microphone gain.")
    elif status == "clipped":
        print("  [ERROR] Audio is clipping!")
        print("          You MUST reduce microphone gain before real measurements.")
    elif status == "silent":
        print("  [ERROR] No audio detected!")
        print("          Check microphone connection and permissions.")

    print()

    # Show peaks if found
    if analysis.peaks:
        print("  Detected peaks:")
        for p in analysis.peaks[:5]:
            print(f"    - {p.freq_hz:7.1f} Hz  (magnitude: {p.magnitude:.3f})")
        if analysis.dominant_hz:
            print(f"\n  Dominant frequency: {analysis.dominant_hz:.1f} Hz")
    else:
        print("  No frequency peaks detected.")
        print("  (This is OK if you didn't tap, or the tap was too quiet)")

    print()

    # Step 6: Save configuration
    print("Step 6: Save configuration")
    print("-" * 40)

    if status in ("clipped", "silent"):
        print("Audio validation failed. Configuration NOT saved.")
        print("Please fix the issues above and run the wizard again:")
        print("  ttp setup")
        return 1

    response = _prompt("Save this configuration? [Y/n]: ").strip().lower()
    if response in ("n", "no"):
        print("Configuration NOT saved.")
        return 0

    # Create and save config
    device_config = AudioDeviceConfig(
        index=selected_idx,
        name=selected_device["name"],
        sample_rate=sample_rate,
        channels=1,
    )

    user_config = UserConfig(audio_device=device_config)
    config_path = save_config(user_config)

    print()
    print("=" * 60)
    print("  Setup complete!")
    print("=" * 60)
    print()
    print(f"  Configuration saved to: {config_path}")
    print()
    print("  Your saved settings will be used automatically by:")
    print("    - ttp record")
    print("    - ttp live")
    print("    - ttp quick")
    print("    - The GUI")
    print()
    print("  To re-run this wizard: ttp setup --reset")
    print()

    return 0


def _show_config() -> int:
    """Show current saved configuration."""
    from tap_tone_pi.core.user_config import load_config, CONFIG_FILE

    config = load_config()

    if not config:
        print(f"No configuration saved at {CONFIG_FILE}")
        print("Run 'ttp setup' to configure your hardware.")
        return 1

    print()
    print("Current tap_tone_pi configuration:")
    print("-" * 40)
    print(f"  Config file: {CONFIG_FILE}")
    print(f"  Version: {config.version}")
    print(f"  Created: {config.created_at}")
    print(f"  Updated: {config.updated_at}")
    print()

    if config.audio_device:
        d = config.audio_device
        print("  Audio device:")
        print(f"    Index: {d.index}")
        print(f"    Name: {d.name}")
        print(f"    Sample rate: {d.sample_rate} Hz")
        print(f"    Channels: {d.channels}")
        print(f"    Validated: {d.validated_at}")
    else:
        print("  Audio device: Not configured")

    print()
    print(f"  Default capture duration: {config.default_capture_seconds}s")
    print(f"  Default output directory: {config.default_output_dir}")
    print()

    return 0


def _prompt(msg: str) -> str:
    """Print prompt and read input (handles Ctrl+C gracefully)."""
    try:
        return input(msg)
    except (KeyboardInterrupt, EOFError):
        print("\nSetup cancelled.")
        sys.exit(1)


def _level_bar(level: float, width: int = 20) -> str:
    """Create a visual level bar."""
    filled = int(level * width)
    bar = "█" * filled + "░" * (width - filled)

    if level >= 0.999:
        return f"[{bar}] CLIPPING!"
    elif level >= 0.9:
        return f"[{bar}] Very loud"
    elif level >= 0.5:
        return f"[{bar}] Good"
    elif level >= 0.1:
        return f"[{bar}] OK"
    elif level >= 0.01:
        return f"[{bar}] Quiet"
    else:
        return f"[{bar}] Very quiet"


def _assess_levels(peak: float, rms: float, clipped: bool, confidence: float) -> str:
    """Assess audio levels and return status."""
    if clipped:
        return "clipped"
    if rms < 0.001:
        return "silent"
    if peak >= 0.9:
        return "loud"
    if rms < 0.01:
        return "quiet"
    return "good"


def build_setup_parser(subparsers) -> None:
    """Add the setup command to the CLI parser."""
    p = subparsers.add_parser(
        "setup",
        help="Run hardware setup wizard",
        description="Interactive wizard to configure audio hardware",
    )
    p.add_argument(
        "--reset",
        action="store_true",
        help="Clear saved config and re-run wizard",
    )
    p.add_argument(
        "--show",
        action="store_true",
        help="Show current saved configuration",
    )
    p.set_defaults(fn=run_wizard)


__all__ = ["run_wizard", "build_setup_parser"]
