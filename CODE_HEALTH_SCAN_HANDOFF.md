# Code Health Scan — Developer Handoff

**Date:** 2026-02-25
**Scope:** Full static analysis of `tap_tone_pi/`, `scripts/`, `modes/` (219 files, ~40K LOC)
**Tools:** Bandit 1.9.4, Radon 6.0.1, Vulture 2.14, Skylos 3.4.3
**Reports generated:** `bandit-report.json`, `radon-cc-report.json`, `radon-mi-report.json`, `vulture-report.txt`, `skylos-deadcode.json`

---

## Executive Summary

| Dimension | Grade | Key Metric |
|---|---|---|
| **Security** | **A** | 0 MEDIUM+ findings (Bandit) |
| **Dead Code** | **B+** | 148 Skylos symbols + 6 Vulture source items; 23 imports already cleaned |
| **Complexity** | **C+** | 17 functions at grade D/E/F; 1 F-grade god-function (CC=52) |
| **Maintainability** | **A** | 98% of files grade A (Radon MI); 4 files need attention |

The codebase is **secure and largely well-maintained**, with concentrated complexity in a small number of large functions and three GUI/CLI files. The remediation roadmap below prioritizes by impact-to-effort ratio.

---

## 1. Security Scan — Bandit 1.9.4

**Report:** `bandit-report.json`
**Threshold:** MEDIUM severity and above
**Result:** **0 findings** at MEDIUM+

### LOW-severity breakdown (informational only — no action required)

| Rule | Count | Description |
|---|---|---|
| `B603` subprocess_without_shell_equals_true | 20 | subprocess calls without `shell=True` — this is actually the *safe* pattern |
| `B101` assert_used | 11 | `assert` in non-test code — acceptable for internal invariants in measurement instrument |
| `B607` start_process_with_partial_path | 11 | subprocess with partial executable path — expected for audio tools (`ffmpeg`, `arecord`) |
| `B404` blacklist (subprocess import) | 8 | Importing `subprocess` module — required for device orchestration |
| `B105` hardcoded_password_string | 4 | Variable names containing "password" — false positives on config field names |
| `B311` blacklist (random) | 2 | Using `random` module — acceptable for non-cryptographic uses (Monte Carlo, synthetic signals) |
| `B110` try_except_pass | 1 | Silent exception — review if in a critical path |
| `B606` start_process_with_no_shell | 1 | subprocess without shell — safe pattern |
| `B112` try_except_continue | 1 | Exception with continue — review if in a critical path |

**Verdict:** Clean security posture. The 59 LOW findings are standard patterns for a hardware-interfacing measurement tool. The two exception-handling findings (`B110`, `B112`) are worth a spot-check to confirm they're not swallowing errors in DSP paths.

---

## 2. Dead Code Scan — Vulture 2.14 + Skylos 3.4.3

### 2a. Vulture findings (≥80% confidence)

**Report:** `vulture-report.txt`
**Total:** 84 findings

| Location | Count | Nature |
|---|---|---|
| **Test files** | 78 | Pytest fixture variables — false positives (fixtures injected by name) |
| **Source files** | 6 | 3 real unused vars + 3 protocol-required `__exit__` args |

#### Source findings detail

| File | Line | Symbol | Confidence | Action |
|---|---|---|---|---|
| `core/auto_trigger.py` | 202 | `time_info` | 100% | **Keep** — PyAudio callback signature requires this parameter |
| `design/inverse_solver.py` | 498 | `initial_guess_mm` | 100% | **Remove** — assigned but immediately overwritten |
| `uncertainty/propagation.py` | 485 | `n_test_points` | 100% | **Remove** — assigned but immediately overwritten |
| `viewer_pack/manifest.py` | 50 | `exc_type` | 100% | **Keep** — `__exit__(exc_type, exc_val, exc_tb)` protocol |
| `viewer_pack/manifest.py` | 50 | `exc_val` | 100% | **Keep** — same |
| `viewer_pack/manifest.py` | 50 | `exc_tb` | 100% | **Keep** — same |

**Net actionable:** 2 unused variable assignments.

#### Test fixture false positives (78 findings)

These are all variables like `patch_passing`, `patch_all_passing`, `patch_with_fail`, `kw`, `tmp_xdg`, `severe_wolf_frf` that appear "unused" because they're pytest fixtures activated by parameter name injection, not direct reference. **No action needed.** Consider adding a Vulture whitelist file (`vulture_whitelist.py`) to suppress these in future scans.

### 2b. Skylos findings (all confidence levels)

**Report:** `skylos-deadcode.json`
**Total at ≥80% confidence:** 148 symbols

| Category | Count | Status |
|---|---|---|
| Unused functions | 80 | **All reviewed — confirmed false positives** (decorators, cross-module calls, `__all__` exports, `self.method` calls) |
| Unused parameters | 29 | Unreviewed — likely callback/protocol signatures |
| Unused imports | 27 | **23 already cleaned** in prior session; 4 remaining are gated behind boundary imports (`BoundarySpec` in `ci/check_boundary_imports.py`) |
| Unused variables | 10 | Mix of legitimate dead code and destructuring assignments |
| Unused classes | 2 | Unreviewed |

### 2c. Cross-reference: Vulture vs Skylos

| Overlap | Count |
|---|---|
| **Confirmed by both tools** | 3 (`time_info`, `initial_guess_mm`, `n_test_points`) |
| **Vulture-only** | 13 (test fixtures + `__exit__` args) |
| **Skylos-only** | 126 (functions, imports, parameters, classes) |

**Key insight:** The tools have **complementary, non-overlapping coverage**. Vulture excels at local unused-variable detection. Skylos excels at cross-file reference analysis (unused functions/imports/classes). Neither found the other's primary findings. Using both tools together provides the most complete dead code picture.

---

## 3. Complexity Scan — Radon Cyclomatic Complexity

**Report:** `radon-cc-report.json`
**Threshold:** Grade C (CC ≥ 11) and worse
**Total functions flagged:** 126

### Grade distribution

| Grade | CC Range | Count | Severity |
|---|---|---|---|
| **C** | 11–15 | 109 | Monitor — refactor opportunistically |
| **D** | 16–25 | 14 | Plan — schedule refactoring |
| **E** | 26–40 | 2 | Urgent — high defect risk |
| **F** | 41+ | 1 | Critical — refactor immediately |

### All D/E/F functions (17 total)

| Grade | CC | Function | File | Lines | Span |
|---|---|---|---|---|---|
| **F** | 52 | `build_qa_lab_spec_entry` | `bending/qa_lab_spec.py` | 566–887 | 322 |
| **E** | 39 | `extract_damping_crossvalidated` | `damping/extraction.py` | 477–647 | 171 |
| **E** | 35 | `main` | `design/thickness_calculator.py` | 808–1017 | 210 |
| **D** | 28 | `match_phases` | `core/phase_crossval.py` | 147–311 | 165 |
| **D** | 28 | `validate_measurement_quality` | `transfer_function/quality.py` | 195–362 | 168 |
| **D** | 26 | `assess_measurement_quality` | `core/uncertainty_flags.py` | 255–401 | 147 |
| **D** | 25 | `build_spreadsheet_entry` | `bending/gore_spreadsheet.py` | 466–626 | 161 |
| **D** | 24 | `_merge_actions` | `agent/messages.py` | 622–743 | 122 |
| **D** | 24 | `export_gui_session` | `gui/export.py` | 168–358 | 191 |
| **D** | 24 | `_build_calibration_block` | `scripts/bending_stiffness_mode.py` | 529–593 | 65 |
| **D** | 23 | `run_single` | `workflow/operator_loop.py` | 239–523 | 285 |
| **D** | 23 | `_run_shadow_hook_inner` | `workflow/operator_loop.py` | 539–708 | 170 |
| **D** | 23 | `validate_viewer_pack` | `scripts/viewer_pack_validate.py` | 106–231 | 126 |
| **D** | 22 | `detect_moments` | `agentic/spine/moments.py` | 229–288 | 60 |
| **D** | 22 | `_validate_point_spectrum` | `validate/viewer_pack_v1.py` | 340–459 | 120 |
| **D** | 22 | `main` | `scripts/plot_coherence_phase.py` | 129–248 | 120 |
| **D** | 21 | `cmd_measure` | `cli/main.py` | 594–749 | 156 |

### Files with highest C-grade density

These files have the most functions at CC ≥ 11, indicating systemic complexity:

| C-grade functions | File | Notes |
|---|---|---|
| 7 | `gui/app.py` | Tkinter main app — also MI grade C |
| 4 | `core/session_diff.py` | Session comparison logic |
| 4 | `gui/widgets.py` | GUI widget library — also MI grade C |
| 4 | `validate/viewer_pack_v1.py` | Pack validation |
| 4 | `scripts/session_close.py` | Session cleanup |
| 3 | `bending/gore_spreadsheet.py` | Spreadsheet generation |
| 3 | `cli/calibrate.py` | Calibration commands |

---

## 4. Maintainability Scan — Radon Maintainability Index

**Report:** `radon-mi-report.json`
**Total files:** 219

### Grade distribution

| Grade | MI Range | Count | % |
|---|---|---|---|
| **A** | 20–100 | 215 | 98.2% |
| **B** | 10–19 | 2 | 0.9% |
| **C** | 0–9 | 2 | 0.9% |

### Files below grade A

| Grade | MI Score | File | Root Cause |
|---|---|---|---|
| **C** | 0.0 | `gui/app.py` | 2,232+ lines, 7 complex methods, monolithic Tkinter app |
| **C** | 6.0 | `gui/widgets.py` | 1,525+ lines, 4 complex methods, widget mega-module |
| **B** | 9.2 | `cli/main.py` | 1,106+ lines, CLI god-module with `cmd_measure` (CC=21) |
| **B** | 17.0 | `scripts/session_close.py` | 982 lines, 4 complex functions, malformed JSONL handling |

---

## Remediation Roadmap

### Phase 1: Quick Wins (1–2 hours)

Low-risk changes with immediate measurable improvement.

#### 1.1 Remove confirmed dead variables
- [ ] `design/inverse_solver.py:498` — delete `initial_guess_mm = ...` assignment (overwritten on next line)
- [ ] `uncertainty/propagation.py:485` — delete `n_test_points = ...` assignment (overwritten on next line)

**Validation:** `make test` — all 1,676 tests must pass.

#### 1.2 Spot-check Bandit exception-handling findings
- [ ] Review `B110` (try/except/pass) location — confirm it's not in a DSP or storage path
- [ ] Review `B112` (try/except/continue) location — same check

**Gate:** If either is in `core/`, `damping/`, `transfer_function/`, `bending/`, or `storage/` — fix to fail-closed per project rules.

#### 1.3 Create Vulture whitelist for test fixtures
- [ ] Create `vulture_whitelist.py` with dummy references to the fixture names (`patch_passing`, `patch_all_passing`, `kw`, `tmp_xdg`, etc.)
- [ ] Future vulture runs: `vulture tap_tone_pi/ tests/ vulture_whitelist.py --min-confidence 80`

This eliminates the 78 false positives from future scan noise.

---

### Phase 2: Complexity Reduction — Critical Path (1–2 days)

Target the F and E grade functions. These have the highest defect risk per research correlating cyclomatic complexity with bug density.

#### 2.1 `build_qa_lab_spec_entry` — F grade, CC=52, 322 lines
**File:** `bending/qa_lab_spec.py:566–887`
**Why it matters:** This is the single worst function in the codebase. CC=52 means 52 independent execution paths — virtually untestable as a unit.

**Recommended decomposition:**
1. Extract validation logic into `_validate_qa_inputs()`
2. Extract dimension calculations into `_compute_dimensions()`
3. Extract statistical summary into `_build_statistics_block()`
4. Extract uncertainty propagation into `_propagate_qa_uncertainties()`
5. The main function becomes a thin orchestrator calling the above

**Target:** CC ≤ 15 for the orchestrator, CC ≤ 10 for each helper.

#### 2.2 `extract_damping_crossvalidated` — E grade, CC=39, 171 lines
**File:** `damping/extraction.py:477–647`
**Why it matters:** Core DSP path — damping extraction is a measurement-critical function.

**Recommended decomposition:**
1. Extract the half-power method branch into its own function (already exists as `extract_damping_halfpower`)
2. Extract curve-fit branch (already exists as `extract_damping_curvefit`)
3. Extract the cross-validation comparison and consensus logic into `_crossvalidate_results()`
4. The main function becomes: call both methods → compare → return consensus

**Target:** CC ≤ 12 for the orchestrator.

#### 2.3 `main` in `thickness_calculator.py` — E grade, CC=35, 210 lines
**File:** `design/thickness_calculator.py:808–1017`
**Why it matters:** CLI entry point that mixes argument parsing, computation, and output formatting.

**Recommended decomposition:**
1. Extract argument parsing into `_parse_args()` (use `argparse` return directly)
2. Extract computation orchestration into `calculate_thickness(params)` (pure function)
3. Extract output formatting into `_format_results()`
4. `main()` becomes: parse → compute → format → print

**Target:** CC ≤ 10 for `main()`, CC ≤ 12 for `calculate_thickness()`.

---

### Phase 3: Complexity Reduction — D-Grade Functions (3–5 days)

Address the 14 D-grade functions. Prioritize by domain criticality.

#### 3.1 Measurement-critical (fix first)

| CC | Function | File | Strategy |
|---|---|---|---|
| 28 | `match_phases` | `core/phase_crossval.py` | Extract phase-matching subroutines for each algorithm branch |
| 28 | `validate_measurement_quality` | `transfer_function/quality.py` | Extract per-metric validators into separate functions |
| 26 | `assess_measurement_quality` | `core/uncertainty_flags.py` | Extract flag-checking logic per uncertainty source |

These are in the measurement-critical `core/` and `transfer_function/` domains. Reducing complexity here directly reduces the risk of subtle measurement bugs.

#### 3.2 Workflow/Agent layer

| CC | Function | File | Strategy |
|---|---|---|---|
| 24 | `_merge_actions` | `agent/messages.py` | Simplify action-merge logic; extract `add()` and `repeated()` closures to module-level |
| 23 | `run_single` | `workflow/operator_loop.py` | Extract pre-check, measure, post-check into phases |
| 23 | `_run_shadow_hook_inner` | `workflow/operator_loop.py` | Extract shadow record generation from hook orchestration |
| 22 | `detect_moments` | `agentic/spine/moments.py` | Already 60 lines — may need interface simplification rather than splitting |

#### 3.3 GUI/Export

| CC | Function | File | Strategy |
|---|---|---|---|
| 24 | `export_gui_session` | `gui/export.py` | Extract file-gathering, zip-building, and metadata-writing into separate functions |
| 25 | `build_spreadsheet_entry` | `bending/gore_spreadsheet.py` | Similar to 2.1 — extract computation blocks |

#### 3.4 Scripts (lower priority)

| CC | Function | File | Strategy |
|---|---|---|---|
| 24 | `_build_calibration_block` | `scripts/bending_stiffness_mode.py` | Extract per-field builders |
| 23 | `validate_viewer_pack` | `scripts/viewer_pack_validate.py` | Extract per-section validators |
| 22 | `main` | `scripts/plot_coherence_phase.py` | Split plot setup from data processing |
| 21 | `cmd_measure` | `cli/main.py` | Extract pre-flight, recording, analysis, and storage phases |

---

### Phase 4: Maintainability — File-Level Restructuring (1–2 weeks)

Target the 4 files below MI grade A. These require structural changes, not just function-level refactoring.

#### 4.1 `gui/app.py` — MI=0.0 (grade C)
**Current state:** 2,232+ lines, 7 C-grade methods, monolithic Tkinter application.

**Recommended approach:**
1. Extract `QualityVerdictViewer` class into its own module (`gui/quality_verdict.py`)
2. Extract measurement flow methods (`do_quality_measure`, `_do_grid_point_measure`) into `gui/measurement_flow.py`
3. Extract `do_chladni_wizard` into `gui/chladni_flow.py`
4. `App` class becomes a router/container that delegates to extracted modules
5. Aim for `app.py` under 800 lines

#### 4.2 `gui/widgets.py` — MI=6.0 (grade C)
**Current state:** 1,525+ lines, 4 C-grade methods, widget mega-module.

**Recommended approach:**
1. Extract `SessionBrowserDialog` into `gui/session_browser.py`
2. Extract `PackDiffDialog` into `gui/pack_diff.py`
3. Extract `SetupWizardDialog` into `gui/setup_wizard.py`
4. Extract `SessionInfo` into `gui/session_info.py`
5. `widgets.py` retains only shared small widgets

#### 4.3 `cli/main.py` — MI=9.2 (grade B)
**Current state:** 1,106+ lines, `cmd_measure` at CC=21.

**Recommended approach:**
1. Extract `cmd_export_pack` into `cli/export.py`
2. Extract `_find_all_sessions` into `cli/session_utils.py`
3. Simplify `cmd_measure` per Phase 3.4 above
4. Aim for `main.py` under 600 lines

#### 4.4 `scripts/session_close.py` — MI=17.0 (grade B)
**Current state:** 982 lines, 4 complex functions for malformed JSONL handling.

**Recommended approach:**
1. Extract `classify_malformed_jsonl_line` and `scan_all_malformed_jsonl_indexes` into `scripts/jsonl_repair.py`
2. Extract `_handle_scan_all_malformed` into the same module
3. `session_close.py` orchestrates scan → classify → repair

---

### Phase 5: Dead Code Cleanup — Remaining Skylos Items (2–3 days)

After the structural refactoring above, re-run Skylos to get a fresh baseline (refactoring often reveals genuine dead code that was previously hidden by long methods).

#### 5.1 Unused parameters (29 items)
Review each parameter. Categories:
- **Protocol/callback signatures** (e.g., `__exit__` args, event handler `event` params) → whitelist
- **Genuine dead parameters** → remove with deprecation if public API, direct removal if internal

#### 5.2 Unused classes (2 items)
Review each class for:
- External usage (imported by ToolBox integration or scripts not in scan scope)
- Test-only usage
- Genuinely dead → remove

#### 5.3 Remaining unused imports (4 items)
These were skipped in the prior cleanup because they're in boundary-check or conditional-import paths. Verify each:
- `BoundarySpec` in `ci/check_boundary_imports.py` — likely needed by the boundary checker itself
- Others — verify with `grep -rn "ImportName" --include="*.py"` before removing

---

### Phase 6: CI Integration (half day)

Encode these scans into CI so regressions are caught automatically.

#### 6.1 Complexity gate
```yaml
# In CI pipeline or Makefile target
radon cc tap_tone_pi/ scripts/ modes/ -n C -a -s
# Fail if average CC > 5 or any new F-grade function appears
```

#### 6.2 Maintainability gate
```yaml
radon mi tap_tone_pi/ scripts/ modes/ -n B
# Fail if any file drops below MI=10
```

#### 6.3 Security gate
```yaml
bandit -r tap_tone_pi/ --severity-level medium -f json
# Fail on any MEDIUM+ finding
```

#### 6.4 Dead code gate
```yaml
vulture tap_tone_pi/ vulture_whitelist.py --min-confidence 90
# Fail on new source-file dead code (exclude tests)
```

---

## Report File Inventory

All reports are in the repository root:

| File | Tool | Size | Format | Regenerate With |
|---|---|---|---|---|
| `bandit-report.json` | Bandit 1.9.4 | ~2KB | JSON | `bandit -r tap_tone_pi/ scripts/ modes/ -f json --severity-level medium -o bandit-report.json` |
| `radon-cc-report.json` | Radon 6.0.1 | 26KB | JSON | `radon cc tap_tone_pi/ scripts/ modes/ -j -n C > radon-cc-report.json` |
| `radon-mi-report.json` | Radon 6.0.1 | 26KB | JSON | `radon mi tap_tone_pi/ scripts/ modes/ -j > radon-mi-report.json` |
| `vulture-report.txt` | Vulture 2.14 | ~8KB | text | `vulture tap_tone_pi/ scripts/ modes/ tests/ --min-confidence 80 > vulture-report.txt` |
| `skylos-deadcode.json` | Skylos 3.4.3 | 1.3MB | JSON | `skylos tap_tone_pi/ scripts/ modes/ -c 80 --json > skylos-deadcode.json` |

---

## Methodology Notes

1. **Bandit** was run with `--severity-level medium` (MEDIUM+ only). A secondary scan at all levels confirmed only 59 LOW findings exist.
2. **Vulture** was run with `--min-confidence 80` to reduce false positives. 78 of 84 findings are test fixture variables (false positives inherent to pytest's injection model).
3. **Radon CC** was filtered to grade C and above (`-n C`). Grade A/B functions (CC 1–10) are healthy and excluded.
4. **Radon MI** was run unfiltered. The MI scale: A (100–20) very maintainable, B (19–10) medium, C (9–0) unmaintainable.
5. **Skylos 3.4.3** was run at ≥80% confidence. The 80 "unused function" findings were all confirmed false positives during manual review (decorators, `__all__` exports, cross-module calls invisible to Skylos's single-pass analysis). This is documented in the prior session handoff.
6. **Cross-referencing** confirmed the tools are complementary: Vulture finds unused variables, Skylos finds unused functions/imports/classes. Zero overlap on non-trivial findings — both are needed for complete coverage.
