# Tap Tone Pi — Project Roadmap

**Last Updated:** 2026-02-18

This document consolidates all development phases and tracks progress toward making Tap Tone Pi a professional-grade audio analyzer.

---

## Executive Summary

| Phase | Status | Description |
|-------|--------|-------------|
| Foundation (v1.0-v2.0) | ✅ Complete | Schema registry, quality gate, operator loop |
| Product Features (v2.1-v2.2) | ✅ Complete | Agent layer, GUI polish, auto-trigger, session browser |
| Phase 1: CLI UX | ✅ Complete | Error handling, preflight, API docs |
| Phase 2: Test Hardening | ✅ Complete | Unit tests, retry logic, validators |
| **Codebase Audit 2026** | ✅ Complete | 4 CRITICAL, 8 MODERATE, 7 MINOR physics fixes |
| **Advanced Physics Design** | ✅ Complete | Inverse solver, γ calibration, Rayleigh-Ritz |
| **Phase 3: Analyzer Value** | ✅ Complete | All items complete — v2.3.0-alpha.4 through v2.3.0-alpha.7 |

---

## Completed: Foundation (v1.0.0 — v2.0.0)

### v1.0.0 — Schema & Contracts (2026-01-18)
- [x] Schema registry (`contracts/schema_registry.json`)
- [x] Contracts: `tap_peaks`, `moe_result`, `measurement_manifest`, `chladni_run`
- [x] Phase-2 schemas: `phase2_ods_snapshot`, `phase2_wolf_candidates`
- [x] Registry-driven validator
- [x] Canonical WAV I/O (`modes/_shared/wav_io.py`)
- [x] CI quality gates (coverage ≥80%, WAV guard, schema validation)

### v1.1.0 — Gold Run Command (2026-01-21)
- [x] `tap_tone gold-run` — one-command capture → export → validate
- [x] `--dry-run` mode for testing without hardware
- [x] Exit code contract (0=success, 2=validation, 3=capture, 4=device, 5=unexpected)

### v1.2.0 — Auto-Trigger Capture (2026-01-21)
- [x] `--auto-trigger` flag for hands-free impulse detection
- [x] EMA noise floor estimation
- [x] Configurable trigger parameters (peak/RMS multipliers, debounce, pre/post roll)
- [x] Clipping detection with reject/accept option
- [x] 22 unit tests for auto-trigger

### v2.0.0 — Package Consolidation (2026-02-05)
- [x] Unified `tap_tone_pi/` package (from 3 fragmented packages)
- [x] Quality Gate system (HARD rules Q001-Q005, SOFT rules Q010-Q013)
- [x] `quality_check.json` emitted for every capture
- [x] Operator Loop workflow (IDLE → PREFLIGHT → CAPTURING → ANALYZING → GATING)
- [x] Attempt tracking with retry/override support
- [x] CLI entry point: `ttp` (primary)
- [x] 89 tests for quality gate + workflow
- [x] 7,305 lines deleted (legacy cleanup)

---

## Completed: Product Features (v2.1.0 — v2.2.5)

### v2.1.0 — Agent Layer & GUI Polish (2026-02-07)
- [x] **Agentic Layer** (`tap_tone_pi.agent`)
  - `MeasurementAgent` — stateful conductor for measurement workflows
  - Rule → explanation → suggestion tables
  - FTUE (First-Time User Experience) with progressive disclosure
  - CLI and GUI renderers
- [x] **GUI Widgets** (`tap_tone_pi.gui.widgets`)
  - `AudioLevelMeter` — real-time level visualization
  - `StatusBar` — color-coded operation feedback
  - `DeviceSelector` — audio device dropdown with test button
  - `SetupWizardDialog` — in-GUI hardware configuration
  - `CaptureProgressDialog` — visual feedback during capture
- [x] **Session Browser** — `SessionBrowserDialog` for viewing past measurements
- [x] **Pack Diff Tooling** — `tap_tone_pi.core.session_diff` module
- [x] **Session Metadata Export** — `meta/session_meta.json` in viewer packs
- [x] **Multi-point Grid** — `tap_tone_pi.core.grid` module
- [x] **Auto-Trigger Detector** — `tap_tone_pi.core.auto_trigger`
- [x] Keyboard shortcuts (Ctrl+B, Ctrl+O, Ctrl+Q, Ctrl+W, Ctrl+D, Ctrl+G, F1)
- [x] 192 tests for agent layer + 36 tests for new features

### v2.2.0-v2.2.5 — GUI Integration & Events (2026-02-08/09)
- [x] GUI Auto-Trigger Integration (listening state, SNR feedback, timeout)
- [x] GUI Export Viewer Pack (one-click export, validation, 11 tests)
- [x] Directive schema cleanup (dataclass migration, frozen contracts)
- [x] Moment detection (MOM-004 CONFIDENCE_CLIMB, MOM-005 TRUST_EROSION)
- [x] 8 moment-detection tests

---

## Completed: Phase 1 — CLI UX Improvements

**Goal:** Professional-grade command-line experience

### 1.1 Error Handling System ✅
- [x] Custom exception hierarchy (`TapToneError` base)
  - `DeviceError`, `DeviceNotFoundError`, `DeviceOpenError`
  - `CaptureError`, `CaptureTimeoutError`
  - `AnalysisError`, `QualityError`, `ValidationError`
  - `FileFormatError`, `ConfigError`
- [x] All exceptions support `suggestion` parameter
- [x] `RetryConfig` and `@with_retry` decorator
- [x] `ErrorContext` for rich error messages
- [x] `format_error_for_user()` utility
- [x] `handle_device_error()` for device-specific errors

### 1.2 Capture Module Refactor ✅
- [x] `tap_tone_pi/capture/__init__.py` as canonical location
- [x] Lazy imports for numpy/sounddevice (faster CLI startup)
- [x] `CaptureResult` dataclass
- [x] `list_devices()` with error handling
- [x] `record_audio()` with full validation
- [x] `auto_detect_device()` with priority order
- [x] Lazy-loaded auto-trigger exports

### 1.3 Documentation ✅
- [x] `docs/API.md` — comprehensive API reference
- [x] `docs/QUICK_START.md` — getting started guide
- [x] `docs/ANALYZER_COMPARISON.md` — commercial comparison & gap analysis

---

## Completed: Phase 2 — Test Hardening

**Goal:** Bulletproof reliability and maintainability

### 2.1 Unit Tests ✅
- [x] `tests/test_core_errors.py` — 35 tests for error system
  - Exception hierarchy tests
  - RetryConfig tests
  - @with_retry decorator tests (success, failure, backoff)
  - ErrorContext tests
  - format_error_for_user tests
  - handle_device_error tests
- [x] Total test count: 961 passing

### 2.2 Validators ✅
- [x] `tap_tone_pi/cli/validators.py`
  - `validate_device_index()`
  - `validate_output_dir()`
  - `validate_sample_rate()`
  - `validate_duration()`
  - `validate_file_exists()`
  - `confirm_overwrite()`
  - `confirm_action()`

### 2.3 Preflight Checks ✅
- [x] `tap_tone_pi/cli/preflight.py`
  - `PreflightResult` dataclass
  - `run_preflight()` — hardware verification
  - `print_preflight_result()` — console output
  - `require_preflight()` — blocking check

---

## Completed: Codebase Audit 2026 (2026-02-17)

**Goal:** Fix physics calculation errors and numerical issues identified in production review

**See:** [CODEBASE_AUDIT_2026.md](CODEBASE_AUDIT_2026.md) for full details

### CRITICAL Fixes (4) — All Complete ✅

| ID | Issue | Impact | Fix |
|----|-------|--------|-----|
| C1 | MOE missing Timoshenko shear | 8-15% overestimation | Added shear correction for L/h < 25 |
| C2 | FFT confidence not physics-based | False confidence | SNR + coherence + spectral flatness |
| C3 | No TF uncertainty propagation | No quality assessment | σ_H/|H| = √[(1-γ²)/(2nγ²)] |
| C4 | Hardcoded epsilon (1e-18) | Numerical instability | Adaptive dtype-aware epsilon |

### MODERATE Fixes (8) — All Complete ✅

| ID | Issue | Fix |
|----|-------|-----|
| M1 | Linear fit no validation | Min 3 points, condition < 10⁴ |
| M2 | Brittle percentile | Bounds [0.1, 99.9], fallback |
| M3 | Auto-trigger no settling | 50ms settling time |
| M4 | Hardcoded 5 Hz tolerance | Frequency-relative tolerance |
| M5 | No Phase 1/2 cross-validation | Mode-linking function |
| M6 | Sample rate not enforced | AudioContainer with validation |
| M7 | Arbitrary diff threshold | GUM-compliant significance |
| M8 | Float comparison tolerance | Domain-specific tolerances |

### MINOR Fixes (7) — All Complete ✅

| ID | Issue | Fix |
|----|-------|-----|
| m1 | Scattered constants | Centralized config |
| m2 | Undocumented window | Docstring added |
| m3 | Unjustified filter order | Documented 24 dB/octave |
| m4 | Grid ID breaks at 26 | Extended AA, AB pattern |
| m5 | Untested retry decorator | Full branch coverage |
| m6 | Conservative clipping | 0.995 threshold |
| m7 | Missing type hints | All public API annotated |

### New Features from Audit

| Feature | Description |
|---------|-------------|
| Gore-Style Stiffness Index | SI = E × h³, instrument presets, cross-validation |
| QA/QC Lab Specification | 9-section GUM-compliant lab report |
| Phase Cross-Validation | P1 ↔ P2 mode correlation |
| AudioContainer | Immutable signal + sample_rate bundle |

**Tests Added:** 88 new tests (Gore: 53, QA Lab: 35)

---

## Completed: Advanced Physics Design Module (2026-02-18)

**Goal:** Physics-driven design tools for plate thickness optimization

### Inverse Thickness Solver ✅

Given target frequencies, solve for optimal plate thickness.

| Component | Description |
|-----------|-------------|
|  enum | SIMPLE (closed-form) vs RAYLEIGH_RITZ (variational) |
|  | Min/max bounds, discretization steps |
|  | Single-target optimization |
|  | Multi-target weighted optimization |
|  | Material property container |
|  | Joint material + thickness selection |

**Note:** Rayleigh-Ritz with simply-supported BC gives ~3× lower frequencies than free plate formula (physically correct).

### γ Calibration Tool ✅

Derive transfer coefficient γ = f_box / f_free from measurements.

| Component | Description |
|-----------|-------------|
|  | (f_free, f_box) pair with uncertainty |
|  | Multi-mode per-specimen container |
|  | Multi-specimen statistical engine |
|  | Quick single-specimen calibration |
|  | Fleet calibration |

**Statistics:** Mean γ, std dev, 95% CI, per-mode and per-specimen breakdown

### Previously Completed Physics Modules

| Module | Description |
|--------|-------------|
| α/β formulation | Body/air coupling parameters |
| Rayleigh-Ritz solver | Variational eigenvalue solver |
| 2-oscillator coupled model | Plate + cavity coupling |
| 3-oscillator coupled model | Top + back + air |
| Calibration tables | Material property database |

**Tests Added:** 53 new tests (inverse solver: 29, γ calibration: 24)

---

## In Progress: Phase 3 — Analyzer Product Improvements

**Goal:** Close gaps with commercial analyzers to increase value proposition

Based on [ANALYZER_COMPARISON.md](ANALYZER_COMPARISON.md), these improvements can be implemented in software to significantly increase the analyzer's value.

### 3.1 Self-Calibration Workflow — P0 ✅ COMPLETED
**Gap:** No way to verify or compensate for measurement chain accuracy
**Solution:** Add loopback self-test and reference tone calibration

| Task | Status | Description |
|------|--------|-------------|
| Loopback test module | ✅ Complete | Output → input system response measurement (`calibration/loopback.py`) |
| Reference tone verification | ✅ Complete | 1 kHz known amplitude verification (`calibration/reference_tone.py`) |
| Compensation curves | ✅ Complete | Per-device calibration storage (`calibration/compensation.py`) |
| Calibration expiry | ✅ Complete | 30-day expiry with VALID/STALE status (`calibration/storage.py`) |
| CLI command | ✅ Complete | `ttp calibrate` command (`cli/calibrate.py`) |
| Hardware loopback support | ✅ Complete | `play_and_record()` function (`capture/__init__.py`) |

**Value Add:** Moves from "uncalibrated" to "user-calibrated" — closes ~50% of accuracy gap

### 3.2 Measurement Uncertainty Reporting — P0 (✅ Complete)
**Gap:** Results show single values without confidence information
**Solution:** Add uncertainty quantification to all measurements

| Task | Status | Description |
|------|--------|-------------|
| TF uncertainty propagation | ✅ Complete | σ_H/|H| = √[(1-γ²)/(2nγ²)] — Audit C3 |
| Physics-based confidence | ✅ Complete | SNR + coherence + spectral flatness — Audit C2 |
| Adaptive numerical precision | ✅ Complete | dtype-aware epsilon — Audit C4 |
| GUM-compliant diff comparison | ✅ Complete | |Δf| > k×√(u_a² + u_b²) — Audit M7 |
| Statistics module | ✅ Complete | `core/statistics.py` — Type A uncertainty, repeatability, propagation |
| Repeatability metrics | ✅ Complete | `compute_repeatability()` — CV%, repeatability limit (ISO 5725-2) |
| Uncertainty flags | ✅ Complete | `core/uncertainty_flags.py` — Quality assessment with severity levels |
| JSON schema update | ✅ Complete | `TypeAResult`, `RepeatabilityMetrics`, `QualityAssessment` dataclasses |
| CLI display | ✅ Complete | `core/format_uncertainty.py` — ±uncertainty formatting utilities |

**Completed:** Full GUM-compliant uncertainty quantification with quality flags

**Value Add:** Professional credibility, identifies questionable measurements

### 3.3 Verification Test Suite — P1 (✅ Complete)
**Gap:** No way to prove the analyzer is working correctly
**Solution:** Built-in verification tests with known results

| Task | Status | Description |
|------|--------|-------------|
| Synthetic test signals | ✅ Complete | `signal_gen/` — sine, sweep, chirp, noise, impulse, multitone, comb |
| Expected vs actual | ✅ Complete | `verify/tests.py` — frequency, amplitude, peak, noise, THD, latency |
| Pass/fail report | ✅ Complete | `verify/report.py` — JSON export, colored CLI output |
| CLI command | ✅ Complete | `cli/verify.py` — `ttp verify`, `--quick`, `--verbose`, `--output` |

**Completed:** Full verification suite with 10 built-in tests, 51 unit tests passing

### 3.4 Signal Generator Module — P1 (✅ Complete)
**Gap:** Cannot perform stimulus-response testing without external generator
**Solution:** Add integrated signal generator

| Task | Status | Description |
|------|--------|-------------|
| Waveform generators | ✅ Complete | `signal_gen/generators.py` — sine, square, triangle, noise |
| Sweep generator | ✅ Complete | Linear (`linear`) and logarithmic (`logarithmic`) sweeps |
| Multi-tone generator | ✅ Complete | `generate_multitone()` for IMD testing |
| Chirp generator | ✅ Complete | `generate_chirp()` for impulse response |
| CLI command | ✅ Complete | `cli/generate.py` — `ttp generate sine/sweep/noise/impulse/multitone/comb` |
| GUI integration | ⬜ Pending | Generator controls in GUI |

**Completed:** Full signal generator with WAV export, 24 unit tests passing

### 3.5 Limit/Mask Testing — P1 ✅ Complete (Sprint LME, v2.3.0-alpha.7)

| Task | Status | Description |
|------|--------|-------------|
| Limit curve format | ✅ Complete | `limits/curves.py` — LimitCurve, LimitPoint, JSON serialization |
| Mask regions | ✅ Complete | `limits/masks.py` — FrequencyMask, exclude regions from testing |
| Pass/fail with margin | ✅ Complete | `limits/testing.py` — check_against_limits(), PASS/WARN/FAIL verdict |
| Template library | ✅ Complete | `limits/presets.py` — tonewood_tap, speaker_response, noise_floor, calibration_flat |
| CLI integration | ✅ Complete | `cli/limits_integration.py` — `--limits`, `--limits-preset`, `--limits-fail` flags |
| Limit editor | ✅ Complete | `analyzer/widgets/limit_overlay.py` — renders limit curves on spectrum, PASS/WARN/FAIL badge |
| Limit editor panel | ✅ Complete | `analyzer/widgets/limit_editor_panel.py` — QDockWidget: preset picker, verdict card, violations list |

**Sprint LME delivered:** 25 tests passing. Limit curves rendered as dashed overlays on `ax_mag`. Unit conversion (dB ↔ linear) handled internally. Violation markers drawn at offending frequencies. Warn margin adjustable via panel spinner. Preset load and JSON file load both wired to `main_window.py`.

### 3.6 Application Notes — P2 ✅
**Gap:** Users don't know how to apply the analyzer to their problems
**Solution:** Create application-specific guides

| Note | Status | Description |
|------|--------|-------------|
| AN-001 | ✅ Complete | Measuring frequency response of a speaker |
| AN-002 | ✅ Complete | Finding resonant modes in a plate |
| AN-003 | ✅ Complete | Transfer function measurement setup |
| AN-004 | ✅ Complete | Coherence and measurement quality |
| AN-005 | ✅ Complete | Comparing two specimens |

**Value Add:** Reduces learning curve, demonstrates capability

### 3.7 Rub & Buzz Detection — P2 ✅
**Gap:** Cannot detect mechanical defects
**Solution:** Add time-domain analysis for transient defects

| Task | Status | Description |
|------|--------|-------------|
| Swept sine integration | ✅ Complete | Requires signal generator |
| Envelope tracking | ✅ Complete | Detect intermittent contact |
| Frequency-dependent threshold | ✅ Complete | Adaptive detection |
| Defect classification | ✅ Complete | Approximate defect position |

**Value Add:** Speaker/driver QC, acoustic defect detection

### 3.8 Theory Documentation — P2 ✅
**Gap:** Users don't understand what the numbers mean
**Solution:** Add theory of operation docs

| Topic | Status | Description |
|-------|--------|-------------|
| FFT fundamentals | ✅ Complete | Windowing, resolution, leakage |
| Coherence interpretation | ✅ Complete | What coherence tells you |
| Transfer function meaning | ✅ Complete | H1, H2, Hv estimators |
| Uncertainty and averaging | ✅ Complete | Why average, how many |
| Common measurement errors | ✅ Complete | Pitfalls and how to avoid |

**Value Add:** User confidence, fewer support questions

---

## Phase 3 Implementation Order

```
P0 (Foundation - Do First)
├── 3.1 Self-Calibration Workflow
└── 3.2 Uncertainty Reporting

P1 (Feature Parity - Do Second)
├── 3.3 Verification Test Suite
├── 3.4 Signal Generator Module
└── 3.5 Limit/Mask Testing

P2 (Differentiation - Do Third)
├── 3.6 Application Notes (3-5)
├── 3.7 Rub & Buzz Detection
└── 3.8 Theory Documentation
```

---

## Value Proposition After Phase 3

### Current State (After Phase 2)
```
Cost: $200
Capability: ~90% of $10k analyzer for relative measurements
Strengths: Quality gate, operator loop, auto-trigger, pack export
Limitations: No calibration, no generator, limited documentation
```

### Phase 3 Completion Summary (v2.3.0-alpha.4 through v2.3.0-alpha.7)
```
Cost: $200 (software only)
Capability: ~95% of $10k analyzer
New: Self-calibration, uncertainty reporting, signal generator, verification
```

### Positioning Statement

> **Tap Tone Pi Analyzer**: A $200 open-source audio analyzer delivering professional-grade spectral analysis, transfer function measurement, and quality control capabilities. Self-calibration and uncertainty reporting provide confidence in results. Native Python scripting enables unlimited customization and automation. Ideal for R&D, education, small-scale production QC, and applications where ±0.5 dB accuracy is sufficient.

---

## What Cannot Be Closed (Hardware Limitations)

These gaps require hardware changes and are **not targeted**:

1. **Noise floor below -90 dBV** — Requires better ADC/preamp
2. **Dynamic range beyond 96 dB** — Requires better ADC
3. **NIST-traceable calibration** — Requires certified reference equipment
4. **Sub-millisecond latency** — Requires dedicated DSP/FPGA
5. **64+ channel synchronized capture** — Requires specialized hardware

For applications requiring these specifications, commercial analyzers remain appropriate.

---

## Test Coverage Summary

| Component | Tests | Status |
|-----------|-------|--------|
| Core errors | 35 | ✅ |
| Quality gate | 89 | ✅ |
| Agent layer | 192 | ✅ |
| Auto-trigger | 22 | ✅ |
| Session diff | 15 | ✅ |
| GUI export | 11 | ✅ |
| Moment detection | 8 | ✅ |
| Rub & Buzz | 27 | ✅ |
| **Codebase Audit fixes** | **88** | ✅ |
| **Gore Stiffness + QA Lab** | **88** | ✅ |
| **Inverse Solver** | **29** | ✅ |
| **γ Calibration** | **24** | ✅ |
| DSP cross-validation | 21 | ✅ |
| Advisory boundary | 16 | ✅ |
| Calibration gate + export | 38 | ✅ |
| **Analyzer Guidance Engine** | **19** | ✅ |
| **Limit curve overlay** | **25** | ✅ |
| **Whole-plate bending** | **31** | ✅ |
| **Total** | **~2,150+** | ✅ |

---

---

## Phase 4: Production Shop Integration

**Status:** Planning
**Target version:** v2.4.x
**Prerequisite:** v2.3.0-alpha.7 tag (all Phase 3 items complete)

The viewer_pack_v1 bundle now carries everything the Production Shop inverse brace engine needs — modal peaks, transfer function, coherence, wood properties, and bending stiffness. Phase 4 closes the loop from measurement to prescription.

| Item | Priority | Description |
|------|----------|-------------|
| ADR-0009 markdown document | P0 | Write `docs/ADR-0009-advisory-boundary.md` — the CI gate references it but the file does not exist |
| Inverse brace engine integration | P0 | Wire viewer_pack_v1 export into Production Shop `inverse_optimizer.py` |
| Bending data in viewer_pack_v1 | P1 | Add `bending/` section to viewer_pack_v1 schema; update `export_viewer_pack_v1.py` |
| Cross-session comparison | P1 | Load two packs and diff modal frequencies — before/after bracing workflow |
| `--method full_plate` auto Poisson | P2 | Lookup table: species → default Poisson ratio so `--poisson` is not required |
| Analyzer guidance: full-analysis trigger | P2 | Add `on_full_analysis_complete` trigger to `AnalyzerGuidanceEngine` for workflow summary |

## References


- [ANALYZER_COMPARISON.md](ANALYZER_COMPARISON.md) — Commercial analyzer comparison
- [API.md](API.md) — API reference
- [QUICK_START.md](QUICK_START.md) — Getting started guide
- [MEASUREMENT_BOUNDARY.md](MEASUREMENT_BOUNDARY.md) — Scope and limitations
- [CHANGELOG.md](../CHANGELOG.md) — Version history
- [CODEBASE_AUDIT_2026.md](CODEBASE_AUDIT_2026.md) — Technical debt fixes (CRITICAL/MODERATE/MINOR)
- [Critical Design Review_tap-tone-pi.md](../Critical%20Design%20Review_tap-tone-pi.md) — 9-category design review
