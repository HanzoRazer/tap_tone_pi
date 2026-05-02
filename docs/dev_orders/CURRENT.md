# Active Dev Order

**Current:** DO-002 — Predicted-vs-measured comparison module
**Spec:** See `docs/03_THREE_WEEK_DEV_PLAN.md` section "DO-002"
**Started:** 2026-05-02
**Estimated effort:** 6-8 hours
**Dependencies:** DO-001 (completed)

## Scope

Create `tap_tone_pi/design/comparison.py` that:
- Consumes `RenderedModeShape` from DO-001
- Consumes `PointSpectrum` from `scripts/phase2/metrics.py`
- Produces `ComparisonResult` with per-point residuals and agreement metrics
- Includes phase data comparison (phase_deg from PointSpectrum)

## Pre-existing test failures (baseline)

3 failures unrelated to this dev order:
- `test_validate_viewer_pack_v1_real_sessions[runs_phase2/session_20260101T234237Z]` — missing 'bending' key
- `test_validate_viewer_pack_v1_real_sessions[runs_phase2/session_20260101T235209Z]` — missing 'bending' key
- `test_advisory_in_calibration_is_error` — advisory boundary test

These are documented, not to be fixed as part of DO-002.

## Daily log

### 2026-05-02
- Committed planning docs and CLAUDE.md
- Committed DO-001 deliverables (mode_shape_render.py, test_mode_shape_render.py)
- Beginning DO-002 implementation
