# Gap Inventory — Modal Mapping & Measurement Toolchain

**Purpose:** Honest assessment of what exists in `tap_tone_pi` repo versus what scanning modal mapping needs. Written 2026-05-01 against the repo state in `luthiers-toolbox-main__36__7z` and `tap_tone_pi-main__10_.zip`.

**Reading order:** This document lists capabilities by status (shipped / partial / missing). Use it to decide what to build and what to leave alone. Section IDs are referenced by the dev orders.

---

## Status legend

- **SHIPPED** — Code exists, tested, working. Do not rebuild.
- **PARTIAL** — Code exists for part of the workflow, gaps in specific areas.
- **MISSING** — No code, must be written.
- **DESIGN-ONLY** — Hardware/process not yet built.

---

## §1 — Spatial scanning workflow (Phase 2 / ODS)

| ID | Capability | Status | Notes |
|---|---|---|---|
| 1.1 | Grid definition schema | **SHIPPED** | `contracts/phase2_grid.schema.json`, `examples/phase2_grid_mm.json` |
| 1.2 | Per-point capture metadata schema | **SHIPPED** | `contracts/phase2_point_capture_meta.schema.json` |
| 1.3 | Session state with resume support | **SHIPPED** | `tap_tone_pi/phase2/session_state.py` |
| 1.4 | Grid display for capture progress | **SHIPPED** | `tap_tone_pi/phase2/grid_display.py` |
| 1.5 | Coherence gating per point | **SHIPPED** | `tap_tone_pi/phase2/coherence_gate.py` |
| 1.6 | Phase 2 vertical-slice runner | **SHIPPED** | `scripts/phase2_slice.py` (synthetic + hardware paths) |
| 1.7 | Transfer function + coherence DSP | **SHIPPED** | `scripts/phase2/dsp.py` |
| 1.8 | 2D scatter heatmap of point values | **SHIPPED** | `scripts/phase2/viz.py: heatmap_scatter()` |
| 1.9 | WSI (weighted shape index) curve | **SHIPPED** | `scripts/phase2/metrics.py` |
| 1.10 | Viewer pack v1 export | **SHIPPED** | `scripts/phase2/export_viewer_pack_v1.py` |
| 1.11 | CLI entry point | **SHIPPED** | `tap_tone_pi/cli/main.py: cmd_phase2` |

**§1 honest assessment:** Far more complete than I initially indicated. The Phase 2 ODS workflow is the modal-scanning capability. Schemas, capture, DSP, visualization, and export all exist. What's missing is the next layer above this (see §3, §4).

---

## §2 — Single-point measurement & analysis

| ID | Capability | Status | Notes |
|---|---|---|---|
| 2.1 | Calibrated audio capture | **SHIPPED** | `tap_tone_pi/capture/`, `tap_tone_pi/calibration/` |
| 2.2 | Loopback calibration | **SHIPPED** | `tap_tone_pi/calibration/loopback.py` |
| 2.3 | Reference tone amplitude verification | **SHIPPED** | `tap_tone_pi/calibration/reference_tone.py` |
| 2.4 | Frequency response compensation | **SHIPPED** | `tap_tone_pi/calibration/compensation.py` |
| 2.5 | Signal generators (sine/sweep/noise/multitone/impulse/comb) | **SHIPPED** | `tap_tone_pi/signal_gen/generators.py` |
| 2.6 | Signal writer (WAV output) | **SHIPPED** | `tap_tone_pi/signal_gen/writer.py` |
| 2.7 | FFT + peak picking | **SHIPPED** | `tap_tone_pi/chladni/peaks_from_wav.py` |
| 2.8 | Frequency tolerance policy (relative/semitone/fixed) | **SHIPPED** | `tap_tone_pi/chladni/policy.py` |
| 2.9 | Damping (Q) measurement | **SHIPPED** | `tap_tone_pi/damping/modes.py` |
| 2.10 | Multi-tap statistical analysis | **SHIPPED** | `tap_tone_pi/multitap/` |
| 2.11 | Wolf tone detection | **SHIPPED** | `tap_tone_pi/wolf/` |
| 2.12 | Rub & buzz detection | **SHIPPED** | `tap_tone_pi/rub_buzz/` |

**§2 honest assessment:** Very mature. The single-point measurement pipeline is production-ready.

---

## §3 — Modal prediction & comparison

| ID | Capability | Status | Notes |
|---|---|---|---|
| 3.1 | Rayleigh-Ritz orthotropic plate solver | **SHIPPED** | `tap_tone_pi/design/rayleigh_ritz.py` |
| 3.2 | Coupled 2-oscillator model | **SHIPPED** | `tap_tone_pi/design/coupled_2osc.py` |
| 3.3 | Thickness calculator (target frequency → thickness) | **SHIPPED** | `tap_tone_pi/design/thickness_calculator.py` |
| 3.4 | Mode shape rendering on grid | **MISSING** | Solver outputs mode shapes mathematically; no rendering on a grid that matches measurement coordinates |
| 3.5 | Predicted-vs-measured overlay | **MISSING** | Side-by-side or differenced visualization comparing predicted φ(x,y) to measured amplitude(x,y) |
| 3.6 | Spatial residual analysis | **MISSING** | Computing where prediction agrees/disagrees with measurement, in measurable units |
| 3.7 | Prediction → grid coordinate transform | **MISSING** | Solver uses normalized plate coordinates; phase2 uses physical mm coordinates; no bridge |

**§3 honest assessment:** This is the actual gap. Prediction engine works. Measurement engine works. They don't talk to each other for spatial mode shape comparison.

---

## §4 — Desktop analyzer integration

| ID | Capability | Status | Notes |
|---|---|---|---|
| 4.1 | Main window framework | **SHIPPED** | `analyzer/main_window.py` (PyQt6) |
| 4.2 | Spectrum chart widget | **SHIPPED** | `analyzer/widgets/spectrum_chart.py` |
| 4.3 | Peaks table widget | **SHIPPED** | `analyzer/widgets/peaks_table.py` |
| 4.4 | Plate tuning widget (mass-vs-freq regression) | **SHIPPED** | `analyzer/widgets/plate_tuning.py` |
| 4.5 | Bode/transfer function plot | **SHIPPED** | `analyzer/widgets/bode_plot.py` |
| 4.6 | Limit overlay & editor | **SHIPPED** | `analyzer/widgets/limit_overlay.py`, `limit_editor_panel.py` |
| 4.7 | Guidance engine integration | **SHIPPED** | `analyzer/guidance/` |
| 4.8 | Viewer pack loader | **SHIPPED** | `analyzer/loaders/viewer_pack.py` |
| 4.9 | HTML / JSON / PDF report generation | **SHIPPED** | `analyzer/reports/` |
| 4.10 | Phase 2 / ODS results widget | **MISSING** | No GUI surface for loading and viewing scanning sessions in the desktop analyzer |
| 4.11 | 2D mode shape map widget | **MISSING** | No interactive heatmap-on-body-outline view in the analyzer (the script-side `heatmap_scatter` exists but isn't a GUI widget) |
| 4.12 | Predicted-vs-measured comparison view | **MISSING** | Depends on §3.5 |

**§4 honest assessment:** The analyzer GUI is mature for tap-test workflow but does not yet surface the Phase 2 scanning workflow at all. Phase 2 results go to viewer packs, not into the analyzer.

---

## §5 — Wood characterization & material database

| ID | Capability | Status | Notes |
|---|---|---|---|
| 5.1 | Bending stiffness MOE calculation | **SHIPPED** | `tap_tone_pi/bending/merge_and_moe.py` |
| 5.2 | Gore stiffness (orthotropic SI) | **SHIPPED** | `tap_tone_pi/bending/gore_stiffness.py` |
| 5.3 | Tonewood deflection (Euler-Bernoulli E from 3-pt bend) | **SHIPPED** | `tap_tone_pi/tonewood_deflection.py` |
| 5.4 | QA lab spec (GUM-compliant uncertainty) | **SHIPPED** | `tap_tone_pi/bending/qa_lab_spec.py` |
| 5.5 | Plot F-vs-d | **SHIPPED** | `tap_tone_pi/bending/plot_f_vs_d.py` |
| 5.6 | Dial indicator serial capture | **SHIPPED** | `tap_tone_pi/capture/dial_indicator_serial.py` |
| 5.7 | Load cell serial capture | **SHIPPED** | `tap_tone_pi/capture/loadcell_serial.py` |
| 5.8 | Wood properties analysis (in analyzer) | **SHIPPED** | `analyzer/analysis/wood_properties.py` |
| 5.9 | Per-flitch persistent database | **MISSING** | No long-term store keying measured E_L/E_C/ρ to flitch ID and supplier |
| 5.10 | Plate experiment campaign manager | **MISSING** | No workflow for running 80-plate characterization (see §6) |

**§5 honest assessment:** Single-measurement pipeline is shipped. Multi-measurement campaign and long-term database are missing.

---

## §6 — Cross-cutting gaps not yet a module

| ID | Capability | Status | Notes |
|---|---|---|---|
| 6.1 | Per-build instrument record | **MISSING** | No schema tying together: wood properties, bracing as-built, modal scans, deflection measurements, setup specs |
| 6.2 | Build-to-build comparison | **MISSING** | No way to compare modal frequencies across instruments to detect calibration drift |
| 6.3 | Tornavoz prototype tracking | **MISSING** | No schema for variable tornavoz depths and their measured effects |
| 6.4 | Body geometry import (Carlos Jumbo blueprint) | **MISSING** | Phase 2 grids are flat coordinates; no body outline overlay |
| 6.5 | Build journal integration | **MISSING** | qa_lab_spec.py is per-measurement; no per-build narrative tying many measurements together |

---

## §7 — Hardware (DESIGN-ONLY)

| ID | Hardware | Status | Notes |
|---|---|---|---|
| 7.1 | Bending rig | **DESIGN-ONLY** | Software path complete; physical fixture not built |
| 7.2 | Deflection rig | **DESIGN-ONLY** | Capture modules ready; physical fixture not built |
| 7.3 | TTP Analyzer (driven excitation hardware) | **DESIGN-ONLY** | Signal-gen software ready; transducer/amp/mic hardware not built |
| 7.4 | Body fixture (cradle for scanning) | **DESIGN-ONLY** | Required for Phase 2 with real instruments |
| 7.5 | Microphone positioning fixture | **DESIGN-ONLY** | Required for repeatable spatial sampling |
| 7.6 | Reference masses (NIST-traceable) | **DESIGN-ONLY** | Calibration metrology, not built/sourced |
| 7.7 | Tuning fork kit (chakra/Solfeggio) | **DESIGN-ONLY** | Cheap immediate option for early modal mapping |

---

## §8 — Summary: what to actually build

**Real software gaps (worth building):**
- §3.4–3.7 — Predicted-vs-measured spatial comparison (the actual analytical bridge)
- §4.10–4.12 — Analyzer GUI integration of Phase 2 scanning results
- §5.9 — Per-flitch wood properties database
- §6.1 — Per-build instrument record schema
- §6.4 — Body geometry overlay on Phase 2 grids

**Not gaps (already shipped):**
- Phase 2 / ODS scanning workflow (§1)
- Single-point measurement (§2)
- Rayleigh-Ritz solver (§3.1)
- Bending rig software (§5.1–5.8)

**Out of scope for software work:**
- Hardware (§7) — physical builds, separate timeline
- Plate experiment campaign management (§5.10) — workflow design first, code later

---

*End of gap inventory. Updated whenever the repo state changes materially.*
