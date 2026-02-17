"""
DEPRECATED: wolf_beat has moved to tap_tone_pi.wolf.wolf_beat

This shim will be removed in v3.0.0.
"""

import warnings

warnings.warn(
    "tap_tone.wolf_beat is deprecated. Use tap_tone_pi.wolf.wolf_beat instead. "
    "This shim will be removed in v3.0.0.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from new location
from tap_tone_pi.wolf.wolf_beat import *  # noqa: F401, F403, E402
from tap_tone_pi.wolf.wolf_beat import (  # noqa: E402
    PeakInfo,
    PeakPair,
    WolfBeatResult,
    AvoidedCrossingModel,
    find_peaks_in_frf,
    find_peak_pairs,
    extract_linewidth,
    extract_linewidth_lorentzian,
    analyze_wolf_beat,
    estimate_coupling_from_split,
    predict_wolf_severity_change,
    simulate_mass_addition,
    simulate_damping_increase,
)
