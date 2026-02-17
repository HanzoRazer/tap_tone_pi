# Codebase Audit: Technical Debt Findings

**Audit Date:** 2026-02-17
**Auditor:** Production Physics Review
**Scope:** tap_tone_pi acoustic measurement package

---

## Executive Summary

This audit identified **4 CRITICAL**, **8 MODERATE**, and **7 MINOR** issues in the tap_tone_pi codebase.
Critical issues cause measurable error in physics calculations (8-15% MOE overestimation) or compromise
measurement integrity. All issues have specific file locations and remediation paths documented below.

---

## CRITICAL Issues (4)

These issues cause measurable error in physics calculations or compromise measurement integrity.

### C1. MOE Missing Timoshenko Shear Correction

**File:** `tap_tone_pi/bending/merge_and_moe.py` lines 104-117

**Problem:** The MOE calculation uses pure Euler-Bernoulli beam theory without Timoshenko shear correction. For typical soundboard specimens (L/h < 20), this causes **8-15% overestimation** of elastic modulus.

**Physics:**
```
Euler-Bernoulli (current):  E = (48 × f² × ρ × L⁴) / (π² × I)
                            [Ignores shear deformation]

Timoshenko (correct):       E_corrected = E_apparent × (1 + β)
                            where β = (12 × E × I) / (κ × G × A × L²)
                            κ = shear correction factor (≈5/6 for rectangular)
                            G = E / (2 × (1 + ν)), ν = Poisson's ratio
```

**Impact:** Incorrectly high MOE values lead to:
- Overconfidence in material stiffness
- Mismatched top/back pairings
- Incorrect thickness calculations

**Fix:** Add Timoshenko correction with configurable L/h threshold (default: apply when L/h < 25).

**See:** [Theory: MOE Shear Correction](theory/moe_shear_correction.md)

---

### C2. FFT Confidence Score Not Derived from Physics

**File:** `tap_tone_pi/core/analysis.py` lines 146-150

**Problem:** The confidence score uses an arbitrary heuristic:
```python
confidence = 0.5 + 0.5 * normalized_magnitude  # WRONG: No physical basis
```

**Correct Approach:**
```
confidence = f(SNR, coherence, spectral_flatness)

SNR contribution:    conf_snr = 1 / (1 + exp(-(SNR_dB - 20) / 5))
Coherence:           conf_coh = γ²  (direct mapping)
Spectral flatness:   conf_flat = 1 - SF  (lower flatness = more tonal = higher confidence)
```

**Impact:** Current heuristic provides false confidence for noisy measurements and underestimates confidence for clean, low-amplitude signals.

**Fix:** Replace with SNR-based derivation with coherence weighting.

**See:** [Theory: Confidence Score Derivation](theory/confidence_derivation.md)

---

### C3. No Uncertainty Propagation in Transfer Function/Coherence

**File:** `tap_tone_pi/core/dsp.py` lines 78-127

**Problem:** Transfer function and coherence calculations return point estimates without uncertainty bounds.

**Missing:**
```python
# Uncertainty in H based on coherence and averaging
σ_H / |H| = √[(1 - γ²) / (2 × n × γ²)]

# Should return:
# - H_magnitude
# - H_phase
# - coherence
# - magnitude_uncertainty  ← MISSING
# - phase_uncertainty      ← MISSING
```

**Impact:** Users cannot assess measurement quality or set valid tolerance bands.

**Fix:** Add uncertainty output based on coherence and averaging count.

---

### C4. Hardcoded Epsilon Without Numerical Justification

**File:** `tap_tone_pi/core/dsp.py` lines 98-99

**Problem:**
```python
eps = 1e-18  # WRONG: Too small for float32, arbitrary for float64
```

**Correct Approach:**
```python
# Adaptive epsilon based on data characteristics
eps = max(np.finfo(signal.dtype).eps, np.abs(denominator).max() * 1e-10)
```

**Impact:** Can cause numerical instability or unnecessarily clip valid data.

**Fix:** Use adaptive epsilon based on data magnitude and dtype.

---

## MODERATE Issues (8)

These issues affect edge cases, reduce accuracy, or create maintenance burden.

### M1. Linear Fit Missing Edge Case Validation

**File:** `tap_tone_pi/bending/merge_and_moe.py` lines 86-102

**Problem:** Linear regression proceeds without checking:
- Minimum point count (n < 3)
- Condition number (near-singular)
- Residual patterns (non-linearity detection)

**Fix:** Add validation: min 3 points, condition number < 10⁴, residual normality test.

---

### M2. Brittle Percentile Selection

**File:** `tap_tone_pi/bending/plot_f_vs_d.py` lines 39-47

**Problem:** Hardcoded percentile (5th/95th) without bounds checking. Empty arrays or outlier-dominated data cause crashes or misleading limits.

**Fix:** Add bounds: percentile clamp to [0.1, 99.9], fallback to min/max with padding.

---

### M3. Auto-Trigger Baseline Ignores Settling Dynamics

**File:** `tap_tone_pi/core/auto_trigger.py` lines 165-177

**Problem:** Baseline is calculated immediately on first N samples without waiting for:
- ADC settling (first 10-50ms after start)
- DC offset stabilization
- Transient rejection

**Fix:** Add configurable settling time (default 50ms), discard initial samples.

---

### M4. Hardcoded 5 Hz Tolerance in Pattern Matching ✅

**File:** `tap_tone_pi/chladni/policy.py` (was index_patterns.py line 24)

**Problem:** Fixed 5 Hz tolerance for frequency matching is inappropriate across the spectrum:
- At 50 Hz: 5 Hz = 10% = too loose
- At 500 Hz: 5 Hz = 1% = reasonable
- At 5000 Hz: 5 Hz = 0.1% = too tight

**Fix:** Implemented frequency-relative tolerance with configurable modes:
- `ToleranceMode.RELATIVE`: tolerance = freq × pct (default 2%)
- `ToleranceMode.SEMITONE`: tolerance = freq × (2^(cents/1200) - 1)
- `ToleranceMode.FIXED`: legacy absolute Hz mode

Environment variables: `CHLADNI_TOLERANCE_MODE`, `CHLADNI_TOLERANCE_PCT`, `CHLADNI_TOLERANCE_CENTS`

**See:** `tap_tone_pi/chladni/policy.py:ToleranceConfig.compute_tolerance_hz()`

---

### M5. No Cross-Validation Between Phase 1 and Phase 2 ✅

**File:** `tap_tone_pi/core/phase_crossval.py`

**Problem:** Phase 1 (single-channel) and Phase 2 (dual-channel) can report different frequencies for the same mode without consistency checks.

**Fix:** Implemented mode-linking function that correlates Phase 1 peaks with Phase 2 ODS results:
- `match_phases()`: Cross-validate P1 peaks against P2 modes with frequency-relative tolerance
- `MatchStatus`: MATCHED, P1_ONLY, P2_ONLY, WEAK_MATCH
- Flags inconsistencies (>30% unmatched modes)
- JSON-serializable CrossValidationResult

**See:** `tap_tone_pi/core/phase_crossval.py:match_phases()`

---

### M6. Sample Rate Consistency Not Enforced ✅

**File:** `tap_tone_pi/io/audio_container.py`

**Problem:** Functions accept sample_rate as parameter but don't validate against actual audio data.

**Fix:** Implemented AudioContainer with embedded sample rate validation:
- `AudioContainer`: Immutable dataclass bundling signal + sample_rate
- `validate_sample_rate()`: Raises SampleRateMismatchError on mismatch
- `load_wav_validated()`: Load with optional sample rate validation
- Tolerance-based validation (default 0.1%)

**See:** `tap_tone_pi/io/audio_container.py:AudioContainer`

---

### M7. Arbitrary Comparison Threshold ✅

**File:** `tap_tone_pi/core/session_diff.py` (was line 50, now `SignificanceConfig`)

**Problem:** Hardcoded threshold (e.g., 1 Hz) for "significant difference" without:
- Scaling by frequency
- Accounting for measurement uncertainty
- User configurability

**Fix:** Implemented uncertainty-based significance testing following GUM principles:
```
Significant if: |Δf| > k × √(u_a² + u_b²)
where k = coverage factor (default 2 for ~95% confidence)
```

Fallback hierarchy:
1. If uncertainties available: use combined uncertainty
2. Otherwise: relative threshold (default 0.5% of mean frequency)
3. Minimum: 0.5 Hz (FFT resolution floor)

**See:** `tap_tone_pi/core/session_diff.py:SignificanceConfig.is_significant()`

---

### M8. Missing Tolerance for Floating-Point Comparison ✅

**File:** `tap_tone_pi/testing/float_compare.py`

**Problem:** Several tests use exact equality for floating-point values.

**Fix:** Implemented domain-specific tolerance helpers:
- `TolerancePresets`: Domain-aware tolerances (frequency, magnitude, phase, stiffness)
- `approx_freq()`, `approx_magnitude()`, `approx_stiffness()`: pytest.approx wrappers
- `assert_freq_close()`: FFT-aware frequency comparison with bin width tolerance
- `freq_isclose()`, `magnitude_isclose()`: numpy-compatible helpers

**See:** `tap_tone_pi/testing/float_compare.py`

---

## MINOR Issues (7)

These issues affect code quality, documentation, or non-critical paths.

### m1. Scattered Configuration Constants

**Problem:** Magic numbers scattered across files instead of centralized config.

**Fix:** Create `tap_tone_pi/config/defaults.py` with all constants.

---

### m2. Undocumented Window Function Choice

**File:** `tap_tone_pi/core/analysis.py` line 113

**Problem:** Hanning window used without documenting trade-offs vs Blackman, Hamming.

**Fix:** Add docstring explaining choice and when alternatives are appropriate.

---

### m3. Unjustified Filter Order

**File:** `tap_tone_pi/core/analysis.py` lines 36-42

**Problem:** Butterworth order=4 chosen without justification.

**Fix:** Document: order=4 provides 24 dB/octave rolloff with minimal phase distortion for modal analysis.

---

### m4. Grid ID Breaks at 26 Rows

**File:** `tap_tone_pi/core/grid.py` line 149

**Problem:** Grid point IDs use single letter (A-Z) for rows, breaking at 27+ rows.

**Fix:** Use AA, AB... pattern for extended grids (like spreadsheet columns).

---

### m5. Untested Retry Decorator

**File:** `tap_tone_pi/core/errors.py` lines 96-149

**Problem:** Retry logic has branch coverage gaps.

**Fix:** Add tests for all retry scenarios: success, partial failure, complete failure, timeout.

---

### m6. Clipping Threshold Too Conservative

**File:** `tap_tone_pi/core/analysis.py` line 98

**Problem:** Clipping detected at 0.999 full scale, but many ADCs show nonlinearity earlier.

**Fix:** Use 0.995 (commercial standard) with configurable override.

---

### m7. Missing Type Hints in Public API

**Problem:** Several public functions lack type hints, reducing IDE support.

**Fix:** Add comprehensive type hints for public API.

---

## Fix Priority Roadmap

| Priority | ID | Issue | Estimated Effort | Status |
|----------|-----|-------|------------------|--------|
| P0 | C1 | MOE Timoshenko shear correction | 2 hours | ✅ Complete |
| P0 | C2 | FFT confidence derivation | 2 hours | ✅ Complete |
| P0 | C3 | TF uncertainty propagation | 3 hours | ✅ Complete |
| P0 | C4 | Adaptive epsilon | 1 hour | ✅ Complete |
| P1 | M1 | Linear fit validation | 1 hour | ✅ Complete |
| P1 | M2 | Percentile bounds | 30 min | ✅ Complete |
| P1 | M3 | Auto-trigger settling | 1 hour | ✅ Complete |
| P1 | M4 | Relative freq tolerance | 30 min | ✅ Complete |
| P1 | M5 | Phase 1/2 cross-validation | 1 hour | ✅ Complete |
| P1 | M6 | Sample rate consistency | 1 hour | ✅ Complete |
| P1 | M7 | Uncertainty-based diff | 1 hour | ✅ Complete |
| P1 | M8 | Float comparison tolerance | 30 min | ✅ Complete |
| P2 | All | Minor issues | 4 hours total | 🔴 Not started |

**Completed: 2026-02-17** — All 4 CRITICAL and 8 MODERATE fixes implemented. 1402 tests passing.

---

## New Features Added

### Gore-Style Stiffness Index System ✅

**Files:** `tap_tone_pi/bending/gore_stiffness.py`, `tap_tone_pi/bending/gore_spreadsheet.py`

**Completed: 2026-02-17**

Comprehensive Gore spreadsheet system for tonewood analysis, integrating static bending
and acoustic tap tone measurements with cross-validation.

**Core Calculations:**
- Stiffness Index: `SI = E × h³` (GPa·mm³)
- Thickness targeting: `h = (SI_target / E)^(1/3)`
- Orthotropic ratios: `E_L / E_C` (typical 10-20 for tonewoods)

**Dynamic MOE from Tap Tone:**
```
E_dynamic = (48 × π² × f² × ρ × L⁴) / (λ⁴ × h²)
where λ = modal constant (4.730 for free-free fundamental)
```

**Cross-Validation:**
- Compares static (bending) vs dynamic (acoustic) E
- Agreement levels: good (<5%), marginal (<10%), poor (>threshold)
- Warnings for unusual divergence patterns

**Instrument Presets:**
- Classical guitar, Dreadnought, OM, Parlor, Archtop
- Ukuleles (soprano, concert, tenor), Mandolin
- Each with SI_L min/typical/max ranges

**Output Formats:**
- JSON primary (full data, provenance, cross-validation)
- CSV export (flat table for spreadsheet import)

**Tests:** 53 new tests covering calculations, presets, cross-validation, and physical realism.

---

### QA/QC Lab Specification Sheet ✅

**Files:** `tap_tone_pi/bending/qa_lab_spec.py`, `tests/test_qa_lab_spec.py`

**Completed: 2026-02-17**

Comprehensive laboratory specification sheet for tonewood QA/QC, integrating
all measurement data sources into a single, traceable record.

**Structure (9 Sections):**

1. **Sample Identification & Traceability**
   - specimen_id, batch_id, run_id, session_id
   - species, grain_direction, material_source

2. **Test Setup & Parameters**
   - operator_id, device_id, fixture_id, mic_id
   - calibration_date, is_calibrated
   - temperature_c, humidity_rh, protocol_version

3. **Primary Measurements**
   - Dimensions (L, W, H), mass, density
   - Frequencies, amplitudes

4. **Derived Properties** (from Gore spreadsheet)
   - E_static, E_dynamic, SI
   - wave_speed, specific_stiffness, radiation_ratio
   - Instrument matching and preset comparison

5. **Modal Analysis**
   - Mode identification (frequency, damping_ratio, Q, confidence)
   - Dominant mode, MAC matrix, modal overlap warning

6. **Error Analysis (GUM-compliant)**
   - Combined uncertainty, expanded uncertainty
   - Coverage factor, effective DOF
   - Component breakdown, dominant error source
   - E_uncertainty_GPa, SI_uncertainty

7. **Quality Assessment**
   - Verdict (pass/warn/fail), policy_version
   - Triggered rules (rule_id, severity, message)
   - Cross-validation result, confidence score, SNR

8. **Special Analysis**
   - Wolf tone: wolf_detected, worst_wolf_freq_hz, beat_hz, severity
   - Chladni: pattern_matched, match_confidence

9. **Audit Trail**
   - software_version, schema_version
   - entry_hash_sha256 (integrity verification)
   - Raw data paths and hashes
   - export_timestamp_utc

**Key Features:**
- Deterministic hash for integrity verification
- JSON and CSV export formats
- Integrates with: gore_spreadsheet, damping/modes, wolf_beat, uncertainty/budget, quality_policy, export_metadata
- 35 new tests

**Usage:**
```python
from tap_tone_pi.bending.qa_lab_spec import (
    build_qa_lab_spec_entry,
    export_qa_lab_csv,
    export_qa_lab_json,
)

entry = build_qa_lab_spec_entry(
    specimen_id="Sitka_001_L",
    direction="L",
    thickness_mm=3.0,
    bending_json_path="bending_moe.json",
    acoustic_json_path="peaks.json",
    operator_id="JSmith",
    device_id="DEV001",
    is_calibrated=True,
)

export_qa_lab_csv([entry], "qa_report.csv")
export_qa_lab_json([entry], "qa_report.json")
```

---

## Related Documentation

- [AN-006: MOE Beam Theory and Shear Corrections](app_notes/AN-006_moe_beam_theory.md)
- [Theory: MOE Shear Correction](theory/moe_shear_correction.md)
- [Theory: Confidence Score Derivation](theory/confidence_derivation.md)
- [Theory: Uncertainty and Averaging](theory/uncertainty_averaging.md)
- [ACOUSTIC_TESTING_METHODS_ANALYSIS.md](ACOUSTIC_TESTING_METHODS_ANALYSIS.md) - Parent document
