# Coherence Interpretation

Coherence (γ²) measures how linearly related the output is to the input at each
frequency. It's your primary indicator of measurement quality.

## Definition

Coherence is defined as:

```
γ²(f) = |Gxy(f)|² / (Gxx(f) × Gyy(f))
```

Where:
- Gxy = Cross-spectral density (input × output*)
- Gxx = Auto-spectral density of input
- Gyy = Auto-spectral density of output

**Range**: 0 ≤ γ² ≤ 1

## What Coherence Tells You

| Coherence | Meaning |
|-----------|---------|
| γ² = 1.0 | Perfect linear relationship, no noise |
| γ² > 0.9 | Excellent measurement quality |
| γ² > 0.8 | Good, acceptable for most purposes |
| γ² > 0.6 | Marginal, consider more averaging |
| γ² < 0.5 | Poor, investigate the cause |
| γ² ≈ 0 | No linear relationship at this frequency |

## Causes of Low Coherence

### 1. Noise on Input or Output

Random noise is uncorrelated with the signal, reducing coherence.

**Symptoms**:
- Broadband coherence reduction
- Improves with more averaging

**Solutions**:
- Increase excitation level
- Reduce ambient noise
- Use more averages

### 2. Low Signal Level

At frequencies where your system has low response (antiresonances), the
signal-to-noise ratio drops.

**Symptoms**:
- Coherence dips at specific frequencies
- Corresponds to valleys in the response

**Solutions**:
- Use shaped excitation (more energy where needed)
- Accept that antiresonances have lower quality
- Use more averages at low-energy frequencies

### 3. Nonlinearity

If the system isn't linear, the output isn't a simple scaled version of the input.

**Symptoms**:
- Coherence drops at high excitation levels
- Distortion visible in time domain

**Solutions**:
- Reduce excitation level
- Check for mechanical issues (rub, buzz)
- Consider nonlinear analysis methods

### 4. External Disturbances

Uncorrelated noise sources (HVAC, traffic, electrical interference).

**Symptoms**:
- Coherence drops at specific frequencies (60 Hz, fan speeds)
- May vary with time

**Solutions**:
- Identify and eliminate sources
- Use better shielding
- Measure at quiet times

### 5. Time Variance

If the system changes during measurement, coherence suffers.

**Symptoms**:
- Erratic coherence
- Different results on repeat measurements

**Solutions**:
- Shorter measurement blocks
- Wait for system to stabilize
- Check for temperature changes

### 6. Leakage (Improper FFT Processing)

If the signal isn't properly windowed, leakage creates spurious correlations.

**Symptoms**:
- Artificially high coherence (surprising!)
- Smeared spectral peaks

**Solutions**:
- Use appropriate window function
- Ensure adequate frequency resolution

## Coherence and Uncertainty

Coherence directly relates to measurement uncertainty:

```
Random error in H(f) ≈ √[(1 - γ²) / (2 × n × γ²)]
```

Where n = number of averages.

### Required Averages for Target Error

| Target Error | γ² = 0.9 | γ² = 0.7 | γ² = 0.5 |
|--------------|----------|----------|----------|
| 10%          | 1        | 2        | 5        |
| 5%           | 3        | 9        | 20       |
| 1%           | 56       | 214      | 500      |

**Conclusion**: High coherence dramatically reduces required averaging.

## Frequency-Dependent Coherence

Coherence typically varies with frequency:

```
        1.0 ┤■■■■■■■■■■■■■■■■■■■■■■■■■■
            │
γ²      0.8 ┤          ▄▄▄▄       ▄▄▄▄
            │         ▄    ▄    ▄    ▄▄
        0.6 ┤        ▄      ▄  ▄
            │       ▄        ▄▄
        0.4 ┤      ▄
            │     ▄
        0.2 ┤ ▄▄▄▄                      ← Low-frequency issues
            │                              (poor excitation)
        0.0 ┼─────────────────────────────
            20  100   500  2k   10k  20k Hz
```

### Common Patterns

**Low at low frequencies**:
- Insufficient excitation energy below 50 Hz
- 1/f noise dominates
- Solution: Longer time records, stronger excitation

**Low at high frequencies**:
- System response rolls off
- ADC noise floor reached
- Solution: Accept or use higher excitation

**Notches at specific frequencies**:
- Antiresonances in system
- Environmental interference
- Normal for some frequencies

## Using Coherence for Quality Control

### Accept/Reject Criteria

For production testing:
```python
def check_measurement_quality(coherence, freqs, accept_threshold=0.8):
    """
    Check if measurement meets quality criteria.
    """
    # Define frequency bands of interest
    bands = [
        (20, 100, 0.6),    # Low: relaxed threshold
        (100, 2000, 0.8),  # Mid: standard threshold
        (2000, 10000, 0.7) # High: slightly relaxed
    ]

    for f_low, f_high, threshold in bands:
        mask = (freqs >= f_low) & (freqs <= f_high)
        band_coherence = np.mean(coherence[mask])
        if band_coherence < threshold:
            return False, f"Low coherence in {f_low}-{f_high} Hz"

    return True, "Measurement quality acceptable"
```

### Coherence-Weighted Averaging

Weight transfer function by coherence:
```python
# Instead of simple average:
H_avg = np.mean(H_measurements, axis=0)

# Use coherence-weighted average:
weights = coherence ** 2
H_weighted = np.sum(H_measurements * weights, axis=0) / np.sum(weights, axis=0)
```

## Coherence vs. Correlation

| Concept | Domain | Range | Meaning |
|---------|--------|-------|---------|
| Correlation | Time | -1 to +1 | Linear relationship in time |
| Coherence | Frequency | 0 to 1 | Linear relationship at each frequency |

Coherence is the frequency-domain equivalent of squared correlation coefficient.

## Practical Tips

1. **Always plot coherence** alongside transfer function
2. **Don't trust H(f) where γ² < 0.5** - mark as suspect
3. **Use coherence to debug setups** - it reveals problems
4. **Average more where coherence is low** - if possible
5. **Report coherence** - it's a quality metric

## Code Example: Coherence Calculation

```python
import numpy as np
from scipy.signal import csd, welch

def compute_coherence(x, y, sample_rate, nperseg=4096):
    """
    Compute coherence between input x and output y.
    """
    # Auto-spectra
    freqs, Gxx = welch(x, sample_rate, nperseg=nperseg)
    _, Gyy = welch(y, sample_rate, nperseg=nperseg)

    # Cross-spectrum
    _, Gxy = csd(x, y, sample_rate, nperseg=nperseg)

    # Coherence
    coherence = np.abs(Gxy)**2 / (Gxx * Gyy + 1e-10)

    return freqs, coherence
```

## Related Topics

- [FFT Fundamentals](fft_fundamentals.md) - How spectra are computed
- [Transfer Functions](transfer_function.md) - Using H1/H2 based on coherence
- [Uncertainty and Averaging](uncertainty_averaging.md) - Coherence and error
