"""
tap_tone_pi.phase2 — Phase 2 Operational Deflection Shape (ODS) workflow.

Phase 2 captures multi-point grid measurements for mode shape visualization.
This module provides:

- Grid display for visual capture progress tracking
- Session state management for resumable captures
- Coherence gating for per-point quality validation

Usage:
    from tap_tone_pi.phase2 import (
        GridDisplay,
        PointStatus,
        SessionState,
        check_coherence_from_arrays,
        CoherenceResult,
    )
    
    # Create grid display
    display = GridDisplay(grid)
    display.update("A1", PointStatus.CAPTURED)
    print(display.render())
    
    # Manage session state (resume support)
    state = SessionState.create(session_dir, grid)
    state.mark_captured("A1", coherence=0.95)
    state.save()
    
    # Check capture quality
    result = check_coherence_from_arrays(signal, None, sample_rate)
    if not result.passed:
        print(result.recommendation)
"""

from tap_tone_pi.phase2.grid_display import (
    GridDisplay,
    PointStatus,
    Colors,
)

from tap_tone_pi.phase2.session_state import (
    SessionState,
    PointRecord,
)

from tap_tone_pi.phase2.coherence_gate import (
    CoherenceResult,
    check_coherence,
    check_coherence_from_arrays,
    format_coherence_feedback,
)

__all__ = [
    # Grid display
    "GridDisplay",
    "PointStatus",
    "Colors",
    
    # Session state
    "SessionState",
    "PointRecord",
    
    # Coherence gate
    "CoherenceResult",
    "check_coherence",
    "check_coherence_from_arrays",
    "format_coherence_feedback",
]
