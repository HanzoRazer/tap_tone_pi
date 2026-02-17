"""Input validation utilities for CLI with clear error messages."""

from __future__ import annotations

import sys
from pathlib import Path


def validate_device_index(device: int | None) -> int | None:
    """Validate audio device index exists.

    Args:
        device: Device index or None for default

    Returns:
        Validated device index

    Raises:
        SystemExit: If device doesn't exist (with helpful message)
    """
    if device is None:
        return None

    from tap_tone_pi.capture import list_devices

    devices = list_devices()
    valid_indices = [d["index"] for d in devices if d["max_input_channels"] > 0]

    if device not in valid_indices:
        print(f"Error: Device {device} not found or has no input channels.", file=sys.stderr)
        print(f"Available input devices: {valid_indices}", file=sys.stderr)
        print("Run 'ttp devices' to see all devices.", file=sys.stderr)
        sys.exit(1)

    return device


def validate_output_dir(path: str, must_exist: bool = False) -> Path:
    """Validate output directory path.

    Args:
        path: Output directory path
        must_exist: If True, directory must already exist

    Returns:
        Validated Path object

    Raises:
        SystemExit: If validation fails (with helpful message)
    """
    out = Path(path)

    if must_exist and not out.exists():
        print(f"Error: Directory does not exist: {out}", file=sys.stderr)
        print(f"Create it with: mkdir -p {out}", file=sys.stderr)
        sys.exit(1)

    if not must_exist and not out.parent.exists():
        print(f"Error: Parent directory does not exist: {out.parent}", file=sys.stderr)
        print(f"Create it with: mkdir -p {out.parent}", file=sys.stderr)
        sys.exit(1)

    return out


def validate_sample_rate(rate: int) -> int:
    """Validate sample rate is in acceptable range.

    Args:
        rate: Sample rate in Hz

    Returns:
        Validated sample rate

    Raises:
        SystemExit: If invalid (with helpful message)
    """
    valid_rates = [8000, 11025, 16000, 22050, 44100, 48000, 96000, 192000]

    if rate < 8000:
        print(f"Error: Sample rate {rate} Hz is too low (minimum: 8000 Hz)", file=sys.stderr)
        sys.exit(1)

    if rate > 192000:
        print(f"Error: Sample rate {rate} Hz is too high (maximum: 192000 Hz)", file=sys.stderr)
        sys.exit(1)

    if rate not in valid_rates:
        print(f"Warning: Non-standard sample rate {rate} Hz", file=sys.stderr)
        print(f"Standard rates: {valid_rates}", file=sys.stderr)

    return rate


def validate_duration(seconds: float) -> float:
    """Validate capture duration.

    Args:
        seconds: Duration in seconds

    Returns:
        Validated duration

    Raises:
        SystemExit: If invalid (with helpful message)
    """
    if seconds <= 0:
        print("Error: Duration must be positive", file=sys.stderr)
        print("Example: --seconds 2.5", file=sys.stderr)
        sys.exit(1)

    if seconds < 0.5:
        print(f"Warning: Very short duration ({seconds}s) may not capture full tap decay", file=sys.stderr)

    if seconds > 30:
        print(f"Warning: Long duration ({seconds}s) will create large files", file=sys.stderr)

    return seconds


def validate_file_exists(path: str, description: str = "File") -> Path:
    """Validate that a file exists.

    Args:
        path: File path
        description: Description for error message

    Returns:
        Validated Path object

    Raises:
        SystemExit: If file doesn't exist
    """
    p = Path(path)

    if not p.exists():
        print(f"Error: {description} not found: {p}", file=sys.stderr)
        sys.exit(1)

    if not p.is_file():
        print(f"Error: {description} is not a file: {p}", file=sys.stderr)
        sys.exit(1)

    return p


# -----------------------------------------------------------------------------
# Confirmation prompts for destructive operations
# -----------------------------------------------------------------------------


def confirm_overwrite(path: Path, force: bool = False) -> bool:
    """Confirm overwriting an existing file or directory.

    Args:
        path: Path to check
        force: If True, skip confirmation (for --force flag)

    Returns:
        True if should proceed, False to abort

    Raises:
        SystemExit: If user aborts
    """
    if not path.exists():
        return True

    if force:
        return True

    # Determine what we're overwriting
    if path.is_dir():
        item_type = "directory"
        # Count contents
        contents = list(path.rglob("*"))
        files = [f for f in contents if f.is_file()]
        size_str = f" ({len(files)} files)"
    else:
        item_type = "file"
        size_bytes = path.stat().st_size
        size_str = f" ({_format_bytes(size_bytes)})"

    msg = f"Warning: {item_type.capitalize()} already exists: {path}{size_str}"
    print("")
    print(msg)
    response = input(f"Overwrite {item_type}? [y/N]: ").strip().lower()

    if response not in ("y", "yes"):
        print("Aborted.")
        sys.exit(0)

    return True


def confirm_action(message: str, force: bool = False) -> bool:
    """Confirm a destructive action.

    Args:
        message: Description of the action
        force: If True, skip confirmation

    Returns:
        True if confirmed

    Raises:
        SystemExit: If user declines
    """
    if force:
        return True

    print("")
    print(message)
    response = input("Are you sure? [y/N]: ").strip().lower()

    if response not in ("y", "yes"):
        print("Aborted.")
        sys.exit(0)

    return True


def _format_bytes(size: int) -> str:
    """Format byte size for display."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
