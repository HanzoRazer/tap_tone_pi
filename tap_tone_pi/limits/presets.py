"""
Built-in limit presets and preset management.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from .curves import LimitCurve
from .masks import FrequencyMask


# Built-in presets for common use cases
BUILTIN_PRESETS: Dict[str, Dict[str, Any]] = {
    "tonewood_tap": {
        "name": "Tonewood Tap Testing",
        "description": "Limits for tonewood tap tone testing in luthiery",
        "limits": [
            {
                "name": "upper_limit",
                "limit_type": "upper",
                "description": "Maximum expected amplitude",
                "points": [
                    {"frequency_hz": 50.0, "value_db": -20.0},
                    {"frequency_hz": 100.0, "value_db": -10.0},
                    {"frequency_hz": 500.0, "value_db": 0.0},
                    {"frequency_hz": 2000.0, "value_db": -10.0},
                    {"frequency_hz": 5000.0, "value_db": -30.0},
                ],
            },
            {
                "name": "lower_limit",
                "limit_type": "lower",
                "description": "Minimum detectable amplitude (noise floor)",
                "points": [
                    {"frequency_hz": 50.0, "value_db": -80.0},
                    {"frequency_hz": 500.0, "value_db": -70.0},
                    {"frequency_hz": 2000.0, "value_db": -75.0},
                    {"frequency_hz": 5000.0, "value_db": -80.0},
                ],
            },
        ],
        "mask": {
            "name": "tonewood_mask",
            "description": "Exclude subsonic and ultrasonic",
            "regions": [
                {"freq_min_hz": 0.1, "freq_max_hz": 30.0, "reason": "Subsonic"},
                {"freq_min_hz": 8000.0, "freq_max_hz": 24000.0, "reason": "Ultrasonic"},
            ],
        },
    },
    "speaker_response": {
        "name": "Speaker Frequency Response",
        "description": "Limits for speaker/driver frequency response testing",
        "limits": [
            {
                "name": "upper_limit",
                "limit_type": "upper",
                "description": "Maximum deviation from flat",
                "points": [
                    {"frequency_hz": 20.0, "value_db": 6.0},
                    {"frequency_hz": 100.0, "value_db": 3.0},
                    {"frequency_hz": 1000.0, "value_db": 3.0},
                    {"frequency_hz": 10000.0, "value_db": 3.0},
                    {"frequency_hz": 20000.0, "value_db": 6.0},
                ],
            },
            {
                "name": "lower_limit",
                "limit_type": "lower",
                "description": "Minimum deviation from flat",
                "points": [
                    {"frequency_hz": 20.0, "value_db": -12.0},
                    {"frequency_hz": 100.0, "value_db": -3.0},
                    {"frequency_hz": 1000.0, "value_db": -3.0},
                    {"frequency_hz": 10000.0, "value_db": -3.0},
                    {"frequency_hz": 20000.0, "value_db": -12.0},
                ],
            },
        ],
        "mask": None,
    },
    "noise_floor": {
        "name": "Noise Floor Test",
        "description": "Verify noise floor is below threshold",
        "limits": [
            {
                "name": "max_noise",
                "limit_type": "upper",
                "description": "Maximum acceptable noise",
                "points": [
                    {"frequency_hz": 20.0, "value_db": -60.0},
                    {"frequency_hz": 1000.0, "value_db": -70.0},
                    {"frequency_hz": 20000.0, "value_db": -60.0},
                ],
            },
        ],
        "mask": {
            "name": "ac_hum_mask",
            "description": "Exclude AC hum frequencies",
            "regions": [
                {"freq_min_hz": 47.0, "freq_max_hz": 53.0, "reason": "50 Hz hum"},
                {"freq_min_hz": 57.0, "freq_max_hz": 63.0, "reason": "60 Hz hum"},
                {
                    "freq_min_hz": 97.0,
                    "freq_max_hz": 103.0,
                    "reason": "100 Hz harmonic",
                },
                {
                    "freq_min_hz": 117.0,
                    "freq_max_hz": 123.0,
                    "reason": "120 Hz harmonic",
                },
            ],
        },
    },
    "calibration_flat": {
        "name": "Calibration Flat Response",
        "description": "Verify flat response within tolerance",
        "limits": [
            {
                "name": "upper_flat",
                "limit_type": "upper",
                "description": "Upper tolerance",
                "points": [
                    {"frequency_hz": 20.0, "value_db": 1.0},
                    {"frequency_hz": 20000.0, "value_db": 1.0},
                ],
            },
            {
                "name": "lower_flat",
                "limit_type": "lower",
                "description": "Lower tolerance",
                "points": [
                    {"frequency_hz": 20.0, "value_db": -1.0},
                    {"frequency_hz": 20000.0, "value_db": -1.0},
                ],
            },
        ],
        "mask": None,
    },
}


def get_preset_names() -> List[str]:
    """Get list of available preset names."""
    return list(BUILTIN_PRESETS.keys())


def load_preset(
    name: str,
) -> tuple[List[LimitCurve], Optional[FrequencyMask]]:
    """
    Load a built-in preset.

    Args:
        name: Preset name

    Returns:
        Tuple of (limit_curves, mask)

    Raises:
        KeyError: If preset not found
    """
    if name not in BUILTIN_PRESETS:
        raise KeyError(f"Unknown preset: {name}. Available: {get_preset_names()}")

    preset = BUILTIN_PRESETS[name]

    # Load limits
    limits = []
    for limit_data in preset.get("limits", []):
        limits.append(LimitCurve.from_dict(limit_data))

    # Load mask
    mask = None
    if preset.get("mask"):
        mask = FrequencyMask.from_dict(preset["mask"])

    return limits, mask


def load_preset_from_file(
    filepath: Path | str,
) -> tuple[List[LimitCurve], Optional[FrequencyMask]]:
    """
    Load a preset from JSON file.

    Args:
        filepath: Path to JSON file

    Returns:
        Tuple of (limit_curves, mask)
    """
    filepath = Path(filepath)
    data = json.loads(filepath.read_text(encoding="utf-8"))

    limits = []
    for limit_data in data.get("limits", []):
        limits.append(LimitCurve.from_dict(limit_data))

    mask = None
    if data.get("mask"):
        mask = FrequencyMask.from_dict(data["mask"])

    return limits, mask


def save_preset(
    filepath: Path | str,
    limits: List[LimitCurve],
    mask: Optional[FrequencyMask] = None,
    name: str = "custom",
    description: str = "",
) -> Path:
    """
    Save limits and mask to JSON file.

    Args:
        filepath: Output path
        limits: Limit curves
        mask: Optional frequency mask
        name: Preset name
        description: Preset description

    Returns:
        Path to saved file
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "name": name,
        "description": description,
        "limits": [limit.to_dict() for limit in limits],
        "mask": mask.to_dict() if mask else None,
    }

    # Atomic write
    tmp_path = filepath.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(data, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    tmp_path.replace(filepath)

    return filepath


def describe_preset(name: str) -> str:
    """
    Get description of a preset.

    Args:
        name: Preset name

    Returns:
        Human-readable description
    """
    if name not in BUILTIN_PRESETS:
        return f"Unknown preset: {name}"

    preset = BUILTIN_PRESETS[name]
    lines = [
        f"Preset: {preset['name']}",
        f"Description: {preset.get('description', 'No description')}",
        "",
        "Limits:",
    ]

    for limit in preset.get("limits", []):
        limit_type = limit.get("limit_type", "unknown").upper()
        lines.append(f"  - {limit['name']} ({limit_type})")
        if limit.get("description"):
            lines.append(f"    {limit['description']}")
        points = limit.get("points", [])
        if points:
            freq_range = (
                f"{points[0]['frequency_hz']:.0f}-{points[-1]['frequency_hz']:.0f} Hz"
            )
            lines.append(f"    Range: {freq_range}")

    mask = preset.get("mask")
    if mask:
        lines.append("")
        lines.append("Mask:")
        lines.append(f"  Name: {mask.get('name', 'unnamed')}")
        for region in mask.get("regions", []):
            lines.append(
                f"  - {region['freq_min_hz']:.0f}-{region['freq_max_hz']:.0f} Hz: {region.get('reason', '')}"
            )

    return "\n".join(lines)
