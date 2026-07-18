# Active Dev Order

**Current:** DO-97G — Laboratory Manual corrective verification
**Status:** verification pending (CI + final adjudication)
**Previous:** DO-97 — Laboratory Manual Packaging & Desktop Access

> **DO-97G status:** DO-97G implementation complete locally; verification pending
> CI and final adjudication. An independent review of DO-97 found contract,
> resource, GUI, and packaging-verification gaps; DO-97G is the single correction
> commit that closes them without redesigning the feature or merging PR #9. The
> six original DO-97 commits are untouched. DO-97 is **not** marked complete —
> the milestone row in `docs/ARCHITECTURE_BASELINE_M4.md` remains
> **⚠ verification pending** until CI and final review confirm the correction.
>
> **Corrections:** reject scalar `applies_to`; enforce complete + acyclic
> supersession; replace private `_coerce_status` with public `parse_manual_status`;
> `Traversable`-native resource access (`resolve_manual_entry_resource`) with
> `resolve_manual_entry_path` reduced to a truthful filesystem-only shim; desktop
> viewer distinguishes empty / unavailable / invalid-manifest / missing-document
> states and cannot crash on a bad manifest; genuine wheel-build + isolated-install
> packaging test asserting the import origin is the installed wheel, not the checkout.
>
> **Local validation (2026-07-17):**
> - Focused tests: `tests/test_laboratory_manual_registry.py` (74), `..._view.py` (11),
>   `test_manual_packaging.py` (5) — all pass.
> - Ruff (touched files): clean. Compileall: pass.
> - Boundary checks: `check_advisory_boundary.py --strict` exit 0;
>   `check_boundary_imports.py --preset analyzer` exit 0;
>   `--preset analyzer_isolation --root analyzer` exit 0.
> - Full suite: 3308 passed, 2 failed, 4 skipped, 1 xfailed. The 2 failures
>   (`scripts/phase2/tests/test_validate_viewer_pack_v1_real_sessions.py`) are
>   pre-existing baseline failures — they reproduce on base with DO-97G changes
>   stashed, concern viewer-pack real-session fixture data (`manifest.contents`
>   missing `bending`), and touch no DO-97 file. Not repaired here (out of scope).
> - PR #9 remains open and unmerged; branch pushed without history rewrite.
>
> Incidental: removed one pre-existing unused import (`QDockWidget`) from the
> touched `analyzer/main_window.py` to keep the file lint-clean.

> **DO-97 note:** the handoff listed a DO-96 "Laboratory manifest and registry"
> and an existing `tap_tone_pi/acoustic_lab/` package as dependencies. Neither
> existed in the repo, and DO-96 appears nowhere in history. DO-97 was
> implemented self-contained (see `docs/ARCHITECTURE_BASELINE_M4.md` §13). The
> manifest ships **empty** by design — no consolidated Laboratory Manual
> document exists yet, and fabricating one was prohibited. `analyzer/` full
> desktop-installer packaging remains a separate out-of-scope task.

> **Note on DO-94 numbering:** the commits `6b74304` / `8255c8e` are tagged
> "(DO-94)" but implement *pressure response mapping* — a non-goal of this
> dev order. This DO-94 (Luthiery Formula Target Mapping) is a distinct work
> item that reuses the same number. Its commits are labeled
> "luthiery formula target" for disambiguation.

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
| DO-089A | Experiment design contract and cohort planning framework | COMPLETED |
| DO-089B | Process variance evidence and feasibility summary | COMPLETED |
| DO-089C | Covariate-aware cohort regression | COMPLETED |

## Pre-existing test failures (baseline)

3 failures unrelated to this dev order:
- `test_validate_viewer_pack_v1_real_sessions[runs_phase2/session_20260101T234237Z]` — missing 'bending' key
- `test_validate_viewer_pack_v1_real_sessions[runs_phase2/session_20260101T235209Z]` — missing 'bending' key
- `test_advisory_in_calibration_is_error` — advisory boundary test

These are documented baseline failures, not introduced by this sprint.

## Daily log

### 2026-06-27 (DO-95)
- DO-95 PR 95A: FormulaValidationEnvelopeV1 contract (`tap_tone_pi/luthiery/formula_validation.py`)
- DO-95 PR 95B: validate_formula_candidate() scalar helper + validate_formula_candidate_from_evidence() overload
- DO-95 PR 95C: optional formula_validation_envelope schema block
- DO-95 PR 95D: additive export integration in export_viewer_pack_v1.py
- DO-95 PR 95E: tests/test_luthiery_formula_validation.py (13 tests)
- DO-95 PR 95F: docs reconciliation + package exports
- DO-95 complete — error-detection evidence around formula candidates; no pass/fail or advisory language

### 2026-06-27 (DO-94)
- DO-94 PR 94A: LuthieryFormulaDomain, LuthieryFormulaTargetV1, LuthieryFormulaEvidenceLinkV1 contracts (`tap_tone_pi/luthiery/formula_targets.py`)
- DO-94 PR 94B: create_luthiery_formula_target(), link_formula_candidate_to_target() helpers
- DO-94 PR 94C: optional luthiery_formula_target / luthiery_formula_evidence_link schema blocks
- DO-94 PR 94D: additive export integration in export_viewer_pack_v1.py
- DO-94 PR 94E: tests/test_luthiery_formula_targets.py (13 tests)
- DO-94 PR 94F: docs reconciliation (CURRENT.md, GOVERNANCE_AUDIT_HANDOFF.md)
- DO-94 complete — declarative luthiery formula target layer; no advisory logic

### 2026-06-19
- DO-89C Stage A: RegressionInputV1, RegressionCoefficientV1 contracts
- DO-89C Stage B: CohortRegressionEvidenceV1 contract
- DO-89C Stage C: FormulaCandidateEvidenceV1 contract
- DO-89C Stage D: fit_linear_cohort_regression() OLS helper
- DO-89C Stage E: create_formula_candidate_evidence() helper
- DO-89C Stage F: Schema additions to phase2_ods_snapshot.schema.json
- DO-89C Stage G: Audit reconciliation
- DO-89C complete — 23 tests

- DO-89B Stage A: ReferenceBodyRecordV1 contract
- DO-89B Stage B: VarianceDecompositionV1 and decompose_variance()
- DO-89B Stage C: ProcessVarianceEvidenceV1 and compute_process_variance_evidence()
- DO-89B Stage D: VarianceBandThresholdsV1 and classify_variance_band()
- DO-89B Stage E: FeasibilitySummaryV1 and create_feasibility_summary()
- DO-89B Stage F: Schema additions to phase2_ods_snapshot.schema.json
- DO-89B Stage G: Audit reconciliation
- DO-89B complete — 35 tests

### 2026-06-18
- DO-89A Stage A: Response variable and MIE contracts
- DO-89A Stage B: Covariate definition contract
- DO-89A Stage C: Randomization plan contract
- DO-89A Stage D: Baseline rebuild plan contract
- DO-89A Stage E: ExperimentDesignV1 governing object
- DO-89A Stage F: Design validation evidence
- DO-89A Stage G: Campaign linkage (experiment_design_id)
- DO-89A Stage H: Schema additions to phase2_ods_snapshot.schema.json
- DO-89A Stage I: Export integration in export_viewer_pack_v1.py
- DO-89A Stage J: Audit reconciliation
- DO-89A complete — 37 tests

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

### 2026-07-16
- DO-97 (97A): Laboratory Manual contracts + empty manifest + canonical READMEs
- DO-97 (97B): Read-only path-safe manual registry (importlib.resources)
- DO-97 (97C): Desktop Help → Laboratory Manual read-only view
- DO-97 (97D): Package-data config; manifest + README verified in built wheel
- DO-97 (97E): 54 tests — contracts, negative, packaging, boundary, GUI
- DO-97 (97F): Reconciled M4 baseline, README, CURRENT.md
- DO-97 complete — 54 new tests, empty manifest by design

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
