"""
Plate tuning workflow with manual deflection profile entry.

Supports iterative thinning workflow:
1. Take multi-point deflection readings across panel
2. Record mass and optional tap frequency
3. Thin the panel
4. Repeat and track progression

See docs/FEATURE_GAP_THICKNESS_TRACKING.md for design.
"""

from .models import DeflectionReading, TuningSession, TuningHistory
from .analysis import (
    compute_density,
    compute_stiffness,
    compute_session_stats,
)

__all__ = [
    "DeflectionReading",
    "TuningSession",
    "TuningHistory",
    "compute_density",
    "compute_stiffness",
    "compute_session_stats",
]
