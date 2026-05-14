"""
Patch: Wire calibration context into Phase 2 session metadata.

Apply this patch to tap_tone_pi/cli/phase2_cmd.py to inject calibration
provenance into every Phase 2 capture session.

Instructions:
1. Add import at top of phase2_cmd.py:
   
   from tap_tone_pi.calibration.session_context import (
       get_calibration_context,
       format_calibration_summary,
       inject_calibration_into_meta,
   )

2. In _run_new(), after creating SessionState, add calibration context:

   # Inject calibration context
   device_index = getattr(args, "device", None) or 0
   cal_context = get_calibration_context(device_index)
   state.set_calibration(cal_context.to_dict())
   
   # Show calibration status
   print(format_calibration_summary(cal_context))
   print()

3. In SessionState class (session_state.py), add:

   calibration: Dict[str, Any] = field(default_factory=dict)
   
   def set_calibration(self, cal_dict: Dict[str, Any]) -> None:
       self.calibration = cal_dict
       self.save()

This ensures every Phase 2 session has calibration provenance recorded.
"""

# This file documents the integration pattern.
# The actual patch should be applied manually to preserve existing code.

PHASE2_CMD_ADDITIONS = '''
# Add to imports section:
from tap_tone_pi.calibration.session_context import (
    get_calibration_context,
    format_calibration_summary,
)

# Add to _run_new() after state = SessionState.create(...):
def _run_new_with_calibration(args: argparse.Namespace) -> int:
    """Start a new Phase 2 session with calibration context."""
    # ... existing validation code ...
    
    # Create session state (existing)
    state = SessionState.create(
        session_dir,
        grid,
        grid_path=str(grid_path),
        coherence_threshold=args.coherence_threshold,
    )
    
    # NEW: Inject calibration context
    device_index = getattr(args, "device", None) or 0
    cal_context = get_calibration_context(device_index)
    
    # Store in session metadata
    state.metadata["calibration"] = cal_context.to_dict()
    state.save()
    
    # Show calibration status to user
    print(format_calibration_summary(cal_context))
    if cal_context.warnings:
        print()  # Extra spacing after warnings
    
    # ... rest of existing code ...
'''

SESSION_STATE_ADDITIONS = '''
# Add to SessionState dataclass fields:
metadata: Dict[str, Any] = field(default_factory=dict)

# Add to to_dict():
"metadata": self.metadata,

# Add to from_dict():
metadata=d.get("metadata", {}),
'''

# Example of what session_state.json will look like after integration:
EXAMPLE_SESSION_STATE = '''
{
  "schema_version": "session_state_v1",
  "grid_path": "config/grids/guitar_top_35pt.json",
  "started_at_utc": "2026-03-28T10:00:00Z",
  "metadata": {
    "calibration": {
      "status": "valid",
      "device_index": 1,
      "device_name": "Scarlett Solo",
      "calibrated_at": "2026-03-15T10:00:00Z",
      "amplitude_offset_db": -0.3,
      "latency_ms": 15.5,
      "is_stale": false,
      "warnings": []
    }
  },
  "points": { ... }
}
'''
