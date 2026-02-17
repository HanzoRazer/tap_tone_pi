# Uncertainty and Averaging

Averaging multiple measurements reduces random error. Understanding how many averages
you need—and when averaging helps vs. when it doesn't—is essential for efficient,
accurate measurements.

## Why Average?

Every measurement contains:
1. **Signal**: The quantity you want to measure
2. **Random noise**: Uncorrelated with signal
3. **Bias**: Systematic error (averaging doesn't help!)

Averaging reduces random noise by √n while preserving the signal.

## The √n Rule

For random noise with standard deviation σ:

```
After n averages: σ_averaged = σ / √n
```

| Averages | Noise Reduction | dB Improvement |
|----------|-----------------|----------------|
| 1        | 1×              | 0 dB           |
| 4        | 2×              | 6 dB           |
| 16       | 4×              | 12 dB          |
| 64       | 8×              | 18 dB          |
| 256      | 16×             | 24 dB          |

**Key insight**: Doubling averages only reduces noise by 3 dB.

## Types of Averaging

### Linear Averaging (RMS)

```python
# Standard averaging: reduces random error
avg_spectrum = np.sqrt(np.mean(spectra**2, axis=0))
```

Best for: Random signals, noise reduction

### Exponential Averaging

```python
# Weighted toward recent measurements
new_avg = alpha * new_spectrum + (1 - alpha) * old_avg
```

Best for: Tracking slowly-changing signals

### Peak Hold

```python
# Keep maximum at each frequency
peak = np.maximum(peak, new_spectrum)
```

Best for: Finding transient events, impact testing

### Vector Averaging (Coherent)

```python
# Average complex spectra (preserves phase)
avg_complex = np.mean(complex_spectra, axis=0)
```

Best for: Time-synchronous averaging, canceling non-coherent content

## How Many Averages?

### Based on Coherence

The normalized random error in |H(f)| is:

```
ε = √[(1 - γ²) / (2 × n × γ²)]
```

Rearranging to find required averages for target error:

```python
def required_averages(coherence, target_error):
    """Calculate averages needed for target relative error."""
    gamma_sq = coherence ** 2
    n = (1 - gamma_sq) / (2 * gamma_sq * target_error**2)
    return int(np.ceil(n))
```

### Practical Recommendations

| Coherence | Averages for 5% error | Averages for 1% error |
|-----------|----------------------|----------------------|
| 0.99      | 1                    | 6                    |
| 0.95      | 1                    | 14                   |
| 0.90      | 3                    | 56                   |
| 0.80      | 8                    | 156                  |
| 0.70      | 15                   | 357                  |
| 0.50      | 50                   | 1000+                |

**Rule of thumb**: For coherence > 0.9, 10-20 averages is usually sufficient.

## Overlap Processing

When using FFT-based analysis, you can increase averages per unit time by overlapping:

```
                Block 1: [====]
                Block 2:    [====]
                Block 3:       [====]
                                  ... etc.

With 50% overlap: 2× more averages in same time
With 75% overlap: 4× more averages
With 87.5% overlap: 8× more averages
```

But overlapped blocks are not independent, so the effective number of averages is:

```python
def effective_averages(n_blocks, overlap_fraction):
    """Estimate effective independent averages."""
    independence = 1 - overlap_fraction
    return n_blocks * independence + overlap_fraction
```

For 75% overlap with 16 blocks:
```
Effective averages ≈ 16 × 0.25 + 0.75 = 4.75 ≈ 5 independent averages
```

## When Averaging Doesn't Help

### 1. Systematic Bias

If your measurement has a consistent offset or scaling error:
```
True value = 100 Hz
Every measurement = 105 Hz
After 1000 averages = 105 Hz (bias unchanged!)
```

**Solution**: Calibrate, not average.

### 2. Coherent Interference

If noise is synchronized with your signal:
```
60 Hz power line hum + 60 Hz signal
= inseparable with averaging
```

**Solution**: Change frequency, filter, or use synchronous detection.

### 3. Time-Varying Systems

If the system changes during measurement:
```
Measurement 1: f_resonance = 100 Hz
Measurement 10: f_resonance = 102 Hz
Average ≠ either!
```

**Solution**: Use shorter blocks, track changes.

### 4. Already at Noise Floor

If SNR is effectively infinite:
```
More averages = more time with no benefit
```

**Solution**: Stop averaging when results stabilize.

## Statistical Confidence

### Confidence Intervals

For normally distributed measurements:

| Confidence | Multiplier |
|------------|------------|
| 68%        | ±1σ        |
| 90%        | ±1.65σ     |
| 95%        | ±1.96σ     |
| 99%        | ±2.58σ     |

```python
def confidence_interval(values, confidence=0.95):
    """Calculate confidence interval for mean."""
    import scipy.stats as stats
    n = len(values)
    mean = np.mean(values)
    std_err = np.std(values, ddof=1) / np.sqrt(n)
    t_value = stats.t.ppf((1 + confidence) / 2, n - 1)
    margin = t_value * std_err
    return mean - margin, mean + margin
```

### Coefficient of Variation

The CV indicates measurement repeatability:

```
CV = (standard deviation / mean) × 100%
```

| CV | Interpretation |
|----|----------------|
| < 1% | Excellent repeatability |
| 1-5% | Good |
| 5-10% | Acceptable |
| > 10% | Poor, investigate |

## Practical Averaging Strategies

### Strategy 1: Fixed Count

```python
# Always take 16 averages
for i in range(16):
    spectrum = measure()
    accumulator += spectrum ** 2
result = np.sqrt(accumulator / 16)
```

Simple but may under- or over-average.

### Strategy 2: Adaptive

```python
# Average until stability criterion met
while not stable:
    new_spectrum = measure()
    accumulator += new_spectrum ** 2
    count += 1
    current = np.sqrt(accumulator / count)
    if count > 1:
        change = np.max(np.abs(current - previous) / previous)
        stable = change < 0.01 and count >= min_averages
    previous = current
```

Efficient but requires stability detection.

### Strategy 3: Time-Limited

```python
# Average for fixed time duration
start = time.time()
while time.time() - start < max_time:
    spectrum = measure()
    accumulator += spectrum ** 2
    count += 1
result = np.sqrt(accumulator / count)
```

Predictable measurement time.

## Weighted Averaging

When measurements have different quality:

```python
def weighted_average(spectra, weights):
    """Average spectra weighted by quality (e.g., coherence)."""
    weighted_sum = np.sum(spectra * weights[:, np.newaxis], axis=0)
    weight_sum = np.sum(weights)
    return weighted_sum / weight_sum
```

Use coherence as weight: high-coherence measurements contribute more.

## Reporting Uncertainty

Always report:
1. **Number of averages** used
2. **Coherence** (or SNR)
3. **Confidence interval** or standard deviation
4. **Any outliers rejected**

Example:
```
Resonant frequency: 125.3 Hz ± 0.4 Hz (95% CI)
n = 20 averages, γ² > 0.95 at resonance
```

## Summary Table: Averaging Recommendations

| Application | Min Averages | Target Coherence | Notes |
|-------------|--------------|------------------|-------|
| Quick check | 4 | 0.8 | Screening only |
| Production test | 10-20 | 0.9 | Standard |
| Lab characterization | 50+ | 0.95 | High accuracy |
| Research/publication | 100+ | 0.99 | Best possible |
| Real-time monitoring | Exp avg (α=0.1) | 0.7 | Tracking |

## Related Topics

- [FFT Fundamentals](fft_fundamentals.md) - Block size and resolution
- [Coherence Interpretation](coherence_interpretation.md) - Quality indicator
- [Common Measurement Errors](common_errors.md) - Avoiding systematic bias
