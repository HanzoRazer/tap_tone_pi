# SPRINTS.md — tap_tone_pi Sprint Tracker

Living document tracking sprint history, open work, and methodology for the tap_tone_pi modal mapping toolchain.

---

## Sprint History

### Sprint 1 — Modal Mapping Foundation (2026-05-02)

**Theme:** Build the per-flitch and per-build data layer, then wire Phase 2 ODS results into the analyzer GUI with predicted-vs-measured comparison.

**Duration:** Single day (2026-05-02)
**Commits:** 17
**Tests added:** 89 (total suite: 2528)

| Dev Order | Title | Tests | Status |
|-----------|-------|-------|--------|
| DO-001 | GUM uncertainty framework | — | COMPLETED |
| DO-002 | Wood species data sourcing | — | COMPLETED |
| DO-003 | Per-flitch wood database | 12 | COMPLETED |
| DO-004 | Per-build instrument record schema | 18 | COMPLETED |
| DO-005 | Analyzer GUI: Phase 2 results widget | 69 | COMPLETED |
| DO-006 | Predicted-vs-measured comparison overlay | 20 | COMPLETED |

**Gap inventory sections closed:** §3.4, §3.5, §3.6, §3.7, §4.10, §4.11, §4.12, §5.9, §6.1

**Key deliverables:**
- `tap_tone_pi/materials/wood_db.py` — FlitchRecord, WoodDatabase
- `tap_tone_pi/materials/build_record.py` — BuildRecord, BuildDatabase, PredictedValues, MeasuredSummary, Residuals
- `analyzer/loaders/phase2_session.py` — Phase2Session, Phase2Point, load_phase2_session
- `analyzer/loaders/prediction_loader.py` — BuildComparison, ModeComparison, load_build_comparison
- `analyzer/widgets/_heatmap.py` — HeatmapWidget (2D colormap grid)
- `analyzer/widgets/phase2_results.py` — Phase2ResultsWidget (composite results view)
- Main window integration: File > Open Phase 2 Session... (Ctrl+2), Phase 2 ODS tab

**Completion docs:** `docs/dev_orders/completed/DO-001.md` through `DO-005.md`

---

### Sprint 2 — Build Context Integration (2026-05-03)

**Theme:** Auto-surface build context when opening Phase 2 sessions; cleanup from Sprint 1.

**Duration:** Single day (2026-05-03)
**Commits:** 4
**Tests added:** 15 (total suite: 2550)

| Dev Order | Title | Tests | Status |
|-----------|-------|-------|--------|
| DO-008 | Build record auto-discovery + cleanup | 15 | COMPLETED |

**Key deliverables:**
- PyQt6 dependency in pyproject.toml
- `_try_discover_build()` in Phase2ResultsWidget
- View > Auto-discover build context menu toggle

**Completion docs:** `docs/dev_orders/completed/DO-008.md`

---

## Open Work — In Progress

None. Sprint 2 complete.

---

## Open Work — Proposed

| Dev Order | Title | Priority | Blocks |
|-----------|-------|----------|--------|
| DO-007 | DXF writer consolidation | BLOCKING | All new DXF work |
| DO-009 | Blueprint vectorizer Loop 1 (intra-frame validation) | HIGH | DO-010 |
| DO-010 | Blueprint vectorizer AGE integration | HIGH | — |
| DO-011 | Wood species JSON per-field attribution | MEDIUM | — |
| DO-012 | Sprint bundle archival | LOW | — |
| DO-013 | Baseline test failure resolution | MEDIUM | — |

### DO-007 — DXF writer consolidation

**Priority:** BLOCKING
**Rationale:** CLAUDE.md mandates no new DXF generator until `services/api/app/cam/dxf_writer.py` exists and all existing generators are refactored to use it.

**Scope:**
- Create `dxf_writer.py` with dual-format support (R12 free tier, R2000 paid tier)
- Refactor existing generators to call it
- Enforce standards: SPLINE/LINE only, no LWPOLYLINE on R12, valid EXTMIN/EXTMAX

### DO-009 — Blueprint vectorizer Loop 1

**Priority:** HIGH
**Rationale:** CLAUDE.md vectorizer architecture decision requires intra-frame validation before export.

**Scope:**
- Add `validate_scale_before_export()` to vectorizer_phase3.py
- Add retry logic with fallback strategies
- Scale validation against instrument spec dimensions

### DO-009 — Blueprint vectorizer AGE integration

**Priority:** HIGH
**Depends on:** DO-008
**Rationale:** Ross requested this in multiple sessions per CLAUDE.md.

**Scope:**
- Wire VectorizerAGE above Loop 1
- Stage-aware Claude API calls for extraction quality evaluation
- Silent fallback when API unavailable

### DO-010 — Wood species JSON per-field attribution

**Priority:** MEDIUM
**Rationale:** CLAUDE.md data sourcing policy requires per-field attribution with source values.

**Scope:**
- Add `_density_source`, `_shrinkage_tangential_source`, `_shrinkage_radial_source` fields
- Migrate existing values to FPL_GTR282_table_5-3, wood_database_meier, or unknown_legacy

### DO-011 — PyQt6 dependency formalization

**Priority:** LOW
**Rationale:** PyQt6 used by analyzer but not in pyproject.toml.

**Scope:**
- Add PyQt6 to pyproject.toml optional dependencies
- Document installation for GUI users

### DO-012 — Sprint bundle archival

**Priority:** LOW
**Rationale:** Sprint artifact directories at repo root should move to docs/archive/sprints/.

**Scope:**
- Move sprint bundle directories to archive
- Update INDEX.md

### DO-013 — Baseline test failure resolution

**Priority:** MEDIUM
**Rationale:** 3 documented baseline failures in CURRENT.md.

**Scope:**
- Fix missing 'bending' key in two session fixtures
- Fix advisory boundary test

---

## Methodology

### Atomic commit discipline

Each dev order stage is committed independently with:
1. Implementation code
2. Tests passing (`pytest` green)
3. Commit message referencing stage and DO number

### Test-first verification

Before marking a stage complete:
- Run full test suite
- Verify no regressions
- Document any baseline failures

### Gap inventory tracking

When a dev order closes a gap from `docs/01_GAP_INVENTORY.md`:
- Update gap status to SHIPPED
- Record the dev order that closed it
- Add to sprint summary

---

## Dev-Order Handoff Pattern

Each dev order has a completion doc in `docs/dev_orders/completed/` with:

```markdown
# DO-XXX — Title

**Status:** COMPLETED YYYY-MM-DD
**Effort actual:** ~N hours
**Dependencies:** DO-YYY (completed)
**Unblocks:** Description of what this enables

---

## Summary
Brief description of what was built.

## Deliverables
| File | Purpose | Tests |
|---|---|---|
| path/to/file.py | What it does | N |

## Commits
| Commit | Stage | Description |
|---|---|---|
| abc123 | A | Stage A description |

## Features
Bullet list of key features.

## Acceptance Criteria — All Met
- [x] Criterion 1
- [x] Criterion 2
```

---

## File Index

| Path | Purpose |
|------|---------|
| `docs/SPRINTS.md` | This file — sprint tracker |
| `docs/dev_orders/CURRENT.md` | Active dev order status |
| `docs/dev_orders/completed/` | Completion docs for finished dev orders |
| `docs/01_GAP_INVENTORY.md` | Gap tracking by section ID |
| `tap_tone_pi/materials/wood_db.py` | Per-flitch wood database |
| `tap_tone_pi/materials/build_record.py` | Per-build instrument records |
| `analyzer/loaders/phase2_session.py` | Phase 2 session loader |
| `analyzer/loaders/prediction_loader.py` | Comparison data loader |
| `analyzer/widgets/_heatmap.py` | 2D heatmap widget |
| `analyzer/widgets/phase2_results.py` | Phase 2 results composite |
| `analyzer/main_window.py` | GUI main window with Phase 2 integration |

---

## Document Maintenance

- Update sprint history after each sprint completes
- Move proposed dev orders to in-progress when started
- Archive completion docs older than 60 days per CLAUDE.md policy
- Keep file index current with key deliverables

---

*Last updated: 2026-05-03*
