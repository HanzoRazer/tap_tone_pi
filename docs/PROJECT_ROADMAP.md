# Tap Tone Pi — Project Roadmap

**Last Updated:** 2026-02-17

This document consolidates all development phases and tracks progress toward making Tap Tone Pi a professional-grade audio analyzer.

---

## Executive Summary

| Phase | Status | Description |
|-------|--------|-------------|
| Foundation (v1.0-v2.0) | ✅ Complete | Schema registry, quality gate, operator loop |
| Product Features (v2.1-v2.2) | ✅ Complete | Agent layer, GUI polish, auto-trigger, session browser |
| Phase 1: CLI UX | ✅ Complete | Error handling, preflight, API docs |
| Phase 2: Test Hardening | ✅ Complete | Unit tests, retry logic, validators |
| **Phase 3: Analyzer Value** | 🔄 In Progress | Self-calibration, uncertainty, signal generator |

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

## 🔄 Phase 3: Analyzer Product Improvements

**Goal:** Close gaps with commercial analyzers to increase value proposition

Based on [ANALYZER_COMPARISON.md](ANALYZER_COMPARISON.md), these improvements can be implemented in software to significantly increase the analyzer's value.

### 3.1 Self-Calibration Workflow — P0 (Highest Priority)
**Gap:** No way to verify or compensate for measurement chain accuracy
**Solution:** Add loopback self-test and reference tone calibration

| Task | Status | Description |
|------|--------|-------------|
| Loopback test module | ⬜ Pending | Output → input system response measurement |
| Reference tone verification | ⬜ Pending | 1 kHz known amplitude verification |
| Compensation curves | ⬜ Pending | Per-device calibration storage |
| Calibration expiry | ⬜ Pending | Warn when calibration is stale |
| CLI command | ⬜ Pending | `ttp calibrate` command |

**Value Add:** Moves from "uncalibrated" to "user-calibrated" — closes ~50% of accuracy gap

### 3.2 Measurement Uncertainty Reporting — P0
**Gap:** Results show single values without confidence information
**Solution:** Add uncertainty quantification to all measurements

| Task | Status | Description |
|------|--------|-------------|
| Statistics module | ⬜ Pending | Mean, std dev, confidence intervals |
| Repeatability metrics | ⬜ Pending | Track measurement-to-measurement variation |
| Uncertainty flags | ⬜ Pending | Flag high-uncertainty measurements |
| JSON schema update | ⬜ Pending | Add uncertainty fields to analysis.json |
| CLI display | ⬜ Pending | Show ±uncertainty in output |

**Value Add:** Professional credibility, identifies questionable measurements

### 3.3 Verification Test Suite — P1
**Gap:** No way to prove the analyzer is working correctly
**Solution:** Built-in verification tests with known results

| Task | Status | Description |
|------|--------|-------------|
| Synthetic test signals | ⬜ Pending | Known sine, multi-tone, noise signals |
| Expected vs actual | ⬜ Pending | Comparison framework |
| Pass/fail report | ⬜ Pending | Verification report generation |
| CLI command | ⬜ Pending | `ttp verify` command |

**Value Add:** Confidence in results, troubleshooting aid

### 3.4 Signal Generator Module — P1
**Gap:** Cannot perform stimulus-response testing without external generator
**Solution:** Add integrated signal generator

| Task | Status | Description |
|------|--------|-------------|
| Waveform generators | ⬜ Pending | Sine, square, triangle, noise |
| Sweep generator | ⬜ Pending | Linear and logarithmic sweeps |
| Multi-tone generator | ⬜ Pending | For IMD testing |
| Chirp generator | ⬜ Pending | For impulse response |
| CLI command | ⬜ Pending | `ttp generate` command |
| GUI integration | ⬜ Pending | Generator controls in GUI |

**Value Add:** Enables closed-loop testing, frequency response sweeps

### 3.5 Limit/Mask Testing — P1
**Gap:** Quality gates exist but no visual limit curves
**Solution:** Add graphical limit testing

| Task | Status | Description |
|------|--------|-------------|
| Limit curve format | ⬜ Pending | JSON schema for upper/lower limits |
| Limit editor | ⬜ Pending | Draw/import limit curves |
| Pass/fail with margin | ⬜ Pending | Calculate margin to limit |
| Template library | ⬜ Pending | Common test templates |
| CLI integration | ⬜ Pending | `--limits` flag for measurements |

**Value Add:** Production QC capability, visual pass/fail

### 3.6 Application Notes — P2
**Gap:** Users don't know how to apply the analyzer to their problems
**Solution:** Create application-specific guides

| Note | Status | Description |
|------|--------|-------------|
| AN-001 | ⬜ Pending | Measuring frequency response of a speaker |
| AN-002 | ⬜ Pending | Finding resonant modes in a plate |
| AN-003 | ⬜ Pending | Transfer function measurement setup |
| AN-004 | ⬜ Pending | Coherence and measurement quality |
| AN-005 | ⬜ Pending | Comparing two specimens |

**Value Add:** Reduces learning curve, demonstrates capability

### 3.7 Rub & Buzz Detection — P2
**Gap:** Cannot detect mechanical defects
**Solution:** Add time-domain analysis for transient defects

| Task | Status | Description |
|------|--------|-------------|
| Swept sine integration | ⬜ Pending | Requires signal generator |
| Envelope tracking | ⬜ Pending | Detect intermittent contact |
| Frequency-dependent threshold | ⬜ Pending | Adaptive detection |
| Defect location estimation | ⬜ Pending | Approximate defect position |

**Value Add:** Speaker/driver QC, acoustic defect detection

### 3.8 Theory Documentation — P2
**Gap:** Users don't understand what the numbers mean
**Solution:** Add theory of operation docs

| Topic | Status | Description |
|-------|--------|-------------|
| FFT fundamentals | ⬜ Pending | Windowing, resolution, leakage |
| Coherence interpretation | ⬜ Pending | What coherence tells you |
| Transfer function meaning | ⬜ Pending | H1, H2, Hv estimators |
| Uncertainty and averaging | ⬜ Pending | Why average, how many |
| Common measurement errors | ⬜ Pending | Pitfalls and how to avoid |

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

### Target State (After Phase 3 P0+P1)
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
| **Total** | **961** | ✅ |

---

## References

- [ANALYZER_COMPARISON.md](ANALYZER_COMPARISON.md) — Commercial analyzer comparison
- [API.md](API.md) — API reference
- [QUICK_START.md](QUICK_START.md) — Getting started guide
- [MEASUREMENT_BOUNDARY.md](MEASUREMENT_BOUNDARY.md) — Scope and limitations
- [CHANGELOG.md](../CHANGELOG.md) — Version history
