#!/usr/bin/env python3
# INSTRUMENT CLASS: MEASUREMENT
"""
plot_f_vs_d.py — DEPRECATED: Use tap_tone_pi.bending.plot_f_vs_d instead.

This module is a re-export shim for backward compatibility.
All functionality has been moved to tap_tone_pi.bending.plot_f_vs_d.

Usage (new):
    python -m tap_tone_pi.bending.plot_f_vs_d --help

Usage (legacy, still works):
    python modes/bending_rig/plot_f_vs_d.py --help
"""

from __future__ import annotations

import warnings

warnings.warn(
    "modes.bending_rig.plot_f_vs_d is deprecated. "
    "Use tap_tone_pi.bending.plot_f_vs_d instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export all public symbols from canonical location
from tap_tone_pi.bending.plot_f_vs_d import (  # noqa: E402
    load_pairs,
    linear_fit,
    percentile_bounds,
    main,
)

__all__ = [
    "load_pairs",
    "linear_fit",
    "percentile_bounds",
    "main",
]

if __name__ == "__main__":
    main()
