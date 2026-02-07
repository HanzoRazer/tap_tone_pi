"""
tap_tone — DEPRECATED: Use tap_tone_pi instead.

This package is deprecated and will be removed in a future version.
All functionality has been migrated to tap_tone_pi.

Migration guide:
    Old:  from tap_tone.capture import record_audio
    New:  from tap_tone_pi.capture import record_audio

    Old:  from tap_tone.analysis import analyze_tap
    New:  from tap_tone_pi.core.analysis import analyze_tap

    Old:  from tap_tone.storage import persist_capture
    New:  from tap_tone_pi.io.storage import persist_capture

    Old:  from tap_tone.config import CaptureConfig, AnalysisConfig
    New:  from tap_tone_pi.core.config import CaptureConfig, AnalysisConfig

CLI migration:
    Old:  tap-tone record --out ./out
    New:  ttp record --out ./out

See docs/MIGRATION.md for full details.
"""
from __future__ import annotations

import warnings

warnings.warn(
    "tap_tone is deprecated. Use tap_tone_pi instead. "
    "See 'from tap_tone_pi import ...' or run 'ttp --help'. "
    "This shim will be removed in v3.0.0.",
    DeprecationWarning,
    stacklevel=2
)

# Backward compatibility shims - import from new locations
try:
    from tap_tone_pi.core.analysis import analyze_tap, AnalysisResult, Peak
    from tap_tone_pi.core.config import CaptureConfig, AnalysisConfig
    from tap_tone_pi.capture import CaptureResult, list_devices, record_audio
    from tap_tone_pi.io.storage import persist_capture, PersistedCapture
except ImportError:
    # Fall back to local implementations if tap_tone_pi not available
    from .analysis import analyze_tap, AnalysisResult, Peak
    from .config import CaptureConfig, AnalysisConfig
    from .capture import CaptureResult, list_devices, record_audio
    from .storage import persist_capture, PersistedCapture

__all__ = [
    # Analysis
    "analyze_tap",
    "AnalysisResult",
    "Peak",
    # Config
    "CaptureConfig",
    "AnalysisConfig",
    # Capture
    "CaptureResult",
    "list_devices",
    "record_audio",
    # Storage
    "persist_capture",
    "PersistedCapture",
]

__version__ = "2.0.0-deprecated"
