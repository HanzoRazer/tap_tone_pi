#!/usr/bin/env python3
"""
merge_and_moe.py — DEPRECATED: Use tap_tone_pi.bending.merge_and_moe instead.

This module is a re-export shim for backward compatibility.
All functionality has been moved to tap_tone_pi.bending.merge_and_moe.

Usage (new):
    python -m tap_tone_pi.bending.merge_and_moe --help

Usage (legacy, still works):
    python modes/bending_rig/merge_and_moe.py --help
"""

import warnings

warnings.warn(
    "modes.bending_rig.merge_and_moe is deprecated. "
    "Use tap_tone_pi.bending.merge_and_moe instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export all public symbols from canonical location
from tap_tone_pi.bending.merge_and_moe import (   # noqa: E402
    main,
    _sha256,
    _load_series,
    _lin_interp,
    _resample,
    _linear_fit,
    _calculate_moe,
)

__all__ = [
    "main",
    "_sha256",
    "_load_series",
    "_lin_interp",
    "_resample",
    "_linear_fit",
    "_calculate_moe",
]

if __name__ == "__main__":
    main()
