# Transfer Functions

The transfer function H(f) describes how a system responds at each frequency.
Different estimators (H1, H2, Hv) are optimal for different noise conditions.

## What is a Transfer Function?

For a linear system:
```
Output(f) = H(f) × Input(f)
```

The transfer function H(f) is complex-valued:
- **Magnitude |H(f)|**: Gain at each frequency
- **Phase ∠H(f)**: Phase shift at each frequency

## The Three Estimators

### H1 Estimator

```
H1(f) = Gxy(f) / Gxx(f)
```

**Assumption**: Noise is on the output (measurement noise, ambient pickup)

**Properties**:
- Underestimates true H(f) when noise is present
- Best when input is clean (controlled excitation)
- Most common choice for acoustic measurements

**Use when**:
- You control the excitation signal
- Measurement pickup has ambient noise
- Output SNR < Input SNR

### H2 Estimator

```
H2(f) = Gyy(f) / Gyx(f)
```

**Assumption**: Noise is on the input (noisy force measurement, impact hammer ringing)

**Properties**:
- Overestimates true H(f) when noise is present
- Best when output is clean
- Compensates for input measurement issues

**Use when**:
- Input measurement has issues (cable noise, sensor noise)
- Impact hammer measurements (ringing on force signal)
- Input SNR < Output SNR

### Hv Estimator

```
Hv(f) = √(H1 × H2)
```

**Assumption**: Noise is on both input and output equally

**Properties**:
- Geometric mean of H1 and H2
- Less biased when both channels have noise
- Requires both H1 and H2 calculation

**Use when**:
- Uncertain about noise distribution
- Both channels have similar SNR
- Want a "middle ground" estimate

## Choosing an Estimator

```
                  Where is the noise?
                         │
         ┌───── Output ──┴── Input ───┬─── Both ───┐
         ▼                            ▼            ▼
        H1                           H2           Hv
    (most common)              (force sensors)  (uncertain)
```

### Decision Guide

| Scenario | Estimator |
|----------|-----------|
| Controlled sweep excitation | H1 |
| Impact hammer measurement | H2 (ringing on hammer) |
| Ambient noise pickup | H1 |
| Noisy force transducer | H2 |
| Electrical pickup on input | H2 |
| Unknown noise sources | Hv |
| High coherence (γ² > 0.95) | Any (they converge) |

## Relationship with Coherence

When coherence is perfect (γ² = 1):
```
H1 = H2 = Hv = H_true
```

When coherence is imperfect:
```
H1 ≤ H_true ≤ H2
Hv ≈ H_true (if noise is balanced)
```

The ratio H1/H2 is related to coherence:
```
γ² = H1 / H2
```

## Practical Implementation

### Computing All Three Estimators

```python
import numpy as np
from scipy.signal import csd, welch

def compute_transfer_functions(input_signal, output_signal, sample_rate,
                                nperseg=4096, noverlap=None):
    """
    Compute H1, H2, and Hv transfer function estimators.

    Returns:
        freqs, H1, H2, Hv, coherence
    """
    if noverlap is None:
        noverlap = nperseg // 2

    # Auto-spectra
    freqs, Gxx = welch(input_signal, sample_rate,
                       nperseg=nperseg, noverlap=noverlap)
    _, Gyy = welch(output_signal, sample_rate,
                   nperseg=nperseg, noverlap=noverlap)

    # Cross-spectra
    _, Gxy = csd(input_signal, output_signal, sample_rate,
                 nperseg=nperseg, noverlap=noverlap)
    _, Gyx = csd(output_signal, input_signal, sample_rate,
                 nperseg=nperseg, noverlap=noverlap)

    # Estimators (with small epsilon for numerical stability)
    eps = 1e-10
    H1 = Gxy / (Gxx + eps)
    H2 = Gyy / (Gyx + eps)
    Hv = np.sqrt(H1 * H2)

    # Coherence
    coherence = np.abs(Gxy)**2 / (Gxx * Gyy + eps)

    return freqs, H1, H2, Hv, coherence
```

### Visualizing Estimator Differences

```python
import matplotlib.pyplot as plt

def plot_estimator_comparison(freqs, H1, H2, Hv, coherence):
    """Plot all estimators with coherence overlay."""
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 8), sharex=True)

    # Magnitude
    ax1.semilogy(freqs, np.abs(H1), label='H1')
    ax1.semilogy(freqs, np.abs(H2), label='H2')
    ax1.semilogy(freqs, np.abs(Hv), label='Hv', linestyle='--')
    ax1.set_ylabel('Magnitude')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Phase
    ax2.plot(freqs, np.angle(H1, deg=True), label='H1')
    ax2.plot(freqs, np.angle(H2, deg=True), label='H2')
    ax2.set_ylabel('Phase (degrees)')
    ax2.set_ylim(-180, 180)
    ax2.grid(True, alpha=0.3)

    # Coherence
    ax3.plot(freqs, coherence)
    ax3.axhline(y=0.8, color='r', linestyle='--', alpha=0.5)
    ax3.set_ylabel('Coherence')
    ax3.set_xlabel('Frequency (Hz)')
    ax3.set_ylim(0, 1)
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig
```

## Units and Scaling

The transfer function has units of output/input:

| Measurement Type | Units |
|------------------|-------|
| Electrical gain | V/V (dimensionless) |
| Mechanical mobility | (m/s)/N = m/(N·s) |
| Accelerance | (m/s²)/N |
| Acoustic response | Pa/V (speaker) |

For sound pressure per force (tap testing):
```
H(f) has units of Pa/N
```

In dB:
```
|H(f)|_dB = 20 × log10(|H(f)|)
```

## Phase Interpretation

The phase of H(f) tells you the time delay at each frequency:

```
Group delay = -dφ/dω = -(1/2π) × d(phase)/d(frequency)
```

For minimum-phase systems:
- Phase is uniquely determined by magnitude
- Phase approaches 0° at low frequencies
- Phase approaches -90° × (number of poles) at high frequencies

For non-minimum-phase systems:
- Additional phase from delays or zeros
- More complex phase patterns

## Special Cases

### Resonance

At resonance:
- Magnitude peaks
- Phase passes through -90° (or +90° for antiresonance)
- Coherence may drop (nonlinearity at high amplitude)

### Antiresonance

At antiresonance:
- Magnitude has a notch
- Phase shifts rapidly
- Coherence drops (low SNR)

### Rigid Body Modes

Below the first resonance:
- Magnitude approximately constant
- Phase approximately 0° or 180°
- Represents rigid body motion

## Error Analysis

The uncertainty in H(f) depends on coherence and averaging:

```
Normalized standard error of |H|:

σ_H / |H| ≈ √[(1 - γ²) / (2 × n × γ²)]
```

Where n = number of averages.

### Confidence Bounds

For 95% confidence:
```
|H|_true ∈ |H|_measured × [1 - 2σ, 1 + 2σ]
```

## Best Practices

1. **Always compute coherence** - it validates your transfer function
2. **Use H1 for most acoustic measurements** - excitation is usually cleaner
3. **Switch to H2 for impact testing** - hammer ringing contaminates input
4. **Compare H1 and H2** - large differences indicate problems
5. **Report which estimator you used** - for reproducibility

## Related Topics

- [FFT Fundamentals](fft_fundamentals.md) - How spectra are computed
- [Coherence Interpretation](coherence_interpretation.md) - Validating measurements
- [Uncertainty and Averaging](uncertainty_averaging.md) - Error reduction
