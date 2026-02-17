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

### M4. Hardcoded 5 Hz Tolerance in Pattern Matching

**File:** `tap_tone_pi/chladni/index_patterns.py` line 24

**Problem:** Fixed 5 Hz tolerance for frequency matching is inappropriate across the spectrum:
- At 50 Hz: 5 Hz = 10% = too loose
- At 500 Hz: 5 Hz = 1% = reasonable
- At 5000 Hz: 5 Hz = 0.1% = too tight

**Fix:** Use relative tolerance (e.g., 2% of center frequency) or semitone-based matching.

---

### M5. No Cross-Validation Between Phase 1 and Phase 2

**Problem:** Phase 1 (single-channel) and Phase 2 (dual-channel) can report different frequencies for the same mode without consistency checks.

**Fix:** Add mode-linking function that correlates Phase 1 peaks with Phase 2 ODS results.

---

### M6. Sample Rate Consistency Not Enforced

**Problem:** Functions accept sample_rate as parameter but don't validate against actual audio data.

**Fix:** Embed sample rate in audio container, validate on load.

---

### M7. Arbitrary Comparison Threshold

**File:** `tap_tone_pi/core/session_diff.py` line 50

**Problem:** Hardcoded threshold (e.g., 5 Hz) for "significant difference" without:
- Scaling by frequency
- Accounting for measurement uncertainty
- User configurability

**Fix:** Use uncertainty-based thresholds: significant if |Δf| > 2×√(u₁² + u₂²)

---

### M8. Missing Tolerance for Floating-Point Comparison

**Problem:** Several tests use exact equality for floating-point values.

**Fix:** Use np.isclose() or pytest.approx() with appropriate tolerances.

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
| P1 | M4 | Relative freq tolerance | 30 min | 🔴 Not started |
| P1 | M7 | Uncertainty-based diff | 1 hour | 🔴 Not started |
| P2 | All | Minor issues | 4 hours total | 🔴 Not started |

**Completed: 2026-02-17** — All 4 CRITICAL and 3 MODERATE fixes implemented. 1199 tests passing.

---

## Related Documentation

- [AN-006: MOE Beam Theory and Shear Corrections](app_notes/AN-006_moe_beam_theory.md)
- [Theory: MOE Shear Correction](theory/moe_shear_correction.md)
- [Theory: Confidence Score Derivation](theory/confidence_derivation.md)
- [Theory: Uncertainty and Averaging](theory/uncertainty_averaging.md)
- [ACOUSTIC_TESTING_METHODS_ANALYSIS.md](ACOUSTIC_TESTING_METHODS_ANALYSIS.md) - Parent document
