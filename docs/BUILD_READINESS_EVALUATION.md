# tap_tone_pi Build Readiness Evaluation

**Date:** 2025-12-31
**Evaluated by:** Claude Code
**Overall Readiness:** 65-70%

---

## Component Breakdown

| Component | % Complete | Status | Notes |
|-----------|-----------|--------|-------|
| **Phase 1 (tap_tone/)** | 95% | Ready | CLI complete, capture + analysis working |
| **Phase 2 DSP/Metrics** | 95% | Ready | Coherence, WSI, provenance all implemented |
| **Phase 2 I/O Layer** | 30% | **BLOCKED** | Outputs don't match v2 schemas |
| **Bending Rig** | 85% | Ready | Complete with serial + simulators |
| **Dependencies** | 100% | Ready | pyproject.toml fully configured |
| **CI/Workflows** | 90% | Mature | 6 workflows, path-based gates |
| **Tests** | 20% | Poor | Only Phase 1 schema tests exist |

---

## Phase 1 (tap_tone/) - 95% Complete

**Status: FUNCTIONALLY COMPLETE**

### main.py Commands:
- `cmd_devices()` - Lists audio devices via sounddevice
- `cmd_record()` - Records, analyzes, and persists single tap
- `cmd_live()` - Continuous loop mode with Ctrl+C support

### Supporting Modules (415 lines total):
- `capture.py` (44 lines) - sounddevice integration, mono recording
- `analysis.py` (133 lines) - FFT peak detection, tap analysis
- `storage.py` (89 lines) - Persists audio WAV + JSON analysis
- `config.py` (19 lines) - CaptureConfig and AnalysisConfig dataclasses
- `ui_simple.py` - Summary printing

### What Works:
- Real-time audio capture (48kHz default, 2.5s default duration)
- Peak detection with prominence/distance/frequency range controls
- Confidence scoring heuristic
- Per-capture JSON output + CSV spectrum export
- Session-wide JSONL log for repeated runs

### Minor Gap:
- No jsonschema validation against Phase 1 schemas

---

## Phase 2 (scripts/phase2/) - 60% Complete

**Status: PARTIALLY COMPLETE - CRITICAL SCHEMA MISMATCHES**

### phase2_slice.py (439 lines) - What Works:
- `cmd_run()` - Full vertical slice workflow
- `cmd_devices()` - Audio device enumeration
- Grid loading from JSON
- Synthetic signal generation (6 harmonics, point-dependent modulation)
- Hardware 2-channel capture via sounddevice
- WAV file I/O (read/write 2-channel float32→int16)
- Transfer function computation (Welch cross-spectrum method)
- Coherence calculation (MSC: magnitude-squared coherence)
- WSI curve generation with admissibility gating
- ODS snapshot at target frequency
- Visualization (heatmap scatter + curve plots)

### Phase 2 DSP Module (94 lines) - Complete:
- `compute_transfer_and_coherence()` - Uses scipy.signal.csd/welch
- `get_dsp_provenance()` - Tracks algo_id, versions, numpy/scipy versions
- `TFResult` dataclass with freq_hz, H, H_mag, H_phase_deg, coherence, pxx, pyy
- Band-limiting (fmin_hz/fmax_hz)
- Nearest-bin frequency lookup

### Phase 2 Metrics Module (214 lines) - Complete:
- `PointSpectrum` dataclass for grid point results
- `build_adjacency()` - 4-nearest-neighbor spatial adjacency
- `compute_localization_index()` - max/mean magnitude ratio
- `compute_energy_gradient()` - normalized neighbor differences
- `compute_phase_disorder()` - circular dispersion
- `compute_wsi()` - Composite score with coherence gating
- `wsi_curve()` - Per-frequency WSI computation
- `get_metrics_provenance()` - Nested provenance export

---

## CRITICAL ISSUE: Schema Compliance Mismatch

The code is **NOT generating output matching the contracts/**:

### wolf_candidates.json

| Schema v2 Requires | Code Actually Writes |
|--------------------|---------------------|
| schema_version | (missing) |
| wsi_threshold | (missing) |
| coherence_threshold | (missing) |
| candidates[].admissible | (missing) |
| candidates[].coh_mean | (missing) |
| candidates[].top_points[] | (missing) |
| provenance{} | (missing) |

### ods_snapshot.json

| Schema v2 Requires | Code Actually Writes |
|--------------------|---------------------|
| schema_version | (missing) |
| capdir | (missing) |
| freqs_hz[] | frequency_hz_actual (single value) |
| points[].coherence[] | (missing) |
| provenance{} | (missing) |

---

## Hardware Integration - 85% Complete

### Complete Modules:
- `modes/acquisition/loadcell_serial.py` (154 lines) - pyserial CSV/regex parsing
- `modes/acquisition/loadcell_sim.py` (67 lines) - Deterministic simulation
- `modes/acquisition/dial_indicator_serial.py` (106 lines) - Serial dial capture
- `modes/acquisition/dial_indicator_sim.py` (66 lines) - Dial simulator

### Bending Rig Analysis (Complete):
- `modes/bending_rig/merge_and_moe.py` - Force vs displacement → MOE
- `modes/bending_rig/plot_f_vs_d.py` - Linear fit visualization
- Makefile with 20+ targets

---

## Test Coverage - 20% Complete

### Current Tests:
- 1 test file: `tests/test_measurement_schemas.py` (26 lines)
- Tests Phase 1 schemas only (tap_peaks, moe_result, manifest)
- No Phase 2 schema validation
- No pytest for phase2_slice.py pipeline

### Missing:
- Unit tests for Phase 2 DSP
- Integration tests for phase2_slice.py with synthetic data
- Phase 2 schema validation tests
- Regression tests for real hardware capture

---

## CI/Build Validation - 90% Complete

### GitHub Workflows (6 total):
1. `phase2_validate.yml` - Schema well-formedness + provenance checks + docs sync
2. `schemas_validate.yml` - Phase 1 schema validation against examples
3. `bending_stiffness_validate.yml` - Bending mode validation
4. `boundary_guard.yml` - Import boundary enforcement
5. `examples_matrix.yml` - Multi-version example validation
6. `no_logic_creep.yml` - Code organization checks

### Makefile:
- 20+ documented targets with defaults
- Full phase2 pipeline: `make phase2-full GRID=... DEVICE=...`
- Phase 2 analysis-only: `make phase2-analyze CAPDIR=...`

---

## Path to 100% Readiness

| Task | Effort | Priority | Status |
|------|--------|----------|--------|
| Fix phase2_slice.py output to match v2 schemas | 1-2 hrs | **CRITICAL** | TODO |
| Wire provenance into JSON outputs | 1 hr | HIGH | TODO |
| Add Phase 2 pytest suite | 4-6 hrs | HIGH | TODO |
| Verify CI passes | 0.5 hr | MEDIUM | TODO |

**Total estimated effort: 6-9 hours**

---

## Recent Patches Applied (2025-12-31)

### Patch 08 - Provenance Stamps
- Added `DSP_ALGO_VERSION`, `get_dsp_provenance()` to dsp.py
- Added `METRICS_ALGO_VERSION`, `get_metrics_provenance()` to metrics.py
- Updated ods_snapshot schema to v2 with provenance block
- Updated wolf_candidates schema to v2 with provenance block

### Patch 09 - Coherence Gating
- `compute_wsi()` now returns `(wsi, admissible)` tuple
- Added `coherence_threshold` parameter (default 0.7)
- Updated wolf_candidates schema with `admissible`, `coh_mean` fields

### Patch 12 - CI Path Gates
- Created `phase2_validate.yml` workflow
- Path-based triggers for scripts/phase2/**, contracts/phase2_*
- Validates schemas, checks docs sync, verifies provenance exports

---

## Next Steps

1. **Fix Phase 2 Output Writers** - Update `phase2_slice.py` to emit JSON matching v2 schemas
2. **Add Phase 2 Tests** - pytest suite for DSP/metrics modules
3. **End-to-end Validation** - Run synthetic pipeline, validate outputs against schemas
