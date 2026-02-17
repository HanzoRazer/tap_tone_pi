# Acoustic Testing Methods: Detailed Analysis & Evolution Path

**Document Version:** 1.0
**Date:** 2026-02-17
**Purpose:** Technical analysis of free-form and fixed-displacement testing methods, with implementation guidance for production-grade physics.

---

## Table of Contents

1. [Document 1: Free Form Testing](#document-1-free-form-testing)
2. [Document 2: Fixed Body Displacement Method](#document-2-fixed-body-displacement-method)
3. [Viable Directions for Evolution](#viable-directions-for-evolution)
4. [Physics Implementation Gap Analysis](#physics-implementation-gap-analysis)
5. [Production-Grade Implementation Guide](#production-grade-implementation-guide)
6. [Quick Start Code Examples](#quick-start-code-examples)

---

## Document 1: Free Form Testing

This describes a **fixture-free acoustic characterization method** for guitars.

### Core Concept

```
Free Form Testing = Suspended instrument + tap excitation + microphone capture
                    → No rigid fixtures, minimal mass loading
                    → Captures "natural" vibration behavior
```

### Key Technical Points

| Aspect | Details | Annotation |
|--------|---------|------------|
| **Suspension** | Rubber bands at tuner posts + bridge pins | Approximates free-free boundary conditions |
| **Excitation** | Tap hammer or fingernail at bridge plate | Impulse response captures all modes simultaneously |
| **Sensing** | Microphone 10-20cm from soundhole | Non-contact, no mass loading |
| **Analysis** | FFT → peaks → mode identification | Standard spectral analysis |

### Strengths Identified

- **Low cost**: No expensive fixtures
- **Portable**: Can test anywhere
- **Non-invasive**: No sensors attached to instrument
- **Natural conditions**: Tests instrument as played

### Limitations Acknowledged

- **Repeatability**: Suspension and tap location vary
- **Quantification**: Relative measurements only (no absolute calibration)
- **Mode coupling**: Air modes and body modes interact in complex ways

---

## Document 2: Fixed Body Displacement Method

This is a comprehensive technical document covering **multiple acoustic characterization approaches** with emphasis on controlled displacement methods.

### Section-by-Section Breakdown

#### 1. Introduction & Motivation (Lines 1-150)

```
Problem: Traditional tap testing is qualitative and non-repeatable
Goal: Develop quantitative, repeatable characterization methods
Application: Luthier QC, production testing, R&D
```

**Key Quote Annotated:**
> "The fundamental limitation of free-form tap testing is that the excitation force is unknown and variable"

This establishes why controlled methods are needed.

#### 2. Fixed Body Displacement Method (Lines 151-400)

**Core Principle:**
```
Instead of: Unknown force → Measure response
Do this:    Known displacement → Release → Measure response

Displacement is easier to control than force
```

**Implementation:**

| Component | Function | Critical Parameter |
|-----------|----------|-------------------|
| Displacement mechanism | Pull soundboard to known position | 1-2mm typical |
| Release mechanism | Sudden release (electromagnetic, solenoid) | <1ms release time |
| Reference point | Fixed frame or fixture | Rigid, isolated from instrument |
| Measurement | Accelerometer or laser vibrometer | High bandwidth (>10kHz) |

**Advantages over tap testing:**
1. **Repeatable excitation**: Same displacement every time
2. **Broadband**: Step release excites all frequencies
3. **Quantifiable**: Known energy input
4. **Consistent**: Operator-independent

#### 3. Monopole Radiation Measurement (Lines 401-600)

**Concept:**
```
Monopole = Net volume displacement of air
         = Primary sound radiation mechanism at low frequencies
         = Correlates with "projection" and "loudness"
```

**Measurement approach:**
- Integrate pressure over closed surface (or use near-field approximation)
- Alternatively: measure soundboard velocity at multiple points, integrate

**Annotation:** This is directly relevant to guitar quality - monopole strength predicts how "loud" an instrument will sound.

#### 4. Mode Shape Visualization (Lines 601-850)

**Methods discussed:**

| Method | Pros | Cons |
|--------|------|------|
| Chladni patterns | Visual, intuitive | Qualitative only |
| Scanning laser vibrometer | Quantitative, high resolution | Expensive ($50k+) |
| Multi-point accelerometers | Quantitative, affordable | Mass loading, limited points |
| Holographic interferometry | Full-field, non-contact | Complex setup |

**Key insight:**
> "Mode shapes are as important as mode frequencies for predicting tonal character"

#### 5. Damping Measurement (Lines 851-1050)

**Three approaches:**
1. **Half-power bandwidth**: Q = f₀ / Δf (from frequency domain)
2. **Logarithmic decrement**: δ = ln(A₁/A₂) (from time domain)
3. **Curve fitting**: Fit exponential decay to impulse response

**Annotation:** Damping is critical but often overlooked. High damping = short sustain but even response. Low damping = long sustain but peaky response.

#### 6. Transfer Function Measurements (Lines 1051-1300)

**Bridge-to-air transfer function:**
```
H(f) = P(f) / F(f)

where:
P(f) = Sound pressure at measurement point
F(f) = Force applied at bridge

Units: Pa/N (or dB re 1 Pa/N)
```

**Measurement chain:**
```
Shaker/hammer → Force sensor → Bridge
                                ↓
                            Instrument
                                ↓
                           Microphone → FFT analyzer
```

#### 7. Production Testing Considerations (Lines 1301-1500)

**Key requirements for production:**

| Requirement | Why | Implementation |
|-------------|-----|----------------|
| Speed | Cost per unit | <60 seconds per test |
| Repeatability | Meaningful comparison | Fixtures, automated excitation |
| Pass/fail criteria | Actionable results | Limit curves, statistical bounds |
| Traceability | Quality records | Unique ID, timestamped data |

**Annotation:** This section bridges lab methods to factory floor reality.

#### 8. Correlation Studies (Lines 1501-1800)

**Subjective-objective correlation:**

| Perceptual Attribute | Measurable Parameter |
|---------------------|---------------------|
| "Brightness" | High-frequency energy ratio |
| "Warmth" | Low-frequency dominance |
| "Projection" | Monopole radiation efficiency |
| "Sustain" | Modal damping (inverse) |
| "Balance" | Mode spacing uniformity |
| "Clarity" | Absence of wolf notes |

**Key quote:**
> "No single measurement predicts overall quality, but a constellation of parameters together can distinguish exceptional instruments"

#### 9. Implementation Guidance (Lines 1801-2100)

**Recommended progression:**
```
Level 1: Tap test + FFT (qualitative screening)
    ↓
Level 2: Fixture + controlled excitation (repeatable)
    ↓
Level 3: Transfer function + monopole (quantitative)
    ↓
Level 4: Full modal analysis (R&D characterization)
```

#### 10. Future Directions (Lines 2101-2388)

**Identified opportunities:**
1. **AI/ML for pattern recognition**: Learn quality signatures from labeled data
2. **Real-time feedback during construction**: Monitor tap response as plates are thinned
3. **Digital twins**: Physics-based models calibrated to measurements
4. **Portable systems**: Smartphone-based analysis with calibrated MEMS microphones

---

## Viable Directions for Evolution

### For Free Form Testing System (Tap Tone Pi)

| Direction | Description | Implementation Path |
|-----------|-------------|---------------------|
| **Standardized suspension protocol** | Document exact rubber band placement, tension | Add setup wizard with photo references |
| **Tap location templates** | Overlay showing optimal tap points | AR/camera overlay or physical template |
| **Multi-tap statistical averaging** | Require 3-5 taps, compute variance | Already have attempt tracking - extend to require N taps |
| **Relative calibration** | Compare to known reference instrument | "Golden sample" workflow |
| **Trend tracking** | Monitor same instrument over time | Session diff already exists - enhance to time series |
| **Environmental compensation** | Temperature/humidity correction curves | Add sensors or manual entry + correction model |

**Most viable immediate enhancement:**
```
Multi-tap statistical mode:
1. Require minimum 3 taps per point
2. Compute mean ± std dev for each peak
3. Flag high-variance peaks as "uncertain"
4. Only pass QC if variance below threshold
```

This leverages existing code (attempt tracking) and adds quantifiable repeatability.

### For Fixed Body Displacement Method

| Direction | Description | Implementation Path |
|-----------|-------------|---------------------|
| **Low-cost displacement fixture** | 3D-printed frame + solenoid release | Design files + BOM, integrate with Tap Tone Pi |
| **Hybrid approach** | Use displacement for calibration, tap for speed | Calibrate tap response to displacement baseline |
| **Monopole proxy measurement** | Near-field pressure integration | Add second microphone + processing |
| **Automated damping extraction** | Fit exponential decay to each mode | Algorithm exists in rub_buzz envelope code |
| **Transfer function workflow** | Force sensor + existing analysis | Add force input channel, compute H1/H2 |

**Most viable bridge between systems:**
```
Calibrated Tap Protocol:
1. ONCE: Measure with displacement fixture (gold standard)
2. ONCE: Measure with tap at same point (correlate)
3. PRODUCTION: Use tap only, apply correction factor
4. PERIODIC: Re-verify tap vs displacement correlation
```

This gives you displacement-method accuracy with tap-method speed.

### Unified Evolution Path

```
                    Current State
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
   Free Form (Tap)                Fixed Displacement
   - Fast, portable               - Repeatable, quantitative
   - Qualitative                  - Expensive, slow
        │                                 │
        └────────────────┬────────────────┘
                         ▼
              Calibrated Hybrid System
              ─────────────────────────
              • Displacement fixture for calibration
              • Tap workflow for production
              • Uncertainty bounds from calibration
              • Periodic re-validation
                         │
                         ▼
              ┌──────────┴──────────┐
              ▼                     ▼
         Statistical             Transfer
         Multi-Tap               Function
         (variance-aware)        (with force sensor)
              │                     │
              └──────────┬──────────┘
                         ▼
                 AI-Assisted QC
                 ─────────────
                 • Learn quality signatures
                 • Predict subjective ratings
                 • Detect anomalies automatically
```

### Priority Recommendation

**Phase 4 priorities for Tap Tone Pi:**

| Priority | Feature | Value | Effort |
|----------|---------|-------|--------|
| P0 | Multi-tap statistical averaging | High repeatability | Low (extend existing) |
| P0 | Automated damping extraction | Key quality metric | Low (use envelope code) |
| P1 | Displacement fixture design | Gold standard calibration | Medium (hardware) |
| P1 | Environmental compensation | Professional credibility | Medium |
| P2 | Transfer function mode | Full characterization | High (force sensor needed) |
| P2 | AI quality prediction | Production QC | High (needs labeled data) |

The **multi-tap statistical mode** and **damping extraction** can be implemented immediately using existing code infrastructure. The displacement fixture requires hardware design but could leverage the software infrastructure already in place.

---

## Physics Implementation Gap Analysis

### What Has Been Simplified

| Feature | What Was Implemented | What Full Physics Requires |
|---------|---------------------|---------------------------|
| **Damping** | Basic log decrement from envelope | Hilbert transform for instantaneous amplitude, bandpass isolation per mode, half-power bandwidth cross-validation, amplitude-dependent damping detection, radiation vs material damping separation |
| **Peak detection** | Local maxima above threshold | Modal parameter estimation (MDOF curve fitting), distinguishing closely-spaced modes, complex mode handling for non-proportional damping |
| **Uncertainty** | Standard deviation of repeated measurements | Proper error propagation through FFT, coherence-based uncertainty bounds, bias vs variance decomposition, confidence intervals with correct DOF |
| **THD+N** | Simple power ratio | Weighting curves (A-weighting, ITU-R 468), proper noise bandwidth normalization, intermodulation products |

### The Full Math Required

#### Damping Extraction (Proper Treatment)

**Method 1: Half-power bandwidth**
```
Q = f_n / (f_2 - f_1)

where f_1, f_2 are -3dB points

Requirements:
- Proper frequency resolution: Δf << (f_2 - f_1)
- Mode isolation: adjacent modes don't overlap
- Correction for spectral leakage
- Windowing effects on apparent bandwidth
```

**Method 2: Logarithmic decrement (time domain)**
```
δ = (1/n) × ln(x_0 / x_n)

ζ = δ / √(4π² + δ²)

Requirements:
- Hilbert transform for analytic signal: x_a(t) = x(t) + j×H{x(t)}
- Envelope: A(t) = |x_a(t)|
- Bandpass filtering to isolate single mode
- Handling of beating from closely-spaced modes
- Statistical fitting: A(t) = A_0 × exp(-ζω_n t) with uncertainty
```

**Method 3: Complex exponential fitting (ERA, Prony)**
```
x(t) = Σ A_k × exp(λ_k × t)

where λ_k = -ζ_k ω_k + j×ω_k×√(1-ζ_k²)

Requirements:
- Singular value decomposition for model order selection
- Stabilization diagrams to distinguish physical vs computational modes
- MAC (Modal Assurance Criterion) for mode pairing
```

#### Multi-tap Uncertainty (Proper Treatment)

**Not just standard deviation:**
```
σ_f = std(f_measurements)  ← Simplified approach

Proper uncertainty budget:
u²(f) = u²_repeatability + u²_resolution + u²_bias + u²_environmental

where:
- u_repeatability = std(f) / √n (Type A)
- u_resolution = Δf / √12 (FFT bin width)
- u_bias = systematic error from calibration
- u_environmental = temperature coefficient × ΔT
```

**Confidence intervals:**
```
f = f_mean ± t_(α/2, n-1) × s / √n

Not just ± σ, but proper t-distribution for small n
```

#### Transfer Function (Proper Treatment)

```
H1 = G_xy / G_xx  (noise on output)
H2 = G_yy / G_yx  (noise on input)
Hv = √(H1 × H2)   (geometric mean)

Coherence: γ² = |G_xy|² / (G_xx × G_yy)

Uncertainty in H:
σ_H / |H| ≈ √[(1 - γ²) / (2nγ²)]

Requirements:
- Welch's method with proper overlap
- Coherent vs incoherent averaging
- Bias correction for short records
```

### What Is Actually Needed for Displacement Fixture

1. **Proper modal parameter extraction** (ERA or polyreference least squares)
2. **Uncertainty propagation** through the entire signal chain
3. **Damping that distinguishes** radiation damping from material damping
4. **Transfer functions** with force input (requires force sensor integration)
5. **Monopole radiation** calculation (requires spatial integration or proxy)

### Implementation Options

**Option A: Production-grade physics**
- Full modal parameter estimation (ERA algorithm)
- Proper uncertainty budgets per ISO GUM
- Multiple damping methods with cross-validation
- Transfer function with coherence-based quality gates
- Will take longer, more complex code, but actually correct

**Option B: Document the gaps explicitly**
- Keep current simplified implementations
- Add detailed documentation of assumptions and limitations
- Mark outputs with "simplified" flags
- Implement full physics yourself where needed

---

## Production-Grade Implementation Guide

This section provides the mathematical foundation and code structure for Option A implementation.

### Module Structure

```
tap_tone_pi/
├── modal/
│   ├── __init__.py
│   ├── era.py              # Eigensystem Realization Algorithm
│   ├── stabilization.py    # Stabilization diagrams
│   ├── mac.py              # Modal Assurance Criterion
│   └── parameter_extraction.py
├── damping/
│   ├── __init__.py
│   ├── halfpower.py        # Half-power bandwidth method
│   ├── logdec.py           # Logarithmic decrement
│   ├── curve_fit.py        # Exponential curve fitting
│   └── cross_validate.py   # Multi-method cross-validation
├── uncertainty/
│   ├── __init__.py
│   ├── budget.py           # ISO GUM uncertainty budgets
│   ├── propagation.py      # Error propagation
│   ├── confidence.py       # Confidence intervals
│   └── monte_carlo.py      # Monte Carlo uncertainty
└── transfer_function/
    ├── __init__.py
    ├── estimators.py       # H1, H2, Hv
    ├── coherence.py        # Coherence calculation
    └── quality.py          # Coherence-based quality gates
```

---

## Quick Start Code Examples

### 1. Proper Damping Extraction with Multiple Methods

```python
"""
tap_tone_pi/damping/extraction.py

Production-grade damping extraction with cross-validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np
from scipy import signal as scipy_signal
from scipy.optimize import curve_fit
from scipy.stats import t as t_distribution


@dataclass
class DampingResult:
    """Result of damping extraction for a single mode."""

    frequency_hz: float
    damping_ratio: float              # ζ (zeta)
    quality_factor: float             # Q = 1/(2ζ)
    decay_time_s: float               # τ = 1/(ζωn)

    # Uncertainty
    damping_ratio_std: float
    confidence_level: float           # e.g., 0.95
    confidence_interval: Tuple[float, float]

    # Method agreement
    method_used: str
    halfpower_estimate: Optional[float]
    logdec_estimate: Optional[float]
    curvefit_estimate: Optional[float]
    methods_agree: bool               # Within tolerance

    def to_dict(self) -> dict:
        return {
            "frequency_hz": self.frequency_hz,
            "damping_ratio": self.damping_ratio,
            "quality_factor": self.quality_factor,
            "decay_time_s": self.decay_time_s,
            "damping_ratio_std": self.damping_ratio_std,
            "confidence_level": self.confidence_level,
            "confidence_interval": list(self.confidence_interval),
            "method_used": self.method_used,
            "halfpower_estimate": self.halfpower_estimate,
            "logdec_estimate": self.logdec_estimate,
            "curvefit_estimate": self.curvefit_estimate,
            "methods_agree": self.methods_agree,
        }


def extract_damping_halfpower(
    freqs: np.ndarray,
    magnitude: np.ndarray,
    peak_freq: float,
    search_bandwidth_hz: float = 50.0,
) -> Tuple[float, float]:
    """
    Extract damping using half-power bandwidth method.

    Q = f_n / (f_2 - f_1)
    ζ = 1 / (2Q)

    Args:
        freqs: Frequency array (Hz)
        magnitude: Magnitude spectrum (linear, not dB)
        peak_freq: Center frequency of mode (Hz)
        search_bandwidth_hz: Search range around peak

    Returns:
        (damping_ratio, uncertainty)
    """
    # Find peak in search range
    mask = (freqs >= peak_freq - search_bandwidth_hz) & \
           (freqs <= peak_freq + search_bandwidth_hz)

    if not np.any(mask):
        return np.nan, np.nan

    local_freqs = freqs[mask]
    local_mag = magnitude[mask]

    peak_idx = np.argmax(local_mag)
    peak_mag = local_mag[peak_idx]
    actual_peak_freq = local_freqs[peak_idx]

    # Find -3dB points (half power = 1/√2 amplitude)
    half_power_level = peak_mag / np.sqrt(2)

    # Find lower -3dB point
    lower_idx = peak_idx
    while lower_idx > 0 and local_mag[lower_idx] > half_power_level:
        lower_idx -= 1

    # Interpolate for precise crossing
    if lower_idx > 0:
        f1 = np.interp(
            half_power_level,
            [local_mag[lower_idx], local_mag[lower_idx + 1]],
            [local_freqs[lower_idx], local_freqs[lower_idx + 1]]
        )
    else:
        f1 = local_freqs[0]

    # Find upper -3dB point
    upper_idx = peak_idx
    while upper_idx < len(local_mag) - 1 and local_mag[upper_idx] > half_power_level:
        upper_idx += 1

    if upper_idx < len(local_mag) - 1:
        f2 = np.interp(
            half_power_level,
            [local_mag[upper_idx], local_mag[upper_idx - 1]],
            [local_freqs[upper_idx], local_freqs[upper_idx - 1]]
        )
    else:
        f2 = local_freqs[-1]

    # Calculate Q and damping
    bandwidth = f2 - f1
    if bandwidth <= 0:
        return np.nan, np.nan

    Q = actual_peak_freq / bandwidth
    damping_ratio = 1.0 / (2.0 * Q)

    # Uncertainty from frequency resolution
    freq_resolution = freqs[1] - freqs[0] if len(freqs) > 1 else 1.0
    # Propagate through Q calculation
    u_bandwidth = freq_resolution * np.sqrt(2)  # Two interpolations
    u_Q = Q * (u_bandwidth / bandwidth)
    u_zeta = damping_ratio * (u_Q / Q)

    return damping_ratio, u_zeta


def extract_damping_logdec(
    signal: np.ndarray,
    sample_rate: int,
    peak_freq: float,
    bandwidth_hz: float = 20.0,
    n_cycles: int = 10,
) -> Tuple[float, float]:
    """
    Extract damping using logarithmic decrement method.

    δ = (1/n) × ln(x_0 / x_n)
    ζ = δ / √(4π² + δ²)

    Args:
        signal: Time-domain signal
        sample_rate: Sample rate (Hz)
        peak_freq: Mode frequency (Hz)
        bandwidth_hz: Bandpass filter bandwidth
        n_cycles: Number of cycles for decrement calculation

    Returns:
        (damping_ratio, uncertainty)
    """
    # Design bandpass filter to isolate mode
    nyquist = sample_rate / 2
    low = (peak_freq - bandwidth_hz / 2) / nyquist
    high = (peak_freq + bandwidth_hz / 2) / nyquist

    # Clamp to valid range
    low = max(0.01, min(low, 0.99))
    high = max(low + 0.01, min(high, 0.99))

    try:
        b, a = scipy_signal.butter(4, [low, high], btype='band')
        filtered = scipy_signal.filtfilt(b, a, signal)
    except ValueError:
        return np.nan, np.nan

    # Compute analytic signal via Hilbert transform
    analytic = scipy_signal.hilbert(filtered)
    envelope = np.abs(analytic)

    # Find envelope peaks (local maxima)
    peak_indices = scipy_signal.find_peaks(envelope, distance=int(sample_rate / peak_freq / 2))[0]

    if len(peak_indices) < n_cycles + 1:
        return np.nan, np.nan

    # Get peak amplitudes
    peak_amplitudes = envelope[peak_indices]

    # Calculate log decrements between successive peaks
    log_decrements = []
    for i in range(len(peak_amplitudes) - 1):
        if peak_amplitudes[i + 1] > 0 and peak_amplitudes[i] > 0:
            delta = np.log(peak_amplitudes[i] / peak_amplitudes[i + 1])
            if delta > 0:  # Should be positive for decaying signal
                log_decrements.append(delta)

    if len(log_decrements) < 3:
        return np.nan, np.nan

    # Average log decrement
    delta_mean = np.mean(log_decrements)
    delta_std = np.std(log_decrements, ddof=1)

    # Convert to damping ratio
    # ζ = δ / √(4π² + δ²)
    damping_ratio = delta_mean / np.sqrt(4 * np.pi**2 + delta_mean**2)

    # Propagate uncertainty
    # dζ/dδ = 4π² / (4π² + δ²)^(3/2)
    denom = (4 * np.pi**2 + delta_mean**2) ** 1.5
    sensitivity = 4 * np.pi**2 / denom
    u_zeta = sensitivity * delta_std / np.sqrt(len(log_decrements))

    return damping_ratio, u_zeta


def extract_damping_curvefit(
    signal: np.ndarray,
    sample_rate: int,
    peak_freq: float,
    bandwidth_hz: float = 20.0,
) -> Tuple[float, float]:
    """
    Extract damping by fitting exponential decay to envelope.

    A(t) = A_0 × exp(-ζ × ω_n × t)

    Args:
        signal: Time-domain signal
        sample_rate: Sample rate (Hz)
        peak_freq: Mode frequency (Hz)
        bandwidth_hz: Bandpass filter bandwidth

    Returns:
        (damping_ratio, uncertainty)
    """
    # Design bandpass filter
    nyquist = sample_rate / 2
    low = (peak_freq - bandwidth_hz / 2) / nyquist
    high = (peak_freq + bandwidth_hz / 2) / nyquist

    low = max(0.01, min(low, 0.99))
    high = max(low + 0.01, min(high, 0.99))

    try:
        b, a = scipy_signal.butter(4, [low, high], btype='band')
        filtered = scipy_signal.filtfilt(b, a, signal)
    except ValueError:
        return np.nan, np.nan

    # Compute envelope
    analytic = scipy_signal.hilbert(filtered)
    envelope = np.abs(analytic)

    # Find start of decay (peak of envelope)
    start_idx = np.argmax(envelope)

    # Use data from peak onwards
    t = np.arange(len(envelope) - start_idx) / sample_rate
    y = envelope[start_idx:]

    # Normalize
    y_norm = y / y[0] if y[0] > 0 else y

    # Only fit where signal is significant
    valid = y_norm > 0.01
    if np.sum(valid) < 10:
        return np.nan, np.nan

    t_fit = t[valid]
    y_fit = y_norm[valid]

    # Exponential decay model: A(t) = exp(-α × t)
    # where α = ζ × ω_n
    def decay_model(t, alpha):
        return np.exp(-alpha * t)

    try:
        omega_n = 2 * np.pi * peak_freq

        # Initial guess: assume Q ≈ 50 → ζ ≈ 0.01
        p0 = [0.01 * omega_n]

        popt, pcov = curve_fit(
            decay_model, t_fit, y_fit,
            p0=p0,
            bounds=(0, omega_n),  # ζ must be 0 < ζ < 1
            maxfev=5000
        )

        alpha = popt[0]
        alpha_std = np.sqrt(pcov[0, 0])

        damping_ratio = alpha / omega_n
        u_zeta = alpha_std / omega_n

        return damping_ratio, u_zeta

    except (RuntimeError, ValueError):
        return np.nan, np.nan


def extract_damping_crossvalidated(
    signal: np.ndarray,
    freqs: np.ndarray,
    magnitude: np.ndarray,
    sample_rate: int,
    peak_freq: float,
    confidence_level: float = 0.95,
    agreement_tolerance: float = 0.3,  # 30% relative difference
) -> DampingResult:
    """
    Extract damping using multiple methods with cross-validation.

    Returns the most reliable estimate with uncertainty and agreement flags.

    Args:
        signal: Time-domain signal
        freqs: Frequency array (Hz)
        magnitude: Magnitude spectrum
        sample_rate: Sample rate (Hz)
        peak_freq: Mode frequency (Hz)
        confidence_level: Confidence level for intervals (e.g., 0.95)
        agreement_tolerance: Maximum relative difference for agreement

    Returns:
        DampingResult with cross-validated damping estimate
    """
    # Get estimates from all three methods
    zeta_hp, u_hp = extract_damping_halfpower(freqs, magnitude, peak_freq)
    zeta_ld, u_ld = extract_damping_logdec(signal, sample_rate, peak_freq)
    zeta_cf, u_cf = extract_damping_curvefit(signal, sample_rate, peak_freq)

    # Collect valid estimates
    estimates = []
    uncertainties = []
    methods = []

    if not np.isnan(zeta_hp) and zeta_hp > 0:
        estimates.append(zeta_hp)
        uncertainties.append(u_hp)
        methods.append("halfpower")

    if not np.isnan(zeta_ld) and zeta_ld > 0:
        estimates.append(zeta_ld)
        uncertainties.append(u_ld)
        methods.append("logdec")

    if not np.isnan(zeta_cf) and zeta_cf > 0:
        estimates.append(zeta_cf)
        uncertainties.append(u_cf)
        methods.append("curvefit")

    if len(estimates) == 0:
        # No valid estimates
        return DampingResult(
            frequency_hz=peak_freq,
            damping_ratio=np.nan,
            quality_factor=np.nan,
            decay_time_s=np.nan,
            damping_ratio_std=np.nan,
            confidence_level=confidence_level,
            confidence_interval=(np.nan, np.nan),
            method_used="none",
            halfpower_estimate=None,
            logdec_estimate=None,
            curvefit_estimate=None,
            methods_agree=False,
        )

    # Inverse-variance weighted average
    weights = [1.0 / (u**2) if u > 0 else 0.0 for u in uncertainties]
    total_weight = sum(weights)

    if total_weight > 0:
        zeta_weighted = sum(e * w for e, w in zip(estimates, weights)) / total_weight
        u_weighted = np.sqrt(1.0 / total_weight)
    else:
        # Fall back to simple average
        zeta_weighted = np.mean(estimates)
        u_weighted = np.std(estimates, ddof=1) if len(estimates) > 1 else estimates[0] * 0.1

    # Check method agreement
    if len(estimates) >= 2:
        relative_spread = (max(estimates) - min(estimates)) / zeta_weighted
        methods_agree = relative_spread < agreement_tolerance
    else:
        methods_agree = True  # Only one method, no disagreement possible

    # Confidence interval (t-distribution for small n)
    n = len(estimates)
    if n > 1:
        t_crit = t_distribution.ppf((1 + confidence_level) / 2, n - 1)
        margin = t_crit * u_weighted
    else:
        # Single estimate: use uncertainty directly with coverage factor
        margin = 2.0 * u_weighted  # k=2 for ~95% coverage

    ci_lower = max(0, zeta_weighted - margin)
    ci_upper = zeta_weighted + margin

    # Derived quantities
    omega_n = 2 * np.pi * peak_freq
    Q = 1.0 / (2.0 * zeta_weighted) if zeta_weighted > 0 else np.inf
    tau = 1.0 / (zeta_weighted * omega_n) if zeta_weighted > 0 and omega_n > 0 else np.inf

    return DampingResult(
        frequency_hz=peak_freq,
        damping_ratio=zeta_weighted,
        quality_factor=Q,
        decay_time_s=tau,
        damping_ratio_std=u_weighted,
        confidence_level=confidence_level,
        confidence_interval=(ci_lower, ci_upper),
        method_used="weighted_average" if len(estimates) > 1 else methods[0],
        halfpower_estimate=zeta_hp if not np.isnan(zeta_hp) else None,
        logdec_estimate=zeta_ld if not np.isnan(zeta_ld) else None,
        curvefit_estimate=zeta_cf if not np.isnan(zeta_cf) else None,
        methods_agree=methods_agree,
    )
```

### 2. ISO GUM Uncertainty Budget

```python
"""
tap_tone_pi/uncertainty/budget.py

ISO GUM compliant uncertainty budget calculations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import numpy as np
from scipy.stats import t as t_distribution


class UncertaintyType(Enum):
    """Type A (statistical) or Type B (other means)."""
    TYPE_A = "A"  # Evaluated by statistical analysis
    TYPE_B = "B"  # Evaluated by other means


@dataclass
class UncertaintyComponent:
    """A single component of the uncertainty budget."""

    name: str
    value: float                    # Standard uncertainty u(x)
    uncertainty_type: UncertaintyType
    distribution: str               # "normal", "rectangular", "triangular", "u-shaped"
    degrees_of_freedom: float       # ν (nu), inf for Type B
    sensitivity_coefficient: float  # c_i = ∂y/∂x_i
    description: str

    @property
    def contribution(self) -> float:
        """Contribution to combined uncertainty: (c_i × u_i)²"""
        return (self.sensitivity_coefficient * self.value) ** 2

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "type": self.uncertainty_type.value,
            "distribution": self.distribution,
            "degrees_of_freedom": self.degrees_of_freedom,
            "sensitivity_coefficient": self.sensitivity_coefficient,
            "contribution_squared": self.contribution,
            "description": self.description,
        }


@dataclass
class UncertaintyBudget:
    """Complete uncertainty budget per ISO GUM."""

    measurand: str                  # What we're measuring
    result_value: float             # Measured value
    result_unit: str                # Unit of measurement
    components: List[UncertaintyComponent] = field(default_factory=list)
    confidence_level: float = 0.95

    def add_type_a(
        self,
        name: str,
        values: np.ndarray,
        sensitivity: float = 1.0,
        description: str = "",
    ) -> None:
        """
        Add Type A uncertainty from repeated measurements.

        u = s / √n where s is sample standard deviation
        """
        n = len(values)
        if n < 2:
            raise ValueError("Type A requires at least 2 measurements")

        mean = np.mean(values)
        std = np.std(values, ddof=1)  # Sample std dev
        u = std / np.sqrt(n)          # Standard uncertainty of mean

        self.components.append(UncertaintyComponent(
            name=name,
            value=u,
            uncertainty_type=UncertaintyType.TYPE_A,
            distribution="normal",
            degrees_of_freedom=n - 1,
            sensitivity_coefficient=sensitivity,
            description=description or f"Statistical (n={n})",
        ))

    def add_type_b_rectangular(
        self,
        name: str,
        half_width: float,
        sensitivity: float = 1.0,
        description: str = "",
    ) -> None:
        """
        Add Type B uncertainty with rectangular distribution.

        u = a / √3 where a is half-width

        Use for: resolution, digitization, tolerances
        """
        u = half_width / np.sqrt(3)

        self.components.append(UncertaintyComponent(
            name=name,
            value=u,
            uncertainty_type=UncertaintyType.TYPE_B,
            distribution="rectangular",
            degrees_of_freedom=np.inf,
            sensitivity_coefficient=sensitivity,
            description=description or f"Rectangular ±{half_width}",
        ))

    def add_type_b_normal(
        self,
        name: str,
        expanded_uncertainty: float,
        coverage_factor: float = 2.0,
        sensitivity: float = 1.0,
        description: str = "",
    ) -> None:
        """
        Add Type B uncertainty with normal distribution.

        u = U / k where U is expanded uncertainty, k is coverage factor

        Use for: calibration certificates, manufacturer specs (95% confidence)
        """
        u = expanded_uncertainty / coverage_factor

        self.components.append(UncertaintyComponent(
            name=name,
            value=u,
            uncertainty_type=UncertaintyType.TYPE_B,
            distribution="normal",
            degrees_of_freedom=np.inf,  # Assumed large for Type B
            sensitivity_coefficient=sensitivity,
            description=description or f"Normal (k={coverage_factor})",
        ))

    def add_type_b_triangular(
        self,
        name: str,
        half_width: float,
        sensitivity: float = 1.0,
        description: str = "",
    ) -> None:
        """
        Add Type B uncertainty with triangular distribution.

        u = a / √6 where a is half-width

        Use for: quantities more likely near center of range
        """
        u = half_width / np.sqrt(6)

        self.components.append(UncertaintyComponent(
            name=name,
            value=u,
            uncertainty_type=UncertaintyType.TYPE_B,
            distribution="triangular",
            degrees_of_freedom=np.inf,
            sensitivity_coefficient=sensitivity,
            description=description or f"Triangular ±{half_width}",
        ))

    @property
    def combined_uncertainty(self) -> float:
        """
        Combined standard uncertainty u_c.

        u_c = √(Σ (c_i × u_i)²)
        """
        return np.sqrt(sum(c.contribution for c in self.components))

    @property
    def effective_degrees_of_freedom(self) -> float:
        """
        Effective degrees of freedom via Welch-Satterthwaite.

        ν_eff = u_c⁴ / Σ((c_i × u_i)⁴ / ν_i)
        """
        u_c = self.combined_uncertainty
        if u_c == 0:
            return np.inf

        numerator = u_c ** 4
        denominator = 0.0

        for c in self.components:
            if c.degrees_of_freedom < np.inf:
                denominator += c.contribution ** 2 / c.degrees_of_freedom

        if denominator == 0:
            return np.inf

        return numerator / denominator

    @property
    def coverage_factor(self) -> float:
        """
        Coverage factor k for given confidence level.

        Uses t-distribution with effective DOF.
        """
        nu_eff = self.effective_degrees_of_freedom

        if nu_eff >= 100:
            # Use normal approximation
            if self.confidence_level == 0.95:
                return 1.96
            elif self.confidence_level == 0.99:
                return 2.58
            else:
                from scipy.stats import norm
                return norm.ppf((1 + self.confidence_level) / 2)
        else:
            return t_distribution.ppf(
                (1 + self.confidence_level) / 2,
                nu_eff
            )

    @property
    def expanded_uncertainty(self) -> float:
        """
        Expanded uncertainty U = k × u_c
        """
        return self.coverage_factor * self.combined_uncertainty

    @property
    def confidence_interval(self) -> tuple:
        """
        Confidence interval: (value - U, value + U)
        """
        U = self.expanded_uncertainty
        return (self.result_value - U, self.result_value + U)

    def to_dict(self) -> dict:
        """Export budget as dictionary."""
        return {
            "measurand": self.measurand,
            "result": {
                "value": self.result_value,
                "unit": self.result_unit,
            },
            "combined_uncertainty": self.combined_uncertainty,
            "effective_dof": self.effective_degrees_of_freedom,
            "coverage_factor": self.coverage_factor,
            "confidence_level": self.confidence_level,
            "expanded_uncertainty": self.expanded_uncertainty,
            "confidence_interval": {
                "lower": self.confidence_interval[0],
                "upper": self.confidence_interval[1],
            },
            "components": [c.to_dict() for c in self.components],
        }

    def format_result(self) -> str:
        """Format result with uncertainty for display."""
        U = self.expanded_uncertainty
        k = self.coverage_factor

        # Determine significant figures based on uncertainty
        if U > 0:
            sig_figs = max(1, int(-np.floor(np.log10(U))) + 1)
        else:
            sig_figs = 3

        return (
            f"{self.measurand}: {self.result_value:.{sig_figs}f} ± "
            f"{U:.{sig_figs}f} {self.result_unit} "
            f"(k={k:.2f}, {self.confidence_level*100:.0f}% confidence)"
        )


def build_frequency_uncertainty_budget(
    frequency_hz: float,
    measurements: np.ndarray,
    fft_resolution_hz: float,
    calibration_uncertainty_hz: float = 0.1,
    temperature_coefficient_hz_per_c: float = 0.05,
    temperature_uncertainty_c: float = 2.0,
) -> UncertaintyBudget:
    """
    Build complete uncertainty budget for a frequency measurement.

    Args:
        frequency_hz: Measured frequency value
        measurements: Array of repeated measurements
        fft_resolution_hz: FFT frequency bin width
        calibration_uncertainty_hz: Calibration certificate uncertainty (k=2)
        temperature_coefficient_hz_per_c: Frequency drift per degree C
        temperature_uncertainty_c: Temperature measurement uncertainty

    Returns:
        Complete UncertaintyBudget
    """
    budget = UncertaintyBudget(
        measurand="Resonant frequency",
        result_value=frequency_hz,
        result_unit="Hz",
        confidence_level=0.95,
    )

    # Type A: Repeatability from measurements
    if len(measurements) >= 2:
        budget.add_type_a(
            name="Repeatability",
            values=measurements,
            sensitivity=1.0,
            description="Statistical scatter of repeated measurements",
        )

    # Type B: FFT resolution (rectangular distribution)
    budget.add_type_b_rectangular(
        name="FFT resolution",
        half_width=fft_resolution_hz / 2,
        sensitivity=1.0,
        description="Frequency bin quantization",
    )

    # Type B: Calibration (normal, from certificate)
    if calibration_uncertainty_hz > 0:
        budget.add_type_b_normal(
            name="Calibration",
            expanded_uncertainty=calibration_uncertainty_hz,
            coverage_factor=2.0,
            sensitivity=1.0,
            description="Reference calibration uncertainty",
        )

    # Type B: Temperature effect
    if temperature_coefficient_hz_per_c > 0 and temperature_uncertainty_c > 0:
        temp_effect = temperature_coefficient_hz_per_c * temperature_uncertainty_c
        budget.add_type_b_rectangular(
            name="Temperature",
            half_width=temp_effect,
            sensitivity=1.0,
            description="Temperature-induced frequency drift",
        )

    return budget
```

### 3. Transfer Function with Coherence Quality Gates

```python
"""
tap_tone_pi/transfer_function/estimators.py

Transfer function estimation with coherence-based quality assessment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np
from scipy import signal as scipy_signal


@dataclass
class TransferFunctionResult:
    """Complete transfer function measurement result."""

    frequencies: np.ndarray         # Hz
    H1: np.ndarray                  # Complex H1 estimator
    H2: np.ndarray                  # Complex H2 estimator
    Hv: np.ndarray                  # Complex Hv estimator (geometric mean)
    coherence: np.ndarray           # γ² (0 to 1)

    # Quality metrics
    n_averages: int
    quality_passed: bool
    quality_flags: dict

    # Uncertainty
    magnitude_uncertainty: np.ndarray  # Relative uncertainty in |H|
    phase_uncertainty_deg: np.ndarray  # Uncertainty in phase (degrees)

    @property
    def magnitude_db(self) -> np.ndarray:
        """Magnitude of Hv in dB."""
        return 20 * np.log10(np.abs(self.Hv) + 1e-10)

    @property
    def phase_deg(self) -> np.ndarray:
        """Phase of Hv in degrees."""
        return np.angle(self.Hv, deg=True)


def compute_transfer_function(
    input_signal: np.ndarray,
    output_signal: np.ndarray,
    sample_rate: int,
    nperseg: int = 4096,
    noverlap: Optional[int] = None,
    window: str = "hanning",
    min_coherence: float = 0.8,
    coherence_band: Tuple[float, float] = (20.0, 20000.0),
) -> TransferFunctionResult:
    """
    Compute transfer function with H1, H2, Hv estimators.

    H1 = Gxy / Gxx  (minimizes noise on output)
    H2 = Gyy / Gyx  (minimizes noise on input)
    Hv = √(H1 × H2) (geometric mean, balanced)

    Args:
        input_signal: Input (excitation) signal
        output_signal: Output (response) signal
        sample_rate: Sample rate (Hz)
        nperseg: FFT segment length
        noverlap: Overlap samples (default: nperseg // 2)
        window: Window function
        min_coherence: Minimum acceptable coherence
        coherence_band: Frequency range for quality check (Hz)

    Returns:
        TransferFunctionResult with all estimators and quality metrics
    """
    if noverlap is None:
        noverlap = nperseg // 2

    # Compute auto-spectra
    freqs, Gxx = scipy_signal.welch(
        input_signal, sample_rate,
        nperseg=nperseg, noverlap=noverlap, window=window
    )
    _, Gyy = scipy_signal.welch(
        output_signal, sample_rate,
        nperseg=nperseg, noverlap=noverlap, window=window
    )

    # Compute cross-spectra
    _, Gxy = scipy_signal.csd(
        input_signal, output_signal, sample_rate,
        nperseg=nperseg, noverlap=noverlap, window=window
    )
    _, Gyx = scipy_signal.csd(
        output_signal, input_signal, sample_rate,
        nperseg=nperseg, noverlap=noverlap, window=window
    )

    # Small epsilon for numerical stability
    eps = 1e-10

    # Transfer function estimators
    H1 = Gxy / (Gxx + eps)
    H2 = Gyy / (Gyx + eps)

    # Hv = geometric mean (handles complex numbers correctly)
    # Hv = √(H1 × H2) but need to handle phase correctly
    Hv = np.sqrt(H1 * H2)

    # Coherence
    coherence = np.abs(Gxy) ** 2 / ((Gxx * Gyy) + eps)
    coherence = np.clip(coherence, 0, 1)

    # Number of averages (approximate)
    n_segments = (len(input_signal) - noverlap) // (nperseg - noverlap)
    n_averages = max(1, n_segments)

    # Uncertainty in H based on coherence
    # σ_H / |H| ≈ √[(1 - γ²) / (2nγ²)]
    with np.errstate(divide='ignore', invalid='ignore'):
        rel_uncertainty = np.sqrt(
            (1 - coherence) / (2 * n_averages * coherence + eps)
        )
        rel_uncertainty = np.nan_to_num(rel_uncertainty, nan=1.0, posinf=1.0)

    # Phase uncertainty (radians, then convert to degrees)
    # For high coherence: σ_φ ≈ σ_H / |H|
    phase_uncertainty_rad = rel_uncertainty
    phase_uncertainty_deg = np.degrees(phase_uncertainty_rad)

    # Quality assessment
    quality_flags = {}

    # Check coherence in band of interest
    band_mask = (freqs >= coherence_band[0]) & (freqs <= coherence_band[1])
    if np.any(band_mask):
        band_coherence = coherence[band_mask]
        mean_coherence = np.mean(band_coherence)
        min_band_coherence = np.min(band_coherence)
        low_coherence_fraction = np.mean(band_coherence < min_coherence)

        quality_flags["mean_coherence"] = mean_coherence
        quality_flags["min_coherence_in_band"] = min_band_coherence
        quality_flags["low_coherence_fraction"] = low_coherence_fraction
        quality_flags["band_hz"] = coherence_band

        # Pass if mean coherence is acceptable and <10% of band is below threshold
        quality_passed = (
            mean_coherence >= min_coherence and
            low_coherence_fraction < 0.1
        )
    else:
        quality_passed = False
        quality_flags["error"] = "No frequencies in specified band"

    quality_flags["n_averages"] = n_averages
    quality_flags["passed"] = quality_passed

    return TransferFunctionResult(
        frequencies=freqs,
        H1=H1,
        H2=H2,
        Hv=Hv,
        coherence=coherence,
        n_averages=n_averages,
        quality_passed=quality_passed,
        quality_flags=quality_flags,
        magnitude_uncertainty=rel_uncertainty,
        phase_uncertainty_deg=phase_uncertainty_deg,
    )


def estimate_required_averages(
    target_coherence: float,
    target_error: float,
) -> int:
    """
    Estimate number of averages needed for target error at given coherence.

    Based on: σ_H / |H| ≈ √[(1 - γ²) / (2nγ²)]

    Solving for n: n = (1 - γ²) / (2γ² × ε²)

    Args:
        target_coherence: Expected coherence (0 to 1)
        target_error: Target relative error (e.g., 0.05 for 5%)

    Returns:
        Required number of averages
    """
    gamma_sq = target_coherence
    epsilon_sq = target_error ** 2

    n = (1 - gamma_sq) / (2 * gamma_sq * epsilon_sq)

    return max(1, int(np.ceil(n)))


def coherence_quality_report(
    result: TransferFunctionResult,
    frequency_bands: Optional[dict] = None,
) -> dict:
    """
    Generate detailed coherence quality report.

    Args:
        result: TransferFunctionResult
        frequency_bands: Dict of {name: (f_low, f_high)} for band analysis

    Returns:
        Quality report dictionary
    """
    if frequency_bands is None:
        frequency_bands = {
            "low": (20, 200),
            "mid": (200, 2000),
            "high": (2000, 10000),
            "full": (20, 20000),
        }

    report = {
        "overall": {
            "n_averages": result.n_averages,
            "passed": result.quality_passed,
        },
        "bands": {},
    }

    for band_name, (f_low, f_high) in frequency_bands.items():
        mask = (result.frequencies >= f_low) & (result.frequencies <= f_high)

        if np.any(mask):
            band_coh = result.coherence[mask]
            band_unc = result.magnitude_uncertainty[mask]

            report["bands"][band_name] = {
                "frequency_range_hz": [f_low, f_high],
                "mean_coherence": float(np.mean(band_coh)),
                "min_coherence": float(np.min(band_coh)),
                "max_coherence": float(np.max(band_coh)),
                "mean_magnitude_uncertainty_percent": float(np.mean(band_unc) * 100),
                "worst_magnitude_uncertainty_percent": float(np.max(band_unc) * 100),
                "n_points": int(np.sum(mask)),
            }

    return report
```

### 4. Multi-Tap Statistical Mode

```python
"""
tap_tone_pi/multitap/statistical.py

Multi-tap measurement with proper statistical analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import numpy as np
from scipy.stats import t as t_distribution

from ..uncertainty.budget import UncertaintyBudget, build_frequency_uncertainty_budget


@dataclass
class PeakStatistics:
    """Statistics for a single peak across multiple taps."""

    nominal_frequency_hz: float     # Expected/target frequency

    # Measurements
    frequencies: List[float]        # Individual measurements
    amplitudes: List[float]         # Individual amplitudes

    # Statistics
    mean_frequency_hz: float
    std_frequency_hz: float
    mean_amplitude: float
    std_amplitude: float

    # Uncertainty (proper treatment)
    uncertainty_budget: Optional[UncertaintyBudget]
    confidence_interval_hz: Tuple[float, float]

    # Quality flags
    n_detections: int               # How many taps found this peak
    n_total_taps: int               # Total taps attempted
    detection_rate: float           # n_detections / n_total_taps
    variance_acceptable: bool       # Std dev below threshold

    def to_dict(self) -> dict:
        return {
            "nominal_frequency_hz": self.nominal_frequency_hz,
            "mean_frequency_hz": self.mean_frequency_hz,
            "std_frequency_hz": self.std_frequency_hz,
            "confidence_interval_hz": list(self.confidence_interval_hz),
            "mean_amplitude": self.mean_amplitude,
            "std_amplitude": self.std_amplitude,
            "n_detections": self.n_detections,
            "n_total_taps": self.n_total_taps,
            "detection_rate": self.detection_rate,
            "variance_acceptable": self.variance_acceptable,
            "uncertainty_budget": self.uncertainty_budget.to_dict() if self.uncertainty_budget else None,
        }


@dataclass
class MultiTapResult:
    """Result of multi-tap statistical analysis."""

    n_taps: int
    peaks: List[PeakStatistics]

    # Overall quality
    all_peaks_consistent: bool
    mean_detection_rate: float

    # Raw data references
    tap_timestamps: List[float]

    def get_reliable_peaks(self, min_detection_rate: float = 0.8) -> List[PeakStatistics]:
        """Return only peaks detected in sufficient taps."""
        return [p for p in self.peaks if p.detection_rate >= min_detection_rate]


def analyze_multi_tap(
    tap_spectra: List[Tuple[np.ndarray, np.ndarray]],  # List of (freqs, magnitude) tuples
    fft_resolution_hz: float,
    expected_peaks_hz: Optional[List[float]] = None,
    peak_search_tolerance_hz: float = 10.0,
    max_variance_hz: float = 2.0,
    confidence_level: float = 0.95,
    temperature_c: Optional[float] = None,
) -> MultiTapResult:
    """
    Analyze multiple tap measurements with statistical treatment.

    Args:
        tap_spectra: List of (frequencies, magnitudes) from each tap
        fft_resolution_hz: FFT frequency resolution
        expected_peaks_hz: Expected peak frequencies (for tracking)
        peak_search_tolerance_hz: Search window around expected peaks
        max_variance_hz: Maximum acceptable std dev for pass
        confidence_level: Confidence level for intervals
        temperature_c: Temperature for uncertainty budget

    Returns:
        MultiTapResult with complete statistical analysis
    """
    n_taps = len(tap_spectra)

    if n_taps < 2:
        raise ValueError("Multi-tap analysis requires at least 2 taps")

    # If no expected peaks provided, find peaks in first tap
    if expected_peaks_hz is None:
        freqs, mags = tap_spectra[0]
        from scipy.signal import find_peaks
        peak_indices, _ = find_peaks(mags, height=np.max(mags) * 0.1, distance=10)
        expected_peaks_hz = [freqs[i] for i in peak_indices[:20]]  # Limit to 20 peaks

    # Track each expected peak across all taps
    peak_stats = []

    for expected_freq in expected_peaks_hz:
        detected_freqs = []
        detected_amps = []

        for freqs, mags in tap_spectra:
            # Search for peak near expected frequency
            search_mask = (
                (freqs >= expected_freq - peak_search_tolerance_hz) &
                (freqs <= expected_freq + peak_search_tolerance_hz)
            )

            if not np.any(search_mask):
                continue

            local_freqs = freqs[search_mask]
            local_mags = mags[search_mask]

            # Find local maximum
            peak_idx = np.argmax(local_mags)
            peak_freq = local_freqs[peak_idx]
            peak_amp = local_mags[peak_idx]

            # Only count if amplitude is significant
            if peak_amp > np.max(mags) * 0.05:
                detected_freqs.append(peak_freq)
                detected_amps.append(peak_amp)

        n_detections = len(detected_freqs)
        detection_rate = n_detections / n_taps

        if n_detections >= 2:
            freq_array = np.array(detected_freqs)
            amp_array = np.array(detected_amps)

            mean_freq = np.mean(freq_array)
            std_freq = np.std(freq_array, ddof=1)
            mean_amp = np.mean(amp_array)
            std_amp = np.std(amp_array, ddof=1)

            # Build uncertainty budget
            budget = build_frequency_uncertainty_budget(
                frequency_hz=mean_freq,
                measurements=freq_array,
                fft_resolution_hz=fft_resolution_hz,
                temperature_coefficient_hz_per_c=0.05 if temperature_c else 0.0,
                temperature_uncertainty_c=2.0 if temperature_c else 0.0,
            )

            # Confidence interval
            t_crit = t_distribution.ppf(
                (1 + confidence_level) / 2,
                n_detections - 1
            )
            margin = t_crit * std_freq / np.sqrt(n_detections)
            ci = (mean_freq - margin, mean_freq + margin)

            variance_ok = std_freq <= max_variance_hz

        elif n_detections == 1:
            mean_freq = detected_freqs[0]
            std_freq = fft_resolution_hz  # Use resolution as uncertainty
            mean_amp = detected_amps[0]
            std_amp = 0.0
            budget = None
            ci = (mean_freq - fft_resolution_hz, mean_freq + fft_resolution_hz)
            variance_ok = True  # Can't assess with single measurement

        else:
            # Peak not detected
            continue

        peak_stats.append(PeakStatistics(
            nominal_frequency_hz=expected_freq,
            frequencies=detected_freqs,
            amplitudes=detected_amps,
            mean_frequency_hz=mean_freq,
            std_frequency_hz=std_freq,
            mean_amplitude=mean_amp,
            std_amplitude=std_amp,
            uncertainty_budget=budget,
            confidence_interval_hz=ci,
            n_detections=n_detections,
            n_total_taps=n_taps,
            detection_rate=detection_rate,
            variance_acceptable=variance_ok,
        ))

    # Overall quality assessment
    if peak_stats:
        all_consistent = all(p.variance_acceptable for p in peak_stats)
        mean_rate = np.mean([p.detection_rate for p in peak_stats])
    else:
        all_consistent = False
        mean_rate = 0.0

    return MultiTapResult(
        n_taps=n_taps,
        peaks=peak_stats,
        all_peaks_consistent=all_consistent,
        mean_detection_rate=mean_rate,
        tap_timestamps=[],  # Would be filled by caller
    )
```

---

## Summary

This document provides:

1. **Detailed analysis** of free-form and fixed-displacement testing methods
2. **Viable evolution paths** for both approaches
3. **Honest assessment** of physics gaps in simplified implementations
4. **Production-grade code examples** for:
   - Cross-validated damping extraction (3 methods)
   - ISO GUM uncertainty budgets
   - Transfer function with coherence quality gates
   - Multi-tap statistical analysis

The code examples are designed as drop-in modules for Tap Tone Pi, implementing Option A (production-grade physics) with proper mathematical rigor.

### Next Steps

1. Integrate these modules into `tap_tone_pi/`
2. Add unit tests for each module
3. Update CLI commands to use production-grade analysis
4. Design displacement fixture hardware
5. Implement calibration workflow linking tap and displacement methods
