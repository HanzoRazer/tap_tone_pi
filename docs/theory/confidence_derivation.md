# Confidence Score Derivation for FFT Peak Detection

This document derives a physics-based confidence score for FFT spectral peaks,
replacing arbitrary heuristics with quantifiable metrics.

## The Problem with Heuristic Confidence

The current implementation uses:

```python
confidence = 0.5 + 0.5 * normalized_magnitude  # BAD
```

This has several issues:
1. No physical meaning
2. Ignores noise floor
3. Same confidence for loud noise and quiet signal
4. Doesn't account for spectral shape

## Physics-Based Confidence Factors

A proper confidence score should consider:

1. **Signal-to-Noise Ratio (SNR)**: Is the peak above the noise?
2. **Spectral Flatness**: Is this a tonal peak or broadband noise?
3. **Peak Sharpness**: Does it look like a resonance (Q factor)?
4. **Coherence** (if available): Is the peak consistent across measurements?

## Derivation

### 1. SNR-Based Confidence

The probability that a peak is real (not noise) follows a sigmoid based on SNR:

```
                    1
conf_SNR = ─────────────────────────
           1 + exp(-(SNR_dB - τ) / σ)

where:
    τ = SNR threshold (default: 15 dB)
    σ = transition steepness (default: 5 dB)
```

**Rationale:**
- SNR < 10 dB: Very likely noise (conf → 0.1)
- SNR = 15 dB: Marginal (conf = 0.5)
- SNR > 20 dB: Likely signal (conf → 0.9)
- SNR > 30 dB: Definitely signal (conf → 1.0)

### Computing SNR from Spectrum

```python
def compute_local_snr(spectrum: np.ndarray, peak_idx: int, noise_band: int = 20) -> float:
    """
    Compute local SNR at a spectral peak.

    Args:
        spectrum: Magnitude spectrum (linear scale)
        peak_idx: Index of the peak
        noise_band: Number of bins on each side for noise estimation

    Returns:
        SNR in dB
    """
    peak_power = spectrum[peak_idx] ** 2

    # Estimate noise from neighboring bins (excluding peak region)
    left_start = max(0, peak_idx - noise_band - 5)
    left_end = max(0, peak_idx - 5)
    right_start = min(len(spectrum) - 1, peak_idx + 5)
    right_end = min(len(spectrum) - 1, peak_idx + noise_band + 5)

    noise_bins = np.concatenate([
        spectrum[left_start:left_end],
        spectrum[right_start:right_end]
    ])

    if len(noise_bins) < 3:
        return 0.0  # Cannot estimate noise

    # Use median for robust noise estimate
    noise_power = np.median(noise_bins) ** 2

    if noise_power < 1e-20:
        return 60.0  # Very high SNR (cap at 60 dB)

    snr_linear = peak_power / noise_power
    snr_db = 10 * np.log10(snr_linear)

    return float(np.clip(snr_db, 0, 60))
```

### 2. Spectral Flatness

Spectral flatness measures how "tonal" vs "noisy" the signal is:

```
              geometric_mean(spectrum)
SF = ────────────────────────────────────
              arithmetic_mean(spectrum)

Range: 0 (pure tone) to 1 (white noise)
```

For confidence, we want low flatness (tonal) = high confidence:

```
conf_flatness = 1 - SF
```

**Rationale:**
- Modal vibration produces tonal peaks (SF ≈ 0.1-0.3)
- Random noise produces flat spectrum (SF ≈ 0.8-1.0)

### Computing Local Spectral Flatness

```python
def compute_local_flatness(spectrum: np.ndarray, center_idx: int, bandwidth: int = 10) -> float:
    """
    Compute spectral flatness in region around a peak.

    Args:
        spectrum: Magnitude spectrum
        center_idx: Center of analysis region
        bandwidth: Number of bins on each side

    Returns:
        Spectral flatness (0 = tonal, 1 = noise-like)
    """
    start = max(0, center_idx - bandwidth)
    end = min(len(spectrum), center_idx + bandwidth + 1)

    region = spectrum[start:end]

    if len(region) < 3 or np.all(region == 0):
        return 0.5

    # Avoid log of zero
    region = np.maximum(region, 1e-20)

    geometric_mean = np.exp(np.mean(np.log(region)))
    arithmetic_mean = np.mean(region)

    if arithmetic_mean < 1e-20:
        return 0.5

    flatness = geometric_mean / arithmetic_mean
    return float(np.clip(flatness, 0, 1))
```

### 3. Peak Sharpness (Q Factor Proxy)

A real resonance has a characteristic shape. We can estimate Q from the half-power bandwidth:

```
Q = f_center / (f_upper - f_lower)

where f_upper, f_lower are the -3dB points
```

High Q → sharp peak → more likely a real mode:

```
conf_Q = 1 - exp(-Q / Q_ref)

where Q_ref = 20 (typical modal Q for wood)
```

### 4. Coherence (When Available)

For dual-channel measurements, coherence directly indicates linearity:

```
conf_coherence = γ² (direct mapping)
```

## Combined Confidence Score

The overall confidence combines factors with appropriate weights:

```
              w_SNR × conf_SNR + w_flat × conf_flat + w_Q × conf_Q + w_coh × conf_coh
confidence = ──────────────────────────────────────────────────────────────────────────
                                   w_SNR + w_flat + w_Q + w_coh

Default weights:
    w_SNR = 0.40   (most important)
    w_flat = 0.20
    w_Q = 0.20
    w_coh = 0.20   (only if available)
```

## Implementation

```python
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np


@dataclass
class ConfidenceComponents:
    """Components of the confidence score."""
    snr_db: float
    snr_confidence: float
    flatness: float
    flatness_confidence: float
    q_factor: Optional[float]
    q_confidence: float
    coherence: Optional[float]
    coherence_confidence: float
    overall: float


def compute_peak_confidence(
    spectrum: np.ndarray,
    freqs: np.ndarray,
    peak_idx: int,
    sample_rate: int,
    coherence: Optional[float] = None,
    snr_threshold: float = 15.0,
    snr_steepness: float = 5.0,
    q_reference: float = 20.0,
) -> ConfidenceComponents:
    """
    Compute physics-based confidence for a spectral peak.

    Args:
        spectrum: Magnitude spectrum (linear scale)
        freqs: Frequency array (Hz)
        peak_idx: Index of the peak
        sample_rate: Sample rate (Hz)
        coherence: Coherence at peak frequency (if available)
        snr_threshold: SNR (dB) for 50% confidence
        snr_steepness: Transition rate (dB)
        q_reference: Reference Q for confidence scaling

    Returns:
        ConfidenceComponents with all factors
    """
    # SNR
    snr_db = compute_local_snr(spectrum, peak_idx)
    conf_snr = 1.0 / (1.0 + np.exp(-(snr_db - snr_threshold) / snr_steepness))

    # Flatness
    flatness = compute_local_flatness(spectrum, peak_idx)
    conf_flat = 1.0 - flatness

    # Q factor (estimate from half-power bandwidth)
    q_factor, conf_q = estimate_q_factor(spectrum, freqs, peak_idx)

    # Coherence
    if coherence is not None:
        conf_coh = float(coherence)
    else:
        conf_coh = 1.0  # No penalty if not available

    # Weighted combination
    if coherence is not None:
        weights = {"snr": 0.35, "flat": 0.20, "q": 0.20, "coh": 0.25}
    else:
        weights = {"snr": 0.45, "flat": 0.25, "q": 0.30, "coh": 0.0}

    overall = (
        weights["snr"] * conf_snr +
        weights["flat"] * conf_flat +
        weights["q"] * conf_q +
        weights["coh"] * conf_coh
    )

    return ConfidenceComponents(
        snr_db=snr_db,
        snr_confidence=conf_snr,
        flatness=flatness,
        flatness_confidence=conf_flat,
        q_factor=q_factor,
        q_confidence=conf_q,
        coherence=coherence,
        coherence_confidence=conf_coh,
        overall=float(np.clip(overall, 0, 1)),
    )


def estimate_q_factor(
    spectrum: np.ndarray,
    freqs: np.ndarray,
    peak_idx: int,
    q_reference: float = 20.0,
) -> Tuple[Optional[float], float]:
    """
    Estimate Q factor from half-power bandwidth.

    Returns:
        (q_factor, q_confidence)
    """
    peak_mag = spectrum[peak_idx]
    half_power = peak_mag / np.sqrt(2)

    # Find -3dB points
    # Left side
    left_idx = peak_idx
    while left_idx > 0 and spectrum[left_idx] > half_power:
        left_idx -= 1

    # Right side
    right_idx = peak_idx
    while right_idx < len(spectrum) - 1 and spectrum[right_idx] > half_power:
        right_idx += 1

    if left_idx == 0 or right_idx == len(spectrum) - 1:
        # Couldn't find both -3dB points
        return None, 0.5

    # Interpolate for precise crossing
    f_center = freqs[peak_idx]

    if spectrum[left_idx] != spectrum[left_idx + 1]:
        f_lower = np.interp(
            half_power,
            [spectrum[left_idx], spectrum[left_idx + 1]],
            [freqs[left_idx], freqs[left_idx + 1]]
        )
    else:
        f_lower = freqs[left_idx]

    if spectrum[right_idx] != spectrum[right_idx - 1]:
        f_upper = np.interp(
            half_power,
            [spectrum[right_idx], spectrum[right_idx - 1]],
            [freqs[right_idx], freqs[right_idx - 1]]
        )
    else:
        f_upper = freqs[right_idx]

    bandwidth = f_upper - f_lower

    if bandwidth <= 0:
        return None, 0.5

    q = f_center / bandwidth

    # Q confidence: higher Q = higher confidence (up to a point)
    # Q < 5: probably not a resonance (conf → 0.2)
    # Q ~ 20: typical mode (conf → 0.6)
    # Q > 50: very sharp resonance (conf → 0.9)
    conf_q = 1.0 - np.exp(-q / q_reference)

    return float(q), float(np.clip(conf_q, 0, 1))
```

## Validation

### Synthetic Test Cases

| Test Case | SNR (dB) | Flatness | Q | Expected Confidence |
|-----------|----------|----------|---|---------------------|
| Pure tone in quiet | 40 | 0.1 | 100 | > 0.95 |
| Mode in noise | 20 | 0.3 | 30 | 0.7-0.8 |
| Weak mode | 12 | 0.4 | 15 | 0.4-0.6 |
| Noise peak | 8 | 0.7 | 5 | 0.2-0.3 |
| White noise | 3 | 0.9 | 2 | < 0.15 |

### Empirical Verification

The confidence score should correlate with:
1. Human operator assessment of "real" vs "noise" peaks
2. Repeatability across multiple tap measurements
3. Coherence (for dual-channel measurements)

## Migration Path

To replace the existing heuristic:

1. **Phase 1**: Add new confidence calculation alongside old
2. **Phase 2**: Log both values, compare
3. **Phase 3**: Replace old with new
4. **Phase 4**: Tune weights based on validation data

## Summary

| Factor | Weight | Rationale |
|--------|--------|-----------|
| SNR | 0.35-0.45 | Primary indicator of peak vs noise |
| Flatness | 0.20-0.25 | Tonal vs broadband character |
| Q factor | 0.20-0.30 | Resonance shape characteristic |
| Coherence | 0.20-0.25 | Consistency across measurements |

The combined score provides:
- Physical interpretability
- Tunable thresholds
- Component-level diagnostics
- Graceful handling of missing coherence data
