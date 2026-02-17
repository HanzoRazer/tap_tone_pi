"""
Limit and mask testing module for Tap Tone Pi.

Provides frequency-dependent limit curves for pass/fail testing:
- Upper/lower limit curves
- Mask regions (exclude from testing)
- Margin calculation
- Pass/fail verdicts with details
"""

from .curves import (
    LimitPoint,
    LimitCurve,
    LimitType,
    create_limit_curve,
    interpolate_limit,
    create_flat_limit,
    create_sloped_limit,
)
from .masks import (
    MaskRegion,
    FrequencyMask,
    create_mask_region,
    apply_mask,
)
from .testing import (
    LimitTestResult,
    LimitViolation,
    check_against_limits,
    calculate_margin,
    find_violations,
)
from .presets import (
    get_preset_names,
    load_preset,
    save_preset,
    BUILTIN_PRESETS,
)

__all__ = [
    # Curves
    "LimitPoint",
    "LimitCurve",
    "LimitType",
    "create_limit_curve",
    "interpolate_limit",
    "create_flat_limit",
    "create_sloped_limit",
    # Masks
    "MaskRegion",
    "FrequencyMask",
    "create_mask_region",
    "apply_mask",
    # Testing
    "LimitTestResult",
    "LimitViolation",
    "check_against_limits",
    "calculate_margin",
    "find_violations",
    # Presets
    "get_preset_names",
    "load_preset",
    "save_preset",
    "BUILTIN_PRESETS",
]
