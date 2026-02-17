"""
DEPRECATED: wolf_advisor has moved to tap_tone_pi.wolf.wolf_advisor

This shim will be removed in v3.0.0.
"""

import warnings

warnings.warn(
    "tap_tone.wolf_advisor is deprecated. Use tap_tone_pi.wolf.wolf_advisor instead. "
    "This shim will be removed in v3.0.0.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from new location
from tap_tone_pi.wolf.wolf_advisor import *  # noqa: F401, F403, E402
from tap_tone_pi.wolf.wolf_advisor import (  # noqa: E402
    MitigationType,
    ConfidenceLevel,
    MitigationRecommendation,
    WolfAdvisorResult,
    WolfDirective,
    WolfAdvisor,
    advise_on_wolf,
    generate_wolf_directive,
)
