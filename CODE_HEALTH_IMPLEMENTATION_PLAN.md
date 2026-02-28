# Code Health Implementation Plan

**Created:** 2026-02-25
**Source reports:** `bandit-report.json`, `radon-cc-report.json`, `radon-mi-report.json`, `vulture-report.txt`, `CODE_HEALTH_SCAN_HANDOFF.md`

---

## Summary of Findings

| Dimension | Current Grade | Target Grade | Effort |
|---|---|---|---|
| Security | **A** (0 MEDIUM+) | A | ~30 min |
| Dead Code | **B+** (2 real unused vars) | A | ~1 hr |
| Complexity | **C+** (17 D/E/F functions) | B+ | ~5 days |
| Maintainability | **A** (4 files below A) | A (all files) | ~1–2 weeks |

---

## Phase 1 — Quick Wins (1–2 hours)

### 1.1 Remove confirmed dead variables

| # | File | Line | Variable | Action |
|---|---|---|---|---|
| 1 | `tap_tone_pi/design/inverse_solver.py` | 498 | `initial_guess_mm` | Delete assignment (overwritten on next line) |
| 2 | `tap_tone_pi/uncertainty/propagation.py` | 485 | `n_test_points` | Delete assignment (overwritten on next line) |

**Validation:** `make test` — all tests must pass.

### 1.2 Spot-check Bandit exception-handling findings

| # | Rule | Description | Action |
|---|---|---|---|
| 3 | `B110` try/except/pass | Locate the 1 occurrence. If in `core/`, `damping/`, `transfer_function/`, `bending/`, or `storage/` → fix to log/re-raise. | Inspect + fix if needed |
| 4 | `B112` try/except/continue | Same check. | Inspect + fix if needed |

### 1.3 Create Vulture whitelist

| # | Task |
|---|---|
| 5 | Create `vulture_whitelist.py` at repo root with dummy references to the 78 false-positive fixture names (`patch_passing`, `patch_all_passing`, `patch_with_fail`, `patch_failing`, `patch_analysis_error`, `kw`, `tmp_xdg`, `severe_wolf_frf`, `patch_with_warn`, `assert_array_less`). Also whitelist `__exit__` args (`exc_type`, `exc_val`, `exc_tb`) and PyAudio callback arg `time_info`. |

**Future scans:** `vulture tap_tone_pi/ tests/ vulture_whitelist.py --min-confidence 80`

---

## Phase 2 — Critical Complexity Reduction (1–2 days)

Target the **F-grade** and **E-grade** functions (3 functions, highest defect risk).

### 2.1 `build_qa_lab_spec_entry` — F grade, CC=52

**File:** `tap_tone_pi/bending/qa_lab_spec.py:566–887` (322 lines)

| # | Extracted Function | Responsibility | Target CC |
|---|---|---|---|
| 6 | `_validate_qa_inputs()` | Input validation & early exits | ≤ 8 |
| 7 | `_compute_dimensions()` | Dimension calculations | ≤ 8 |
| 8 | `_build_statistics_block()` | Statistical summary assembly | ≤ 10 |
| 9 | `_propagate_qa_uncertainties()` | Uncertainty propagation block | ≤ 10 |
| 10 | Refactored `build_qa_lab_spec_entry()` orchestrator | Thin orchestrator calling above | ≤ 15 |

**Constraints:** Pure DSP, no I/O in analysis — file writes stay out of these helpers.

### 2.2 `extract_damping_crossvalidated` — E grade, CC=39

**File:** `tap_tone_pi/damping/extraction.py:477–647` (171 lines)

| # | Extracted Function | Responsibility | Target CC |
|---|---|---|---|
| 11 | `_crossvalidate_results()` | Cross-validation comparison & consensus logic | ≤ 10 |
| 12 | Refactored `extract_damping_crossvalidated()` | Orchestrator: call half-power → call curve-fit → cross-validate → return | ≤ 12 |

### 2.3 `main` in thickness_calculator.py — E grade, CC=35

**File:** `tap_tone_pi/design/thickness_calculator.py:808–1017` (210 lines)

| # | Extracted Function | Responsibility | Target CC |
|---|---|---|---|
| 13 | `_parse_thickness_args()` | Argument parsing | ≤ 5 |
| 14 | `calculate_thickness(params)` | Pure computation orchestration | ≤ 12 |
| 15 | `_format_thickness_results()` | Output formatting | ≤ 8 |
| 16 | Refactored `main()` | parse → compute → format → print | ≤ 10 |

---

## Phase 3 — D-Grade Complexity Reduction (3–5 days)

14 functions at CC 21–28. Ordered by domain criticality.

### 3.1 Measurement-critical (highest priority)

| # | CC | Function | File | Strategy |
|---|---|---|---|---|
| 17 | 28 | `match_phases` | `core/phase_crossval.py:147–311` | Extract per-algorithm branch subroutines |
| 18 | 28 | `validate_measurement_quality` | `transfer_function/quality.py:195–362` | Extract per-metric validators |
| 19 | 26 | `assess_measurement_quality` | `core/uncertainty_flags.py:255–401` | Extract per-flag checking logic |

### 3.2 Workflow / Agent layer

| # | CC | Function | File | Strategy |
|---|---|---|---|---|
| 20 | 24 | `_merge_actions` | `agent/messages.py:622–743` | Simplify merge logic; lift closures to module level |
| 21 | 23 | `run_single` | `workflow/operator_loop.py:239–523` | Extract pre-check / measure / post-check phases |
| 22 | 23 | `_run_shadow_hook_inner` | `workflow/operator_loop.py:539–708` | Separate shadow record generation from orchestration |
| 23 | 22 | `detect_moments` | `agentic/spine/moments.py:229–288` | Interface simplification (only 60 lines) |

### 3.3 GUI / Export

| # | CC | Function | File | Strategy |
|---|---|---|---|---|
| 24 | 25 | `build_spreadsheet_entry` | `bending/gore_spreadsheet.py:466–626` | Extract computation blocks (like 2.1) |
| 25 | 24 | `export_gui_session` | `gui/export.py:168–358` | Extract file-gathering, zip-building, metadata-writing |

### 3.4 Scripts / CLI (lower priority)

| # | CC | Function | File | Strategy |
|---|---|---|---|---|
| 26 | 24 | `_build_calibration_block` | `scripts/bending_stiffness_mode.py:529–593` | Extract per-field builders |
| 27 | 23 | `validate_viewer_pack` | `scripts/viewer_pack_validate.py:106–231` | Extract per-section validators |
| 28 | 22 | `main` | `scripts/plot_coherence_phase.py:129–248` | Split plot setup from data processing |
| 29 | 21 | `cmd_measure` | `cli/main.py:594–749` | Extract pre-flight / recording / analysis / storage phases |

---

## Phase 4 — File-Level Maintainability Restructuring (1–2 weeks)

Target the 4 files below MI grade A.

### 4.1 `gui/app.py` — MI=0.0, grade C (2,232+ lines)

| # | Task | Target |
|---|---|---|
| 30 | Extract `QualityVerdictViewer` class → `gui/quality_verdict.py` | New file ~300 lines |
| 31 | Extract measurement methods (`do_quality_measure`, `_do_grid_point_measure`) → `gui/measurement_flow.py` | New file ~300 lines |
| 32 | Extract `do_chladni_wizard` → `gui/chladni_flow.py` | New file ~200 lines |
| 33 | Slim `App` to router/container delegating to extracted modules | `app.py` ≤ 800 lines |

### 4.2 `gui/widgets.py` — MI=6.0, grade C (1,525+ lines)

| # | Task | Target |
|---|---|---|
| 34 | Extract `SessionBrowserDialog` → `gui/session_browser.py` | New file |
| 35 | Extract `PackDiffDialog` → `gui/pack_diff.py` | New file |
| 36 | Extract `SetupWizardDialog` → `gui/setup_wizard.py` | New file |
| 37 | Extract `SessionInfo` → `gui/session_info.py` | New file |
| 38 | Retain only shared small widgets in `widgets.py` | ≤ 400 lines |

### 4.3 `cli/main.py` — MI=9.2, grade B (1,106+ lines)

| # | Task | Target |
|---|---|---|
| 39 | Extract `cmd_export_pack` → `cli/export.py` | New file |
| 40 | Extract `_find_all_sessions` → `cli/session_utils.py` | New file |
| 41 | Simplify `cmd_measure` (ties into #29) | `main.py` ≤ 600 lines |

### 4.4 `scripts/session_close.py` — MI=17.0, grade B (982 lines)

| # | Task | Target |
|---|---|---|
| 42 | Extract `classify_malformed_jsonl_line` + `scan_all_malformed_jsonl_indexes` + `_handle_scan_all_malformed` → `scripts/jsonl_repair.py` | New file |
| 43 | Slim `session_close.py` to orchestrator: scan → classify → repair | ≤ 500 lines |

---

## Phase 5 — Dead Code Cleanup (2–3 days)

*Run after Phase 3–4 refactoring* — structural changes often reveal new dead code.

| # | Category | Count | Action |
|---|---|---|---|
| 44 | Unused parameters (Skylos) | 29 | Review: protocol/callback signatures → whitelist; genuine → remove |
| 45 | Unused classes (Skylos) | 2 | Verify external usage; remove if genuinely dead |
| 46 | Remaining unused imports (Skylos) | 4 | Verify with grep; remove if safe (e.g., `BoundarySpec` may be needed by boundary checker) |
| 47 | Re-run both Vulture + Skylos | — | Capture new baseline after refactoring |

---

## Phase 6 — CI Integration (half day)

Encode gates so regressions are caught automatically.

### 6.1 Makefile / CI targets

| # | Gate | Command | Fail Condition |
|---|---|---|---|
| 48 | Complexity | `radon cc tap_tone_pi/ scripts/ modes/ -n C -a -s` | Any new F-grade function OR average CC > 5 |
| 49 | Maintainability | `radon mi tap_tone_pi/ scripts/ modes/ -n B` | Any file drops below MI=10 |
| 50 | Security | `bandit -r tap_tone_pi/ --severity-level medium -f json` | Any MEDIUM+ finding |
| 51 | Dead code | `vulture tap_tone_pi/ vulture_whitelist.py --min-confidence 90` | Any new source-file dead code |

### 6.2 Baseline files

| # | Task |
|---|---|
| 52 | Update `complexity_baseline.json` after Phase 2–3 to lock in improvements |
| 53 | Add `vulture_whitelist.py` to repo |

---

## Execution Order & Dependencies

```
Phase 1 (Quick Wins)          ─── no dependencies, start immediately
    │
Phase 2 (F/E functions)       ─── can start in parallel with Phase 1
    │
Phase 3 (D functions)         ─── depends on Phase 2 patterns being established
    │
Phase 4 (File restructuring)  ─── depends on Phase 3 for gui/app.py and cli/main.py
    │                              (functions must be simplified before extraction)
Phase 5 (Dead code cleanup)   ─── depends on Phase 3–4 (re-scan after restructuring)
    │
Phase 6 (CI gates)            ─── depends on Phase 1–5 completion for baselines
```

## Validation at Each Phase

- **After every change:** `make test` (all 1,676 tests must pass)
- **After Phase 1:** Re-run vulture — should show 0 source-file findings
- **After Phase 2:** Re-run `radon cc -n E` — should show 0 E/F functions
- **After Phase 3:** Re-run `radon cc -n D` — should show 0 D+ functions
- **After Phase 4:** Re-run `radon mi -n B` — should show 0 B/C files
- **After Phase 5:** Re-run Skylos — net decrease in findings
- **After Phase 6:** `make ci-dry-run` passes all new gates

## Total Estimated Effort

| Phase | Estimate |
|---|---|
| Phase 1 — Quick Wins | 1–2 hours |
| Phase 2 — F/E functions | 1–2 days |
| Phase 3 — D functions | 3–5 days |
| Phase 4 — File restructuring | 1–2 weeks |
| Phase 5 — Dead code cleanup | 2–3 days |
| Phase 6 — CI integration | 0.5 day |
| **Total** | **~3–4 weeks** |
