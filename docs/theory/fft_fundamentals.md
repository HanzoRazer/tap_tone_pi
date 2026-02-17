# FFT Fundamentals

The Fast Fourier Transform (FFT) is the foundation of frequency analysis. Understanding
its properties is essential for correct interpretation of spectral measurements.

## What the FFT Does

The FFT converts a time-domain signal into its frequency components. Given N samples
at sample rate fs:

- **Frequency resolution**: Δf = fs / N
- **Maximum frequency**: fmax = fs / 2 (Nyquist frequency)
- **Number of frequency bins**: N/2 + 1 (for real signals)

### Example

```
Sample rate: 48000 Hz
Block size:  4096 samples
→ Frequency resolution: 48000 / 4096 = 11.7 Hz
→ Frequency range: 0 Hz to 24000 Hz
→ Number of bins: 2049
```

## Frequency Resolution vs. Time Resolution

There's a fundamental trade-off:

| Block Size | Freq Resolution | Time to Acquire |
|------------|-----------------|-----------------|
| 1024       | 46.9 Hz         | 21 ms           |
| 4096       | 11.7 Hz         | 85 ms           |
| 16384      | 2.9 Hz          | 341 ms          |
| 65536      | 0.73 Hz         | 1.37 s          |

**Rule of thumb**: To resolve two frequencies f1 and f2, you need:
```
Block size ≥ fs / |f2 - f1|
```

For guitar modes spaced 5 Hz apart at 48 kHz sample rate:
```
Block size ≥ 48000 / 5 = 9600 → use 16384
```

## Spectral Leakage

The FFT assumes your signal is periodic within the analysis window. When it's not,
energy "leaks" from each frequency into neighboring bins.

### The Problem

Consider a 100 Hz sine wave analyzed with an FFT:
- If exactly 10 cycles fit in the window: Sharp peak at 100 Hz
- If 10.5 cycles fit: Energy spreads across many bins

This happens because the FFT "sees" a discontinuity at the window edges where the
signal doesn't smoothly connect back to its start.

### The Solution: Windowing

A **window function** tapers the signal to zero at the edges, eliminating the
discontinuity:

```
windowed_signal = raw_signal × window_function
```

## Window Functions

Different windows trade off frequency resolution against leakage suppression:

| Window | Main Lobe Width | Side Lobe Level | Best For |
|--------|-----------------|-----------------|----------|
| Rectangular | Narrowest | -13 dB | Transient analysis |
| Hanning | 1.5× | -32 dB | General purpose |
| Hamming | 1.4× | -43 dB | General purpose |
| Blackman | 1.7× | -58 dB | Close frequencies |
| Flat-top | 3.8× | -93 dB | Amplitude accuracy |
| Kaiser (β=8.6) | Adjustable | -100 dB | Narrowband signals |

### Choosing a Window

```
                      Need accurate amplitude?
                              │
              ┌───── YES ─────┴───── NO ─────┐
              ▼                              ▼
         Flat-top                   Close-spaced peaks?
                                          │
                          ┌───── YES ─────┴───── NO ─────┐
                          ▼                              ▼
                     Blackman                       Hanning
```

**Tap Tone Pi default**: Hanning window (good balance for modal analysis)

## Coherent Gain and Scaling

Windows reduce the effective signal level. To get correct amplitudes:

```python
# Coherent gain correction
coherent_gain = np.sum(window) / len(window)
corrected_spectrum = spectrum / coherent_gain
```

For power spectra, use the **energy correction factor**:
```python
energy_correction = np.sum(window**2) / len(window)
corrected_power = power / energy_correction
```

## Practical FFT Settings in Tap Tone Pi

### For Tap Testing (Impulse Response)

```python
fft_size = 8192      # Good resolution, fast enough
window = "hanning"   # Suppresses leakage
overlap = 0.5        # 50% overlap for averaging
```

### For Steady-State (Sweep, Noise)

```python
fft_size = 16384     # Better resolution
window = "hanning"
overlap = 0.75       # More averages per unit time
```

### For Amplitude-Critical Measurements

```python
fft_size = 8192
window = "flat_top"  # Accurate amplitude
overlap = 0.5
```

## Zero Padding

Adding zeros to the end of a signal before FFT:
- **Does**: Interpolate between frequency bins (smoother display)
- **Does NOT**: Improve actual frequency resolution

```python
# Original: 4096 samples → 11.7 Hz bins
# Zero-padded to 16384 → 2.9 Hz bins (but same actual resolution)
```

Useful for finding peak frequencies more precisely, but doesn't reveal new information.

## Aliasing

Frequencies above fs/2 "fold back" into the measurement range:

```
True frequency: 25000 Hz
Sample rate: 48000 Hz
Apparent frequency: 48000 - 25000 = 23000 Hz
```

**Prevention**: Use anti-aliasing filter (built into most ADCs) and ensure your
signal bandwidth doesn't exceed fs/2.

## Summary: FFT Checklist

1. **Choose block size** based on required frequency resolution
2. **Choose window** based on signal type and measurement goal
3. **Apply correct scaling** for amplitude accuracy
4. **Verify sample rate** is at least 2× your maximum frequency of interest
5. **Use averaging** to reduce noise (see [Uncertainty and Averaging](uncertainty_averaging.md))

## Code Example

```python
import numpy as np
from scipy.signal import get_window

def compute_spectrum(signal, sample_rate, window='hanning', fft_size=None):
    """
    Compute properly scaled magnitude spectrum.
    """
    if fft_size is None:
        fft_size = len(signal)

    # Apply window
    window = get_window(window, len(signal))
    windowed = signal * window

    # Coherent gain for amplitude correction
    coherent_gain = np.sum(window) / len(window)

    # Compute FFT
    spectrum = np.fft.rfft(windowed, n=fft_size)
    freqs = np.fft.rfftfreq(fft_size, 1/sample_rate)

    # Scale for single-sided spectrum
    magnitude = np.abs(spectrum) * 2 / len(signal) / coherent_gain
    magnitude[0] /= 2  # DC bin
    if len(spectrum) == fft_size // 2 + 1:
        magnitude[-1] /= 2  # Nyquist bin

    return freqs, magnitude
```

## Related Topics

- [Coherence Interpretation](coherence_interpretation.md) - Uses averaged cross-spectra
- [Transfer Functions](transfer_function.md) - Ratios of spectra
- [Uncertainty and Averaging](uncertainty_averaging.md) - Why we average FFTs
