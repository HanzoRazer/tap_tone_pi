# Active Dev Order

**Current:** DO-003 — Per-flitch wood database schema + CRUD
**Spec:** See `docs/03_THREE_WEEK_DEV_PLAN.md` section "DO-003"
**Started:** (not yet started)
**Estimated effort:** 6-8 hours
**Dependencies:** None

## Scope

Create `tap_tone_pi/materials/wood_db.py` and `contracts/wood_flitch_record.schema.json`:
- JSON-backed flitch record store
- CRUD operations (add_flitch, add_measurement, get_flitch, list_flitches)
- Query support (stats_for_species, stats_for_supplier)
- Schema validation with jsonschema

## Pre-existing test failures (baseline)

3 failures unrelated to this dev order:
- `test_validate_viewer_pack_v1_real_sessions[runs_phase2/session_20260101T234237Z]` — missing 'bending' key
- `test_validate_viewer_pack_v1_real_sessions[runs_phase2/session_20260101T235209Z]` — missing 'bending' key
- `test_advisory_in_calibration_is_error` — advisory boundary test

These are documented, not to be fixed as part of DO-003.

## Daily log

### 2026-05-02
- DO-001 and DO-002 completed
- DO-003 ready to start
