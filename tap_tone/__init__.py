"""
tap_tone — DEPRECATED namespace shim.

This package is deprecated and will be removed in a future version.
Use `tap_tone_pi` instead.

Migration:
    # Old (deprecated)
    from tap_tone.core import analysis

    # New
    from tap_tone_pi.core import analysis

All imports from this package will emit a DeprecationWarning.
"""

import warnings

warnings.warn(
    "The 'tap_tone' package is deprecated and will be removed in v3.0. "
    "Use 'tap_tone_pi' instead. "
    "Example: from tap_tone_pi.core import analysis",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export tap_tone_pi for backward compatibility
# This allows `from tap_tone import X` to work (with warning)
from tap_tone_pi import *  # noqa: E402, F401, F403
