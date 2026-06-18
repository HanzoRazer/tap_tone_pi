# Active Dev Order

**Current:** None — sprint complete
**Previous:** DO-089 — Campaign lifecycle state and measurement set aggregation
**Completed:** 2026-06-12

## Sprint Summary

DO-001 through DO-008, and DO-084 through DO-089 completed. The tap_tone_pi modal mapping toolchain now has:

| Dev Order | Description | Status |
|---|---|---|
| DO-001 | GUM uncertainty framework | COMPLETED |
| DO-002 | Wood species data sourcing | COMPLETED |
| DO-003 | Per-flitch wood database | COMPLETED |
| DO-004 | Per-build instrument record schema | COMPLETED |
| DO-005 | Analyzer GUI: Phase 2 results widget | COMPLETED |
| DO-006 | Predicted-vs-measured comparison overlay | COMPLETED |
| DO-008 | Build record auto-discovery + cleanup | COMPLETED |
| DO-084 | Transfer function uncertainty propagation | COMPLETED |
| DO-085 | Repeatability evidence and measurement validity envelope | COMPLETED |
| DO-086 | Workflow measurement contracts and procedural provenance | COMPLETED |
| DO-087 | Experimental provenance and measurement campaign lineage | COMPLETED |
| DO-088 | Build session and environmental provenance | COMPLETED |
| DO-089 | Campaign lifecycle state and measurement set aggregation | COMPLETED |

## Pre-existing test failures (baseline)

3 failures unrelated to this dev order:
- `test_validate_viewer_pack_v1_real_sessions[runs_phase2/session_20260101T234237Z]` — missing 'bending' key
- `test_validate_viewer_pack_v1_real_sessions[runs_phase2/session_20260101T235209Z]` — missing 'bending' key
- `test_advisory_in_calibration_is_error` — advisory boundary test

These are documented baseline failures, not introduced by this sprint.

## Daily log

### 2026-06-12
- DO-089 Stage A: CampaignLifecycleState enum and campaign lifecycle fields (7 tests)
- DO-089 Stage B: State transition helpers with validation (14 tests)
- DO-089 Stage C: MeasurementSetV1 and MeasurementSetSummaryV1 dataclasses (10 tests)
- DO-089 Stage D: Collection and aggregation helpers (7 tests)
- DO-089 Stage E: CampaignLifecycleExportV1 export block (4 tests)
- DO-089 Stage F: Schema additions to phase2_ods_snapshot.schema.json
- DO-089 Stage G: Export integration in export_viewer_pack_v1.py
- DO-089 Stage H: Audit reconciliation (GOVERNANCE_AUDIT_HANDOFF.md, CURRENT.md)
- DO-089 complete — 42 tests

### 2026-05-03
- DO-008 Stage A: Doc reconciliation — no-op (no prediction.py refs found)
- DO-008 Stage B: PyQt6 dependency declaration (1 test)
- DO-008 Stage C: Build record auto-discovery (11 tests)
- DO-008 Stage D: View menu opt-out toggle (3 tests)
- DO-008 complete — 15 new tests

### 2026-05-02
- DO-001, DO-002, DO-003, DO-004 completed
- DO-005 Stage A: Phase 2 session loader (26 tests)
- DO-005 Stage B: Heatmap rendering primitive (20 tests)
- DO-005 Stage C: Phase 2 results widget (15 tests)
- DO-005 Stage D: Main window integration (8 tests)
- DO-006 Stage E: Comparison mode + prediction loader (20 tests)
- Sprint complete — 89 tests across all stages
